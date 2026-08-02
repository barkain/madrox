"""MCP Protocol implementation - STDIO proxy to parent HTTP server.

Instead of importing the backend's tool definitions (which triggers heavy
imports), this STDIO server fetches tool schemas from the parent HTTP
server's /tools endpoint and generates lightweight proxy functions.
"""

import asyncio
import inspect
import logging
import os
from pathlib import Path
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
        self._dashboard_started = False

        # Register local-only tools (not proxied to parent)
        @self.mcp.tool
        async def get_dashboard_url() -> str:
            """Get the URL for the Madrox Monitor dashboard.

            Starts the dashboard if it is not already running — it is not
            launched at session startup, so a session that never opens it does
            not pay for a Next.js dev server.

            Returns:
                The dashboard URL with the correct port for this session.
            """
            port = os.getenv("MADROX_FRONTEND_PORT", "3002")
            await self._ensure_dashboard_running(port)
            return f"http://localhost:{port}"

    @staticmethod
    def _port_is_open(port: str) -> bool:
        """True if something is already listening on the dashboard port."""
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.3)
            return probe.connect_ex(("127.0.0.1", int(port))) == 0

    async def _ensure_dashboard_running(self, port: str) -> None:
        """Start the Next.js dashboard once, on first request.

        Launching it eagerly for every session was the single largest cost of a
        Madrox session: a `next dev` server each, whether or not the dashboard
        was ever opened.

        The child is spawned from this process so the existing cleanup, which
        kills whole process trees, still reaps it when the session ends.
        """
        if self._dashboard_started or self._port_is_open(port):
            self._dashboard_started = True
            return

        frontend_dir = os.getenv("MADROX_FRONTEND_DIR")
        if not frontend_dir or not Path(frontend_dir).is_dir():
            logger.warning("Dashboard requested but frontend directory is missing")
            return

        # Mark before awaiting so two concurrent calls cannot both spawn one.
        self._dashboard_started = True

        # start_plugin.sh points this at the session log dir; with no launcher
        # there is nowhere session-scoped to write, so discard rather than
        # scattering files in a world-writable directory.
        log_path = os.getenv("MADROX_FRONTEND_LOG") or os.devnull
        env = {
            **os.environ,
            "PORT": port,
            "NEXT_PUBLIC_BACKEND_PORT": os.getenv("MADROX_BACKEND_PORT", ""),
        }

        try:
            log_file = open(log_path, "ab")  # noqa: SIM115 - handed to the child
        except OSError as e:
            logger.warning(f"Could not open dashboard log {log_path}: {e}")
            return

        try:
            if not (Path(frontend_dir) / "node_modules").is_dir():
                logger.info("Installing dashboard dependencies (first run)")
                install = await asyncio.create_subprocess_exec(
                    "npm",
                    "install",
                    "--prefix",
                    frontend_dir,
                    stdout=log_file,
                    stderr=log_file,
                )
                await install.wait()

            await asyncio.create_subprocess_exec(
                "npx",
                "next",
                "dev",
                "-p",
                port,
                cwd=frontend_dir,
                env=env,
                stdout=log_file,
                stderr=log_file,
            )
            logger.info(f"Started Madrox dashboard on port {port}")
        except (OSError, ValueError) as e:
            self._dashboard_started = False
            logger.warning(f"Could not start dashboard: {e}")
        finally:
            log_file.close()

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
