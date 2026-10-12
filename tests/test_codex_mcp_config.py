"""Test Codex MCP configuration."""

import shlex
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.harnesses import CodexHarness
from orchestrator.tmux_instance_manager import TmuxInstanceManager


@pytest.fixture(autouse=True)
def isolated_codex_home(monkeypatch, tmp_path):
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    return codex_home


def config_overrides(command: list[str]) -> list[str]:
    argv = shlex.split(" ".join(command))
    return [argv[index + 1] for index, value in enumerate(argv) if value == "-c"]


@pytest.mark.asyncio
async def test_codex_mcp_configuration():
    """Codex MCP servers are attached to the child process, not registered globally."""
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
    await manager._configure_mcp_servers(mock_pane, instance)

    assert sent_commands == []
    overrides = config_overrides(CodexHarness.build_launch_command(instance))
    assert 'mcp_servers.playwright.command="npx"' in overrides
    assert 'mcp_servers.playwright.args=[ "@playwright/mcp@latest",]' in overrides
    assert "mcp_servers.playwright.enabled=true" in overrides
    assert any(value.startswith('mcp_servers.madrox.command="') for value in overrides)
    assert "mcp_servers.madrox.enabled=true" in overrides

    # Verify NO config file was created for Codex
    config_file = instance["workspace_dir"] / ".claude_mcp_config.json"
    assert not config_file.exists(), "Codex should not create Claude-style JSON config file"

    # Codex carries the configuration on its own launch command.
    assert "_mcp_config_path" not in instance
    assert instance["_mcp_launch_overrides"]


@pytest.mark.asyncio
async def test_codex_mcp_with_env_vars():
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

    await manager._configure_mcp_servers(mock_pane, instance)

    assert sent_commands == []
    overrides = instance["_mcp_launch_overrides"]
    assert 'mcp_servers.github.command="npx"' in overrides
    assert 'mcp_servers.github.args=[ "-y", "@modelcontextprotocol/server-github",]' in overrides
    assert 'mcp_servers.github.env.GITHUB_PERSONAL_ACCESS_TOKEN="test_token_123"' in overrides


@pytest.mark.asyncio
async def test_codex_madrox_stdio_support():
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
    await manager._configure_mcp_servers(mock_pane, instance)

    assert sent_commands == []
    overrides = instance["_mcp_launch_overrides"]
    assert 'mcp_servers.madrox.env.MADROX_TRANSPORT="stdio"' in overrides
    assert any(
        value == 'mcp_servers.madrox.env.MADROX_PARENT_URL="http://localhost:8001"'
        for value in overrides
    )


@pytest.mark.asyncio
async def test_codex_launch_and_resume_use_same_http_and_stdio_overrides(tmp_path):
    manager = TmuxInstanceManager(
        {"workspace_base_dir": str(tmp_path / "workspaces"), "max_concurrent_instances": 10}
    )
    instance = {
        "id": "mixed-transports",
        "workspace_dir": tmp_path / "workspaces" / "mixed-transports",
        "instance_type": "codex",
        "profile": "review",
        "mcp_servers": {
            "remote-api": {"transport": "http", "url": "https://mcp.example.test/a?x=1"},
            "local_tool": {
                "transport": "stdio",
                "command": "/opt/Tools With Spaces/server",
                "args": ["--label", 'a "quoted" value'],
                "env": {"SAFE_TOKEN": 'value with "quotes"'},
            },
        },
    }
    instance["workspace_dir"].mkdir(parents=True)
    pane = MagicMock()

    await manager._configure_mcp_servers(pane, instance)

    launch = config_overrides(CodexHarness.build_launch_command(instance))
    resume = config_overrides(CodexHarness.build_resume_command(instance))
    assert launch == resume == instance["_mcp_launch_overrides"]
    assert "--profile" in shlex.split(" ".join(CodexHarness.build_launch_command(instance)))
    assert "--profile" in shlex.split(" ".join(CodexHarness.build_resume_command(instance)))
    assert 'mcp_servers.remote-api.url="https://mcp.example.test/a?x=1"' in launch
    assert 'mcp_servers.local_tool.command="/opt/Tools With Spaces/server"' in launch
    assert 'mcp_servers.local_tool.args=[ "--label", "a \\"quoted\\" value",]' in launch
    assert 'mcp_servers.local_tool.env.SAFE_TOKEN="value with \\"quotes\\""' in launch
    pane.send_keys.assert_not_called()


@pytest.mark.asyncio
async def test_codex_children_keep_parent_urls_process_local(monkeypatch, tmp_path):
    instances = []
    for index, port in enumerate((8101, 8202), start=1):
        monkeypatch.setenv("ORCHESTRATOR_PORT", str(port))
        manager = TmuxInstanceManager(
            {
                "workspace_base_dir": str(tmp_path / f"workspaces-{index}"),
                "max_concurrent_instances": 10,
            }
        )
        instance = {
            "id": f"child-{index}",
            "workspace_dir": tmp_path / f"workspaces-{index}" / f"child-{index}",
            "instance_type": "codex",
            "mcp_servers": {},
        }
        instance["workspace_dir"].mkdir(parents=True)
        await manager._configure_mcp_servers(MagicMock(), instance)
        instances.append(instance)

    first = instances[0]["_mcp_launch_overrides"]
    second = instances[1]["_mcp_launch_overrides"]
    assert 'mcp_servers.madrox.env.MADROX_PARENT_URL="http://localhost:8101"' in first
    assert 'mcp_servers.madrox.env.MADROX_PARENT_URL="http://localhost:8202"' in second
    assert not any("8202" in value for value in first)
    assert not any("8101" in value for value in second)


@pytest.mark.asyncio
async def test_codex_mcp_setup_preserves_shared_config(isolated_codex_home, tmp_path):
    config_path = isolated_codex_home / "config.toml"
    original = (
        'model = "personal-default"\n[mcp_servers.personal]\nurl = "https://personal.test/mcp"\n'
    )
    config_path.write_text(original)
    manager = TmuxInstanceManager(
        {"workspace_base_dir": str(tmp_path / "workspaces"), "max_concurrent_instances": 10}
    )
    instance = {
        "id": "no-global-mutation",
        "workspace_dir": tmp_path / "workspaces" / "no-global-mutation",
        "instance_type": "codex",
        "mcp_servers": {},
    }
    instance["workspace_dir"].mkdir(parents=True)
    pane = MagicMock()

    with patch("orchestrator.tmux_instance_manager.core.update_toml_config") as update:
        await manager._configure_mcp_servers(pane, instance)

    assert config_path.read_text() == original
    update.assert_not_called()
    pane.send_keys.assert_not_called()
    assert "personal" not in "\n".join(instance["_mcp_launch_overrides"])


@pytest.mark.asyncio
async def test_codex_rejects_incompatible_existing_transport(isolated_codex_home, tmp_path):
    config_path = isolated_codex_home / "config.toml"
    original = '[mcp_servers.madrox]\nurl = "https://personal.test/mcp"\n'
    config_path.write_text(original)
    manager = TmuxInstanceManager(
        {"workspace_base_dir": str(tmp_path / "workspaces"), "max_concurrent_instances": 10}
    )
    instance = {
        "id": "transport-collision",
        "workspace_dir": tmp_path / "workspaces" / "transport-collision",
        "instance_type": "codex",
        "mcp_servers": {},
    }
    instance["workspace_dir"].mkdir(parents=True)
    pane = MagicMock()

    with pytest.raises(ValueError, match="process-local stdio override cannot replace it safely"):
        await manager._configure_mcp_servers(pane, instance)

    assert config_path.read_text() == original
    pane.send_keys.assert_not_called()


@pytest.mark.asyncio
async def test_codex_checks_selected_profile_for_transport_collisions(
    isolated_codex_home, tmp_path
):
    (isolated_codex_home / "review.config.toml").write_text(
        '[mcp_servers.madrox]\nurl = "https://profile.test/mcp"\n'
    )
    manager = TmuxInstanceManager(
        {"workspace_base_dir": str(tmp_path / "workspaces"), "max_concurrent_instances": 10}
    )
    instance = {
        "id": "profile-collision",
        "workspace_dir": tmp_path / "workspaces" / "profile-collision",
        "instance_type": "codex",
        "profile": "review",
        "mcp_servers": {},
    }
    instance["workspace_dir"].mkdir(parents=True)

    with pytest.raises(ValueError, match="already configured as http"):
        await manager._configure_mcp_servers(MagicMock(), instance)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("existing", "requested", "retained"),
    [
        (
            '[mcp_servers.madrox]\ncommand = "bash"\nargs = ["start_plugin.sh"]\n'
            '[mcp_servers.madrox.env]\nSTALE_SECRET = "old"\n',
            {},
            "env",
        ),
        (
            '[mcp_servers.remote]\nurl = "https://old.test/mcp"\n'
            '[mcp_servers.remote.http_headers]\nAuthorization = "secret"\n',
            {"remote": {"transport": "http", "url": "https://new.test/mcp"}},
            "http_headers",
        ),
    ],
)
async def test_codex_rejects_stale_same_transport_connection_fields(
    isolated_codex_home, tmp_path, existing, requested, retained
):
    (isolated_codex_home / "config.toml").write_text(existing)
    manager = TmuxInstanceManager(
        {"workspace_base_dir": str(tmp_path / "workspaces"), "max_concurrent_instances": 10}
    )
    instance = {
        "id": "stale-connection",
        "workspace_dir": tmp_path / "workspaces" / "stale-connection",
        "instance_type": "codex",
        "mcp_servers": requested,
    }
    instance["workspace_dir"].mkdir(parents=True)

    with pytest.raises(ValueError, match=retained):
        await manager._configure_mcp_servers(MagicMock(), instance)


@pytest.mark.asyncio
async def test_codex_allows_launcher_to_child_proxy_override(isolated_codex_home, tmp_path):
    (isolated_codex_home / "config.toml").write_text(
        '[mcp_servers.madrox]\ncommand = "bash"\nargs = ["/plugins/madrox/start_plugin.sh"]\n'
    )
    manager = TmuxInstanceManager(
        {"workspace_base_dir": str(tmp_path / "workspaces"), "max_concurrent_instances": 10}
    )
    instance = {
        "id": "safe-same-transport",
        "workspace_dir": tmp_path / "workspaces" / "safe-same-transport",
        "instance_type": "codex",
        "mcp_servers": {},
    }
    instance["workspace_dir"].mkdir(parents=True)

    await manager._configure_mcp_servers(MagicMock(), instance)

    assert any(
        value.startswith('mcp_servers.madrox.command="')
        for value in instance["_mcp_launch_overrides"]
    )


@pytest.mark.asyncio
async def test_codex_launch_log_does_not_expose_mcp_secrets(isolated_codex_home, tmp_path, caplog):
    manager = TmuxInstanceManager(
        {"workspace_base_dir": str(tmp_path / "workspaces"), "max_concurrent_instances": 10}
    )
    workspace = tmp_path / "workspaces" / "secret-log"
    workspace.mkdir(parents=True)
    instance = {
        "id": "secret-log",
        "workspace_dir": str(workspace),
        "instance_type": "codex",
        "bypass_isolation": True,
        "mcp_servers": {
            "private": {
                "command": "python",
                "args": ["server.py"],
                "env": {"TOKEN": "SECRET_SENTINEL"},
            }
        },
    }
    manager.instances[instance["id"]] = instance
    pane = MagicMock()
    session = MagicMock()
    session.windows = [MagicMock()]
    session.windows[0].panes = [pane]
    manager.tmux_server.new_session = MagicMock(return_value=session)
    manager._kill_existing_session = MagicMock()
    manager._export_session_env = MagicMock()
    manager._wait_for_cli_ready = AsyncMock(return_value=True)
    manager._bootstrap_instance = AsyncMock()

    with caplog.at_level("DEBUG"):
        await manager._start_cli_session(instance["id"], resume=False)

    assert "SECRET_SENTINEL" not in caplog.text
    assert "scoped MCP override(s)" in caplog.text
    exported = manager._export_session_env.call_args.args[2]
    assert exported["CODEX_HOME"] == str(isolated_codex_home)


@pytest.mark.asyncio
async def test_claude_still_uses_json_config():
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

    await manager._configure_mcp_servers(mock_pane, instance)

    # Verify config file WAS created for Claude
    config_file = instance["workspace_dir"] / ".claude_mcp_config.json"
    assert config_file.exists(), "Claude should create JSON config file"

    # Verify _mcp_config_path WAS set
    assert "_mcp_config_path" in instance
    assert instance["_mcp_config_path"] == str(config_file)
