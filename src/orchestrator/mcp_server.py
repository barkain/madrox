"""MCP Protocol implementation - STDIO proxy to parent HTTP server.

Instead of importing the backend's tool definitions (which triggers heavy
imports), this STDIO server fetches tool schemas from the parent HTTP
server's /tools endpoint and generates lightweight proxy functions.
"""

import asyncio
import inspect
import logging
import os
from typing import Any

import httpx
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "number": float,
    "array": list,
    "object": dict,
}


def _make_proxy_from_schema(
    server: "OrchestrationMCPServer",
    tool_name: str,
    description: str,
    input_schema: dict[str, Any],
) -> Any:
    """Create a proxy function from a JSON Schema tool definition.

    Uses inspect.Parameter to build a proper function signature that
    FastMCP/Pydantic can introspect.
    """
    properties = input_schema.get("properties", {})
    required_set = set(input_schema.get("required", []))

    # Build inspect.Parameter list for the signature
    params = []
    param_names_required = [n for n in properties if n in required_set]
    param_names_optional = [n for n in properties if n not in required_set]
    all_param_names = param_names_required + param_names_optional

    annotations: dict[str, Any] = {}
    for name in param_names_required:
        json_type = properties[name].get("type", "string")
        python_type = _JSON_TYPE_MAP.get(json_type, str)
        annotations[name] = python_type
        params.append(
            inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=python_type)
        )
    for name in param_names_optional:
        json_type = properties[name].get("type", "string")
        python_type = _JSON_TYPE_MAP.get(json_type, str)
        annotations[name] = python_type | None
        params.append(
            inspect.Parameter(
                name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=python_type | None,
            )
        )

    # Capture tool_name and param names in closure
    _tool = tool_name
    _params = list(all_param_names)
    _server = server

    async def proxy_fn(**kwargs):
        args = {k: v for k, v in kwargs.items() if v is not None}
        return await _server._call_parent(_tool, args)

    proxy_fn.__name__ = tool_name
    proxy_fn.__qualname__ = tool_name
    proxy_fn.__doc__ = description
    proxy_fn.__module__ = __name__
    proxy_fn.__signature__ = inspect.Signature(params)  # type: ignore[attr-defined]
    proxy_fn.__annotations__ = annotations

    return proxy_fn


class OrchestrationMCPServer:
    """STDIO MCP proxy server that forwards all tool calls to the parent HTTP server.

    Tool schemas are fetched from the parent HTTP server at startup rather than
    imported from backend modules, keeping the STDIO proxy lightweight with no
    heavy dependency chain.
    """

    def __init__(self, parent_url: str | None = None):
        """Initialize proxy MCP server.

        Args:
            parent_url: URL of the parent HTTP server (e.g. http://localhost:8001).
                       Auto-detected from MADROX_PARENT_URL env var if not provided.
        """
        default_port = os.getenv("ORCHESTRATOR_PORT", "8001")
        self.parent_url = parent_url or os.getenv(
            "MADROX_PARENT_URL", f"http://localhost:{default_port}"
        )
        self.mcp = FastMCP("claude-orchestrator-stdio-proxy")

        # Register local-only tools (not proxied to parent)
        @self.mcp.tool
        async def get_dashboard_url() -> str:
            """Get the URL for the Madrox Monitor dashboard.

            Returns:
                The dashboard URL with the correct port for this session.
            """
            port = os.getenv("MADROX_FRONTEND_PORT", "3002")
            return f"http://localhost:{port}"

    async def _register_proxy_tools(self):
        """Fetch tool schemas from the parent HTTP server and register proxies.

        Retries up to 3 times with 1s delay on failure. Each tool schema is
        used to generate a proxy function with matching signature.
        """
        url = f"{self.parent_url}/tools"
        last_error = None

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    break
            except Exception as e:
                last_error = e
                logger.warning(f"Failed to fetch tools (attempt {attempt + 1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        else:
            logger.error(f"Could not fetch tool schemas from {url}: {last_error}")
            return

        tools = data.get("tools", [])
        for tool_def in tools:
            tool_name = tool_def["name"]
            description = tool_def.get("description", "")
            input_schema = tool_def.get("inputSchema", {})
            proxy_fn = _make_proxy_from_schema(self, tool_name, description, input_schema)
            self.mcp.tool()(proxy_fn)

        logger.info(f"Registered {len(tools)} proxy tools from {self.parent_url}")

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
        """Register proxy tools and return the FastMCP server instance for running."""
        await self._register_proxy_tools()
        return self.mcp
