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

    def __init__(self, config: dict[str, Any]):
        """Initialize the tmux instance manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.instances: dict[str, dict[str, Any]] = {}
        self.tmux_sessions: dict[str, libtmux.Session] = {}
        self.message_history: dict[str, list[dict]] = {}

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
        enable_madrox: bool = False,
        **kwargs,
    ) -> str:
        """Spawn a new Claude instance in a tmux session.

        Args:
            name: Human-readable name for the instance
            role: Predefined role (general, frontend_developer, etc.)
            system_prompt: Custom system prompt
            model: Claude model to use (None = use CLI default)
            bypass_isolation: Allow full filesystem access
            enable_madrox: Enable madrox MCP server tools
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

        # Start the tmux session
        try:
            await self._initialize_tmux_session(instance_id)
            instance["state"] = "running"
            logger.info(
                f"Successfully spawned Claude instance {instance_id} ({instance_name}) with role {role} via tmux",
                extra={"instance_id": instance_id, "role": role, "name": instance_name},
            )
        except Exception as e:
            instance["state"] = "error"
            instance["error_message"] = str(e)
            logger.error(
                f"Failed to initialize tmux instance {instance_id}: {e}",
                extra={"instance_id": instance_id, "error": str(e)},
            )
            raise

        return instance_id

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

        try:
            # Record message in history
            self.message_history[instance_id].append(
                {"role": "user", "content": message, "timestamp": datetime.now(UTC).isoformat()}
            )

            # Send message via tmux
            session = self.tmux_sessions[instance_id]
            window = session.windows[0]
            pane = window.panes[0]

            # Send the message
            pane.send_keys(message, enter=True)
            logger.debug(f"Sent message to instance {instance_id} via tmux")

            if not wait_for_response:
                return {
                    "instance_id": instance_id,
                    "status": "sent",
                    "timestamp": datetime.now(UTC).isoformat(),
                }

            # Wait for response with timeout
            start_time = time.time()
            initial_output = "\n".join(pane.cmd("capture-pane", "-p").stdout)

            # Wait for Claude to process (token usage indicator changes)
            await asyncio.sleep(timeout_seconds)

            # Capture full scrollback history
            full_output = "\n".join(pane.cmd("capture-pane", "-p", "-S", "-").stdout)

            # Extract the actual response from the output
            response_text = self._extract_response(full_output, initial_output)

            # Add response to history
            self.message_history[instance_id].append(
                {
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

            # Update usage statistics (estimates)
            estimated_tokens = len(message.split()) + len(response_text.split())
            estimated_cost = estimated_tokens * 0.00001

            instance["total_tokens_used"] += estimated_tokens
            instance["total_cost"] += estimated_cost
            instance["request_count"] += 1

            self.total_tokens_used += estimated_tokens
            self.total_cost += estimated_cost

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
                "message_id": str(uuid.uuid4()),
                "response": response_text,
                "timestamp": datetime.now(UTC).isoformat(),
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
                window_name="claude",
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

        # Build Claude CLI command
        cmd_parts = ["claude", "--permission-mode", "bypassPermissions"]

        # Add model if specified
        if model := instance.get("model"):
            cmd_parts.extend(["--model", model])

        # Start Claude CLI
        cmd = " ".join(cmd_parts)
        pane.send_keys(cmd, enter=True)
        logger.debug(f"Started Claude CLI in tmux session: {cmd}")

        # Wait for Claude to initialize
        await asyncio.sleep(10)

        # Send initial system prompt if provided
        system_prompt = instance.get("system_prompt")
        if system_prompt:
            # Send context as first message
            workspace_path = instance["workspace_dir"]
            has_custom_prompt = instance.get("has_custom_prompt", False)

            prompt_prefix = "" if has_custom_prompt else "You are a specialized Claude instance. "

            if instance.get("bypass_isolation", False):
                workspace_info = (
                    f"\n\nIMPORTANT: You have FULL FILESYSTEM ACCESS. You can read and write files anywhere.\n"
                    f"Your workspace directory is at: {workspace_path}\n"
                    f"You can write files to any absolute path."
                )
            else:
                workspace_info = (
                    f"\n\nIMPORTANT: You have a workspace directory at: {workspace_path}\n"
                    f"You can read and write files within this directory. When asked to write files, "
                    f"write them to your workspace directory unless specifically asked to write elsewhere."
                )

            full_prompt = (
                f"{prompt_prefix}{system_prompt}{workspace_info if not has_custom_prompt else ''}"
            )
            pane.send_keys(full_prompt, enter=True)
            logger.debug("Sent initial system prompt to instance")

            # Wait for initial response
            await asyncio.sleep(5)

        logger.info(f"Tmux session initialized for instance {instance_id}")

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
