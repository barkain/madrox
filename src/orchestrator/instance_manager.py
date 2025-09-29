"""Instance Manager for Claude Orchestrator."""

import asyncio
import logging
import os
import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .name_generator import get_instance_name
from .pty_instance import PTYInstance

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
        self.processes: dict[str, subprocess.Popen] = {}  # instance_id -> process
        self.pty_instances: dict[str, PTYInstance] = {}  # instance_id -> PTY instance
        self.message_queues: dict[str, asyncio.Queue] = {}
        self.response_buffers: dict[str, str] = {}  # instance_id -> buffered response
        self.message_history: dict[str, list[dict]] = {}  # instance_id -> message history

        # Job tracking for async messages
        self.jobs: dict[str, dict[str, Any]] = {}  # job_id -> job metadata
        self.job_processes: dict[str, subprocess.Popen] = {}  # job_id -> background process

        # Resource tracking
        self.total_tokens_used = 0
        self.total_cost = 0.0

        # Create workspace base directory
        self.workspace_base = Path(config.get("workspace_base_dir", "/tmp/claude_orchestrator"))
        self.workspace_base.mkdir(parents=True, exist_ok=True)

    async def spawn_instance(
        self,
        name: str | None = None,
        role: str = "general",
        system_prompt: str | None = None,
        model: str = "claude-4-sonnet-20250514",
        bypass_isolation: bool = False,
        use_pty: bool = False,  # Back to subprocess for reliability
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

        # Generate a funny name if not provided or if empty string
        if not name or name == "unnamed" or name == "":
            instance_name = get_instance_name(None)
        else:
            instance_name = get_instance_name(name)

        # Create isolated workspace
        workspace_dir = self.workspace_base / instance_id
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Build system prompt based on role
        if not system_prompt:
            system_prompt = self._get_role_prompt(role)

        # Add a greeting with the instance's funny name
        greeting = f"\n\nHello! I'm {instance_name}, your Madrox instance. "
        if instance_name.count('-') > 1:  # Has a title
            greeting += "As you can tell from my distinguished title, I'm here to help! "
        else:
            greeting += "I'm ready to assist you with any tasks you have. "
        greeting += "Let's get started! 🚀"

        system_prompt = system_prompt + greeting

        # Create instance record
        instance = {
            "id": instance_id,
            "name": instance_name,
            "role": role,
            "model": model,
            "state": "initializing",
            "system_prompt": system_prompt,
            "workspace_dir": str(workspace_dir),
            "bypass_isolation": bypass_isolation,
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
            "use_pty": use_pty,
        }

        self.instances[instance_id] = instance
        self.message_queues[instance_id] = asyncio.Queue()

        # Start the instance
        try:
            if use_pty:
                await self._initialize_pty_instance(instance_id)
            else:
                await self._initialize_instance(instance_id)
            instance["state"] = "running"
            mode = "PTY" if use_pty else "subprocess"
            logger.info(f"Successfully spawned Claude instance {instance_id} ({instance_name}) with role {role} using {mode}")
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
            If wait_for_response=True: Response data dict
            If wait_for_response=False: Dict with job_id and status
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
            if wait_for_response:
                # Send message and wait for response
                try:
                    if instance.get("use_pty", False):
                        response_data = await self._send_pty_message(instance_id, message, timeout_seconds)
                    else:
                        response_data = await asyncio.wait_for(
                            self._send_and_receive_message(
                                instance_id,
                                message,
                                process_timeout=timeout_seconds,
                            ),
                            timeout=timeout_seconds
                        )
                    return response_data
                except TimeoutError:
                    # On timeout, create a job for tracking and return partial status
                    logger.warning(f"Timeout waiting for response from instance {instance_id}")

                    # Create a job to track the ongoing work
                    job_id = str(uuid.uuid4())
                    timestamp = datetime.now(UTC).isoformat()

                    self.jobs[job_id] = {
                        "job_id": job_id,
                        "instance_id": instance_id,
                        "message": message,
                        "status": "processing",
                        "created_at": timestamp,
                        "updated_at": timestamp,
                        "result": None,
                        "error": None,
                        "estimated_completion_seconds": 30  # Estimate additional time needed
                    }

                    # Continue processing in background
                    asyncio.create_task(
                        self._continue_processing(job_id, instance_id, timeout_seconds)
                    )

                    return {
                        "status": "timeout",
                        "job_id": job_id,
                        "message": f"Request is still processing. Check status with job_id: {job_id}",
                        "estimated_wait_seconds": 30,
                        "instance_state": instance["state"],
                        "retry_recommended": True
                    }
            else:
                # Create job for async processing
                job_id = str(uuid.uuid4())
                timestamp = datetime.now(UTC).isoformat()

                self.jobs[job_id] = {
                    "job_id": job_id,
                    "instance_id": instance_id,
                    "message": message,
                    "status": "pending",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "result": None,
                    "error": None
                }

                # Add to message history
                if instance_id not in self.message_history:
                    self.message_history[instance_id] = []

                self.message_history[instance_id].append({
                    "role": "user",
                    "content": message,
                    "timestamp": timestamp,
                    "job_id": job_id
                })

                # Start async processing
                asyncio.create_task(
                    self._process_job_async(job_id, instance_id, message, timeout_seconds)
                )

                logger.info(f"Created async job {job_id} for instance {instance_id}")
                return {"job_id": job_id, "status": "pending"}

        finally:
            # Only update back to idle if we were waiting for response
            if wait_for_response and instance["state"] == "busy":
                instance["state"] = "idle"

    async def _monitor_background_process(
        self,
        job_id: str,
        process: subprocess.Popen,
        instance_id: str
    ):
        """Monitor a background process that timed out initially."""
        try:
            # Continue monitoring the process
            stdout, stderr = await asyncio.get_event_loop().run_in_executor(
                None, process.communicate
            )

            if process.returncode == 0 and stdout:
                response_text = stdout.strip()

                # Update job with result
                self.jobs[job_id]["status"] = "completed"
                self.jobs[job_id]["result"] = {
                    "instance_id": instance_id,
                    "message_id": str(uuid.uuid4()),
                    "response": response_text,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                self.jobs[job_id]["updated_at"] = datetime.now(UTC).isoformat()

                # Add to message history
                if instance_id in self.message_history:
                    self.message_history[instance_id].append({
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "job_id": job_id
                    })

                # Update usage statistics
                estimated_tokens = len(response_text.split())
                estimated_cost = estimated_tokens * 0.00001

                if instance_id in self.instances:
                    self.instances[instance_id]["total_tokens_used"] += estimated_tokens
                    self.instances[instance_id]["total_cost"] += estimated_cost

                logger.info(f"Background job {job_id} completed successfully")
            else:
                # Process failed
                self.jobs[job_id]["status"] = "failed"
                self.jobs[job_id]["error"] = stderr if stderr else "Process failed with no output"
                self.jobs[job_id]["updated_at"] = datetime.now(UTC).isoformat()
                logger.error(f"Background job {job_id} failed: {stderr}")

        except Exception as e:
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error"] = str(e)
            self.jobs[job_id]["updated_at"] = datetime.now(UTC).isoformat()
            logger.error(f"Error monitoring background job {job_id}: {e}")
        finally:
            # Clean up process reference from separate storage
            if job_id in self.job_processes:
                del self.job_processes[job_id]

    async def _continue_processing(
        self,
        job_id: str,
        instance_id: str,
        additional_timeout: int = 60
    ):
        """Continue processing a job that timed out initially."""
        try:
            # Wait a bit more for the response
            await asyncio.sleep(additional_timeout)

            # Check if we have a response in the buffer
            if instance_id in self.response_buffers and self.response_buffers[instance_id]:
                response_data = {"content": self.response_buffers[instance_id]}
                self.response_buffers[instance_id] = ""  # Clear buffer

                # Update job with result
                self.jobs[job_id]["status"] = "completed"
                self.jobs[job_id]["result"] = response_data
                self.jobs[job_id]["updated_at"] = datetime.now(UTC).isoformat()

                logger.info(f"Job {job_id} completed after extended wait")
            else:
                # Still no response, mark as requiring retry
                self.jobs[job_id]["status"] = "needs_retry"
                self.jobs[job_id]["updated_at"] = datetime.now(UTC).isoformat()
                self.jobs[job_id]["estimated_completion_seconds"] = 60

        except Exception as e:
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error"] = str(e)
            self.jobs[job_id]["updated_at"] = datetime.now(UTC).isoformat()
            logger.error(f"Error continuing job {job_id}: {e}")

    async def _process_job_async(
        self,
        job_id: str,
        instance_id: str,
        message: str,
        timeout_seconds: int
    ):
        """Process a job asynchronously."""
        try:
            # Update job status to processing
            self.jobs[job_id]["status"] = "processing"
            self.jobs[job_id]["updated_at"] = datetime.now(UTC).isoformat()

            # Send message and wait for response
            instance = self.instances[instance_id]
            if instance.get("use_pty", False):
                response_data = await self._send_pty_message(instance_id, message, timeout_seconds)
            else:
                response_data = await asyncio.wait_for(
                    self._send_and_receive_message(
                        instance_id,
                        message,
                        process_timeout=timeout_seconds,
                    ),
                    timeout=timeout_seconds
                )

            # Update job with result
            self.jobs[job_id]["status"] = "completed"
            self.jobs[job_id]["result"] = response_data
            self.jobs[job_id]["updated_at"] = datetime.now(UTC).isoformat()

            # Add response to message history
            if instance_id in self.message_history:
                self.message_history[instance_id].append({
                    "role": "assistant",
                    "content": response_data.get("content", ""),
                    "timestamp": datetime.now(UTC).isoformat(),
                    "job_id": job_id
                })

            logger.info(f"Completed job {job_id} for instance {instance_id}")

        except TimeoutError:
            # Don't mark as failed on timeout - keep processing
            self.jobs[job_id]["status"] = "processing_slow"
            self.jobs[job_id]["error"] = None
            self.jobs[job_id]["updated_at"] = datetime.now(UTC).isoformat()
            self.jobs[job_id]["estimated_completion_seconds"] = 30
            logger.warning(f"Job {job_id} taking longer than {timeout_seconds} seconds, continuing in background")

        except Exception as e:
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error"] = str(e)
            self.jobs[job_id]["updated_at"] = datetime.now(UTC).isoformat()
            logger.error(f"Job {job_id} failed: {e}")

        finally:
            # Update instance state back to idle
            if instance_id in self.instances:
                self.instances[instance_id]["state"] = "idle"

    async def get_job_status(self, job_id: str, wait_for_completion: bool = True, max_wait: int = 120) -> dict[str, Any] | None:
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

        instance = self.instances[instance_id]

        # Get message history for this instance
        if instance_id not in self.message_history:
            return []

        messages = self.message_history[instance_id]

        # Convert messages to output format
        output_messages = []
        for i, msg in enumerate(messages):
            output_messages.append({
                "instance_id": instance_id,
                "timestamp": instance["last_activity"],  # Would be better to track per-message
                "type": "user" if msg["role"] == "user" else "response",
                "content": msg["content"],
                "message_index": i
            })

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

            # Clean up PTY instance if exists
            if instance_id in self.pty_instances:
                await self.pty_instances[instance_id].cleanup()
                del self.pty_instances[instance_id]

            # Update instance state
            instance["state"] = "terminated"
            instance["terminated_at"] = datetime.now(UTC).isoformat()

            # Clean up message queue
            if instance_id in self.message_queues:
                del self.message_queues[instance_id]

            # Remove conversation history
            if instance_id in self.message_history:
                del self.message_history[instance_id]

            # Remove process tracking (processes are spawned per message now)
            if instance_id in self.processes:
                del self.processes[instance_id]

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
        """Initialize a Claude CLI instance."""
        instance = self.instances[instance_id]

        logger.info(f"Initializing Claude CLI instance {instance_id}")

        # Initialize message history
        self.message_history[instance_id] = []
        self.response_buffers[instance_id] = ""

        # Workspace directory is already prepared during spawn

        # Build the Claude CLI command for interactive mode
        # Each message spawns a new claude process with the full conversation context
        cmd = [
            "claude",
            "--permission-mode", "bypassPermissions",  # Allow file operations without approval
            "--print"  # Ensure we get output
        ]

        # Add allowed tools if specified
        if "allowed_tools" in instance:
            cmd.extend(["--allowed-tools"] + instance["allowed_tools"])

        # Store the command template for this instance
        instance["cmd_template"] = cmd

        # Add the initial system prompt as context
        system_prompt = instance["system_prompt"]
        workspace_path = instance["workspace_dir"]  # Get the string path

        if instance.get("bypass_isolation", False):
            # Full filesystem access
            instance["context"] = (
                f"You are a specialized Claude instance. {system_prompt}\n\n"
                f"IMPORTANT: You have FULL FILESYSTEM ACCESS. You can read and write files anywhere.\n"
                f"Your workspace directory is at: {workspace_path}\n"
                f"Your current working directory will be: {Path.cwd()}\n"
                f"You can write files to any absolute path or relative to the current directory."
            )
        else:
            # Isolated workspace
            instance["context"] = (
                f"You are a specialized Claude instance. {system_prompt}\n\n"
                f"IMPORTANT: You have a workspace directory at: {workspace_path}\n"
                f"You can read and write files within this directory. When asked to write files, "
                f"write them to your workspace directory unless specifically asked to write elsewhere. "
                f"Your current working directory is: {workspace_path}"
            )

        # Initialize without starting a process yet
        # Processes will be started on-demand for each message
        logger.info(f"Instance {instance_id} initialized (process will start on first message)")
        instance["conversation_id"] = f"conv_{instance_id}"

    async def _initialize_pty_instance(self, instance_id: str):
        """Initialize a PTY-based Claude CLI instance."""
        instance = self.instances[instance_id]

        logger.info(f"Initializing PTY Claude CLI instance {instance_id}")

        # Initialize message history
        self.message_history[instance_id] = []
        self.response_buffers[instance_id] = ""

        # Add the context for PTY instances
        system_prompt = instance["system_prompt"]
        workspace_path = instance["workspace_dir"]

        if instance.get("bypass_isolation", False):
            # Full filesystem access
            instance["context"] = (
                f"You are a specialized Claude instance. {system_prompt}\n\n"
                f"IMPORTANT: You have FULL FILESYSTEM ACCESS. You can read and write files anywhere.\n"
                f"Your workspace directory is at: {workspace_path}\n"
                f"Your current working directory will be: {Path.cwd()}\n"
                f"You can write files to any absolute path or relative to the current directory."
            )
        else:
            # Isolated workspace
            instance["context"] = (
                f"You are a specialized Claude instance. {system_prompt}\n\n"
                f"IMPORTANT: You have a workspace directory at: {workspace_path}\n"
                f"You can read and write files within this directory. When asked to write files, "
                f"write them to your workspace directory unless specifically asked to write elsewhere. "
                f"Your current working directory is: {workspace_path}"
            )

        # Create PTY instance
        pty_instance = PTYInstance(instance_id, instance)

        # Start the PTY session
        await pty_instance.start()

        # Store PTY instance
        self.pty_instances[instance_id] = pty_instance

        logger.info(f"PTY instance {instance_id} initialized successfully")
        instance["conversation_id"] = f"conv_{instance_id}"

    async def _send_pty_message(self, instance_id: str, message: str, timeout: int) -> dict[str, Any]:
        """Send message to PTY instance and get response."""
        if instance_id not in self.pty_instances:
            raise RuntimeError(f"PTY instance {instance_id} not found")

        pty_instance = self.pty_instances[instance_id]

        # Record message in history
        if instance_id not in self.message_history:
            self.message_history[instance_id] = []

        self.message_history[instance_id].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now(UTC).isoformat()
        })

        try:
            # Send message via PTY
            response_data = await pty_instance.send_message(message, timeout)

            # Add response to history
            self.message_history[instance_id].append({
                "role": "assistant",
                "content": response_data.get("response", ""),
                "timestamp": datetime.now(UTC).isoformat()
            })

            # Update usage statistics (estimates)
            estimated_tokens = len(message.split()) + len(response_data.get("response", "").split())
            estimated_cost = estimated_tokens * 0.00001

            instance = self.instances[instance_id]
            instance["total_tokens_used"] += estimated_tokens
            instance["total_cost"] += estimated_cost
            instance["request_count"] += 1

            self.total_tokens_used += estimated_tokens
            self.total_cost += estimated_cost

            return {
                "instance_id": instance_id,
                "message_id": str(uuid.uuid4()),
                "response": response_data.get("response", ""),
                "timestamp": datetime.now(UTC).isoformat(),
                "tokens_used": estimated_tokens,
                "cost": estimated_cost
            }

        except Exception as e:
            logger.error(f"Error sending PTY message to instance {instance_id}: {e}")
            raise

    async def _send_and_receive_message(
        self,
        instance_id: str,
        message: str,
        *,
        process_timeout: int | float | None = None,
    ) -> dict[str, Any]:
        """Send message to Claude CLI instance and receive response."""
        instance = self.instances[instance_id]

        # Record message in history
        if instance_id not in self.message_history:
            self.message_history[instance_id] = []

        self.message_history[instance_id].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now(UTC).isoformat()
        })

        try:
            # Build conversation context from history
            context = instance.get("context", "")
            conversation = "\n\n".join([
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in self.message_history[instance_id][-5:]  # Last 5 messages for context
            ])

            # Construct the full prompt with context
            full_prompt = f"{context}\n\n{conversation}\n\nPlease respond to the latest user message."

            # Create a new process for this interaction
            cmd = instance["cmd_template"] + [full_prompt]

            # Pass current environment to subprocess so MCP servers work
            env = os.environ.copy()

            # Add any instance-specific environment variables
            if "environment_vars" in instance:
                env.update(instance["environment_vars"])

            # Set working directory based on isolation setting
            working_dir = str(Path.cwd()) if instance.get("bypass_isolation", False) else instance["workspace_dir"]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=working_dir,
                env=env,  # Pass environment to subprocess
                text=True,
                bufsize=-1
            )

            # Store process for potential later retrieval
            self.processes[instance_id] = process

            try:
                # Wait for the response
                stdout, stderr = process.communicate(
                    timeout=process_timeout if process_timeout is not None else 180
                )

                if process.returncode != 0:
                    logger.error(f"Claude CLI failed: {stderr}")
                    raise RuntimeError(f"Claude CLI process failed: {stderr}")

                response_text = stdout.strip()

                if not response_text:
                    raise RuntimeError("No response received from Claude CLI")

                # Add assistant response to history
                self.message_history[instance_id].append({
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now(UTC).isoformat()
                })

                # Update usage statistics (estimates since CLI doesn't provide token counts)
                estimated_tokens = len(message.split()) + len(response_text.split())
                estimated_cost = estimated_tokens * 0.00001  # Rough estimate

                instance["total_tokens_used"] += estimated_tokens
                instance["total_cost"] += estimated_cost
                instance["request_count"] += 1

                self.total_tokens_used += estimated_tokens
                self.total_cost += estimated_cost

                logger.debug(f"Sent message to instance {instance_id}. Response length: {len(response_text)}")

                return {
                    "instance_id": instance_id,
                    "message_id": str(uuid.uuid4()),
                    "response": response_text,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "tokens_used": estimated_tokens,
                    "cost": estimated_cost
                }

            except subprocess.TimeoutExpired:
                # Don't kill the process - let it continue running
                logger.warning(f"Timeout waiting for response from instance {instance_id}, but process continues")

                # Create a job to track the ongoing work
                job_id = str(uuid.uuid4())
                timestamp = datetime.now(UTC).isoformat()

                self.jobs[job_id] = {
                    "job_id": job_id,
                    "instance_id": instance_id,
                    "message": message,
                    "status": "processing",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "result": None,
                    "error": None,
                    "estimated_completion_seconds": 60
                }

                # Store process separately to avoid JSON serialization issues
                self.job_processes[job_id] = process

                # Start monitoring the process in background
                asyncio.create_task(
                    self._monitor_background_process(job_id, process, instance_id)
                )

                # Return timeout response with job tracking
                return {
                    "status": "timeout",
                    "job_id": job_id,
                    "message": "Request is still processing in background",
                    "estimated_wait_seconds": 60,
                    "instance_state": instance["state"]
                }
        except Exception as e:
            logger.error(f"Error communicating with Claude CLI: {e}")
            raise RuntimeError(f"Failed to communicate with Claude CLI: {e}") from e


    async def _process_queued_message(self, instance_id: str) -> dict[str, Any] | None:
        """Process a queued message for an instance.

        This method is used when messages are sent without waiting for response.
        """
        if instance_id not in self.message_queues:
            return None

        try:
            # Get message from queue with a short timeout
            message = await asyncio.wait_for(
                self.message_queues[instance_id].get(),
                timeout=1.0
            )

            # Process the message
            return await self._send_and_receive_message(instance_id, message)

        except TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Error processing queued message for instance {instance_id}: {e}")
            return None

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

        # Clean up process tracking (processes are spawned per message now)
        if instance_id in self.processes:
            del self.processes[instance_id]
            logger.debug(f"Cleaned up process tracking for instance {instance_id}")

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

    async def retrieve_instance_file(
        self,
        instance_id: str,
        filename: str,
        destination_path: str | None = None
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
