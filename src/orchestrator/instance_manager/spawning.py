"""Instance spawning MCP tools and helpers."""

import logging
from pathlib import Path
from typing import Any

from ..config import validate_model
from ._mcp import mcp

logger = logging.getLogger(__name__)


class SpawningMixin:
    """MCP tools for spawning Claude and Codex instances."""

    # Declared by InstanceManager; present here for type checking only
    instances: dict[str, dict[str, Any]]
    tmux_manager: Any
    spawn_instance: Any

    @mcp.tool
    async def spawn_claude(
        self,
        name: str,
        role: str = "general",
        system_prompt: str | None = None,
        model: str | None = None,
        bypass_isolation: bool = True,
        parent_instance_id: str | None = None,
        wait_for_ready: bool = True,
        initial_prompt: str | None = None,
        mcp_servers: str | None = None,
        use_worktree: bool = False,
        git_repo: str | None = None,
    ) -> dict[str, Any]:
        """Spawn a new Claude instance with specific role and configuration.

        Args:
            name: Instance name
            role: Predefined role for the instance
            system_prompt: Custom system prompt (overrides role)
            model: Claude model to use. Options:
                   - claude-sonnet-4-5 (default, recommended, smartest model for daily use)
                   - claude-opus-4-6 (latest Opus, most capable)
                   - claude-opus-4-1 (legacy, reaches usage limits faster)
                   - claude-haiku-4-5 (fastest model for simple tasks)
            bypass_isolation: Allow full filesystem access (default: true)
            parent_instance_id: Parent instance ID for tracking bidirectional communication
            wait_for_ready: Wait for instance to initialize (default: true)
            initial_prompt: Initial prompt to send as CLI argument (bypasses paste detection)
            mcp_servers: JSON string of MCP server configurations. Format:
                        '{"server_name": {"transport": "http", "url": "http://localhost:8002/mcp"}}'
            use_worktree: Create a git worktree for workspace isolation (default: false)
            git_repo: Path to git repository for worktree creation (required if use_worktree is true)

        Returns:
            Dictionary with instance_id and status
        """
        validated_model = validate_model("claude", model)

        instance_id = await self.spawn_instance(
            name=name,
            role=role,
            system_prompt=system_prompt,
            model=validated_model,
            bypass_isolation=bypass_isolation,
            parent_instance_id=parent_instance_id,
            wait_for_ready=wait_for_ready,
            initial_prompt=initial_prompt,
            mcp_servers=mcp_servers,
            use_worktree=use_worktree,
            git_repo=git_repo,
        )
        return {"instance_id": instance_id, "status": "spawned", "name": name}

    @mcp.tool
    async def spawn_multiple_instances(
        self,
        instances: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Spawn multiple Claude or Codex instances in parallel for better performance.

        Args:
            instances: List of instance configurations to spawn.
                       Each config supports: name, type ("claude" or "codex"),
                       role, system_prompt, model, initial_prompt, bypass_isolation,
                       sandbox_mode (codex only), parent_instance_id, use_worktree, git_repo.

        Returns:
            Dictionary with spawned instance IDs and any errors
        """
        results: dict[str, list[Any]] = {"spawned": [], "errors": []}
        for instance_config in instances:
            try:
                # Map "type" to "instance_type" for spawn_instance()
                config = dict(instance_config)
                if "type" in config:
                    config["instance_type"] = config.pop("type")
                instance_id = await self.spawn_instance(**config)
                results["spawned"].append({"instance_id": instance_id, **instance_config})
            except Exception as e:
                results["errors"].append({"config": instance_config, "error": str(e)})
        return results

    @mcp.tool
    async def spawn_codex(
        self,
        name: str,
        model: str | None = None,
        sandbox_mode: str = "workspace-write",
        profile: str | None = None,
        initial_prompt: str | None = None,
        bypass_isolation: bool = True,
        parent_instance_id: str | None = None,
        mcp_servers: str | None = None,
        use_worktree: bool = False,
        git_repo: str | None = None,
    ) -> dict[str, Any]:
        """Spawn a new Codex CLI instance (OpenAI GPT models only).

        Args:
            name: Instance name
            model: OpenAI GPT model to use. Options:
                   - gpt-5-codex (default)
                   - gpt-5.3-codex
                   - gpt-5.4
            sandbox_mode: Sandbox policy for shell commands (read-only, workspace-write, danger-full-access)
            profile: Configuration profile from config.toml
            initial_prompt: Initial prompt to start the session
            bypass_isolation: Allow full filesystem access
            parent_instance_id: Parent instance ID for tracking
            mcp_servers: JSON string of MCP server configurations. Format:
                        '{"server_name": {"transport": "http", "url": "http://localhost:8002/mcp"}}'
            use_worktree: Create a git worktree for workspace isolation (default: false)
            git_repo: Path to git repository for worktree creation (required if use_worktree is true)

        Returns:
            Dictionary with instance_id and status
        """
        validated_model = validate_model("codex", model)

        instance_id = await self.spawn_instance(
            name=name,
            model=validated_model,
            bypass_isolation=bypass_isolation,
            sandbox_mode=sandbox_mode,
            profile=profile,
            initial_prompt=initial_prompt,
            instance_type="codex",
            parent_instance_id=parent_instance_id,
            mcp_servers=mcp_servers,
            use_worktree=use_worktree,
            git_repo=git_repo,
        )
        self.instances[instance_id]["instance_type"] = "codex"
        return {
            "instance_id": instance_id,
            "status": "spawned",
            "name": name,
            "instance_type": "codex",
        }

    def list_persisted_instances(self) -> dict[str, Any]:
        """List all persisted instances from previous sessions that can be resumed.

        Returns instances whose workspace directories still exist, meaning their
        conversation context can be resumed with resume_instance.

        Returns:
            Dictionary with resumable instances and their metadata
        """
        state_store = self.tmux_manager.state_store
        if not state_store:
            return {"instances": [], "message": "State store not configured"}

        all_persisted = state_store.load_all()
        resumable = []

        for iid, record in all_persisted.items():
            workspace = record.get("workspace_dir", "")
            ws_exists = Path(workspace).exists() if workspace else False

            # Check if already active in current session
            already_active = iid in self.instances and self.instances[iid].get("state") not in (
                "terminated",
                "error",
            )

            resumable.append(
                {
                    "instance_id": iid,
                    "name": record.get("name"),
                    "role": record.get("role"),
                    "model": record.get("model"),
                    "state": record.get("state"),
                    "instance_type": record.get("instance_type", "claude"),
                    "created_at": record.get("created_at"),
                    "last_activity": record.get("last_activity"),
                    "workspace_dir": workspace,
                    "workspace_exists": ws_exists,
                    "can_resume": ws_exists and not already_active,
                    "already_active": already_active,
                }
            )

        return {
            "instances": resumable,
            "total": len(resumable),
            "resumable": len([r for r in resumable if r["can_resume"]]),
            "active": len([r for r in resumable if r["already_active"]]),
        }

    async def resume_instance(
        self,
        instance_id: str,
        name: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Resume a previous instance's conversation context in a new instance.

        Spawns a new Claude instance in the previous instance's workspace directory
        using --continue to pick up its full conversation history.

        Args:
            instance_id: ID of the previous instance to resume (from list_persisted_instances)
            name: Optional new name (defaults to previous name + "-resumed")
            model: Optional model override (defaults to previous instance's model)

        Returns:
            Dictionary with new instance_id and status
        """
        state_store = self.tmux_manager.state_store
        if not state_store:
            raise RuntimeError("State store not configured — cannot resume instances")

        all_persisted = state_store.load_all()
        if instance_id not in all_persisted:
            raise ValueError(
                f"Instance {instance_id} not found in persisted state. "
                f"Use list_persisted_instances to see available instances."
            )

        record = all_persisted[instance_id]
        workspace = record.get("workspace_dir", "")

        if not Path(workspace).exists():
            raise RuntimeError(
                f"Workspace {workspace} no longer exists — conversation context is lost"
            )

        # Check if already active
        if instance_id in self.instances and self.instances[instance_id].get("state") not in (
            "terminated",
            "error",
        ):
            raise RuntimeError(
                f"Instance {instance_id} is already active (state={self.instances[instance_id]['state']}). "
                f"Use send_to_instance to communicate with it directly."
            )

        resumed_name = name or f"{record.get('name', 'instance')}-resumed"
        resumed_model = model or record.get("model")

        # Use the recovery path which spawns with --continue in existing workspace
        record["id"] = instance_id
        record["retry_count"] = record.get("retry_count", 0)
        if resumed_name != record.get("name"):
            record["name"] = resumed_name
        if resumed_model:
            record["model"] = resumed_model

        new_id = self.tmux_manager.recover_instance(record)
        self.instances[new_id] = self.tmux_manager.instances[new_id]

        return {
            "instance_id": new_id,
            "name": resumed_name,
            "status": "resuming",
            "resumed_from": instance_id,
            "workspace_dir": workspace,
            "message": "Resuming conversation context from previous instance. "
            "The instance will be ready shortly with full conversation history.",
        }
