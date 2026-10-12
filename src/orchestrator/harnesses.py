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

import toml

from .config import get_harness_config, resolve_model

logger = logging.getLogger(__name__)


def _toml_value(value: Any) -> str:
    """Serialize one value exactly as Codex's ``-c key=value`` parser expects."""
    assignment = toml.dumps({"value": value}).strip()
    return assignment.split("=", 1)[1].strip()


def _merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Return Codex-style recursively merged config values."""
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


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

        The result is shell-quoted: every caller joins the command parts with
        spaces and hands the string to a shell, so an operator-supplied path
        containing spaces would otherwise split into several argv words.
        """
        override = os.getenv(f"MADROX_{cls.name.upper()}_BIN") or get_harness_config(cls.name).get(
            "command"
        )
        if override:
            return shlex.quote(str(override))
        return shlex.quote(shutil.which(cls.binary) or cls.binary)

    @classmethod
    def default_model(cls) -> str | None:
        """Configured default model for this harness (None if unset)."""
        return resolve_model(cls.name, None)

    @classmethod
    def extra_args(cls) -> list[str]:
        """Operator-supplied flags appended to every launch (from YAML).

        Each argument is shell-quoted so that a value which is one logical
        argv entry stays one: ``extra_args: ["--rules", "Use pytest only"]``
        must not become four words once the parts are joined for the shell.
        """
        extra = get_harness_config(cls.name).get("extra_args") or []
        if isinstance(extra, str):
            return [shlex.quote(arg) for arg in shlex.split(extra)]
        return [shlex.quote(str(arg)) for arg in extra]

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

    @classmethod
    def mcp_launch_overrides(
        cls, instance: dict[str, Any], mcp_servers: dict[str, Any]
    ) -> list[str] | None:
        """Return process-local config values for MCP servers, if supported.

        A non-None result tells the manager that this harness carries the MCP
        configuration on its launch command and needs no registration side
        effects before startup.
        """
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

    @classmethod
    def launch_environment(cls, instance: dict[str, Any]) -> dict[str, str]:
        """Environment values that must match this harness's inspected config."""
        return {}


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
    def _mcp_config_args(cls, instance: dict[str, Any]) -> list[str]:
        return [
            argument
            for override in instance.get("_mcp_launch_overrides", [])
            for argument in ("-c", shlex.quote(override))
        ]

    @classmethod
    def build_launch_command(cls, instance: dict[str, Any]) -> list[str]:
        cmd = [
            cls.executable(),
            *cls._mcp_config_args(instance),
            *cls._autonomy_args(instance, resuming=False),
        ]
        if profile := instance.get("profile"):
            cmd.extend(["--profile", shlex.quote(str(profile))])
        cmd.extend(cls._model_args(instance))
        cmd.extend(cls.extra_args())
        return cmd

    @classmethod
    def build_resume_command(cls, instance: dict[str, Any]) -> list[str]:
        # `resume --last` picks the most recent session in this workspace.
        cmd = [cls.executable(), "resume", "--last"]
        cmd.extend(cls._mcp_config_args(instance))
        if profile := instance.get("profile"):
            cmd.extend(["--profile", shlex.quote(str(profile))])
        cmd.extend(cls._autonomy_args(instance, resuming=True))
        cmd.extend(cls._model_args(instance))
        cmd.extend(cls.extra_args())
        return cmd

    @classmethod
    def mcp_launch_overrides(
        cls, instance: dict[str, Any], mcp_servers: dict[str, Any]
    ) -> list[str]:
        """Encode MCP servers as launch-scoped Codex ``-c`` overrides.

        Codex merges these values with the user's config in memory, preserving
        authentication, defaults, and unrelated personal MCP servers.  Unlike
        ``codex mcp add``, this never mutates the shared config.toml.
        """
        cls._reject_unsafe_mcp_collisions(instance, mcp_servers)
        overrides: list[str] = []
        for name, config in mcp_servers.items():
            transport = config.get("transport", "stdio" if "command" in config else "http")
            supported_connection = (
                {"command", "args", "env"} if transport == "stdio" else {"url", "bearer_token"}
            )
            connection_fields = {
                "command",
                "args",
                "env",
                "env_vars",
                "cwd",
                "url",
                "bearer_token",
                "bearer_token_env_var",
                "http_headers",
                "env_http_headers",
            }
            unsupported = sorted(
                key
                for key in config
                if key in connection_fields and key not in supported_connection
            )
            if unsupported:
                raise ValueError(
                    f"Codex MCP server '{name}' includes unsupported launch-scoped settings "
                    f"({', '.join(unsupported)}); the shared Codex config was not changed."
                )
            prefix = f"mcp_servers.{name}"
            overrides.append(f"{prefix}.enabled={_toml_value(True)}")
            if transport == "stdio":
                command = config.get("command")
                if not command:
                    raise ValueError(f"MCP server '{name}' has no stdio command")
                args = config.get("args", [])
                args = args if isinstance(args, list) else [args]
                overrides.append(f"{prefix}.command={_toml_value(str(command))}")
                overrides.append(f"{prefix}.args={_toml_value([str(arg) for arg in args])}")
                for key, value in (config.get("env", {}) or {}).items():
                    overrides.append(f"{prefix}.env.{key}={_toml_value(str(value))}")
            elif transport == "http":
                url = config.get("url")
                if not url:
                    raise ValueError(f"MCP server '{name}' has no HTTP URL")
                overrides.append(f"{prefix}.url={_toml_value(str(url))}")
                if bearer_token := config.get("bearer_token"):
                    overrides.append(f"{prefix}.bearer_token={_toml_value(str(bearer_token))}")
            else:
                raise ValueError(f"MCP server '{name}' uses unsupported transport '{transport}'")
        return overrides

    @classmethod
    def _reject_unsafe_mcp_collisions(
        cls, instance: dict[str, Any], mcp_servers: dict[str, Any]
    ) -> None:
        """Reject collisions whose stale connection fields survive Codex's deep merge."""
        config_path = cls.mcp_http_config_path()
        config_paths = [config_path]
        if profile := instance.get("profile"):
            if Path(str(profile)).name != str(profile):
                raise ValueError(f"Invalid Codex profile name '{profile}'")
            config_paths.append(config_path.with_name(f"{profile}.config.toml"))

        existing: dict[str, Any] = {}
        for path in config_paths:
            try:
                document = toml.load(path) if path.exists() else {}
            except (OSError, toml.TomlDecodeError):
                continue
            entries = document.get("mcp_servers", {})
            if isinstance(entries, dict):
                existing = _merge_dicts(existing, entries)

        connection_keys = {
            "command",
            "args",
            "env",
            "env_vars",
            "cwd",
            "url",
            "bearer_token",
            "bearer_token_env_var",
            "http_headers",
            "env_http_headers",
        }
        for name, desired in mcp_servers.items():
            current = existing.get(name)
            if not isinstance(current, dict):
                continue
            desired_transport = desired.get(
                "transport", "stdio" if "command" in desired else "http"
            )
            current_transport = "stdio" if "command" in current else "http"
            if desired_transport != current_transport:
                raise ValueError(
                    f"Codex MCP server '{name}' is already configured as {current_transport}, "
                    f"so a process-local {desired_transport} override cannot replace it safely. "
                    "Rename the child server or align its transport; the shared Codex config "
                    "was not changed."
                )
            supported_keys = (
                {"command", "args", "env"}
                if desired_transport == "stdio"
                else {"url", "bearer_token"}
            )
            unsupported = sorted(
                key for key in desired if key in connection_keys and key not in supported_keys
            )
            if unsupported:
                raise ValueError(
                    f"Codex MCP server '{name}' includes unsupported launch-scoped settings "
                    f"({', '.join(unsupported)}); the shared Codex config was not changed."
                )
            effective = _merge_dicts(current, desired)
            desired_connection = {
                key: value for key, value in desired.items() if key in supported_keys
            }
            effective_connection = {
                key: value for key, value in effective.items() if key in connection_keys
            }
            if effective_connection != desired_connection:
                retained = sorted(
                    key
                    for key, value in effective_connection.items()
                    if desired_connection.get(key) != value
                )
                raise ValueError(
                    f"Codex MCP server '{name}' has existing connection settings "
                    f"({', '.join(retained)}) that a process-local override cannot remove safely. "
                    "Rename the child server or remove the stale settings; the shared Codex config "
                    "was not changed."
                )

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
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        return codex_home / "config.toml"

    @classmethod
    def launch_environment(cls, instance: dict[str, Any]) -> dict[str, str]:
        # Pin the child to the exact config root inspected for collision safety.
        return {"CODEX_HOME": str(cls.mcp_http_config_path().parent)}

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

    #: Grok documents the short form only (`grok -p "Hello" -m my-model`); the
    #: inherited `--model` was not picked up, so the CLI silently used its own
    #: default model instead of the requested one.
    model_flag: ClassVar[str] = "-m"

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
        # Grok's stdio form takes no transport flag and needs a `--` separator
        # before the server command:
        #   grok mcp add [--scope project] <name> -- <command> [args...]
        # --scope project keeps the registration inside the instance workspace.
        cmd = [
            cls.executable(),
            "mcp",
            "add",
            "--scope",
            "project",
            shlex.quote(name),
            "--",
        ]
        if env:
            # Grok has no CLI flag for env vars (they live in config.toml), so
            # run the server under `env` rather than dropping them. A bare
            # `KEY=value cmd` would not work: the registered command is exec'd
            # as argv, not interpreted by a shell.
            cmd.append("env")
            cmd.extend(shlex.quote(f"{key}={value}") for key, value in env.items())
        cmd.append(shlex.quote(command))
        cmd.extend(shlex.quote(str(arg)) for arg in args)
        return cmd

    @classmethod
    def mcp_add_http_command(cls, name: str, url: str) -> list[str]:
        return [
            cls.executable(),
            "mcp",
            "add",
            "--scope",
            "project",
            "--transport",
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
