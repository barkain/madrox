"""Test Codex MCP configuration."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.orchestrator.tmux_instance_manager import TmuxInstanceManager


def test_codex_mcp_configuration():
    """Test that Codex instances configure MCP servers using `codex mcp add` commands."""
    config = {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}

    manager = TmuxInstanceManager(config)

    # Create a mock instance with Playwright config (Codex type)
    instance = {
        "id": "test-codex-instance",
        "workspace_dir": Path(config["workspace_base_dir"]) / "test-codex-instance",
        "instance_type": "codex",
        "enable_madrox": False,
        "mcp_servers": {"playwright": {"command": "npx", "args": ["@playwright/mcp@latest"]}},
    }

    instance["workspace_dir"].mkdir(parents=True, exist_ok=True)

    # Mock pane to capture send_keys calls
    mock_pane = MagicMock()
    sent_commands = []

    def capture_command(cmd, enter=False):
        sent_commands.append(cmd)

    mock_pane.send_keys = capture_command

    # Run the configuration
    manager._configure_mcp_servers(mock_pane, instance)

    # Verify `codex mcp add` command was sent
    assert len(sent_commands) == 1
    command = sent_commands[0]

    # Should contain: codex mcp add playwright npx @playwright/mcp@latest
    assert "codex mcp add playwright npx @playwright/mcp@latest" in command

    # Verify NO config file was created for Codex
    config_file = instance["workspace_dir"] / ".claude_mcp_config.json"
    assert not config_file.exists(), "Codex should not create Claude-style JSON config file"

    # Verify _mcp_config_path was NOT set for Codex
    assert "_mcp_config_path" not in instance


def test_codex_mcp_with_env_vars():
    """Test Codex MCP configuration with environment variables."""
    config = {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}

    manager = TmuxInstanceManager(config)

    instance = {
        "id": "test-codex-github",
        "workspace_dir": Path(config["workspace_base_dir"]) / "test-codex-github",
        "instance_type": "codex",
        "enable_madrox": False,
        "mcp_servers": {
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "test_token_123"},
            }
        },
    }

    instance["workspace_dir"].mkdir(parents=True, exist_ok=True)

    mock_pane = MagicMock()
    sent_commands = []
    mock_pane.send_keys = lambda cmd, enter=False: sent_commands.append(cmd)

    manager._configure_mcp_servers(mock_pane, instance)

    assert len(sent_commands) == 1
    command = sent_commands[0]

    # Should contain env var
    assert "codex mcp add github npx -y @modelcontextprotocol/server-github" in command
    assert "--env GITHUB_PERSONAL_ACCESS_TOKEN=test_token_123" in command


def test_codex_http_mcp_warning():
    """Test that Codex logs a warning for HTTP MCP servers (not supported yet)."""
    config = {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}

    manager = TmuxInstanceManager(config)

    instance = {
        "id": "test-codex-http",
        "workspace_dir": Path(config["workspace_base_dir"]) / "test-codex-http",
        "instance_type": "codex",
        "enable_madrox": True,  # This will try to add HTTP Madrox server
        "mcp_servers": {},
    }

    instance["workspace_dir"].mkdir(parents=True, exist_ok=True)

    mock_pane = MagicMock()
    sent_commands = []
    mock_pane.send_keys = lambda cmd, enter=False: sent_commands.append(cmd)

    # Run configuration (HTTP Madrox will be skipped with a warning)
    manager._configure_mcp_servers(mock_pane, instance)

    # Should not send any commands (HTTP not supported for Codex)
    assert len(sent_commands) == 0


def test_claude_still_uses_json_config():
    """Verify that Claude instances still use JSON config files."""
    config = {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}

    manager = TmuxInstanceManager(config)

    # Claude instance (not Codex)
    instance = {
        "id": "test-claude-instance",
        "workspace_dir": Path(config["workspace_base_dir"]) / "test-claude-instance",
        "instance_type": "claude",
        "enable_madrox": False,
        "mcp_servers": {"playwright": {"command": "npx", "args": ["@playwright/mcp@latest"]}},
    }

    instance["workspace_dir"].mkdir(parents=True, exist_ok=True)

    mock_pane = MagicMock()

    manager._configure_mcp_servers(mock_pane, instance)

    # Verify config file WAS created for Claude
    config_file = instance["workspace_dir"] / ".claude_mcp_config.json"
    assert config_file.exists(), "Claude should create JSON config file"

    # Verify _mcp_config_path WAS set
    assert "_mcp_config_path" in instance
    assert instance["_mcp_config_path"] == str(config_file)
