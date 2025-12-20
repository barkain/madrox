"""Test MCP stdio configuration format."""

import json
import tempfile
from pathlib import Path

from orchestrator.tmux_instance_manager import TmuxInstanceManager


def test_mcp_stdio_config_format():
    """Test that stdio MCP configs are generated in the correct format for Claude Code."""
    config = {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}

    manager = TmuxInstanceManager(config)

    # Create a mock instance with Playwright config
    instance = {
        "id": "test-instance",
        "workspace_dir": Path(config["workspace_base_dir"]) / "test-instance",
        "mcp_servers": {"playwright": {"command": "npx", "args": ["@playwright/mcp@latest"]}},
    }

    instance["workspace_dir"].mkdir(parents=True, exist_ok=True)

    # Mock pane (not used in this test)
    class MockPane:
        pass

    pane = MockPane()

    # Run the configuration
    manager._configure_mcp_servers(pane, instance)

    # Read the generated config
    config_path = instance["workspace_dir"] / ".claude_mcp_config.json"
    assert config_path.exists(), "MCP config file should be created"

    with open(config_path) as f:
        mcp_config = json.load(f)

    # Verify structure
    assert "mcpServers" in mcp_config
    assert "playwright" in mcp_config["mcpServers"]

    playwright_config = mcp_config["mcpServers"]["playwright"]

    # The key assertion: stdio configs should NOT have "type" field
    assert "type" not in playwright_config, "stdio MCP configs should not have 'type' field"
    assert "command" in playwright_config
    assert "args" in playwright_config
    assert playwright_config["command"] == "npx"
    assert playwright_config["args"] == ["@playwright/mcp@latest"]


def test_mcp_http_config_format():
    """Test that http MCP configs include the type field and Madrox is always added."""
    config = {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}

    manager = TmuxInstanceManager(config)

    instance = {
        "id": "test-instance",
        "workspace_dir": Path(config["workspace_base_dir"]) / "test-instance",
        "mcp_servers": {},  # Madrox should be added automatically
    }

    instance["workspace_dir"].mkdir(parents=True, exist_ok=True)

    class MockPane:
        pass

    pane = MockPane()

    manager._configure_mcp_servers(pane, instance)

    config_path = instance["workspace_dir"] / ".claude_mcp_config.json"
    with open(config_path) as f:
        mcp_config = json.load(f)

    # Verify http transport includes type field
    assert "madrox" in mcp_config["mcpServers"]
    madrox_config = mcp_config["mcpServers"]["madrox"]

    assert "type" in madrox_config, "http MCP configs should have 'type' field"
    assert madrox_config["type"] == "http"
    assert "url" in madrox_config


def test_mcp_transport_auto_detection():
    """Test that transport is auto-detected from presence of 'command' field."""
    config = {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}

    manager = TmuxInstanceManager(config)

    instance = {
        "id": "test-instance",
        "workspace_dir": Path(config["workspace_base_dir"]) / "test-instance",
        "mcp_servers": {
            # No "transport" field - should auto-detect as stdio from "command"
            "playwright": {"command": "npx", "args": ["@playwright/mcp@latest"]}
        },
    }

    instance["workspace_dir"].mkdir(parents=True, exist_ok=True)

    class MockPane:
        pass

    pane = MockPane()

    manager._configure_mcp_servers(pane, instance)

    config_path = instance["workspace_dir"] / ".claude_mcp_config.json"
    with open(config_path) as f:
        mcp_config = json.load(f)

    # Should be treated as stdio (no type field)
    playwright_config = mcp_config["mcpServers"]["playwright"]
    assert "type" not in playwright_config
    assert "command" in playwright_config


def test_mcp_mixed_transports():
    """Test config with both stdio and http MCP servers. Madrox (http) is always added."""
    config = {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}

    manager = TmuxInstanceManager(config)

    instance = {
        "id": "test-instance",
        "workspace_dir": Path(config["workspace_base_dir"]) / "test-instance",
        "mcp_servers": {
            "playwright": {  # stdio
                "command": "npx",
                "args": ["@playwright/mcp@latest"],
            }
        },  # Madrox (http) will be added automatically
    }

    instance["workspace_dir"].mkdir(parents=True, exist_ok=True)

    class MockPane:
        pass

    pane = MockPane()

    manager._configure_mcp_servers(pane, instance)

    config_path = instance["workspace_dir"] / ".claude_mcp_config.json"
    with open(config_path) as f:
        mcp_config = json.load(f)

    # Verify both servers are present with correct formats
    assert "madrox" in mcp_config["mcpServers"]
    assert "playwright" in mcp_config["mcpServers"]

    # http server has type
    assert "type" in mcp_config["mcpServers"]["madrox"]
    assert mcp_config["mcpServers"]["madrox"]["type"] == "http"

    # stdio server does not have type
    assert "type" not in mcp_config["mcpServers"]["playwright"]
    assert "command" in mcp_config["mcpServers"]["playwright"]
