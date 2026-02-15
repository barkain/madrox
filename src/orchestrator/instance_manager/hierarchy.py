"""Instance hierarchy, status, and tree visualization MCP tools."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..compat import UTC
from ._mcp import mcp

logger = logging.getLogger(__name__)


class HierarchyMixin:
    """MCP tools for querying instance hierarchy and status."""

    # Declared by InstanceManager; present here for type checking only
    instances: dict[str, dict[str, Any]]
    total_tokens_used: int
    total_cost: float
    config: dict[str, Any]
    shared_state_manager: Any

    def _get_instance_status_internal(
        self, instance_id: str | None = None, summary_only: bool = False
    ) -> dict[str, Any]:
        """Internal method to get status of instance(s)."""
        all_instances = dict(self.instances)

        if hasattr(self, "shared_state_manager") and self.shared_state_manager:
            try:
                for iid, metadata in self.shared_state_manager.instance_metadata.items():
                    if iid not in all_instances:
                        all_instances[iid] = dict(metadata)
            except Exception as e:
                logger.warning(f"Failed to read shared instance metadata: {e}")

        if instance_id:
            if instance_id not in all_instances:
                raise ValueError(f"Instance {instance_id} not found")
            return all_instances[instance_id].copy()
        else:
            if summary_only:
                return {
                    "instances": {
                        iid: {
                            "id": inst["id"],
                            "name": inst["name"],
                            "state": inst["state"],
                            "role": inst["role"],
                        }
                        for iid, inst in all_instances.items()
                    },
                    "total_instances": len(all_instances),
                    "active_instances": len(
                        [
                            i
                            for i in all_instances.values()
                            if i["state"] in ["running", "idle", "busy"]
                        ]
                    ),
                }
            else:
                return {
                    "instances": {iid: inst.copy() for iid, inst in all_instances.items()},
                    "total_instances": len(all_instances),
                    "active_instances": len(
                        [
                            i
                            for i in all_instances.values()
                            if i["state"] in ["running", "idle", "busy"]
                        ]
                    ),
                    "total_tokens_used": self.total_tokens_used,
                    "total_cost": self.total_cost,
                }

    @mcp.tool
    def get_instance_status(
        self,
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        """Get status for a single instance or all instances.

        Args:
            instance_id: Optional instance ID (omit for all instances)

        Returns:
            Dictionary with instance status information
        """
        return self._get_instance_status_internal(instance_id=instance_id)

    @mcp.tool
    async def get_live_instance_status(
        self,
        instance_id: str,
    ) -> dict[str, Any]:
        """Get live status with execution time and last activity for an instance.

        Args:
            instance_id: Instance ID

        Returns:
            Dictionary with live status including execution_time, state, last_activity
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        created_at = datetime.fromisoformat(instance["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        current_time = datetime.now(UTC)
        execution_time = (current_time - created_at).total_seconds()

        return {
            "instance_id": instance_id,
            "execution_time": execution_time,
            "state": instance["state"],
            "last_activity": instance["last_activity"],
            "name": instance.get("name"),
            "role": instance.get("role"),
        }

    def _get_children_internal(
        self, parent_id: str, include_terminated: bool = False
    ) -> list[dict[str, Any]]:
        """Internal method to get all child instances of a parent."""
        children = []

        all_instances = dict(self.instances)
        if hasattr(self, "shared_state_manager") and self.shared_state_manager:
            try:
                for iid, metadata in self.shared_state_manager.instance_metadata.items():
                    if iid not in all_instances:
                        all_instances[iid] = dict(metadata)
            except Exception as e:
                logger.warning(f"Failed to read shared instance metadata in get_children: {e}")

        for instance_id, instance in all_instances.items():
            is_child = instance.get("parent_instance_id") == parent_id
            include = is_child and (include_terminated or instance.get("state") != "terminated")
            if include:
                children.append(
                    {
                        "id": instance_id,
                        "name": instance.get("name"),
                        "role": instance.get("role"),
                        "state": instance.get("state"),
                        "instance_type": instance.get("instance_type"),
                    }
                )

        if include_terminated:
            artifacts_base = Path(self.config.get("artifacts_dir", "/tmp/madrox_logs/artifacts"))
            if artifacts_base.exists():
                import json

                for artifact_dir in artifacts_base.iterdir():
                    if not artifact_dir.is_dir():
                        continue

                    instance_id = artifact_dir.name
                    if any(c["id"] == instance_id for c in children):
                        continue

                    metadata_path = artifact_dir / "_metadata.json"
                    if metadata_path.exists():
                        try:
                            with open(metadata_path) as f:
                                metadata = json.load(f)

                            if metadata.get("parent_instance_id") == parent_id:
                                children.append(
                                    {
                                        "id": instance_id,
                                        "name": metadata.get("instance_name", "unknown"),
                                        "role": metadata.get("role", "unknown"),
                                        "state": "terminated",
                                        "instance_type": metadata.get("instance_type", "claude"),
                                    }
                                )
                        except Exception as e:
                            logger.warning(f"Failed to load metadata for {instance_id}: {e}")

        return children

    @mcp.tool
    def get_children(self, parent_id: str) -> list[dict[str, Any]]:
        """Get all child instances of a parent.

        Args:
            parent_id: Parent instance ID

        Returns:
            List of child instance details (excludes terminated instances)
        """
        return self._get_children_internal(parent_id)

    def _get_peers_internal(
        self, instance_id: str, include_self: bool = False
    ) -> list[dict[str, Any]]:
        """Internal method to get all peer instances (siblings sharing the same parent)."""
        all_instances = dict(self.instances)
        if hasattr(self, "shared_state_manager") and self.shared_state_manager:
            try:
                for iid, metadata in self.shared_state_manager.instance_metadata.items():
                    if iid not in all_instances:
                        all_instances[iid] = dict(metadata)
            except Exception as e:
                logger.warning(f"Failed to read shared instance metadata in get_peers: {e}")

        instance = all_instances.get(instance_id)
        if not instance:
            return []

        parent_id = instance.get("parent_instance_id")
        if not parent_id:
            return []

        peers = []
        for iid, inst in all_instances.items():
            if inst.get("parent_instance_id") != parent_id:
                continue
            if inst.get("state") == "terminated":
                continue
            if not include_self and iid == instance_id:
                continue
            peers.append(
                {
                    "id": iid,
                    "name": inst.get("name"),
                    "role": inst.get("role"),
                    "state": inst.get("state"),
                    "instance_type": inst.get("instance_type"),
                }
            )
        return peers

    @mcp.tool
    def get_peers(self, instance_id: str) -> list[dict[str, Any]]:
        """Get all peer instances (siblings that share the same parent).

        Use this to discover teammates for direct peer-to-peer communication.
        After discovering peers, use send_to_instance(instance_id=peer_id, message='...')
        to message them directly.

        Args:
            instance_id: Your own instance ID

        Returns:
            List of peer instance details (excludes terminated instances and self)
        """
        return self._get_peers_internal(instance_id)

    @mcp.tool
    def get_instance_tree(self) -> str:
        """Build a hierarchical tree view of all instances.

        Returns:
            Formatted tree string showing instance hierarchy
        """
        roots = []
        for instance_id, instance in self.instances.items():
            if not instance.get("parent_instance_id") and instance.get("state") != "terminated":
                roots.append((instance_id, instance.get("name", "unknown")))

        if not roots:
            return "No instances running"

        roots.sort(key=lambda x: x[1])

        lines: list[str] = []
        for i, (root_id, _) in enumerate(roots):
            is_last_root = i == len(roots) - 1
            self._build_tree_recursive(root_id, "", is_last_root, lines, is_root=True)

        return "\n".join(lines)

    def _build_tree_recursive(
        self, instance_id: str, prefix: str, is_last: bool, lines: list[str], is_root: bool = False
    ) -> None:
        """Recursively build tree structure."""
        instance = self.instances.get(instance_id)
        if not instance:
            return

        if is_root:
            connector = ""
        else:
            connector = "└── " if is_last else "├── "

        name = instance.get("name", "unknown")
        short_id = instance_id[:8] + "..."
        state = instance.get("state", "unknown")
        instance_type = instance.get("instance_type", "claude")

        line = f"{prefix}{connector}{name} ({short_id}) [{state}] ({instance_type})"
        lines.append(line)

        children = self._get_children_internal(instance_id)
        child_count = len(children)

        children.sort(key=lambda x: x.get("name") or "")

        for i, child in enumerate(children):
            is_last_child = i == child_count - 1
            if is_root:
                new_prefix = ""
            else:
                new_prefix = prefix + ("    " if is_last else "│   ")
            self._build_tree_recursive(child["id"], new_prefix, is_last_child, lines)
