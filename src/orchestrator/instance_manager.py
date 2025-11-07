"""Instance Manager for Claude Orchestrator."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .config import validate_model
from .logging_manager import LoggingManager
from .tmux_instance_manager import TmuxInstanceManager

logger = logging.getLogger(__name__)

# Create FastMCP instance at module level for decorator use
mcp = FastMCP("claude-orchestrator")


class InstanceManager:
    """Manages Claude instances and their lifecycle with MCP tools."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the instance manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.mcp = mcp  # Reference module-level mcp instance
        self.instances: dict[str, dict[str, Any]] = {}

        # Job tracking for async messages
        self.jobs: dict[str, dict[str, Any]] = {}  # job_id -> job metadata

        # Resource tracking
        self.total_tokens_used = 0
        self.total_cost = 0.0

        # Create workspace base directory
        self.workspace_base = Path(config.get("workspace_base_dir", "/tmp/claude_orchestrator"))
        self.workspace_base.mkdir(parents=True, exist_ok=True)

        # Initialize logging manager
        log_dir = config.get("log_dir", "/tmp/madrox_logs")
        log_level = config.get("log_level", "INFO")
        self.logging_manager = LoggingManager(log_dir=log_dir, log_level=log_level)
        logger.info(f"Logging manager initialized: {log_dir}")

        # Initialize shared state manager for IPC
        from .shared_state_manager import SharedStateManager

        self.shared_state_manager = SharedStateManager()
        logger.info("Shared state manager initialized for IPC")

        # Initialize Tmux instance manager for Claude and Codex instances
        self.tmux_manager = TmuxInstanceManager(
            config,
            logging_manager=self.logging_manager,
            shared_state_manager=self.shared_state_manager,
        )

        # Main instance tracking - will be populated after spawning real main instance
        self.main_instance_id: str | None = None
        self._main_spawn_lock = asyncio.Lock()

        # Main message inbox - accumulates messages for auto-injection
        self.main_message_inbox: list[dict[str, Any]] = []
        self._last_main_message_index = -1
        self._main_monitor_task: asyncio.Task | None = None

    @mcp.tool
    async def spawn_claude(
        self,
        name: str,
        role: str = "general",
        system_prompt: str | None = None,
        model: str | None = None,
        bypass_isolation: bool = True,
        parent_instance_id: str | None = None,
        wait_for_ready: bool = True,
        initial_prompt: str | None = None,
        mcp_servers: str | None = None,
    ) -> dict[str, Any]:
        """Spawn a new Claude instance with specific role and configuration.

        Args:
            name: Instance name
            role: Predefined role for the instance
            system_prompt: Custom system prompt (overrides role)
            model: Claude model to use. Options:
                   - claude-sonnet-4-5 (default, recommended, smartest model for daily use)
                   - claude-opus-4-1 (legacy, reaches usage limits faster)
                   - claude-haiku-4-5 (fastest model for simple tasks)
            bypass_isolation: Allow full filesystem access (default: true)
            parent_instance_id: Parent instance ID for tracking bidirectional communication
            wait_for_ready: Wait for instance to initialize (default: true)
            initial_prompt: Initial prompt to send as CLI argument (bypasses paste detection)
            mcp_servers: JSON string of MCP server configurations. Format:
                        '{"server_name": {"transport": "http", "url": "http://localhost:8002/mcp"}}'

        Returns:
            Dictionary with instance_id and status
        """
        # Validate model against allowed Claude models
        validated_model = validate_model("claude", model)

        instance_id = await self.spawn_instance(
            name=name,
            role=role,
            system_prompt=system_prompt,
            model=validated_model,
            bypass_isolation=bypass_isolation,
            parent_instance_id=parent_instance_id,
            wait_for_ready=wait_for_ready,
            initial_prompt=initial_prompt,
            mcp_servers=mcp_servers,
        )
        return {"instance_id": instance_id, "status": "spawned", "name": name}

    @mcp.tool
    async def spawn_multiple_instances(
        self,
        instances: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Spawn multiple Claude instances in parallel for better performance.

        Args:
            instances: List of instance configurations to spawn

        Returns:
            Dictionary with spawned instance IDs and any errors
        """
        results = {"spawned": [], "errors": []}
        for instance_config in instances:
            try:
                instance_id = await self.spawn_instance(**instance_config)
                results["spawned"].append({"instance_id": instance_id, **instance_config})
            except Exception as e:
                results["errors"].append({"config": instance_config, "error": str(e)})
        return results

    @mcp.tool
    async def send_to_instance(
        self,
        instance_id: str,
        message: str,
        wait_for_response: bool = False,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        """Send a message to a specific Claude instance (non-blocking by default).

        Args:
            instance_id: ID of the target instance
            message: Message to send
            wait_for_response: Set to true to wait for response
            timeout_seconds: Timeout in seconds (default 180)

        Returns:
            Dictionary with response or status
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        # Delegate to TmuxInstanceManager for Claude and Codex instances
        if instance.get("instance_type") in ["claude", "codex"]:
            result = await self.tmux_manager.send_message(
                instance_id=instance_id,
                message=message,
                wait_for_response=wait_for_response,
                timeout_seconds=timeout_seconds,
            )
            return result or {"status": "message_sent"}

        # No other instance types supported
        raise ValueError(f"Unsupported instance type: {instance.get('instance_type')}")

    @mcp.tool
    async def send_to_multiple_instances(
        self,
        instance_ids: list[str],
        message: str,
        wait_for_responses: bool = False,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        """Send the same message to multiple instances in parallel.

        Args:
            instance_ids: List of instance IDs to send to
            message: Message to send
            wait_for_responses: Wait for responses from all instances
            timeout_seconds: Timeout in seconds

        Returns:
            Dictionary with results for each instance
        """
        results = {"sent": [], "errors": []}
        tasks = []
        for instance_id in instance_ids:
            tasks.append(
                self.send_to_instance(
                    instance_id=instance_id,
                    message=message,
                    wait_for_response=wait_for_responses,
                    timeout_seconds=timeout_seconds,
                )
            )

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for i, instance_id in enumerate(instance_ids):
            response = responses[i]
            if isinstance(response, Exception):
                results["errors"].append({"instance_id": instance_id, "error": str(response)})
            else:
                results["sent"].append({"instance_id": instance_id, "response": response})

        return results

    @mcp.tool
    async def get_instance_output(
        self,
        instance_id: str,
        limit: int = 100,
        since: str | None = None,
    ) -> dict[str, Any]:
        """Get recent output from a Claude instance.

        Args:
            instance_id: ID of the instance
            limit: Maximum number of messages to retrieve
            since: ISO timestamp filter

        Returns:
            Dictionary with output messages
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        # All instances use tmux now - get history from tmux manager
        if instance_id not in self.tmux_manager.message_history:
            return {"instance_id": instance_id, "output": []}

        messages = self.tmux_manager.message_history[instance_id]

        # Convert messages to output format
        output_messages = []
        for i, msg in enumerate(messages):
            output_messages.append(
                {
                    "instance_id": instance_id,
                    "timestamp": instance["last_activity"],  # Would be better to track per-message
                    "type": "user" if msg["role"] == "user" else "response",
                    "content": msg["content"],
                    "message_index": i,
                }
            )

        # Apply since filter if provided
        if since:
            since_dt = datetime.fromisoformat(since)
            # Note: In a real implementation, we'd track timestamps per message
            # For now, we can only filter based on the last activity
            last_activity = datetime.fromisoformat(instance["last_activity"])
            if last_activity < since_dt:
                return {"instance_id": instance_id, "output": []}

        # Apply limit
        if len(output_messages) > limit:
            output_messages = output_messages[-limit:]

        return {"instance_id": instance_id, "output": output_messages}

    async def _get_output_messages(
        self, instance_id: str, limit: int = 100, since: str | None = None
    ) -> list[dict[str, Any]]:
        """Internal helper to get output messages for an instance.

        Args:
            instance_id: Instance ID
            limit: Maximum number of messages
            since: ISO timestamp filter

        Returns:
            List of output messages
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        # All instances use tmux now - get history from tmux manager
        if instance_id not in self.tmux_manager.message_history:
            return []

        messages = self.tmux_manager.message_history[instance_id]

        # Convert messages to output format
        output_messages = []
        for i, msg in enumerate(messages):
            output_messages.append(
                {
                    "instance_id": instance_id,
                    "timestamp": instance["last_activity"],
                    "type": "user" if msg["role"] == "user" else "response",
                    "content": msg["content"],
                    "message_index": i,
                }
            )

        # Apply since filter if provided
        if since:
            since_dt = datetime.fromisoformat(since)
            last_activity = datetime.fromisoformat(instance["last_activity"])
            if last_activity < since_dt:
                return []

        # Apply limit
        if len(output_messages) > limit:
            output_messages = output_messages[-limit:]

        return output_messages

    @mcp.tool
    async def get_multiple_instance_outputs(
        self,
        instance_ids: list[str],
        limit: int = 100,
        since: str | None = None,
    ) -> dict[str, Any]:
        """Get recent output from multiple instances.

        Args:
            instance_ids: List of instance IDs
            limit: Maximum number of messages per instance
            since: ISO timestamp filter

        Returns:
            Dictionary with outputs for each instance
        """
        results = {"outputs": [], "errors": []}
        for instance_id in instance_ids:
            try:
                output = await self._get_output_messages(instance_id, limit, since)
                results["outputs"].append({"instance_id": instance_id, "output": output})
            except Exception as e:
                results["errors"].append({"instance_id": instance_id, "error": str(e)})
        return results

    @mcp.tool
    async def terminate_multiple_instances(
        self,
        instance_ids: list[str],
        force: bool = False,
    ) -> dict[str, Any]:
        """Terminate multiple Claude instances in parallel.

        Args:
            instance_ids: List of instance IDs to terminate
            force: Force termination for all instances

        Returns:
            Dictionary with termination results
        """
        results = {"terminated": [], "failed": []}
        for iid in instance_ids:
            try:
                success = await self._terminate_instance_internal(iid, force=force)
                if success:
                    results["terminated"].append(iid)
                else:
                    results["failed"].append(iid)
            except Exception as e:
                results["failed"].append({"instance_id": iid, "error": str(e)})
        return results

    def _get_instance_status_internal(self, instance_id: str | None = None, summary_only: bool = False) -> dict[str, Any]:
        """Internal method to get status of instance(s).

        Args:
            instance_id: Specific instance ID, or None for all instances
            summary_only: If True and instance_id is None, return only basic summary without full instance data

        Returns:
            Instance status data
        """
        if instance_id:
            if instance_id not in self.instances:
                raise ValueError(f"Instance {instance_id} not found")
            return self.instances[instance_id].copy()
        else:
            # When returning all instances, optionally return just summary to avoid large payloads
            if summary_only:
                # Return minimal summary - just IDs, names, and states
                return {
                    "instances": {
                        iid: {
                            "id": inst["id"],
                            "name": inst["name"],
                            "state": inst["state"],
                            "role": inst["role"],
                        }
                        for iid, inst in self.instances.items()
                    },
                    "total_instances": len(self.instances),
                    "active_instances": len(
                        [
                            i
                            for i in self.instances.values()
                            if i["state"] in ["running", "idle", "busy"]
                        ]
                    ),
                }
            else:
                return {
                    "instances": {iid: inst.copy() for iid, inst in self.instances.items()},
                    "total_instances": len(self.instances),
                    "active_instances": len(
                        [
                            i
                            for i in self.instances.values()
                            if i["state"] in ["running", "idle", "busy"]
                        ]
                    ),
                    "total_tokens_used": self.total_tokens_used,
                    "total_cost": self.total_cost,
                }

    @mcp.tool
    def get_instance_status(
        self,
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        """Get status for a single instance or all instances.

        Args:
            instance_id: Optional instance ID (omit for all instances)

        Returns:
            Dictionary with instance status information
        """
        return self._get_instance_status_internal(instance_id=instance_id)

    @mcp.tool
    async def get_live_instance_status(
        self,
        instance_id: str,
    ) -> dict[str, Any]:
        """Get live status with execution time and last activity for an instance.

        Args:
            instance_id: Instance ID

        Returns:
            Dictionary with live status including execution_time, state, last_activity
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        # Calculate execution time
        created_at = datetime.fromisoformat(instance["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        current_time = datetime.now(UTC)
        execution_time = (current_time - created_at).total_seconds()

        return {
            "instance_id": instance_id,
            "execution_time": execution_time,
            "state": instance["state"],
            "last_activity": instance["last_activity"],
            "name": instance.get("name"),
            "role": instance.get("role"),
        }

    @mcp.tool
    async def reply_to_caller(
        self,
        instance_id: str,
        reply_message: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Reply back to the instance/coordinator that sent you a message.

        Args:
            instance_id: Your instance ID (the responder)
            reply_message: Your reply content
            correlation_id: Message ID from the incoming message (optional)

        Returns:
            Dictionary with reply status
        """
        return await self.handle_reply_to_caller(
            instance_id=instance_id,
            reply_message=reply_message,
            correlation_id=correlation_id,
        )

    async def _get_pending_replies_internal(
        self,
        instance_id: str,
        wait_timeout: int = 0,
    ) -> list[dict[str, Any]]:
        """Internal method to check for pending replies.

        Args:
            instance_id: Instance ID to check inbox for
            wait_timeout: Seconds to wait for at least one reply (0 = non-blocking)

        Returns:
            List of pending reply messages
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        # Get the response queue for this instance
        if instance_id not in self.tmux_manager.response_queues:
            return []

        queue = self.tmux_manager.response_queues[instance_id]
        replies = []

        # If wait_timeout > 0, wait for at least one message
        if wait_timeout > 0:
            try:
                first_reply = await asyncio.wait_for(queue.get(), timeout=wait_timeout)
                replies.append(first_reply)
            except TimeoutError:
                return []

        # Drain remaining queued messages (non-blocking)
        while not queue.empty():
            try:
                reply = queue.get_nowait()
                replies.append(reply)
            except asyncio.QueueEmpty:
                break

        return replies

    @mcp.tool
    async def get_pending_replies(
        self,
        instance_id: str,
        wait_timeout: int = 0,
    ) -> list[dict[str, Any]]:
        """Check for pending replies from children or other instances.

        When children use reply_to_caller, their replies are queued in the parent's
        response queue. This tool allows the parent to poll for these queued replies.

        Args:
            instance_id: Your instance ID (to check your inbox)
            wait_timeout: Seconds to wait for at least one reply (0 = non-blocking)

        Returns:
            List of pending reply messages from children
        """
        return await self._get_pending_replies_internal(instance_id, wait_timeout)

    async def spawn_instance(
        self,
        name: str | None = None,
        role: str = "general",
        system_prompt: str | None = None,
        model: str | None = None,
        bypass_isolation: bool = False,
        instance_type: str = "claude",
        **kwargs,
    ) -> str:
        """Spawn a new Claude instance.

        Args:
            name: Human-readable name for the instance
            role: Predefined role (general, frontend_developer, etc.)
            system_prompt: Custom system prompt
            model: Claude model to use (None = use CLI default)
            bypass_isolation: Allow full filesystem access
            instance_type: Type of instance (always "claude", handled by tmux)
            **kwargs: Additional configuration options (including parent_instance_id)

        Returns:
            Instance ID
        """
        # MANDATORY: Enforce parent_instance_id requirement
        is_main_instance = name == "main-orchestrator"
        is_team_supervisor = name.endswith("-lead")  # Team supervisors can be root-level
        parent_id = kwargs.get("parent_instance_id")

        if parent_id is None and not is_main_instance and not is_team_supervisor:
            raise ValueError(
                f"Cannot spawn instance '{name}': parent_instance_id is required but could not be determined. "
                f"This instance is not the main orchestrator and no parent was detected. "
                f"\n"
                f"Possible causes:\n"
                f"  1. Spawning from external client without explicit parent_instance_id\n"
                f"  2. Caller instance detection failed (instance not in 'busy' state)\n"
                f"  3. Spawning before any managed instances exist\n"
                f"\n"
                f"Solutions:\n"
                f"  1. Provide parent_instance_id explicitly: spawn_claude(..., parent_instance_id='abc123')\n"
                f"  2. Spawn from within a managed instance (auto-detection will work)\n"
                f"  3. First spawn the main orchestrator, then use it as parent\n"
            )

        # Validate that parent_instance_id exists (if provided)
        if parent_id and parent_id not in self.instances:
            raise ValueError(
                f"Cannot spawn instance '{name}': parent_instance_id '{parent_id}' does not exist. "
                f"The specified parent instance was not found in the managed instances. "
                f"\n"
                f"Possible causes:\n"
                f"  1. Parent instance ID is incorrect or misspelled\n"
                f"  2. Parent instance has already been terminated\n"
                f"  3. Using a placeholder value like 'supervisor' instead of actual instance ID\n"
                f"\n"
                f"Solutions:\n"
                f"  1. Verify the parent instance ID is correct\n"
                f"  2. Use your actual instance_id (provided in your system prompt)\n"
                f"  3. Let auto-detection work by not providing parent_instance_id\n"
            )

        # Log final parent assignment
        if parent_id:
            logger.info(f"Instance '{name}' will have parent: {parent_id}")
        elif is_main_instance:
            logger.info(f"Instance '{name}' is main orchestrator (no parent)")
        elif is_team_supervisor:
            logger.info(f"Instance '{name}' is team supervisor (root-level, no parent)")
        else:
            # Should never reach here due to exception above
            raise RuntimeError(f"Invalid state: instance '{name}' has no parent but is not main orchestrator or team supervisor")

        # All Claude instances are handled by TmuxInstanceManager
        instance_id = await self.tmux_manager.spawn_instance(
            name=name,
            role=role,
            system_prompt=system_prompt,
            model=model,
            bypass_isolation=bypass_isolation,
            instance_type=instance_type,
            **kwargs,
        )
        # Copy instance to main instances dict for unified tracking
        self.instances[instance_id] = self.tmux_manager.instances[instance_id]
        return instance_id

    @mcp.tool
    async def spawn_codex(
        self,
        name: str,
        model: str | None = None,
        sandbox_mode: str = "workspace-write",
        profile: str | None = None,
        initial_prompt: str | None = None,
        bypass_isolation: bool = False,
        parent_instance_id: str | None = None,
        mcp_servers: str | None = None,
    ) -> dict[str, Any]:
        """Spawn a new Codex CLI instance (OpenAI GPT models only).

        Args:
            name: Instance name
            model: OpenAI GPT model to use. Options:
                   - gpt-5-codex (default and only allowed model)
            sandbox_mode: Sandbox policy for shell commands (read-only, workspace-write, danger-full-access)
            profile: Configuration profile from config.toml
            initial_prompt: Initial prompt to start the session
            bypass_isolation: Allow full filesystem access
            parent_instance_id: Parent instance ID for tracking
            mcp_servers: JSON string of MCP server configurations. Format:
                        '{"server_name": {"transport": "http", "url": "http://localhost:8002/mcp"}}'

        Returns:
            Dictionary with instance_id and status
        """
        # Validate model against allowed Codex models
        validated_model = validate_model("codex", model)

        # Delegate to TmuxInstanceManager for Codex instances
        instance_id = await self.tmux_manager.spawn_instance(
            name=name,
            model=validated_model,
            bypass_isolation=bypass_isolation,
            sandbox_mode=sandbox_mode,
            profile=profile,
            initial_prompt=initial_prompt,
            instance_type="codex",
            parent_instance_id=parent_instance_id,
            mcp_servers=mcp_servers,
        )
        # Copy instance to main instances dict for unified tracking
        self.instances[instance_id] = self.tmux_manager.instances[instance_id]
        self.instances[instance_id]["instance_type"] = "codex"
        return {
            "instance_id": instance_id,
            "status": "spawned",
            "name": name,
            "instance_type": "codex",
        }

    @mcp.tool
    async def spawn_team_from_template(
        self,
        template_name: str,
        task_description: str,
        supervisor_role: str | None = None,
        parent_instance_id: str | None = None,
    ) -> str:
        """Spawn a complete team from a predefined template.

        Available templates:
        - software_engineering_team: Build SaaS apps, APIs, microservices (6 instances, 2-4 hrs)
        - research_analysis_team: Market research, competitive intelligence (5 instances, 2-3 hrs)
        - security_audit_team: Security reviews, compliance assessments (7 instances, 2-4 hrs)
        - data_pipeline_team: ETL pipelines, data lake ingestion (5 instances, 2-4 hrs)

        Args:
            template_name: Name of the template to use
            task_description: Description of the task for the team
            supervisor_role: Optional supervisor role (defaults to template's recommended role)
            parent_instance_id: Optional parent instance ID for supervisor (for auto-detection if not provided)

        Returns:
            Formatted result text with supervisor ID and network topology
        """
        from pathlib import Path

        # Load template file
        project_root = Path(__file__).parent.parent.parent
        template_path = project_root / "templates" / f"{template_name}.md"

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

        # Build instruction message FIRST (before spawning)
        instruction = self._build_template_instruction(
            template_content=template_content, task_description=task_description
        )

        # Spawn supervisor WITH instruction as initial_prompt (bypasses paste detection)
        supervisor_id = await self.spawn_instance(
            name=f"{template_name}-lead",
            role=role,
            wait_for_ready=True,
            initial_prompt=instruction,
            parent_instance_id=parent_instance_id,
        )

        # No need to send_message - instruction already received via CLI argument
        logger.info(
            f"Spawned supervisor {supervisor_id} with initial instruction "
            f"({len(instruction)} chars, {len(instruction)/1024:.2f}KB)"
        )

        # Wait briefly for network assembly
        await asyncio.sleep(10)

        # Get network tree preview
        tree_preview = "Initializing network..."
        try:
            roots = []
            for instance_id, instance in self.instances.items():
                if not instance.get("parent_instance_id") and instance.get("state") != "terminated":
                    roots.append((instance_id, instance.get("name", "unknown")))

            if roots:
                roots.sort(key=lambda x: x[1])
                lines = []
                for i, (root_id, _) in enumerate(roots):
                    is_last_root = i == len(roots) - 1
                    self._build_tree_recursive(root_id, "", is_last_root, lines, is_root=True)
                tree_preview = "\n".join(lines)
        except Exception as e:
            logger.warning(f"Failed to build tree preview: {e}")

        # Build result
        result_text = f"""✅ Team spawned from template: {template_name}

📋 **Template Details:**
- Supervisor ID: {supervisor_id}
- Team Size: {template_meta["team_size"]} instances
- Estimated Duration: {template_meta["duration"]}
- Estimated Cost: {template_meta["estimated_cost"]}
- Status: Initializing

🌳 **Network Topology:**
{tree_preview}

📝 **Task:**
{task_description[:200]}{"..." if len(task_description) > 200 else ""}

⏳ The supervisor is now spawning the team and executing the workflow.
Use get_pending_replies({supervisor_id}) to monitor progress.
Use get_instance_tree() to see the full network hierarchy."""

        return result_text

    def _parse_template_metadata(self, template_content: str) -> dict[str, Any]:
        """Extract metadata from template markdown."""
        lines = template_content.split("\n")

        # Parse Team Size from "Team Size: X instances"
        team_size = 6  # default
        for line in lines:
            if "Team Size" in line and "instances" in line:
                try:
                    parts = line.split("instances")[0].split()
                    team_size = int(parts[-1])
                except (ValueError, IndexError):
                    pass

        # Parse Duration from "Estimated Duration: X hours"
        duration = "2-4 hours"
        for line in lines:
            if "Estimated Duration" in line or "Duration:" in line:
                if ":" in line:
                    duration = line.split(":", 1)[-1].strip()

        # Parse Supervisor Role from markdown
        supervisor_role = "general"
        in_supervisor_section = False
        for line in lines:
            if any(
                header in line
                for header in [
                    "### Technical Lead",
                    "### Research Lead",
                    "### Security Lead",
                    "### Data Engineering Lead",
                ]
            ):
                in_supervisor_section = True
            elif line.startswith("###"):
                in_supervisor_section = False

            if in_supervisor_section and "**Role**:" in line:
                if "`" in line:
                    supervisor_role = line.split("`")[1]
                    break

        return {
            "team_size": team_size,
            "duration": duration,
            "estimated_cost": f"${team_size * 5}",
            "supervisor_role": supervisor_role,
        }

    def _extract_section(self, content: str, header: str) -> str:
        """Extract markdown section by header."""
        lines = content.split("\n")
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

        return "\n".join(section_lines).strip()

    def _build_template_instruction(self, template_content: str, task_description: str) -> str:
        """Build instruction message for supervisor from template."""
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

    async def handle_reply_to_caller(
        self,
        instance_id: str,
        reply_message: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Handle reply from instance back to its caller.

        This implements the bidirectional messaging protocol by delegating
        to TmuxInstanceManager which manages the response queues.

        Args:
            instance_id: ID of instance sending the reply
            reply_message: Content of the reply
            correlation_id: Optional message ID for correlation

        Returns:
            Dict with success status and delivery info
        """
        # CRITICAL FIX: When using shared_state (STDIO transport), STDIO subprocesses
        # don't have instances in their local dict - only response queues are shared.
        # Skip instance validation and let TmuxInstanceManager handle the reply.
        if not self.shared_state_manager and instance_id not in self.instances:
            return {"success": False, "error": f"Instance {instance_id} not found"}

        # Delegate to TmuxInstanceManager for queue management
        return await self.tmux_manager.handle_reply_to_caller(
            instance_id=instance_id,
            reply_message=reply_message,
            correlation_id=correlation_id,
        )

    @mcp.tool
    async def get_job_status(
        self, job_id: str, wait_for_completion: bool = True, max_wait: int = 120
    ) -> dict[str, Any] | None:
        """Get the status of a job.

        Args:
            job_id: Job ID to check
            wait_for_completion: If True, wait for job to complete
            max_wait: Maximum seconds to wait for completion

        Returns:
            Job status dict or None if not found
        """
        if job_id not in self.jobs:
            return None

        # If not waiting or job already complete, return immediately
        job = self.jobs[job_id]
        if not wait_for_completion or job["status"] in ["completed", "failed", "timeout"]:
            return job

        # Wait for completion
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < max_wait:
            job = self.jobs[job_id]
            if job["status"] in ["completed", "failed", "timeout"]:
                return job
            await asyncio.sleep(1)

        # Return current status after max wait
        return self.jobs[job_id]

    def _get_children_internal(self, parent_id: str) -> list[dict[str, Any]]:
        """Internal method to get all child instances of a parent.

        Args:
            parent_id: Parent instance ID

        Returns:
            List of child instance details (excludes terminated instances)
        """
        children = []
        for instance_id, instance in self.instances.items():
            if (
                instance.get("parent_instance_id") == parent_id
                and instance.get("state") != "terminated"
            ):
                children.append(
                    {
                        "id": instance_id,
                        "name": instance.get("name"),
                        "role": instance.get("role"),
                        "state": instance.get("state"),
                        "instance_type": instance.get("instance_type"),
                    }
                )
        return children

    @mcp.tool
    def get_children(self, parent_id: str) -> list[dict[str, Any]]:
        """Get all child instances of a parent.

        Args:
            parent_id: Parent instance ID

        Returns:
            List of child instance details (excludes terminated instances)
        """
        return self._get_children_internal(parent_id)

    @mcp.tool
    async def broadcast_to_children(
        self, parent_id: str, message: str, wait_for_responses: bool = False
    ) -> dict[str, Any]:
        """Broadcast a message to all children of a parent.

        Args:
            parent_id: Parent instance ID
            message: Message to broadcast
            wait_for_responses: Wait for responses from all children

        Returns:
            Dictionary with results for each child
        """
        children = self._get_children_internal(parent_id)

        if not children:
            return {"children_count": 0, "results": []}

        # Send to all children in parallel
        tasks = []
        for child in children:
            tasks.append(
                self.send_to_instance(
                    instance_id=child["id"],
                    message=message,
                    wait_for_response=wait_for_responses,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Format results
        formatted_results = []
        for i, child in enumerate(children):
            result = results[i]
            if isinstance(result, Exception):
                formatted_results.append(
                    {
                        "child_id": child["id"],
                        "child_name": child["name"],
                        "status": "error",
                        "error": str(result),
                    }
                )
            else:
                formatted_results.append(
                    {
                        "child_id": child["id"],
                        "child_name": child["name"],
                        "status": "sent" if not wait_for_responses else "completed",
                        "response": result if wait_for_responses else None,
                    }
                )

        return {
            "children_count": len(children),
            "results": formatted_results,
        }

    @mcp.tool
    def get_instance_tree(self) -> str:
        """Build a hierarchical tree view of all instances.

        Returns:
            Formatted tree string showing instance hierarchy
        """
        # Find root instances (no parent) that are not terminated
        roots = []
        for instance_id, instance in self.instances.items():
            if not instance.get("parent_instance_id") and instance.get("state") != "terminated":
                roots.append((instance_id, instance.get("name", "unknown")))

        if not roots:
            return "No instances running"

        # Sort by name for consistent output
        roots.sort(key=lambda x: x[1])

        # Build tree for each root
        lines = []
        for i, (root_id, _) in enumerate(roots):
            is_last_root = i == len(roots) - 1
            self._build_tree_recursive(root_id, "", is_last_root, lines, is_root=True)

        return "\n".join(lines)

    def _build_tree_recursive(
        self, instance_id: str, prefix: str, is_last: bool, lines: list[str], is_root: bool = False
    ) -> None:
        """Recursively build tree structure."""
        instance = self.instances.get(instance_id)
        if not instance:
            return

        # Build the current line
        if is_root:
            connector = ""
        else:
            connector = "└── " if is_last else "├── "

        name = instance.get("name", "unknown")
        short_id = instance_id[:8] + "..."
        state = instance.get("state", "unknown")
        instance_type = instance.get("instance_type", "claude")

        line = f"{prefix}{connector}{name} ({short_id}) [{state}] ({instance_type})"
        lines.append(line)

        # Get children and recurse
        children = self._get_children_internal(instance_id)
        child_count = len(children)

        # Sort children by name
        children.sort(key=lambda x: x["name"])

        for i, child in enumerate(children):
            is_last_child = i == child_count - 1
            if is_root:
                new_prefix = ""
            else:
                new_prefix = prefix + ("    " if is_last else "│   ")
            self._build_tree_recursive(child["id"], new_prefix, is_last_child, lines)

    @mcp.tool
    async def coordinate_instances(
        self,
        coordinator_id: str,
        participant_ids: list[str],
        task_description: str,
        coordination_type: str = "sequential",
    ) -> dict[str, Any]:
        """Coordinate multiple instances for a complex task.

        Args:
            coordinator_id: Coordinating instance ID
            participant_ids: Participant instance IDs
            task_description: Description of the task
            coordination_type: How to coordinate (sequential, parallel, consensus)

        Returns:
            Dictionary with coordination results
        """
        task_id = str(uuid.uuid4())

        # Validate all instances exist and are available
        all_ids = [coordinator_id] + participant_ids
        for iid in all_ids:
            if iid not in self.instances:
                raise ValueError(f"Instance {iid} not found")
            if self.instances[iid]["state"] not in ["running", "idle"]:
                raise RuntimeError(f"Instance {iid} is not available")

        # Create coordination task
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

        logger.info(f"Started coordination task {task_id} with {len(participant_ids)} participants")

        # Start coordination process in background
        asyncio.create_task(self._execute_coordination(coordination_task))

        return {"task_id": task_id, "status": "started"}

    async def _interrupt_instance_internal(self, instance_id: str) -> dict[str, Any]:
        """Internal method to interrupt an instance.

        Args:
            instance_id: Instance ID to interrupt

        Returns:
            Status dict with success/failure info
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        # Delegate to TmuxInstanceManager for all instances
        if instance.get("instance_type") in ["claude", "codex"]:
            result = await self.tmux_manager.interrupt_instance(instance_id)
            # Update main instances dict
            self.instances[instance_id] = self.tmux_manager.instances[instance_id]
            return result

        # No other instance types supported
        raise ValueError(f"Unsupported instance type: {instance.get('instance_type')}")

    @mcp.tool
    async def interrupt_instance(self, instance_id: str) -> dict[str, Any]:
        """Send interrupt signal (Ctrl+C) to a running instance.

        Args:
            instance_id: Instance ID to interrupt

        Returns:
            Status dict with success/failure info
        """
        return await self._interrupt_instance_internal(instance_id)

    @mcp.tool
    async def interrupt_multiple_instances(
        self,
        instance_ids: list[str],
    ) -> dict[str, Any]:
        """Send interrupt signal (Ctrl+C) to multiple running instances.

        Args:
            instance_ids: List of instance IDs to interrupt

        Returns:
            Dictionary with interrupt results for each instance
        """
        results = {"interrupted": [], "failed": []}
        for instance_id in instance_ids:
            try:
                result = await self._interrupt_instance_internal(instance_id)
                if result.get("success"):
                    results["interrupted"].append(instance_id)
                else:
                    results["failed"].append(
                        {"instance_id": instance_id, "error": "Failed to interrupt"}
                    )
            except Exception as e:
                results["failed"].append({"instance_id": instance_id, "error": str(e)})
        return results

    async def _terminate_instance_internal(self, instance_id: str, force: bool = False) -> bool:
        """Internal method to terminate a Claude or Codex instance.

        Args:
            instance_id: Instance ID to terminate
            force: Force termination even if busy

        Returns:
            True if terminated successfully
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        # Delegate to TmuxInstanceManager for all instances
        if instance.get("instance_type") in ["claude", "codex"]:
            result = await self.tmux_manager.terminate_instance(instance_id, force)
            if result:
                # Update main instances dict
                self.instances[instance_id] = self.tmux_manager.instances[instance_id]
            return result

        # No other instance types supported
        raise ValueError(f"Unsupported instance type: {instance.get('instance_type')}")

    @mcp.tool
    async def terminate_instance(
        self,
        instance_id: str,
        force: bool = False,
    ) -> dict[str, Any]:
        """Terminate a Claude instance.

        Args:
            instance_id: ID of the instance to terminate
            force: Force termination even if busy

        Returns:
            Dictionary with termination status
        """
        success = await self._terminate_instance_internal(
            instance_id=instance_id,
            force=force,
        )
        return {
            "instance_id": instance_id,
            "status": "terminated" if success else "failed",
            "success": success,
        }

    def _get_role_prompt(self, role: str) -> str:
        """Get system prompt for a role by loading from resources/prompts directory.

        Args:
            role: The role name (e.g., "general", "frontend_developer")

        Returns:
            The system prompt text for the role
        """
        from pathlib import Path

        # Get the project root directory (parent of src/orchestrator)
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent
        prompts_dir = project_root / "resources" / "prompts"

        # Try to load from file
        prompt_file = prompts_dir / f"{role}.txt"

        try:
            if prompt_file.exists():
                return prompt_file.read_text(encoding="utf-8").strip()
            else:
                logger.warning(
                    f"Prompt file not found for role '{role}', using fallback",
                    extra={"role": role, "expected_path": str(prompt_file)},
                )
                # Fallback to basic prompts if file doesn't exist
                fallback_prompts = {
                    "general": "You are a helpful AI assistant capable of handling various tasks.",
                    "frontend_developer": "You are a senior frontend developer specializing in React, TypeScript, and modern web technologies.",
                    "backend_developer": "You are a senior backend developer specializing in Python, APIs, and distributed systems.",
                    "testing_specialist": "You are a testing specialist focused on writing comprehensive tests and ensuring code quality.",
                    "documentation_writer": "You are a technical writer who creates clear, comprehensive documentation.",
                    "code_reviewer": "You are a senior code reviewer who provides constructive feedback and ensures best practices.",
                    "architect": "You are a software architect who designs scalable systems and makes architectural decisions.",
                    "debugger": "You are a debugging specialist who identifies and fixes complex issues in code.",
                    "security_analyst": "You are a security specialist who identifies vulnerabilities and ensures secure coding practices.",
                    "data_analyst": "You are a data analyst who works with data processing, analysis, and visualization.",
                }
                return fallback_prompts.get(role, fallback_prompts["general"])
        except Exception as e:
            logger.error(
                f"Error loading prompt file for role '{role}': {e}",
                extra={"role": role, "error": str(e)},
            )
            # Return minimal fallback on error
            return f"You are a helpful AI assistant with expertise in {role.replace('_', ' ')}."

    async def _execute_coordination(self, coordination_task: dict[str, Any]):
        """Execute a coordination task."""
        task_id = coordination_task["task_id"]
        participant_ids = coordination_task["participant_ids"]

        try:
            logger.info(f"Executing coordination task {task_id}")

            # Mock coordination logic
            if coordination_task["coordination_type"] == "sequential":
                for i, participant_id in enumerate(participant_ids):
                    step_result = await self.send_to_instance(
                        participant_id,
                        f"Please work on step {i + 1} of the coordination task: {coordination_task['description']}",
                    )
                    coordination_task["results"][participant_id] = step_result

            coordination_task["status"] = "completed"
            coordination_task["completed_at"] = datetime.now(UTC).isoformat()

            logger.info(f"Completed coordination task {task_id}")

        except Exception as e:
            logger.error(f"Error in coordination task {task_id}: {e}")
            coordination_task["status"] = "failed"
            coordination_task["error"] = str(e)

    async def ensure_main_instance(self) -> str:
        """Ensure main instance is spawned and return its ID.

        This method is idempotent - it will spawn the main instance only once
        on first call, and subsequent calls return the existing instance ID.

        Returns:
            The main instance ID
        """
        async with self._main_spawn_lock:
            if self.main_instance_id is not None:
                return self.main_instance_id

            logger.info("Auto-spawning main orchestrator instance in tmux")

            # Spawn the main instance as a real tmux-based madrox instance
            main_id = await self.spawn_instance(
                name="main-orchestrator",
                role="general",
                system_prompt=(
                    "You are the main orchestrator instance. "
                    "Child instances can communicate with you using your instance_id. "
                    "You can coordinate work across multiple specialized instances."
                ),
                bypass_isolation=False,
                wait_for_ready=True,
            )

            self.main_instance_id = main_id
            logger.info(f"Main instance spawned successfully: {main_id}")

            # Start background monitor for main instance messages
            self._start_main_monitor()

            # Give the monitor task a chance to start
            await asyncio.sleep(0.1)

            return main_id

    def _start_main_monitor(self):
        """Start background task to monitor main instance output."""
        if self._main_monitor_task is None or self._main_monitor_task.done():
            self._main_monitor_task = asyncio.create_task(self._monitor_main_messages())
            logger.info("Started main instance message monitor")

    async def _monitor_main_messages(self):
        """Background task that polls main instance for new messages."""
        if self.main_instance_id is None:
            return

        logger.info(f"Main monitor started for instance {self.main_instance_id}")

        while True:
            try:
                # Check if main instance still exists
                if self.main_instance_id not in self.instances:
                    logger.info("Main instance terminated, stopping monitor")
                    break

                # Get recent messages from main instance
                try:
                    messages = await self._get_output_messages(self.main_instance_id, limit=100)

                    # Process new messages
                    for msg in messages:
                        msg_index = msg.get("message_index", -1)
                        if msg_index > self._last_main_message_index and msg.get("type") == "user":
                            self.main_message_inbox.append(msg)
                            self._last_main_message_index = msg_index
                            logger.debug(
                                f"Added message to main inbox: {msg.get('content', '')[:100]}"
                            )
                except Exception as e:
                    logger.error(f"Monitor error getting messages: {e}")

                # Poll every 2 seconds
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error in main monitor: {e}")
                await asyncio.sleep(5)

    @mcp.tool
    def get_main_instance_id(self) -> str | None:
        """Get the main instance ID for child instances to communicate with.

        Returns:
            Main instance ID if spawned, None otherwise
        """
        return self.main_instance_id

    def get_and_clear_main_inbox(self) -> list[dict[str, Any]]:
        """Get all pending main messages and clear the inbox.

        Returns:
            List of pending messages sent to main instance
        """
        messages = self.main_message_inbox.copy()
        self.main_message_inbox.clear()
        return messages

    async def health_check(self):
        """Perform health check on all instances."""
        logger.info("Performing health check on all instances")

        current_time = datetime.now(UTC)
        timeout_minutes = self.config.get("instance_timeout_minutes", 60)

        for instance_id, instance in list(self.instances.items()):
            if instance["state"] == "terminated":
                continue

            # Check for timeout
            last_activity = datetime.fromisoformat(instance["last_activity"])
            # Ensure last_activity is timezone-aware (it should already have timezone from UTC)
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=UTC)
            if current_time - last_activity > timedelta(minutes=timeout_minutes):
                logger.warning(f"Instance {instance_id} timed out, terminating")
                await self._terminate_instance_internal(instance_id, force=True)
                continue

            # Check resource limits
            max_tokens = instance.get("resource_limits", {}).get("max_total_tokens")
            if max_tokens and instance["total_tokens_used"] > max_tokens:
                logger.warning(f"Instance {instance_id} exceeded token limit, terminating")
                await self._terminate_instance_internal(instance_id, force=True)
                continue

            max_cost = instance.get("resource_limits", {}).get("max_cost")
            if max_cost and instance["total_cost"] > max_cost:
                logger.warning(f"Instance {instance_id} exceeded cost limit, terminating")
                await self._terminate_instance_internal(instance_id, force=True)
                continue

        logger.info(
            f"Health check complete. Active instances: {len([i for i in self.instances.values() if i['state'] not in ['terminated', 'error']])}"
        )

    async def _retrieve_instance_file_internal(
        self, instance_id: str, filename: str, destination_path: str | None = None
    ) -> str | None:
        """Internal method to retrieve a file from an instance's workspace directory.

        Args:
            instance_id: The instance ID
            filename: Name of the file to retrieve
            destination_path: Optional destination path (defaults to current directory)

        Returns:
            Path to the retrieved file, or None if not found
        """
        if instance_id not in self.instances:
            logger.error(f"Instance {instance_id} not found")
            return None

        instance = self.instances[instance_id]
        workspace_dir = Path(instance["workspace_dir"])
        source_file = workspace_dir / filename

        if not source_file.exists():
            logger.warning(f"File {filename} not found in instance {instance_id} workspace")
            return None

        # Determine destination
        if destination_path:
            dest = Path(destination_path)
            if dest.is_dir():
                dest = dest / filename
        else:
            dest = Path.cwd() / filename

        try:
            import shutil

            shutil.copy2(source_file, dest)
            logger.info(f"Retrieved file {filename} from instance {instance_id} to {dest}")
            return str(dest)
        except Exception as e:
            logger.error(f"Failed to retrieve file: {e}")
            return None

    @mcp.tool
    async def retrieve_instance_file(
        self, instance_id: str, filename: str, destination_path: str | None = None
    ) -> str | None:
        """Retrieve a file from an instance's workspace directory.

        Args:
            instance_id: The instance ID
            filename: Name of the file to retrieve
            destination_path: Optional destination path (defaults to current directory)

        Returns:
            Path to the retrieved file, or None if not found
        """
        return await self._retrieve_instance_file_internal(instance_id, filename, destination_path)

    @mcp.tool
    async def retrieve_multiple_instance_files(
        self,
        retrievals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Retrieve files from multiple instances.

        Args:
            retrievals: List of dicts with instance_id, filename, destination_path

        Returns:
            Dictionary with retrieved file paths and errors
        """
        results = {"retrieved": [], "errors": []}
        for retrieval in retrievals:
            try:
                instance_id = retrieval["instance_id"]
                filename = retrieval["filename"]
                destination_path = retrieval.get("destination_path")

                path = await self._retrieve_instance_file_internal(
                    instance_id, filename, destination_path
                )
                if path:
                    results["retrieved"].append(
                        {
                            "instance_id": instance_id,
                            "filename": filename,
                            "path": path,
                        }
                    )
                else:
                    results["errors"].append(
                        {
                            "instance_id": instance_id,
                            "filename": filename,
                            "error": "File not found",
                        }
                    )
            except Exception as e:
                results["errors"].append(
                    {
                        "instance_id": retrieval.get("instance_id"),
                        "filename": retrieval.get("filename"),
                        "error": str(e),
                    }
                )
        return results

    async def _list_instance_files_internal(self, instance_id: str) -> list[str] | None:
        """Internal method to list all files in an instance's workspace directory.

        Args:
            instance_id: The instance ID

        Returns:
            List of file paths relative to workspace, or None if instance not found
        """
        if instance_id not in self.instances:
            logger.error(f"Instance {instance_id} not found")
            return None

        instance = self.instances[instance_id]
        workspace_dir = Path(instance["workspace_dir"])

        if not workspace_dir.exists():
            logger.warning(f"Workspace directory for instance {instance_id} does not exist")
            return []

        try:
            files = []
            for item in workspace_dir.rglob("*"):
                if item.is_file():
                    relative_path = item.relative_to(workspace_dir)
                    files.append(str(relative_path))

            logger.debug(f"Found {len(files)} files in instance {instance_id} workspace")
            return sorted(files)
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    @mcp.tool
    async def list_instance_files(self, instance_id: str) -> list[str] | None:
        """List all files in an instance's workspace directory.

        Args:
            instance_id: The instance ID

        Returns:
            List of file paths relative to workspace, or None if instance not found
        """
        return await self._list_instance_files_internal(instance_id)

    @mcp.tool
    async def list_multiple_instance_files(
        self,
        instance_ids: list[str],
    ) -> dict[str, Any]:
        """List files for multiple instances.

        Args:
            instance_ids: List of instance IDs

        Returns:
            Dictionary with file listings and errors for each instance
        """
        results = {"listings": [], "errors": []}
        for instance_id in instance_ids:
            try:
                files = await self._list_instance_files_internal(instance_id)
                if files is not None:
                    results["listings"].append(
                        {
                            "instance_id": instance_id,
                            "files": files,
                            "file_count": len(files),
                        }
                    )
                else:
                    results["errors"].append(
                        {
                            "instance_id": instance_id,
                            "error": "Instance not found",
                        }
                    )
            except Exception as e:
                results["errors"].append(
                    {
                        "instance_id": instance_id,
                        "error": str(e),
                    }
                )
        return results

    async def get_instance_logs(
        self, instance_id: str, log_type: str = "instance", tail: int = 100
    ) -> list[str]:
        """Retrieve logs for a specific instance.

        Args:
            instance_id: Instance ID
            log_type: Type of log (instance, communication, tmux_output)
            tail: Number of recent lines to return (0 for all)

        Returns:
            List of log lines
        """
        if not self.logging_manager:
            logger.warning("Logging manager not initialized")
            return []

        return self.logging_manager.get_instance_logs(instance_id, log_type, tail)

    @mcp.tool
    async def get_tmux_pane_content(self, instance_id: str, lines: int = 100) -> str:
        """Capture the current tmux pane content for an instance.

        Args:
            instance_id: Instance ID
            lines: Number of lines to capture (default: 100, -1 for all visible)

        Returns:
            Captured pane content as string
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        try:
            session = self.tmux_manager.tmux_sessions.get(instance_id)
            if not session:
                raise RuntimeError(f"No tmux session found for instance {instance_id}")

            window = session.windows[0]
            pane = window.panes[0]

            # Capture pane content with specified number of lines
            if lines == -1:
                # Capture all visible content
                output = "\n".join(pane.cmd("capture-pane", "-p").stdout)
            else:
                # Capture specified number of lines from the end
                output = "\n".join(pane.cmd("capture-pane", "-p", "-S", f"-{lines}").stdout)

            return output
        except Exception as e:
            logger.error(f"Failed to capture tmux pane for instance {instance_id}: {e}")
            raise

    async def get_audit_logs(
        self, since: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Retrieve audit trail logs.

        Args:
            since: ISO timestamp to get logs since (optional)
            limit: Maximum number of log entries to return

        Returns:
            List of audit log entries as dicts
        """
        if not self.logging_manager:
            logger.warning("Logging manager not initialized")
            return []

        import json
        from datetime import datetime

        audit_dir = self.logging_manager.audit_dir
        audit_logs = []

        # Read audit files (newest first)
        audit_files = sorted(audit_dir.glob("audit_*.jsonl"), reverse=True)

        since_dt = datetime.fromisoformat(since) if since else None

        for audit_file in audit_files:
            try:
                # Read all lines from the file in order (oldest first in file)
                with audit_file.open("r") as f:
                    for line in f:
                        if not line.strip():
                            continue

                        try:
                            log_entry = json.loads(line)

                            # Filter by timestamp if specified (exclude logs at or before since timestamp)
                            if since_dt:
                                log_timestamp = datetime.fromisoformat(log_entry["timestamp"])
                                if log_timestamp <= since_dt:
                                    continue

                            audit_logs.append(log_entry)

                            if len(audit_logs) >= limit:
                                break
                        except json.JSONDecodeError:
                            continue

                if len(audit_logs) >= limit:
                    break
            except Exception as e:
                logger.error(f"Failed to read audit file {audit_file}: {e}")
                continue

        # Return in chronological order (oldest first)
        # Frontend will reverse when displaying
        return audit_logs[-limit:] if audit_logs else []

    async def list_logged_instances(self) -> list[dict[str, Any]]:
        """List all instances that have logs.

        Returns:
            List of instance info dicts
        """
        if not self.logging_manager:
            logger.warning("Logging manager not initialized")
            return []

        instance_ids = self.logging_manager.get_all_instance_ids()
        instances_info = []

        for instance_id in instance_ids:
            # Try to get metadata
            instance_dir = self.logging_manager.instances_dir / instance_id
            metadata_file = instance_dir / "metadata.json"

            if metadata_file.exists():
                try:
                    import json

                    metadata = json.loads(metadata_file.read_text())
                    instances_info.append(metadata)
                except Exception:
                    instances_info.append({"instance_id": instance_id})
            else:
                instances_info.append({"instance_id": instance_id})

        return instances_info

    @mcp.tool
    async def collect_team_artifacts(self, team_supervisor_id: str) -> dict[str, Any]:
        """Collect and organize artifacts from all team members.

        Gets all children of supervisor, creates team artifacts directory,
        copies artifacts from each child's workspace, generates team manifest JSON,
        and returns collection summary.

        Args:
            team_supervisor_id: Instance ID of the team supervisor/coordinator

        Returns:
            Dictionary with collection summary including artifacts_dir, manifest_path,
            members_count, total_files_collected, etc.
        """
        if team_supervisor_id not in self.instances:
            raise ValueError(f"Team supervisor instance {team_supervisor_id} not found")

        supervisor = self.instances[team_supervisor_id]

        try:
            # Get all children of the supervisor
            children = self._get_children_internal(team_supervisor_id)

            if not children:
                logger.warning(f"Team supervisor {team_supervisor_id} has no child instances")
                return {
                    "success": True,
                    "team_supervisor_id": team_supervisor_id,
                    "members_count": 0,
                    "total_files_collected": 0,
                    "message": "No child instances found",
                }

            # Create team artifacts directory structure
            artifacts_base = Path(self.config.get("artifacts_dir", "/tmp/madrox_artifacts"))
            artifacts_base.mkdir(parents=True, exist_ok=True)

            # Create team-specific directory (use supervisor ID)
            team_artifacts_dir = artifacts_base / f"team_{team_supervisor_id}"
            team_artifacts_dir.mkdir(parents=True, exist_ok=True)

            # Create subdirectory for each team member
            total_files_collected = 0
            member_summaries = []
            collection_errors = []

            import json
            import shutil

            for child in children:
                child_id = child["id"]
                child_name = child.get("name", "unknown")

                try:
                    # Get child's workspace artifacts
                    child_instance = self.instances[child_id]
                    child_workspace = Path(child_instance.get("workspace_dir", ""))

                    if not child_workspace.exists():
                        logger.warning(f"Child workspace does not exist for {child_id}")
                        collection_errors.append(
                            {"child_id": child_id, "error": "Workspace does not exist"}
                        )
                        continue

                    # Create child's artifacts subdirectory
                    child_artifacts_dir = team_artifacts_dir / child_id
                    child_artifacts_dir.mkdir(parents=True, exist_ok=True)

                    # Get artifact patterns from config
                    artifact_patterns = self.config.get(
                        "artifact_patterns",
                        ["*.py", "*.md", "*.json", "*.txt", "*.log", "*.yaml", "*.yml", "*.toml"],
                    )

                    # Copy matching files from child workspace
                    child_files_copied = 0
                    import fnmatch

                    for item in child_workspace.rglob("*"):
                        if not item.is_file():
                            continue

                        filename = item.name
                        matches_pattern = any(
                            fnmatch.fnmatch(filename, pattern) for pattern in artifact_patterns
                        )

                        if matches_pattern:
                            try:
                                relative_path = item.relative_to(child_workspace)
                                target_path = child_artifacts_dir / relative_path
                                target_path.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(item, target_path)
                                child_files_copied += 1
                                total_files_collected += 1
                            except Exception as e:
                                logger.warning(f"Failed to copy artifact {item}: {e}")
                                collection_errors.append(
                                    {"file": str(item), "error": str(e), "child_id": child_id}
                                )

                    # Create child metadata file
                    child_metadata = {
                        "child_id": child_id,
                        "child_name": child_name,
                        "instance_type": child.get("instance_type"),
                        "role": child.get("role"),
                        "model": child.get("model"),
                        "created_at": child.get("created_at"),
                        "files_collected": child_files_copied,
                        "workspace_dir": str(child_workspace),
                    }

                    child_metadata_path = child_artifacts_dir / "_metadata.json"
                    child_metadata_path.write_text(json.dumps(child_metadata, indent=2))

                    member_summaries.append(
                        {
                            "child_id": child_id,
                            "child_name": child_name,
                            "files_collected": child_files_copied,
                            "artifacts_dir": str(child_artifacts_dir),
                        }
                    )

                except Exception as e:
                    logger.error(f"Failed to collect artifacts from child {child_id}: {e}")
                    collection_errors.append({"child_id": child_id, "error": str(e)})

            # Generate team manifest JSON
            team_manifest = {
                "team_supervisor_id": team_supervisor_id,
                "supervisor_name": supervisor.get("name"),
                "team_artifacts_dir": str(team_artifacts_dir),
                "created_at": datetime.now(UTC).isoformat(),
                "members_count": len(children),
                "total_files_collected": total_files_collected,
                "member_summaries": member_summaries,
                "collection_errors": collection_errors if collection_errors else None,
            }

            # Write manifest to JSON file
            manifest_path = team_artifacts_dir / "_team_manifest.json"
            manifest_path.write_text(json.dumps(team_manifest, indent=2))

            logger.info(
                f"Collected team artifacts from {len(children)} members: {total_files_collected} files",
                extra={
                    "team_supervisor_id": team_supervisor_id,
                    "team_artifacts_dir": str(team_artifacts_dir),
                    "members_count": len(children),
                    "total_files": total_files_collected,
                },
            )

            return {
                "success": True,
                "team_supervisor_id": team_supervisor_id,
                "team_artifacts_dir": str(team_artifacts_dir),
                "members_count": len(children),
                "total_files_collected": total_files_collected,
                "manifest_path": str(manifest_path),
                "member_summaries": member_summaries,
                "errors": collection_errors if collection_errors else None,
            }

        except Exception as e:
            logger.error(
                f"Failed to collect team artifacts for supervisor {team_supervisor_id}: {e}",
                extra={"team_supervisor_id": team_supervisor_id, "error": str(e)},
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
                "team_supervisor_id": team_supervisor_id,
            }

    async def shutdown(self):
        """Shutdown the instance manager and clean up resources."""
        logger.info("Shutting down instance manager")

        # Terminate all instances
        for instance_id in list(self.instances.keys()):
            try:
                await self._terminate_instance_internal(instance_id, force=True)
            except Exception as e:
                logger.error(f"Error terminating instance {instance_id}: {e}")

        # Shutdown shared state manager
        if self.shared_state_manager:
            self.shared_state_manager.shutdown()
            logger.info("Shared state manager shutdown complete")
