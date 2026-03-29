"""MCP Protocol implementation - STDIO proxy to parent HTTP server.

Instead of creating a duplicate InstanceManager, this STDIO server proxies
all MCP tool calls to the parent HTTP server's /tools/execute endpoint.
This ensures a single source of truth for instance state.
"""

import inspect
import logging
import os
from typing import get_type_hints

import httpx
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def _make_proxy_fn(server: "OrchestrationMCPServer", tool_name: str, original_fn):
    """Create a proxy function that matches the original's signature.

    Uses exec() to generate a function with the exact parameter names and
    type annotations that FastMCP/Pydantic expects. The generated function
    forwards all calls to the parent HTTP server.
    """
    sig = inspect.signature(original_fn)
    params = [(name, p) for name, p in sig.parameters.items() if name != "self"]

    # Build function parameter string (e.g. "instance_id: str, message: str, ...")
    param_strs = []
    for name, _p in params:
        param_strs.append(name)

    params_str = ", ".join(param_strs)
    kwargs_str = ", ".join(f'"{name}": {name}' for name, _ in params)

    # Generate a proper async function with matching parameter names
    func_code = f"""
async def {tool_name}({params_str}):
    return await _server._call_parent("{tool_name}", {{{kwargs_str}}})
"""

    # Get type hints from original function (excluding 'self' and 'return')
    try:
        hints = get_type_hints(original_fn)
    except Exception:
        hints = getattr(original_fn, "__annotations__", {})
    local_hints = {k: v for k, v in hints.items() if k != "self" and k != "return"}

    # Execute in a namespace with the server reference and type annotations available
    namespace = {"_server": server, **local_hints}
    exec(func_code, namespace)  # noqa: S102

    fn = namespace[tool_name]
    fn.__doc__ = original_fn.__doc__
    fn.__module__ = __name__

    # Set annotations from original function (minus 'self' and 'return')
    fn.__annotations__ = local_hints

    return fn


class OrchestrationMCPServer:
    """STDIO MCP proxy server that forwards all tool calls to the parent HTTP server.

    When Codex (or other STDIO MCP clients) call tools, this proxy forwards
    them to the parent Madrox HTTP server which manages all instances and
    tmux sessions. This avoids the problem of isolated InstanceManagers with
    empty registries.
    """

    def __init__(self, parent_url: str | None = None):
        """Initialize proxy MCP server.

        Args:
            parent_url: URL of the parent HTTP server (e.g. http://localhost:8001).
                       Auto-detected from MADROX_PARENT_URL env var if not provided.
        """
        default_port = os.getenv("ORCHESTRATOR_PORT", "8001")
        self.parent_url = parent_url or os.getenv("MADROX_PARENT_URL", f"http://localhost:{default_port}")
        self.mcp = FastMCP("claude-orchestrator-stdio-proxy")

        # Register proxy tools by introspecting InstanceManager's tool schemas
        self._register_proxy_tools()

        logger.info(
            f"Proxy MCP server initialized: {len(self.mcp._tool_manager._tools)} tools → {self.parent_url}"
        )

    def _register_proxy_tools(self):
        """Register all tools as proxies to the parent HTTP server.

        Introspects InstanceManager's @mcp.tool methods to get their names,
        signatures, and docstrings, then creates proxy functions with matching
        schemas that forward calls via HTTP.
        """
        from orchestrator.instance_manager._mcp import mcp as source_mcp

        source_tools = source_mcp._tool_manager._tools

        for tool_name, tool_func in source_tools.items():
            original_fn = tool_func.fn
            proxy_fn = _make_proxy_fn(self, tool_name, original_fn)
            self.mcp.tool()(proxy_fn)

        # Register local-only tools (not proxied to parent)
        @self.mcp.tool
        async def get_dashboard_url() -> str:
            """Get the URL for the Madrox Monitor dashboard.

            Returns:
                The dashboard URL with the correct port for this session.
            """
            port = os.getenv("MADROX_FRONTEND_PORT", "3002")
            return f"http://localhost:{port}"

        logger.info(f"Registered {len(source_tools)} proxy tools")

    async def _call_parent(self, tool_name: str, arguments: dict) -> dict | list | str:
        """Forward a tool call to the parent HTTP server.

        Args:
            tool_name: MCP tool name
            arguments: Tool arguments

        Returns:
            Tool result from parent server
        """
        url = f"{self.parent_url}/tools/execute"

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(
                    url,
                    json={"tool": tool_name, "arguments": arguments},
                )

                if resp.status_code >= 400:
                    error_text = resp.text
                    logger.error(
                        f"Parent returned {resp.status_code} for {tool_name}: {error_text}"
                    )
                    return {"error": error_text, "status_code": resp.status_code}

                return resp.json()

        except httpx.ConnectError:
            msg = f"Cannot connect to parent server at {self.parent_url}"
            logger.error(msg)
            return {"error": msg}
        except Exception as e:
            logger.error(f"Proxy call to {tool_name} failed: {e}")
            return {"error": str(e)}

    async def run(self):
        """Get the FastMCP server instance for running."""
        return self.mcp
