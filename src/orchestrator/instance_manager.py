"""Instance Manager for Claude Orchestrator."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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
        self.message_queues: dict[str, asyncio.Queue] = {}
        self.active_conversations: dict[str, str] = {}  # instance_id -> conversation_id

        # Resource tracking
        self.total_tokens_used = 0
        self.total_cost = 0.0

        # Create workspace base directory
        self.workspace_base = Path(config.get("workspace_base_dir", "/tmp/claude_orchestrator"))
        self.workspace_base.mkdir(parents=True, exist_ok=True)

    async def spawn_instance(
        self,
        name: str,
        role: str = "general",
        system_prompt: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        **kwargs
    ) -> str:
        """Spawn a new Claude instance.

        Args:
            name: Human-readable name for the instance
            role: Predefined role (general, frontend_developer, etc.)
            system_prompt: Custom system prompt
            model: Claude model to use
            **kwargs: Additional configuration options

        Returns:
            Instance ID
        """
        if len(self.instances) >= self.config.get("max_concurrent_instances", 10):
            raise RuntimeError("Maximum concurrent instances reached")

        instance_id = str(uuid.uuid4())

        # Create isolated workspace
        workspace_dir = self.workspace_base / instance_id
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Build system prompt based on role
        if not system_prompt:
            system_prompt = self._get_role_prompt(role)

        # Create instance record
        instance = {
            "id": instance_id,
            "name": name,
            "role": role,
            "model": model,
            "state": "initializing",
            "system_prompt": system_prompt,
            "workspace_dir": str(workspace_dir),
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity": datetime.now(UTC).isoformat(),
            "total_tokens_used": 0,
            "total_cost": 0.0,
            "request_count": 0,
            "conversation_id": None,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.0),
            "environment_vars": kwargs.get("environment_vars", {}),
            "resource_limits": kwargs.get("resource_limits", {}),
            "parent_instance_id": kwargs.get("parent_instance_id"),
            "error_message": None,
            "retry_count": 0,
        }

        self.instances[instance_id] = instance
        self.message_queues[instance_id] = asyncio.Queue()

        # Start the instance
        try:
            await self._initialize_instance(instance_id)
            instance["state"] = "running"
            logger.info(f"Successfully spawned Claude instance {instance_id} ({name}) with role {role}")
        except Exception as e:
            instance["state"] = "error"
            instance["error_message"] = str(e)
            logger.error(f"Failed to initialize instance {instance_id}: {e}")
            raise

        return instance_id

    async def send_to_instance(
        self,
        instance_id: str,
        message: str,
        wait_for_response: bool = True,
        timeout_seconds: int = 30,
        priority: int = 0
    ) -> dict[str, Any] | None:
        """Send a message to a Claude instance.

        Args:
            instance_id: Target instance ID
            message: Message to send
            wait_for_response: Whether to wait for response
            timeout_seconds: Response timeout
            priority: Message priority

        Returns:
            Response data if wait_for_response=True, None otherwise
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]
        if instance["state"] not in ["running", "idle"]:
            raise RuntimeError(f"Instance {instance_id} is not in a valid state: {instance['state']}")

        # Update instance state
        instance["state"] = "busy"
        instance["last_activity"] = datetime.now(UTC).isoformat()

        try:
            # Send message to instance (mock implementation for now)
            response = await self._send_message_to_claude(instance_id, message)

            if wait_for_response:
                # Wait for response with timeout
                try:
                    response_data = await asyncio.wait_for(
                        self._wait_for_response(instance_id, response["message_id"]),
                        timeout=timeout_seconds
                    )
                    return response_data
                except TimeoutError:
                    logger.warning(f"Timeout waiting for response from instance {instance_id}")
                    return None
        finally:
            # Update instance state back to idle
            if instance["state"] == "busy":
                instance["state"] = "idle"

        return None

    async def get_instance_output(
        self,
        instance_id: str,
        since: str | None = None,
        limit: int = 100
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

        # Mock implementation - in real implementation, this would fetch from message history
        instance = self.instances[instance_id]

        return [
            {
                "instance_id": instance_id,
                "timestamp": instance["last_activity"],
                "type": "response",
                "content": f"Sample output from {instance['name']}",
                "tokens_used": 10,
                "cost": 0.001
            }
        ]

    async def coordinate_instances(
        self,
        coordinator_id: str,
        participant_ids: list[str],
        task_description: str,
        coordination_type: str = "sequential"
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
            "results": {}
        }

        logger.info(f"Started coordination task {task_id} with {len(participant_ids)} participants")

        # Start coordination process in background
        asyncio.create_task(self._execute_coordination(coordination_task))

        return task_id

    async def terminate_instance(self, instance_id: str, force: bool = False) -> bool:
        """Terminate a Claude instance.

        Args:
            instance_id: Instance ID to terminate
            force: Force termination even if busy

        Returns:
            True if terminated successfully
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        if not force and instance["state"] == "busy":
            logger.warning(f"Cannot terminate busy instance {instance_id} without force=True")
            return False

        try:
            # Clean up instance resources
            await self._cleanup_instance(instance_id)

            # Update instance state
            instance["state"] = "terminated"
            instance["terminated_at"] = datetime.now(UTC).isoformat()

            # Clean up message queue
            if instance_id in self.message_queues:
                del self.message_queues[instance_id]

            # Remove conversation
            if instance_id in self.active_conversations:
                del self.active_conversations[instance_id]

            logger.info(f"Successfully terminated instance {instance_id}")
            return True

        except Exception as e:
            logger.error(f"Error terminating instance {instance_id}: {e}")
            instance["error_message"] = str(e)
            return False

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
                "active_instances": len([i for i in self.instances.values() if i["state"] in ["running", "idle", "busy"]]),
                "total_tokens_used": self.total_tokens_used,
                "total_cost": self.total_cost
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
            "data_analyst": "You are a data analyst who works with data processing, analysis, and visualization."
        }

        return role_prompts.get(role, role_prompts["general"])

    async def _initialize_instance(self, instance_id: str):
        """Initialize a Claude instance."""
        instance = self.instances[instance_id]

        # Mock initialization - in real implementation, this would:
        # 1. Create isolated environment
        # 2. Start Claude conversation
        # 3. Send initial system prompt
        # 4. Verify instance is responsive

        logger.info(f"Initializing instance {instance_id}")

        # Simulate initialization delay
        await asyncio.sleep(0.1)

        # Create conversation ID (mock)
        conversation_id = f"conv_{uuid.uuid4()}"
        instance["conversation_id"] = conversation_id
        self.active_conversations[instance_id] = conversation_id

    async def _send_message_to_claude(self, instance_id: str, message: str) -> dict[str, Any]:
        """Send message to Claude instance."""
        instance = self.instances[instance_id]

        # Mock implementation - in real implementation, this would use Claude API
        message_id = str(uuid.uuid4())

        # Update usage statistics
        tokens_used = len(message.split()) * 2  # Rough estimate
        cost = tokens_used * 0.00001  # Mock cost calculation

        instance["total_tokens_used"] += tokens_used
        instance["total_cost"] += cost
        instance["request_count"] += 1

        self.total_tokens_used += tokens_used
        self.total_cost += cost

        logger.debug(f"Sent message to instance {instance_id}: {message[:100]}...")

        return {
            "message_id": message_id,
            "tokens_used": tokens_used,
            "cost": cost
        }

    async def _wait_for_response(self, instance_id: str, message_id: str) -> dict[str, Any]:
        """Wait for response from Claude instance."""
        # Mock implementation - simulate processing time
        await asyncio.sleep(0.5)

        return {
            "instance_id": instance_id,
            "message_id": message_id,
            "response": f"Mock response from instance {instance_id}",
            "timestamp": datetime.now(UTC).isoformat(),
            "tokens_used": 20,
            "cost": 0.0002,
            "processing_time_ms": 500
        }

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
                        f"Please work on step {i+1} of the coordination task: {coordination_task['description']}"
                    )
                    coordination_task["results"][participant_id] = step_result

            coordination_task["status"] = "completed"
            coordination_task["completed_at"] = datetime.now(UTC).isoformat()

            logger.info(f"Completed coordination task {task_id}")

        except Exception as e:
            logger.error(f"Error in coordination task {task_id}: {e}")
            coordination_task["status"] = "failed"
            coordination_task["error"] = str(e)

    async def _cleanup_instance(self, instance_id: str):
        """Clean up instance resources."""
        instance = self.instances[instance_id]

        # Clean up workspace directory
        workspace_dir = Path(instance["workspace_dir"])
        if workspace_dir.exists():
            try:
                import shutil
                shutil.rmtree(workspace_dir)
                logger.debug(f"Cleaned up workspace for instance {instance_id}")
            except Exception as e:
                logger.warning(f"Failed to clean up workspace for {instance_id}: {e}")

        # Close any active conversations
        # (Mock implementation - real version would close Claude conversations)
        if instance_id in self.active_conversations:
            logger.debug(f"Closed conversation for instance {instance_id}")

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

        logger.info(f"Health check complete. Active instances: {len([i for i in self.instances.values() if i['state'] not in ['terminated', 'error']])}")
