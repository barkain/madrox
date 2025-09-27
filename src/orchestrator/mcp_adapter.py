"""MCP Protocol adapter for the existing FastAPI server."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response
from sse_starlette.sse import EventSourceResponse

from .simple_models import InstanceRole

logger = logging.getLogger(__name__)


class MCPAdapter:
    """Adapter to expose FastAPI endpoints as MCP-compliant SSE endpoints."""

    def __init__(self, instance_manager):
        """Initialize the MCP adapter with instance manager."""
        self.manager = instance_manager
        self.router = APIRouter(prefix="/mcp")
        self._register_routes()

    def _register_routes(self):
        """Register MCP-compliant routes."""

        @self.router.post("/")
        async def handle_mcp_request(request: Request) -> Response:
            """Handle MCP JSON-RPC requests."""
            try:
                body = await request.json()
                method = body.get("method")
                params = body.get("params", {})
                request_id = body.get("id")

                # Handle different MCP methods
                if method == "initialize":
                    result = {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                            "resources": {},
                        },
                        "serverInfo": {
                            "name": "claude-orchestrator",
                            "version": "1.0.0"
                        }
                    }

                elif method == "tools/list":
                    result = {
                        "tools": [
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
                                            "description": "Predefined role"
                                        },
                                        "system_prompt": {"type": "string", "description": "Custom system prompt"},
                                        "model": {"type": "string", "description": "Claude model to use"}
                                    },
                                    "required": ["name"]
                                }
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
                                        "timeout_seconds": {"type": "integer", "default": 30}
                                    },
                                    "required": ["instance_id", "message"]
                                }
                            },
                            {
                                "name": "get_instance_output",
                                "description": "Get recent output from a Claude instance",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_id": {"type": "string"},
                                        "since": {"type": "string", "description": "ISO timestamp filter"},
                                        "limit": {"type": "integer", "default": 100}
                                    },
                                    "required": ["instance_id"]
                                }
                            },
                            {
                                "name": "coordinate_instances",
                                "description": "Coordinate multiple instances for a complex task",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "coordinator_id": {"type": "string", "description": "Coordinating instance ID"},
                                        "participant_ids": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "Participant instance IDs"
                                        },
                                        "task_description": {"type": "string"},
                                        "coordination_type": {
                                            "type": "string",
                                            "enum": ["sequential", "parallel", "consensus"],
                                            "default": "sequential"
                                        }
                                    },
                                    "required": ["coordinator_id", "participant_ids", "task_description"]
                                }
                            },
                            {
                                "name": "terminate_instance",
                                "description": "Terminate a Claude instance",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_id": {"type": "string"},
                                        "force": {"type": "boolean", "default": False}
                                    },
                                    "required": ["instance_id"]
                                }
                            },
                            {
                                "name": "get_instance_status",
                                "description": "Get status for a single instance or all instances",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_id": {
                                            "type": "string",
                                            "description": "Optional instance ID (omit for all instances)"
                                        }
                                    }
                                }
                            }
                        ]
                    }

                elif method == "tools/call":
                    tool_name = params.get("name")
                    tool_args = params.get("arguments", {})

                    # Execute the tool
                    if tool_name == "spawn_claude":
                        instance_id = await self.manager.spawn_instance(
                            name=tool_args.get("name", "unnamed"),
                            role=tool_args.get("role", "general"),
                            system_prompt=tool_args.get("system_prompt"),
                            model=tool_args.get("model", "claude-3-5-sonnet-20241022"),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Spawned instance '{tool_args.get('name')}' with ID: {instance_id}"
                                }
                            ]
                        }

                    elif tool_name == "send_to_instance":
                        response = await self.manager.send_to_instance(
                            instance_id=tool_args["instance_id"],
                            message=tool_args["message"],
                            wait_for_response=tool_args.get("wait_for_response", True),
                            timeout_seconds=tool_args.get("timeout_seconds", 30),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": response.get("response", "Message sent") if response else "Message sent (no response)"
                                }
                            ]
                        }

                    elif tool_name == "get_instance_output":
                        output = await self.manager.get_instance_output(
                            instance_id=tool_args["instance_id"],
                            since=tool_args.get("since"),
                            limit=tool_args.get("limit", 100),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(output, indent=2)
                                }
                            ]
                        }

                    elif tool_name == "coordinate_instances":
                        coordination_result = await self.manager.coordinate_instances(
                            coordinator_id=tool_args["coordinator_id"],
                            participant_ids=tool_args["participant_ids"],
                            task_description=tool_args["task_description"],
                            coordination_type=tool_args.get("coordination_type", "sequential"),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Coordination completed: {coordination_result}"
                                }
                            ]
                        }

                    elif tool_name == "terminate_instance":
                        success = await self.manager.terminate_instance(
                            instance_id=tool_args["instance_id"],
                            force=tool_args.get("force", False),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Instance {tool_args['instance_id']} terminated" if success else f"Failed to terminate {tool_args['instance_id']}"
                                }
                            ]
                        }

                    elif tool_name == "get_instance_status":
                        status = self.manager.get_instance_status(
                            instance_id=tool_args.get("instance_id")
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(status, indent=2)
                                }
                            ]
                        }

                    else:
                        result = {"error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}

                else:
                    result = {"error": {"code": -32601, "message": f"Method not found: {method}"}}

                # Return JSON-RPC response
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }

                return Response(content=json.dumps(response), media_type="application/json")

            except Exception as e:
                logger.error(f"Error handling MCP request: {e}")
                return Response(
                    content=json.dumps({
                        "jsonrpc": "2.0",
                        "id": body.get("id") if "body" in locals() else None,
                        "error": {
                            "code": -32603,
                            "message": str(e)
                        }
                    }),
                    media_type="application/json"
                )

        # Allow clients that omit the trailing slash (e.g. /mcp)
        self.router.add_api_route(
            "",
            handle_mcp_request,
            methods=["POST"],
        )

        @self.router.get("/sse")
        async def mcp_sse_endpoint(request: Request):
            """SSE endpoint for MCP streaming communication."""

            async def event_generator():
                """Generate SSE events for MCP communication."""
                try:
                    # Send initial connection message
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "jsonrpc": "2.0",
                            "method": "connection/ready",
                            "params": {}
                        })
                    }

                    # Keep connection alive
                    import asyncio
                    while True:
                        await asyncio.sleep(30)
                        yield {
                            "event": "ping",
                            "data": json.dumps({"timestamp": "now"})
                        }

                except Exception as e:
                    logger.error(f"SSE error: {e}")
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": str(e)})
                    }

            return EventSourceResponse(event_generator())

        @self.router.get("/health")
        async def mcp_health():
            """MCP health check endpoint."""
            return {
                "status": "healthy",
                "server": "claude-orchestrator",
                "version": "1.0.0",
                "transport": "sse"
            }
