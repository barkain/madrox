"""Helper utilities for loading and managing MCP server configurations."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MCPConfigLoader:
    """Load and manage MCP server configurations from resources/mcp_configs."""

    def __init__(self):
        """Initialize the MCP config loader."""
        # Get the project root directory
        current_file = Path(__file__)
        self.project_root = current_file.parent.parent.parent
        self.configs_dir = self.project_root / "resources" / "mcp_configs"

    def list_available_configs(self) -> list[str]:
        """List all available MCP configuration names.

        Returns:
            List of available MCP server names
        """
        if not self.configs_dir.exists():
            logger.warning(f"MCP configs directory not found: {self.configs_dir}")
            return []

        configs = []
        for config_file in self.configs_dir.glob("*.json"):
            if config_file.name != "README.md":
                configs.append(config_file.stem)

        return sorted(configs)

    def load_config(self, name: str) -> dict | None:
        """Load a specific MCP configuration by name.

        Args:
            name: Name of the MCP server (e.g., 'playwright', 'github')

        Returns:
            Configuration dict with 'name', 'description', 'config', etc., or None if not found
        """
        config_path = self.configs_dir / f"{name}.json"

        if not config_path.exists():
            logger.error(f"MCP config not found: {name}")
            return None

        try:
            with open(config_path) as f:
                config_data = json.load(f)
            logger.debug(f"Loaded MCP config: {name}")
            return config_data
        except Exception as e:
            logger.error(f"Error loading MCP config '{name}': {e}")
            return None

    def get_mcp_servers_dict(self, *names: str, **custom_configs: dict) -> dict:
        """Build an mcp_servers dict for spawn_instance from config names and custom configs.

        Args:
            *names: Names of MCP configs to load (e.g., 'playwright', 'github')
            **custom_configs: Additional custom MCP server configs

        Returns:
            Dict suitable for passing to spawn_instance's mcp_servers parameter

        Example:
            >>> loader = MCPConfigLoader()
            >>> mcp_servers = loader.get_mcp_servers_dict(
            ...     'playwright',
            ...     'github',
            ...     custom_api={'command': 'python', 'args': ['server.py']}
            ... )
            >>> instance_id = await manager.spawn_instance(
            ...     name='agent',
            ...     mcp_servers=mcp_servers
            ... )
        """
        mcp_servers = {}

        # Load named configs
        for name in names:
            config_data = self.load_config(name)
            if config_data:
                mcp_servers[config_data["name"]] = config_data["config"]
            else:
                logger.warning(f"Skipping unavailable MCP config: {name}")

        # Add custom configs
        mcp_servers.update(custom_configs)

        return mcp_servers

    def load_with_overrides(
        self, name: str, args_overrides: list[str] | None = None, env_overrides: dict | None = None
    ) -> dict | None:
        """Load a config with argument and environment overrides.

        Useful for configs that need customization (e.g., filesystem paths, DB connections).

        Args:
            name: Name of the MCP server config
            args_overrides: Override the args field in the config
            env_overrides: Override environment variables

        Returns:
            Modified configuration dict, or None if config not found

        Example:
            >>> loader = MCPConfigLoader()
            >>> filesystem_config = loader.load_with_overrides(
            ...     'filesystem',
            ...     args_overrides=['-y', '@modelcontextprotocol/server-filesystem', '/home/user/data']
            ... )
        """
        config_data = self.load_config(name)
        if not config_data:
            return None

        # Override args if provided
        if args_overrides is not None:
            config_data["config"]["args"] = args_overrides

        # Override env if provided
        if env_overrides is not None:
            if "env" not in config_data:
                config_data["env"] = {}
            config_data["env"].update(env_overrides)

        return config_data


# Convenience function for quick access
def get_mcp_servers(*names: str, **custom_configs: dict) -> dict:
    """Quick helper to get MCP servers dict.

    Args:
        *names: Names of MCP configs to load
        **custom_configs: Additional custom MCP server configs

    Returns:
        Dict suitable for passing to spawn_instance's mcp_servers parameter

    Example:
        >>> from orchestrator.mcp_loader import get_mcp_servers
        >>> mcp_servers = get_mcp_servers('playwright', 'github')
        >>> instance_id = await manager.spawn_instance(name='agent', mcp_servers=mcp_servers)
    """
    loader = MCPConfigLoader()
    return loader.get_mcp_servers_dict(*names, **custom_configs)
