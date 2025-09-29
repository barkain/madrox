"""Stdio MCP Server for Madrox - Compatible with OpenAI Codex CLI."""

import asyncio
import json
import logging
import sys
import os
from typing import Any, Optional

from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from .instance_manager import InstanceManager
from .simple_models import OrchestratorConfig, InstanceRole

logger = logging.getLogger(__name__)


class MadroxStdioServer:
    """Stdio MCP Server for Madrox orchestrator."""

    def __init__(self, config: OrchestratorConfig):
        """Initialize the stdio MCP server.

        Args:
            config: Configuration for the orchestrator
        """
        self.config = config
        self.instance_manager = InstanceManager(config.to_dict())
        self.server = Server("madrox")

        # Register handlers
        self._setup_handlers()

        logger.info("Madrox Stdio MCP Server initialized")

    def _setup_handlers(self):
        """Setup MCP protocol handlers."""

        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """Return available tools."""
            return [
                types.Tool(
                    name="spawn_claude",
                    description="Spawn a new Claude instance with specific role and configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Instance name"
                            },
                            "role": {
                                "type": "string",
                                "enum": [role.value for role in InstanceRole],
                                "description": "Predefined role",
                                "default": "general"
                            },
                            "system_prompt": {
                                "type": "string",
                                "description": "Custom system prompt"
                            },
                            "model": {
                                "type": "string",
                                "description": "Claude model to use",
                                "default": "claude-4-sonnet-20250514"
                            }
                        },
                        "required": ["name"]
                    }
                ),
                types.Tool(
                    name="send_to_instance",
                    description="Send a message to a specific Claude instance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_id": {
                                "type": "string",
                                "description": "Target instance ID"
                            },
                            "message": {
                                "type": "string",
                                "description": "Message to send"
                            },
                            "wait_for_response": {
                                "type": "boolean",
                                "description": "Wait for response",
                                "default": True
                            },
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "Response timeout",
                                "default": 30
                            }
                        },
                        "required": ["instance_id", "message"]
                    }
                ),
                types.Tool(
                    name="get_instance_output",
                    description="Get recent output from a Claude instance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_id": {
                                "type": "string",
                                "description": "Instance ID"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of messages",
                                "default": 100
                            },
                            "since": {
                                "type": "string",
                                "description": "ISO timestamp filter"
                            }
                        },
                        "required": ["instance_id"]
                    }
                ),
                types.Tool(
                    name="coordinate_instances",
                    description="Coordinate multiple instances for a complex task",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "coordinator_id": {
                                "type": "string",
                                "description": "Coordinating instance ID"
                            },
                            "participant_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Participant instance IDs"
                            },
                            "task_description": {
                                "type": "string",
                                "description": "Task description"
                            },
                            "coordination_type": {
                                "type": "string",
                                "enum": ["sequential", "parallel", "consensus"],
                                "description": "Coordination type",
                                "default": "sequential"
                            }
                        },
                        "required": ["coordinator_id", "participant_ids", "task_description"]
                    }
                ),
                types.Tool(
                    name="terminate_instance",
                    description="Terminate a Claude instance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_id": {
                                "type": "string",
                                "description": "Instance ID to terminate"
                            },
                            "force": {
                                "type": "boolean",
                                "description": "Force termination",
                                "default": False
                            }
                        },
                        "required": ["instance_id"]
                    }
                ),
                types.Tool(
                    name="get_instance_status",
                    description="Get status for a single instance or all instances",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_id": {
                                "type": "string",
                                "description": "Optional instance ID (omit for all instances)"
                            }
                        }
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(
            name: str,
            arguments: dict[str, Any]
        ) -> list[TextContent]:
            """Handle tool calls."""
            try:
                if name == "spawn_claude":
                    result = await self._spawn_claude(**arguments)
                elif name == "send_to_instance":
                    result = await self._send_to_instance(**arguments)
                elif name == "get_instance_output":
                    result = await self._get_instance_output(**arguments)
                elif name == "coordinate_instances":
                    result = await self._coordinate_instances(**arguments)
                elif name == "terminate_instance":
                    result = await self._terminate_instance(**arguments)
                elif name == "get_instance_status":
                    result = await self._get_instance_status(**arguments)
                else:
                    result = {"error": f"Unknown tool: {name}"}

                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}", exc_info=True)
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)}, indent=2)
                )]

    async def _spawn_claude(
        self,
        name: str,
        role: str = "general",
        system_prompt: Optional[str] = None,
        model: str = "claude-4-sonnet-20250514",
        **kwargs
    ) -> dict[str, Any]:
        """Spawn a new Claude instance."""
        try:
            # Validate role
            if role not in [r.value for r in InstanceRole]:
                role = InstanceRole.GENERAL.value

            instance_id = await self.instance_manager.spawn_instance(
                name=name,
                role=role,
                system_prompt=system_prompt,
                model=model,
                **kwargs
            )

            instance = self.instance_manager.instances[instance_id]

            return {
                "success": True,
                "instance_id": instance_id,
                "name": instance["name"],
                "role": role,
                "model": model,
                "message": f"Successfully spawned Claude instance '{instance['name']}'"
            }

        except Exception as e:
            logger.error(f"Failed to spawn instance: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to spawn Claude instance: {e}"
            }

    async def _send_to_instance(
        self,
        instance_id: str,
        message: str,
        wait_for_response: bool = True,
        timeout_seconds: int = 30,
        **kwargs
    ) -> dict[str, Any]:
        """Send message to Claude instance."""
        try:
            response = await self.instance_manager.send_to_instance(
                instance_id=instance_id,
                message=message,
                wait_for_response=wait_for_response,
                timeout_seconds=timeout_seconds,
                **kwargs
            )

            if response:
                return {
                    "success": True,
                    "instance_id": instance_id,
                    "response": response,
                    "message": "Message sent and response received"
                }
            else:
                return {
                    "success": True,
                    "instance_id": instance_id,
                    "message": "Message sent" + (" (no response requested)" if not wait_for_response else " (timeout)")
                }

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to send message: {e}"
            }

    async def _get_instance_output(
        self,
        instance_id: str,
        since: Optional[str] = None,
        limit: int = 100,
        **kwargs
    ) -> dict[str, Any]:
        """Get instance output."""
        try:
            output = await self.instance_manager.get_instance_output(
                instance_id=instance_id,
                since=since,
                limit=limit
            )

            return {
                "success": True,
                "instance_id": instance_id,
                "output": output,
                "count": len(output),
                "message": f"Retrieved {len(output)} output messages"
            }

        except Exception as e:
            logger.error(f"Failed to get output: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to get output: {e}"
            }

    async def _coordinate_instances(
        self,
        coordinator_id: str,
        participant_ids: list[str],
        task_description: str,
        coordination_type: str = "sequential",
        **kwargs
    ) -> dict[str, Any]:
        """Coordinate multiple instances."""
        try:
            task_id = await self.instance_manager.coordinate_instances(
                coordinator_id=coordinator_id,
                participant_ids=participant_ids,
                task_description=task_description,
                coordination_type=coordination_type
            )

            return {
                "success": True,
                "task_id": task_id,
                "coordinator_id": coordinator_id,
                "participant_ids": participant_ids,
                "coordination_type": coordination_type,
                "message": f"Started coordination task {task_id}"
            }

        except Exception as e:
            logger.error(f"Failed to start coordination: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to start coordination: {e}"
            }

    async def _terminate_instance(
        self,
        instance_id: str,
        force: bool = False,
        **kwargs
    ) -> dict[str, Any]:
        """Terminate Claude instance."""
        try:
            success = await self.instance_manager.terminate_instance(
                instance_id=instance_id,
                force=force
            )

            if success:
                return {
                    "success": True,
                    "instance_id": instance_id,
                    "message": f"Successfully terminated instance {instance_id}"
                }
            else:
                return {
                    "success": False,
                    "instance_id": instance_id,
                    "message": f"Failed to terminate instance {instance_id} (try with force=true)"
                }

        except Exception as e:
            logger.error(f"Failed to terminate instance: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to terminate instance: {e}"
            }

    async def _get_instance_status(
        self,
        instance_id: Optional[str] = None,
        **kwargs
    ) -> dict[str, Any]:
        """Get instance status."""
        try:
            status = self.instance_manager.get_instance_status(instance_id)
            return {
                "success": True,
                "status": status,
                "message": "Retrieved instance status"
            }

        except Exception as e:
            logger.error(f"Failed to get instance status: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to fetch instance status: {e}"
            }

    async def run(self):
        """Run the stdio server."""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            init_options = InitializationOptions(
                server_name="madrox",
                server_version="1.0.0",
                capabilities=self.server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={}
                )
            )

            await self.server.run(
                read_stream,
                write_stream,
                init_options
            )


async def main():
    """Main entry point for the stdio server."""
    # Setup logging to stderr to avoid interfering with stdio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)]
    )

    # Load configuration from environment
    config = OrchestratorConfig(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        server_host="stdio",
        server_port=0,  # Not used for stdio
        max_concurrent_instances=int(os.getenv("MAX_INSTANCES", "10")),
        workspace_base_dir=os.getenv("WORKSPACE_DIR", "/tmp/claude_orchestrator"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )

    # Create and run server
    server = MadroxStdioServer(config)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())