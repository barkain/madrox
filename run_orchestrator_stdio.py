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

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestrator.instance_manager import InstanceManager
from src.orchestrator.simple_models import InstanceRole, OrchestratorConfig

# Setup logging to stderr to avoid interfering with stdio
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


class MadroxStdioServer:
    """Stdio MCP Server for Madrox orchestrator using JSON-RPC."""

    def __init__(self):
        """Initialize the stdio MCP server."""
        # Load configuration from environment
        self.config = OrchestratorConfig(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            server_host="stdio",
            server_port=0,  # Not used for stdio
            max_concurrent_instances=int(os.getenv("MAX_INSTANCES", "10")),
            workspace_base_dir=os.getenv("WORKSPACE_DIR", "/tmp/claude_orchestrator"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

        self.instance_manager = InstanceManager(self.config.to_dict())
        self.server_info = {"name": "madrox", "version": "1.0.0", "vendor": "claude-orchestrator"}

        logger.info("Madrox Stdio MCP Server initialized")

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
        model: str = "claude-4-sonnet-20250514",
        use_pty: bool = True,  # Force PTY mode for interactive Claude CLI
        **kwargs,
    ) -> dict:
        """Spawn a new Claude instance."""
        try:
            if role not in [r.value for r in InstanceRole]:
                role = InstanceRole.GENERAL.value

            instance_id = await self.instance_manager.spawn_instance(
                name=name, role=role, system_prompt=system_prompt,
                model=model, use_pty=use_pty, **kwargs
            )

            instance = self.instance_manager.instances[instance_id]

            return {
                "success": True,
                "instance_id": instance_id,
                "name": instance["name"],
                "role": role,
                "model": model,
                "message": f"Successfully spawned Claude instance '{instance['name']}'",
            }

        except Exception as e:
            logger.error(f"Failed to spawn instance: {e}")
            return {"success": False, "error": str(e)}

    async def send_to_instance(
        self,
        instance_id: str,
        message: str,
        wait_for_response: bool = True,
        timeout_seconds: int = 30,
        **kwargs,
    ) -> dict:
        """Send message to Claude instance."""
        try:
            response = await self.instance_manager.send_to_instance(
                instance_id=instance_id,
                message=message,
                wait_for_response=wait_for_response,
                timeout_seconds=timeout_seconds,
                **kwargs,
            )

            if response:
                return {
                    "success": True,
                    "instance_id": instance_id,
                    "response": response,
                    "message": "Message sent and response received",
                }
            else:
                return {"success": True, "instance_id": instance_id, "message": "Message sent"}

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return {"success": False, "error": str(e)}

    async def get_instance_output(
        self, instance_id: str, since: str | None = None, limit: int = 100, **kwargs
    ) -> dict:
        """Get instance output."""
        try:
            output = await self.instance_manager.get_instance_output(
                instance_id=instance_id, since=since, limit=limit
            )

            return {
                "success": True,
                "instance_id": instance_id,
                "output": output,
                "count": len(output),
            }

        except Exception as e:
            logger.error(f"Failed to get output: {e}")
            return {"success": False, "error": str(e)}

    async def coordinate_instances(
        self,
        coordinator_id: str,
        participant_ids: list[str],
        task_description: str,
        coordination_type: str = "sequential",
        **kwargs,
    ) -> dict:
        """Coordinate multiple instances."""
        try:
            task_id = await self.instance_manager.coordinate_instances(
                coordinator_id=coordinator_id,
                participant_ids=participant_ids,
                task_description=task_description,
                coordination_type=coordination_type,
            )

            return {
                "success": True,
                "task_id": task_id,
                "coordinator_id": coordinator_id,
                "participant_ids": participant_ids,
                "coordination_type": coordination_type,
            }

        except Exception as e:
            logger.error(f"Failed to start coordination: {e}")
            return {"success": False, "error": str(e)}

    async def terminate_instance(self, instance_id: str, force: bool = False, **kwargs) -> dict:
        """Terminate Claude instance."""
        try:
            success = await self.instance_manager.terminate_instance(
                instance_id=instance_id, force=force
            )

            if success:
                return {
                    "success": True,
                    "instance_id": instance_id,
                    "message": f"Successfully terminated instance {instance_id}",
                }
            else:
                return {
                    "success": False,
                    "instance_id": instance_id,
                    "message": f"Failed to terminate instance {instance_id}",
                }

        except Exception as e:
            logger.error(f"Failed to terminate instance: {e}")
            return {"success": False, "error": str(e)}

    async def get_instance_status(self, instance_id: str | None = None, **kwargs) -> dict:
        """Get instance status."""
        try:
            status = self.instance_manager.get_instance_status(instance_id)
            return {"success": True, "status": status}

        except Exception as e:
            logger.error(f"Failed to get instance status: {e}")
            return {"success": False, "error": str(e)}

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
