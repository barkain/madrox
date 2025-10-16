"""MCP Protocol adapter for the existing FastAPI server."""

import asyncio
import json
import logging

from fastapi import APIRouter, Request, Response
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)


class MCPAdapter:
    """Adapter to expose FastAPI endpoints as MCP-compliant SSE endpoints."""

    def __init__(self, instance_manager):
        """Initialize the MCP adapter with instance manager."""
        self.manager = instance_manager
        self.router = APIRouter(prefix="/mcp")
        self._tools_list = None  # Cache for tools list (lazy-loaded)
        self._register_routes()

    async def get_available_tools(self) -> list[dict]:
        """Get list of available MCP tools.

        Returns:
            List of tool definitions with name, description, and inputSchema
        """
        if self._tools_list is None:
            # Build tools list on first access
            self._tools_list = await self._build_tools_list()
        return self._tools_list

    async def _build_tools_list(self) -> list[dict]:
        """Build the list of available MCP tools dynamically from FastMCP.

        Queries the InstanceManager's FastMCP instance for registered tools
        and transforms them to MCP protocol format.

        Returns:
            List of tool definitions with name, description, and inputSchema
        """
        # Get tools from FastMCP (returns dict[str, FunctionTool])
        tools_dict = await self.manager.mcp.get_tools()

        tools_list = []
        for tool_name, tool_obj in tools_dict.items():
            # Convert FastMCP tool to MCP protocol format
            mcp_tool = tool_obj.to_mcp_tool()

            # Filter out 'self' from inputSchema properties (artifact from method binding)
            input_schema = mcp_tool.inputSchema.copy()
            if 'properties' in input_schema and 'self' in input_schema['properties']:
                input_schema['properties'] = {
                    k: v for k, v in input_schema['properties'].items() if k != 'self'
                }
                if 'required' in input_schema and 'self' in input_schema['required']:
                    input_schema['required'] = [
                        r for r in input_schema['required'] if r != 'self'
                    ]

            tools_list.append({
                "name": mcp_tool.name,
                "description": mcp_tool.description,
                "inputSchema": input_schema,
            })

        logger.info(f"Built tools list: {len(tools_list)} tools discovered from FastMCP")
        return tools_list

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

    def _parse_template_metadata(self, template_content: str) -> dict:
        """Extract metadata from template markdown.

        Args:
            template_content: Template markdown content

        Returns:
            Dictionary with team_size, duration, estimated_cost, supervisor_role
        """
        lines = template_content.split('\n')

        # Parse Team Size from "Team Size: X instances"
        team_size = 6  # default
        for line in lines:
            if "Team Size" in line and "instances" in line:
                try:
                    # Extract number before "instances"
                    parts = line.split("instances")[0].split()
                    team_size = int(parts[-1])
                except (ValueError, IndexError):
                    pass

        # Parse Duration from "Estimated Duration: X hours"
        duration = "2-4 hours"
        for line in lines:
            if "Estimated Duration" in line or "Duration:" in line:
                # Extract everything after the colon
                if ":" in line:
                    duration = line.split(":", 1)[-1].strip()

        # Parse Supervisor Role from markdown
        supervisor_role = "general"
        in_supervisor_section = False
        for line in lines:
            # Look for supervisor section headers
            if any(header in line for header in ["### Technical Lead", "### Research Lead",
                                                   "### Security Lead", "### Data Engineering Lead"]):
                in_supervisor_section = True
            elif line.startswith("###"):
                in_supervisor_section = False

            # Extract role from **Role**: `role_name`
            if in_supervisor_section and "**Role**:" in line:
                if "`" in line:
                    supervisor_role = line.split("`")[1]
                    break

        return {
            "team_size": team_size,
            "duration": duration,
            "estimated_cost": f"${team_size * 5}",
            "supervisor_role": supervisor_role
        }

    def _extract_section(self, content: str, header: str) -> str:
        """Extract markdown section by header.

        Args:
            content: Markdown content
            header: Section header (e.g., "## Workflow Phases")

        Returns:
            Section content
        """
        lines = content.split('\n')
        section_lines = []
        in_section = False

        for line in lines:
            if line.strip().startswith(header):
                in_section = True
                continue
            if in_section and line.startswith("## ") and line.strip() != header:
                break
            if in_section:
                section_lines.append(line)

        return '\n'.join(section_lines).strip()

    def _build_template_instruction(self, template_content: str, task_description: str) -> str:
        """Build instruction message for supervisor from template.

        Args:
            template_content: Template markdown content
            task_description: User's specific task description

        Returns:
            Instruction message for supervisor
        """
        # Extract key sections
        team_structure = self._extract_section(template_content, "## Team Structure")
        workflow_phases = self._extract_section(template_content, "## Workflow Phases")
        communication = self._extract_section(template_content, "## Communication Protocols")

        instruction = f"""Execute the team workflow from this template:

TASK DESCRIPTION:
{task_description}

TEAM STRUCTURE TO SPAWN:
{team_structure[:500]}... [See full template for details]

WORKFLOW PHASES TO EXECUTE:
{workflow_phases[:800]}... [See full template for details]

COMMUNICATION PROTOCOLS TO USE:
{communication[:400]}... [See full template for details]

CRITICAL EXECUTION INSTRUCTIONS:
1. Spawn your team members with parent_instance_id set to YOUR instance_id
2. Use broadcast_to_children for team-wide announcements
3. Use send_to_instance for 1-on-1 coordination
4. Workers MUST use reply_to_caller to report back to you
5. Poll get_pending_replies every 5-15 minutes to collect worker responses
6. Follow the workflow phases sequentially as outlined in the template
7. Report final deliverables and status when complete

Begin execution now. Spawn your team and start the workflow."""

        return instruction

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
                    # Use dynamically generated tools list from FastMCP
                    result = {"tools": await self.get_available_tools()}

                elif method == "tools/call":
                    tool_name = params.get("name")
                    tool_args = params.get("arguments", {})

                    # AUTO-DETECT CALLER INSTANCE (for parent_instance_id injection)
                    # Strategy: Find instances currently in "busy" state - they're actively executing tools
                    caller_instance_id = None

                    # First pass: Look for busy instances (actively making MCP calls)
                    busy_instances = []
                    for instance_id, instance_data in self.manager.instances.items():
                        if instance_data.get("state") == "busy" and instance_data.get("enable_madrox"):
                            busy_instances.append((instance_id, instance_data.get("last_activity")))

                    if busy_instances:
                        # If multiple busy instances, pick most recently active
                        busy_instances.sort(key=lambda x: x[1] if x[1] else "", reverse=True)
                        caller_instance_id = busy_instances[0][0]
                        logger.info(f"Auto-detected BUSY caller instance: {caller_instance_id}")
                    else:
                        # Fallback: Find most recently active instance with madrox that has made requests
                        latest_activity = None
                        for instance_id, instance_data in self.manager.instances.items():
                            if not instance_data.get("enable_madrox", False):
                                continue
                            if instance_data.get("state") == "terminated":
                                continue
                            if instance_data.get("request_count", 0) == 0:
                                continue

                            last_activity = instance_data.get("last_activity")
                            if last_activity:
                                if latest_activity is None or last_activity > latest_activity:
                                    latest_activity = last_activity
                                    caller_instance_id = instance_id

                        if caller_instance_id:
                            logger.info(f"Auto-detected ACTIVE caller instance (fallback): {caller_instance_id}")

                    # Execute the tool
                    if tool_name == "spawn_claude":
                        # AUTO-INJECT parent_instance_id if not provided and caller detected
                        parent_id = tool_args.get("parent_instance_id")
                        if not parent_id and caller_instance_id:
                            parent_id = caller_instance_id
                            logger.info(
                                f"Auto-injected parent_instance_id={caller_instance_id} for spawn_claude call from managed instance"
                            )

                        # Supervision pattern validation: Workers MUST have madrox enabled
                        enable_madrox = tool_args.get("enable_madrox", True)

                        if parent_id and not enable_madrox:
                            logger.warning(
                                f"Forcing enable_madrox=True for supervised instance '{tool_args.get('name')}' "
                                f"with parent {parent_id}. Workers must have madrox enabled for bidirectional communication."
                            )
                            enable_madrox = True

                        instance_id = await self.manager.spawn_instance(
                            name=tool_args.get("name", "unnamed"),
                            role=tool_args.get("role", "general"),
                            system_prompt=tool_args.get("system_prompt"),
                            model=tool_args.get("model"),  # None = use CLI default
                            bypass_isolation=tool_args.get("bypass_isolation", False),
                            enable_madrox=enable_madrox,
                            wait_for_ready=tool_args.get("wait_for_ready", True),
                            parent_instance_id=parent_id,
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
                            # AUTO-INJECT parent_instance_id if not provided and caller detected
                            parent_id = instance_config.get("parent_instance_id")
                            if not parent_id and caller_instance_id:
                                parent_id = caller_instance_id
                                logger.info(
                                    f"Auto-injected parent_instance_id={caller_instance_id} for '{instance_config.get('name')}' in spawn_multiple_instances"
                                )

                            # Supervision pattern validation: Workers MUST have madrox enabled
                            enable_madrox = instance_config.get("enable_madrox", True)

                            if parent_id and not enable_madrox:
                                logger.warning(
                                    f"Forcing enable_madrox=True for supervised instance '{instance_config.get('name')}' "
                                    f"with parent {parent_id}. Workers must have madrox enabled for bidirectional communication."
                                )
                                enable_madrox = True

                            spawn_tasks.append(
                                self.manager.spawn_instance(
                                    name=instance_config.get("name", "unnamed"),
                                    role=instance_config.get("role", "general"),
                                    system_prompt=instance_config.get("system_prompt"),
                                    model=instance_config.get("model"),
                                    bypass_isolation=instance_config.get("bypass_isolation", False),
                                    enable_madrox=enable_madrox,
                                    wait_for_ready=instance_config.get("wait_for_ready", True),
                                    parent_instance_id=parent_id,
                                    mcp_servers=instance_config.get("mcp_servers", {}),
                                    instance_type=instance_config.get("instance_type", "claude"),
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
                        # Bypass decorator - call tmux_manager directly
                        instance_id = tool_args["instance_id"]
                        if instance_id not in self.manager.instances:
                            raise ValueError(f"Instance {instance_id} not found")

                        instance = self.manager.instances[instance_id]

                        # Delegate to TmuxInstanceManager
                        if instance.get("instance_type") in ["claude", "codex"]:
                            response = await self.manager.tmux_manager.send_message(
                                instance_id=instance_id,
                                message=tool_args["message"],
                                wait_for_response=tool_args.get("wait_for_response", False),
                                timeout_seconds=tool_args.get("timeout_seconds", 180),
                            )
                            if response is None:
                                response = {"status": "message_sent"}
                        else:
                            raise ValueError(f"Unsupported instance type: {instance.get('instance_type')}")

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

                        # Create send tasks for all instances - bypass decorator
                        async def send_message_bypass(msg_config):
                            instance_id = msg_config["instance_id"]
                            if instance_id not in self.manager.instances:
                                raise ValueError(f"Instance {instance_id} not found")

                            instance = self.manager.instances[instance_id]
                            if instance.get("instance_type") in ["claude", "codex"]:
                                result = await self.manager.tmux_manager.send_message(
                                    instance_id=instance_id,
                                    message=msg_config["message"],
                                    wait_for_response=msg_config.get("wait_for_response", True),
                                    timeout_seconds=msg_config.get("timeout_seconds", 180),
                                )
                                return result or {"status": "message_sent"}
                            else:
                                raise ValueError(f"Unsupported instance type: {instance.get('instance_type')}")

                        send_tasks = []
                        for msg_config in messages_config:
                            send_tasks.append(send_message_bypass(msg_config))

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
                        # Bypass decorator - use internal helper
                        messages = await self.manager._get_output_messages(
                            instance_id=tool_args["instance_id"],
                            limit=tool_args.get("limit", 100),
                            since=tool_args.get("since"),
                        )
                        output = {
                            "instance_id": tool_args["instance_id"],
                            "output": messages
                        }
                        result = {
                            "content": [{"type": "text", "text": json.dumps(output, indent=2)}]
                        }

                    elif tool_name == "coordinate_instances":
                        # Bypass decorator - inline coordination logic
                        import uuid
                        from datetime import UTC, datetime

                        task_id = str(uuid.uuid4())
                        coordinator_id = tool_args["coordinator_id"]
                        participant_ids = tool_args["participant_ids"]
                        task_description = tool_args["task_description"]
                        coordination_type = tool_args.get("coordination_type", "sequential")

                        # Validate all instances exist
                        all_ids = [coordinator_id] + participant_ids
                        for iid in all_ids:
                            if iid not in self.manager.instances:
                                raise ValueError(f"Instance {iid} not found")
                            if self.manager.instances[iid]["state"] not in ["running", "idle"]:
                                raise RuntimeError(f"Instance {iid} is not available")

                        # Start coordination in background
                        coordination_task = {
                            "task_id": task_id,
                            "description": task_description,
                            "coordinator_id": coordinator_id,
                            "participant_ids": participant_ids,
                            "coordination_type": coordination_type,
                            "status": "running",
                            "started_at": datetime.now(UTC).isoformat(),
                            "steps": [],
                            "results": {},
                        }
                        asyncio.create_task(self.manager._execute_coordination(coordination_task))

                        coordination_result = {"task_id": task_id, "status": "started"}
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Coordination completed: {coordination_result}",
                                }
                            ]
                        }

                    elif tool_name == "interrupt_instance":
                        # Bypass decorator - use internal method
                        interrupt_result = await self.manager._interrupt_instance_internal(
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

                        # Create interrupt tasks for all instances - bypass decorator
                        interrupt_tasks = []
                        for instance_id in instance_ids:
                            interrupt_tasks.append(
                                self.manager._interrupt_instance_internal(instance_id=instance_id)
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
                                # result_item is dict but success=False or not a dict
                                error_msg = (
                                    result_item.get("error", "Unknown error")
                                    if isinstance(result_item, dict)
                                    else f"Unexpected result: {result_item}"
                                )
                                errors.append(
                                    {
                                        "instance_id": instance_id,
                                        "error": error_msg,
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
                        # Bypass decorator - use internal method
                        success = await self.manager._terminate_instance_internal(
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

                        # Create termination tasks for all instances - bypass decorator
                        terminate_tasks = []
                        for instance_id in instance_ids:
                            terminate_tasks.append(
                                self.manager._terminate_instance_internal(
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

                        # Create tasks for all output requests - bypass decorator
                        output_tasks = []
                        for req in requests:
                            output_tasks.append(
                                self.manager._get_output_messages(
                                    instance_id=req["instance_id"],
                                    limit=req.get("limit", 100),
                                    since=req.get("since"),
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

                        # Create tasks for all file retrievals - bypass decorator
                        retrieve_tasks = []
                        for req in requests:
                            retrieve_tasks.append(
                                self.manager._retrieve_instance_file_internal(
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

                        # Create tasks for all list operations - bypass decorator
                        list_tasks = []
                        for instance_id in instance_ids:
                            list_tasks.append(
                                self.manager._list_instance_files_internal(instance_id=instance_id)
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
                        # Bypass decorator - inline job status logic
                        job_id = tool_args["job_id"]
                        wait_for_completion = tool_args.get("wait_for_completion", True)
                        max_wait = tool_args.get("max_wait", 120)

                        if job_id not in self.manager.jobs:
                            job_status = None
                        else:
                            job = self.manager.jobs[job_id]
                            if not wait_for_completion or job["status"] in ["completed", "failed", "timeout"]:
                                job_status = job
                            else:
                                # Wait for completion
                                start_time = asyncio.get_event_loop().time()
                                while asyncio.get_event_loop().time() - start_time < max_wait:
                                    job = self.manager.jobs[job_id]
                                    if job["status"] in ["completed", "failed", "timeout"]:
                                        break
                                    await asyncio.sleep(1)
                                job_status = self.manager.jobs[job_id]

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
                        # Bypass decorator - use internal method
                        status = self.manager._get_instance_status_internal(
                            instance_id=tool_args.get("instance_id")
                        )
                        result = {
                            "content": [{"type": "text", "text": json.dumps(status, indent=2)}]
                        }

                    elif tool_name == "get_live_instance_status":
                        instance_id = tool_args["instance_id"]

                        # Get basic instance status - bypass decorator
                        instance = self.manager._get_instance_status_internal(instance_id)

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
                        # Bypass decorator - use internal method
                        children = self.manager._get_children_internal(parent_id=tool_args["parent_id"])
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
                        # Bypass decorator - inline implementation
                        parent_id = tool_args["parent_id"]
                        message = tool_args["message"]
                        wait_for_responses = tool_args.get("wait_for_responses", False)

                        children = self.manager._get_children_internal(parent_id)

                        if not children:
                            broadcast_result = {"children_count": 0, "results": []}
                        else:
                            # Send to all children in parallel - bypass decorator
                            async def send_to_child(child):
                                instance_id = child["id"]
                                if instance_id not in self.manager.instances:
                                    raise ValueError(f"Instance {instance_id} not found")

                                instance = self.manager.instances[instance_id]
                                if instance.get("instance_type") in ["claude", "codex"]:
                                    result = await self.manager.tmux_manager.send_message(
                                        instance_id=instance_id,
                                        message=message,
                                        wait_for_response=wait_for_responses,
                                    )
                                    return result or {"status": "message_sent"}
                                else:
                                    raise ValueError(f"Unsupported instance type: {instance.get('instance_type')}")

                            tasks = [send_to_child(child) for child in children]
                            results = await asyncio.gather(*tasks, return_exceptions=True)

                            # Format results
                            formatted_results = []
                            for i, child in enumerate(children):
                                result = results[i]
                                if isinstance(result, Exception):
                                    formatted_results.append({
                                        "child_id": child["id"],
                                        "child_name": child["name"],
                                        "status": "error",
                                        "error": str(result),
                                    })
                                else:
                                    formatted_results.append({
                                        "child_id": child["id"],
                                        "child_name": child["name"],
                                        "status": "sent" if not wait_for_responses else "completed",
                                        "response": result if wait_for_responses else None,
                                    })

                            broadcast_result = {
                                "children_count": len(children),
                                "results": formatted_results,
                            }

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
                        # Bypass decorator - inline tree building
                        roots = []
                        for instance_id, instance in self.manager.instances.items():
                            if not instance.get("parent_instance_id") and instance.get("state") != "terminated":
                                roots.append((instance_id, instance.get("name", "unknown")))

                        if not roots:
                            tree_output = "No instances running"
                        else:
                            roots.sort(key=lambda x: x[1])
                            lines = []
                            for i, (root_id, _) in enumerate(roots):
                                is_last_root = i == len(roots) - 1
                                self.manager._build_tree_recursive(root_id, "", is_last_root, lines, is_root=True)
                            tree_output = "\n".join(lines)

                        result = {
                            "content": [
                                {"type": "text", "text": f"Instance Hierarchy:\n\n{tree_output}"}
                            ]
                        }

                    elif tool_name == "retrieve_instance_file":
                        # Bypass decorator - use internal method
                        file_path = await self.manager._retrieve_instance_file_internal(
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
                        # Bypass decorator - use internal method
                        files = await self.manager._list_instance_files_internal(
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

                    elif tool_name == "spawn_codex":
                        # Call internal spawn_instance with codex type
                        instance_id = await self.manager.tmux_manager.spawn_instance(
                            name=tool_args.get("name", "unnamed"),
                            model=tool_args.get("model"),
                            bypass_isolation=tool_args.get("bypass_isolation", False),
                            sandbox_mode=tool_args.get("sandbox_mode", "workspace-write"),
                            profile=tool_args.get("profile"),
                            initial_prompt=tool_args.get("initial_prompt"),
                            instance_type="codex",
                            parent_instance_id=tool_args.get("parent_instance_id"),
                        )
                        # Copy to main instances dict
                        self.manager.instances[instance_id] = self.manager.tmux_manager.instances[instance_id]
                        self.manager.instances[instance_id]["instance_type"] = "codex"

                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Spawned Codex instance '{tool_args.get('name')}' with ID: {instance_id}",
                                }
                            ]
                        }

                    elif tool_name == "get_tmux_pane_content":
                        # Bypass decorator - inline tmux pane capture
                        instance_id = tool_args["instance_id"]
                        lines = tool_args.get("lines", 100)

                        if instance_id not in self.manager.instances:
                            raise ValueError(f"Instance {instance_id} not found")

                        try:
                            session = self.manager.tmux_manager.tmux_sessions.get(instance_id)
                            if not session:
                                raise RuntimeError(f"No tmux session found for instance {instance_id}")

                            window = session.windows[0]
                            pane = window.panes[0]

                            # Capture pane content
                            if lines == -1:
                                content = "\n".join(pane.cmd("capture-pane", "-p").stdout)
                            else:
                                content = "\n".join(pane.cmd("capture-pane", "-p", "-S", f"-{lines}").stdout)
                        except Exception as e:
                            logger.error(f"Failed to capture tmux pane for instance {instance_id}: {e}")
                            raise

                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": content,
                                }
                            ]
                        }

                    # DEPRECATED: get_main_instance_id tool removed
                    # Child instances should use their own instance_id in reply_to_caller, not main instance ID
                    # This tool was causing unwanted auto-spawning of main orchestrator instances
                    elif tool_name == "get_main_instance_id":
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "⚠️ DEPRECATED: This tool has been removed.\n\n"
                                    "Use your own instance_id in reply_to_caller, not the main instance ID.\n"
                                    "Your instance_id is already provided in your system prompt.",
                                }
                            ],
                            "isError": True,
                        }

                    elif tool_name == "reply_to_caller":
                        # Handle reply from instance to its caller
                        reply_result = await self.manager.handle_reply_to_caller(
                            instance_id=tool_args["instance_id"],
                            reply_message=tool_args["reply_message"],
                            correlation_id=tool_args.get("correlation_id"),
                        )

                        if reply_result["success"]:
                            # Format delivered_to: show first 8 chars of instance ID for readability
                            delivered_to = reply_result.get('delivered_to', 'caller')
                            if delivered_to and len(delivered_to) > 8 and delivered_to != 'coordinator':
                                delivered_to_display = f"{delivered_to[:8]}..."
                            else:
                                delivered_to_display = delivered_to

                            result = {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"✅ Reply delivered to {delivered_to_display}"
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

                    elif tool_name == "get_pending_replies":
                        # Poll response queue for pending replies from children
                        replies = await self.manager._get_pending_replies_internal(
                            instance_id=tool_args["instance_id"],
                            wait_timeout=tool_args.get("wait_timeout", 0),
                        )

                        if replies:
                            reply_text = f"📬 Received {len(replies)} pending replies:\n\n"
                            for idx, reply in enumerate(replies, 1):
                                sender = reply.get('sender_id', 'unknown')
                                sender_display = f"{sender[:8]}..." if len(sender) > 8 else sender
                                message = reply.get('reply_message', '')
                                correlation = reply.get('correlation_id', 'none')
                                reply_text += f"Reply #{idx} from {sender_display}:\n"
                                reply_text += f"  Message: {message}\n"
                                reply_text += f"  Correlation: {correlation}\n\n"

                            result = {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": reply_text.strip(),
                                    }
                                ]
                            }
                        else:
                            result = {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "📭 No pending replies in queue",
                                    }
                                ]
                            }

                    elif tool_name == "spawn_team_from_template":
                        # Spawn a complete team from a predefined template
                        from pathlib import Path

                        template_name = tool_args["template_name"]
                        task_description = tool_args["task_description"]
                        supervisor_role = tool_args.get("supervisor_role")

                        # Load template file
                        template_path = Path("templates") / f"{template_name}.md"
                        if not template_path.exists():
                            raise ValueError(
                                f"Template not found: {template_name}\n"
                                f"Available templates: software_engineering_team, research_analysis_team, "
                                f"security_audit_team, data_pipeline_team"
                            )

                        template_content = template_path.read_text()

                        # Parse template metadata
                        template_meta = self._parse_template_metadata(template_content)

                        # Use provided supervisor role or template default
                        role = supervisor_role or template_meta["supervisor_role"]

                        # Spawn supervisor
                        supervisor_id = await self.manager.spawn_instance(
                            name=f"{template_name}-lead",
                            role=role,
                            enable_madrox=True,
                            wait_for_ready=True,
                        )

                        # Build instruction message
                        instruction = self._build_template_instruction(
                            template_content=template_content,
                            task_description=task_description
                        )

                        # Send instructions to supervisor (non-blocking)
                        await self.manager.tmux_manager.send_message(
                            instance_id=supervisor_id,
                            message=instruction,
                            wait_for_response=False
                        )

                        # Wait briefly for network assembly
                        await asyncio.sleep(15)

                        # Get network tree preview
                        tree_preview = "Initializing network..."
                        try:
                            roots = []
                            for instance_id, instance in self.manager.instances.items():
                                if not instance.get("parent_instance_id") and instance.get("state") != "terminated":
                                    roots.append((instance_id, instance.get("name", "unknown")))

                            if roots:
                                roots.sort(key=lambda x: x[1])
                                lines = []
                                for i, (root_id, _) in enumerate(roots):
                                    is_last_root = i == len(roots) - 1
                                    self.manager._build_tree_recursive(root_id, "", is_last_root, lines, is_root=True)
                                tree_preview = "\n".join(lines)
                        except Exception as e:
                            logger.warning(f"Failed to build tree preview: {e}")

                        # Build result
                        result_text = f"""✅ Team spawned from template: {template_name}

📋 **Template Details:**
- Supervisor ID: {supervisor_id}
- Team Size: {template_meta['team_size']} instances
- Estimated Duration: {template_meta['duration']}
- Estimated Cost: {template_meta['estimated_cost']}
- Status: Initializing

🌳 **Network Topology:**
{tree_preview}

📝 **Task:**
{task_description[:200]}{'...' if len(task_description) > 200 else ''}

⏳ The supervisor is now spawning the team and executing the workflow.
Use get_pending_replies({supervisor_id}) to monitor progress.
Use get_instance_tree() to see the full network hierarchy."""

                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": result_text,
                                }
                            ]
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
