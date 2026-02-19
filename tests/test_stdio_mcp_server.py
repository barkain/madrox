"""Integration tests for STDIO MCP Server proxy tool registration.

Tests the OrchestrationMCPServer proxy to ensure all 28 tools are properly
registered and accessible via the STDIO transport.
"""

import pytest

from orchestrator.mcp_server import OrchestrationMCPServer


@pytest.fixture
def proxy_server():
    """Create a proxy MCP server for testing."""
    return OrchestrationMCPServer(parent_url="http://localhost:9999")


@pytest.mark.asyncio
async def test_all_tools_registered(proxy_server):
    """Test that all 28 tools are registered after initialization."""
    tools = await proxy_server.mcp.get_tools()

    assert len(tools) == 28, f"Expected 28 tools, got {len(tools)}"

    critical_tools = [
        "spawn_claude",
        "spawn_codex",
        "send_to_instance",
        "reply_to_caller",
        "get_pending_replies",
        "get_instance_status",
        "terminate_instance",
    ]

    for tool_name in critical_tools:
        assert tool_name in tools, f"Critical tool '{tool_name}' not found in registered tools"


@pytest.mark.asyncio
async def test_tool_categories_complete(proxy_server):
    """Test that all tool categories have the expected number of tools."""
    tools = await proxy_server.mcp.get_tools()
    tool_names = set(tools.keys())

    categories = {
        "lifecycle": [
            "spawn_claude",
            "spawn_codex",
            "spawn_multiple_instances",
            "spawn_team_from_template",
            "terminate_instance",
            "terminate_multiple_instances",
        ],
        "messaging": [
            "send_to_instance",
            "send_to_multiple_instances",
            "reply_to_caller",
            "get_pending_replies",
            "broadcast_to_children",
            "get_instance_output",
        ],
        "status": [
            "get_instance_status",
            "get_live_instance_status",
            "get_multiple_instance_outputs",
            "get_children",
            "get_instance_tree",
            "get_main_instance_id",
            "get_tmux_pane_content",
        ],
        "files": [
            "retrieve_instance_file",
            "retrieve_multiple_instance_files",
            "list_instance_files",
            "list_multiple_instance_files",
        ],
        "coordination": [
            "coordinate_instances",
            "interrupt_instance",
            "interrupt_multiple_instances",
            "get_job_status",
        ],
    }

    for category, expected_tools in categories.items():
        missing = set(expected_tools) - tool_names
        assert not missing, f"Category '{category}' is missing tools: {missing}"


@pytest.mark.asyncio
async def test_validation_catches_missing_tools(proxy_server):
    """Test that all expected tools are present."""
    assert hasattr(proxy_server, "mcp")
    assert hasattr(proxy_server, "parent_url")

    tools = await proxy_server.mcp.get_tools()
    assert len(tools) == 28


def test_class_docstring_updated():
    """Test that class docstring reflects the proxy approach."""
    docstring = OrchestrationMCPServer.__doc__

    assert docstring is not None, "Class should have a docstring"
    assert "proxy" in docstring.lower(), "Docstring should mention proxy approach"


@pytest.mark.asyncio
async def test_stdio_server_run_method(proxy_server):
    """Test that the run() method returns the FastMCP instance."""
    mcp_instance = await proxy_server.run()

    assert mcp_instance is proxy_server.mcp
    assert mcp_instance.name == "claude-orchestrator-stdio-proxy"


@pytest.mark.asyncio
async def test_get_peers_tool_registered(proxy_server):
    """Test that get_peers is registered (previously missing in STDIO)."""
    tools = await proxy_server.mcp.get_tools()
    assert "get_peers" in tools


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
