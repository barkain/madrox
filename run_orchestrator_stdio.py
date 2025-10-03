#!/usr/bin/env python3
"""Stdio MCP Server for Madrox - Compatible with OpenAI Codex CLI.

This server implements the MCP protocol over stdio using JSON-RPC 2.0.
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

from src.orchestrator.simple_models import InstanceRole

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
    """

    def __init__(self):
        """Initialize the stdio MCP server."""
        # HTTP server endpoint for proxying requests
        self.http_server_url = os.getenv("MADROX_HTTP_SERVER", "http://localhost:8001")

        self.server_info = {"name": "madrox", "version": "1.0.0", "vendor": "claude-orchestrator"}

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
            "capabilities": {
                "tools": {}
            },
            "serverInfo": self.server_info
        }

    async def handle_list_tools(self) -> list[dict]:
        """Handle tools/list request."""
        return [
            {
                "name": "spawn_claude",
                "description": "Spawn a new Claude instance with specific role and configuration",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Instance name"},
                        "role": {
                            "type": "string",
                            "enum": [role.value for role in InstanceRole],
                            "description": "Predefined role",
                        },
                        "system_prompt": {"type": "string", "description": "Custom system prompt"},
                        "model": {"type": "string", "description": "Claude model to use"},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "send_to_instance",
                "description": "Send a message to a specific Claude instance",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "instance_id": {"type": "string"},
                        "message": {"type": "string"},
                        "wait_for_response": {"type": "boolean", "default": True},
                        "timeout_seconds": {"type": "integer", "default": 30},
                    },
                    "required": ["instance_id", "message"],
                },
            },
            {
                "name": "get_instance_output",
                "description": "Get recent output from a Claude instance",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "instance_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 100},
                        "since": {"type": "string"},
                    },
                    "required": ["instance_id"],
                },
            },
            {
                "name": "coordinate_instances",
                "description": "Coordinate multiple instances for a complex task",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "coordinator_id": {"type": "string"},
                        "participant_ids": {"type": "array", "items": {"type": "string"}},
                        "task_description": {"type": "string"},
                        "coordination_type": {
                            "type": "string",
                            "enum": ["sequential", "parallel", "consensus"],
                            "default": "sequential",
                        },
                    },
                    "required": ["coordinator_id", "participant_ids", "task_description"],
                },
            },
            {
                "name": "terminate_instance",
                "description": "Terminate a Claude instance",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "instance_id": {"type": "string"},
                        "force": {"type": "boolean", "default": False},
                    },
                    "required": ["instance_id"],
                },
            },
            {
                "name": "get_instance_status",
                "description": "Get status for instances",
                "inputSchema": {
                    "type": "object",
                    "properties": {"instance_id": {"type": "string"}},
                },
            },
        ]

    async def handle_call_tool(self, name: str, arguments: dict) -> list[dict]:
        """Handle tools/call request."""
        try:
            if name == "spawn_claude":
                result = await self.spawn_claude(**arguments)
            elif name == "send_to_instance":
                result = await self.send_to_instance(**arguments)
            elif name == "get_instance_output":
                result = await self.get_instance_output(**arguments)
            elif name == "coordinate_instances":
                result = await self.coordinate_instances(**arguments)
            elif name == "terminate_instance":
                result = await self.terminate_instance(**arguments)
            elif name == "get_instance_status":
                result = await self.get_instance_status(**arguments)
            else:
                result = {"error": f"Unknown tool: {name}"}

            return [{"type": "text", "text": json.dumps(result, indent=2)}]

        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            return [{"type": "text", "text": json.dumps({"error": str(e)}, indent=2)}]

    async def spawn_claude(
        self,
        name: str,
        role: str = "general",
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs,
    ) -> dict:
        """Spawn a new Claude instance (proxied to HTTP server)."""
        try:
            # Normalize parameter names (Codex uses parent_id, HTTP server expects parent_instance_id)
            if "parent_id" in kwargs:
                kwargs["parent_instance_id"] = kwargs.pop("parent_id")

            # Proxy request to HTTP server
            payload = {
                "name": name,
                "role": role,
                "system_prompt": system_prompt,
                "model": model,
                **kwargs
            }
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}

            result = await self._http_request(
                "POST",
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "spawn_claude",
                        "arguments": payload
                    }
                }
            )

            # Extract result from JSON-RPC response
            if "result" in result and "content" in result["result"]:
                content = result["result"]["content"][0]["text"]
                return json.loads(content)
            else:
                return {"success": False, "error": "Invalid response from HTTP server"}

        except Exception as e:
            logger.error(f"Failed to spawn instance: {e}")
            return {"success": False, "error": str(e)}

    async def _proxy_tool(self, tool_name: str, arguments: dict) -> dict:
        """Proxy any tool call to HTTP server."""
        try:
            result = await self._http_request(
                "POST",
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                }
            )

            # Extract result from JSON-RPC response
            if "result" in result and "content" in result["result"]:
                content = result["result"]["content"][0]["text"]
                return json.loads(content)
            else:
                return {"success": False, "error": "Invalid response from HTTP server"}

        except Exception as e:
            logger.error(f"Failed to proxy tool {tool_name}: {e}")
            return {"success": False, "error": str(e)}

    async def send_to_instance(
        self,
        instance_id: str,
        message: str,
        wait_for_response: bool = True,
        timeout_seconds: int = 30,
        **kwargs,
    ) -> dict:
        """Send message to Claude instance (proxied to HTTP server)."""
        return await self._proxy_tool("send_to_instance", {
            "instance_id": instance_id,
            "message": message,
            "wait_for_response": wait_for_response,
            "timeout_seconds": timeout_seconds,
            **kwargs
        })

    async def get_instance_output(
        self, instance_id: str, since: str | None = None, limit: int = 100, **kwargs
    ) -> dict:
        """Get instance output (proxied to HTTP server)."""
        return await self._proxy_tool("get_instance_output", {
            "instance_id": instance_id,
            "since": since,
            "limit": limit,
            **kwargs
        })

    async def coordinate_instances(
        self,
        coordinator_id: str,
        participant_ids: list[str],
        task_description: str,
        coordination_type: str = "sequential",
        **kwargs,
    ) -> dict:
        """Coordinate multiple instances (proxied to HTTP server)."""
        return await self._proxy_tool("coordinate_instances", {
            "coordinator_id": coordinator_id,
            "participant_ids": participant_ids,
            "task_description": task_description,
            "coordination_type": coordination_type,
            **kwargs
        })

    async def terminate_instance(self, instance_id: str, force: bool = False, **kwargs) -> dict:
        """Terminate Claude instance (proxied to HTTP server)."""
        return await self._proxy_tool("terminate_instance", {
            "instance_id": instance_id,
            "force": force,
            **kwargs
        })

    async def get_instance_status(self, instance_id: str | None = None, **kwargs) -> dict:
        """Get instance status (proxied to HTTP server)."""
        args = {**kwargs}
        if instance_id is not None:
            args["instance_id"] = instance_id
        return await self._proxy_tool("get_instance_status", args)

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
