# ruff: noqa: S101
"""Integration tests for STDIO MCP Server proxy tool registration.

Tests the OrchestrationMCPServer proxy to ensure tools are properly
registered from the parent HTTP server's /tools endpoint.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.mcp_server import OrchestrationMCPServer

MOCK_TOOLS_RESPONSE = {
    "tools": [
        {
            "name": "spawn_claude",
            "description": "Spawn a new Claude instance",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Instance name"},
                    "role": {"type": "string", "description": "Role"},
                },
                "required": [],
            },
        },
        {
            "name": "spawn_codex",
            "description": "Spawn a new Codex instance",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Instance name"},
                },
                "required": [],
            },
        },
        {
            "name": "send_to_instance",
            "description": "Send a message to a specific instance",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "instance_id": {"type": "string", "description": "Target instance ID"},
                    "message": {"type": "string", "description": "Message to send"},
                },
                "required": ["instance_id", "message"],
            },
        },
        {
            "name": "reply_to_caller",
            "description": "Reply to the calling instance",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Reply message"},
                },
                "required": ["message"],
            },
        },
        {
            "name": "get_pending_replies",
            "description": "Get pending replies",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "get_instance_status",
            "description": "Get instance status",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "instance_id": {"type": "string", "description": "Instance ID"},
                },
                "required": [],
            },
        },
        {
            "name": "terminate_instance",
            "description": "Terminate an instance",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "instance_id": {"type": "string", "description": "Instance ID"},
                    "force": {"type": "boolean", "description": "Force termination"},
                },
                "required": ["instance_id"],
            },
        },
        {
            "name": "get_peers",
            "description": "Get peer instances",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
    ]
}


def _mock_httpx_client(response_json=None, status_code=200):
    """Create a mock httpx.AsyncClient context manager."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = response_json or MOCK_TOOLS_RESPONSE
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.fixture
def proxy_server():
    """Create a proxy MCP server (tools not yet registered)."""
    return OrchestrationMCPServer(parent_url="http://localhost:9999")


@pytest.mark.asyncio
async def test_all_tools_registered(proxy_server):
    """Test that proxy tools + local tools are registered after run()."""
    with patch("orchestrator.mcp_server.httpx.AsyncClient", return_value=_mock_httpx_client()):
        await proxy_server.run()

    tools = await proxy_server.mcp.get_tools()
    # 8 proxy tools + 1 local (get_dashboard_url)
    assert len(tools) == 9, f"Expected 9 tools, got {len(tools)}: {list(tools.keys())}"

    critical_tools = [
        "spawn_claude",
        "spawn_codex",
        "send_to_instance",
        "reply_to_caller",
        "get_pending_replies",
        "get_instance_status",
        "terminate_instance",
        "get_dashboard_url",
    ]
    for tool_name in critical_tools:
        assert tool_name in tools, f"Critical tool '{tool_name}' not found"


@pytest.mark.asyncio
async def test_tools_not_registered_before_run(proxy_server):
    """Test that only local tools exist before run() is called."""
    tools = await proxy_server.mcp.get_tools()
    assert len(tools) == 1
    assert "get_dashboard_url" in tools


@pytest.mark.asyncio
async def test_proxy_tool_has_correct_signature(proxy_server):
    """Test that proxy tools have proper parameter signatures from schema."""
    with patch("orchestrator.mcp_server.httpx.AsyncClient", return_value=_mock_httpx_client()):
        await proxy_server.run()

    tools = await proxy_server.mcp.get_tools()
    send_tool = tools["send_to_instance"]
    mcp_tool = send_tool.to_mcp_tool()
    schema = mcp_tool.inputSchema

    assert "instance_id" in schema["properties"]
    assert "message" in schema["properties"]


def test_class_docstring_updated():
    """Test that class docstring reflects the proxy approach."""
    docstring = OrchestrationMCPServer.__doc__
    assert docstring is not None
    assert "proxy" in docstring.lower()


@pytest.mark.asyncio
async def test_stdio_server_run_method(proxy_server):
    """Test that run() registers tools and returns the FastMCP instance."""
    with patch("orchestrator.mcp_server.httpx.AsyncClient", return_value=_mock_httpx_client()):
        mcp_instance = await proxy_server.run()

    assert mcp_instance is proxy_server.mcp
    assert mcp_instance.name == "claude-orchestrator-stdio-proxy"

    tools = await mcp_instance.get_tools()
    assert len(tools) == 9


@pytest.mark.asyncio
async def test_get_peers_tool_registered(proxy_server):
    """Test that get_peers is registered."""
    with patch("orchestrator.mcp_server.httpx.AsyncClient", return_value=_mock_httpx_client()):
        await proxy_server.run()

    tools = await proxy_server.mcp.get_tools()
    assert "get_peers" in tools


@pytest.mark.asyncio
async def test_init_is_lightweight():
    """Test that __init__ completes without network calls."""
    server = OrchestrationMCPServer(parent_url="http://nonexistent:9999")
    assert server.parent_url == "http://nonexistent:9999"
    assert server.mcp is not None

    tools = await server.mcp.get_tools()
    assert len(tools) == 1
    assert "get_dashboard_url" in tools


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
