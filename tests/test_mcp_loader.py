"""Test MCP configuration loader."""


from src.orchestrator.mcp_loader import MCPConfigLoader, get_mcp_servers


def test_list_available_configs():
    """Test listing available MCP configurations."""
    loader = MCPConfigLoader()
    configs = loader.list_available_configs()

    # Should have at least the configs we created
    expected_configs = [
        "playwright",
        "puppeteer",
        "github",
        "filesystem",
        "sqlite",
        "postgres",
        "brave-search",
        "google-drive",
        "slack",
        "memory",
    ]

    for config_name in expected_configs:
        assert config_name in configs, f"Expected config '{config_name}' not found"


def test_load_playwright_config():
    """Test loading the Playwright MCP config."""
    loader = MCPConfigLoader()
    config = loader.load_config("playwright")

    assert config is not None
    assert config["name"] == "playwright"
    assert "description" in config
    assert "config" in config

    # Check the config format
    assert "command" in config["config"]
    assert "args" in config["config"]
    assert config["config"]["command"] == "npx"
    assert "@playwright/mcp@latest" in config["config"]["args"]


def test_load_nonexistent_config():
    """Test loading a config that doesn't exist."""
    loader = MCPConfigLoader()
    config = loader.load_config("nonexistent-server")

    assert config is None


def test_get_mcp_servers_dict():
    """Test building an mcp_servers dict from config names."""
    loader = MCPConfigLoader()
    mcp_servers = loader.get_mcp_servers_dict("playwright", "memory")

    assert isinstance(mcp_servers, dict)
    assert "playwright" in mcp_servers
    assert "memory" in mcp_servers

    # Check structure
    assert "command" in mcp_servers["playwright"]
    assert "args" in mcp_servers["playwright"]


def test_get_mcp_servers_dict_with_custom():
    """Test mixing prebuilt configs with custom configs."""
    loader = MCPConfigLoader()
    mcp_servers = loader.get_mcp_servers_dict(
        "playwright", custom_server={"command": "python", "args": ["server.py"]}
    )

    assert "playwright" in mcp_servers
    assert "custom_server" in mcp_servers
    assert mcp_servers["custom_server"]["command"] == "python"


def test_get_mcp_servers_convenience_function():
    """Test the convenience function."""
    mcp_servers = get_mcp_servers("playwright", "github")

    assert isinstance(mcp_servers, dict)
    assert "playwright" in mcp_servers
    assert "github" in mcp_servers


def test_load_with_overrides():
    """Test loading a config with overrides."""
    loader = MCPConfigLoader()

    # Override filesystem path
    config = loader.load_with_overrides(
        "filesystem",
        args_overrides=["-y", "@modelcontextprotocol/server-filesystem", "/custom/path"],
    )

    assert config is not None
    assert config["config"]["args"] == [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/custom/path",
    ]


def test_load_with_env_overrides():
    """Test loading a config with environment variable overrides."""
    loader = MCPConfigLoader()

    # Override GitHub token
    config = loader.load_with_overrides(
        "github", env_overrides={"GITHUB_PERSONAL_ACCESS_TOKEN": "test_token_123"}
    )

    assert config is not None
    assert "env" in config
    assert config["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == "test_token_123"


def test_configs_have_required_fields():
    """Test that all config files have required fields."""
    loader = MCPConfigLoader()
    configs = loader.list_available_configs()

    for config_name in configs:
        config = loader.load_config(config_name)

        assert config is not None, f"Config '{config_name}' failed to load"
        assert "name" in config, f"Config '{config_name}' missing 'name' field"
        assert "description" in config, f"Config '{config_name}' missing 'description' field"
        assert "config" in config, f"Config '{config_name}' missing 'config' field"

        # Config should have either command (stdio) or url (http)
        config_dict = config["config"]
        has_command = "command" in config_dict
        has_url = "url" in config_dict

        assert has_command or has_url, f"Config '{config_name}' must have either 'command' or 'url'"
