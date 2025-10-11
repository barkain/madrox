"""Tmux-based Instance Manager for Claude Orchestrator.

Manages Claude CLI instances via tmux sessions for persistent interactive communication.
"""

import asyncio
import logging
import re
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import libtmux

from .name_generator import get_instance_name
from .simple_models import MessageEnvelope

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

        # Bidirectional messaging queues (in-memory, lightweight)
        self.response_queues: dict[str, asyncio.Queue] = {}
        self.message_registry: dict[str, MessageEnvelope] = {}
        self.main_message_inbox: list[dict[str, Any]] = []
        self.main_instance_id: str | None = None

        # Resource tracking
        self.total_tokens_used = 0
        self.total_cost = 0.0

        # Create workspace base directory
        self.workspace_base = Path(config.get("workspace_base_dir", "/tmp/claude_orchestrator"))
        self.workspace_base.mkdir(parents=True, exist_ok=True)

        # Connect to tmux server
        self.tmux_server = libtmux.Server()
        logger.info("Connected to tmux server")

        # Store server port for MCP config generation
        import os

        self.server_port = int(os.getenv("ORCHESTRATOR_PORT", "8001"))

    def _configure_mcp_servers(self, pane, instance: dict[str, Any]):
        """Configure MCP servers in the tmux session before spawning Claude/Codex CLI.

        For Claude: Creates a JSON config file and uses --mcp-config flag
        For Codex: Runs `codex mcp add` commands in the tmux pane

        Args:
            pane: libtmux pane object
            instance: Instance metadata dict
        """
        import json
        import time

        workspace_dir = Path(instance["workspace_dir"])
        mcp_servers = instance.get("mcp_servers", {})
        instance_type = instance.get("instance_type", "claude")

        # Handle case where mcp_servers might be a JSON string (from MCP protocol)
        if isinstance(mcp_servers, str):
            try:
                import json

                mcp_servers = json.loads(mcp_servers)
                # Update instance dict with parsed value
                instance["mcp_servers"] = mcp_servers
            except json.JSONDecodeError:
                logger.error(f"Invalid mcp_servers JSON string: {mcp_servers}")
                mcp_servers = {}

        # Ensure mcp_servers is a dict
        if not isinstance(mcp_servers, dict):
            logger.error(f"mcp_servers is not a dict: {type(mcp_servers)}, value: {mcp_servers}")
            mcp_servers = {}

        # Auto-add Madrox if enable_madrox=True and not explicitly configured
        if instance.get("enable_madrox") and "madrox" not in mcp_servers:
            mcp_servers["madrox"] = {
                "transport": "http",
                "url": f"http://localhost:{self.server_port}/mcp",
            }

        # Handle Codex instances differently - use `codex mcp add` commands
        if instance_type == "codex":
            if not mcp_servers:
                logger.debug(f"No MCP servers to configure for Codex instance {instance['id']}")
                return

            logger.info(
                f"Configuring {len(mcp_servers)} MCP servers for Codex instance {instance['id']}"
            )

            for server_name, server_config in mcp_servers.items():
                try:
                    has_command = "command" in server_config
                    transport = server_config.get("transport", "stdio" if has_command else "http")

                    if transport == "stdio":
                        command = server_config.get("command")
                        if not command:
                            logger.warning(
                                f"Skipping MCP server '{server_name}' - no command provided"
                            )
                            continue

                        args = server_config.get("args", [])
                        if not isinstance(args, list):
                            args = [args] if args else []

                        # Build codex mcp add command
                        codex_cmd_parts = ["codex", "mcp", "add", server_name, command] + args

                        # Add environment variables if specified
                        env_vars = server_config.get("env", {})
                        for key, value in env_vars.items():
                            codex_cmd_parts.extend(["--env", f"{key}={value}"])

                        codex_cmd = " ".join(codex_cmd_parts)
                        logger.info(f"Adding Codex MCP server: {codex_cmd}")

                        pane.send_keys(codex_cmd, enter=True)
                        time.sleep(0.5)  # Wait for command to complete

                    elif transport == "http":
                        logger.warning(
                            f"Codex does not support HTTP MCP servers yet ('{server_name}'), skipping"
                        )
                        continue

                except Exception as e:
                    logger.error(
                        f"Error configuring Codex MCP server '{server_name}': {e}", exc_info=True
                    )
                    raise

            logger.info(f"Configured MCP servers for Codex instance {instance['id']}")
            return  # Codex doesn't use _mcp_config_path

        # Handle Claude instances - create JSON config file
        mcp_config_path = workspace_dir / ".claude_mcp_config.json"
        mcp_config = {"mcpServers": {}}

        # Build config from mcp_servers parameter
        for server_name, server_config in mcp_servers.items():
            # Auto-detect transport type:
            # - If "command" is present, default to "stdio"
            # - Otherwise default to "http"
            has_command = "command" in server_config
            transport = server_config.get("transport", "stdio" if has_command else "http")

            if transport == "http":
                url = server_config.get("url")
                if not url:
                    logger.warning(
                        f"Skipping MCP server '{server_name}' - no URL provided for http transport"
                    )
                    continue

                mcp_config["mcpServers"][server_name] = {
                    "type": "http",  # Claude Code uses "type" not "transport"
                    "url": url,
                }

            elif transport == "stdio":
                command = server_config.get("command")
                if not command:
                    logger.warning(
                        f"Skipping MCP server '{server_name}' - no command provided for stdio transport"
                    )
                    continue

                args = server_config.get("args", [])
                # Claude Code expects stdio servers WITHOUT a "type" field
                # It infers stdio from the presence of "command"
                mcp_config["mcpServers"][server_name] = {
                    "command": command,
                    "args": args if isinstance(args, list) else [args],
                }

            else:
                logger.warning(
                    f"Skipping MCP server '{server_name}' - unsupported transport '{transport}'"
                )
                continue

        # Write config file
        mcp_config_path.write_text(json.dumps(mcp_config, indent=2))
        logger.info(
            f"Created MCP config for instance {instance['id']}: {len(mcp_config['mcpServers'])} servers"
        )

        # Store the config path so we can use --mcp-config flag when starting Claude
        instance["_mcp_config_path"] = str(mcp_config_path)

    async def spawn_instance(
        self,
        name: str | None = None,
        role: str = "general",
        system_prompt: str | None = None,
        model: str | None = None,
        bypass_isolation: bool = True,
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
            "mcp_servers": kwargs.get("mcp_servers", {}),
            "statusline": "",
            "error_message": None,
            "retry_count": 0,
        }

        self.instances[instance_id] = instance
        self.message_history[instance_id] = []

        # Initialize response queue for this instance immediately at spawn
        # This ensures the instance can receive replies from children even before sending messages
        self.response_queues[instance_id] = asyncio.Queue()

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
                    exc_info=True,  # This will print the full stack trace
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

            # Create message envelope for bidirectional tracking
            envelope = MessageEnvelope(
                message_id=message_id,
                sender_id="coordinator",  # Or parent instance ID if applicable
                recipient_id=instance_id,
                content=message,
                sent_at=send_timestamp,
            )
            self.message_registry[message_id] = envelope

            # Initialize response queue for this instance if needed
            if instance_id not in self.response_queues:
                self.response_queues[instance_id] = asyncio.Queue()

            # Check if system prompt is pending (first message after spawn)
            if instance.get("_system_prompt_pending"):
                logger.info(
                    f"Sending pending system prompt with first message to instance {instance_id}"
                )
                # Get the pending system prompt
                system_prompt = instance.get("_pending_system_prompt", "")

                # Send system prompt first (without correlation ID)
                session = self.tmux_sessions[instance_id]
                window = session.windows[0]
                pane = window.panes[0]

                if system_prompt:
                    self._send_multiline_message_to_pane(pane, system_prompt)
                    logger.debug("Sent pending system prompt")

                    # Wait for Claude to process system prompt
                    await asyncio.sleep(8)

                # Clear the pending flag
                instance["_system_prompt_pending"] = False
                instance.pop("_pending_system_prompt", None)

            # Format message with correlation ID for bidirectional tracking
            formatted_message = f"[MSG:{message_id}] {message}"

            # Send message via tmux
            session = self.tmux_sessions[instance_id]
            window = session.windows[0]
            pane = window.panes[0]

            # Use new multiline-safe method
            self._send_multiline_message_to_pane(pane, formatted_message)
            envelope.mark_delivered()

            logger.debug(f"Sent message {message_id} to instance {instance_id}")

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
                    "message_id": message_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }

            # BIDIRECTIONAL MESSAGING: Check response queue first
            # Instance may use reply_to_caller tool for explicit response
            try:
                queue_response = await asyncio.wait_for(
                    self.response_queues[instance_id].get(), timeout=timeout_seconds
                )
                # Got explicit reply via bidirectional protocol
                response_text = queue_response["reply_message"]
                logger.info(f"Received bidirectional reply from instance {instance_id}")

                # Mark envelope as replied
                envelope.mark_replied(response_text)

                # Update stats and return
                response_timestamp = datetime.now(UTC)
                response_time = (response_timestamp - send_timestamp).total_seconds()

                estimated_tokens = len(message.split()) + len(response_text.split())
                estimated_cost = estimated_tokens * 0.00001

                instance["total_tokens_used"] += estimated_tokens
                instance["total_cost"] += estimated_cost
                instance["request_count"] += 1

                self.total_tokens_used += estimated_tokens
                self.total_cost += estimated_cost

                # Add to message history
                self.message_history[instance_id].append(
                    {
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": response_timestamp.isoformat(),
                    }
                )

                # Log the response
                if self.logging_manager:
                    instance_logger = self.logging_manager.get_instance_logger(
                        instance_id, instance.get("name")
                    )
                    instance_logger.info(
                        f"Received bidirectional response ({len(response_text)} chars, {response_time:.2f}s)",
                        extra={
                            "event_type": "bidirectional_reply_received",
                            "message_id": message_id,
                            "direction": "inbound",
                            "content": response_text,
                            "correlation_id": queue_response.get("correlation_id"),
                        },
                    )

                instance["state"] = "idle"
                return {
                    "instance_id": instance_id,
                    "response": response_text,
                    "message_id": message_id,
                    "response_time": response_time,
                    "estimated_tokens": estimated_tokens,
                    "protocol": "bidirectional",
                    "timestamp": response_timestamp.isoformat(),
                }

            except TimeoutError:
                # No explicit reply via bidirectional protocol, fall back to pane polling
                logger.debug("No bidirectional reply received, falling back to pane polling")
                envelope.mark_timeout()

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

                # NOTE: Claude CLI in interactive mode uses rich terminal UI, not JSON
                # Tool event capture via JSON parsing is not possible in interactive tmux sessions
                # Users should use get_tmux_pane_content() for detailed terminal output inspection

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
                "protocol": "polling_fallback",  # Legacy polling method
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
                extra={"instance_id": instance_id, "children": children_to_terminate},
            )
            for child_id in children_to_terminate:
                try:
                    await self.terminate_instance(child_id, force=True)
                except Exception as e:
                    logger.error(
                        f"Failed to terminate child instance {child_id}: {e}",
                        extra={"parent_id": instance_id, "child_id": child_id},
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
                            datetime.now(UTC) - datetime.fromisoformat(instance["created_at"])
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

        # Configure MCP servers before spawning CLI
        self._configure_mcp_servers(pane, instance)

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
            # Claude CLI command (interactive mode)
            # NOTE: --output-format stream-json only works with --print (non-interactive)
            # For interactive tmux sessions, we must parse the terminal output directly
            cmd_parts = [
                "claude",
                "--permission-mode",
                "bypassPermissions",
                "--dangerously-skip-permissions",
            ]

            # Add MCP config if configured
            if mcp_config_path := instance.get("_mcp_config_path"):
                cmd_parts.extend(["--mcp-config", mcp_config_path])

            # Prevent inheriting custom statusline from parent's ~/.claude/settings.json
            # Only load 'local' and 'project' settings, skip 'user' settings
            cmd_parts.extend(["--setting-sources", "local,project"])

            # Add model if specified
            if model := instance.get("model"):
                cmd_parts.extend(["--model", model])

        # Start CLI
        cmd = " ".join(cmd_parts)
        pane.send_keys(cmd, enter=True)
        logger.debug(f"Started {instance_type} CLI in tmux session: {cmd}")

        # Adaptive wait - poll until CLI is ready
        # MCP configuration can take 45+ seconds to load
        max_init_wait = 60  # Increased from 30 to handle MCP server loading
        init_start = time.time()
        cli_ready = False

        while time.time() - init_start < max_init_wait:
            await asyncio.sleep(1)  # Check every second
            output = "\n".join(pane.cmd("capture-pane", "-p").stdout)

            # Detect ready state by checking for interactive indicators
            # Claude CLI shows various prompts, Codex shows ready state
            if instance_type == "codex":
                # Codex ready when it shows prompt or waits for input
                if any(
                    indicator in output for indicator in ["codex>", "Working on:", "Thinking..."]
                ):
                    cli_ready = True
                    break
            else:
                # Claude ready when it shows "What would you like" or similar ready prompt
                # CRITICAL: Must see the actual ready message, not just initialization output
                if any(
                    indicator in output
                    for indicator in [
                        "What would you like",  # Standard ready prompt
                        "How can I help",  # Alternative ready prompt
                        "ready to assist",  # Another variant
                    ]
                ):
                    cli_ready = True
                    logger.debug("Claude CLI ready - detected ready prompt")
                    break

        if not cli_ready:
            logger.warning(
                f"CLI initialization may not be complete after {time.time() - init_start:.1f}s, proceeding anyway"
            )
        else:
            logger.debug(f"CLI initialized in {time.time() - init_start:.1f}s")

        # CRITICAL: Additional safety wait to ensure CLI is FULLY ready for multiline input
        # Even after showing ready prompt, Claude needs time to be ready for C-j sequences
        if instance_type != "codex":
            logger.debug("Additional safety wait for multiline input readiness...")
            await asyncio.sleep(3)  # Extra 3 seconds after ready detection
            logger.debug("Ready for multiline input")

        # Handle initial prompts based on instance type
        if instance_type == "codex":
            # For Codex, send initial_prompt if provided
            if initial_prompt := instance.get("initial_prompt"):
                pane.send_keys(initial_prompt, enter=True)
                logger.debug("Sent initial prompt to Codex instance")
                await asyncio.sleep(5)
        else:
            # For Claude, DEFER system prompt until first message
            # This ensures Claude is fully ready and avoids shell execution
            system_prompt = instance.get("system_prompt")
            if system_prompt:
                logger.debug("System prompt will be sent with first user message")
                # Flag that system prompt is pending
                instance["_system_prompt_pending"] = True

                # BUILD the system prompt now for later use
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
                        f"- You control what information (IDs, tasks) flows up to your parent or down to your children\n\n"
                        f"BIDIRECTIONAL MESSAGING PROTOCOL:\n"
                        f"When you receive messages from the coordinator or parent instance, they will be formatted as:\n"
                        f"  [MSG:correlation-id] message content here\n\n"
                        f"To respond efficiently using the bidirectional protocol, use the reply_to_caller tool:\n"
                        f"  reply_to_caller(\n"
                        f"    instance_id='{instance['id']}',\n"
                        f"    reply_message='your response here',\n"
                        f"    correlation_id='correlation-id-from-message'\n"
                        f"  )\n\n"
                        f"Benefits of using reply_to_caller:\n"
                        f"- Instant delivery (no polling delay)\n"
                        f"- Proper request-response correlation\n"
                        f"- More efficient than text output\n\n"
                        f"If you don't use reply_to_caller, the system will fall back to polling your output (slower but works)."
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

                # ALWAYS append bidirectional messaging instructions (even for custom prompts)
                bidirectional_instructions = ""
                if instance.get("enable_madrox"):
                    bidirectional_instructions = (
                        f"\n\n{'─' * 80}\n"
                        f"BIDIRECTIONAL MESSAGING PROTOCOL (REQUIRED):\n"
                        f"When you receive messages formatted as [MSG:correlation-id] content,\n"
                        f"you MUST respond using the reply_to_caller tool:\n\n"
                        f"  reply_to_caller(\n"
                        f"    instance_id='{instance['id']}',\n"
                        f"    reply_message='your response here',\n"
                        f"    correlation_id='correlation-id-from-message'\n"
                        f"  )\n\n"
                        f"IMPORTANT: Always use reply_to_caller for every response to messages.\n"
                        f"This enables instant bidirectional communication and proper correlation.\n"
                        f"{'─' * 80}\n"
                    )

                full_prompt = f"{prompt_prefix}{system_prompt}{workspace_info if not has_custom_prompt else ''}{bidirectional_instructions}"

                # Store the system prompt for later (send with first message)
                instance["_pending_system_prompt"] = full_prompt
                logger.debug("System prompt stored for sending with first user message")

        logger.info(f"Tmux session initialized for {instance_type} instance {instance_id}")

    def _send_multiline_message_to_pane(self, pane, message: str) -> None:
        """Send multiline message to tmux pane without getting stuck.

        Properly handles newlines by sending them line-by-line with C-j (newline without submit).
        Final Enter submits the entire message.

        Args:
            pane: libtmux pane object
            message: Message content (may contain newlines)
        """
        import time

        lines = message.split("\n")
        total_lines = len(lines)

        # Send each line with C-j between them (newline without submit)
        for i, line in enumerate(lines):
            # Send the line content
            if line:  # Only send non-empty lines
                pane.send_keys(line, enter=False, literal=True)

            # Add newline between lines (not after last line)
            if i < total_lines - 1:
                pane.send_keys("C-j", enter=False, literal=False)
                time.sleep(0.01)  # Small delay to avoid paste detection

        # Final Enter to submit
        time.sleep(0.05)
        pane.send_keys("", enter=True)

        logger.debug(f"Sent multiline message ({len(message)} chars, {total_lines} lines)")

    async def handle_reply_to_caller(
        self,
        instance_id: str,
        reply_message: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Handle reply from instance back to its caller.

        This implements the bidirectional messaging protocol by queuing the reply
        in the appropriate response queue.

        Args:
            instance_id: ID of instance sending the reply
            reply_message: Content of the reply
            correlation_id: Optional message ID for correlation

        Returns:
            Dict with success status and delivery info
        """
        try:
            instance = self.instances.get(instance_id)
            if not instance:
                return {"success": False, "error": f"Instance {instance_id} not found"}

            # Determine the caller (parent instance or coordinator)
            parent_id = instance.get("parent_instance_id")
            delivered_to = parent_id if parent_id else "coordinator"

            # If there's a correlation_id, update the message envelope
            if correlation_id and correlation_id in self.message_registry:
                envelope = self.message_registry[correlation_id]
                envelope.mark_replied(reply_message, datetime.now())
                logger.debug(f"Correlated reply to message {correlation_id}")

            # Queue the reply in the caller's response queue
            if parent_id and parent_id in self.response_queues:
                await self.response_queues[parent_id].put(
                    {
                        "sender_id": instance_id,
                        "reply_message": reply_message,
                        "correlation_id": correlation_id,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                logger.info(f"Reply queued for parent instance {parent_id}")
            elif not parent_id:
                # Reply to coordinator - use special coordinator queue
                if "coordinator" not in self.response_queues:
                    self.response_queues["coordinator"] = asyncio.Queue()
                await self.response_queues["coordinator"].put(
                    {
                        "sender_id": instance_id,
                        "reply_message": reply_message,
                        "correlation_id": correlation_id,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                logger.info("Reply queued for coordinator")

            # Log the communication
            if self.logging_manager:
                self.logging_manager.log_communication(
                    instance_id=instance_id,
                    direction="outbound",
                    message_type="reply",
                    content=reply_message[:200],
                    parent_id=parent_id,
                )

            return {
                "success": True,
                "delivered_to": delivered_to,
                "correlation_id": correlation_id,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error handling reply from {instance_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_event_statistics(self, instance_id: str) -> dict[str, Any]:
        """Get statistics about captured events for an instance.

        NOTE: Only user and assistant messages are captured. Tool call events
        are not available in interactive Claude CLI mode. Use get_tmux_pane_content()
        for detailed terminal output that includes tool execution details.

        Args:
            instance_id: Instance ID to get statistics for

        Returns:
            Dict with event counts (tool_calls/tool_results will always be 0)
        """
        if instance_id not in self.message_history:
            return {
                "instance_id": instance_id,
                "error": "Instance not found",
                "total_events": 0,
            }

        history = self.message_history[instance_id]

        # Count events by role/type
        # NOTE: tool_calls and tool_results will always be 0 in interactive mode
        event_counts = {
            "user_messages": 0,
            "assistant_messages": 0,
            "tool_calls": 0,  # Always 0 - interactive mode doesn't emit JSON events
            "tool_results": 0,  # Always 0 - interactive mode doesn't emit JSON events
            "total_events": len(history),
        }

        for event in history:
            role = event.get("role")

            if role == "user":
                event_counts["user_messages"] += 1
            elif role == "assistant":
                event_counts["assistant_messages"] += 1

        return {
            "instance_id": instance_id,
            "event_counts": event_counts,
            "tools_used": {},  # Empty - tool tracking not available
            "total_events": len(history),
        }

    # REMOVED: _parse_cli_output method
    # Claude CLI in interactive mode (used for tmux sessions) does not emit JSON output.
    # --output-format stream-json ONLY works with --print (non-interactive mode).
    # Interactive sessions use rich terminal UI which cannot be parsed as structured JSON.
    # For detailed output inspection, use get_tmux_pane_content() to capture raw terminal output.

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
    async def get_audit_logs(self, since: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
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

    def get_and_clear_main_inbox(self) -> list[dict[str, Any]]:
        """Get all pending main messages and clear the inbox.

        Returns:
            List of pending messages sent to main instance
        """
        messages = self.main_message_inbox.copy()
        self.main_message_inbox.clear()
        return messages

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
            session = self.tmux_sessions.get(instance_id)
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

    async def send_to_instance(
        self,
        instance_id: str,
        message: str,
        wait_for_response: bool = True,
        timeout_seconds: int = 30,
        priority: int = 0,
    ) -> dict[str, Any] | None:
        """Send a message to a Claude or Codex instance (alias for send_message).

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
        return await self.send_message(
            instance_id=instance_id,
            message=message,
            wait_for_response=wait_for_response,
            timeout_seconds=timeout_seconds,
        )
