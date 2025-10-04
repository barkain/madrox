"""Tmux-based Instance Manager for Claude Orchestrator.

Manages Claude CLI instances via tmux sessions for persistent interactive communication.
"""

import asyncio
import logging
import re
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import libtmux

from .name_generator import get_instance_name

logger = logging.getLogger(__name__)


class TmuxInstanceManager:
    """Manages Claude instances via tmux sessions."""

    def __init__(self, config: dict[str, Any], logging_manager=None):
        """Initialize the tmux instance manager.

        Args:
            config: Configuration dictionary
            logging_manager: Optional LoggingManager instance for structured logging
        """
        self.config = config
        self.instances: dict[str, dict[str, Any]] = {}
        self.tmux_sessions: dict[str, libtmux.Session] = {}
        self.message_history: dict[str, list[dict]] = {}
        self.logging_manager = logging_manager

        # Resource tracking
        self.total_tokens_used = 0
        self.total_cost = 0.0

        # Create workspace base directory
        self.workspace_base = Path(config.get("workspace_base_dir", "/tmp/claude_orchestrator"))
        self.workspace_base.mkdir(parents=True, exist_ok=True)

        # Connect to tmux server
        self.tmux_server = libtmux.Server()
        logger.info("Connected to tmux server")

    async def spawn_instance(
        self,
        name: str | None = None,
        role: str = "general",
        system_prompt: str | None = None,
        model: str | None = None,
        bypass_isolation: bool = False,
        enable_madrox: bool = True,
        instance_type: str = "claude",
        sandbox_mode: str | None = None,
        profile: str | None = None,
        initial_prompt: str | None = None,
        wait_for_ready: bool = True,
        **kwargs,
    ) -> str:
        """Spawn a new Claude or Codex instance in a tmux session.

        Args:
            name: Human-readable name for the instance
            role: Predefined role (general, frontend_developer, etc.)
            system_prompt: Custom system prompt
            model: Claude/Codex model to use (None = use CLI default)
            bypass_isolation: Allow full filesystem access
            enable_madrox: Enable madrox MCP server tools
            instance_type: Type of instance - "claude" or "codex"
            sandbox_mode: For Codex - sandbox policy (read-only, workspace-write, danger-full-access)
            profile: For Codex - configuration profile from config.toml
            initial_prompt: For Codex - initial prompt to send after initialization
            wait_for_ready: Wait for instance to fully initialize (default: True). If False, returns immediately.
            **kwargs: Additional configuration options

        Returns:
            Instance ID
        """
        # Count only active instances
        active_count = len([i for i in self.instances.values() if i["state"] != "terminated"])
        if active_count >= self.config.get("max_concurrent_instances", 10):
            raise RuntimeError("Maximum concurrent instances reached")

        instance_id = str(uuid.uuid4())

        # Generate a funny name if not provided
        if not name or name == "unnamed" or name == "":
            instance_name = get_instance_name(None)
        else:
            instance_name = get_instance_name(name)

        # Create isolated workspace
        workspace_dir = self.workspace_base / instance_id
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Write instance metadata file so child knows its own ID
        metadata_file = workspace_dir / ".madrox_instance_id"
        metadata_file.write_text(instance_id)

        # Register madrox MCP if enabled
        if enable_madrox:
            try:
                result = subprocess.run(
                    [
                        "claude",
                        "mcp",
                        "add",
                        "madrox",
                        "http://localhost:8001/mcp",
                        "--transport",
                        "http",
                        "--scope",
                        "local",
                    ],
                    cwd=str(workspace_dir),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    logger.info(f"Registered madrox MCP for instance {instance_id}")
                else:
                    logger.warning(f"Failed to register madrox MCP: {result.stderr}")
            except Exception as e:
                logger.warning(f"Could not register madrox MCP: {e}")

        # Build system prompt based on role
        has_custom_prompt = bool(system_prompt)
        if not system_prompt:
            system_prompt = self._get_role_prompt(role)
            greeting = f"\n\nHello! I'm {instance_name}, your Madrox instance. "
            if instance_name.count("-") > 1:
                greeting += "As you can tell from my distinguished title, I'm here to help! "
            else:
                greeting += "I'm ready to assist you with any tasks you have. "
            system_prompt = system_prompt + greeting

        # Create instance record
        instance = {
            "id": instance_id,
            "name": instance_name,
            "role": role,
            "model": model,
            "state": "initializing",
            "system_prompt": system_prompt,
            "has_custom_prompt": has_custom_prompt,
            "workspace_dir": str(workspace_dir),
            "bypass_isolation": bypass_isolation,
            "enable_madrox": enable_madrox,
            "instance_type": instance_type,
            "sandbox_mode": sandbox_mode,
            "profile": profile,
            "initial_prompt": initial_prompt,
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity": datetime.now(UTC).isoformat(),
            "total_tokens_used": 0,
            "total_cost": 0.0,
            "request_count": 0,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.0),
            "environment_vars": kwargs.get("environment_vars", {}),
            "resource_limits": kwargs.get("resource_limits", {}),
            "parent_instance_id": kwargs.get("parent_instance_id"),
            "error_message": None,
            "retry_count": 0,
        }

        self.instances[instance_id] = instance
        self.message_history[instance_id] = []

        # Setup instance-specific logger
        if self.logging_manager:
            instance_logger = self.logging_manager.get_instance_logger(instance_id, instance_name)
            instance_logger.info(f"Instance created with role: {role}, type: {instance_type}")

            # Log audit event
            self.logging_manager.log_audit_event(
                event_type="instance_spawn",
                instance_id=instance_id,
                details={
                    "instance_name": instance_name,
                    "role": role,
                    "instance_type": instance_type,
                    "model": model,
                    "enable_madrox": enable_madrox,
                    "bypass_isolation": bypass_isolation,
                },
            )

        # Start the tmux session
        if wait_for_ready:
            # Blocking: wait for full initialization
            try:
                await self._initialize_tmux_session(instance_id)
                instance["state"] = "running"
                logger.info(
                    f"Successfully spawned {instance_type} instance {instance_id} ({instance_name}) with role {role} via tmux",
                    extra={
                        "instance_id": instance_id,
                        "instance_type": instance_type,
                        "role": role,
                        "instance_name": instance_name,
                    },
                )

                if self.logging_manager:
                    instance_logger = self.logging_manager.get_instance_logger(
                        instance_id, instance_name
                    )
                    instance_logger.info("Instance initialization completed successfully")

            except Exception as e:
                instance["state"] = "error"
                instance["error_message"] = str(e)
                logger.error(
                    f"Failed to initialize tmux instance {instance_id}: {e}",
                    extra={"instance_id": instance_id, "error": str(e)},
                )

                if self.logging_manager:
                    instance_logger = self.logging_manager.get_instance_logger(
                        instance_id, instance_name
                    )
                    instance_logger.error(f"Initialization failed: {e}")

                raise
        else:
            # Non-blocking: launch initialization in background
            logger.info(
                f"Spawning {instance_type} instance {instance_id} ({instance_name}) in background",
                extra={"instance_id": instance_id, "instance_type": instance_type},
            )
            asyncio.create_task(self._initialize_instance_background(instance_id))

        return instance_id

    async def _initialize_instance_background(self, instance_id: str):
        """Initialize an instance in the background (non-blocking spawn).

        Args:
            instance_id: Instance ID to initialize
        """
        instance = self.instances.get(instance_id)
        if not instance:
            logger.error(f"Instance {instance_id} not found for background initialization")
            return

        try:
            await self._initialize_tmux_session(instance_id)
            instance["state"] = "running"
            logger.info(
                f"Background initialization completed for instance {instance_id} ({instance['name']})",
                extra={"instance_id": instance_id, "instance_name": instance["name"]},
            )
        except Exception as e:
            instance["state"] = "error"
            instance["error_message"] = str(e)
            logger.error(
                f"Background initialization failed for instance {instance_id}: {e}",
                extra={"instance_id": instance_id, "error": str(e)},
            )

    async def send_message(
        self,
        instance_id: str,
        message: str,
        wait_for_response: bool = True,
        timeout_seconds: int = 30,
    ) -> dict[str, Any]:
        """Send a message to a Claude instance via tmux.

        Args:
            instance_id: Target instance ID
            message: Message to send
            wait_for_response: Whether to wait for response
            timeout_seconds: Response timeout

        Returns:
            Response data dict
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]
        if instance["state"] not in ["running", "idle"]:
            raise RuntimeError(
                f"Instance {instance_id} is not in a valid state: {instance['state']}"
            )

        # Update instance state
        instance["state"] = "busy"
        instance["last_activity"] = datetime.now(UTC).isoformat()

        # Generate message ID for tracking
        message_id = str(uuid.uuid4())
        send_timestamp = datetime.now(UTC)

        try:
            # Record message in history
            self.message_history[instance_id].append(
                {"role": "user", "content": message, "timestamp": send_timestamp.isoformat()}
            )

            # Log communication event
            if self.logging_manager:
                instance_logger = self.logging_manager.get_instance_logger(
                    instance_id, instance.get("name")
                )
                instance_logger.info(
                    f"Sending message (wait={wait_for_response}): {message[:100]}...",
                    extra={
                        "event_type": "message_sent",
                        "message_id": message_id,
                        "direction": "outbound",
                        "content": message,
                    },
                )

            # Send message via tmux
            session = self.tmux_sessions[instance_id]
            window = session.windows[0]
            pane = window.panes[0]

            # Send the message
            # Claude Code has aggressive paste detection - we need to simulate SLOW typing
            # Split into small chunks (words/chars) and send with realistic typing delays
            import time
            import subprocess

            # Strategy: Send message line-by-line with delays to simulate human typing
            # Even splitting lines is too fast - need to use tmux send-keys with literal flag
            # and disable bracketed paste

            # Disable bracketed paste mode in the pane first
            subprocess.run(['tmux', 'send-keys', '-t', session.name, '-X', 'cancel'],
                          capture_output=True)

            # Send message using send-keys with literal flag (-l) which sends character by character
            # This is slower but avoids paste detection
            result = subprocess.run(['tmux', 'send-keys', '-t', session.name, '-l', message],
                          capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"tmux send-keys failed: {result.stderr}")

            logger.debug(f"Sent {len(message)} chars to instance {instance_id} via tmux literal mode")

            # Wait a moment then send Enter
            time.sleep(0.2)
            pane.send_keys("", enter=True)

            logger.debug(f"Submitted message to instance {instance_id}")

            if not wait_for_response:
                # Still track outbound message tokens even when not waiting for response
                estimated_tokens = len(message.split())
                estimated_cost = estimated_tokens * 0.00001

                instance["total_tokens_used"] += estimated_tokens
                instance["total_cost"] += estimated_cost
                instance["request_count"] += 1

                self.total_tokens_used += estimated_tokens
                self.total_cost += estimated_cost

                return {
                    "instance_id": instance_id,
                    "status": "sent",
                    "timestamp": datetime.now(UTC).isoformat(),
                }

            # Capture baseline AFTER sending (brief delay for message to appear)
            await asyncio.sleep(0.3)
            initial_output = "\n".join(pane.cmd("capture-pane", "-p").stdout)

            # Activity-based response detection with stability monitoring
            start_time = time.time()
            last_size = len(initial_output)
            stable_count = 0
            poll_count = 0
            response_started = False

            while time.time() - start_time < timeout_seconds:
                await asyncio.sleep(0.3)  # Faster consistent polling
                poll_count += 1

                # Capture current visible pane only (not full scrollback - faster)
                current_output = "\n".join(pane.cmd("capture-pane", "-p").stdout)
                current_size = len(current_output)

                # Check if response has started (output growing)
                if current_size > last_size:
                    response_started = True
                    stable_count = 0  # Reset stability counter
                    last_size = current_size
                    continue

                # If response started and output is now stable
                if response_started:
                    stable_count += 1

                    # Declare complete after output stable for 1 second (3-4 polls at 0.3s)
                    if stable_count >= 3:
                        logger.debug(
                            f"Response complete: stable for {stable_count * 0.3:.1f}s after {time.time() - start_time:.1f}s total (poll #{poll_count})"
                        )
                        break

            if not response_started:
                logger.warning(
                    f"No response activity detected after {poll_count} polls, {time.time() - start_time:.1f}s"
                )

            logger.debug(
                f"Polling completed after {poll_count} polls, {time.time() - start_time:.1f}s"
            )

            # Now capture full scrollback for response extraction
            full_output = "\n".join(pane.cmd("capture-pane", "-p", "-S", "-").stdout)

            # Extract the actual response from the output
            response_text = self._extract_response(full_output, initial_output)

            # Add response to history
            response_timestamp = datetime.now(UTC)
            self.message_history[instance_id].append(
                {
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": response_timestamp.isoformat(),
                }
            )

            # Calculate response time
            response_time = (response_timestamp - send_timestamp).total_seconds()

            # Update usage statistics (estimates)
            estimated_tokens = len(message.split()) + len(response_text.split())
            estimated_cost = estimated_tokens * 0.00001

            instance["total_tokens_used"] += estimated_tokens
            instance["total_cost"] += estimated_cost
            instance["request_count"] += 1

            self.total_tokens_used += estimated_tokens
            self.total_cost += estimated_cost

            # Log response with structured data
            if self.logging_manager:
                instance_logger = self.logging_manager.get_instance_logger(
                    instance_id, instance.get("name")
                )
                instance_logger.info(
                    f"Received response ({len(response_text)} chars, {estimated_tokens} tokens, {response_time:.2f}s)",
                    extra={
                        "event_type": "message_received",
                        "message_id": message_id,
                        "direction": "inbound",
                        "content": response_text,
                        "tokens": estimated_tokens,
                        "cost": estimated_cost,
                        "response_time": response_time,
                    },
                )

                # Log tmux output for debugging
                self.logging_manager.log_tmux_output(instance_id, full_output)

                # Log audit event
                self.logging_manager.log_audit_event(
                    event_type="message_exchange",
                    instance_id=instance_id,
                    details={
                        "message_id": message_id,
                        "message_length": len(message),
                        "response_length": len(response_text),
                        "tokens": estimated_tokens,
                        "cost": estimated_cost,
                        "response_time_seconds": response_time,
                    },
                )

            logger.info(
                f"Received response from instance {instance_id}",
                extra={
                    "instance_id": instance_id,
                    "response_length": len(response_text),
                    "estimated_tokens": estimated_tokens,
                },
            )

            return {
                "instance_id": instance_id,
                "message_id": message_id,
                "response": response_text,
                "timestamp": response_timestamp.isoformat(),
                "tokens_used": estimated_tokens,
                "cost": estimated_cost,
            }

        except Exception as e:
            logger.error(
                f"Error sending message to instance {instance_id}: {e}",
                extra={"instance_id": instance_id, "error": str(e)},
            )
            raise
        finally:
            # Update state back to idle
            if instance["state"] == "busy":
                instance["state"] = "idle"

    async def interrupt_instance(self, instance_id: str) -> dict[str, Any]:
        """Send interrupt signal (Ctrl+C) to a running instance.

        This stops the current task without terminating the instance.
        Similar to pressing Escape or Ctrl+C in the terminal.

        Args:
            instance_id: Instance ID to interrupt

        Returns:
            Status dict with success/failure info
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        if instance["state"] not in ["running", "busy", "idle"]:
            return {
                "success": False,
                "instance_id": instance_id,
                "error": f"Instance is {instance['state']}, cannot interrupt",
                "timestamp": datetime.now(UTC).isoformat(),
            }

        try:
            # Get tmux pane
            session = self.tmux_sessions.get(instance_id)
            if not session:
                raise RuntimeError(f"No tmux session found for instance {instance_id}")

            window = session.windows[0]
            pane = window.panes[0]

            # Send Ctrl+C to interrupt the current operation
            # This works in both Claude and Codex CLI modes
            pane.send_keys("C-c", literal=False)  # Send Ctrl+C

            # Wait briefly for interrupt to take effect
            await asyncio.sleep(0.5)

            # Verify the interrupt was processed by checking output
            output = "\n".join(pane.cmd("capture-pane", "-p").stdout)
            interrupted = any(
                indicator in output.lower()
                for indicator in ["interrupt", "cancel", "stopped", "^c"]
            )

            if interrupted:
                logger.info(
                    f"Successfully interrupted instance {instance_id}",
                    extra={"instance_id": instance_id, "state": instance["state"]},
                )
            else:
                logger.warning(
                    f"Interrupt signal sent but no confirmation detected for instance {instance_id}",
                    extra={"instance_id": instance_id},
                )

            # Update state
            instance["state"] = "idle"
            instance["last_activity"] = datetime.now(UTC).isoformat()

            return {
                "success": True,
                "instance_id": instance_id,
                "message": "Interrupt signal sent successfully",
                "confirmed": interrupted,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.error(
                f"Failed to interrupt instance {instance_id}: {e}",
                extra={"instance_id": instance_id, "error": str(e)},
            )
            return {
                "success": False,
                "instance_id": instance_id,
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            }

    async def terminate_instance(self, instance_id: str, force: bool = False) -> bool:
        """Terminate a Claude instance and kill its tmux session.

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
            logger.warning(
                f"Cannot terminate busy instance {instance_id} without force=True",
                extra={"instance_id": instance_id},
            )
            return False

        # First, terminate all child instances (cascade)
        children_to_terminate = [
            child_id
            for child_id, child_instance in self.instances.items()
            if child_instance.get("parent_instance_id") == instance_id
            and child_instance.get("state") != "terminated"
        ]

        if children_to_terminate:
            logger.info(
                f"Cascade terminating {len(children_to_terminate)} child instances of {instance_id}",
                extra={"instance_id": instance_id, "children": children_to_terminate}
            )
            for child_id in children_to_terminate:
                try:
                    await self.terminate_instance(child_id, force=True)
                except Exception as e:
                    logger.error(
                        f"Failed to terminate child instance {child_id}: {e}",
                        extra={"parent_id": instance_id, "child_id": child_id}
                    )

        try:
            # Kill tmux session
            if instance_id in self.tmux_sessions:
                session = self.tmux_sessions[instance_id]
                session_name = f"madrox-{instance_id}"
                try:
                    session.kill_session()
                    logger.info(f"Killed tmux session: {session_name}")
                except Exception as e:
                    logger.warning(f"Failed to kill tmux session {session_name}: {e}")
                del self.tmux_sessions[instance_id]

            # Update instance state
            instance["state"] = "terminated"
            instance["terminated_at"] = datetime.now(UTC).isoformat()

            # Clean up workspace
            workspace_dir = Path(instance["workspace_dir"])
            if workspace_dir.exists():
                try:
                    import shutil

                    shutil.rmtree(workspace_dir)
                    logger.debug(f"Cleaned up workspace for instance {instance_id}")
                except Exception as e:
                    logger.warning(f"Failed to clean up workspace for {instance_id}: {e}")

            # Remove message history
            if instance_id in self.message_history:
                del self.message_history[instance_id]

            # Log termination
            if self.logging_manager:
                instance_logger = self.logging_manager.get_instance_logger(
                    instance_id, instance.get("name")
                )
                instance_logger.info(
                    f"Instance terminated (force={force})",
                    extra={
                        "total_requests": instance.get("request_count", 0),
                        "total_tokens": instance.get("total_tokens_used", 0),
                        "total_cost": instance.get("total_cost", 0.0),
                    },
                )

                # Log audit event
                self.logging_manager.log_audit_event(
                    event_type="instance_terminate",
                    instance_id=instance_id,
                    details={
                        "instance_name": instance.get("name"),
                        "force": force,
                        "final_state": "terminated",
                        "total_requests": instance.get("request_count", 0),
                        "total_tokens": instance.get("total_tokens_used", 0),
                        "total_cost": instance.get("total_cost", 0.0),
                        "uptime_seconds": (
                            datetime.now(UTC)
                            - datetime.fromisoformat(instance["created_at"])
                        ).total_seconds(),
                    },
                )

            logger.info(
                f"Successfully terminated instance {instance_id}",
                extra={"instance_id": instance_id},
            )
            return True

        except Exception as e:
            logger.error(
                f"Error terminating instance {instance_id}: {e}",
                extra={"instance_id": instance_id, "error": str(e)},
            )
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

    async def _initialize_tmux_session(self, instance_id: str):
        """Initialize a tmux session for the instance."""
        instance = self.instances[instance_id]
        workspace_dir = instance["workspace_dir"]
        instance_type = instance.get("instance_type", "claude")
        session_name = f"madrox-{instance_id}"

        logger.debug(f"Creating tmux session: {session_name}")

        # Kill existing session if any
        try:
            existing = self.tmux_server.find_where({"session_name": session_name})
            if existing:
                existing.kill_session()
                logger.debug(f"Killed existing session: {session_name}")
        except Exception:
            pass

        # Create new session
        try:
            session = self.tmux_server.new_session(
                session_name=session_name,
                window_name=instance_type,
                start_directory=workspace_dir,
                x=160,
                y=50,
            )
        except Exception as e:
            logger.error(f"Failed to create tmux session: {e}")
            raise

        # Store session reference
        self.tmux_sessions[instance_id] = session

        # Get the pane
        window = session.windows[0]
        pane = window.panes[0]

        # Build CLI command based on instance type
        if instance_type == "codex":
            cmd_parts = ["codex"]

            # Add sandbox mode if specified
            if sandbox_mode := instance.get("sandbox_mode"):
                cmd_parts.extend(["--sandbox", sandbox_mode])

            # Add profile if specified
            if profile := instance.get("profile"):
                cmd_parts.extend(["--profile", profile])

            # Add model if specified
            if model := instance.get("model"):
                cmd_parts.extend(["--model", model])
        else:
            # Claude CLI command
            cmd_parts = [
                "claude",
                "--permission-mode",
                "bypassPermissions",
                "--dangerously-skip-permissions",
            ]

            # Add model if specified
            if model := instance.get("model"):
                cmd_parts.extend(["--model", model])

        # Start CLI
        cmd = " ".join(cmd_parts)
        pane.send_keys(cmd, enter=True)
        logger.debug(f"Started {instance_type} CLI in tmux session: {cmd}")

        # Adaptive wait - poll until CLI is ready
        max_init_wait = 30
        init_start = time.time()
        cli_ready = False

        while time.time() - init_start < max_init_wait:
            await asyncio.sleep(0.5)
            output = "\n".join(pane.cmd("capture-pane", "-p").stdout)

            # Detect ready state by checking for interactive indicators
            # Claude CLI shows various prompts, Codex shows ready state
            if instance_type == "codex":
                # Codex ready when it shows prompt or waits for input
                if any(indicator in output for indicator in ["codex>", "Working on:", "Thinking..."]):
                    cli_ready = True
                    break
            else:
                # Claude ready when it shows response or is waiting for input
                # Look for thinking indicators or response completion
                if any(indicator in output for indicator in ["Thinking", "⏺", ">", "│"]):
                    cli_ready = True
                    break

        if not cli_ready:
            logger.warning(
                f"CLI initialization may not be complete after {time.time() - init_start:.1f}s, proceeding anyway"
            )
        else:
            logger.debug(f"CLI initialized in {time.time() - init_start:.1f}s")

        # Handle initial prompts based on instance type
        if instance_type == "codex":
            # For Codex, send initial_prompt if provided
            if initial_prompt := instance.get("initial_prompt"):
                pane.send_keys(initial_prompt, enter=True)
                logger.debug("Sent initial prompt to Codex instance")
                await asyncio.sleep(5)
        else:
            # For Claude, send system prompt as before
            system_prompt = instance.get("system_prompt")
            if system_prompt:
                # Send context as first message
                workspace_path = instance["workspace_dir"]
                has_custom_prompt = instance.get("has_custom_prompt", False)

                prompt_prefix = (
                    "" if has_custom_prompt else "You are a specialized Claude instance. "
                )

                # Add instance ID information for parent communication
                instance_id_info = (
                    f"\n\nYour instance ID: {instance['id']}\n"
                    f"This ID is also stored in {workspace_path}/.madrox_instance_id\n"
                )

                if instance.get("parent_instance_id"):
                    parent_info = (
                        f"Your parent instance ID: {instance['parent_instance_id']}\n"
                        f"You can send messages to your parent using: send_to_instance(parent_instance_id='{instance['parent_instance_id']}', message='your message')\n"
                    )
                    instance_id_info += parent_info

                # Add instructions for spawning children with parent tracking
                if instance.get("enable_madrox"):
                    spawn_info = (
                        f"\nWhen spawning child instances, pass your instance_id as parent_instance_id:\n"
                        f"  spawn_claude(name='child', role='general', parent_instance_id='{instance['id']}')\n"
                        f"This enables bidirectional communication between parent and child.\n\n"
                        f"HIERARCHICAL MESSAGE PASSING PATTERN:\n"
                        f"- Children send messages to you (their parent) using: send_to_instance(parent_instance_id='{instance['id']}', message='...')\n"
                        f"- You coordinate and decide how to route messages between children\n"
                        f"- Use get_children(parent_id='{instance['id']}') to see all your children\n"
                        f"- Use broadcast_to_children(parent_id='{instance['id']}', message='...') to message all children\n"
                        f"- You control what information (IDs, tasks) flows up to your parent or down to your children"
                    )
                    instance_id_info += spawn_info

                if instance.get("bypass_isolation", False):
                    workspace_info = (
                        f"\n\nIMPORTANT: You have FULL FILESYSTEM ACCESS. You can read and write files anywhere.\n"
                        f"Your workspace directory is at: {workspace_path}\n"
                        f"You can write files to any absolute path."
                        f"{instance_id_info}"
                    )
                else:
                    workspace_info = (
                        f"\n\nIMPORTANT: You have a workspace directory at: {workspace_path}\n"
                        f"You can read and write files within this directory. When asked to write files, "
                        f"write them to your workspace directory unless specifically asked to write elsewhere."
                        f"{instance_id_info}"
                    )

                full_prompt = f"{prompt_prefix}{system_prompt}{workspace_info if not has_custom_prompt else ''}"
                pane.send_keys(full_prompt, enter=True)
                logger.debug("Sent initial system prompt to Claude instance")

                # Wait for initial response
                await asyncio.sleep(5)

        logger.info(f"Tmux session initialized for {instance_type} instance {instance_id}")

    def _extract_response(self, full_output: str, initial_output: str) -> str:
        """Extract the actual Claude response from tmux output.

        Strips the interactive UI chrome (borders, status bars, etc.) to get the content.

        Args:
            full_output: Full output from pane
            initial_output: Initial output before message was sent

        Returns:
            Cleaned response text
        """
        # Split into lines
        lines = full_output.split("\n")

        # Filter out UI chrome
        content_lines = []
        for line in lines:
            # Skip UI borders and decorations
            if line.strip().startswith("╭") or line.strip().startswith("╰"):
                continue
            if line.strip().startswith("│") and line.strip().endswith("│"):
                # Extract content between borders
                content = line.strip()[1:-1].strip()
                if content:
                    content_lines.append(content)
                continue
            # Skip status bars (token usage, etc.)
            if "%" in line and ("tokens" in line.lower() or "usage" in line.lower()):
                continue
            # Skip empty lines at start/end
            if not line.strip():
                continue

            content_lines.append(line)

        # Join and clean up
        response = "\n".join(content_lines)

        # Remove our sent message from the response (it echoes back)
        # Find the last user message in history
        if self.message_history.get(list(self.instances.keys())[0]):
            last_messages = [
                msg["content"]
                for msg in self.message_history[list(self.instances.keys())[0]]
                if msg["role"] == "user"
            ]
            if last_messages:
                last_msg = last_messages[-1]
                # Remove the echoed message
                response = response.replace(last_msg, "").strip()

        # Clean up extra whitespace
        response = re.sub(r"\n{3,}", "\n\n", response)

        return response.strip()

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

    async def check_pane_health(self, instance_id: str) -> dict[str, Any]:
        """Check if tmux pane and underlying process are healthy.

        Args:
            instance_id: Instance ID to check

        Returns:
            Health status dict with details
        """
        if instance_id not in self.instances:
            return {
                "healthy": False,
                "instance_id": instance_id,
                "error": "Instance not found",
            }

        if instance_id not in self.tmux_sessions:
            return {
                "healthy": False,
                "instance_id": instance_id,
                "error": "No tmux session found",
            }

        try:
            session = self.tmux_sessions[instance_id]
            window = session.windows[0]
            pane = window.panes[0]

            # Check if pane is still active
            pane_info = pane.cmd("display-message", "-p", "#{pane_active}")
            is_active = pane_info.stdout[0].strip() == "1"

            if not is_active:
                logger.warning(f"Pane for instance {instance_id} is not active")
                return {
                    "healthy": False,
                    "instance_id": instance_id,
                    "error": "Pane is not active",
                }

            # Check if underlying process is alive
            pane_pid_result = pane.cmd("display-message", "-p", "#{pane_pid}")
            if not pane_pid_result.stdout:
                return {
                    "healthy": False,
                    "instance_id": instance_id,
                    "error": "Could not get pane PID",
                }

            pid = int(pane_pid_result.stdout[0].strip())

            # Check process existence using psutil
            try:
                import psutil

                if not psutil.pid_exists(pid):
                    logger.error(f"Process {pid} for instance {instance_id} no longer exists")
                    return {
                        "healthy": False,
                        "instance_id": instance_id,
                        "error": f"Process {pid} no longer exists",
                    }

                # Get process info for additional diagnostics
                proc = psutil.Process(pid)
                proc_status = proc.status()

                return {
                    "healthy": True,
                    "instance_id": instance_id,
                    "pane_active": is_active,
                    "process_id": pid,
                    "process_status": proc_status,
                }

            except ImportError:
                # Fallback: check if PID exists using os.kill with signal 0
                import os

                try:
                    os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
                    return {
                        "healthy": True,
                        "instance_id": instance_id,
                        "pane_active": is_active,
                        "process_id": pid,
                        "process_status": "unknown (psutil not available)",
                    }
                except OSError:
                    logger.error(f"Process {pid} for instance {instance_id} no longer exists")
                    return {
                        "healthy": False,
                        "instance_id": instance_id,
                        "error": f"Process {pid} no longer exists",
                    }

        except Exception as e:
            logger.error(f"Health check failed for instance {instance_id}: {e}")
            return {
                "healthy": False,
                "instance_id": instance_id,
                "error": str(e),
            }
