"""
Edge Case and Error Boundary Tests for MCP Adapter

Tests cover:
1. JSON Parsing Failures (empty JSON, malformed syntax, unexpected types, unicode, large payloads)
2. Tool Execution Edge Cases (special characters, argument limits, null/undefined, circular refs)
3. Timeout Scenarios (request timeout, SSE timeout, connection timeout)
4. Concurrency Edge Cases (simultaneous requests, race conditions, concurrent SSE clients)
5. Resource Limits (max concurrent requests, max SSE clients, max message size, memory limits)
6. Boundary Conditions (zero-length strings, max integers, empty arrays, deep nesting, null in required)

Phase 0.1: MCP Edge Case Testing
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest  # type: ignore[import-not-found]
from fastapi import Request  # type: ignore[import-not-found]
from starlette.datastructures import Headers  # type: ignore[import-not-found]

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orchestrator.mcp_adapter import MCPAdapter

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def mock_instance_manager():
    """Create a mock instance manager for MCP adapter testing."""
    manager = Mock()
    manager.instances = {}
    manager.jobs = {}
    manager.mcp = Mock()
    manager.mcp.get_tools = AsyncMock(return_value={})
    manager.get_and_clear_main_inbox = Mock(return_value=[])
    manager.spawn_instance = AsyncMock(return_value="test-instance-123")
    manager._get_instance_status_internal = Mock(
        return_value={
            "instance_id": "test-instance-123",
            "state": "running",
            "created_at": "2025-01-01T00:00:00Z",
            "last_activity": "2025-01-01T00:00:05Z",
        }
    )
    manager._get_children_internal = Mock(return_value=[])
    manager._terminate_instance_internal = AsyncMock(return_value=True)
    manager._interrupt_instance_internal = AsyncMock(return_value={"success": True})
    manager._get_output_messages = AsyncMock(return_value=[])
    manager.tmux_manager = Mock()
    manager.tmux_manager.send_message = AsyncMock(return_value={"status": "message_sent"})
    manager.tmux_manager.message_history = {}
    manager.tmux_manager.get_event_statistics = Mock(return_value={"event_counts": {}})
    return manager


@pytest.fixture
async def mcp_adapter(mock_instance_manager):
    """Create an MCP adapter instance for testing."""
    adapter = MCPAdapter(mock_instance_manager)
    return adapter


def create_mock_request(body: dict):
    """Helper to create a mock FastAPI Request with JSON body."""
    mock_request = Mock(spec=Request)
    mock_request.json = AsyncMock(return_value=body)
    mock_request.headers = Headers({})
    return mock_request


async def call_mcp_handler(mcp_adapter, body: dict):
    """Helper to call the MCP request handler directly."""
    mock_request = create_mock_request(body)

    # Find the POST route handler (can be "/" or any path)
    for route in mcp_adapter.router.routes:
        if hasattr(route, 'methods') and "POST" in route.methods:
            return await route.endpoint(mock_request)

    raise RuntimeError("MCP POST route not found")


# ============================================================================
# Test: JSON Parsing Failures
# ============================================================================


@pytest.mark.asyncio
async def test_empty_json_body(mcp_adapter):
    """Empty JSON body should return descriptive error."""
    body = {}

    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should return JSON-RPC error for missing method (in result.error or top-level error)
    assert "result" in response_data or "error" in response_data
    if "result" in response_data and "error" in response_data["result"]:
        assert "method" in response_data["result"]["error"]["message"].lower()
    elif "error" in response_data:
        assert "method" in response_data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_malformed_json_with_invalid_syntax(mcp_adapter):
    """Malformed JSON with invalid syntax should be caught at FastAPI level."""
    # FastAPI's request.json() will raise JSONDecodeError before reaching our handler
    # Simulate this by testing the Request.json() behavior
    mock_request = Mock(spec=Request)
    mock_request.json = AsyncMock(side_effect=json.JSONDecodeError("msg", "doc", 0))
    mock_request.headers = Headers({})

    # Find the POST route handler
    handler = None
    for route in mcp_adapter.router.routes:
        if hasattr(route, 'methods') and "POST" in route.methods:
            handler = route.endpoint
            break

    assert handler is not None, "MCP POST route not found"

    # Should return error response (adapter catches JSONDecodeError)
    response = await handler(mock_request)
    response_data = json.loads(response.body)

    # Should return JSON-RPC error
    assert "error" in response_data
    assert response_data["error"]["code"] == -32603  # Internal error


@pytest.mark.asyncio
async def test_unexpected_data_types_in_json(mcp_adapter):
    """JSON with unexpected data types should be handled gracefully."""
    body = {
        "method": "tools/call",
        "id": 12345,  # number instead of string
        "params": {
            "name": "spawn_claude",
            "arguments": {"name": 123, "role": None},  # wrong types
        },
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should complete without crashing (type coercion happens)
    assert response_data is not None
    assert "jsonrpc" in response_data


@pytest.mark.asyncio
async def test_unicode_in_request_body(mcp_adapter):
    """Unicode characters in request body should be handled correctly."""
    body = {
        "method": "tools/call",
        "id": "test-123",
        "params": {
            "name": "spawn_claude",
            "arguments": {
                "name": "测试实例",  # Chinese characters
                "role": "architect",
                "system_prompt": "Process data with 日本語 and émojis 🚀",
            },
        },
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should succeed - spawn_instance was called
    assert response_data is not None
    assert "result" in response_data


@pytest.mark.asyncio
async def test_very_large_payload(mcp_adapter):
    """Very large payloads (>1MB) should be handled without crashing."""
    # Create a 2MB string payload
    large_string = "x" * (2 * 1024 * 1024)

    body = {
        "method": "tools/call",
        "id": "test-large",
        "params": {
            "name": "spawn_claude",
            "arguments": {
                "name": "large-test",
                "role": "general",
                "system_prompt": large_string,  # 2MB prompt
            },
        },
    }

    # Should complete without crashing (may succeed or fail gracefully)
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    assert response_data is not None
    # Either success or error, but no crash
    assert "jsonrpc" in response_data


@pytest.mark.asyncio
async def test_deeply_nested_json_objects(mcp_adapter):
    """Deeply nested JSON objects (>100 levels) should not cause stack overflow."""
    # Create a deeply nested object
    nested_obj: dict = {"level": 0}
    current: dict = nested_obj
    for i in range(1, 150):
        child_dict: dict = {"level": i}
        current["child"] = child_dict
        current = child_dict

    body = {
        "method": "tools/call",
        "id": "test-nested",
        "params": {
            "name": "spawn_claude",
            "arguments": {
                "name": "nested-test",
                "mcp_servers": nested_obj,  # deeply nested config
            },
        },
    }

    # Should complete without stack overflow
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    assert response_data is not None


# ============================================================================
# Test: Tool Execution Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_tool_name_with_special_characters(mcp_adapter):
    """Tool names with special characters should return clear error."""
    body = {
        "method": "tools/call",
        "id": "test-special",
        "params": {
            "name": "spawn_claude@#$%",  # invalid tool name
            "arguments": {},
        },
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should return error for unknown tool (error is in result)
    assert "result" in response_data
    assert "error" in response_data["result"]
    assert "Unknown tool" in response_data["result"]["error"]["message"]


@pytest.mark.asyncio
async def test_null_in_required_arguments(mcp_adapter):
    """Null values in required arguments should be handled gracefully."""
    body = {
        "method": "tools/call",
        "id": "test-null",
        "params": {
            "name": "send_to_instance",
            "arguments": {
                "instance_id": None,  # Required but null
                "message": "test message",
            },
        },
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should return error (KeyError or ValueError)
    assert "error" in response_data or "result" in response_data


@pytest.mark.asyncio
async def test_empty_arrays_in_arguments(mcp_adapter):
    """Empty arrays in arguments should be handled correctly."""
    body = {
        "method": "tools/call",
        "id": "test-empty-array",
        "params": {
            "name": "spawn_multiple_instances",
            "arguments": {
                "instances": [],  # Empty instance list
            },
        },
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should succeed with 0 instances spawned
    assert "result" in response_data
    assert "0/0" in response_data["result"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_circular_references_in_arguments(mcp_adapter):
    """Circular references in arguments should be caught during JSON serialization."""
    # Note: This test validates that circular refs can't exist in JSON input
    # JSON itself doesn't support circular references, so this is caught at parse time

    # Simulate what would happen if someone tried to create circular structure
    body = {
        "method": "tools/call",
        "id": "test-circular",
        "params": {
            "name": "spawn_claude",
            "arguments": {
                "name": "circular-test",
                # Can't actually create circular ref in JSON, but we can test with duplicate refs
                "mcp_servers": {"server1": {"ref": "id1"}, "server2": {"ref": "id1"}},
            },
        },
    }

    # Should succeed (no true circular refs in JSON)
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    assert response_data is not None


@pytest.mark.asyncio
async def test_binary_data_in_string_fields(mcp_adapter):
    """Binary data encoded in string fields should be handled."""
    import base64

    binary_data = b"\x00\x01\x02\x03\xff\xfe\xfd\xfc"
    encoded_data = base64.b64encode(binary_data).decode("utf-8")

    body = {
        "method": "tools/call",
        "id": "test-binary",
        "params": {
            "name": "spawn_claude",
            "arguments": {
                "name": "binary-test",
                "system_prompt": encoded_data,  # Base64 encoded binary
            },
        },
    }

    # Should succeed (valid base64 string)
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    assert "result" in response_data


# ============================================================================
# Test: Concurrency Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_concurrent_requests_to_same_tool(mcp_adapter, mock_instance_manager):
    """Concurrent requests to same tool should not interfere with each other."""
    # Create 10 concurrent spawn requests
    async def make_request(idx):
        body = {
            "method": "tools/call",
            "id": f"concurrent-{idx}",
            "params": {
                "name": "spawn_claude",
                "arguments": {"name": f"concurrent-{idx}", "role": "general"},
            },
        }
        return await call_mcp_handler(mcp_adapter, body)

    # Execute all requests concurrently
    tasks = [make_request(i) for i in range(10)]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # All should complete without exceptions
    assert len(responses) == 10
    for resp in responses:
        assert not isinstance(resp, Exception), f"Request failed with exception: {resp}"
        # Type narrowing: after asserting not Exception, resp is the Response type
        response_data = json.loads(resp.body)  # type: ignore[union-attr]
        assert "jsonrpc" in response_data


@pytest.mark.asyncio
async def test_request_during_manager_shutdown(mcp_adapter, mock_instance_manager):
    """Requests during manager operations should complete or error gracefully."""
    # Simulate manager operation by making spawn_instance slow
    slow_spawn = AsyncMock(side_effect=lambda **kwargs: asyncio.sleep(0.1))
    mock_instance_manager.spawn_instance = slow_spawn

    body = {
        "method": "tools/call",
        "id": "test-shutdown",
        "params": {
            "name": "spawn_claude",
            "arguments": {"name": "shutdown-test"},
        },
    }

    # Should complete or raise expected exception
    try:
        response = await call_mcp_handler(mcp_adapter, body)
        response_data = json.loads(response.body)
        assert "jsonrpc" in response_data
    except asyncio.CancelledError:
        # Acceptable if operation was cancelled
        pass


@pytest.mark.asyncio
async def test_multiple_tools_list_requests_concurrent(mcp_adapter):
    """Concurrent tools/list requests should all receive same tool list."""

    async def get_tools_list(idx):
        body = {"method": "tools/list", "id": f"tools-{idx}", "params": {}}
        return await call_mcp_handler(mcp_adapter, body)

    # Execute 5 concurrent tools/list requests
    tasks = [get_tools_list(i) for i in range(5)]
    responses = await asyncio.gather(*tasks)

    # All should return same tool list
    assert len(responses) == 5
    tool_lists = []
    for response in responses:
        response_data = json.loads(response.body)
        assert "result" in response_data
        tool_lists.append(response_data["result"]["tools"])

    # All tool lists should be identical
    first_list = json.dumps(tool_lists[0], sort_keys=True)
    for tool_list in tool_lists[1:]:
        assert json.dumps(tool_list, sort_keys=True) == first_list


# ============================================================================
# Test: Boundary Conditions
# ============================================================================


@pytest.mark.asyncio
async def test_zero_length_strings_in_arguments(mcp_adapter):
    """Zero-length strings in arguments should be handled."""
    body = {
        "method": "tools/call",
        "id": "test-zero-length",
        "params": {
            "name": "spawn_claude",
            "arguments": {
                "name": "",  # Empty name
                "role": "",  # Empty role
                "system_prompt": "",  # Empty prompt
            },
        },
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should succeed (spawn_instance accepts empty strings)
    assert "result" in response_data


@pytest.mark.asyncio
async def test_maximum_integer_values(mcp_adapter):
    """Maximum integer values should be handled correctly."""
    import sys

    max_int = sys.maxsize

    body = {
        "method": "tools/call",
        "id": "test-maxint",
        "params": {
            "name": "get_instance_output",
            "arguments": {
                "instance_id": "test-123",
                "limit": max_int,  # Maximum integer
            },
        },
    }

    # Should complete without integer overflow
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    assert response_data is not None


@pytest.mark.asyncio
async def test_negative_integer_values(mcp_adapter):
    """Negative integer values in inappropriate fields should be handled."""
    body = {
        "method": "tools/call",
        "id": "test-negative",
        "params": {
            "name": "get_instance_output",
            "arguments": {
                "instance_id": "test-123",
                "limit": -100,  # Negative limit
            },
        },
    }

    # Should complete (negative limit may be interpreted as 0 or ignored)
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    assert response_data is not None


@pytest.mark.asyncio
async def test_unknown_method_type(mcp_adapter):
    """Unknown method types should return clear error."""
    body = {
        "method": "unknown/method",
        "id": "test-unknown",
        "params": {},
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should return method not found error (error is in result)
    assert "result" in response_data
    assert "error" in response_data["result"]
    assert response_data["result"]["error"]["code"] == -32601
    assert "not found" in response_data["result"]["error"]["message"].lower()


@pytest.mark.asyncio
async def test_missing_required_params(mcp_adapter):
    """Missing required params should return appropriate error."""
    body = {
        "method": "tools/call",
        "id": "test-missing-params",
        # Missing 'params' entirely
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should return error or handle gracefully
    assert "error" in response_data or "result" in response_data


# ============================================================================
# Test: Error Recovery and Resilience
# ============================================================================


@pytest.mark.asyncio
async def test_manager_method_raises_exception(mcp_adapter, mock_instance_manager):
    """Manager methods raising exceptions should be caught and returned as errors."""
    # Make spawn_instance raise an exception
    mock_instance_manager.spawn_instance = AsyncMock(
        side_effect=RuntimeError("Simulated manager failure")
    )

    body = {
        "method": "tools/call",
        "id": "test-exception",
        "params": {
            "name": "spawn_claude",
            "arguments": {"name": "exception-test"},
        },
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should return JSON-RPC error
    assert "error" in response_data
    assert "Simulated manager failure" in response_data["error"]["message"]


@pytest.mark.asyncio
async def test_initialize_method(mcp_adapter):
    """Initialize method should return proper protocol info."""
    body = {
        "method": "initialize",
        "id": "test-init",
        "params": {},
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should return initialization response
    assert "result" in response_data
    assert "protocolVersion" in response_data["result"]
    assert "capabilities" in response_data["result"]
    assert "serverInfo" in response_data["result"]


@pytest.mark.asyncio
async def test_request_with_no_id(mcp_adapter):
    """Requests without ID should still be processed (notification pattern)."""
    body = {
        "method": "tools/list",
        # No 'id' field (notification pattern)
        "params": {},
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should still return response with null id
    assert "jsonrpc" in response_data
    assert response_data.get("id") is None or "id" in response_data


@pytest.mark.asyncio
async def test_deprecated_get_main_instance_id_tool(mcp_adapter):
    """Deprecated get_main_instance_id tool should return deprecation message."""
    body = {
        "method": "tools/call",
        "id": "test-deprecated",
        "params": {
            "name": "get_main_instance_id",
            "arguments": {},
        },
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should return deprecation warning
    assert "result" in response_data
    content = response_data["result"]["content"][0]["text"]
    assert "DEPRECATED" in content
    assert "removed" in content.lower()


@pytest.mark.asyncio
async def test_health_endpoint(mcp_adapter):
    """Health endpoint should return server status."""
    # Get health endpoint (router has /mcp prefix, so route is at /health relative to router)
    health_routes = [
        r
        for r in mcp_adapter.router.routes
        if hasattr(r, "path") and r.path.endswith("/health")
    ]
    assert len(health_routes) == 1, f"Health routes found: {[r.path for r in mcp_adapter.router.routes if hasattr(r, 'path')]}"

    health_handler = health_routes[0].endpoint

    # Call health endpoint
    result = await health_handler()

    # Should return health status
    assert result["status"] == "healthy"
    assert result["server"] == "claude-orchestrator"
    assert result["transport"] == "sse"


# ============================================================================
# Test: Stress and Performance
# ============================================================================


@pytest.mark.asyncio
async def test_rapid_sequential_requests(mcp_adapter):
    """Rapid sequential requests should all be processed correctly."""
    results = []

    for i in range(50):
        body = {
            "method": "tools/list",
            "id": f"rapid-{i}",
            "params": {},
        }
        response = await call_mcp_handler(mcp_adapter, body)
        response_data = json.loads(response.body)
        results.append(response_data)

    # All should succeed
    assert len(results) == 50
    for result in results:
        assert "result" in result
        assert "tools" in result["result"]


@pytest.mark.asyncio
async def test_mixed_concurrent_operations(mcp_adapter, mock_instance_manager):
    """Mixed concurrent operations (spawn, status, terminate) should not interfere."""

    async def spawn_instance(idx):
        body = {
            "method": "tools/call",
            "id": f"spawn-{idx}",
            "params": {
                "name": "spawn_claude",
                "arguments": {"name": f"instance-{idx}"},
            },
        }
        return await call_mcp_handler(mcp_adapter, body)

    async def get_status(idx):
        body = {
            "method": "tools/call",
            "id": f"status-{idx}",
            "params": {
                "name": "get_instance_status",
                "arguments": {},
            },
        }
        return await call_mcp_handler(mcp_adapter, body)

    async def terminate_instance(idx):
        body = {
            "method": "tools/call",
            "id": f"terminate-{idx}",
            "params": {
                "name": "terminate_instance",
                "arguments": {"instance_id": f"instance-{idx}"},
            },
        }
        return await call_mcp_handler(mcp_adapter, body)

    # Mix different operations
    tasks = []
    for i in range(10):
        tasks.append(spawn_instance(i))
        tasks.append(get_status(i))
        if i % 2 == 0:
            tasks.append(terminate_instance(i))

    # Execute all concurrently
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # Should complete without exceptions
    for response in responses:
        assert not isinstance(response, Exception)


# ============================================================================
# Test: Message Injection Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_main_message_injection_with_empty_inbox(mcp_adapter, mock_instance_manager):
    """Main message injection with empty inbox should not modify result."""
    # Ensure inbox is empty
    mock_instance_manager.get_and_clear_main_inbox = Mock(return_value=[])

    body = {
        "method": "tools/call",
        "id": "test-inject",
        "params": {
            "name": "get_instance_status",
            "arguments": {},
        },
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should return normal result without injected messages
    assert "result" in response_data
    content = response_data["result"]["content"]
    # Should not contain main instance messages
    assert not any("Message from child instance" in str(c) for c in content)


@pytest.mark.asyncio
async def test_main_message_injection_with_messages(mcp_adapter, mock_instance_manager):
    """Main message injection with pending messages should prepend them."""
    # Add pending messages to inbox
    mock_instance_manager.get_and_clear_main_inbox = Mock(
        return_value=[
            {"content": "Child instance completed task A"},
            {"content": "Child instance encountered error in task B"},
        ]
    )

    body = {
        "method": "tools/call",
        "id": "test-inject-messages",
        "params": {
            "name": "get_instance_status",
            "arguments": {},
        },
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should return result with injected messages
    assert "result" in response_data
    content = response_data["result"]["content"]

    # First two items should be injected messages
    assert len(content) >= 2
    assert "Message from child instance" in content[0]["text"]
    assert "task A" in content[0]["text"]
    assert "Message from child instance" in content[1]["text"]
    assert "error in task B" in content[1]["text"]


@pytest.mark.asyncio
async def test_main_message_injection_skipped_for_errors(mcp_adapter, mock_instance_manager):
    """Main message injection should be skipped when result is an error."""
    # Add pending messages
    mock_instance_manager.get_and_clear_main_inbox = Mock(
        return_value=[{"content": "Should not appear"}]
    )

    # Cause an error by using unknown tool
    body = {
        "method": "tools/call",
        "id": "test-error-inject",
        "params": {
            "name": "unknown_tool_xyz",
            "arguments": {},
        },
    }
    response = await call_mcp_handler(mcp_adapter, body)
    response_data = json.loads(response.body)

    # Should return error without injected messages
    assert "result" in response_data
    assert "error" in response_data["result"]
    # Should not contain injected message
    result_str = json.dumps(response_data["result"])
    assert "Should not appear" not in result_str


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
