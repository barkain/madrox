"""MCP Protocol implementation for Claude Orchestrator - Dynamic tool binding."""

import logging

from fastmcp import FastMCP

from src.orchestrator.instance_manager import InstanceManager
from src.orchestrator.simple_models import OrchestratorConfig

logger = logging.getLogger(__name__)


class OrchestrationMCPServer:
    """MCP Server for Claude Orchestration.

    For STDIO mode, we create wrapper functions that properly bind to the InstanceManager
    instance. This ensures all tool calls are routed to the correct manager methods with
    proper self binding.
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

        # Dynamically register all tools from manager with proper binding
        self._register_bound_tools()

        logger.info(
            f"OrchestrationMCPServer initialized with {len(self.mcp._tool_manager._tools)} bound tools"
        )

    def _register_bound_tools(self):
        """Dynamically register all tools from InstanceManager with proper self binding.

        Binds unbound instance methods to self.manager, then registers the bound methods.
        Bound methods have 'self' already resolved, so they register cleanly with FastMCP.
        """
        # Get all tools from the manager's mcp instance
        source_tools = self.manager.mcp._tool_manager._tools

        registered_count = 0
        for tool_name, tool_func in source_tools.items():
            # Get the original function from the FunctionTool
            original_func = tool_func.fn

            # Bind the unbound method to self.manager using descriptor protocol
            # This removes 'self' from the signature by pre-binding it
            bound_method = original_func.__get__(self.manager, type(self.manager))

            # Register the bound method (no exclude_args needed - 'self' already bound)
            self.mcp.tool()(bound_method)

            registered_count += 1

        logger.info(
            f"Registered {registered_count} bound tools (self parameter pre-bound)"
        )

    async def run(self):
        """Get the FastMCP server instance for running."""
        return self.mcp
