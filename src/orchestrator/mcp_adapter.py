"""MCP Protocol adapter for the existing FastAPI server."""

import asyncio
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

    def _inject_main_messages(self, result: dict) -> dict:
        """Inject pending main instance messages into the tool result.

        Args:
            result: Original tool result

        Returns:
            Result with main messages prepended
        """
        # Get pending messages from main inbox
        main_messages = self.manager.get_and_clear_main_inbox()

        if not main_messages:
            return result

        # Skip injection for error results
        if "error" in result:
            return result

        # Prepend main messages to content
        if "content" in result:
            main_content = []
            for msg in main_messages:
                main_content.append(
                    {
                        "type": "text",
                        "text": f"📨 Message from child instance:\n\n{msg.get('content', '')}",
                    }
                )

            # Prepend to existing content
            result["content"] = main_content + result["content"]

        return result

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
                                        "wait_for_ready": {
                                            "type": "boolean",
                                            "default": True,
                                            "description": "Wait for instance to initialize (default: true). Set to false for non-blocking spawn.",
                                        },
                                        "parent_instance_id": {
                                            "type": "string",
                                            "description": "Parent instance ID for tracking bidirectional communication (optional)",
                                        },
                                        "mcp_servers": {
                                            "type": "object",
                                            "description": "MCP servers to configure for this instance. Example: {'madrox': {'transport': 'http', 'url': 'http://localhost:8001/mcp'}}",
                                        },
                                    },
                                    "required": ["name"],
                                },
                            },
                            {
                                "name": "spawn_multiple_instances",
                                "description": "Spawn multiple Claude instances in parallel for better performance",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instances": {
                                            "type": "array",
                                            "description": "List of instance configurations to spawn",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {
                                                        "type": "string",
                                                        "description": "Instance name",
                                                    },
                                                    "role": {
                                                        "type": "string",
                                                        "enum": [
                                                            role.value for role in InstanceRole
                                                        ],
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
                                                        "default": True,
                                                        "description": "Enable madrox MCP server (allows spawning sub-instances)",
                                                    },
                                                    "wait_for_ready": {
                                                        "type": "boolean",
                                                        "default": True,
                                                        "description": "Wait for instance to initialize (default: true). Set to false for non-blocking spawn.",
                                                    },
                                                    "parent_instance_id": {
                                                        "type": "string",
                                                        "description": "Parent instance ID for tracking bidirectional communication (optional)",
                                                    },
                                                    "mcp_servers": {
                                                        "type": "object",
                                                        "description": "MCP servers to configure for this instance. Example: {'madrox': {'transport': 'http', 'url': 'http://localhost:8001/mcp'}}",
                                                    },
                                                },
                                                "required": ["name"],
                                            },
                                        },
                                    },
                                    "required": ["instances"],
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
                                "name": "send_to_multiple_instances",
                                "description": "Send messages to multiple Claude instances in parallel for better performance",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "messages": {
                                            "type": "array",
                                            "description": "List of messages to send to instances",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "instance_id": {"type": "string"},
                                                    "message": {"type": "string"},
                                                    "wait_for_response": {
                                                        "type": "boolean",
                                                        "default": True,
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
                                    },
                                    "required": ["messages"],
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
                                "name": "get_multiple_instance_outputs",
                                "description": "Get recent output from multiple Claude instances in parallel",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "requests": {
                                            "type": "array",
                                            "description": "List of output requests",
                                            "items": {
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
                                    },
                                    "required": ["requests"],
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
                                "name": "interrupt_instance",
                                "description": "Send interrupt signal (Ctrl+C / Escape) to stop current task without terminating the instance",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_id": {
                                            "type": "string",
                                            "description": "Instance ID to interrupt",
                                        },
                                    },
                                    "required": ["instance_id"],
                                },
                            },
                            {
                                "name": "interrupt_multiple_instances",
                                "description": "Send interrupt signal to multiple instances in parallel",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_ids": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "List of instance IDs to interrupt",
                                        },
                                    },
                                    "required": ["instance_ids"],
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
                                "name": "terminate_multiple_instances",
                                "description": "Terminate multiple Claude instances in parallel",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_ids": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "List of instance IDs to terminate",
                                        },
                                        "force": {
                                            "type": "boolean",
                                            "default": False,
                                            "description": "Force termination for all instances",
                                        },
                                    },
                                    "required": ["instance_ids"],
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
                                "name": "get_live_instance_status",
                                "description": "Get real-time execution status including current tool, execution time, tools executed, and last output",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_id": {
                                            "type": "string",
                                            "description": "Instance ID to get live status for",
                                        }
                                    },
                                    "required": ["instance_id"],
                                },
                            },
                            {
                                "name": "get_children",
                                "description": "Get all child instances of a parent instance",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "parent_id": {
                                            "type": "string",
                                            "description": "Parent instance ID",
                                        }
                                    },
                                    "required": ["parent_id"],
                                },
                            },
                            {
                                "name": "broadcast_to_children",
                                "description": "Broadcast a message to all children of a parent instance",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "parent_id": {
                                            "type": "string",
                                            "description": "Parent instance ID",
                                        },
                                        "message": {
                                            "type": "string",
                                            "description": "Message to broadcast to all children",
                                        },
                                        "wait_for_responses": {
                                            "type": "boolean",
                                            "description": "Wait for responses from all children (default: false)",
                                            "default": False,
                                        },
                                    },
                                    "required": ["parent_id", "message"],
                                },
                            },
                            {
                                "name": "get_instance_tree",
                                "description": "Get a hierarchical tree view of all running instances showing parent-child relationships",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {},
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
                                "name": "retrieve_multiple_instance_files",
                                "description": "Retrieve files from multiple instances' workspace directories in parallel",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "requests": {
                                            "type": "array",
                                            "description": "List of file retrieval requests",
                                            "items": {
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
                                    },
                                    "required": ["requests"],
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
                                "name": "list_multiple_instance_files",
                                "description": "List all files in multiple instances' workspace directories in parallel",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_ids": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "List of instance IDs to list files for",
                                        },
                                    },
                                    "required": ["instance_ids"],
                                },
                            },
                            {
                                "name": "get_tmux_pane_content",
                                "description": "Capture the current tmux pane content for an instance",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_id": {
                                            "type": "string",
                                            "description": "Instance ID",
                                        },
                                        "lines": {
                                            "type": "integer",
                                            "description": "Number of lines to capture (default: 100, -1 for all)",
                                            "default": 100,
                                        },
                                    },
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
                                        "parent_instance_id": {
                                            "type": "string",
                                            "description": "Parent instance ID for tracking bidirectional communication (optional)",
                                        },
                                        "mcp_servers": {
                                            "type": "object",
                                            "description": "MCP servers to configure for this instance. Example: {'playwright': {'command': 'npx', 'args': ['@playwright/mcp@latest']}}",
                                        },
                                    },
                                    "required": ["name"],
                                },
                            },
                            {
                                "name": "get_main_instance_id",
                                "description": "Get the main orchestrator instance ID for direct communication. Auto-spawns the main instance if not already running.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {},
                                },
                            },
                            {
                                "name": "reply_to_caller",
                                "description": "Reply back to the instance/coordinator that sent you a message. Use this to create bidirectional communication instead of just outputting text.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "instance_id": {
                                            "type": "string",
                                            "description": "Your instance ID (the responder)",
                                        },
                                        "reply_message": {
                                            "type": "string",
                                            "description": "Your reply content",
                                        },
                                        "correlation_id": {
                                            "type": "string",
                                            "description": "Message ID from the incoming message (optional, for correlation)",
                                        },
                                    },
                                    "required": ["instance_id", "reply_message"],
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
                            enable_madrox=tool_args.get("enable_madrox", True),
                            wait_for_ready=tool_args.get("wait_for_ready", True),
                            parent_instance_id=tool_args.get("parent_instance_id"),
                            mcp_servers=tool_args.get("mcp_servers", {}),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Spawned instance '{tool_args.get('name')}' with ID: {instance_id}",
                                }
                            ]
                        }

                    elif tool_name == "spawn_multiple_instances":
                        instances_config = tool_args.get("instances", [])

                        # Create spawn tasks for all instances
                        spawn_tasks = []
                        for instance_config in instances_config:
                            spawn_tasks.append(
                                self.manager.spawn_instance(
                                    name=instance_config.get("name", "unnamed"),
                                    role=instance_config.get("role", "general"),
                                    system_prompt=instance_config.get("system_prompt"),
                                    model=instance_config.get("model"),
                                    bypass_isolation=instance_config.get("bypass_isolation", False),
                                    enable_madrox=instance_config.get("enable_madrox", True),
                                    wait_for_ready=instance_config.get("wait_for_ready", True),
                                    parent_instance_id=instance_config.get("parent_instance_id"),
                                    mcp_servers=instance_config.get("mcp_servers", {}),
                                )
                            )

                        # Execute all spawns in parallel
                        results = await asyncio.gather(*spawn_tasks, return_exceptions=True)

                        # Process results
                        spawned_instances = []
                        errors = []

                        for idx, spawn_result in enumerate(results):
                            if isinstance(spawn_result, Exception):
                                errors.append(
                                    {
                                        "index": idx,
                                        "name": instances_config[idx].get("name", "unknown"),
                                        "error": str(spawn_result),
                                    }
                                )
                            else:
                                # spawn_result is the instance_id
                                spawned_instances.append(
                                    {
                                        "name": instances_config[idx].get("name"),
                                        "instance_id": spawn_result,
                                    }
                                )

                        # Build response text
                        response_lines = [
                            f"Spawned {len(spawned_instances)}/{len(instances_config)} instances successfully"
                        ]

                        if spawned_instances:
                            response_lines.append("\nSuccessfully spawned:")
                            for instance in spawned_instances:
                                response_lines.append(
                                    f"  - {instance['name']}: {instance['instance_id']}"
                                )

                        if errors:
                            response_lines.append("\nErrors:")
                            for error in errors:
                                response_lines.append(f"  - {error['name']}: {error['error']}")

                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "\n".join(response_lines),
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

                    elif tool_name == "send_to_multiple_instances":
                        messages_config = tool_args.get("messages", [])

                        # Create send tasks for all instances
                        send_tasks = []
                        for msg_config in messages_config:
                            send_tasks.append(
                                self.manager.send_to_instance(
                                    instance_id=msg_config["instance_id"],
                                    message=msg_config["message"],
                                    wait_for_response=msg_config.get("wait_for_response", True),
                                    timeout_seconds=msg_config.get("timeout_seconds", 180),
                                )
                            )

                        # Execute all sends in parallel
                        results = await asyncio.gather(*send_tasks, return_exceptions=True)

                        # Process results
                        successful_sends = []
                        errors = []

                        for idx, send_result in enumerate(results):
                            msg_config = messages_config[idx]
                            instance_id = msg_config["instance_id"]

                            if isinstance(send_result, Exception):
                                errors.append(
                                    {
                                        "instance_id": instance_id,
                                        "error": str(send_result),
                                    }
                                )
                            elif isinstance(send_result, dict):
                                # Successful send
                                successful_sends.append(
                                    {
                                        "instance_id": instance_id,
                                        "response": send_result.get("response", "Sent"),
                                    }
                                )
                            else:
                                # Unexpected result type
                                successful_sends.append(
                                    {
                                        "instance_id": instance_id,
                                        "response": str(send_result),
                                    }
                                )

                        # Build response text
                        response_lines = [
                            f"Sent to {len(successful_sends)}/{len(messages_config)} instances successfully"
                        ]

                        if successful_sends:
                            response_lines.append("\nResponses:")
                            for send_info in successful_sends:
                                response_lines.append(
                                    f"\n--- {send_info['instance_id']} ---\n{send_info['response']}"
                                )

                        if errors:
                            response_lines.append("\nErrors:")
                            for error in errors:
                                response_lines.append(
                                    f"  - {error['instance_id']}: {error['error']}"
                                )

                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "\n".join(response_lines),
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

                    elif tool_name == "interrupt_instance":
                        interrupt_result = await self.manager.interrupt_instance(
                            instance_id=tool_args["instance_id"]
                        )
                        if interrupt_result["success"]:
                            result = {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"⏸️ Interrupt signal sent to instance {tool_args['instance_id']}\n"
                                        f"Current task stopped, instance remains active and ready for new messages.",
                                    }
                                ]
                            }
                        else:
                            result = {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"❌ Failed to interrupt instance {tool_args['instance_id']}: "
                                        f"{interrupt_result.get('error', 'Unknown error')}",
                                    }
                                ],
                                "isError": True,
                            }

                    elif tool_name == "interrupt_multiple_instances":
                        instance_ids = tool_args.get("instance_ids", [])

                        # Create interrupt tasks for all instances
                        interrupt_tasks = []
                        for instance_id in instance_ids:
                            interrupt_tasks.append(
                                self.manager.interrupt_instance(instance_id=instance_id)
                            )

                        # Execute all interrupts in parallel
                        results = await asyncio.gather(*interrupt_tasks, return_exceptions=True)

                        # Process results
                        interrupted_instances = []
                        errors = []

                        for idx, result_item in enumerate(results):
                            instance_id = instance_ids[idx]
                            if isinstance(result_item, Exception):
                                errors.append(
                                    {"instance_id": instance_id, "error": str(result_item)}
                                )
                            elif isinstance(result_item, dict) and result_item.get("success"):
                                interrupted_instances.append(instance_id)
                            else:
                                errors.append(
                                    {
                                        "instance_id": instance_id,
                                        "error": result_item.get("error", "Unknown error"),
                                    }
                                )

                        # Build response message
                        message_parts = []
                        if interrupted_instances:
                            message_parts.append(
                                f"⏸️ Interrupted {len(interrupted_instances)}/{len(instance_ids)} instances successfully:\n"
                                + "\n".join(f"  - {iid}" for iid in interrupted_instances)
                            )
                        if errors:
                            message_parts.append(
                                f"\n❌ Errors ({len(errors)}):\n"
                                + "\n".join(f"  - {e['instance_id']}: {e['error']}" for e in errors)
                            )

                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "\n".join(message_parts)
                                    if message_parts
                                    else "No instances interrupted",
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

                    elif tool_name == "terminate_multiple_instances":
                        instance_ids = tool_args.get("instance_ids", [])
                        force = tool_args.get("force", False)

                        # Create termination tasks for all instances
                        terminate_tasks = []
                        for instance_id in instance_ids:
                            terminate_tasks.append(
                                self.manager.terminate_instance(
                                    instance_id=instance_id, force=force
                                )
                            )

                        # Execute all terminations in parallel
                        results = await asyncio.gather(*terminate_tasks, return_exceptions=True)

                        # Process results
                        terminated_instances = []
                        errors = []

                        for idx, terminate_result in enumerate(results):
                            instance_id = instance_ids[idx]

                            if isinstance(terminate_result, Exception):
                                errors.append(
                                    {"instance_id": instance_id, "error": str(terminate_result)}
                                )
                            elif terminate_result:
                                # Successfully terminated
                                terminated_instances.append(instance_id)
                            else:
                                # Termination failed (returned False)
                                errors.append(
                                    {
                                        "instance_id": instance_id,
                                        "error": "Termination failed (try with force=true)",
                                    }
                                )

                        # Build response text
                        response_lines = [
                            f"Terminated {len(terminated_instances)}/{len(instance_ids)} instances successfully"
                        ]

                        if terminated_instances:
                            response_lines.append("\nSuccessfully terminated:")
                            for instance_id in terminated_instances:
                                response_lines.append(f"  - {instance_id}")

                        if errors:
                            response_lines.append("\nErrors:")
                            for error in errors:
                                response_lines.append(
                                    f"  - {error['instance_id']}: {error['error']}"
                                )

                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "\n".join(response_lines),
                                }
                            ]
                        }

                    elif tool_name == "get_multiple_instance_outputs":
                        requests = tool_args.get("requests", [])

                        # Create tasks for all output requests
                        output_tasks = []
                        for req in requests:
                            output_tasks.append(
                                self.manager.get_instance_output(
                                    instance_id=req["instance_id"],
                                    since=req.get("since"),
                                    limit=req.get("limit", 100),
                                )
                            )

                        # Execute all in parallel
                        results = await asyncio.gather(*output_tasks, return_exceptions=True)

                        # Process results
                        outputs = []
                        errors = []

                        for idx, output_result in enumerate(results):
                            instance_id = requests[idx]["instance_id"]

                            if isinstance(output_result, Exception):
                                errors.append(
                                    {"instance_id": instance_id, "error": str(output_result)}
                                )
                            else:
                                outputs.append(
                                    {"instance_id": instance_id, "output": output_result}
                                )

                        # Build response
                        response_data = {"outputs": outputs, "errors": errors}
                        result = {
                            "content": [
                                {"type": "text", "text": json.dumps(response_data, indent=2)}
                            ]
                        }

                    elif tool_name == "retrieve_multiple_instance_files":
                        requests = tool_args.get("requests", [])

                        # Create tasks for all file retrievals
                        retrieve_tasks = []
                        for req in requests:
                            retrieve_tasks.append(
                                self.manager.retrieve_instance_file(
                                    instance_id=req["instance_id"],
                                    filename=req["filename"],
                                    destination_path=req.get("destination_path"),
                                )
                            )

                        # Execute all in parallel
                        results = await asyncio.gather(*retrieve_tasks, return_exceptions=True)

                        # Process results
                        retrieved_files = []
                        errors = []

                        for idx, retrieve_result in enumerate(results):
                            req = requests[idx]
                            instance_id = req["instance_id"]
                            filename = req["filename"]

                            if isinstance(retrieve_result, Exception):
                                errors.append(
                                    {
                                        "instance_id": instance_id,
                                        "filename": filename,
                                        "error": str(retrieve_result),
                                    }
                                )
                            elif retrieve_result:
                                retrieved_files.append(
                                    {
                                        "instance_id": instance_id,
                                        "filename": filename,
                                        "path": retrieve_result,
                                    }
                                )
                            else:
                                errors.append(
                                    {
                                        "instance_id": instance_id,
                                        "filename": filename,
                                        "error": "File not found",
                                    }
                                )

                        # Build response text
                        response_lines = [
                            f"Retrieved {len(retrieved_files)}/{len(requests)} files successfully"
                        ]

                        if retrieved_files:
                            response_lines.append("\nRetrieved files:")
                            for file_info in retrieved_files:
                                response_lines.append(
                                    f"  - {file_info['instance_id']}/{file_info['filename']}: {file_info['path']}"
                                )

                        if errors:
                            response_lines.append("\nErrors:")
                            for error in errors:
                                response_lines.append(
                                    f"  - {error['instance_id']}/{error['filename']}: {error['error']}"
                                )

                        result = {"content": [{"type": "text", "text": "\n".join(response_lines)}]}

                    elif tool_name == "list_multiple_instance_files":
                        instance_ids = tool_args.get("instance_ids", [])

                        # Create tasks for all list operations
                        list_tasks = []
                        for instance_id in instance_ids:
                            list_tasks.append(
                                self.manager.list_instance_files(instance_id=instance_id)
                            )

                        # Execute all in parallel
                        results = await asyncio.gather(*list_tasks, return_exceptions=True)

                        # Process results
                        file_listings = []
                        errors = []

                        for idx, list_result in enumerate(results):
                            instance_id = instance_ids[idx]

                            if isinstance(list_result, Exception):
                                errors.append(
                                    {"instance_id": instance_id, "error": str(list_result)}
                                )
                            elif list_result:
                                file_listings.append(
                                    {"instance_id": instance_id, "files": list_result}
                                )
                            else:
                                file_listings.append({"instance_id": instance_id, "files": []})

                        # Build response
                        response_data = {"listings": file_listings, "errors": errors}
                        result = {
                            "content": [
                                {"type": "text", "text": json.dumps(response_data, indent=2)}
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

                    elif tool_name == "get_live_instance_status":
                        instance_id = tool_args["instance_id"]

                        # Get basic instance status
                        instance = self.manager.get_instance_status(instance_id)

                        # Get event statistics from tmux_manager
                        event_stats = self.manager.tmux_manager.get_event_statistics(instance_id)

                        # Get most recent assistant output from message history
                        last_output = None
                        message_history = self.manager.tmux_manager.message_history.get(
                            instance_id, []
                        )
                        if message_history:
                            # Get the last assistant message as last_output
                            for event in reversed(message_history):
                                if event.get("role") == "assistant":
                                    content = event.get("content", "")
                                    last_output = (
                                        content[:200] + "..." if len(content) > 200 else content
                                    )
                                    break

                        # Calculate execution time (uptime)
                        from datetime import datetime

                        created_at = datetime.fromisoformat(instance["created_at"])
                        now = (
                            datetime.now(created_at.tzinfo)
                            if created_at.tzinfo
                            else datetime.utcnow()
                        )
                        execution_time = (now - created_at).total_seconds()

                        live_status = {
                            "instance_id": instance_id,
                            "state": instance["state"],
                            "current_tool": None,  # Not available in interactive mode
                            "execution_time": execution_time,
                            "tools_executed": 0,  # Not available in interactive mode
                            "last_output": last_output,
                            "last_activity": instance["last_activity"],
                            "tools_breakdown": {},  # Not available in interactive mode
                            "event_counts": event_stats.get("event_counts", {}),
                            "note": "Tool tracking not available in interactive mode. Use get_tmux_pane_content for detailed output.",
                        }

                        result = {
                            "content": [{"type": "text", "text": json.dumps(live_status, indent=2)}]
                        }

                    elif tool_name == "get_children":
                        children = self.manager.get_children(parent_id=tool_args["parent_id"])
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Found {len(children)} children:\n\n"
                                    + json.dumps(children, indent=2),
                                }
                            ]
                        }

                    elif tool_name == "broadcast_to_children":
                        broadcast_result = await self.manager.broadcast_to_children(
                            parent_id=tool_args["parent_id"],
                            message=tool_args["message"],
                            wait_for_responses=tool_args.get("wait_for_responses", False),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Broadcasted to {broadcast_result['children_count']} children\n\n"
                                    + json.dumps(broadcast_result["results"], indent=2),
                                }
                            ]
                        }

                    elif tool_name == "get_instance_tree":
                        tree_output = self.manager.get_instance_tree()
                        result = {
                            "content": [
                                {"type": "text", "text": f"Instance Hierarchy:\n\n{tree_output}"}
                            ]
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
                            parent_instance_id=tool_args.get("parent_instance_id"),
                            mcp_servers=tool_args.get("mcp_servers", {}),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Spawned Codex instance '{tool_args.get('name')}' with ID: {instance_id}",
                                }
                            ]
                        }

                    elif tool_name == "get_tmux_pane_content":
                        content = await self.manager.get_tmux_pane_content(
                            instance_id=tool_args["instance_id"],
                            lines=tool_args.get("lines", 100),
                        )
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": content,
                                }
                            ]
                        }

                    elif tool_name == "get_main_instance_id":
                        # Ensure main instance is spawned
                        main_id = await self.manager.ensure_main_instance()
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Main instance ID: {main_id}\n\nUse this ID to send messages directly to the main orchestrator:\nsend_to_instance(instance_id='{main_id}', message='your message')",
                                }
                            ]
                        }

                    elif tool_name == "reply_to_caller":
                        # Handle reply from instance to its caller
                        reply_result = await self.manager.handle_reply_to_caller(
                            instance_id=tool_args["instance_id"],
                            reply_message=tool_args["reply_message"],
                            correlation_id=tool_args.get("correlation_id"),
                        )

                        if reply_result["success"]:
                            result = {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"✅ Reply delivered to {reply_result.get('delivered_to', 'caller')}"
                                        + (
                                            f" (correlated with message {reply_result.get('correlation_id')})"
                                            if reply_result.get("correlation_id")
                                            else ""
                                        ),
                                    }
                                ]
                            }
                        else:
                            result = {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"❌ Failed to deliver reply: {reply_result.get('error', 'Unknown error')}",
                                    }
                                ],
                                "isError": True,
                            }

                    else:
                        result = {
                            "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                        }

                else:
                    result = {"error": {"code": -32601, "message": f"Method not found: {method}"}}

                # Inject pending main instance messages into the response
                result = self._inject_main_messages(result)

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
