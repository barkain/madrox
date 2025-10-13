"""MCP Protocol implementation for Claude Orchestrator - Unified elegant design."""

import logging

from src.orchestrator.instance_manager import InstanceManager
from src.orchestrator.simple_models import OrchestratorConfig

logger = logging.getLogger(__name__)


class OrchestrationMCPServer:
    """MCP Server for Claude Orchestration using elegant unified design.

    All MCP tools are registered directly on InstanceManager methods using
    FastMCP's @mcp.tool() decorator at module level, eliminating wrapper functions.
    """

    def __init__(self, config: OrchestratorConfig):
        """Initialize MCP server with orchestrator config.

        Args:
            config: Orchestrator configuration
        """
        self.config = config

        # Initialize InstanceManager - it creates and uses module-level mcp instance
        self.manager = InstanceManager(config.to_dict())

        # Reference the manager's mcp instance (which is the module-level mcp)
        self.mcp = self.manager.mcp

        logger.info("OrchestrationMCPServer initialized with direct-decorated MCP tools")

    async def run(self):
        """Get the FastMCP server instance for running."""
        return self.mcp
