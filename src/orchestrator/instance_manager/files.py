"""Instance file operations MCP tools."""

import logging
from pathlib import Path
from typing import Any

from ._mcp import mcp

logger = logging.getLogger(__name__)


class FilesMixin:
    """MCP tools for retrieving and listing instance workspace files."""

    # Declared by InstanceManager; present here for type checking only
    instances: dict[str, dict[str, Any]]

    async def _retrieve_instance_file_internal(
        self, instance_id: str, filename: str, destination_path: str | None = None
    ) -> str | None:
        """Internal method to retrieve a file from an instance's workspace directory."""
        if instance_id not in self.instances:
            logger.error(f"Instance {instance_id} not found")
            return None

        instance = self.instances[instance_id]
        workspace_dir = Path(instance["workspace_dir"])
        source_file = workspace_dir / filename

        if not source_file.exists():
            logger.warning(f"File {filename} not found in instance {instance_id} workspace")
            return None

        if destination_path:
            dest = Path(destination_path)
            if dest.is_dir():
                dest = dest / filename
        else:
            dest = Path.cwd() / filename

        try:
            import shutil

            shutil.copy2(source_file, dest)
            logger.info(f"Retrieved file {filename} from instance {instance_id} to {dest}")
            return str(dest)
        except Exception as e:
            logger.error(f"Failed to retrieve file: {e}")
            return None

    @mcp.tool
    async def retrieve_instance_file(
        self, instance_id: str, filename: str, destination_path: str | None = None
    ) -> str | None:
        """Retrieve a file from an instance's workspace directory.

        Args:
            instance_id: The instance ID
            filename: Name of the file to retrieve
            destination_path: Optional destination path (defaults to current directory)

        Returns:
            Path to the retrieved file, or None if not found
        """
        return await self._retrieve_instance_file_internal(instance_id, filename, destination_path)

    @mcp.tool
    async def retrieve_multiple_instance_files(
        self,
        retrievals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Retrieve files from multiple instances.

        Args:
            retrievals: List of dicts with instance_id, filename, destination_path

        Returns:
            Dictionary with retrieved file paths and errors
        """
        results: dict[str, list[Any]] = {"retrieved": [], "errors": []}
        for retrieval in retrievals:
            try:
                instance_id = retrieval["instance_id"]
                filename = retrieval["filename"]
                destination_path = retrieval.get("destination_path")

                path = await self._retrieve_instance_file_internal(
                    instance_id, filename, destination_path
                )
                if path:
                    results["retrieved"].append(
                        {
                            "instance_id": instance_id,
                            "filename": filename,
                            "path": path,
                        }
                    )
                else:
                    results["errors"].append(
                        {
                            "instance_id": instance_id,
                            "filename": filename,
                            "error": "File not found",
                        }
                    )
            except Exception as e:
                results["errors"].append(
                    {
                        "instance_id": retrieval.get("instance_id"),
                        "filename": retrieval.get("filename"),
                        "error": str(e),
                    }
                )
        return results

    async def _list_instance_files_internal(self, instance_id: str) -> list[str] | None:
        """Internal method to list all files in an instance's workspace directory."""
        if instance_id not in self.instances:
            logger.error(f"Instance {instance_id} not found")
            return None

        instance = self.instances[instance_id]
        workspace_dir = Path(instance["workspace_dir"])

        if not workspace_dir.exists():
            logger.warning(f"Workspace directory for instance {instance_id} does not exist")
            return []

        try:
            files = []
            for item in workspace_dir.rglob("*"):
                if item.is_file():
                    relative_path = item.relative_to(workspace_dir)
                    files.append(str(relative_path))

            logger.debug(f"Found {len(files)} files in instance {instance_id} workspace")
            return sorted(files)
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    @mcp.tool
    async def list_instance_files(self, instance_id: str) -> list[str] | None:
        """List all files in an instance's workspace directory.

        Args:
            instance_id: The instance ID

        Returns:
            List of file paths relative to workspace, or None if instance not found
        """
        return await self._list_instance_files_internal(instance_id)

    @mcp.tool
    async def list_multiple_instance_files(
        self,
        instance_ids: list[str],
    ) -> dict[str, Any]:
        """List files for multiple instances.

        Args:
            instance_ids: List of instance IDs

        Returns:
            Dictionary with file listings and errors for each instance
        """
        results: dict[str, list[Any]] = {"listings": [], "errors": []}
        for instance_id in instance_ids:
            try:
                files = await self._list_instance_files_internal(instance_id)
                if files is not None:
                    results["listings"].append(
                        {
                            "instance_id": instance_id,
                            "files": files,
                            "file_count": len(files),
                        }
                    )
                else:
                    results["errors"].append(
                        {
                            "instance_id": instance_id,
                            "error": "Instance not found",
                        }
                    )
            except Exception as e:
                results["errors"].append(
                    {
                        "instance_id": instance_id,
                        "error": str(e),
                    }
                )
        return results
