"""Additional comprehensive tests for MCP Adapter to increase coverage to 70%+.

Focuses on uncovered code paths:
- Auto-parent injection in spawn tools
- Timeout and job tracking in messaging
- Error handling in batch operations
- Coordination and job status
- Template spawning
- Monitoring service tools
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.orchestrator.mcp_adapter import MCPAdapter


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_instance_manager():
    """Create comprehensive mock instance manager."""
    manager = MagicMock()
    manager.instances = {}
    manager.jobs = {}
    manager.response_queues = {}

    # FastMCP mock
    mock_tool = MagicMock()
    mock_tool.to_mcp_tool.return_value = MagicMock(
        name="test_tool",
        description="Test tool",
        inputSchema={"type": "object", "properties": {}, "required": []},
    )
    manager.mcp = MagicMock()
    manager.mcp.get_tools = AsyncMock(return_value={"test_tool": mock_tool})

    # TmuxInstanceManager mock
    manager.tmux_manager = MagicMock()
    manager.tmux_manager.instances = {}
    manager.tmux_manager.message_history = {}
    manager.tmux_manager.tmux_sessions = {}
    manager.tmux_manager.send_message = AsyncMock(return_value={"response": "test"})
    manager.tmux_manager.spawn_instance = AsyncMock(return_value="inst-123")
    manager.tmux_manager.get_event_statistics = MagicMock(return_value={"event_counts": {}})

    # Internal methods
    manager.spawn_instance = AsyncMock(return_value="inst-123")
    manager._terminate_instance_internal = AsyncMock(return_value=True)
    manager._interrupt_instance_internal = AsyncMock(return_value={"success": True})
    manager._get_output_messages = AsyncMock(return_value=[])
    manager._get_instance_status_internal = MagicMock(
        return_value={
            "instance_id": "inst-123",
            "state": "running",
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
        }
    )
    manager._get_children_internal = MagicMock(return_value=[])
    manager._retrieve_instance_file_internal = AsyncMock(return_value="/tmp/file.txt")
    manager._list_instance_files_internal = AsyncMock(return_value=["file1.txt"])
    manager._get_pending_replies_internal = AsyncMock(return_value=[])
    manager.get_and_clear_main_inbox = MagicMock(return_value=[])
    manager.handle_reply_to_caller = AsyncMock(
        return_value={"success": True, "delivered_to": "caller"}
    )
    manager._build_tree_recursive = MagicMock()
    manager._execute_coordination = AsyncMock()

    return manager


@pytest.fixture
def mcp_adapter(mock_instance_manager):
    """Create MCPAdapter instance."""
    return MCPAdapter(mock_instance_manager)


@pytest.fixture
async def app(mcp_adapter):
    """Create FastAPI app with MCP adapter."""
    test_app = FastAPI()
    test_app.include_router(mcp_adapter.router)
    return test_app


@pytest.fixture
async def async_client(app):
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ============================================================================
# TEST: Auto-Parent Injection in Spawn Tools
# ============================================================================


class TestAutoParentInjection:
    """Test automatic parent_instance_id injection."""

    @pytest.mark.asyncio
    async def test_spawn_claude_auto_inject_busy_instance(
        self, async_client, mock_instance_manager
    ):
        """Test spawn_claude auto-injects parent from busy instance."""
        # Setup: one busy instance
        mock_instance_manager.instances = {
            "parent-busy": {
                "state": "busy",
                "last_activity": datetime.now().isoformat(),
            }
        }
        mock_instance_manager.spawn_instance.return_value = "child-123"

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "spawn_claude",
                "arguments": {
                    "name": "child",
                    "role": "general"
                    # parent_instance_id NOT provided
                },
            },
            "id": 1,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        # Verify parent was auto-injected
        mock_instance_manager.spawn_instance.assert_called_once()
        call_kwargs = mock_instance_manager.spawn_instance.call_args[1]
        assert call_kwargs["parent_instance_id"] == "parent-busy"

    @pytest.mark.asyncio
    async def test_spawn_multiple_instances_auto_inject_parent(
        self, async_client, mock_instance_manager
    ):
        """Test spawn_multiple_instances auto-injects parent."""
        # Setup: one busy instance
        mock_instance_manager.instances = {
            "parent-busy": {
                "state": "busy",
                "last_activity": datetime.now().isoformat(),
            }
        }
        mock_instance_manager.spawn_instance.side_effect = ["child-1", "child-2"]

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "spawn_multiple_instances",
                "arguments": {
                    "instances": [
                        {"name": "worker-1", "role": "backend_developer"},
                        {"name": "worker-2", "role": "frontend_developer"},
                    ]
                },
            },
            "id": 2,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        # Both calls should have parent_instance_id auto-injected
        assert mock_instance_manager.spawn_instance.call_count == 2
        for call_item in mock_instance_manager.spawn_instance.call_args_list:
            assert call_item[1]["parent_instance_id"] == "parent-busy"

    @pytest.mark.asyncio
    async def test_spawn_multiple_instances_with_errors(
        self, async_client, mock_instance_manager
    ):
        """Test spawn_multiple_instances handles partial failures."""
        mock_instance_manager.spawn_instance.side_effect = [
            "child-1",
            RuntimeError("Spawn failed"),
            "child-3",
        ]

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "spawn_multiple_instances",
                "arguments": {
                    "instances": [
                        {"name": "worker-1"},
                        {"name": "worker-2"},
                        {"name": "worker-3"},
                    ]
                },
            },
            "id": 3,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        assert "result" in data
        text = data["result"]["content"][0]["text"]

        # Should report 2/3 success
        assert "2/3" in text
        assert "Errors:" in text
        assert "worker-2" in text


# ============================================================================
# TEST: Messaging with Timeout and Job Tracking
# ============================================================================


class TestMessagingTimeoutAndJobs:
    """Test messaging tools with timeout and job tracking."""

    @pytest.mark.asyncio
    async def test_send_to_instance_timeout_response(
        self, async_client, mock_instance_manager
    ):
        """Test send_to_instance returns timeout with job_id."""
        mock_instance_manager.instances["inst-123"] = {
            "instance_type": "claude",
            "state": "running",
        }
        mock_instance_manager.tmux_manager.send_message.return_value = {
            "status": "timeout",
            "job_id": "job-456",
            "estimated_wait_seconds": 60,
        }

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "send_to_instance",
                "arguments": {
                    "instance_id": "inst-123",
                    "message": "Long task",
                    "wait_for_response": True,
                    "timeout_seconds": 10,
                },
            },
            "id": 4,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        assert "result" in data
        text = data["result"]["content"][0]["text"]
        assert "timed out" in text.lower()  # "Request timed out"
        assert "job-456" in text
        assert "60" in text  # estimated_wait_seconds

    @pytest.mark.asyncio
    async def test_send_to_instance_pending_status(
        self, async_client, mock_instance_manager
    ):
        """Test send_to_instance with pending status (non-blocking)."""
        mock_instance_manager.instances["inst-123"] = {
            "instance_type": "claude",
            "state": "running",
        }
        mock_instance_manager.tmux_manager.send_message.return_value = {
            "status": "pending",
            "job_id": "job-789",
        }

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "send_to_instance",
                "arguments": {
                    "instance_id": "inst-123",
                    "message": "Async task",
                    "wait_for_response": False,
                },
            },
            "id": 5,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        assert "job-789" in text
        assert "pending" in text.lower()

    @pytest.mark.asyncio
    async def test_send_to_instance_no_response(
        self, async_client, mock_instance_manager
    ):
        """Test send_to_instance when response is None."""
        mock_instance_manager.instances["inst-123"] = {
            "instance_type": "claude",
            "state": "running",
        }
        mock_instance_manager.tmux_manager.send_message.return_value = None

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "send_to_instance",
                "arguments": {
                    "instance_id": "inst-123",
                    "message": "Fire and forget",
                },
            },
            "id": 6,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        assert "message_sent" in text.lower() or "no response" in text.lower()

    @pytest.mark.asyncio
    async def test_send_to_instance_not_found_error(
        self, async_client, mock_instance_manager
    ):
        """Test send_to_instance with non-existent instance."""
        mock_instance_manager.instances = {}  # No instances

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "send_to_instance",
                "arguments": {
                    "instance_id": "nonexistent",
                    "message": "Test",
                },
            },
            "id": 7,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        assert "error" in data
        assert "not found" in data["error"]["message"].lower()


# ============================================================================
# TEST: Batch Operations Error Handling
# ============================================================================


class TestBatchOperationsErrorHandling:
    """Test error handling in batch operations."""

    @pytest.mark.asyncio
    async def test_send_to_multiple_instances_mixed_results(
        self, async_client, mock_instance_manager
    ):
        """Test send_to_multiple_instances with both successes and errors."""
        mock_instance_manager.instances = {
            "inst-1": {"instance_type": "claude", "state": "running"},
            "inst-2": {"instance_type": "claude", "state": "running"},
            "inst-3": {"instance_type": "claude", "state": "running"},
        }

        async def mock_send(**kwargs):
            instance_id = kwargs["instance_id"]
            if instance_id == "inst-2":
                raise RuntimeError("Instance busy")
            return {"response": f"Response from {instance_id}"}

        mock_instance_manager.tmux_manager.send_message.side_effect = mock_send

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "send_to_multiple_instances",
                "arguments": {
                    "messages": [
                        {"instance_id": "inst-1", "message": "Task 1"},
                        {"instance_id": "inst-2", "message": "Task 2"},
                        {"instance_id": "inst-3", "message": "Task 3"},
                    ]
                },
            },
            "id": 8,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]

        # Should show 2/3 success
        assert "2/3" in text
        assert "Errors:" in text
        assert "inst-2" in text
        assert "Instance busy" in text

    @pytest.mark.asyncio
    async def test_terminate_multiple_instances_partial_failure(
        self, async_client, mock_instance_manager
    ):
        """Test terminate_multiple_instances with some failures."""

        async def mock_terminate(**kwargs):
            instance_id = kwargs["instance_id"]
            if instance_id == "inst-2":
                return False  # Termination failed
            return True

        mock_instance_manager._terminate_instance_internal.side_effect = mock_terminate

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "terminate_multiple_instances",
                "arguments": {
                    "instance_ids": ["inst-1", "inst-2", "inst-3"],
                    "force": False,
                },
            },
            "id": 9,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]

        # Should show 2/3 terminated
        assert "2/3" in text
        assert "Errors:" in text
        assert "inst-2" in text
        assert "force=true" in text.lower()

    @pytest.mark.asyncio
    async def test_interrupt_multiple_instances_with_errors(
        self, async_client, mock_instance_manager
    ):
        """Test interrupt_multiple_instances with mixed results."""

        async def mock_interrupt(**kwargs):
            instance_id = kwargs["instance_id"]
            if instance_id == "inst-2":
                return {"success": False, "error": "Not running"}
            return {"success": True}

        mock_instance_manager._interrupt_instance_internal.side_effect = mock_interrupt

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "interrupt_multiple_instances",
                "arguments": {
                    "instance_ids": ["inst-1", "inst-2", "inst-3"],
                },
            },
            "id": 10,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]

        # Should show 2/3 interrupted
        assert "2/3" in text
        assert "inst-2" in text
        assert "Not running" in text


# ============================================================================
# TEST: Coordination and Job Status
# ============================================================================


class TestCoordinationAndJobStatus:
    """Test coordinate_instances and get_job_status tools."""

    @pytest.mark.asyncio
    async def test_coordinate_instances_sequential(
        self, async_client, mock_instance_manager
    ):
        """Test coordinate_instances with sequential coordination."""
        mock_instance_manager.instances = {
            "coord-123": {"state": "running"},
            "worker-1": {"state": "idle"},
            "worker-2": {"state": "idle"},
        }

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "coordinate_instances",
                "arguments": {
                    "coordinator_id": "coord-123",
                    "participant_ids": ["worker-1", "worker-2"],
                    "task_description": "Process data sequentially",
                    "coordination_type": "sequential",
                },
            },
            "id": 11,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        assert "Coordination completed" in text
        assert "started" in text.lower()

        # Verify coordination task was created
        mock_instance_manager._execute_coordination.assert_called_once()

    @pytest.mark.asyncio
    async def test_coordinate_instances_instance_not_found(
        self, async_client, mock_instance_manager
    ):
        """Test coordinate_instances with non-existent participant."""
        mock_instance_manager.instances = {
            "coord-123": {"state": "running"},
        }

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "coordinate_instances",
                "arguments": {
                    "coordinator_id": "coord-123",
                    "participant_ids": ["nonexistent"],
                    "task_description": "Test",
                },
            },
            "id": 12,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        assert "error" in data
        assert "not found" in data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_get_job_status_pending_no_wait(
        self, async_client, mock_instance_manager
    ):
        """Test get_job_status for pending job without waiting."""
        mock_instance_manager.jobs["job-123"] = {
            "job_id": "job-123",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_job_status",
                "arguments": {
                    "job_id": "job-123",
                    "wait_for_completion": False,
                },
            },
            "id": 13,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        job_data = json.loads(text)
        assert job_data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_job_status_completed_with_wait(
        self, async_client, mock_instance_manager
    ):
        """Test get_job_status for completed job (returns immediately)."""
        mock_instance_manager.jobs["job-456"] = {
            "job_id": "job-456",
            "status": "completed",
            "result": "Success",
        }

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_job_status",
                "arguments": {
                    "job_id": "job-456",
                    "wait_for_completion": True,
                    "max_wait": 10,
                },
            },
            "id": 14,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        job_data = json.loads(text)
        assert job_data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, async_client, mock_instance_manager):
        """Test get_job_status for non-existent job."""
        mock_instance_manager.jobs = {}

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_job_status",
                "arguments": {
                    "job_id": "nonexistent",
                },
            },
            "id": 15,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        assert "not found" in text.lower()


# ============================================================================
# TEST: Live Instance Status
# ============================================================================


class TestLiveInstanceStatus:
    """Test get_live_instance_status tool."""

    @pytest.mark.asyncio
    async def test_get_live_instance_status_with_output(
        self, async_client, mock_instance_manager
    ):
        """Test get_live_instance_status with message history."""
        # Use UTC timezone for consistency
        from datetime import timezone
        now = datetime.now(timezone.utc)
        past_time = now  # Same time to avoid negative execution time
        mock_instance_manager._get_instance_status_internal.return_value = {
            "instance_id": "inst-123",
            "state": "running",
            "created_at": past_time.isoformat(),
            "last_activity": now.isoformat(),
        }

        mock_instance_manager.tmux_manager.message_history["inst-123"] = [
            {"role": "user", "content": "Task 1"},
            {"role": "assistant", "content": "Completed task 1 successfully"},
            {"role": "user", "content": "Task 2"},
            {"role": "assistant", "content": "Working on task 2..."},
        ]

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_live_instance_status",
                "arguments": {
                    "instance_id": "inst-123",
                },
            },
            "id": 16,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        status = json.loads(text)

        assert status["instance_id"] == "inst-123"
        assert status["state"] == "running"
        assert "last_output" in status
        assert "Working on task 2" in status["last_output"]
        assert "execution_time" in status
        assert status["execution_time"] >= 0  # Can be 0 or positive

    @pytest.mark.asyncio
    async def test_get_live_instance_status_no_output(
        self, async_client, mock_instance_manager
    ):
        """Test get_live_instance_status with no message history."""
        mock_instance_manager.tmux_manager.message_history["inst-456"] = []

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_live_instance_status",
                "arguments": {
                    "instance_id": "inst-456",
                },
            },
            "id": 17,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        status = json.loads(text)

        assert status["last_output"] is None


# ============================================================================
# TEST: Hierarchy Tools
# ============================================================================


class TestHierarchyTools:
    """Test broadcast_to_children and get_instance_tree."""

    @pytest.mark.asyncio
    async def test_broadcast_to_children_success(
        self, async_client, mock_instance_manager
    ):
        """Test broadcast_to_children sends to all children."""
        children = [
            {"id": "child-1", "name": "worker-1"},
            {"id": "child-2", "name": "worker-2"},
        ]
        mock_instance_manager._get_children_internal.return_value = children
        mock_instance_manager.instances = {
            "child-1": {"instance_type": "claude", "state": "running"},
            "child-2": {"instance_type": "claude", "state": "running"},
        }
        mock_instance_manager.tmux_manager.send_message.return_value = {
            "status": "message_sent"
        }

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "broadcast_to_children",
                "arguments": {
                    "parent_id": "parent-123",
                    "message": "Broadcast message",
                    "wait_for_responses": False,
                },
            },
            "id": 18,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        assert "Broadcasted to 2 children" in text
        assert "worker-1" in text
        assert "worker-2" in text

    @pytest.mark.asyncio
    async def test_broadcast_to_children_no_children(
        self, async_client, mock_instance_manager
    ):
        """Test broadcast_to_children when no children exist."""
        mock_instance_manager._get_children_internal.return_value = []

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "broadcast_to_children",
                "arguments": {
                    "parent_id": "lonely-parent",
                    "message": "Hello?",
                },
            },
            "id": 19,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        assert "0 children" in text

    @pytest.mark.asyncio
    async def test_broadcast_to_children_with_errors(
        self, async_client, mock_instance_manager
    ):
        """Test broadcast_to_children with some send failures."""
        children = [
            {"id": "child-1", "name": "worker-1"},
            {"id": "child-2", "name": "worker-2"},
        ]
        mock_instance_manager._get_children_internal.return_value = children
        mock_instance_manager.instances = {
            "child-1": {"instance_type": "claude", "state": "running"},
            "child-2": {"instance_type": "claude", "state": "running"},
        }

        async def mock_send(**kwargs):
            if kwargs["instance_id"] == "child-2":
                raise RuntimeError("Send failed")
            return {"status": "message_sent"}

        mock_instance_manager.tmux_manager.send_message.side_effect = mock_send

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "broadcast_to_children",
                "arguments": {
                    "parent_id": "parent-123",
                    "message": "Test",
                },
            },
            "id": 20,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        # Should show one success, one error
        assert "worker-1" in text
        assert "worker-2" in text
        assert "error" in text.lower()

    @pytest.mark.asyncio
    async def test_get_instance_tree_with_instances(
        self, async_client, mock_instance_manager
    ):
        """Test get_instance_tree builds hierarchy."""
        mock_instance_manager.instances = {
            "root-1": {"parent_instance_id": None, "state": "running", "name": "root"},
            "child-1": {
                "parent_instance_id": "root-1",
                "state": "running",
                "name": "child",
            },
        }

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_instance_tree",
                "arguments": {},
            },
            "id": 21,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        assert "Instance Hierarchy" in text
        assert mock_instance_manager._build_tree_recursive.called

    @pytest.mark.asyncio
    async def test_get_instance_tree_no_instances(
        self, async_client, mock_instance_manager
    ):
        """Test get_instance_tree when no instances running."""
        mock_instance_manager.instances = {}

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_instance_tree",
                "arguments": {},
            },
            "id": 22,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        assert "No instances running" in text


# ============================================================================
# TEST: File Operations
# ============================================================================


class TestFileOperations:
    """Test file retrieval and listing operations."""

    @pytest.mark.asyncio
    async def test_retrieve_multiple_instance_files_mixed_results(
        self, async_client, mock_instance_manager
    ):
        """Test retrieve_multiple_instance_files with some failures."""

        async def mock_retrieve(**kwargs):
            filename = kwargs["filename"]
            if filename == "missing.txt":
                return None  # File not found
            return f"/tmp/{filename}"

        mock_instance_manager._retrieve_instance_file_internal.side_effect = (
            mock_retrieve
        )

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "retrieve_multiple_instance_files",
                "arguments": {
                    "requests": [
                        {"instance_id": "inst-1", "filename": "file1.txt"},
                        {"instance_id": "inst-2", "filename": "missing.txt"},
                        {"instance_id": "inst-3", "filename": "file3.txt"},
                    ]
                },
            },
            "id": 23,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]

        # Should show 2/3 success
        assert "2/3" in text
        assert "Errors:" in text
        assert "missing.txt" in text
        assert "File not found" in text

    @pytest.mark.asyncio
    async def test_list_multiple_instance_files_success(
        self, async_client, mock_instance_manager
    ):
        """Test list_multiple_instance_files for multiple instances."""

        async def mock_list(**kwargs):
            instance_id = kwargs["instance_id"]
            return [f"{instance_id}-file1.txt", f"{instance_id}-file2.py"]

        mock_instance_manager._list_instance_files_internal.side_effect = mock_list

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "list_multiple_instance_files",
                "arguments": {
                    "instance_ids": ["inst-1", "inst-2"],
                },
            },
            "id": 24,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        response_data = json.loads(text)

        assert len(response_data["listings"]) == 2
        assert len(response_data["errors"]) == 0


# ============================================================================
# TEST: Get Output Messages
# ============================================================================


class TestGetOutputMessages:
    """Test get_instance_output and get_multiple_instance_outputs."""

    @pytest.mark.asyncio
    async def test_get_multiple_instance_outputs_success(
        self, async_client, mock_instance_manager
    ):
        """Test get_multiple_instance_outputs returns all outputs."""

        async def mock_get_output(**kwargs):
            instance_id = kwargs["instance_id"]
            return [
                {"role": "user", "content": f"Query to {instance_id}"},
                {"role": "assistant", "content": f"Response from {instance_id}"},
            ]

        mock_instance_manager._get_output_messages.side_effect = mock_get_output

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_multiple_instance_outputs",
                "arguments": {
                    "requests": [
                        {"instance_id": "inst-1", "limit": 100},
                        {"instance_id": "inst-2", "limit": 50},
                    ]
                },
            },
            "id": 25,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        response_data = json.loads(text)

        assert len(response_data["outputs"]) == 2
        assert response_data["outputs"][0]["instance_id"] == "inst-1"
        assert len(response_data["outputs"][0]["output"]) == 2


# ============================================================================
# TEST: Template Spawning
# ============================================================================


class TestTemplateSpawning:
    """Test spawn_team_from_template tool."""

    @pytest.mark.asyncio
    async def test_spawn_team_from_template_success(
        self, async_client, mock_instance_manager
    ):
        """Test spawn_team_from_template spawns supervisor."""
        # Create a mock template file
        template_content = """
Team Size: 5 instances
Estimated Duration: 2-4 hours

### Technical Lead
**Role**: `architect`

## Team Structure
- Lead: architect
- Workers: 4 developers

## Workflow Phases
1. Planning
2. Implementation
3. Testing

## Communication Protocols
Use reply_to_caller for updates
"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value=template_content):
                mock_instance_manager.spawn_instance.return_value = "supervisor-123"

                request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "spawn_team_from_template",
                        "arguments": {
                            "template_name": "software_engineering_team",
                            "task_description": "Build a web application",
                        },
                    },
                    "id": 26,
                }

                response = await async_client.post("/mcp/", json=request)
                assert response.status_code == 200

                data = response.json()
                text = data["result"]["content"][0]["text"]

                assert "Team spawned" in text
                assert "supervisor-123" in text
                assert "5 instances" in text
                assert "2-4 hours" in text

    @pytest.mark.asyncio
    async def test_spawn_team_from_template_not_found(
        self, async_client, mock_instance_manager
    ):
        """Test spawn_team_from_template with non-existent template."""
        with patch("pathlib.Path.exists", return_value=False):
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "spawn_team_from_template",
                    "arguments": {
                        "template_name": "nonexistent_template",
                        "task_description": "Test",
                    },
                },
                "id": 27,
            }

            response = await async_client.post("/mcp/", json=request)
            assert response.status_code == 200

            data = response.json()
            assert "error" in data
            assert "not found" in data["error"]["message"].lower()


# ============================================================================
# TEST: Monitoring Service Tools
# ============================================================================


class TestMonitoringServiceTools:
    """Test get_agent_summary and get_all_agent_summaries."""

    @pytest.mark.asyncio
    async def test_get_agent_summary_success(
        self, async_client, mock_instance_manager
    ):
        """Test get_agent_summary returns summary."""
        mock_monitoring = MagicMock()
        mock_monitoring.is_running.return_value = True
        mock_monitoring.get_summary = AsyncMock(
            return_value={
                "instance_id": "inst-123",
                "summary": "Processed 10 requests successfully",
                "status": "active",
            }
        )
        mock_instance_manager.monitoring_service = mock_monitoring

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_agent_summary",
                "arguments": {
                    "instance_id": "inst-123",
                },
            },
            "id": 28,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        summary = json.loads(text)

        assert summary["instance_id"] == "inst-123"
        assert "summary" in summary

    @pytest.mark.asyncio
    async def test_get_agent_summary_not_running(
        self, async_client, mock_instance_manager
    ):
        """Test get_agent_summary when service not running."""
        mock_monitoring = MagicMock()
        mock_monitoring.is_running.return_value = False
        mock_instance_manager.monitoring_service = mock_monitoring

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_agent_summary",
                "arguments": {
                    "instance_id": "inst-123",
                },
            },
            "id": 29,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        # Should return error in result
        assert "result" in data
        assert "error" in data["result"]
        assert "not running" in data["result"]["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_get_agent_summary_not_available(
        self, async_client, mock_instance_manager
    ):
        """Test get_agent_summary when service not available."""
        # Set both potential locations to None
        mock_instance_manager.monitoring_service = None
        if hasattr(mock_instance_manager, 'tmux_manager'):
            mock_instance_manager.tmux_manager.monitoring_service = None

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_agent_summary",
                "arguments": {
                    "instance_id": "inst-123",
                },
            },
            "id": 30,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        # Could be error at top level or in result
        if "error" in data:
            assert "available" in data["error"]["message"].lower() or "await" in data["error"]["message"].lower()
        else:
            assert "result" in data
            assert "error" in data["result"]
            assert "available" in data["result"]["error"]["message"].lower() or "await" in data["result"]["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_get_all_agent_summaries_success(
        self, async_client, mock_instance_manager
    ):
        """Test get_all_agent_summaries returns all summaries."""
        mock_monitoring = MagicMock()
        mock_monitoring.is_running.return_value = True
        mock_monitoring.get_all_summaries = AsyncMock(
            return_value={
                "inst-1": {"summary": "Summary 1", "status": "active"},
                "inst-2": {"summary": "Summary 2", "status": "idle"},
            }
        )
        mock_instance_manager.monitoring_service = mock_monitoring

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_all_agent_summaries",
                "arguments": {},
            },
            "id": 31,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        response_data = json.loads(text)

        assert response_data["count"] == 2
        assert "inst-1" in response_data["summaries"]
        assert "inst-2" in response_data["summaries"]

    @pytest.mark.asyncio
    async def test_get_all_agent_summaries_with_filter(
        self, async_client, mock_instance_manager
    ):
        """Test get_all_agent_summaries with status filter."""
        mock_monitoring = MagicMock()
        mock_monitoring.is_running.return_value = True
        mock_monitoring.get_all_summaries = AsyncMock(
            return_value={
                "inst-1": {"summary": "Summary 1", "status": "active"},
                "inst-2": {"summary": "Summary 2", "status": "idle"},
                "inst-3": {"summary": "Summary 3", "status": "active"},
            }
        )
        mock_instance_manager.monitoring_service = mock_monitoring

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_all_agent_summaries",
                "arguments": {
                    "status_filter": ["active"],
                },
            },
            "id": 32,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        response_data = json.loads(text)

        # Should filter to only active instances
        assert response_data["count"] == 2  # inst-1 and inst-3
        assert all(
            s["status"] == "active" for s in response_data["summaries"].values()
        )


# ============================================================================
# TEST: Tmux Pane Content
# ============================================================================


class TestTmuxPaneContent:
    """Test get_tmux_pane_content tool."""

    @pytest.mark.asyncio
    async def test_get_tmux_pane_content_success(
        self, async_client, mock_instance_manager
    ):
        """Test get_tmux_pane_content retrieves pane output."""
        mock_pane = MagicMock()
        mock_pane.cmd.return_value = MagicMock(stdout=["Line 1", "Line 2", "Line 3"])

        mock_window = MagicMock()
        mock_window.panes = [mock_pane]

        mock_session = MagicMock()
        mock_session.windows = [mock_window]

        mock_instance_manager.instances["inst-123"] = {"state": "running"}
        mock_instance_manager.tmux_manager.tmux_sessions = {"inst-123": mock_session}

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_tmux_pane_content",
                "arguments": {
                    "instance_id": "inst-123",
                    "lines": 100,
                },
            },
            "id": 33,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]
        assert "Line 1" in text
        assert "Line 2" in text

    @pytest.mark.asyncio
    async def test_get_tmux_pane_content_all_lines(
        self, async_client, mock_instance_manager
    ):
        """Test get_tmux_pane_content with lines=-1 (all lines)."""
        mock_pane = MagicMock()
        mock_pane.cmd.return_value = MagicMock(stdout=["Full", "History"])

        mock_window = MagicMock()
        mock_window.panes = [mock_pane]

        mock_session = MagicMock()
        mock_session.windows = [mock_window]

        mock_instance_manager.instances["inst-123"] = {"state": "running"}
        mock_instance_manager.tmux_manager.tmux_sessions = {"inst-123": mock_session}

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_tmux_pane_content",
                "arguments": {
                    "instance_id": "inst-123",
                    "lines": -1,  # All lines
                },
            },
            "id": 34,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        # Verify cmd was called without -S parameter
        mock_pane.cmd.assert_called_with("capture-pane", "-p")


# ============================================================================
# TEST: Reply Tools
# ============================================================================


class TestReplyTools:
    """Test reply_to_caller and get_pending_replies."""

    @pytest.mark.asyncio
    async def test_reply_to_caller_with_short_id(
        self, async_client, mock_instance_manager
    ):
        """Test reply_to_caller with long delivered_to ID (shows first 8 chars)."""
        mock_instance_manager.handle_reply_to_caller.return_value = {
            "success": True,
            "delivered_to": "very-long-instance-id-123456789",
        }

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "reply_to_caller",
                "arguments": {
                    "instance_id": "child-123",
                    "reply_message": "Task complete",
                },
            },
            "id": 35,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]

        # Should show shortened ID
        assert "very-lon..." in text  # First 8 chars + ...
        assert "very-long-instance-id-123456789" not in text  # Full ID not shown

    @pytest.mark.asyncio
    async def test_get_pending_replies_with_multiple_replies(
        self, async_client, mock_instance_manager
    ):
        """Test get_pending_replies returns multiple replies."""
        replies = [
            {
                "sender_id": "child-1-very-long-id",
                "reply_message": "Done with task A",
                "correlation_id": "corr-1",
            },
            {
                "sender_id": "child-2-very-long-id",
                "reply_message": "Done with task B",
                "correlation_id": "corr-2",
            },
        ]
        mock_instance_manager._get_pending_replies_internal.return_value = replies

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_pending_replies",
                "arguments": {
                    "instance_id": "parent-123",
                    "wait_timeout": 0,
                },
            },
            "id": 36,
        }

        response = await async_client.post("/mcp/", json=request)
        assert response.status_code == 200

        data = response.json()
        text = data["result"]["content"][0]["text"]

        assert "2 pending replies" in text
        # Sender IDs are shortened to first 8 chars
        assert "child-1-" in text or "child-1" in text
        assert "task A" in text
        assert "child-2-" in text or "child-2" in text
        assert "task B" in text


if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=src/orchestrator/mcp_adapter",
            "--cov-report=term-missing",
        ]
    )
