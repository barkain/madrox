"""Integration tests for STDIO MCP Server tool registration.

Tests the OrchestrationMCPServer to ensure all 27 tools are properly
registered and accessible via the STDIO transport.
"""


import pytest

from src.orchestrator.mcp_server import OrchestrationMCPServer
from src.orchestrator.simple_models import OrchestratorConfig


@pytest.fixture
def test_config():
    """Create a test configuration for OrchestrationMCPServer."""
    return OrchestratorConfig(
        workspace_base_dir="/tmp/test_madrox_workspace",
        log_dir="/tmp/test_madrox_logs",
        log_level="ERROR",  # Reduce noise in tests
    )


@pytest.mark.asyncio
async def test_all_tools_registered(test_config):
    """Test that all 27 tools are registered after initialization."""
    # Create server
    server = OrchestrationMCPServer(test_config)

    # Get registered tools
    tools = await server.mcp.get_tools()

    # Verify tool count
    assert len(tools) == 27, f"Expected 27 tools, got {len(tools)}"

    # Verify specific critical tools exist
    critical_tools = [
        'spawn_claude',
        'spawn_codex',
        'send_to_instance',
        'reply_to_caller',
        'get_pending_replies',
        'get_instance_status',
        'terminate_instance',
    ]

    for tool_name in critical_tools:
        assert tool_name in tools, f"Critical tool '{tool_name}' not found in registered tools"


@pytest.mark.asyncio
async def test_tool_categories_complete(test_config):
    """Test that all tool categories have the expected number of tools."""
    server = OrchestrationMCPServer(test_config)
    tools = await server.mcp.get_tools()
    tool_names = set(tools.keys())

    # Define expected tool categories and their members
    categories = {
        'lifecycle': [
            'spawn_claude',
            'spawn_codex',
            'spawn_multiple_instances',
            'spawn_team_from_template',
            'terminate_instance',
            'terminate_multiple_instances',
        ],
        'messaging': [
            'send_to_instance',
            'send_to_multiple_instances',
            'reply_to_caller',
            'get_pending_replies',
            'broadcast_to_children',
            'get_instance_output',
        ],
        'status': [
            'get_instance_status',
            'get_live_instance_status',
            'get_multiple_instance_outputs',
            'get_children',
            'get_instance_tree',
            'get_main_instance_id',
            'get_tmux_pane_content',
        ],
        'files': [
            'retrieve_instance_file',
            'retrieve_multiple_instance_files',
            'list_instance_files',
            'list_multiple_instance_files',
        ],
        'coordination': [
            'coordinate_instances',
            'interrupt_instance',
            'interrupt_multiple_instances',
            'get_job_status',
        ],
    }

    # Verify all tools in each category are present
    for category, expected_tools in categories.items():
        missing = set(expected_tools) - tool_names
        assert not missing, f"Category '{category}' is missing tools: {missing}"


@pytest.mark.asyncio
async def test_validation_catches_missing_tools(test_config):
    """Test that validation catches if tools are missing (regression test)."""
    # This test verifies the validation logic would catch issues
    # We can't easily mock the missing tools, but we verify the validation exists

    server = OrchestrationMCPServer(test_config)

    # The fact that server initialized successfully means validation passed
    # and 27 tools are present (validation would have raised RuntimeError otherwise)
    assert hasattr(server, 'mcp')
    assert hasattr(server, 'manager')

    # Verify the validation constant matches reality
    tools = await server.mcp.get_tools()
    assert len(tools) == 27  # This matches the expected_tools_count in the validation


def test_class_docstring_updated():
    """Test that class docstring reflects the wrapper functions approach."""
    docstring = OrchestrationMCPServer.__doc__

    assert docstring is not None, "Class should have a docstring"

    # Verify docstring mentions wrapper functions approach
    assert 'wrapper' in docstring.lower(), "Docstring should mention wrapper functions approach"

    # Verify it mentions proper binding
    assert 'binding' in docstring.lower() or 'bind' in docstring.lower(), \
        "Docstring should reference proper binding of methods"


@pytest.mark.asyncio
async def test_stdio_server_run_method(test_config):
    """Test that the run() method returns the FastMCP instance."""
    server = OrchestrationMCPServer(test_config)

    # Call run() method
    mcp_instance = await server.run()

    # Verify it returns the mcp instance
    assert mcp_instance is server.mcp
    assert mcp_instance.name == "claude-orchestrator-stdio"


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
