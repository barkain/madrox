#!/usr/bin/env python3
"""Stdio MCP Server for Madrox - Compatible with OpenAI Codex CLI.

This server implements the MCP protocol over stdio using JSON-RPC 2.0.
All tool definitions and operations are proxied to the main HTTP server,
eliminating code duplication.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import aiohttp

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Setup logging to stderr to avoid interfering with stdio
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


class MadroxStdioServer:
    """Stdio MCP Server for Madrox orchestrator using JSON-RPC.

    This server proxies all operations to the HTTP server to maintain
    a unified view of all instances regardless of which server spawned them.
    All tool definitions are fetched from the HTTP server, eliminating duplication.
    """

    def __init__(self):
        """Initialize the stdio MCP server."""
        # HTTP server endpoint for proxying requests
        self.http_server_url = os.getenv("MADROX_HTTP_SERVER", "http://localhost:8001")

        self.server_info = {
            "name": "madrox",
            "version": "1.0.0",
            "vendor": "claude-orchestrator",
        }

        logger.info(f"Madrox Stdio MCP Server initialized (proxying to {self.http_server_url})")

    async def _http_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make HTTP request to the main orchestrator server."""
        url = f"{self.http_server_url}{endpoint}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, **kwargs) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            logger.error(f"HTTP request failed: {method} {url} - {e}")
            raise

    def create_response(self, id: Any, result: Any = None, error: Any = None) -> dict:
        """Create a JSON-RPC response."""
        response = {"jsonrpc": "2.0", "id": id}
        if error is not None:
            response["error"] = error
        else:
            response["result"] = result
        return response

    def create_notification(self, method: str, params: Any = None) -> dict:
        """Create a JSON-RPC notification."""
        notification = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            notification["params"] = params
        return notification

    async def handle_initialize(self, params: dict) -> dict:
        """Handle initialize request."""
        return {
            "protocolVersion": "0.1.0",
            "capabilities": {"tools": {}},
            "serverInfo": self.server_info,
        }

    async def handle_list_tools(self) -> list[dict]:
        """Handle tools/list request by proxying to HTTP server.

        This eliminates tool definition duplication - tools are now defined
        once in mcp_server.py using FastMCP @mcp.tool() decorator.
        """
        try:
            result = await self._http_request(
                "POST",
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )

            # Extract tools from JSON-RPC response
            if "result" in result and "tools" in result["result"]:
                return result["result"]["tools"]
            else:
                logger.error(f"Invalid tools/list response: {result}")
                return []

        except Exception as e:
            logger.error(f"Failed to fetch tools from HTTP server: {e}")
            return []

    async def handle_call_tool(self, name: str, arguments: dict) -> list[dict]:
        """Handle tools/call request by proxying to HTTP server."""
        try:
            result = await self._http_request(
                "POST",
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
            )

            # Extract result from JSON-RPC response
            if "result" in result and "content" in result["result"]:
                return result["result"]["content"]
            elif "error" in result:
                error_msg = result["error"].get("message", "Unknown error")
                return [{"type": "text", "text": json.dumps({"error": error_msg}, indent=2)}]
            else:
                return [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"error": "Invalid response from HTTP server"}, indent=2
                        ),
                    }
                ]

        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            return [{"type": "text", "text": json.dumps({"error": str(e)}, indent=2)}]

    async def handle_request(self, request: dict) -> dict | None:
        """Handle a JSON-RPC request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method == "initialized":
                # Notification, no response needed
                return None
            elif method == "tools/list":
                tools = await self.handle_list_tools()
                result = {"tools": tools}
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                content = await self.handle_call_tool(name, arguments)
                result = {"content": content}
            else:
                error = {"code": -32601, "message": f"Method not found: {method}"}
                return self.create_response(request_id, error=error)

            return self.create_response(request_id, result=result)

        except Exception as e:
            logger.error(f"Error handling request {method}: {e}", exc_info=True)
            error = {"code": -32603, "message": "Internal error", "data": str(e)}
            return self.create_response(request_id, error=error)

    async def run(self):
        """Run the stdio server."""
        logger.info("Madrox stdio server starting...")

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            try:
                # Read line from stdin
                line = await reader.readline()
                if not line:
                    break

                # Parse JSON-RPC request
                try:
                    request = json.loads(line.decode())
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    continue

                # Handle request
                response = await self.handle_request(request)

                # Send response if not a notification
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)

        logger.info("Madrox stdio server shutting down...")


async def main():
    """Main entry point."""
    server = MadroxStdioServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
