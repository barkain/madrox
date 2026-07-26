"""Harness registry — one place that knows how each CLI agent is driven.

A *harness* is an interactive coding CLI that Madrox drives inside a tmux
session (Claude Code, Codex, Grok Build, ...).  Everything that differs
between them — executable name, full-autonomy ("yolo") flags, how a model is
selected, how a previous conversation is resumed, how MCP servers are
registered, and which terminal markers mean "ready" or "idle" — lives here so
the manager code stays harness-agnostic.

Adding a harness means adding one subclass and one registry entry; no
``if instance_type == ...`` branches anywhere else.

Model selection is deliberately unconstrained: model ids are never validated
against an allowlist, because vendors ship new models constantly.  When a
caller does not name a model, the harness default from ``config/models.yaml``
is used (overridable per harness with ``MADROX_MODEL_<HARNESS>``).
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
from pathlib import Path
from typing import Any, ClassVar

from .config import get_harness_config, resolve_model

logger = logging.getLogger(__name__)


class Harness:
    """Describes how to launch and talk to one CLI agent.

    Subclasses override the command builders; the shared behaviour (binary
    resolution, model resolution, readiness markers) is data-driven.
    """

    #: Registry key / ``instance_type`` value.
    name: ClassVar[str] = ""
    #: Human-readable label used in logs and tool descriptions.
    label: ClassVar[str] = ""
    #: Executable looked up on PATH when no override is configured.
    binary: ClassVar[str] = ""
    #: Flag used to select a model (``--model <id>``).
    model_flag: ClassVar[str] = "--model"

    #: Substrings that mean "the CLI finished booting and accepts input".
    ready_indicators: ClassVar[tuple[str, ...]] = ()
    #: Substrings that, on the *last* content line, mean "waiting for input".
    idle_indicators: ClassVar[tuple[str, ...]] = ()
    #: Bare prompt characters that make up an idle prompt line on their own.
    bare_prompt_chars: ClassVar[tuple[str, ...]] = ()
    #: Marker pairs (all must be present) that identify a workspace-trust prompt.
    trust_prompt_markers: ClassVar[tuple[tuple[str, ...], ...]] = ()

    #: "cli_arg" -> initial prompt is passed on the command line;
    #: "pane" -> it is typed into the pane once the CLI is ready.
    prompt_delivery: ClassVar[str] = "pane"
    #: Transport used for the auto-injected "madrox" MCP server.
    auto_mcp_transport: ClassVar[str] = "http"
    #: When set, MCP servers are written to this JSON file and passed with
    #: ``mcp_config_flag``; otherwise they are registered via CLI commands.
    mcp_config_filename: ClassVar[str | None] = None
    mcp_config_flag: ClassVar[str] = "--mcp-config"

    # ------------------------------------------------------------------
    # Binary / model resolution
    # ------------------------------------------------------------------
    @classmethod
    def executable(cls) -> str:
        """Resolve the executable to run.

        Precedence: ``MADROX_<NAME>_BIN`` env var, ``command:`` in
        ``config/models.yaml``, PATH lookup, then the bare binary name (so the
        failure surfaces from the shell with a useful message).
        """
        override = os.getenv(f"MADROX_{cls.name.upper()}_BIN") or get_harness_config(cls.name).get(
            "command"
        )
        if override:
            return str(override)
        return shutil.which(cls.binary) or cls.binary

    @classmethod
    def default_model(cls) -> str | None:
        """Configured default model for this harness (None if unset)."""
        return resolve_model(cls.name, None)

    @classmethod
    def extra_args(cls) -> list[str]:
        """Operator-supplied flags appended to every launch (from YAML)."""
        extra = get_harness_config(cls.name).get("extra_args") or []
        if isinstance(extra, str):
            return shlex.split(extra)
        return [str(arg) for arg in extra]

    # ------------------------------------------------------------------
    # Command construction
    # ------------------------------------------------------------------
    @classmethod
    def build_launch_command(cls, instance: dict[str, Any]) -> list[str]:
        """Build the argv for a fresh session."""
        raise NotImplementedError

    @classmethod
    def build_resume_command(cls, instance: dict[str, Any]) -> list[str]:
        """Build the argv for resuming the instance's previous conversation."""
        raise NotImplementedError

    @classmethod
    def _model_args(cls, instance: dict[str, Any]) -> list[str]:
        model = instance.get("model") or cls.default_model()
        return [cls.model_flag, shlex.quote(model)] if model else []

    # ------------------------------------------------------------------
    # MCP registration
    # ------------------------------------------------------------------
    @classmethod
    def mcp_add_stdio_command(
        cls, name: str, command: str, args: list[str], env: dict[str, str]
    ) -> list[str] | None:
        """CLI command registering a stdio MCP server (None if unsupported)."""
        return None

    @classmethod
    def mcp_add_http_command(cls, name: str, url: str) -> list[str] | None:
        """CLI command registering an HTTP MCP server (None if unsupported)."""
        return None

    @classmethod
    def mcp_http_config_path(cls) -> Path | None:
        """TOML config file used for HTTP MCP servers when there is no CLI verb."""
        return None

    # ------------------------------------------------------------------
    # Terminal markers
    # ------------------------------------------------------------------
    @classmethod
    def is_ready_output(cls, output: str) -> bool:
        return any(indicator in output for indicator in cls.ready_indicators)

    @classmethod
    def is_idle_line(cls, last_line: str) -> bool:
        return last_line in cls.bare_prompt_chars or any(
            indicator in last_line for indicator in cls.idle_indicators
        )

    @classmethod
    def is_trust_prompt(cls, output: str) -> bool:
        return any(
            all(marker in output for marker in marker_set)
            for marker_set in cls.trust_prompt_markers
        )

    @classmethod
    def prepare_workspace(cls, workspace_dir: str) -> None:
        """Hook for pre-launch workspace setup (e.g. pre-trusting a directory)."""
        return None


class ClaudeHarness(Harness):
    """Anthropic Claude Code CLI."""

    name = "claude"
    label = "Claude Code"
    binary = "claude"

    ready_indicators = (
        'Try "',
        "⏵⏵",
        "bypass permissions",
        "What would you like",
        "How can I help",
    )
    # Only the bare "❯" means idle — "⏵⏵"/"bypass permissions" are status-bar
    # text that is visible at all times, including while thinking.
    idle_indicators = ('Try "', "What would you like", "How can I help")
    bare_prompt_chars = ("❯",)
    trust_prompt_markers = (("Yes, I trust this folder", "No, exit"),)

    prompt_delivery = "cli_arg"
    auto_mcp_transport = "http"
    mcp_config_filename = ".claude_mcp_config.json"

    #: Full-autonomy flags (Claude's equivalent of yolo mode).
    yolo_flags: ClassVar[tuple[str, ...]] = (
        "--permission-mode",
        "bypassPermissions",
        "--dangerously-skip-permissions",
    )
    #: Load only project/local settings so the parent's statusline is not inherited.
    isolation_flags: ClassVar[tuple[str, ...]] = ("--setting-sources", "local,project")

    @classmethod
    def _base_command(cls, instance: dict[str, Any]) -> list[str]:
        cmd = [cls.executable(), *cls.yolo_flags]
        if mcp_config_path := instance.get("_mcp_config_path"):
            cmd.extend([cls.mcp_config_flag, shlex.quote(str(mcp_config_path))])
        cmd.extend(cls.isolation_flags)
        cmd.extend(cls._model_args(instance))
        cmd.extend(cls.extra_args())
        return cmd

    @classmethod
    def build_launch_command(cls, instance: dict[str, Any]) -> list[str]:
        cmd = cls._base_command(instance)
        # Claude accepts the first prompt as a positional argument, which
        # avoids the terminal paste-detection heuristics entirely.
        if initial_prompt := instance.get("initial_prompt"):
            cmd.append(shlex.quote(initial_prompt))
        return cmd

    @classmethod
    def build_resume_command(cls, instance: dict[str, Any]) -> list[str]:
        cmd = cls._base_command(instance)
        cmd.insert(1, "--continue")
        return cmd


class CodexHarness(Harness):
    """OpenAI Codex CLI."""

    name = "codex"
    label = "Codex"
    binary = "codex"

    ready_indicators = ("codex>", "Working on:", "Thinking...", "OpenAI Codex", "›")
    idle_indicators = ("codex>",)
    bare_prompt_chars = ("›",)
    trust_prompt_markers = (
        ("Do you trust", "Yes"),
        ("trust", "No, quit"),
    )

    prompt_delivery = "pane"
    auto_mcp_transport = "stdio"

    #: Codex's yolo switch — bypasses both approvals and the sandbox.
    yolo_flags: ClassVar[tuple[str, ...]] = ("--dangerously-bypass-approvals-and-sandbox",)

    @classmethod
    def _autonomy_args(cls, instance: dict[str, Any], *, resuming: bool) -> list[str]:
        if instance.get("bypass_isolation"):
            return list(cls.yolo_flags)
        if resuming:
            # `-a never` and the bypass flag are mutually exclusive.
            return ["-a", "never"]
        if sandbox_mode := instance.get("sandbox_mode"):
            return ["--sandbox", shlex.quote(str(sandbox_mode))]
        return []

    @classmethod
    def build_launch_command(cls, instance: dict[str, Any]) -> list[str]:
        cmd = [cls.executable(), *cls._autonomy_args(instance, resuming=False)]
        if profile := instance.get("profile"):
            cmd.extend(["--profile", shlex.quote(str(profile))])
        cmd.extend(cls._model_args(instance))
        cmd.extend(cls.extra_args())
        return cmd

    @classmethod
    def build_resume_command(cls, instance: dict[str, Any]) -> list[str]:
        # `resume --last` picks the most recent session in this workspace.
        cmd = [cls.executable(), "resume", "--last"]
        cmd.extend(cls._autonomy_args(instance, resuming=True))
        cmd.extend(cls._model_args(instance))
        cmd.extend(cls.extra_args())
        return cmd

    @classmethod
    def mcp_add_stdio_command(
        cls, name: str, command: str, args: list[str], env: dict[str, str]
    ) -> list[str]:
        cmd = [cls.executable(), "mcp", "add", shlex.quote(name), shlex.quote(command)]
        cmd.extend(shlex.quote(str(arg)) for arg in args)
        for key, value in env.items():
            cmd.extend(["--env", shlex.quote(f"{key}={value}")])
        return cmd

    @classmethod
    def mcp_http_config_path(cls) -> Path:
        # Codex has no `mcp add` verb for HTTP servers — they live in config.toml.
        return Path.home() / ".codex" / "config.toml"

    @classmethod
    def prepare_workspace(cls, workspace_dir: str) -> None:
        """Pre-trust the workspace so Codex does not open a blocking prompt.

        The trust dialog defaults to "No, quit"; if it is answered wrongly the
        CLI exits and the bootstrap text leaks into the shell.
        """
        from .toml_config import update_toml_config

        # macOS resolves /tmp -> /private/tmp, so trust both spellings.
        keys = {str(workspace_dir), str(Path(workspace_dir).resolve())}

        def _trust(config: dict[str, Any]) -> bool:
            projects = config.setdefault("projects", {})
            changed = False
            for key in keys:
                if key not in projects:
                    projects[key] = {"trust_level": "trusted"}
                    changed = True
            return changed

        if update_toml_config(cls.mcp_http_config_path(), _trust):
            logger.info(f"Pre-trusted Codex workspace: {keys}")


class GrokHarness(Harness):
    """xAI Grok Build CLI."""

    name = "grok"
    label = "Grok Build"
    binary = "grok"

    ready_indicators = ("grok>", "Grok Build", "GROK BUILD", "›", "❯")
    idle_indicators = ("grok>",)
    bare_prompt_chars = ("›", "❯")
    trust_prompt_markers = (
        ("Do you trust", "Yes"),
        ("trust this", "Yes"),
    )

    prompt_delivery = "pane"
    auto_mcp_transport = "http"

    #: Grok's yolo switch — the CLI flag behind the `/yolo` slash command.
    yolo_flags: ClassVar[tuple[str, ...]] = ("--always-approve",)

    @classmethod
    def _base_command(cls, instance: dict[str, Any]) -> list[str]:
        cmd = [cls.executable()]
        if instance.get("bypass_isolation", True):
            cmd.extend(cls.yolo_flags)
        cmd.extend(cls._model_args(instance))
        cmd.extend(cls.extra_args())
        return cmd

    @classmethod
    def build_launch_command(cls, instance: dict[str, Any]) -> list[str]:
        return cls._base_command(instance)

    @classmethod
    def build_resume_command(cls, instance: dict[str, Any]) -> list[str]:
        cmd = cls._base_command(instance)
        # `--resume` without a value continues the most recent session.
        cmd.insert(1, "--resume")
        return cmd

    @classmethod
    def mcp_add_stdio_command(
        cls, name: str, command: str, args: list[str], env: dict[str, str]
    ) -> list[str]:
        # --scope project keeps the registration inside the instance workspace.
        cmd = [
            cls.executable(),
            "mcp",
            "add",
            "--scope",
            "project",
            "-t",
            "stdio",
            shlex.quote(name),
            shlex.quote(command),
        ]
        cmd.extend(shlex.quote(str(arg)) for arg in args)
        for key, value in env.items():
            cmd.extend(["-e", shlex.quote(f"{key}={value}")])
        return cmd

    @classmethod
    def mcp_add_http_command(cls, name: str, url: str) -> list[str]:
        return [
            cls.executable(),
            "mcp",
            "add",
            "--scope",
            "project",
            "-t",
            "http",
            shlex.quote(name),
            shlex.quote(url),
        ]


_HARNESS_CLASSES: tuple[type[Harness], ...] = (ClaudeHarness, CodexHarness, GrokHarness)

HARNESSES: dict[str, type[Harness]] = {harness.name: harness for harness in _HARNESS_CLASSES}

#: Friendly spellings accepted wherever an instance type is given.
HARNESS_ALIASES: dict[str, str] = {
    "claude_code": "claude",
    "claude-code": "claude",
    "anthropic": "claude",
    "codex_cli": "codex",
    "openai": "codex",
    "grok_build": "grok",
    "grok-build": "grok",
    "xai": "grok",
}

DEFAULT_HARNESS = ClaudeHarness.name


def normalize_harness_name(instance_type: str | None) -> str:
    """Map an instance type (or alias) to a canonical harness name."""
    if not instance_type:
        return DEFAULT_HARNESS
    key = str(instance_type).strip().lower()
    return HARNESS_ALIASES.get(key, key)


def get_harness(instance_type: str | None) -> type[Harness]:
    """Look up the harness for an instance type.

    Raises:
        ValueError: If the instance type is not a supported harness.
    """
    key = normalize_harness_name(instance_type)
    harness = HARNESSES.get(key)
    if harness is None:
        raise ValueError(
            f"Unsupported instance type: {instance_type!r}. "
            f"Supported harnesses: {', '.join(sorted(HARNESSES))}"
        )
    return harness


def is_supported_harness(instance_type: str | None) -> bool:
    """True when the instance type maps to a registered harness."""
    return normalize_harness_name(instance_type) in HARNESSES


def harness_names() -> list[str]:
    """Sorted list of registered harness names."""
    return sorted(HARNESSES)
