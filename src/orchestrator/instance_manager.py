"""Instance Manager for Claude Orchestrator."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .tmux_instance_manager import TmuxInstanceManager

logger = logging.getLogger(__name__)


class InstanceManager:
    """Manages Claude instances and their lifecycle."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the instance manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.instances: dict[str, dict[str, Any]] = {}

        # Job tracking for async messages
        self.jobs: dict[str, dict[str, Any]] = {}  # job_id -> job metadata

        # Resource tracking
        self.total_tokens_used = 0
        self.total_cost = 0.0

        # Create workspace base directory
        self.workspace_base = Path(config.get("workspace_base_dir", "/tmp/claude_orchestrator"))
        self.workspace_base.mkdir(parents=True, exist_ok=True)

        # Initialize Tmux instance manager for Claude and Codex instances
        self.tmux_manager = TmuxInstanceManager(config)

    async def spawn_instance(
        self,
        name: str | None = None,
        role: str = "general",
        system_prompt: str | None = None,
        model: str | None = None,
        bypass_isolation: bool = False,
        enable_madrox: bool = False,
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
            enable_madrox: Enable madrox MCP server tools (allows spawning sub-instances)
            instance_type: Type of instance (always "claude", handled by tmux)
            **kwargs: Additional configuration options

        Returns:
            Instance ID
        """
        # All Claude instances are handled by TmuxInstanceManager
        instance_id = await self.tmux_manager.spawn_instance(
            name=name,
            role=role,
            system_prompt=system_prompt,
            model=model,
            bypass_isolation=bypass_isolation,
            enable_madrox=enable_madrox,
            **kwargs,
        )
        # Copy instance to main instances dict for unified tracking
        self.instances[instance_id] = self.tmux_manager.instances[instance_id]
        self.instances[instance_id]["instance_type"] = "claude"
        return instance_id

    async def spawn_codex_instance(
        self,
        name: str | None = None,
        model: str | None = None,
        sandbox_mode: str = "workspace-write",
        profile: str | None = None,
        initial_prompt: str | None = None,
        bypass_isolation: bool = False,
        **kwargs,
    ) -> str:
        """Spawn a new Codex CLI instance.

        Args:
            name: Human-readable name for the instance
            model: Codex model to use - OpenAI models only (None = use CLI default, typically gpt-5-codex)
            sandbox_mode: Sandbox policy for shell commands
            profile: Configuration profile from config.toml
            initial_prompt: Initial prompt to start the session
            bypass_isolation: Allow full filesystem access
            **kwargs: Additional configuration options

        Returns:
            Instance ID
        """
        # Validate model - Codex only supports OpenAI models
        if model and ("claude" in model.lower() or "anthropic" in model.lower()):
            raise ValueError(
                f"Invalid model '{model}' for Codex instance. "
                f"Codex only supports OpenAI models (e.g., 'gpt-5-codex', 'gpt-4', 'gpt-4o'). "
                f"Use spawn_instance() for Claude models."
            )

        # Delegate to TmuxInstanceManager for Codex instances
        instance_id = await self.tmux_manager.spawn_instance(
            name=name,
            model=model,
            bypass_isolation=bypass_isolation,
            sandbox_mode=sandbox_mode,
            profile=profile,
            initial_prompt=initial_prompt,
            instance_type="codex",
            **kwargs,
        )
        # Copy instance to main instances dict for unified tracking
        self.instances[instance_id] = self.tmux_manager.instances[instance_id]
        self.instances[instance_id]["instance_type"] = "codex"
        return instance_id

    async def send_to_instance(
        self,
        instance_id: str,
        message: str,
        wait_for_response: bool = True,
        timeout_seconds: int = 30,
        priority: int = 0,
    ) -> dict[str, Any] | None:
        """Send a message to a Claude or Codex instance.

        Args:
            instance_id: Target instance ID
            message: Message to send
            wait_for_response: Whether to wait for response
            timeout_seconds: Response timeout
            priority: Message priority (currently unused)

        Returns:
            If wait_for_response=True: Response data dict
            If wait_for_response=False: Dict with job_id and status
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        # Delegate to TmuxInstanceManager for Claude and Codex instances
        if instance.get("instance_type") in ["claude", "codex"]:
            return await self.tmux_manager.send_message(
                instance_id=instance_id,
                message=message,
                wait_for_response=wait_for_response,
                timeout_seconds=timeout_seconds,
            )

        # No other instance types supported
        raise ValueError(f"Unsupported instance type: {instance.get('instance_type')}")

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

    async def get_instance_output(
        self, instance_id: str, since: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get recent output from an instance.

        Args:
            instance_id: Instance ID
            since: ISO timestamp to get messages since
            limit: Maximum number of messages

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
                return []

        # Apply limit
        if len(output_messages) > limit:
            return output_messages[-limit:]

        return output_messages

    async def coordinate_instances(
        self,
        coordinator_id: str,
        participant_ids: list[str],
        task_description: str,
        coordination_type: str = "sequential",
    ) -> str:
        """Coordinate multiple instances for a task.

        Args:
            coordinator_id: ID of coordinating instance
            participant_ids: List of participating instance IDs
            task_description: Description of the coordination task
            coordination_type: Type of coordination (sequential, parallel, consensus)

        Returns:
            Coordination task ID
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

        return task_id

    async def terminate_instance(self, instance_id: str, force: bool = False) -> bool:
        """Terminate a Claude or Codex instance.

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

    def get_instance_status(self, instance_id: str | None = None) -> dict[str, Any]:
        """Get status of instance(s).

        Args:
            instance_id: Specific instance ID, or None for all instances

        Returns:
            Instance status data
        """
        if instance_id:
            if instance_id not in self.instances:
                raise ValueError(f"Instance {instance_id} not found")
            return self.instances[instance_id].copy()
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

    def _get_role_prompt(self, role: str) -> str:
        """Get system prompt for a role."""
        role_prompts = {
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

        return role_prompts.get(role, role_prompts["general"])

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
                await self.terminate_instance(instance_id, force=True)
                continue

            # Check resource limits
            max_tokens = instance.get("resource_limits", {}).get("max_total_tokens")
            if max_tokens and instance["total_tokens_used"] > max_tokens:
                logger.warning(f"Instance {instance_id} exceeded token limit, terminating")
                await self.terminate_instance(instance_id, force=True)
                continue

            max_cost = instance.get("resource_limits", {}).get("max_cost")
            if max_cost and instance["total_cost"] > max_cost:
                logger.warning(f"Instance {instance_id} exceeded cost limit, terminating")
                await self.terminate_instance(instance_id, force=True)
                continue

        logger.info(
            f"Health check complete. Active instances: {len([i for i in self.instances.values() if i['state'] not in ['terminated', 'error']])}"
        )

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

    async def list_instance_files(self, instance_id: str) -> list[str] | None:
        """List all files in an instance's workspace directory.

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
