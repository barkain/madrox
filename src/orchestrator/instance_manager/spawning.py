"""Instance spawning MCP tools and helpers."""

import logging
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
    ) -> dict[str, Any]:
        """Spawn a new Claude instance with specific role and configuration.

        Args:
            name: Instance name
            role: Predefined role for the instance
            system_prompt: Custom system prompt (overrides role)
            model: Claude model to use. Options:
                   - claude-sonnet-4-5 (default, recommended, smartest model for daily use)
                   - claude-opus-4-1 (legacy, reaches usage limits faster)
                   - claude-haiku-4-5 (fastest model for simple tasks)
            bypass_isolation: Allow full filesystem access (default: true)
            parent_instance_id: Parent instance ID for tracking bidirectional communication
            wait_for_ready: Wait for instance to initialize (default: true)
            initial_prompt: Initial prompt to send as CLI argument (bypasses paste detection)
            mcp_servers: JSON string of MCP server configurations. Format:
                        '{"server_name": {"transport": "http", "url": "http://localhost:8002/mcp"}}'

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
        )
        return {"instance_id": instance_id, "status": "spawned", "name": name}

    @mcp.tool
    async def spawn_multiple_instances(
        self,
        instances: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Spawn multiple Claude instances in parallel for better performance.

        Args:
            instances: List of instance configurations to spawn

        Returns:
            Dictionary with spawned instance IDs and any errors
        """
        results: dict[str, list[Any]] = {"spawned": [], "errors": []}
        for instance_config in instances:
            try:
                instance_id = await self.spawn_instance(**instance_config)
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
        bypass_isolation: bool = False,
        parent_instance_id: str | None = None,
        mcp_servers: str | None = None,
    ) -> dict[str, Any]:
        """Spawn a new Codex CLI instance (OpenAI GPT models only).

        Args:
            name: Instance name
            model: OpenAI GPT model to use. Options:
                   - gpt-5-codex (default and only allowed model)
            sandbox_mode: Sandbox policy for shell commands (read-only, workspace-write, danger-full-access)
            profile: Configuration profile from config.toml
            initial_prompt: Initial prompt to start the session
            bypass_isolation: Allow full filesystem access
            parent_instance_id: Parent instance ID for tracking
            mcp_servers: JSON string of MCP server configurations. Format:
                        '{"server_name": {"transport": "http", "url": "http://localhost:8002/mcp"}}'

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
        )
        self.instances[instance_id]["instance_type"] = "codex"
        return {
            "instance_id": instance_id,
            "status": "spawned",
            "name": name,
            "instance_type": "codex",
        }
