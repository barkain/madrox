"""MCP Protocol implementation for Claude Orchestrator - Unified elegant design."""

import logging
from typing import Any

from fastmcp import FastMCP

from src.orchestrator.instance_manager import InstanceManager
from src.orchestrator.simple_models import OrchestratorConfig

logger = logging.getLogger(__name__)


class OrchestrationMCPServer:
    """MCP Server for Claude Orchestration.

    For STDIO mode, we create a separate FastMCP instance and manually register
    wrapper functions that bind to the manager instance. This avoids the issue
    of FastMCP not knowing which InstanceManager instance to use for method calls.
    """

    def __init__(self, config: OrchestratorConfig):
        """Initialize MCP server with orchestrator config.

        Args:
            config: Orchestrator configuration
        """
        self.config = config

        # Initialize InstanceManager
        self.manager = InstanceManager(config.to_dict())

        # Create a NEW FastMCP instance for STDIO mode (don't use module-level one)
        self.mcp = FastMCP("claude-orchestrator-stdio")

        # Register bound wrapper functions for all tools
        self._register_bound_tools()

        logger.info("OrchestrationMCPServer initialized with bound tool wrappers for STDIO")

    def _register_bound_tools(self):
        """Register wrapper functions that bind to self.manager instance."""

        # For each tool in the manager's mcp, create a bound wrapper
        # Note: We can't use the module-level mcp tools because they have unbound methods
        # Instead, we manually register functions that call the manager instance methods

        @self.mcp.tool()
        async def reply_to_caller(
            instance_id: str,
            reply_message: str,
            correlation_id: str | None = None,
        ) -> dict[str, Any]:
            """Reply back to the instance/coordinator that sent you a message."""
            return await self.manager.handle_reply_to_caller(
                instance_id=instance_id,
                reply_message=reply_message,
                correlation_id=correlation_id,
            )

        # Add more tool wrappers as needed...
        # For now, just registering reply_to_caller to test the fix

    async def run(self):
        """Get the FastMCP server instance for running."""
        return self.mcp
