"""Instance spawning MCP tools and helpers."""

import logging
import uuid
from pathlib import Path
from typing import Any

from ..config import resolve_model
from ._mcp import mcp

logger = logging.getLogger(__name__)


class SpawningMixin:
    """MCP tools for spawning harness instances (Claude, Codex, Grok)."""

    # Declared by InstanceManager; present here for type checking only
    instances: dict[str, dict[str, Any]]
    tmux_manager: Any
    spawn_instance: Any

    @staticmethod
    def _apply_response_status(result: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        """Fold a send_message reply into a spawn result.

        Surfaces a backend failure (non-null ``error``) as status "failed" with
        the message in ``error_message``; otherwise marks the spawn "completed".
        """
        result["response"] = response.get("response", "")
        error = response.get("error")
        if error:
            result["status"] = "failed"
            result["error_message"] = error
        else:
            result["status"] = "completed"
        return result

    async def _spawn_harness_instance(
        self,
        instance_type: str,
        name: str,
        model: str | None,
        initial_prompt: str | None,
        wait_for_response: bool,
        timeout_seconds: int,
        **spawn_kwargs: Any,
    ) -> dict[str, Any]:
        """Spawn one instance of any harness and shape the tool response.

        Shared by spawn_claude / spawn_codex / spawn_grok so every harness gets
        the same model-default resolution, response handling and result shape.
        """
        resolved_model = resolve_model(instance_type, model)

        # When the caller waits for the reply, the prompt is sent as a message
        # afterwards so the response can be captured.
        spawn_prompt = None if wait_for_response else initial_prompt

        instance_id = await self.spawn_instance(
            name=name,
            model=resolved_model,
            instance_type=instance_type,
            initial_prompt=spawn_prompt,
            **spawn_kwargs,
        )

        result: dict[str, Any] = {
            "instance_id": instance_id,
            "status": "spawned",
            "name": name,
            "instance_type": instance_type,
            "model": resolved_model,
        }

        if wait_for_response and initial_prompt:
            response = await self.tmux_manager.send_message(
                instance_id=instance_id,
                message=initial_prompt,
                wait_for_response=True,
                timeout_seconds=timeout_seconds,
            )
            self._apply_response_status(result, response)
        else:
            # Nobody waited for a reply, but the bootstrap may still have seen
            # the backend reject the request (unknown model, auth failure).
            # Report that instead of a misleading "spawned".
            spawn_error = (self.instances.get(instance_id) or {}).get("error_message")
            if spawn_error:
                result["status"] = "failed"
                result["error_message"] = spawn_error

        return result

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
        use_worktree: bool = False,
        git_repo: str | None = None,
        wait_for_response: bool = False,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        """Spawn a new Claude Code instance with specific role and configuration.

        Args:
            name: Instance name
            role: Predefined role for the instance
            system_prompt: Custom system prompt (overrides role)
            model: Claude model to use. Omit it to get the configured default
                   (config/models.yaml, currently claude-opus-5). Any model id
                   is accepted and forwarded to the CLI as-is — model names are
                   NOT checked against an allowlist, so newly released models
                   work without a Madrox update. If the CLI rejects the model,
                   the spawn returns status "failed" with the backend error in
                   error_message.
            bypass_isolation: Allow full filesystem access (default: true)
            parent_instance_id: Parent instance ID for tracking bidirectional communication
            wait_for_ready: Wait for instance to initialize (default: true)
            initial_prompt: Initial prompt to send as CLI argument (bypasses paste detection)
            mcp_servers: JSON string of MCP server configurations. Format:
                        '{"server_name": {"transport": "http", "url": "http://localhost:8002/mcp"}}'
            use_worktree: Create a git worktree for workspace isolation (default: false)
            git_repo: Path to git repository for worktree creation (required if use_worktree is true)
            wait_for_response: Wait for the initial_prompt response and return it (default: false).
                              When true and initial_prompt is provided, the response is captured
                              and included in the return value instead of fire-and-forget.
            timeout_seconds: Timeout for waiting for response (default: 180)

        Returns:
            Dictionary with instance_id, status and resolved model (and response
            when wait_for_response=True)
        """
        return await self._spawn_harness_instance(
            instance_type="claude",
            name=name,
            model=model,
            initial_prompt=initial_prompt,
            wait_for_response=wait_for_response,
            timeout_seconds=timeout_seconds,
            role=role,
            system_prompt=system_prompt,
            bypass_isolation=bypass_isolation,
            parent_instance_id=parent_instance_id,
            wait_for_ready=wait_for_ready,
            mcp_servers=mcp_servers,
            use_worktree=use_worktree,
            git_repo=git_repo,
        )

    @mcp.tool
    async def spawn_multiple_instances(
        self,
        instances: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Spawn multiple instances in parallel for better performance.

        Args:
            instances: List of instance configurations to spawn.
                       Each config supports: name, type ("claude", "codex" or
                       "grok"), role, system_prompt, model, initial_prompt,
                       bypass_isolation, sandbox_mode (codex only),
                       parent_instance_id, use_worktree, git_repo.
                       Omitting "model" uses that harness's configured default.

        Returns:
            Dictionary with spawned instance IDs and any errors
        """
        results: dict[str, list[Any]] = {"spawned": [], "errors": []}
        for instance_config in instances:
            try:
                # Map "type" to "instance_type" for spawn_instance()
                config = dict(instance_config)
                if "type" in config:
                    config["instance_type"] = config.pop("type")
                instance_id = await self.spawn_instance(**config)
                results["spawned"].append({"instance_id": instance_id, **instance_config})
            except Exception as e:
                results["errors"].append({"config": instance_config, "error": str(e)})
        return results

    @mcp.tool
    async def spawn_codex(
        self,
        name: str,
        model: str | None = None,
        sandbox_mode: str = "workspace-write",
        profile: str | None = None,
        initial_prompt: str | None = None,
        bypass_isolation: bool = True,
        parent_instance_id: str | None = None,
        mcp_servers: str | None = None,
        use_worktree: bool = False,
        git_repo: str | None = None,
        wait_for_response: bool = False,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        """Spawn a new Codex CLI instance (OpenAI GPT models).

        Runs with Codex's full-autonomy mode when bypass_isolation is true
        (--dangerously-bypass-approvals-and-sandbox).

        Args:
            name: Instance name
            model: OpenAI GPT model to use. Omit it to get the configured
                   default (config/models.yaml, currently gpt-5.6-sol). Any
                   model string is accepted and forwarded to the Codex CLI
                   as-is — Codex routes through a proxy whose valid model ids
                   change independently of Madrox, so model names are NOT
                   validated against an allowlist. If the backend does not
                   recognise the model, the spawn returns status "failed" with
                   the backend error in error_message (see
                   docs/TROUBLESHOOTING.md).
            sandbox_mode: Sandbox policy for shell commands (read-only, workspace-write, danger-full-access)
            profile: Configuration profile from config.toml
            initial_prompt: Initial prompt to start the session
            bypass_isolation: Allow full filesystem access
            parent_instance_id: Parent instance ID for tracking
            mcp_servers: JSON string of MCP server configurations. Format:
                        '{"server_name": {"transport": "http", "url": "http://localhost:8002/mcp"}}'
            use_worktree: Create a git worktree for workspace isolation (default: false)
            git_repo: Path to git repository for worktree creation (required if use_worktree is true)
            wait_for_response: Wait for the initial_prompt response and return it (default: false).
                              When true and initial_prompt is provided, the response is captured
                              and included in the return value instead of fire-and-forget.
            timeout_seconds: Timeout for waiting for response (default: 180)

        Returns:
            Dictionary with instance_id, status and resolved model (and response
            when wait_for_response=True)
        """
        return await self._spawn_harness_instance(
            instance_type="codex",
            name=name,
            model=model,
            initial_prompt=initial_prompt,
            wait_for_response=wait_for_response,
            timeout_seconds=timeout_seconds,
            bypass_isolation=bypass_isolation,
            sandbox_mode=sandbox_mode,
            profile=profile,
            parent_instance_id=parent_instance_id,
            mcp_servers=mcp_servers,
            use_worktree=use_worktree,
            git_repo=git_repo,
        )

    @mcp.tool
    async def spawn_grok(
        self,
        name: str,
        model: str | None = None,
        role: str = "general",
        system_prompt: str | None = None,
        initial_prompt: str | None = None,
        bypass_isolation: bool = True,
        parent_instance_id: str | None = None,
        mcp_servers: str | None = None,
        use_worktree: bool = False,
        git_repo: str | None = None,
        wait_for_response: bool = False,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        """Spawn a new Grok Build CLI instance (xAI Grok models).

        Runs with Grok's yolo mode when bypass_isolation is true
        (--always-approve, the flag behind the /yolo slash command), matching
        how Claude and Codex instances are launched.

        Args:
            name: Instance name
            model: Grok model to use. Omit it to get the configured default
                   (config/models.yaml, currently grok-build-0.1). Any model
                   string is accepted and forwarded to the Grok CLI as-is —
                   model names are NOT validated against an allowlist. If the
                   CLI does not recognise the model, the spawn returns status
                   "failed" with the backend error in error_message.
            role: Predefined role for the instance
            system_prompt: Custom system prompt (overrides role)
            initial_prompt: Initial prompt to start the session
            bypass_isolation: Allow full filesystem access / auto-approve tools
            parent_instance_id: Parent instance ID for tracking
            mcp_servers: JSON string of MCP server configurations. Format:
                        '{"server_name": {"transport": "http", "url": "http://localhost:8002/mcp"}}'
            use_worktree: Create a git worktree for workspace isolation (default: false)
            git_repo: Path to git repository for worktree creation (required if use_worktree is true)
            wait_for_response: Wait for the initial_prompt response and return it (default: false).
                              When true and initial_prompt is provided, the response is captured
                              and included in the return value instead of fire-and-forget.
            timeout_seconds: Timeout for waiting for response (default: 180)

        Returns:
            Dictionary with instance_id, status and resolved model (and response
            when wait_for_response=True)
        """
        return await self._spawn_harness_instance(
            instance_type="grok",
            name=name,
            model=model,
            initial_prompt=initial_prompt,
            wait_for_response=wait_for_response,
            timeout_seconds=timeout_seconds,
            role=role,
            system_prompt=system_prompt,
            bypass_isolation=bypass_isolation,
            parent_instance_id=parent_instance_id,
            mcp_servers=mcp_servers,
            use_worktree=use_worktree,
            git_repo=git_repo,
        )

    def list_persisted_instances(self) -> dict[str, Any]:
        """List all persisted instances from previous sessions that can be resumed.

        Returns instances whose workspace directories still exist, meaning their
        conversation context can be resumed with resume_instance.

        Returns:
            Dictionary with resumable instances and their metadata
        """
        state_store = self.tmux_manager.state_store
        if not state_store:
            return {"instances": [], "message": "State store not configured"}

        all_persisted = state_store.load_all()
        resumable = []

        for iid, record in all_persisted.items():
            workspace = record.get("workspace_dir", "")
            ws_exists = Path(workspace).exists() if workspace else False

            # Check if already active in current session
            already_active = iid in self.instances and self.instances[iid].get("state") not in (
                "terminated",
                "error",
            )

            resumable.append(
                {
                    "instance_id": iid,
                    "name": record.get("name"),
                    "role": record.get("role"),
                    "model": record.get("model"),
                    "state": record.get("state"),
                    "instance_type": record.get("instance_type", "claude"),
                    "created_at": record.get("created_at"),
                    "last_activity": record.get("last_activity"),
                    "workspace_dir": workspace,
                    "workspace_exists": ws_exists,
                    "can_resume": ws_exists and not already_active,
                    "already_active": already_active,
                }
            )

        return {
            "instances": resumable,
            "total": len(resumable),
            "resumable": len([r for r in resumable if r["can_resume"]]),
            "active": len([r for r in resumable if r["already_active"]]),
        }

    async def resume_instance(
        self,
        instance_id: str,
        name: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Resume a previous instance's conversation context in a new instance.

        Spawns a new Claude instance in the previous instance's workspace directory
        using --continue to pick up its full conversation history.

        Args:
            instance_id: ID of the previous instance to resume (from list_persisted_instances)
            name: Optional new name (defaults to previous name + "-resumed")
            model: Optional model override (defaults to previous instance's model)

        Returns:
            Dictionary with new instance_id and status
        """
        state_store = self.tmux_manager.state_store
        if not state_store:
            raise RuntimeError("State store not configured — cannot resume instances")

        all_persisted = state_store.load_all()
        if instance_id not in all_persisted:
            raise ValueError(
                f"Instance {instance_id} not found in persisted state. "
                f"Use list_persisted_instances to see available instances."
            )

        record = all_persisted[instance_id]
        workspace = record.get("workspace_dir", "")

        if not Path(workspace).exists():
            raise RuntimeError(
                f"Workspace {workspace} no longer exists — conversation context is lost"
            )

        # Check if already active
        if instance_id in self.instances and self.instances[instance_id].get("state") not in (
            "terminated",
            "error",
        ):
            raise RuntimeError(
                f"Instance {instance_id} is already active (state={self.instances[instance_id]['state']}). "
                f"Use send_to_instance to communicate with it directly."
            )

        resumed_name = name or f"{record.get('name', 'instance')}-resumed"
        resumed_model = model or record.get("model")

        # Generate new UUID so the resumed instance has its own identity
        new_id = str(uuid.uuid4())
        new_record = dict(record)
        new_record["id"] = new_id
        new_record["name"] = resumed_name
        new_record["retry_count"] = record.get("retry_count", 0)
        new_record["resumed_from"] = instance_id
        if resumed_model:
            new_record["model"] = resumed_model

        recovered_id = self.tmux_manager.recover_instance(new_record)
        self.instances[recovered_id] = self.tmux_manager.instances[recovered_id]

        return {
            "instance_id": recovered_id,
            "name": resumed_name,
            "status": "resuming",
            "resumed_from": instance_id,
            "workspace_dir": workspace,
            "message": "Resuming conversation context from previous instance. "
            "The instance will be ready shortly with full conversation history.",
        }
