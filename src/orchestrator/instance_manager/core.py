"""Core InstanceManager class — assembles all mixins."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..compat import UTC
from ..logging_manager import LoggingManager
from ..tmux_instance_manager import TmuxInstanceManager
from ._mcp import mcp
from .files import FilesMixin
from .hierarchy import HierarchyMixin
from .lifecycle import LifecycleMixin
from .messaging import MessagingMixin
from .spawning import SpawningMixin
from .templates import TemplateMixin

logger = logging.getLogger(__name__)


class InstanceManager(
    SpawningMixin,
    MessagingMixin,
    HierarchyMixin,
    LifecycleMixin,
    TemplateMixin,
    FilesMixin,
):
    """Manages Claude instances and their lifecycle with MCP tools."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the instance manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.mcp = mcp
        self.instances: dict[str, dict[str, Any]] = {}

        # Job tracking for async messages
        self.jobs: dict[str, dict[str, Any]] = {}

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
        from ..shared_state_manager import SharedStateManager

        self.shared_state_manager = SharedStateManager()
        logger.info("Shared state manager initialized for IPC")

        # Initialize Tmux instance manager for Claude and Codex instances
        self.tmux_manager = TmuxInstanceManager(
            config,
            logging_manager=self.logging_manager,
            shared_state_manager=self.shared_state_manager,
        )

        # Main instance tracking
        self.main_instance_id: str | None = None
        self._main_spawn_lock = asyncio.Lock()

        # Main message inbox
        self.main_message_inbox: list[dict[str, Any]] = []
        self._last_main_message_index = -1
        self._main_monitor_task: asyncio.Task | None = None

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
        parent_id = kwargs.get("parent_instance_id")

        if parent_id is None:
            logger.info(
                f"Spawning root-level instance '{name}' with no parent (external client spawn)"
            )

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

        if parent_id:
            logger.info(f"Instance '{name}' will have parent: {parent_id}")
        else:
            logger.info(f"Instance '{name}' is root-level (no parent)")

        instance_id = await self.tmux_manager.spawn_instance(
            name=name,
            role=role,
            system_prompt=system_prompt,
            model=model,
            bypass_isolation=bypass_isolation,
            instance_type=instance_type,
            **kwargs,
        )
        self.instances[instance_id] = self.tmux_manager.instances[instance_id]
        return instance_id

    def _get_role_prompt(self, role: str) -> str:
        """Get system prompt for a role by loading from resources/prompts directory."""
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent.parent
        prompts_dir = project_root / "resources" / "prompts"

        prompt_file = prompts_dir / f"{role}.txt"

        try:
            if prompt_file.exists():
                return prompt_file.read_text(encoding="utf-8").strip()
            else:
                logger.warning(
                    f"Prompt file not found for role '{role}', using fallback",
                    extra={"role": role, "expected_path": str(prompt_file)},
                )
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
            return f"You are a helpful AI assistant with expertise in {role.replace('_', ' ')}."

    async def health_check(self):
        """Perform health check on all instances."""
        logger.info("Performing health check on all instances")

        current_time = datetime.now(UTC)
        timeout_minutes = self.config.get("instance_timeout_minutes", 60)

        for instance_id, instance in list(self.instances.items()):
            if instance["state"] == "terminated":
                continue

            last_activity = datetime.fromisoformat(instance["last_activity"])
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=UTC)
            if current_time - last_activity > timedelta(minutes=timeout_minutes):
                logger.warning(f"Instance {instance_id} timed out, terminating")
                await self._terminate_instance_internal(instance_id, force=True)
                continue

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

            if lines == -1:
                output = "\n".join(pane.cmd("capture-pane", "-p").stdout)
            else:
                output = "\n".join(pane.cmd("capture-pane", "-p", "-S", f"-{lines}").stdout)

            return output
        except Exception as e:
            logger.error(f"Failed to capture tmux pane for instance {instance_id}: {e}")
            raise

    async def ensure_main_instance(self) -> str:
        """Ensure main instance is spawned and return its ID."""
        async with self._main_spawn_lock:
            if self.main_instance_id is not None:
                return self.main_instance_id

            logger.info("Auto-spawning main orchestrator instance in tmux")

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

            self._start_main_monitor()

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
                if self.main_instance_id not in self.instances:
                    logger.info("Main instance terminated, stopping monitor")
                    break

                try:
                    messages = await self._get_output_messages(self.main_instance_id, limit=100)

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
        """Get all pending main messages and clear the inbox."""
        messages = self.main_message_inbox.copy()
        self.main_message_inbox.clear()
        return messages

    async def get_instance_logs(
        self, instance_id: str, log_type: str = "instance", tail: int = 100
    ) -> list[str]:
        """Retrieve logs for a specific instance."""
        if not self.logging_manager:
            logger.warning("Logging manager not initialized")
            return []

        return self.logging_manager.get_instance_logs(instance_id, log_type, tail)

    async def get_audit_logs(
        self, since: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Retrieve audit trail logs."""
        if not self.logging_manager:
            logger.warning("Logging manager not initialized")
            return []

        audit_dir = self.logging_manager.audit_dir
        audit_logs = []

        audit_files = sorted(audit_dir.glob("audit_*.jsonl"), reverse=True)

        since_dt = datetime.fromisoformat(since) if since else None

        for audit_file in audit_files:
            try:
                with audit_file.open("r") as f:
                    for line in f:
                        if not line.strip():
                            continue

                        try:
                            log_entry = json.loads(line)

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

        return audit_logs[:limit]

    async def list_logged_instances(self) -> list[dict[str, Any]]:
        """List all instances that have logs."""
        if not self.logging_manager:
            logger.warning("Logging manager not initialized")
            return []

        instance_ids = self.logging_manager.get_all_instance_ids()
        instances_info = []

        for instance_id in instance_ids:
            instance_dir = self.logging_manager.instances_dir / instance_id
            metadata_file = instance_dir / "metadata.json"

            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text())
                    instances_info.append(metadata)
                except Exception:
                    instances_info.append({"instance_id": instance_id})
            else:
                instances_info.append({"instance_id": instance_id})

        return instances_info

    async def shutdown(self):
        """Shutdown the instance manager and clean up resources."""
        logger.info("Shutting down instance manager")

        for instance_id in list(self.instances.keys()):
            try:
                await self._terminate_instance_internal(instance_id, force=True)
            except Exception as e:
                logger.error(f"Error terminating instance {instance_id}: {e}")

        if self.shared_state_manager:
            self.shared_state_manager.shutdown()
            logger.info("Shared state manager shutdown complete")
