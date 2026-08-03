"""Unit tests for the harness registry (Claude / Codex / Grok)."""

import shlex

import pytest

from orchestrator.config import _load_model_config, resolve_model
from orchestrator.harnesses import (
    ClaudeHarness,
    CodexHarness,
    GrokHarness,
    get_harness,
    harness_names,
    is_supported_harness,
    normalize_harness_name,
)


@pytest.fixture(autouse=True)
def _clear_config_cache(monkeypatch):
    """Each test sees the repository config, not a cached or overridden one."""
    for var in (
        "MADROX_MODELS_CONFIG",
        "MADROX_MODEL_CLAUDE",
        "MADROX_MODEL_CODEX",
        "MADROX_MODEL_GROK",
        "MADROX_CLAUDE_BIN",
        "MADROX_CODEX_BIN",
        "MADROX_GROK_BIN",
    ):
        monkeypatch.delenv(var, raising=False)
    _load_model_config.cache_clear()
    yield
    _load_model_config.cache_clear()


class TestRegistry:
    def test_registered_harnesses(self):
        assert harness_names() == ["claude", "codex", "grok"]

    def test_lookup_by_name(self):
        assert get_harness("claude") is ClaudeHarness
        assert get_harness("codex") is CodexHarness
        assert get_harness("grok") is GrokHarness

    def test_lookup_defaults_to_claude(self):
        assert get_harness(None) is ClaudeHarness

    def test_aliases_and_case(self):
        assert get_harness("GROK") is GrokHarness
        assert get_harness("grok-build") is GrokHarness
        assert get_harness("claude-code") is ClaudeHarness
        assert normalize_harness_name(" Codex ") == "codex"

    def test_unknown_harness_raises_with_options(self):
        with pytest.raises(ValueError) as exc:
            get_harness("gemini")
        assert "gemini" in str(exc.value)
        assert "claude, codex, grok" in str(exc.value)

    def test_is_supported_harness(self):
        assert is_supported_harness("codex")
        assert is_supported_harness("grok")
        assert not is_supported_harness("gemini")
        assert is_supported_harness(None)  # unset instance_type -> claude


class TestModelDefaults:
    """No model is pinned: omit one and the CLI picks. A hardcoded id goes
    stale the moment the vendor ships a new model, and a stale id does not
    degrade — it breaks spawning."""

    def test_no_model_is_pinned_by_default(self):
        assert ClaudeHarness.default_model() is None
        assert CodexHarness.default_model() is None
        assert GrokHarness.default_model() is None

    def test_explicit_model_passes_through(self):
        assert resolve_model("claude", "some-model-shipped-tomorrow") == (
            "some-model-shipped-tomorrow"
        )
        assert resolve_model("grok", "grok-9") == "grok-9"

    def test_blank_model_is_treated_as_unset(self):
        assert resolve_model("codex", "   ") is None
        assert resolve_model("codex", None) is None

    def test_configured_default_is_still_honoured(self, monkeypatch, tmp_path):
        """Operators can still pin one deliberately."""
        config = tmp_path / "models.yaml"
        config.write_text("codex:\n  default: gpt-5.5\n")
        monkeypatch.setenv("MADROX_MODELS_CONFIG", str(config))
        _load_model_config.cache_clear()

        assert resolve_model("codex", None) == "gpt-5.5"

    def test_env_override_wins_over_yaml(self, monkeypatch):
        monkeypatch.setenv("MADROX_MODEL_GROK", "grok-5-fast")
        assert GrokHarness.default_model() == "grok-5-fast"

    def test_unknown_harness_has_no_default(self):
        assert resolve_model("gemini", None) is None


class TestLaunchCommands:
    """Every harness launches in its own full-autonomy (yolo) mode."""

    def test_claude_launch_uses_yolo_flags_and_default_model(self):
        cmd = ClaudeHarness.build_launch_command({"bypass_isolation": True})
        assert "--permission-mode" in cmd
        assert "bypassPermissions" in cmd
        assert "--dangerously-skip-permissions" in cmd
        # No model requested -> no flag, so the CLI uses its own current default.
        assert "--model" not in cmd

    def test_claude_launch_honours_explicit_model_and_prompt(self):
        cmd = ClaudeHarness.build_launch_command(
            {"model": "claude-sonnet-5", "initial_prompt": "hi there"}
        )
        assert cmd[cmd.index("--model") + 1] == "claude-sonnet-5"
        assert cmd[-1] == "'hi there'"

    def test_claude_resume_continues_conversation(self):
        cmd = ClaudeHarness.build_resume_command({})
        assert cmd[1] == "--continue"
        assert "--dangerously-skip-permissions" in cmd

    def test_codex_launch_bypasses_approvals_when_isolated(self):
        cmd = CodexHarness.build_launch_command({"bypass_isolation": True})
        assert "--dangerously-bypass-approvals-and-sandbox" in cmd
        assert "--model" not in cmd

    def test_codex_launch_uses_sandbox_when_not_bypassing(self):
        cmd = CodexHarness.build_launch_command(
            {"bypass_isolation": False, "sandbox_mode": "workspace-write"}
        )
        assert "--dangerously-bypass-approvals-and-sandbox" not in cmd
        assert cmd[cmd.index("--sandbox") + 1] == "workspace-write"

    def test_codex_resume_uses_resume_last(self):
        cmd = CodexHarness.build_resume_command({"bypass_isolation": False})
        assert cmd[1:3] == ["resume", "--last"]
        # -a never and the bypass flag are mutually exclusive
        assert "-a" in cmd and "--dangerously-bypass-approvals-and-sandbox" not in cmd

    def test_grok_launch_uses_yolo_flag_and_no_pinned_model(self):
        cmd = GrokHarness.build_launch_command({"bypass_isolation": True})
        assert "--always-approve" in cmd
        assert "-m" not in cmd

    def test_grok_uses_the_short_model_flag(self):
        """Grok documents `-m` only. `--model` was not picked up, so the CLI
        silently ran its own default model instead of the requested one —
        a wrong-model failure with no error to point at it."""
        cmd = GrokHarness.build_launch_command({"model": "grok-4.5"})
        assert "-m" in cmd
        assert "--model" not in cmd

    def test_grok_explicit_model_reaches_the_command(self):
        cmd = GrokHarness.build_launch_command({"model": "grok-4.3"})
        assert cmd[cmd.index("-m") + 1] == "grok-4.3"

    def test_grok_launch_without_bypass_has_no_yolo_flag(self):
        cmd = GrokHarness.build_launch_command({"bypass_isolation": False})
        assert "--always-approve" not in cmd

    def test_grok_resume_continues_last_session(self):
        cmd = GrokHarness.build_resume_command({"bypass_isolation": True})
        assert cmd[1] == "--resume"
        assert "--always-approve" in cmd

    def test_extra_args_from_config(self, monkeypatch, tmp_path):
        config = tmp_path / "models.yaml"
        config.write_text(
            "grok:\n  default: grok-test\n  command: /opt/grok\n  extra_args: ['--verbose']\n"
        )
        monkeypatch.setenv("MADROX_MODELS_CONFIG", str(config))
        _load_model_config.cache_clear()

        cmd = GrokHarness.build_launch_command({"bypass_isolation": True})
        assert cmd[0] == "/opt/grok"
        assert cmd[cmd.index("-m") + 1] == "grok-test"
        assert cmd[-1] == "--verbose"

    def test_binary_env_override(self, monkeypatch):
        monkeypatch.setenv("MADROX_GROK_BIN", "/usr/local/bin/grok-build")
        assert GrokHarness.executable() == "/usr/local/bin/grok-build"


class TestShellQuoting:
    """Command parts are joined with spaces and run by a shell (core.py:2013),
    so operator-supplied config values must survive that round trip intact."""

    def test_extra_args_keep_multiword_values_as_one_argv(self, monkeypatch, tmp_path):
        config = tmp_path / "models.yaml"
        config.write_text("grok:\n  extra_args: ['--rules', 'Use pytest only']\n")
        monkeypatch.setenv("MADROX_MODELS_CONFIG", str(config))
        _load_model_config.cache_clear()

        joined = " ".join(GrokHarness.extra_args())
        assert joined == "--rules 'Use pytest only'"
        assert shlex.split(joined) == ["--rules", "Use pytest only"]

    def test_executable_path_with_spaces_stays_one_argv(self, monkeypatch):
        monkeypatch.setenv("MADROX_GROK_BIN", "/opt/my tools/grok")
        _load_model_config.cache_clear()

        executable = GrokHarness.executable()
        assert shlex.split(executable) == ["/opt/my tools/grok"]


class TestMcpRegistration:
    def test_claude_uses_a_json_config_file(self):
        assert ClaudeHarness.mcp_config_filename == ".claude_mcp_config.json"
        assert ClaudeHarness.mcp_add_stdio_command("s", "npx", [], {}) is None

    def test_codex_registers_stdio_servers_via_cli(self):
        cmd = CodexHarness.mcp_add_stdio_command(
            "github", "npx", ["-y", "server-github"], {"TOKEN": "abc"}
        )
        joined = " ".join(cmd)
        assert "mcp add github npx -y server-github" in joined
        assert "--env TOKEN=abc" in joined

    def test_codex_http_servers_go_to_config_toml(self):
        assert CodexHarness.mcp_add_http_command("madrox", "http://x/mcp") is None
        assert CodexHarness.mcp_http_config_path().name == "config.toml"

    def test_grok_registers_both_transports_via_cli(self):
        # Per https://docs.x.ai/build/features/mcp-servers the stdio form takes
        # no transport flag and separates the server command with `--`.
        stdio = " ".join(GrokHarness.mcp_add_stdio_command("db", "npx", ["srv"], {"K": "v"}))
        assert "mcp add --scope project db -- " in stdio
        assert "-t stdio" not in stdio
        # Grok has no CLI flag for env vars, so they ride in via `env`.
        assert "env K=v npx srv" in stdio

        http = " ".join(GrokHarness.mcp_add_http_command("madrox", "http://localhost:8001/mcp"))
        assert "mcp add --scope project --transport http madrox http://localhost:8001/mcp" in http

    def test_grok_stdio_omits_env_wrapper_when_no_env(self):
        stdio = " ".join(GrokHarness.mcp_add_stdio_command("db", "npx", ["srv"], {}))
        assert stdio.endswith("mcp add --scope project db -- npx srv")


class TestTerminalMarkers:
    def test_claude_idle_detection_ignores_status_bar(self):
        assert ClaudeHarness.is_idle_line("❯")
        assert not ClaudeHarness.is_idle_line("⏵⏵ bypass permissions")

    def test_codex_and_grok_idle_detection(self):
        assert CodexHarness.is_idle_line("›")
        assert GrokHarness.is_idle_line("›")
        assert not GrokHarness.is_idle_line("Thinking...")

    def test_trust_prompt_detection(self):
        assert ClaudeHarness.is_trust_prompt("Yes, I trust this folder\nNo, exit")
        assert not ClaudeHarness.is_trust_prompt("Yes, I trust this folder")
        assert CodexHarness.is_trust_prompt("Do you trust the contents?\n1. Yes\n2. No")
