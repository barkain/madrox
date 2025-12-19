"""Test Codex MCP configuration."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from orchestrator.tmux_instance_manager import TmuxInstanceManager


def test_codex_mcp_configuration():
    """Test that Codex instances configure MCP servers using `codex mcp add` commands."""
    config = {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}

    manager = TmuxInstanceManager(config)

    # Create a mock instance with Playwright config (Codex type)
    instance = {
        "id": "test-codex-instance",
        "workspace_dir": Path(config["workspace_base_dir"]) / "test-codex-instance",
        "instance_type": "codex",
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

    # Verify `codex mcp add` commands were sent (playwright + madrox)
    assert len(sent_commands) == 2, (
        f"Expected 2 commands (playwright + madrox), got {len(sent_commands)}: {sent_commands}"
    )

    # First command should be playwright
    assert "codex mcp add playwright npx @playwright/mcp@latest" in sent_commands[0]

    # Second command should be madrox (always added)
    assert "codex mcp add madrox" in sent_commands[1]

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

    # Should have 2 commands: github + madrox (always added)
    assert len(sent_commands) == 2, (
        f"Expected 2 commands (github + madrox), got {len(sent_commands)}: {sent_commands}"
    )

    # First command should be github with env var
    assert "codex mcp add github npx -y @modelcontextprotocol/server-github" in sent_commands[0]
    assert "--env GITHUB_PERSONAL_ACCESS_TOKEN=test_token_123" in sent_commands[0]

    # Second command should be madrox (always added)
    assert "codex mcp add madrox" in sent_commands[1]


def test_codex_madrox_stdio_support():
    """Test that Codex instances get Madrox via stdio transport (not HTTP)."""
    config = {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}

    manager = TmuxInstanceManager(config)

    instance = {
        "id": "test-codex-madrox",
        "workspace_dir": Path(config["workspace_base_dir"]) / "test-codex-madrox",
        "instance_type": "codex",
        "mcp_servers": {},  # Madrox is always added via stdio transport
    }

    instance["workspace_dir"].mkdir(parents=True, exist_ok=True)

    mock_pane = MagicMock()
    sent_commands = []
    mock_pane.send_keys = lambda cmd, enter=False: sent_commands.append(cmd)

    # Run configuration - Madrox should be added via stdio
    manager._configure_mcp_servers(mock_pane, instance)

    # Should send 1 command for Madrox via stdio transport
    assert len(sent_commands) == 1, (
        f"Expected 1 command (madrox stdio), got {len(sent_commands)}: {sent_commands}"
    )
    assert "codex mcp add madrox" in sent_commands[0]
    assert "MADROX_TRANSPORT=stdio" in sent_commands[0]


def test_claude_still_uses_json_config():
    """Verify that Claude instances still use JSON config files. Madrox is always included."""
    config = {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}

    manager = TmuxInstanceManager(config)

    # Claude instance (not Codex)
    instance = {
        "id": "test-claude-instance",
        "workspace_dir": Path(config["workspace_base_dir"]) / "test-claude-instance",
        "instance_type": "claude",
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
