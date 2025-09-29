"""MCP Protocol adapter for the existing FastAPI server."""

import json
import logging

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
                        "serverInfo": {"name": "claude-orchestrator", "version": "1.0.0"},
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
                                            "description": "Predefined role",
                                        },
                                        "system_prompt": {
                                            "type": "string",
                                            "description": "Custom system prompt",
                                        },
                                        "model": {
                                            "type": "string",
                                            "description": "Claude model to use (omit to use CLI default)",
                                        },
                                        "bypass_isolation": {
                                            "type": "boolean",
                                            "description": "Allow full filesystem access (default: false)",
                                        },
                                        "enable_madrox": {
                                            "type": "boolean",
                                            "default": False,
                                            "description": "Enable madrox MCP server (allows spawning sub-instances)",
                                        },
                                    },
                                    "required": ["name"],
                                },
                            },
                            {
                                "name": "send_to_instance",
                                "description": "Send a message to a specific Claude instance (non-blocking by default)",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_id": {"type": "string"},
                                        "message": {"type": "string"},
                                        "wait_for_response": {
                                            "type": "boolean",
                                            "default": False,
                                            "description": "Set to true to wait for response",
                                        },
                                        "timeout_seconds": {
                                            "type": "integer",
                                            "default": 180,
                                            "description": "Timeout in seconds (default 180)",
                                        },
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
                                        "since": {
                                            "type": "string",
                                            "description": "ISO timestamp filter",
                                        },
                                        "limit": {"type": "integer", "default": 100},
                                    },
                                    "required": ["instance_id"],
                                },
                            },
                            {
                                "name": "get_job_status",
                                "description": "Get the status of an asynchronous job (waits for completion by default)",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "job_id": {
                                            "type": "string",
                                            "description": "Job ID to check status",
                                        },
                                        "wait_for_completion": {
                                            "type": "boolean",
                                            "default": True,
                                            "description": "Wait for job to complete (default true)",
                                        },
                                        "max_wait": {
                                            "type": "integer",
                                            "default": 120,
                                            "description": "Maximum seconds to wait (default 120)",
                                        },
                                    },
                                    "required": ["job_id"],
                                },
                            },
                            {
                                "name": "coordinate_instances",
                                "description": "Coordinate multiple instances for a complex task",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "coordinator_id": {
                                            "type": "string",
                                            "description": "Coordinating instance ID",
                                        },
                                        "participant_ids": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "Participant instance IDs",
                                        },
                                        "task_description": {"type": "string"},
                                        "coordination_type": {
                                            "type": "string",
                                            "enum": ["sequential", "parallel", "consensus"],
                                            "default": "sequential",
                                        },
                                    },
                                    "required": [
                                        "coordinator_id",
                                        "participant_ids",
                                        "task_description",
                                    ],
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
                                "description": "Get status for a single instance or all instances",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_id": {
                                            "type": "string",
                                            "description": "Optional instance ID (omit for all instances)",
                                        }
                                    },
                                },
                            },
                            {
                                "name": "retrieve_instance_file",
                                "description": "Retrieve a file from an instance's workspace directory",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_id": {"type": "string"},
                                        "filename": {
                                            "type": "string",
                                            "description": "Name of the file to retrieve",
                                        },
                                        "destination_path": {
                                            "type": "string",
                                            "description": "Optional destination path (defaults to current directory)",
                                        },
                                    },
                                    "required": ["instance_id", "filename"],
                                },
                            },
                            {
                                "name": "list_instance_files",
                                "description": "List all files in an instance's workspace directory",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"instance_id": {"type": "string"}},
                                    "required": ["instance_id"],
                                },
                            },
                            {
                                "name": "spawn_codex_instance",
                                "description": "Spawn a new Codex CLI instance with specific configuration",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "description": "Instance name"},
                                        "model": {
                                            "type": "string",
                                            "description": "Codex model to use - OpenAI models only (omit to use CLI default, typically gpt-5-codex)",
                                        },
                                        "sandbox_mode": {
                                            "type": "string",
                                            "default": "workspace-write",
                                            "enum": [
                                                "read-only",
                                                "workspace-write",
                                                "danger-full-access",
                                            ],
                                            "description": "Sandbox policy for shell commands",
                                        },
                                        "profile": {
                                            "type": "string",
                                            "description": "Configuration profile from config.toml",
                                        },
                                        "initial_prompt": {
                                            "type": "string",
                                            "description": "Initial prompt to start the session",
                                        },
                                    },
                                    "required": ["name"],
                                },
                            },
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
                            model=tool_args.get("model"),  # None = use CLI default
                            bypass_isolation=tool_args.get("bypass_isolation", False),
                            enable_madrox=tool_args.get("enable_madrox", False),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Spawned instance '{tool_args.get('name')}' with ID: {instance_id}",
                                }
                            ]
                        }

                    elif tool_name == "send_to_instance":
                        response = await self.manager.send_to_instance(
                            instance_id=tool_args["instance_id"],
                            message=tool_args["message"],
                            wait_for_response=tool_args.get(
                                "wait_for_response", False
                            ),  # Default to False
                            timeout_seconds=tool_args.get(
                                "timeout_seconds", 180
                            ),  # Default to 180 seconds
                        )

                        # Handle response based on whether we waited or not
                        if isinstance(response, dict) and "status" in response:
                            if response["status"] == "timeout":
                                # Timeout with job tracking
                                text = (
                                    f"Request timed out but is still processing.\n"
                                    f"Job ID: {response['job_id']}\n"
                                    f"Estimated wait: {response.get('estimated_wait_seconds', 30)} seconds\n"
                                    f"Use get_job_status with job_id to check progress"
                                )
                            elif response["status"] == "pending":
                                # Non-blocking job created
                                text = f"Message sent (job_id: {response['job_id']}, status: {response['status']})"
                            else:
                                # Other status response
                                text = f"Response: {response}"

                            result = {"content": [{"type": "text", "text": text}]}
                        elif response:
                            # Blocking: return actual response
                            result = {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": response.get("response", str(response)),
                                    }
                                ]
                            }
                        else:
                            # No response
                            result = {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Message sent but no response received",
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
                            "content": [{"type": "text", "text": json.dumps(output, indent=2)}]
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
                                    "text": f"Coordination completed: {coordination_result}",
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
                                    "text": f"Instance {tool_args['instance_id']} terminated"
                                    if success
                                    else f"Failed to terminate {tool_args['instance_id']}",
                                }
                            ]
                        }

                    elif tool_name == "get_job_status":
                        job_status = await self.manager.get_job_status(
                            job_id=tool_args["job_id"],
                            wait_for_completion=tool_args.get("wait_for_completion", True),
                            max_wait=tool_args.get("max_wait", 120),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(job_status, indent=2)
                                    if job_status
                                    else "Job not found",
                                }
                            ]
                        }

                    elif tool_name == "get_instance_status":
                        status = self.manager.get_instance_status(
                            instance_id=tool_args.get("instance_id")
                        )
                        result = {
                            "content": [{"type": "text", "text": json.dumps(status, indent=2)}]
                        }

                    elif tool_name == "retrieve_instance_file":
                        file_path = await self.manager.retrieve_instance_file(
                            instance_id=tool_args["instance_id"],
                            filename=tool_args["filename"],
                            destination_path=tool_args.get("destination_path"),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"File retrieved successfully to: {file_path}"
                                    if file_path
                                    else "File not found",
                                }
                            ]
                        }

                    elif tool_name == "list_instance_files":
                        files = await self.manager.list_instance_files(
                            instance_id=tool_args["instance_id"]
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(files, indent=2)
                                    if files
                                    else "No files found or instance not found",
                                }
                            ]
                        }

                    elif tool_name == "spawn_codex_instance":
                        instance_id = await self.manager.spawn_codex_instance(
                            name=tool_args.get("name", "unnamed"),
                            model=tool_args.get("model"),  # None = use CLI default
                            sandbox_mode=tool_args.get("sandbox_mode", "workspace-write"),
                            profile=tool_args.get("profile"),
                            initial_prompt=tool_args.get("initial_prompt"),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Spawned Codex instance '{tool_args.get('name')}' with ID: {instance_id}",
                                }
                            ]
                        }

                    else:
                        result = {
                            "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                        }

                else:
                    result = {"error": {"code": -32601, "message": f"Method not found: {method}"}}

                # Return JSON-RPC response
                response = {"jsonrpc": "2.0", "id": request_id, "result": result}

                return Response(content=json.dumps(response), media_type="application/json")

            except Exception as e:
                logger.error(f"Error handling MCP request: {e}")
                return Response(
                    content=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": body.get("id") if "body" in locals() else None,
                            "error": {"code": -32603, "message": str(e)},
                        }
                    ),
                    media_type="application/json",
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
                        "data": json.dumps(
                            {"jsonrpc": "2.0", "method": "connection/ready", "params": {}}
                        ),
                    }

                    # Keep connection alive
                    import asyncio

                    while True:
                        await asyncio.sleep(30)
                        yield {"event": "ping", "data": json.dumps({"timestamp": "now"})}

                except Exception as e:
                    logger.error(f"SSE error: {e}")
                    yield {"event": "error", "data": json.dumps({"error": str(e)})}

            return EventSourceResponse(event_generator())

        @self.router.get("/health")
        async def mcp_health():
            """MCP health check endpoint."""
            return {
                "status": "healthy",
                "server": "claude-orchestrator",
                "version": "1.0.0",
                "transport": "sse",
            }
