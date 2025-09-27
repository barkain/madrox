"""MCP Protocol implementation for Claude Orchestrator."""

import logging
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

from src.orchestrator.instance_manager import InstanceManager
from src.orchestrator.simple_models import OrchestratorConfig, InstanceRole

logger = logging.getLogger(__name__)


class OrchestrationMCPServer:
    """MCP Server for Claude Orchestration."""

    def __init__(self, config: OrchestratorConfig):
        """Initialize MCP server with orchestrator config."""
        self.config = config
        self.server = Server("claude-orchestrator")
        # Use a plain dict config for InstanceManager
        self.manager = InstanceManager(config.to_dict())

        # Register handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register all MCP protocol handlers."""

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """List available orchestration tools."""
            return [
                Tool(
                    name="spawn_claude",
                    description="Spawn a new Claude instance with specific role and configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Human-readable name for the instance"
                            },
                            "role": {
                                "type": "string",
                                "enum": [role.value for role in InstanceRole],
                                "description": "Predefined role for the instance"
                            },
                            "system_prompt": {
                                "type": "string",
                                "description": "Optional custom system prompt"
                            },
                            "model": {
                                "type": "string",
                                "description": "Claude model to use",
                                "default": "claude-3-5-sonnet-20241022"
                            }
                        },
                        "required": ["name"]
                    }
                ),
                Tool(
                    name="send_to_instance",
                    description="Send a message to a specific Claude instance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_id": {
                                "type": "string",
                                "description": "ID of the target instance"
                            },
                            "message": {
                                "type": "string",
                                "description": "Message to send"
                            },
                            "wait_for_response": {
                                "type": "boolean",
                                "description": "Whether to wait for response",
                                "default": True
                            },
                            "timeout_seconds": {
                                "type": "number",
                                "description": "Timeout in seconds",
                                "default": 30
                            }
                        },
                        "required": ["instance_id", "message"]
                    }
                ),
                Tool(
                    name="get_instance_output",
                    description="Get recent output from a Claude instance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_id": {
                                "type": "string",
                                "description": "ID of the instance"
                            },
                            "since": {
                                "type": "string",
                                "description": "ISO timestamp to get messages since"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum messages to retrieve",
                                "default": 100
                            }
                        },
                        "required": ["instance_id"]
                    }
                ),
                Tool(
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
                                "description": "Participating instance IDs"
                            },
                            "task_description": {
                                "type": "string",
                                "description": "Description of the task"
                            },
                            "coordination_type": {
                                "type": "string",
                                "enum": ["sequential", "parallel", "consensus"],
                                "description": "How to coordinate the instances",
                                "default": "sequential"
                            }
                        },
                        "required": ["coordinator_id", "participant_ids", "task_description"]
                    }
                ),
                Tool(
                    name="terminate_instance",
                    description="Terminate a Claude instance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_id": {
                                "type": "string",
                                "description": "ID of the instance to terminate"
                            },
                            "force": {
                                "type": "boolean",
                                "description": "Force termination even if busy",
                                "default": False
                            }
                        },
                        "required": ["instance_id"]
                    }
                ),
                Tool(
                    name="get_instance_status",
                    description="Get status of an instance or all instances",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "instance_id": {
                                "type": "string",
                                "description": "Optional instance ID (omit for all instances)"
                            }
                        }
                    }
                ),
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
            """Handle tool execution requests."""
            try:
                if name == "spawn_claude":
                    instance_id = await self.manager.spawn_instance(
                        name=arguments.get("name", "unnamed"),
                        role=arguments.get("role", "general"),
                        system_prompt=arguments.get("system_prompt"),
                        model=arguments.get("model", "claude-3-5-sonnet-20241022"),
                    )
                    return [
                        TextContent(
                            type="text",
                            text=f"Successfully spawned Claude instance '{arguments.get('name')}' with ID: {instance_id}"
                        )
                    ]

                elif name == "send_to_instance":
                    response = await self.manager.send_to_instance(
                        instance_id=arguments["instance_id"],
                        message=arguments["message"],
                        wait_for_response=arguments.get("wait_for_response", True),
                        timeout_seconds=arguments.get("timeout_seconds", 30),
                    )
                    if response:
                        return [
                            TextContent(
                                type="text",
                                text=response.get("response", "Message sent successfully")
                            )
                        ]
                    return [
                        TextContent(
                            type="text",
                            text="Message sent (no response requested)"
                        )
                    ]

                elif name == "get_instance_output":
                    output = await self.manager.get_instance_output(
                        instance_id=arguments["instance_id"],
                        since=arguments.get("since"),
                        limit=arguments.get("limit", 100),
                    )
                    return [
                        TextContent(
                            type="text",
                            text=f"Instance output:\n{output}"
                        )
                    ]

                elif name == "coordinate_instances":
                    result = await self.manager.coordinate_instances(
                        coordinator_id=arguments["coordinator_id"],
                        participant_ids=arguments["participant_ids"],
                        task_description=arguments["task_description"],
                        coordination_type=arguments.get("coordination_type", "sequential"),
                    )
                    return [
                        TextContent(
                            type="text",
                            text=f"Coordination task completed: {result}"
                        )
                    ]

                elif name == "terminate_instance":
                    success = await self.manager.terminate_instance(
                        instance_id=arguments["instance_id"],
                        force=arguments.get("force", False),
                    )
                    if success:
                        return [
                            TextContent(
                                type="text",
                                text=f"Instance {arguments['instance_id']} terminated successfully"
                            )
                        ]
                    return [
                        TextContent(
                            type="text",
                            text=f"Failed to terminate instance {arguments['instance_id']}"
                        )
                    ]

                elif name == "get_instance_status":
                    status = self.manager.get_instance_status(
                        instance_id=arguments.get("instance_id")
                    )
                    return [
                        TextContent(
                            type="text",
                            text=f"Instance status:\n{status}"
                        )
                    ]

                else:
                    return [
                        TextContent(
                            type="text",
                            text=f"Unknown tool: {name}"
                        )
                    ]

            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                return [
                    TextContent(
                        type="text",
                        text=f"Error executing {name}: {str(e)}"
                    )
                ]

    async def run(self) -> Server:
        """Get the MCP server instance for running."""
        # Initialize with options
        init_options = InitializationOptions(
            server_name="claude-orchestrator",
            server_version="1.0.0",
            capabilities=self.server.get_capabilities(
                notification_options=None,
                experimental_capabilities={},
            ),
        )

        return self.server
