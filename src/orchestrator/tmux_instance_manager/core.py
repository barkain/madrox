"""Tmux-based Instance Manager for Claude Orchestrator.

Manages Claude CLI instances via tmux sessions for persistent interactive communication.
"""

import asyncio
import base64
import json
import logging
import re
import shlex
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import libtmux

from ..compat import UTC
from ..config import resolve_model
from ..harnesses import Harness, get_harness
from ..llm_summarizer import LLMSummarizer
from ..monitoring_service import MonitoringService
from ..name_generator import get_instance_name
from ..simple_models import MessageEnvelope
from ..toml_config import update_toml_config
from .helpers import MAX_MESSAGE_HISTORY_PER_INSTANCE, redact_authkey

logger = logging.getLogger(__name__)

#: Valid MCP server name / environment variable name (CWE-77 hardening).
_MCP_SERVER_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_ENV_VAR_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

#: Commands run in the pane before the CLI starts are pipelined; this pause
#: only keeps the pane readable while they scroll past.
_PANE_COMMAND_PACING_SECONDS = 0.05


class TmuxInstanceManager:
    """Manages Claude instances via tmux sessions."""

    def __init__(self, config: dict[str, Any], logging_manager=None, shared_state_manager=None):
        """Initialize the tmux instance manager.

        Args:
            config: Configuration dictionary
            logging_manager: Optional LoggingManager instance for structured logging
            shared_state_manager: Optional SharedStateManager for cross-process IPC
        """
        self.config = config
        self.instances: dict[str, dict[str, Any]] = {}
        self.tmux_sessions: dict[str, libtmux.Session] = {}
        self.message_history: dict[str, list[dict]] = {}
        self.logging_manager = logging_manager

        # Persistent state store (injected by server)
        self.state_store = config.get("_state_store")

        # NEW: Use shared state manager for IPC
        self.shared_state = shared_state_manager

        # DEPRECATED: Keep for backward compatibility with HTTP transport
        self.response_queues: dict[str, asyncio.Queue] = {}
        self.message_registry: dict[str, MessageEnvelope] = {}
        self.main_message_inbox: list[dict[str, Any]] = []
        self.main_instance_id: str | None = None

        # Suspend/resume locks (per-instance)
        self._resume_locks: dict[str, asyncio.Lock] = {}

        # Resource tracking
        self.total_tokens_used = 0

        # Create workspace base directory
        self.workspace_base = Path(
            config.get("workspace_base_dir", "/tmp/claude_orchestrator")  # noqa: S108
        )
        self.workspace_base.mkdir(parents=True, exist_ok=True)

        # Connect to tmux server
        self.tmux_server = libtmux.Server()
        logger.info("Connected to tmux server")

        # Store server port for MCP config generation
        import os

        self.server_port = int(os.getenv("ORCHESTRATOR_PORT", "8001"))

        # Initialize monitoring service if OPENROUTER_API_KEY is available
        self.monitoring_service = None
        if os.getenv("OPENROUTER_API_KEY"):
            try:
                llm_summarizer = LLMSummarizer()
                self.monitoring_service = MonitoringService(
                    instance_manager=self, llm_summarizer=llm_summarizer, poll_interval=12
                )

                # Configure loggers for MonitoringService and LLMSummarizer
                # These loggers use src.orchestrator.* namespace which needs explicit parent setup
                for logger_name in [
                    "src.orchestrator.monitoring_service",
                    "src.orchestrator.llm_summarizer",
                ]:
                    module_logger = logging.getLogger(logger_name)
                    module_logger.setLevel(logging.DEBUG)
                    module_logger.propagate = True
                    module_logger.handlers.clear()
                    module_logger.parent = logging.getLogger("orchestrator")

                logger.info("MonitoringService initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize MonitoringService: {e}", exc_info=True)
        else:
            logger.info("MonitoringService disabled (OPENROUTER_API_KEY not set)")

        # Manager health monitoring
        self._manager_health_task: asyncio.Task | None = None
        self._queue_poller_task: asyncio.Task | None = None
        self._manager_health_check_interval = 30  # seconds
        self._manager_health_failures = 0
        self._max_health_failures = 3  # Alert after 3 consecutive failures
        self._health_monitoring_enabled = False
        self._monitoring_service_started = False

        # NOTE: Don't start health monitoring here - no event loop yet!
        # Health monitoring will start lazily when first instance is spawned

    def _limit_message_history(self, instance_id: str) -> None:
        """Limit message history size to prevent unbounded memory growth.

        SECURITY FIX (CWE-770): Keeps only the last MAX_MESSAGE_HISTORY_PER_INSTANCE
        messages per instance to prevent memory leaks in long-running processes.

        Args:
            instance_id: Instance ID whose message history to limit
        """
        if instance_id in self.message_history:
            history = self.message_history[instance_id]
            if len(history) > MAX_MESSAGE_HISTORY_PER_INSTANCE:
                # Keep only the last MAX_MESSAGE_HISTORY_PER_INSTANCE messages
                excess = len(history) - MAX_MESSAGE_HISTORY_PER_INSTANCE
                self.message_history[instance_id] = history[-MAX_MESSAGE_HISTORY_PER_INSTANCE:]
                logger.debug(
                    f"Trimmed {excess} old messages from history for instance {instance_id} "
                    f"(keeping last {MAX_MESSAGE_HISTORY_PER_INSTANCE})"
                )

    def _save_state(self) -> None:
        """Persist current instance state to disk (if state_store configured).

        Safe to call from both sync and async contexts. File I/O is fast
        (<1ms for typical state) but callers in hot async paths should
        prefer _save_state_async() to avoid blocking the event loop.
        """
        if self.state_store:
            try:
                self.state_store.save_all(self.instances)
            except Exception as e:
                logger.error(f"Failed to persist instance state: {e}")

    async def _save_state_async(self) -> None:
        """Async version of _save_state — runs file I/O in executor."""
        if self.state_store:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._save_state)

    async def _get_from_shared_queue(self, instance_id: str, timeout: int) -> dict:
        """Get message from shared queue with async wrapper.

        Wraps blocking multiprocessing.Queue.get() in executor to avoid blocking event loop.

        Args:
            instance_id: Instance ID whose queue to read from
            timeout: Timeout in seconds

        Returns:
            Message dict from queue

        Raises:
            TimeoutError: If no message received within timeout
        """
        import concurrent.futures

        if not self.shared_state:
            raise RuntimeError("Shared state not available (HTTP mode)")

        queue = self.shared_state.get_response_queue(instance_id)
        loop = asyncio.get_event_loop()

        # Run blocking queue.get() in thread executor
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = loop.run_in_executor(
                executor,
                queue.get,  # Blocking call
                True,  # block=True
                timeout,  # timeout in seconds
            )
            try:
                return await future
            except Exception as e:
                # Convert queue.Empty to TimeoutError for consistency
                if "Empty" in str(type(e).__name__):
                    raise TimeoutError(
                        f"No message received from instance {instance_id} within {timeout}s"
                    ) from None
                raise

    async def _put_to_shared_queue(self, instance_id: str, message: dict):
        """Put message to shared queue with async wrapper.

        Args:
            instance_id: Target instance ID whose queue to write to
            message: Message dict to send
        """
        import concurrent.futures

        if not self.shared_state:
            raise RuntimeError("Shared state not available (HTTP mode)")

        queue = self.shared_state.get_response_queue(instance_id)
        lock = self.shared_state.queue_locks[instance_id]
        loop = asyncio.get_event_loop()

        def put_with_lock():
            with lock:
                queue.put(message, block=True, timeout=5)

        # Run blocking queue.put() in thread executor
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            await loop.run_in_executor(executor, put_with_lock)

    @staticmethod
    def _normalize_mcp_servers(instance: dict[str, Any]) -> dict[str, Any]:
        """Coerce the instance's ``mcp_servers`` field into a dict.

        The MCP protocol delivers it as a JSON string; the Python API passes a
        dict. Anything unusable degrades to an empty mapping.
        """
        mcp_servers = instance.get("mcp_servers", {})

        if isinstance(mcp_servers, str):
            try:
                mcp_servers = json.loads(mcp_servers)
            except json.JSONDecodeError:
                logger.error(f"Invalid mcp_servers JSON string: {mcp_servers}")
                mcp_servers = {}

        if not isinstance(mcp_servers, dict):
            logger.error(f"mcp_servers is not a dict: {type(mcp_servers)}, value: {mcp_servers}")
            mcp_servers = {}

        instance["mcp_servers"] = mcp_servers
        return mcp_servers

    def _add_madrox_mcp_server(
        self, mcp_servers: dict[str, Any], harness: type[Harness], instance_id: str
    ) -> None:
        """Wire the instance back to this orchestrator over the harness's transport."""
        if "madrox" in mcp_servers:
            return

        if harness.auto_mcp_transport == "stdio":
            # A STDIO subprocess proxies every tool call to the parent HTTP server.
            orchestrator_script = str(
                Path(__file__).parent.parent.parent.parent / "run_orchestrator.py"
            )
            parent_url = f"http://localhost:{self.server_port}"
            mcp_servers["madrox"] = {
                "transport": "stdio",
                "command": sys.executable,
                "args": [orchestrator_script],
                "env": {"MADROX_TRANSPORT": "stdio", "MADROX_PARENT_URL": parent_url},
            }
            logger.debug(
                f"Configured STDIO madrox proxy for {instance_id}: "
                f"{sys.executable} {orchestrator_script} -> {parent_url}"
            )
        else:
            # HTTP transport keeps every spawn visible to the parent server.
            mcp_servers["madrox"] = {
                "transport": "http",
                "url": f"http://localhost:{self.server_port}/mcp",
            }
            logger.debug(
                f"Configured HTTP madrox for {instance_id}: http://localhost:{self.server_port}/mcp"
            )

    @staticmethod
    def _mcp_transport(server_config: dict[str, Any]) -> str:
        """Transport for a server entry — stdio when a command is present, else http."""
        return server_config.get("transport", "stdio" if "command" in server_config else "http")

    @staticmethod
    def _validate_mcp_identifiers(server_name: str, env_vars: dict[str, str]) -> None:
        """Reject names that would break out of the shell command (CWE-77)."""
        if not _MCP_SERVER_NAME_RE.match(server_name):
            raise ValueError(
                f"Invalid MCP server name '{server_name}'. "
                f"Server names must contain only letters, numbers, underscores, and hyphens."
            )

        for key in env_vars:
            if not _ENV_VAR_NAME_RE.match(key):
                raise ValueError(
                    f"Invalid environment variable name '{key}'. "
                    f"Variable names must start with a letter or underscore and "
                    f"contain only letters, numbers, and underscores."
                )

    async def _configure_mcp_servers(self, pane, instance: dict[str, Any]) -> None:
        """Configure MCP servers in the tmux session before the CLI starts.

        Harnesses that read a JSON config file (Claude) get one written to their
        workspace; the rest have their servers registered with ``<cli> mcp add``
        commands typed into the pane, falling back to the harness's TOML config
        for transports the CLI cannot register.

        Args:
            pane: libtmux pane object
            instance: Instance metadata dict
        """
        harness = get_harness(instance.get("instance_type"))
        mcp_servers = self._normalize_mcp_servers(instance)
        self._add_madrox_mcp_server(mcp_servers, harness, instance["id"])

        if harness.mcp_config_filename:
            self._write_mcp_config_file(instance, harness, mcp_servers)
            return

        await self._register_mcp_servers_via_cli(pane, instance, harness, mcp_servers)

    async def _register_mcp_servers_via_cli(
        self,
        pane,
        instance: dict[str, Any],
        harness: type[Harness],
        mcp_servers: dict[str, Any],
    ) -> None:
        """Register MCP servers by typing ``<cli> mcp add`` commands into the pane."""
        if not mcp_servers:
            logger.debug(
                f"No MCP servers to configure for {harness.name} instance {instance['id']}"
            )
            return

        logger.info(
            f"Configuring {len(mcp_servers)} MCP servers for {harness.name} instance {instance['id']}"
        )

        # Servers the CLI cannot register itself are batched into one TOML write.
        pending_http: dict[str, dict[str, Any]] = {}

        for server_name, server_config in mcp_servers.items():
            try:
                transport = self._mcp_transport(server_config)

                if transport == "stdio":
                    command = server_config.get("command")
                    if not command:
                        logger.warning(f"Skipping MCP server '{server_name}' - no command provided")
                        continue

                    env_vars = server_config.get("env", {}) or {}
                    self._validate_mcp_identifiers(server_name, env_vars)

                    if not (
                        Path(command).is_absolute()
                        or command in ("python", "python3", "node", "npx")
                    ):
                        logger.warning(
                            f"Command '{command}' is not an absolute path or known safe command. "
                            f"This may be a security risk."
                        )

                    args = server_config.get("args", [])
                    if not isinstance(args, list):
                        args = [args] if args else []

                    cmd_parts = harness.mcp_add_stdio_command(
                        server_name, str(command), args, env_vars
                    )

                elif transport == "http":
                    url = server_config.get("url")
                    if not url:
                        logger.warning(
                            f"Skipping MCP server '{server_name}' - no URL provided for http transport"
                        )
                        continue

                    self._validate_mcp_identifiers(server_name, {})
                    cmd_parts = harness.mcp_add_http_command(server_name, str(url))
                    if cmd_parts is None:
                        pending_http[server_name] = server_config
                        continue

                else:
                    logger.warning(
                        f"Skipping MCP server '{server_name}' - unsupported transport '{transport}'"
                    )
                    continue

                if cmd_parts is None:
                    logger.warning(
                        f"Harness '{harness.name}' cannot register '{transport}' MCP server "
                        f"'{server_name}' - skipping"
                    )
                    continue

                cli_command = " ".join(cmd_parts)
                logger.info(f"Adding {harness.name} MCP server: {cli_command}")
                pane.send_keys(cli_command, enter=True)
                await asyncio.sleep(_PANE_COMMAND_PACING_SECONDS)

            except Exception as e:
                logger.error(
                    f"Error configuring {harness.name} MCP server '{server_name}': {e}",
                    exc_info=True,
                )
                raise

        if pending_http:
            self._write_mcp_servers_to_toml(harness, pending_http)

        logger.info(f"Configured MCP servers for {harness.name} instance {instance['id']}")

    @staticmethod
    def _write_mcp_servers_to_toml(harness: type[Harness], servers: dict[str, Any]) -> None:
        """Write HTTP MCP servers into the harness's TOML config in one pass."""
        config_path = harness.mcp_http_config_path()
        if config_path is None:
            logger.warning(
                f"Harness '{harness.name}' has no config file for HTTP MCP servers: "
                f"{', '.join(servers)}"
            )
            return

        def _apply(config: dict[str, Any]) -> bool:
            entries = config.setdefault("mcp_servers", {})
            for server_name, server_config in servers.items():
                entry = {"url": server_config["url"]}
                if bearer_token := server_config.get("bearer_token"):
                    entry["bearer_token"] = bearer_token
                entries[server_name] = entry
            return True

        update_toml_config(config_path, _apply)
        logger.info(
            f"Added {len(servers)} HTTP MCP server(s) to {harness.name} config {config_path}"
        )

    @staticmethod
    def _write_mcp_config_file(
        instance: dict[str, Any], harness: type[Harness], mcp_servers: dict[str, Any]
    ) -> None:
        """Write a JSON MCP config file and record its path for the launch command."""
        mcp_config_path = Path(instance["workspace_dir"]) / str(harness.mcp_config_filename)
        servers: dict[str, Any] = {}

        for server_name, server_config in mcp_servers.items():
            transport = TmuxInstanceManager._mcp_transport(server_config)

            if transport == "http":
                url = server_config.get("url")
                if not url:
                    logger.warning(
                        f"Skipping MCP server '{server_name}' - no URL provided for http transport"
                    )
                    continue
                # Claude Code uses "type", not "transport".
                servers[server_name] = {"type": "http", "url": url}

            elif transport == "stdio":
                command = server_config.get("command")
                if not command:
                    logger.warning(
                        f"Skipping MCP server '{server_name}' - no command provided for stdio transport"
                    )
                    continue

                args = server_config.get("args", [])
                # Claude Code infers stdio from the presence of "command" — no "type" key.
                entry: dict[str, Any] = {
                    "command": command,
                    "args": args if isinstance(args, list) else [args],
                }
                if env_vars := server_config.get("env", {}):
                    entry["env"] = env_vars
                    logger.debug(f"Adding {len(env_vars)} env vars to MCP server '{server_name}'")

                servers[server_name] = entry

            else:
                logger.warning(
                    f"Skipping MCP server '{server_name}' - unsupported transport '{transport}'"
                )

        mcp_config_path.write_text(json.dumps({"mcpServers": servers}, indent=2))
        logger.info(f"Created MCP config for instance {instance['id']}: {len(servers)} servers")

        # Recorded here, consumed by the harness when building the launch command.
        instance["_mcp_config_path"] = str(mcp_config_path)

    async def spawn_instance(
        self,
        name: str | None = None,
        role: str = "general",
        system_prompt: str | None = None,
        model: str | None = None,
        bypass_isolation: bool = True,
        instance_type: str = "claude",
        sandbox_mode: str | None = None,
        profile: str | None = None,
        initial_prompt: str | None = None,
        wait_for_ready: bool = True,
        **kwargs,
    ) -> str:
        """Spawn a new harness instance (Claude, Codex, Grok, ...) in a tmux session.

        Args:
            name: Human-readable name for the instance
            role: Predefined role (general, frontend_developer, etc.)
            system_prompt: Custom system prompt
            model: Model to run. None resolves to the harness default from
                config/models.yaml (or the CLI's own default if unconfigured).
                Any model id is accepted — no allowlist.
            bypass_isolation: Allow full filesystem access (harness "yolo" mode)
            instance_type: Harness to run - "claude", "codex" or "grok"
            sandbox_mode: For Codex - sandbox policy (read-only, workspace-write, danger-full-access)
            profile: For Codex - configuration profile from config.toml
            initial_prompt: Initial prompt to send once the CLI is ready
            wait_for_ready: Wait for instance to fully initialize (default: True). If False, returns immediately.
            **kwargs: Additional configuration options

        Returns:
            Instance ID

        Raises:
            ValueError: If instance_type is not a supported harness
        """
        # Fail fast on an unknown harness, before any workspace is created.
        harness = get_harness(instance_type)
        instance_type = harness.name

        # Resolve the model once, here, so every spawn path (MCP tool, HTTP
        # adapter, direct call) gets the same harness default.
        model = resolve_model(instance_type, model)

        # Count only active instances
        active_count = len(
            [i for i in self.instances.values() if i["state"] not in ("terminated", "suspended")]
        )
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

        use_worktree = kwargs.get("use_worktree", False)
        git_repo = kwargs.get("git_repo")
        git_worktree_branch = None

        if use_worktree:
            repo_path = git_repo or await self._detect_git_repo(kwargs.get("parent_instance_id"))
            if repo_path:
                branch_name = (
                    f"madrox/{self._sanitize_branch_name(instance_name)}-{instance_id[:8]}"
                )
                # Ensure parent directory exists (git worktree add creates the final dir)
                workspace_dir.parent.mkdir(parents=True, exist_ok=True)
                success = await self._create_worktree(repo_path, str(workspace_dir), branch_name)
                if success:
                    git_repo = repo_path
                    git_worktree_branch = branch_name
                else:
                    logger.warning(
                        f"Worktree creation failed for {instance_name}, using regular workspace"
                    )
                    use_worktree = False
            else:
                logger.warning(
                    f"No git repo found for worktree, using regular workspace for {instance_name}"
                )
                use_worktree = False

        if not use_worktree:
            # Only create workspace dir if not using worktree (worktree add creates it)
            workspace_dir.mkdir(parents=True, exist_ok=True)

        # Write instance metadata file so child knows its own ID
        metadata_file = workspace_dir / ".madrox_instance_id"
        metadata_file.write_text(instance_id)

        # Lazy startup of health monitoring (after event loop is running)
        if self.shared_state and not self._health_monitoring_enabled:
            try:
                self._start_manager_health_monitoring()
                self._health_monitoring_enabled = True
                logger.info("Manager health monitoring started (lazy initialization)")
            except Exception as e:
                logger.error(f"Failed to start health monitoring: {e}", exc_info=True)

        # Start monitoring service if available
        if self.monitoring_service and not self._monitoring_service_started:
            try:
                asyncio.create_task(self.monitoring_service.start())
                self._monitoring_service_started = True
                logger.info("MonitoringService background task started")
            except Exception as e:
                logger.error(f"Failed to start MonitoringService: {e}", exc_info=True)

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
            "instance_type": instance_type,
            "sandbox_mode": sandbox_mode,
            "profile": profile,
            "initial_prompt": initial_prompt,
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity": datetime.now(UTC).isoformat(),
            "total_tokens_used": 0,
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
            "use_worktree": use_worktree,
            "git_repo": git_repo if use_worktree else None,
            "git_worktree_branch": git_worktree_branch,
        }

        self.instances[instance_id] = instance
        self.message_history[instance_id] = []

        # Initialize response queue for this instance immediately at spawn
        # This ensures the instance can receive replies from children even before sending messages
        if self.shared_state:
            # Use shared queue for STDIO transport
            self.shared_state.create_response_queue(instance_id)

            # Register instance in shared metadata for cross-process visibility
            # This allows parent HTTP server to see instances spawned by STDIO children
            created_at_str = instance["created_at"]
            if hasattr(created_at_str, "isoformat"):
                created_at_str = created_at_str.isoformat()

            self.shared_state.instance_metadata[instance_id] = {
                "id": instance_id,
                "name": instance_name,
                "state": "initializing",
                "role": role,
                "instance_type": instance_type,
                "model": model,
                "parent_instance_id": kwargs.get("parent_instance_id"),
                "created_at": created_at_str,
            }
        else:
            # Fall back to local queue for HTTP transport
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
                    "bypass_isolation": bypass_isolation,
                },
            )

        # Start the tmux session
        if wait_for_ready:
            # Blocking: wait for full initialization
            try:
                await self._initialize_tmux_session(instance_id)
                instance["state"] = "idle"
                await self._process_queued_messages(instance_id)
                logger.info(
                    f"Successfully spawned {instance_type} instance {instance_id} ({instance_name}) with role {role} via tmux",
                    extra={
                        "instance_id": instance_id,
                        "instance_type": instance_type,
                        "role": role,
                        "instance_name": instance_name,
                    },
                )

                self._save_state()

                if self.logging_manager:
                    instance_logger = self.logging_manager.get_instance_logger(
                        instance_id, instance_name
                    )
                    instance_logger.info("Instance initialization completed successfully")

            except Exception as e:
                instance["state"] = "error"
                instance["error_message"] = str(e)
                self._save_state()
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
            instance["state"] = "idle"
            self._save_state()
            await self._process_queued_messages(instance_id)
            logger.info(
                f"Background initialization completed for instance {instance_id} ({instance['name']})",
                extra={"instance_id": instance_id, "instance_name": instance["name"]},
            )
        except Exception as e:
            instance["state"] = "error"
            instance["error_message"] = str(e)
            self._save_state()
            logger.error(
                f"Background initialization failed for instance {instance_id}: {e}",
                extra={"instance_id": instance_id, "error": str(e)},
            )

    async def _wait_for_queue_response(self, instance_id: str, timeout: int) -> dict:
        """Wait for a bidirectional reply via response queue."""
        if self.shared_state:
            # Chunk into 1s waits so the task is cancellable
            deadline = time.time() + timeout
            while time.time() < deadline:
                remaining = max(1, int(deadline - time.time()))
                chunk = min(remaining, 1)
                try:
                    return await self._get_from_shared_queue(instance_id, timeout=chunk)
                except TimeoutError:
                    continue
            raise TimeoutError(f"No queue response from {instance_id} within {timeout}s")
        else:
            return await asyncio.wait_for(self.response_queues[instance_id].get(), timeout=timeout)

    @staticmethod
    def _last_content_line(output: str) -> str:
        """Last line of pane output that is neither status bar nor separator.

        Claude's "⏵⏵ bypass permissions" bar and the box-drawing rules around
        the input field are visible at all times, so they can never be used to
        tell idle from thinking.
        """
        for pane_line in reversed(output.split("\n")):
            stripped = pane_line.strip()
            if (
                stripped
                and "⏵⏵" not in pane_line
                and "esc to interrupt" not in pane_line
                and not stripped.startswith("─")
            ):
                return stripped
        return ""

    async def _wait_for_pane_response(
        self, pane, initial_output: str, timeout: int, instance_type: str = "claude"
    ) -> str:
        """Poll tmux pane for response completion. Returns full scrollback output.

        Two-phase detection:
        1. Wait for output to start growing (response started)
        2. After output stabilises, keep polling for the CLI prompt which
           only appears after all tool calls (including reply_to_caller)
           complete. Fall back to stability-only after 15s without a prompt.
        """
        harness = get_harness(instance_type)
        start_time = time.time()
        last_size = len(initial_output)
        stable_count = 0
        poll_count = 0
        response_started = False
        stability_reached_at: float | None = None
        last_line = ""

        while time.time() - start_time < timeout:
            await asyncio.sleep(0.3)
            poll_count += 1

            current_output = "\n".join(pane.cmd("capture-pane", "-p").stdout)
            current_size = len(current_output)

            if current_size > last_size:
                response_started = True
                stable_count = 0
                stability_reached_at = None
                last_size = current_size
                continue

            if response_started:
                stable_count += 1
                # The idle prompt is only meaningful once output has settled, so
                # scan for it here rather than on every poll.
                last_line = self._last_content_line(current_output)
                if stable_count >= 3 and stability_reached_at is None:
                    stability_reached_at = time.time()
                    logger.info(
                        f"Pane poll: output stable after {time.time() - start_time:.1f}s "
                        f"(poll #{poll_count}), last_line: {repr(last_line[:80])}"
                    )

                # Only check for prompt AFTER stability — avoids matching
                # old prompts that are visible while output is still changing.
                if stability_reached_at and harness.is_idle_line(last_line):
                    # Verify the prompt is NEW — count bare "❯" lines in initial
                    # vs current output. If the count increased, it's a real new prompt.
                    if instance_type == "claude" and last_line == "❯":
                        initial_prompts = initial_output.count("\n❯\n") + initial_output.count(
                            "\n❯ \n"
                        )
                        current_prompts = current_output.count("\n❯\n") + current_output.count(
                            "\n❯ \n"
                        )
                        if current_prompts <= initial_prompts:
                            continue  # Stale prompt — keep waiting
                    logger.info(
                        f"Pane poll: prompt detected after "
                        f"{time.time() - start_time:.1f}s (poll #{poll_count}), "
                        f"last_line: {repr(last_line[:80])}"
                    )
                    break

                if stability_reached_at and (time.time() - stability_reached_at > 15):
                    logger.info(
                        f"Pane poll: no prompt after 15s stability, "
                        f"returning pane (poll #{poll_count})"
                    )
                    break

        if not response_started:
            logger.warning(
                f"No response activity detected after {poll_count} polls, "
                f"{time.time() - start_time:.1f}s"
            )

        logger.debug(f"Polling completed after {poll_count} polls, {time.time() - start_time:.1f}s")
        return "\n".join(pane.cmd("capture-pane", "-p", "-S", "-").stdout)

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

        # Queue message if instance is busy (instead of rejecting)
        if instance["state"] == "busy":
            message_id = str(uuid.uuid4())
            if self.shared_state:
                self.shared_state.queue_message(instance_id, message, message_id)
                logger.info(f"Instance {instance_id} is busy, queued message {message_id}")
                return {
                    "instance_id": instance_id,
                    "status": "queued",
                    "message_id": message_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            # Fallback for HTTP mode without shared state - still reject
            raise RuntimeError(f"Instance {instance_id} is busy (no queue in HTTP mode)")

        # Auto-resume suspended instances
        if instance["state"] == "suspended":
            logger.info(f"Auto-resuming suspended instance {instance_id}")
            resumed = await self._resume_suspended_instance(instance_id)
            if not resumed:
                raise RuntimeError(f"Failed to resume suspended instance {instance_id}")

        if instance["state"] not in ["running", "idle"]:
            raise RuntimeError(
                f"Instance {instance_id} is not in a valid state: {instance['state']}"
            )

        # Update instance state
        instance["state"] = "busy"
        instance["last_activity"] = datetime.now(UTC).isoformat()
        await self._save_state_async()

        # Generate message ID for tracking
        message_id = str(uuid.uuid4())
        send_timestamp = datetime.now(UTC)

        try:
            # Record message in history
            self.message_history[instance_id].append(
                {"role": "user", "content": message, "timestamp": send_timestamp.isoformat()}
            )
            # SECURITY FIX (CWE-770): Limit history size to prevent unbounded growth
            self._limit_message_history(instance_id)

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

            # Register in shared state or local state
            if self.shared_state:
                self.shared_state.register_message(message_id, envelope.to_dict())
            else:
                self.message_registry[message_id] = envelope

            # Initialize response queue for this instance if needed
            if not self.shared_state and instance_id not in self.response_queues:
                self.response_queues[instance_id] = asyncio.Queue()

            # Check if system prompt is pending (first message after spawn)
            if instance.get("_system_prompt_pending"):
                logger.info(
                    f"Combining pending system prompt with first message to instance {instance_id}"
                )
                # Get the pending system prompt
                system_prompt = instance.get("_pending_system_prompt", "")

                # Combine system prompt with user message for single send
                if system_prompt:
                    formatted_message = f"{system_prompt}\n\n[MSG:{message_id}] {message}"
                else:
                    formatted_message = f"[MSG:{message_id}] {message}"

                # Clear the pending flag
                instance["_system_prompt_pending"] = False
                instance.pop("_pending_system_prompt", None)
            else:
                # Normal flow - just format the user message
                formatted_message = f"[MSG:{message_id}] {message}"

            # Send message via tmux (SINGLE SEND)
            session = self.tmux_sessions[instance_id]
            window = session.windows[0]
            pane = window.panes[0]

            # Use new multiline-safe method
            await self._send_multiline_message_to_pane(pane, formatted_message)
            envelope.mark_delivered()

            logger.debug(f"Sent message {message_id} to instance {instance_id}")

            if not wait_for_response:
                # Still track outbound message tokens even when not waiting for response
                # Fallback to word-count estimation
                estimated_tokens = len(message.split())

                instance["total_tokens_used"] += estimated_tokens
                instance["request_count"] += 1

                self.total_tokens_used += estimated_tokens

                return {
                    "instance_id": instance_id,
                    "status": "sent",
                    "message_id": message_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }

            # Race bidirectional queue against pane polling concurrently.
            # Child instances may or may not call reply_to_caller — running
            # both in parallel means we never block on an empty queue.

            # Drain stale queue items from previous messages
            if not self.shared_state and instance_id in self.response_queues:
                q = self.response_queues[instance_id]
                drained = 0
                while not q.empty():
                    try:
                        q.get_nowait()
                        drained += 1
                    except asyncio.QueueEmpty:
                        break
                if drained:
                    logger.info(f"Drained {drained} stale queue item(s) for {instance_id}")

            await asyncio.sleep(0.3)
            initial_output = "\n".join(pane.cmd("capture-pane", "-p").stdout)

            instance_type = instance.get("instance_type", "claude")
            queue_task = asyncio.create_task(
                self._wait_for_queue_response(instance_id, timeout_seconds)
            )
            poll_task = asyncio.create_task(
                self._wait_for_pane_response(pane, initial_output, timeout_seconds, instance_type)
            )

            done, pending = await asyncio.wait(
                {queue_task, poll_task}, return_when=asyncio.FIRST_COMPLETED
            )

            # When pane polling wins, the queue likely already has the clean
            # reply_to_caller response (it's delivered before the CLI prompt
            # appears). Give the queue a brief window to also complete.
            if poll_task in done and queue_task in pending:
                try:
                    await asyncio.wait_for(asyncio.shield(queue_task), timeout=5.0)
                    done = {queue_task}
                    pending = {poll_task}
                    logger.debug(
                        "Queue response arrived shortly after pane polling — preferring queue"
                    )
                except (TimeoutError, Exception):
                    pass

            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, TimeoutError, Exception):
                    pass

            # Prefer queue when both complete (cleaner response text)
            if queue_task in done and queue_task.exception() is None:
                winner = queue_task
            else:
                winner = done.pop()
            protocol = "unknown"
            full_output: str | None = None

            if winner is queue_task and winner.exception() is None:
                queue_response = winner.result()
                # Verify correlation — ignore stale replies from previous messages
                if (
                    queue_response.get("correlation_id")
                    and queue_response["correlation_id"] != message_id
                ):
                    logger.info(
                        f"Ignoring stale queue reply (correlation {queue_response['correlation_id'][:8]}… "
                        f"!= {message_id[:8]}…) — falling back to pane"
                    )
                    full_output = "\n".join(pane.cmd("capture-pane", "-p", "-S", "-").stdout)
                    response_text = self._extract_response(full_output, initial_output, instance_id)
                    protocol = "fallback"
                else:
                    response_text = queue_response["reply_message"]
                    protocol = "bidirectional"
                    logger.info(f"Received bidirectional reply from instance {instance_id}")

                    if self.shared_state:
                        self.shared_state.update_message_status(
                            message_id,
                            status="replied",
                            reply_content=response_text,
                            replied_at=datetime.now().isoformat(),
                        )
                    else:
                        envelope.mark_replied(response_text)

            elif winner is poll_task and winner.exception() is None:
                full_output = winner.result()
                response_text = self._extract_response(full_output, initial_output, instance_id)
                protocol = "pane_polling"
                logger.info(f"Detected response via pane polling for instance {instance_id}")
                envelope.mark_timeout()

            else:
                exc = winner.exception()
                logger.warning(f"Both response detection paths failed for {instance_id}: {exc}")
                envelope.mark_timeout()
                full_output = "\n".join(pane.cmd("capture-pane", "-p", "-S", "-").stdout)
                response_text = self._extract_response(full_output, initial_output, instance_id)
                protocol = "fallback"

            # Detect silent backend failures (e.g. Codex Bedrock model 404s).
            # A clean bidirectional reply means the instance actually responded,
            # so only scan the pane for the pane-derived protocols. Scan only the
            # NEW output (delta against initial_output) so stale error lines from
            # previous messages still in scrollback are not re-detected.
            backend_error: str | None = None
            if protocol != "bidirectional":
                scan_output = full_output
                if scan_output is None:
                    scan_output = "\n".join(pane.cmd("capture-pane", "-p", "-S", "-").stdout)
                backend_error = self._detect_backend_error(scan_output, initial_output)
                # Empty output with no detected error is still a failure to
                # surface — the instance produced nothing.
                if not backend_error and not response_text.strip():
                    backend_error = (
                        "Instance produced no output (possible backend failure). "
                        "Inspect the terminal with get_tmux_pane_content for details."
                    )

            # Set on failure, clear on success — otherwise a transient error
            # would stick to the instance (and to persisted state) forever.
            instance["error_message"] = backend_error
            if backend_error:
                logger.warning(
                    f"Backend error detected for instance {instance_id}: {backend_error}"
                )

            # Add response to history
            response_timestamp = datetime.now(UTC)
            self.message_history[instance_id].append(
                {
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": response_timestamp.isoformat(),
                }
            )
            # SECURITY FIX (CWE-770): Limit history size to prevent unbounded growth
            self._limit_message_history(instance_id)

            # Calculate response time
            response_time = (response_timestamp - send_timestamp).total_seconds()

            # Update usage statistics with word-count estimation
            estimated_tokens = len(message.split()) + len(response_text.split())

            instance["total_tokens_used"] += estimated_tokens
            instance["request_count"] += 1

            self.total_tokens_used += estimated_tokens

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
                        "response_time": response_time,
                    },
                )

                # Log tmux output for debugging (only available from polling path)
                if protocol != "bidirectional":
                    pane_output = "\n".join(pane.cmd("capture-pane", "-p", "-S", "-").stdout)
                    self.logging_manager.log_tmux_output(instance_id, pane_output)

                # Log audit event
                self.logging_manager.log_audit_event(
                    event_type="message_exchange",
                    instance_id=instance_id,
                    details={
                        "message_id": message_id,
                        "message_length": len(message),
                        "response_length": len(response_text),
                        "tokens": estimated_tokens,
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
                # NOTE: deliberately no "status" key here — the MCP adapter
                # branches on `"status" in response` to format job/timeout
                # replies, so adding it would misroute normal waited replies.
                # Callers detect failure via a non-null "error".
                "error": backend_error,
                "timestamp": response_timestamp.isoformat(),
                "tokens_used": estimated_tokens,
                "response_time": response_time,
                "estimated_tokens": estimated_tokens,
                "protocol": protocol,
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
                await self._save_state_async()
                # Process any queued messages
                await self._process_queued_messages(instance_id)

    async def _process_queued_messages(self, instance_id: str) -> None:
        """Process queued messages for an instance that just became idle.

        Args:
            instance_id: Instance ID to process messages for
        """
        if not self.shared_state or not self.shared_state.has_queued_messages(instance_id):
            return

        instance = self.instances.get(instance_id)
        if not instance:
            logger.warning(f"Instance {instance_id} not found, cannot process queued messages")
            return

        queued = self.shared_state.get_queued_messages(instance_id)
        if not queued:
            return

        logger.info(f"Processing {len(queued)} queued messages for instance {instance_id}")

        # Mark busy while draining queue to prevent new messages interleaving
        instance["state"] = "busy"
        instance["last_activity"] = datetime.now(UTC).isoformat()

        try:
            session = self.tmux_sessions.get(instance_id)
            if not session:
                logger.warning(
                    f"No tmux session found for {instance_id}, cannot deliver queued messages"
                )
                return

            window = session.windows[0]
            pane = window.panes[0]

            for msg in queued:
                formatted = f"[MSG:{msg['message_id']}] {msg['message']}"
                await self._send_multiline_message_to_pane(pane, formatted)
                logger.info(
                    f"Delivered queued message {msg['message_id']} to {instance_id} "
                    f"(queued at {msg['queued_at']})"
                )
                # Brief pause between queued messages
                await asyncio.sleep(0.1)
        finally:
            instance["state"] = "idle"
            instance["last_activity"] = datetime.now(UTC).isoformat()

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

            # Stop monitoring service if this is the last active instance
            active_count = len(
                [
                    i
                    for i in self.instances.values()
                    if i["state"] not in ["terminated", "error"] and i["id"] != instance_id
                ]
            )
            if (
                active_count == 0
                and self.monitoring_service
                and self.monitoring_service.is_running()
            ):
                await self.monitoring_service.stop()
                logger.info("MonitoringService stopped (no active instances)")

            # Update instance state
            instance["state"] = "terminated"
            instance["terminated_at"] = datetime.now(UTC).isoformat()
            self._save_state()

            # Clean up git worktree if applicable
            if instance.get("use_worktree") and instance.get("git_repo"):
                await self._remove_worktree(instance)

            # No artifact preservation needed - workspace IS the artifacts directory
            # All files remain in place, no copying or cleanup required

            # Remove message history
            if instance_id in self.message_history:
                del self.message_history[instance_id]

            # Clean up shared state resources
            if self.shared_state:
                self.shared_state.cleanup_instance(instance_id)
                logger.debug(f"Cleaned up shared state resources for instance {instance_id}")

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

    async def suspend_instance(self, instance_id: str) -> bool:
        """Suspend an instance: kill tmux session but preserve state for later resume."""
        if instance_id not in self.instances:
            raise ValueError(f"Instance {instance_id} not found")

        instance = self.instances[instance_id]

        if instance["state"] in ("terminated", "suspended"):
            logger.warning(f"Instance {instance_id} is already {instance['state']}")
            return instance["state"] == "suspended"

        try:
            # Kill tmux session
            session = self.tmux_sessions.get(instance_id)
            if session:
                try:
                    session.kill_session()
                except Exception as e:
                    logger.warning(f"Error killing tmux session for {instance_id}: {e}")
                self.tmux_sessions.pop(instance_id, None)

            # Update state
            instance["state"] = "suspended"
            instance["suspended_at"] = datetime.now(UTC).isoformat()
            self._save_state()

            # Log audit event
            if self.logging_manager:
                self.logging_manager.log_audit_event(
                    event_type="instance_suspended",
                    instance_id=instance_id,
                    details={
                        "instance_name": instance.get("name"),
                        "total_requests": instance.get("request_count", 0),
                    },
                )

            logger.info(
                f"Suspended instance {instance_id} ({instance.get('name')})",
                extra={"instance_id": instance_id},
            )
            return True

        except Exception as e:
            logger.error(
                f"Error suspending instance {instance_id}: {e}",
                extra={"instance_id": instance_id, "error": str(e)},
            )
            instance["error_message"] = str(e)
            return False

    async def _resume_suspended_instance(self, instance_id: str, timeout: float = 60.0) -> bool:
        """Resume a suspended instance by recreating its tmux session with --continue."""
        # Per-instance lock to prevent concurrent resume attempts
        if instance_id not in self._resume_locks:
            self._resume_locks[instance_id] = asyncio.Lock()

        async with self._resume_locks[instance_id]:
            if instance_id not in self.instances:
                raise ValueError(f"Instance {instance_id} not found")

            instance = self.instances[instance_id]

            # Already running — nothing to do
            if instance["state"] in ("running", "idle", "busy"):
                return True

            if instance["state"] != "suspended":
                logger.warning(
                    f"Cannot resume instance {instance_id}: state is {instance['state']}"
                )
                return False

            workspace_dir = instance.get("workspace_dir", "")
            marker = Path(workspace_dir) / ".madrox_instance_id"
            if not Path(workspace_dir).exists() or not marker.exists():
                logger.error(f"Workspace {workspace_dir} or metadata missing, cannot resume")
                return False

            # Prepare for recovery
            instance["state"] = "initializing"
            instance["retry_count"] = instance.get("retry_count", 0) + 1
            self.message_history[instance_id] = []

            # Ensure response queue exists
            if self.shared_state:
                self.shared_state.create_response_queue(instance_id)
            elif instance_id not in self.response_queues:
                self.response_queues[instance_id] = asyncio.Queue()

            self._save_state()

            # Recover: create tmux session with --continue
            await self._recover_instance_async(instance_id)

            # Check result
            if instance["state"] == "idle":
                instance.pop("suspended_at", None)
                self._save_state()

                if self.logging_manager:
                    self.logging_manager.log_audit_event(
                        event_type="instance_resumed",
                        instance_id=instance_id,
                        details={
                            "instance_name": instance.get("name"),
                            "retry_count": instance.get("retry_count", 0),
                        },
                    )

                logger.info(
                    f"Resumed suspended instance {instance_id} ({instance.get('name')})",
                    extra={"instance_id": instance_id},
                )
                return True

            logger.error(f"Failed to resume instance {instance_id}: state is {instance['state']}")
            return False

    def reconnect_instance(self, persisted_record: dict[str, Any]) -> str:
        """Reconnect to a persisted instance whose tmux session is still alive."""
        instance_id = persisted_record["id"]
        session_name = f"madrox-{instance_id}"

        try:
            session = self.tmux_server.find_where({"session_name": session_name})
        except Exception:
            session = None

        if not session:
            raise RuntimeError(f"Tmux session {session_name} not found for reconnect")

        # Restore instance record (without transient keys — they'll be rebuilt)
        self.instances[instance_id] = persisted_record
        self.tmux_sessions[instance_id] = session
        self.message_history[instance_id] = []

        # Create response queue
        if self.shared_state:
            self.shared_state.create_response_queue(instance_id)
        else:
            self.response_queues[instance_id] = asyncio.Queue()

        harness = get_harness(persisted_record.get("instance_type"))

        # Restore MCP config path if file exists on disk
        workspace_dir = persisted_record.get("workspace_dir", "")
        if harness.mcp_config_filename:
            mcp_config_path = Path(workspace_dir) / harness.mcp_config_filename
            if mcp_config_path.exists():
                persisted_record["_mcp_config_path"] = str(mcp_config_path)

        # Detect current CLI state from pane content
        try:
            window = session.windows[0]
            pane = window.panes[0]
            output = "\n".join(pane.cmd("capture-pane", "-p").stdout)

            busy_indicators = ["Thinking", "Running", "⏳"]

            if any(ind in output for ind in busy_indicators):
                persisted_record["state"] = "busy"
            elif harness.is_ready_output(output):
                persisted_record["state"] = "idle"
            # else: keep persisted state
        except Exception as e:
            logger.warning(f"Could not detect CLI state for {instance_id}: {e}")

        # Restore main_instance_id if this is the main orchestrator
        if persisted_record.get("name") == "main-orchestrator":
            self.main_instance_id = instance_id

        if self.logging_manager:
            self.logging_manager.log_audit_event(
                event_type="instance_reconnected",
                instance_id=instance_id,
                details={
                    "instance_name": persisted_record.get("name"),
                    "state": persisted_record.get("state"),
                },
            )

        logger.info(
            f"Reconnected instance {instance_id} in state '{persisted_record.get('state')}'"
        )
        self._save_state()
        return instance_id

    def recover_instance(self, persisted_record: dict[str, Any]) -> str:
        """Recover a persisted instance whose tmux session has died.

        Respawns with --continue to preserve conversation context.
        """
        instance_id = persisted_record["id"]
        workspace_dir = persisted_record.get("workspace_dir", "")

        # Verify workspace still exists
        ws_path = Path(workspace_dir)
        metadata_file = ws_path / ".madrox_instance_id"
        if not ws_path.exists() or not metadata_file.exists():
            raise RuntimeError(f"Workspace {workspace_dir} or metadata missing, cannot recover")

        # Restore instance record
        persisted_record["state"] = "initializing"
        persisted_record["retry_count"] = persisted_record.get("retry_count", 0) + 1
        self.instances[instance_id] = persisted_record
        self.message_history[instance_id] = []

        # Create response queue
        if self.shared_state:
            self.shared_state.create_response_queue(instance_id)
        else:
            self.response_queues[instance_id] = asyncio.Queue()

        # Schedule async recovery (tmux session creation needs to happen in background)
        asyncio.create_task(self._recover_instance_async(instance_id))

        self._save_state()
        return instance_id

    async def _recover_instance_async(self, instance_id: str) -> None:
        """Async recovery: create tmux session with --continue flag."""
        instance = self.instances.get(instance_id)
        if not instance:
            return

        try:
            await self._initialize_tmux_session_for_recovery(instance_id)
            instance["state"] = "idle"
            self._save_state()
            logger.info(f"Successfully recovered instance {instance_id} ({instance.get('name')})")

            if self.logging_manager:
                self.logging_manager.log_audit_event(
                    event_type="instance_recovered",
                    instance_id=instance_id,
                    details={
                        "instance_name": instance.get("name"),
                        "retry_count": instance.get("retry_count", 0),
                    },
                )
        except Exception as e:
            instance["state"] = "error"
            instance["error_message"] = f"Recovery failed: {e}"
            self._save_state()
            logger.error(f"Failed to recover instance {instance_id}: {e}", exc_info=True)

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
            }

    def get_all_instances(self) -> dict[str, dict[str, Any]]:
        """
        Get all instances (required by MonitoringService).

        Returns:
            Dict mapping instance_id to instance data
        """
        return {iid: inst.copy() for iid, inst in self.instances.items()}

    async def get_instance_output(self, instance_id: str, limit: int = 1000) -> dict[str, Any]:
        """
        Get recent output for an instance (required by MonitoringService).

        Args:
            instance_id: Instance ID
            limit: Maximum number of lines (default 1000)

        Returns:
            Dict with 'output' key containing recent output text
        """
        if instance_id not in self.instances:
            return {"output": ""}

        try:
            # Use get_tmux_pane_content to retrieve recent output
            output = await self.get_tmux_pane_content(instance_id, lines=limit)
            return {"output": output}
        except Exception as e:
            logger.warning(f"Failed to get output for instance {instance_id}: {e}")
            return {"output": ""}

    # ------------------------------------------------------------------
    # Tmux session startup
    # ------------------------------------------------------------------
    def _build_session_env(self) -> dict[str, str]:
        """Manager IPC credentials the child process needs to reach this daemon."""
        if not self.shared_state:
            return {}

        session_env: dict[str, str] = {}
        manager_address = self.shared_state.manager_address

        if isinstance(manager_address, tuple):
            manager_host, manager_port = manager_address
            session_env["MADROX_MANAGER_HOST"] = str(manager_host)
            session_env["MADROX_MANAGER_PORT"] = str(manager_port)
            location = f"TCP {manager_host}:{manager_port}"
        else:
            session_env["MADROX_MANAGER_SOCKET"] = str(manager_address)
            location = f"Unix socket {manager_address}"

        session_env["MADROX_MANAGER_AUTHKEY"] = base64.b64encode(
            self.shared_state.manager_authkey
        ).decode("ascii")

        # SECURITY FIX (CWE-532): never log the authkey itself.
        logger.debug(
            f"Manager IPC credentials for tmux session ({location}), "
            f"authkey={redact_authkey(self.shared_state.manager_authkey)}"
        )
        return session_env

    def _kill_existing_session(self, session_name: str) -> None:
        """Remove a stale tmux session with the same name, if any."""
        try:
            existing = self.tmux_server.find_where({"session_name": session_name})
            if existing:
                existing.kill_session()
                logger.debug(f"Killed existing session: {session_name}")
        except Exception as e:
            logger.debug(f"No existing session to clean up: {e}")

    @staticmethod
    def _export_session_env(session, pane, session_env: dict[str, str]) -> None:
        """Make the IPC credentials visible to the shell and its children.

        tmux session variables are not exported into the shell automatically, so
        they are both set on the session and exported in the pane.
        """
        if not session_env:
            return

        for key, value in session_env.items():
            try:
                session.set_environment(key, value)
            except Exception as e:
                logger.warning(f"Failed to set environment variable {key}: {e}")

        for key, value in session_env.items():
            pane.send_keys(f"export {key}={shlex.quote(value)}", enter=True)

        logger.debug(f"Exported {len(session_env)} environment variables to shell")

    async def _wait_for_cli_ready(
        self, pane, harness: type[Harness], max_wait: float = 10.0
    ) -> bool:
        """Poll the pane until the CLI is accepting input.

        Also answers the workspace-trust dialog, which otherwise blocks startup
        (and, for Codex, exits the CLI when it times out).

        Returns:
            True when a ready marker was seen before ``max_wait`` elapsed.
        """
        start = time.time()

        while time.time() - start < max_wait:
            await asyncio.sleep(0.15)
            output = "\n".join(pane.cmd("capture-pane", "-p").stdout)

            if harness.is_trust_prompt(output):
                pane.send_keys("1", enter=True)
                logger.debug("Auto-accepted workspace trust prompt")
                await asyncio.sleep(0.5)
                continue

            if harness.is_ready_output(output):
                logger.debug(f"{harness.label} CLI ready in {time.time() - start:.1f}s")
                return True

        logger.warning(
            f"{harness.label} CLI not detected as ready after {time.time() - start:.1f}s"
        )
        return False

    async def _initialize_tmux_session(self, instance_id: str) -> None:
        """Start a fresh CLI session for the instance."""
        await self._start_cli_session(instance_id, resume=False)

    async def _initialize_tmux_session_for_recovery(self, instance_id: str) -> None:
        """Recreate a session that resumes the instance's previous conversation."""
        await self._start_cli_session(instance_id, resume=True)

    async def _start_cli_session(self, instance_id: str, *, resume: bool) -> None:
        """Create the tmux session and launch the harness CLI inside it.

        Args:
            instance_id: Instance to start
            resume: Continue the instance's previous conversation instead of
                starting a new one (used by recovery and auto-resume)
        """
        instance = self.instances[instance_id]
        harness = get_harness(instance.get("instance_type"))
        session_name = f"madrox-{instance_id}"
        prefix = "Recovery: " if resume else ""

        logger.debug(f"{prefix}Creating tmux session: {session_name}")
        self._kill_existing_session(session_name)

        session_env = self._build_session_env()
        try:
            session = self.tmux_server.new_session(
                session_name=session_name,
                window_name=harness.name,
                start_directory=instance["workspace_dir"],
                x=160,
                y=50,
                environment=session_env or None,
            )
        except Exception as e:
            logger.error(f"Failed to create tmux session: {e}")
            raise

        self.tmux_sessions[instance_id] = session
        pane = session.windows[0].panes[0]

        self._export_session_env(session, pane, session_env)

        # MCP servers must be registered before the CLI starts; for Claude this
        # also records the config path consumed by the launch command.
        await self._configure_mcp_servers(pane, instance)

        # Harness-specific pre-launch setup (e.g. pre-trusting the workspace).
        harness.prepare_workspace(instance["workspace_dir"])

        cmd_parts = (
            harness.build_resume_command(instance)
            if resume
            else harness.build_launch_command(instance)
        )
        cmd = " ".join(cmd_parts)
        pane.send_keys(cmd, enter=True)
        logger.debug(f"{prefix}Started {harness.name} CLI in tmux session: {cmd}")

        cli_ready = await self._wait_for_cli_ready(pane, harness)

        if resume:
            # Conversation context comes back with the resume flags — sending the
            # bootstrap again would duplicate it.
            logger.info(
                f"Recovery: tmux session initialized for {harness.name} instance {instance_id}"
            )
            return

        await self._bootstrap_instance(pane, instance, harness, cli_ready)
        logger.info(f"Tmux session initialized for {harness.name} instance {instance_id}")

    # ------------------------------------------------------------------
    # First-contact bootstrap
    # ------------------------------------------------------------------
    async def _bootstrap_instance(
        self, pane, instance: dict[str, Any], harness: type[Harness], cli_ready: bool
    ) -> None:
        """Give a freshly started instance its identity and first prompt."""
        if harness.prompt_delivery == "cli_arg":
            # The initial prompt already went out as a command-line argument.
            # The system prompt rides along with the first user message, which
            # guarantees the CLI is fully ready for multiline input by then.
            await asyncio.sleep(0.15)
            if instance.get("system_prompt"):
                instance["_system_prompt_pending"] = True
                instance["_pending_system_prompt"] = self._build_system_prompt(instance)
                logger.debug("System prompt stored for sending with first user message")
            return

        # Pane-delivered harnesses type the bootstrap into the CLI, so it must
        # really be up — otherwise the text lands in the shell and executes.
        if not cli_ready:
            logger.warning(
                f"{harness.label} CLI not ready - waiting additional time before bootstrap"
            )
            cli_ready = await self._wait_for_cli_ready(pane, harness, max_wait=10.0)
            if not cli_ready:
                # Raise rather than return: the caller marks the instance failed
                # and reports it. Returning quietly left the spawn looking
                # healthy while every later message went to the bare shell.
                raise RuntimeError(
                    f"{harness.label} CLI failed to start within timeout - "
                    f"skipped bootstrap to avoid shell execution"
                )

        await asyncio.sleep(0.3)  # Brief settle time for input readiness

        bootstrap = f"SYSTEM INFORMATION:\n{self._build_identity_briefing(instance)}\n"

        # Pane-delivered harnesses have no --system-prompt flag, so role and
        # custom system prompts have to ride along with the briefing. Without
        # this they were accepted by spawn_* and then silently dropped.
        if role_instructions := self._pane_role_instructions(instance):
            bootstrap += f"\nYOUR ROLE AND INSTRUCTIONS:\n{role_instructions}\n"

        await self._send_multiline_message_to_pane(pane, bootstrap)
        logger.debug(f"Sent instance_id information to {harness.label} instance")
        await asyncio.sleep(2)  # Let the CLI process the briefing

        if initial_prompt := instance.get("initial_prompt"):
            baseline = "\n".join(pane.cmd("capture-pane", "-p", "-S", "-").stdout)
            pane.send_keys(initial_prompt, enter=True)
            logger.debug(f"Sent initial prompt to {harness.label} instance")
            await asyncio.sleep(2)
            # The backend can reject the request outright (unknown model, auth
            # failure). Nobody is waiting on a reply here, so scan the pane
            # ourselves — otherwise the spawn reports "spawned" and the error
            # is only ever visible to someone looking at the terminal.
            await self._record_bootstrap_error(pane, instance, baseline)

    @staticmethod
    def _reply_protocol_block(instance_id: str) -> str:
        """The reply_to_caller contract, shared by every harness."""
        return (
            f"RESPONDING TO MESSAGES:\n"
            f"When you receive messages formatted as:\n"
            f"  [MSG:correlation-id] message content here\n\n"
            f"You MUST use the reply_to_caller tool to respond:\n"
            f"  reply_to_caller(\n"
            f"    instance_id='{instance_id}',\n"
            f"    reply_message='your response here',\n"
            f"    correlation_id='correlation-id-from-message'\n"
            f"  )\n"
        )

    async def _record_bootstrap_error(
        self, pane, instance: dict[str, Any], baseline: str, max_wait: float = 8.0
    ) -> None:
        """Store any backend error the CLI printed in response to the first prompt.

        Polls briefly rather than checking once: a rejection round-trips through
        the backend, so it usually lands a second or two after the prompt.
        """
        deadline = time.monotonic() + max_wait
        while True:
            try:
                output = "\n".join(pane.cmd("capture-pane", "-p", "-S", "-").stdout)
            except Exception as e:  # pragma: no cover - pane vanished mid-spawn
                logger.debug(f"Could not capture pane for bootstrap error scan: {e}")
                return

            if error := self._detect_backend_error(output, baseline):
                instance["error_message"] = error
                logger.warning(
                    f"Backend error during spawn of {instance['id']}: {error}",
                    extra={"instance_id": instance["id"]},
                )
                return

            if time.monotonic() >= deadline:
                return
            await asyncio.sleep(0.5)

    @staticmethod
    def _pane_role_instructions(instance: dict[str, Any]) -> str | None:
        """Role / custom system prompt to type into a pane-delivered CLI.

        Returns None for a plain default instance, whose generic "helpful
        assistant" boilerplate carries no instruction worth spending the
        CLI's first turn on.
        """
        system_prompt = (instance.get("system_prompt") or "").strip()
        if not system_prompt:
            return None

        role = instance.get("role")
        if not instance.get("has_custom_prompt") and role in (None, "", "general"):
            return None

        return system_prompt

    def _build_identity_briefing(self, instance: dict[str, Any]) -> str:
        """Identity + messaging contract typed into pane-driven CLIs at startup."""
        workspace_path = instance["workspace_dir"]
        instance_id = instance["id"]

        briefing = (
            f"Your instance ID: {instance_id}\n"
            f"This ID is also stored in {workspace_path}/.madrox_instance_id\n"
        )

        if parent_id := instance.get("parent_instance_id"):
            briefing += (
                f"Your parent instance ID: {parent_id}\n"
                f"If send_to_instance is available, you can message your parent using: "
                f"send_to_instance(parent_instance_id='{parent_id}', message='your message')\n"
                f"\n{self._reply_protocol_block(instance_id)}"
                f"IMPORTANT: Simply outputting text will NOT deliver your response to the parent.\n"
                f"You must use reply_to_caller for the parent to receive your answer.\n"
            )
        else:
            briefing += (
                f"\nYou are a ROOT INSTANCE (spawned by the coordinator).\n"
                f"Your workspace: {workspace_path}\n\n"
                f"{self._reply_protocol_block(instance_id)}"
                f"This delivers your response instantly to the coordinator.\n"
            )

        return briefing

    def _build_system_prompt(self, instance: dict[str, Any]) -> str:
        """Assemble the deferred system prompt sent with the first user message."""
        instance_id = instance["id"]
        workspace_path = instance["workspace_dir"]
        has_custom_prompt = instance.get("has_custom_prompt", False)
        system_prompt = instance.get("system_prompt", "")

        prompt_prefix = "" if has_custom_prompt else "You are a specialized Claude instance. "

        instance_id_info = (
            f"\n\nYour instance ID: {instance_id}\n"
            f"This ID is also stored in {workspace_path}/.madrox_instance_id\n"
        )

        if parent_id := instance.get("parent_instance_id"):
            instance_id_info += (
                f"Your parent instance ID: {parent_id}\n"
                f"You can send messages to your parent using: "
                f"send_to_instance(parent_instance_id='{parent_id}', message='your message')\n"
                f"\nWhen spawning child instances, pass your instance_id as parent_instance_id:\n"
                f"  spawn_claude(name='child', role='general', parent_instance_id='{instance_id}')\n"
                f"This enables bidirectional communication between parent and child.\n\n"
                f"PERFORMANCE TIP: When spawning children, use timeout_seconds=10 for single instance spawns,\n"
                f"and timeout_seconds=20 for multiple instances (spawn_multiple_instances with 2+ children).\n\n"
                f"HIERARCHICAL MESSAGE PASSING PATTERN:\n"
                f"- Children send messages to you (their parent) using: send_to_instance(parent_instance_id='{instance_id}', message='...')\n"
                f"- You coordinate and decide how to route messages between children\n"
                f"- Use get_children(parent_id='{instance_id}') to see all your children\n"
                f"- Use broadcast_to_children(parent_id='{instance_id}', message='...') to message all children\n"
                f"- You control what information (IDs, tasks) flows up to your parent or down to your children\n\n"
                f"PEER-TO-PEER COMMUNICATION:\n"
                f"- Use get_peers(instance_id='{instance_id}') to discover your teammates (siblings with the same parent)\n"
                f"- Use send_to_instance(instance_id='peer_id', message='...') to message them directly\n"
                f"- Messages to busy peers are automatically queued and delivered when they become idle\n\n"
                f"BIDIRECTIONAL MESSAGING PROTOCOL:\n"
                f"When you receive messages from the coordinator or parent instance, they will be formatted as:\n"
                f"  [MSG:correlation-id] message content here\n\n"
                f"To respond efficiently using the bidirectional protocol, use the reply_to_caller tool:\n"
                f"  reply_to_caller(\n"
                f"    instance_id='{instance_id}',\n"
                f"    reply_message='your response here',\n"
                f"    correlation_id='correlation-id-from-message'\n"
                f"  )\n\n"
                f"Benefits of using reply_to_caller:\n"
                f"- Instant delivery (no polling delay)\n"
                f"- Proper request-response correlation\n"
                f"- More efficient than text output\n\n"
                f"If you don't use reply_to_caller, the system will fall back to polling your output (slower but works)."
            )
        else:
            instance_id_info += (
                f"\nYou are a ROOT INSTANCE (spawned by the coordinator).\n"
                f"Your workspace: {workspace_path}\n\n"
                f"{self._reply_protocol_block(instance_id)}"
                f"This delivers your response instantly to the coordinator.\n"
            )

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

        if instance.get("parent_instance_id"):
            bidirectional_instructions = (
                f"\n\n{'─' * 80}\n"
                f"BIDIRECTIONAL MESSAGING PROTOCOL (REQUIRED):\n"
                f"When you receive messages formatted as [MSG:correlation-id] content,\n"
                f"you MUST respond using the reply_to_caller tool:\n\n"
                f"  reply_to_caller(\n"
                f"    instance_id='{instance_id}',\n"
                f"    reply_message='your response here',\n"
                f"    correlation_id='correlation-id-from-message'\n"
                f"  )\n\n"
                f"IMPORTANT: Always use reply_to_caller for every response to messages.\n"
                f"This enables instant bidirectional communication and proper correlation.\n"
                f"{'─' * 80}\n"
            )
        else:
            bidirectional_instructions = ""

        return (
            f"{prompt_prefix}{system_prompt}"
            f"{workspace_info if not has_custom_prompt else ''}"
            f"{bidirectional_instructions}"
        )

    async def _send_multiline_message_to_pane(self, pane, message: str) -> None:
        """Send multiline message to tmux pane without triggering paste detection.

        Uses line-by-line send_keys with C-j (newline without submit) and adaptive timing.
        CRITICAL: Adds delay AFTER each send_keys call to prevent instant keystroke bursts.
        The pacing yields to the event loop, so a long message to one instance
        does not stall every other instance.

        Args:
            pane: libtmux pane object
            message: Message content (may contain newlines)
        """
        # Health check: verify Claude CLI is running (not at shell prompt)
        # Only check visible screen (not scroll buffer which contains export commands)
        pane_lines = pane.cmd("capture-pane", "-p").stdout
        visible_lines = pane_lines[-10:] if isinstance(pane_lines, list) else pane_lines
        pane_content = (
            "\n".join(visible_lines) if isinstance(visible_lines, list) else visible_lines
        )
        shell_indicators = ["zsh: ", "bash: "]
        if any(indicator in pane_content for indicator in shell_indicators):
            raise RuntimeError("Claude CLI has exited. Instance at shell prompt. Restart needed.")

        message_size_kb = len(message) / 1024
        lines = message.split("\n")
        total_lines = len(lines)

        # Adaptive timing based on message size
        # Values chosen to stay well above paste detection threshold (10-15ms)
        if message_size_kb >= 3.0:
            delay_per_keystroke = 0.020  # 20ms for large messages (50 keystrokes/sec)
        elif message_size_kb >= 1.0:
            delay_per_keystroke = 0.015  # 15ms for medium messages (67 keystrokes/sec)
        else:
            delay_per_keystroke = 0.010  # 10ms for small messages (100 keystrokes/sec)

        # Send each line with C-j between them (newline without submit)
        keystroke_count = 0
        for i, line in enumerate(lines):
            # Send the line content
            if line:  # Only send non-empty lines
                pane.send_keys(line, enter=False, literal=True)
                await asyncio.sleep(delay_per_keystroke)  # CRITICAL: Delay after line
                keystroke_count += 1

            # Add newline between lines (not after last line)
            if i < total_lines - 1:
                pane.send_keys("C-j", enter=False, literal=False)
                await asyncio.sleep(delay_per_keystroke)  # CRITICAL: Delay after C-j
                keystroke_count += 1

        # Small delay before Enter
        await asyncio.sleep(0.05)

        # Send Enter keystroke
        pane.send_keys("Enter", literal=False)

        total_time = keystroke_count * delay_per_keystroke
        logger.info(
            f"Sent message via send_keys: {len(message)} chars, {total_lines} lines, "
            f"{message_size_kb:.2f}KB, {keystroke_count} keystrokes, "
            f"{delay_per_keystroke * 1000:.1f}ms/keystroke, {total_time:.2f}s total"
        )

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
            # CRITICAL FIX: Skip instance validation for STDIO transport
            # STDIO subprocesses don't have instances in their local dict - only HTTP server does
            if not instance and not self.shared_state:
                return {"success": False, "error": f"Instance {instance_id} not found"}

            # Determine the caller (parent instance or coordinator)
            # For STDIO transport, parent_id may not be available locally
            parent_id = instance.get("parent_instance_id") if instance else None
            delivered_to = parent_id if parent_id else "coordinator"

            # Update message envelope if correlated
            if correlation_id:
                if self.shared_state:
                    try:
                        self.shared_state.update_message_status(
                            correlation_id,
                            status="replied",
                            reply_content=reply_message,
                            replied_at=datetime.now().isoformat(),
                        )
                    except KeyError:
                        # STDIO subprocess doesn't have access to parent's message registry
                        # This is expected - just log and continue with queueing the reply
                        logger.debug(
                            f"Message {correlation_id} not in local registry (STDIO subprocess), "
                            f"skipping status update"
                        )
                elif correlation_id in self.message_registry:
                    envelope = self.message_registry[correlation_id]
                    envelope.mark_replied(reply_message, datetime.now())

                logger.debug(f"Correlated reply to message {correlation_id}")

            # Queue the reply
            reply_payload = {
                "sender_id": instance_id,
                "reply_message": reply_message,
                "correlation_id": correlation_id,
                "timestamp": datetime.now().isoformat(),
            }

            if self.shared_state:
                # Use shared queue for STDIO transport
                target_id = parent_id if parent_id else "coordinator"
                await self._put_to_shared_queue(target_id, reply_payload)
                logger.info(f"Reply queued for {target_id} via shared queue")
                # Also queue in the child's own queue so send_message() can pick it up
                await self._put_to_shared_queue(instance_id, reply_payload)
                logger.debug(
                    f"Reply also queued in child {instance_id}'s queue for send_message pickup"
                )
            else:
                # Use local queue for HTTP transport
                if parent_id:
                    # Ensure parent's response queue exists
                    if parent_id not in self.response_queues:
                        self.response_queues[parent_id] = asyncio.Queue()
                        logger.debug(f"Created response queue for parent {parent_id}")
                    await self.response_queues[parent_id].put(reply_payload)
                    logger.info(f"Reply queued for parent instance {parent_id}")
                elif not parent_id:
                    # Reply to coordinator - use special coordinator queue
                    if "coordinator" not in self.response_queues:
                        self.response_queues["coordinator"] = asyncio.Queue()
                    await self.response_queues["coordinator"].put(reply_payload)
                    logger.info("Reply queued for coordinator")

                # Also queue in the child's own queue so send_message() can pick it up
                if instance_id not in self.response_queues:
                    self.response_queues[instance_id] = asyncio.Queue()
                await self.response_queues[instance_id].put(reply_payload)
                logger.debug(
                    f"Reply also queued in child {instance_id}'s queue for send_message pickup"
                )

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

    def _extract_response(
        self, full_output: str, initial_output: str, instance_id: str | None = None
    ) -> str:
        """Extract the new response from tmux pane output using baseline diff.

        Computes the diff between full_output and initial_output, then strips
        terminal chrome to get the actual response text.

        Args:
            full_output: Full scrollback after response
            initial_output: Baseline captured before message was sent
            instance_id: Target instance ID for message history lookup

        Returns:
            Cleaned response text
        """
        # Diff-based: only process lines added after the baseline
        initial_lines = initial_output.split("\n")
        full_lines = full_output.split("\n")

        # Find where new content starts — match the tail of initial output
        # in the full output to handle scrollback growth
        new_lines = full_lines
        if len(initial_lines) >= 3:
            anchor = initial_lines[-3:]
            for i in range(len(full_lines) - 2):
                if full_lines[i : i + 3] == anchor:
                    new_lines = full_lines[i + 3 :]
                    break

        # Strip terminal chrome from new content only
        content_lines = []
        for line in new_lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Claude UI chrome
            if stripped.startswith("╭") or stripped.startswith("╰") or stripped.startswith("─"):
                continue
            if stripped.startswith("│") and stripped.endswith("│"):
                content = stripped[1:-1].strip()
                if content:
                    content_lines.append(content)
                continue
            # Status bars
            if "%" in line and ("tokens" in line.lower() or "usage" in line.lower()):
                continue
            # CLI decorations
            if stripped.startswith("⏵⏵") or stripped.startswith("✻") or stripped.startswith("✳"):
                continue
            if stripped.startswith("✢") or stripped.startswith("·"):
                continue
            # Prompt lines
            if stripped == "❯" or stripped == "›":
                continue
            # Codex spinner lines
            if stripped.startswith("Working (") or stripped.startswith("Improve documentation"):
                continue
            # Tip lines
            if stripped.startswith("⎿  Tip:"):
                continue
            # Tool call lines (collapsed)
            if "Called madrox" in stripped or "ctrl+o to expand" in stripped:
                continue
            # MSG echo (the sent message)
            if stripped.startswith("[MSG:"):
                continue
            # Status line at bottom
            if "bypass permissions" in stripped or "esc to interrupt" in stripped:
                continue
            if "Context" in stripped and "left" in stripped:
                continue

            content_lines.append(line.rstrip())

        response = "\n".join(content_lines)
        response = re.sub(r"\n{3,}", "\n\n", response)
        return response.strip()

    # Codex marks error/warning lines in the pane with a leading glyph; model
    # response prose never does. We use that to gate the weaker, prose-like
    # patterns so a legitimate reply that merely mentions "rate limit" or
    # "does not exist" is not misread as a backend failure.
    _ERROR_GLYPHS = "■▲●⚠✖✗"

    # STRONG signatures: unambiguous backend/transport failures. Matched anywhere
    # on a new line — these phrasings do not occur in normal model output.
    _BACKEND_ERROR_STRONG = re.compile(
        r"unexpected status\s+[45]\d{2}"
        r"|\b[45]\d{2}\s+(?:not found|bad request|unauthorized|forbidden|"
        r"internal server error|bad gateway|service unavailable|too many requests)"
        r"|json-rpc error"
        r"|engine not found"
        r"|engine bad request"
        r"|task submission failed"
        r"|job registration failed"
        r"|model metadata for .* not found",
        re.IGNORECASE,
    )

    # WEAK signatures: prose-like phrases that also appear in legitimate replies.
    # Only treated as errors when the line is glyph-marked as a CLI error.
    _BACKEND_ERROR_WEAK = re.compile(
        r"does not exist"
        r"|stream error"
        r"|stream disconnected before completion"
        r"|\brate limit(?:ed)?\b"
        r"|\bquota exceeded\b",
        re.IGNORECASE,
    )

    def _detect_backend_error(self, output: str, initial_output: str | None = None) -> str | None:
        """Scan NEW tmux pane output for a backend/CLI error message.

        The interactive Codex/Claude CLIs surface backend failures (model 404s,
        JSON-RPC errors, stream errors, …) as lines in the terminal but produce
        no response text. Without scanning for them the MCP layer reports a
        silent "completed" with an empty response. This returns a concise error
        string when such a failure is found, else None.

        Only output produced *after* ``initial_output`` is considered, so error
        lines left in scrollback by previous messages are not re-detected.
        Strong backend signatures match anywhere on a new line; weaker prose-like
        phrases only count when the line is glyph-marked as a CLI error, to avoid
        false positives on legitimate model responses.

        Args:
            output: Raw tmux pane content to scan (full scrollback capture).
            initial_output: Baseline captured before the message was sent; only
                lines after this baseline are scanned. None scans everything.

        Returns:
            The detected error message (with any continuation/context line
            appended), or None if no backend error is present.
        """
        if not output:
            return None

        raw_lines = output.split("\n")

        # Restrict to lines added after the baseline, mirroring _extract_response.
        if initial_output:
            initial_lines = initial_output.split("\n")
            if len(initial_lines) >= 3:
                anchor = initial_lines[-3:]
                for i in range(len(raw_lines) - 2):
                    if raw_lines[i : i + 3] == anchor:
                        raw_lines = raw_lines[i + 3 :]
                        break

        for idx, raw_line in enumerate(raw_lines):
            line = raw_line.strip()
            if not line:
                continue
            glyph_marked = line[0] in self._ERROR_GLYPHS
            if self._BACKEND_ERROR_STRONG.search(line) or (
                glyph_marked and self._BACKEND_ERROR_WEAK.search(line)
            ):
                # Strip leading CLI status glyphs (Codex uses ■/▲/●, ⚠ etc.)
                cleaned = re.sub(rf"^[{self._ERROR_GLYPHS}•·\s]+", "", line).strip()
                # Append an immediately following indented continuation line
                # (e.g. the "url: https://…" that Codex prints under a 404)
                # so the error message keeps its context.
                if idx + 1 < len(raw_lines):
                    cont = raw_lines[idx + 1]
                    if cont.startswith((" ", "\t")) and cont.strip():
                        cleaned = f"{cleaned} {cont.strip()}"
                return cleaned
        return None

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

    async def health_check(self):
        """Perform health check on all instances."""
        logger.info("Performing health check on all instances")

        current_time = datetime.now(UTC)
        timeout_minutes = self.config.get("instance_timeout_minutes", 30)

        for instance_id, instance in list(self.instances.items()):
            if instance["state"] in ("terminated", "suspended"):
                continue

            # Check for timeout
            last_activity = datetime.fromisoformat(instance["last_activity"])
            # Ensure last_activity is timezone-aware (it should already have timezone from UTC)
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=UTC)
            if current_time - last_activity > timedelta(minutes=timeout_minutes):
                logger.warning(f"Instance {instance_id} timed out, suspending")
                await self.suspend_instance(instance_id)
                continue

            # Check resource limits
            max_tokens = instance.get("resource_limits", {}).get("max_total_tokens")
            if max_tokens and instance["total_tokens_used"] > max_tokens:
                logger.warning(f"Instance {instance_id} exceeded token limit, terminating")
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

    async def _queue_poller_loop(self):
        """Background loop that delivers queued messages to idle instances."""
        logger.info("Queue poller started (interval=2s)")
        while True:
            try:
                await asyncio.sleep(2)
                if not self.shared_state:
                    continue
                for instance_id, instance in list(self.instances.items()):
                    if instance["state"] == "idle" and self.shared_state.has_queued_messages(
                        instance_id
                    ):
                        logger.info(
                            f"Queue poller: delivering queued messages to idle instance {instance_id}"
                        )
                        await self._process_queued_messages(instance_id)
            except asyncio.CancelledError:
                logger.info("Queue poller stopped")
                break
            except Exception as e:
                logger.error(f"Queue poller error: {e}")

    def _start_manager_health_monitoring(self):
        """Start background task for manager health monitoring.

        This is called automatically during initialization if shared_state is available.
        """
        if not self.shared_state:
            logger.warning("Cannot start manager health monitoring without shared_state")
            return

        # Create task for periodic health checks
        self._manager_health_task = asyncio.create_task(self._manager_health_monitor_loop())
        logger.info(
            f"Manager health monitoring started (interval={self._manager_health_check_interval}s)"
        )

        # Start queue poller for delivering queued messages to idle instances
        self._queue_poller_task = asyncio.create_task(self._queue_poller_loop())

    async def _manager_health_monitor_loop(self):
        """Background loop that periodically checks Manager daemon health.

        This task runs continuously and checks the Manager daemon health every
        _manager_health_check_interval seconds. If the manager becomes unresponsive,
        it logs errors and eventually triggers graceful degradation.
        """
        logger.info("Manager health monitor loop started")

        while True:
            try:
                # Wait for the check interval
                await asyncio.sleep(self._manager_health_check_interval)

                # Skip health check if no shared_state (HTTP transport)
                if not self.shared_state:
                    continue

                # Perform health check
                health_result = self.shared_state.health_check(timeout=5.0)

                if health_result["healthy"]:
                    # Health check passed - reset failure counter
                    if self._manager_health_failures > 0:
                        logger.info(
                            f"Manager health recovered (was {self._manager_health_failures} failures)",
                            extra={"response_time_ms": health_result["response_time_ms"]},
                        )
                    self._manager_health_failures = 0
                    logger.debug(
                        f"Manager health check passed ({health_result['response_time_ms']}ms)"
                    )
                else:
                    # Health check failed
                    self._manager_health_failures += 1
                    logger.error(
                        f"Manager health check failed (failure {self._manager_health_failures}/{self._max_health_failures}): {health_result['error']}",
                        extra={
                            "manager_alive": health_result.get("manager_alive", False),
                            "error": health_result["error"],
                        },
                    )

                    # Check if we've exceeded failure threshold
                    if self._manager_health_failures >= self._max_health_failures:
                        logger.critical(
                            f"Manager daemon has failed {self._manager_health_failures} consecutive health checks - CRITICAL FAILURE",
                            extra={
                                "health_result": health_result,
                                "active_instances": len(
                                    [
                                        i
                                        for i in self.instances.values()
                                        if i["state"] not in ["terminated", "error"]
                                    ]
                                ),
                            },
                        )

                        # Trigger graceful degradation
                        await self._handle_manager_failure()

                        # Break the loop - manager is dead
                        break

            except asyncio.CancelledError:
                logger.info("Manager health monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in manager health monitor loop: {e}", exc_info=True)
                # Continue monitoring even if there's an error
                continue

        logger.info("Manager health monitor loop stopped")

    async def _handle_manager_failure(self):
        """Handle graceful degradation when Manager daemon dies.

        This method is called when the Manager daemon becomes unresponsive after
        multiple consecutive health check failures. It:
        1. Logs the critical failure
        2. Disables shared_state to prevent further IPC attempts
        3. Optionally terminates affected instances
        4. Provides error reporting
        """
        logger.critical("═" * 80)
        logger.critical("MANAGER DAEMON FAILURE DETECTED - INITIATING GRACEFUL DEGRADATION")
        logger.critical("═" * 80)

        if not self.shared_state:
            logger.warning("Manager already disabled")
            return

        # Count affected instances
        active_instances = [
            (iid, inst)
            for iid, inst in self.instances.items()
            if inst["state"] not in ["terminated", "error"]
        ]

        logger.critical(
            f"Manager daemon failure will affect {len(active_instances)} active instances",
            extra={"affected_instances": [iid for iid, _ in active_instances]},
        )

        # Disable shared_state to prevent further IPC attempts
        logger.warning("Disabling shared_state to prevent further IPC failures")
        self.shared_state = None

        # Log audit event if available
        if self.logging_manager:
            self.logging_manager.log_audit_event(
                event_type="manager_daemon_failure",
                instance_id="orchestrator",
                details={
                    "affected_instances_count": len(active_instances),
                    "affected_instances": [iid for iid, _ in active_instances],
                    "failure_reason": "Manager daemon unresponsive after multiple health checks",
                },
            )

        # Mark all affected instances with error
        for instance_id, instance in active_instances:
            instance["error_message"] = "Manager daemon died - bidirectional messaging unavailable"
            logger.error(
                f"Instance {instance_id} ({instance.get('name')}) affected by manager failure",
                extra={"instance_id": instance_id},
            )

        logger.critical(
            "Graceful degradation complete. System will continue with degraded functionality."
        )
        logger.critical("Bidirectional messaging and IPC features are now DISABLED.")
        logger.critical("═" * 80)

    async def stop_manager_health_monitoring(self):
        """Stop the manager health monitoring task.

        This should be called during shutdown to cleanly stop the background task.
        """
        if self._manager_health_task and not self._manager_health_task.done():
            logger.info("Stopping manager health monitoring")
            self._manager_health_task.cancel()
            try:
                await self._manager_health_task
            except asyncio.CancelledError:
                pass
            logger.info("Manager health monitoring stopped")

        if self._queue_poller_task and not self._queue_poller_task.done():
            logger.info("Stopping queue poller")
            self._queue_poller_task.cancel()
            try:
                await self._queue_poller_task
            except asyncio.CancelledError:
                pass
            logger.info("Queue poller stopped")

    # ── Git worktree helpers ─────────────────────────────────────────────

    async def _run_git_cmd(self, args: list[str], cwd: str) -> str | None:
        """Run a git command asynchronously and return stdout on success.

        Args:
            args: Git subcommand arguments (e.g. ["rev-parse", "--show-toplevel"]).
            cwd: Working directory for the command.

        Returns:
            Stripped stdout string on success, None on failure.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                *args,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return stdout.decode().strip()
            logger.debug(
                "git %s failed (rc=%s): %s",
                " ".join(args),
                proc.returncode,
                stderr.decode().strip(),
            )
        except Exception:
            logger.debug("git %s raised an exception", " ".join(args), exc_info=True)
        return None

    async def _detect_git_repo(self, parent_instance_id: str | None) -> str | None:
        """Detect the git repository root for an instance.

        Checks the parent instance's workspace first, then falls back to cwd.

        Args:
            parent_instance_id: Optional parent instance ID to inherit repo from.

        Returns:
            Absolute path to the git repo root, or None.
        """
        import os

        # Try parent workspace first
        if parent_instance_id and parent_instance_id in self.instances:
            parent_ws = self.instances[parent_instance_id].get("workspace_dir")
            if parent_ws:
                result = await self._run_git_cmd(["rev-parse", "--show-toplevel"], cwd=parent_ws)
                if result:
                    return result

        # Fallback to current working directory
        result = await self._run_git_cmd(["rev-parse", "--show-toplevel"], cwd=os.getcwd())
        return result

    async def _create_worktree(self, repo: str, target_dir: str, branch: str) -> bool:
        """Create a git worktree for an instance workspace.

        Args:
            repo: Path to the main git repository.
            target_dir: Destination directory for the worktree.
            branch: Branch name to create in the worktree.

        Returns:
            True on success, False on failure.
        """
        result = await self._run_git_cmd(
            ["-C", repo, "worktree", "add", target_dir, "-b", branch], cwd=repo
        )
        if result is not None:
            logger.info("Created worktree at %s on new branch %s", target_dir, branch)
            return True

        # Branch may already exist – try without -b
        result = await self._run_git_cmd(
            ["-C", repo, "worktree", "add", target_dir, branch], cwd=repo
        )
        if result is not None:
            logger.info("Created worktree at %s on existing branch %s", target_dir, branch)
            return True

        logger.warning("Failed to create worktree at %s for branch %s", target_dir, branch)
        return False

    async def _remove_worktree(self, instance: dict) -> None:
        """Remove a git worktree and its branch for a terminated instance.

        Args:
            instance: Instance dict containing workspace_dir, git_repo,
                      and git_worktree_branch keys.
        """
        workspace = instance.get("workspace_dir")
        repo = instance.get("git_repo")
        branch = instance.get("git_worktree_branch")

        if not (workspace and repo and branch):
            return

        # Remove the worktree
        result = await self._run_git_cmd(
            ["-C", repo, "worktree", "remove", workspace, "--force"], cwd=repo
        )
        if result is not None:
            logger.info("Removed worktree at %s", workspace)
        else:
            logger.warning("Failed to remove worktree at %s", workspace)

        # Clean up the branch (safe delete — refuses to delete unmerged branches)
        result = await self._run_git_cmd(["-C", repo, "branch", "-d", branch], cwd=repo)
        if result is not None:
            logger.info("Deleted branch %s", branch)
        else:
            logger.warning(
                "Worktree branch '%s' has unmerged changes and was preserved. "
                "Merge manually with: git merge %s",
                branch,
                branch,
            )

    @staticmethod
    def _sanitize_branch_name(name: str) -> str:
        """Convert an instance name to a valid git branch name.

        Lowercases the name, replaces non-alphanumeric/hyphen characters with
        hyphens, collapses consecutive hyphens, and strips leading/trailing
        hyphens.

        Args:
            name: Raw instance name.

        Returns:
            Sanitized branch name.
        """
        name = name.lower()
        name = re.sub(r"[^a-z0-9-]", "-", name)
        name = re.sub(r"-{2,}", "-", name)
        name = name.strip("-")
        return name
