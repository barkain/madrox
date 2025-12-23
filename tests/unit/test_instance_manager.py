"""Unit tests for instance_manager.py - Core orchestration logic."""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.orchestrator.instance_manager import InstanceManager


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return {
        "workspace_base_dir": "/tmp/test_workspace",
        "log_dir": "/tmp/test_logs",
        "log_level": "INFO",
        "max_concurrent_instances": 10,
        "instance_timeout_minutes": 60,
    }


@pytest.fixture
def mock_tmux_manager():
    """Create mock TmuxInstanceManager."""
    mock = MagicMock()
    mock.spawn_claude_instance = AsyncMock()
    mock.spawn_codex_instance = AsyncMock()
    mock.send_message = AsyncMock()
    mock.terminate_instance = AsyncMock()
    mock.get_pane_content = AsyncMock()
    mock.message_history = {}
    return mock


@pytest.fixture
def mock_logging_manager():
    """Create mock LoggingManager."""
    mock = MagicMock()
    mock.get_instance_logs = AsyncMock(return_value=[])
    mock.list_instances = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_shared_state_manager():
    """Create mock SharedStateManager."""
    mock = MagicMock()
    mock.create_response_queue = MagicMock()
    mock.get_response_queue = MagicMock()
    mock.register_message = MagicMock()
    mock.get_message_envelope = MagicMock()
    mock.cleanup_instance = MagicMock()
    return mock


@pytest.fixture
async def instance_manager(mock_config):
    """Create InstanceManager with mocked dependencies."""
    with patch("src.orchestrator.instance_manager.validate_model") as mock_validate:
        mock_validate.side_effect = lambda provider, model: model or "claude-sonnet-4-5"
        with patch("src.orchestrator.instance_manager.LoggingManager") as mock_log_mgr_class:
            with patch(
                "src.orchestrator.shared_state_manager.SharedStateManager"
            ) as mock_state_mgr_class:
                with patch(
                    "src.orchestrator.instance_manager.TmuxInstanceManager"
                ) as mock_tmux_mgr_class:
                    # Setup mocks
                    mock_log_mgr = MagicMock()
                    mock_state_mgr = MagicMock()
                    mock_tmux_mgr = MagicMock()
                    mock_tmux_mgr.message_history = {}
                    mock_tmux_mgr.instances = {}

                    # Mock async methods on tmux_manager with side effects to populate instances
                    instance_counter = {"count": 0}

                    async def mock_spawn_instance(*args, **kwargs):
                        instance_counter["count"] += 1
                        # Generate unique instance ID
                        instance_id = f"inst-{instance_counter['count']}"
                        instance_data = {
                            "instance_id": instance_id,
                            "name": kwargs.get("name", "test"),
                            "status": "running",
                            "instance_type": kwargs.get("instance_type", "claude"),
                            "parent_id": kwargs.get("parent_instance_id"),
                        }
                        mock_tmux_mgr.instances[instance_id] = instance_data
                        return instance_id

                    mock_tmux_mgr.spawn_instance = AsyncMock(side_effect=mock_spawn_instance)
                    mock_tmux_mgr.spawn_claude_instance = AsyncMock(return_value="inst-123")
                    mock_tmux_mgr.spawn_codex_instance = AsyncMock(return_value="codex-123")
                    mock_tmux_mgr.send_message = AsyncMock()
                    mock_tmux_mgr.terminate_instance = AsyncMock()
                    mock_tmux_mgr.get_pane_content = AsyncMock(return_value="")
                    mock_tmux_mgr.handle_reply_to_caller = AsyncMock(return_value={"success": True})

                    mock_log_mgr_class.return_value = mock_log_mgr
                    mock_state_mgr_class.return_value = mock_state_mgr
                    mock_tmux_mgr_class.return_value = mock_tmux_mgr

                    # Create instance manager
                    manager = InstanceManager(mock_config)

                    yield manager

                    # Cleanup
                    if hasattr(manager, "shutdown"):
                        try:
                            await manager.shutdown()
                        except Exception:  # noqa: E722
                            pass


class TestInstanceSpawning:
    """Test Claude/Codex instance creation."""

    @pytest.mark.asyncio
    async def test_spawn_claude_success(self, instance_manager):
        """Test successful Claude instance spawning."""
        # Execute - use .fn to access the actual function from FunctionTool
        result = await instance_manager.spawn_claude.fn(
            instance_manager, name="test-instance", role="general", model="claude-sonnet-4-5"
        )

        # Assert
        assert "instance_id" in result
        assert result["status"] == "spawned"
        assert result["name"] == "test-instance"
        assert result["instance_id"] in instance_manager.instances

    @pytest.mark.asyncio
    async def test_spawn_claude_with_custom_model(self, instance_manager):
        """Test spawning Claude with specific model."""
        instance_manager.tmux_manager.spawn_claude_instance = AsyncMock(return_value="inst-456")

        result = await instance_manager.spawn_claude.fn(
            instance_manager, name="haiku-instance", role="general", model="claude-haiku-4-5"
        )

        assert "instance_id" in result
        assert "spawned" in result["status"]

    @pytest.mark.asyncio
    async def test_spawn_claude_with_parent_id(self, instance_manager):
        """Test spawning child instance with parent tracking."""
        # First, create the parent instance
        instance_manager.instances["parent-123"] = {
            "instance_id": "parent-123",
            "name": "parent",
            "status": "running",
        }

        result = await instance_manager.spawn_claude.fn(
            instance_manager,
            name="child-instance",
            role="backend_developer",
            parent_instance_id="parent-123",
        )

        assert "instance_id" in result
        # Verify the child has the parent_id set
        child_id = result["instance_id"]
        assert instance_manager.instances[child_id]["parent_id"] == "parent-123"

    @pytest.mark.asyncio
    async def test_spawn_claude_with_system_prompt(self, instance_manager):
        """Test spawning with custom system prompt."""
        instance_manager.tmux_manager.spawn_claude_instance = AsyncMock(return_value="custom-123")

        custom_prompt = "You are a specialized testing agent."
        result = await instance_manager.spawn_claude.fn(
            instance_manager, name="custom-agent", system_prompt=custom_prompt
        )

        assert "instance_id" in result

    @pytest.mark.asyncio
    async def test_spawn_claude_with_initial_prompt(self, instance_manager):
        """Test spawning with initial prompt."""
        instance_manager.tmux_manager.spawn_claude_instance = AsyncMock(return_value="init-123")

        result = await instance_manager.spawn_claude.fn(
            instance_manager, name="init-instance", initial_prompt="Start working on task X"
        )

        assert "instance_id" in result

    @pytest.mark.asyncio
    async def test_spawn_claude_with_mcp_servers(self, instance_manager):
        """Test spawning with MCP server configuration."""
        instance_manager.tmux_manager.spawn_claude_instance = AsyncMock(return_value="mcp-123")

        mcp_config = json.dumps(
            {"test_server": {"transport": "http", "url": "http://localhost:8000/mcp"}}
        )

        result = await instance_manager.spawn_claude.fn(
            instance_manager, name="mcp-instance", mcp_servers=mcp_config
        )

        assert "instance_id" in result

    @pytest.mark.asyncio
    async def test_spawn_claude_bypass_isolation(self, instance_manager):
        """Test spawning with bypass_isolation flag."""
        instance_manager.tmux_manager.spawn_claude_instance = AsyncMock(return_value="bypass-123")

        result = await instance_manager.spawn_claude.fn(
            instance_manager, name="bypass-instance", bypass_isolation=True
        )

        assert "instance_id" in result

    @pytest.mark.asyncio
    async def test_spawn_multiple_instances_success(self, instance_manager):
        """Test spawning multiple instances in parallel."""
        instance_manager.spawn_instance = AsyncMock(side_effect=["inst-1", "inst-2", "inst-3"])

        instances_config = [
            {"name": "instance-1", "role": "general"},
            {"name": "instance-2", "role": "backend_developer"},
            {"name": "instance-3", "role": "testing_specialist"},
        ]

        result = await instance_manager.spawn_multiple_instances.fn(
            instance_manager, instances_config
        )

        assert len(result["spawned"]) == 3
        assert len(result["errors"]) == 0
        assert result["spawned"][0]["instance_id"] == "inst-1"
        assert result["spawned"][1]["instance_id"] == "inst-2"
        assert result["spawned"][2]["instance_id"] == "inst-3"

    @pytest.mark.asyncio
    async def test_spawn_multiple_instances_with_errors(self, instance_manager):
        """Test handling errors when spawning multiple instances."""
        instance_manager.spawn_instance = AsyncMock(
            side_effect=["inst-1", Exception("Spawn failed"), "inst-3"]
        )

        instances_config = [
            {"name": "instance-1", "role": "general"},
            {"name": "instance-2", "role": "backend_developer"},
            {"name": "instance-3", "role": "testing_specialist"},
        ]

        result = await instance_manager.spawn_multiple_instances.fn(
            instance_manager, instances_config
        )

        assert len(result["spawned"]) == 2
        assert len(result["errors"]) == 1
        assert result["errors"][0]["error"] == "Spawn failed"

    @pytest.mark.asyncio
    async def test_spawn_codex_success(self, instance_manager):
        """Test successful Codex instance spawning."""
        instance_manager.tmux_manager.spawn_codex_instance = AsyncMock(return_value="codex-123")

        result = await instance_manager.spawn_codex.fn(
            instance_manager, name="codex-instance", model="gpt-5-codex"
        )

        assert "instance_id" in result
        assert result["status"] == "spawned"

    @pytest.mark.asyncio
    async def test_spawn_codex_with_sandbox_mode(self, instance_manager):
        """Test spawning Codex with sandbox mode."""
        instance_manager.tmux_manager.spawn_codex_instance = AsyncMock(return_value="sandbox-123")

        result = await instance_manager.spawn_codex.fn(
            instance_manager, name="sandbox-codex", sandbox_mode="workspace-write"
        )

        assert "instance_id" in result

    @pytest.mark.asyncio
    async def test_spawn_instance_validates_model(self, instance_manager):
        """Test that spawn_claude validates model names."""
        instance_manager.tmux_manager.spawn_claude_instance = AsyncMock(return_value="valid-123")

        # Valid model should work
        result = await instance_manager.spawn_claude.fn(
            instance_manager, name="test", model="claude-sonnet-4-5"
        )
        assert "instance_id" in result

    @pytest.mark.asyncio
    async def test_spawn_multiple_instances_empty_list(self, instance_manager):
        """Test spawning with empty instance list."""
        result = await instance_manager.spawn_multiple_instances.fn(instance_manager, [])

        assert result["spawned"] == []
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_spawn_claude_wait_for_ready(self, instance_manager):
        """Test spawning with wait_for_ready flag."""
        instance_manager.tmux_manager.spawn_claude_instance = AsyncMock(return_value="ready-123")

        result = await instance_manager.spawn_claude.fn(
            instance_manager, name="ready-instance", wait_for_ready=True
        )

        assert "instance_id" in result


class TestMessageSending:
    """Test bidirectional communication protocol."""

    @pytest.mark.asyncio
    async def test_send_to_instance_success(self, instance_manager):
        """Test sending message to instance."""
        # Setup instance
        instance_manager.instances["inst-123"] = {
            "instance_id": "inst-123",
            "instance_type": "claude",
            "status": "running",
        }

        instance_manager.tmux_manager.send_message = AsyncMock(
            return_value={"status": "message_sent", "response": "OK"}
        )

        result = await instance_manager.send_to_instance.fn(
            instance_manager, instance_id="inst-123", message="Test message"
        )

        assert result["status"] == "message_sent"
        instance_manager.tmux_manager.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_instance_not_found(self, instance_manager):
        """Test sending message to non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            await instance_manager.send_to_instance.fn(
                instance_manager, instance_id="nonexistent", message="Test"
            )

    @pytest.mark.asyncio
    async def test_send_to_instance_with_response(self, instance_manager):
        """Test sending message and waiting for response."""
        instance_manager.instances["inst-456"] = {
            "instance_id": "inst-456",
            "instance_type": "claude",
            "status": "running",
        }

        instance_manager.tmux_manager.send_message = AsyncMock(
            return_value={"status": "response_received", "response": "Task completed successfully"}
        )

        result = await instance_manager.send_to_instance.fn(
            instance_manager,
            instance_id="inst-456",
            message="Complete task",
            wait_for_response=True,
            timeout_seconds=30,
        )

        assert "response" in result

    @pytest.mark.asyncio
    async def test_send_to_instance_unsupported_type(self, instance_manager):
        """Test sending to unsupported instance type."""
        instance_manager.instances["unknown-123"] = {
            "instance_id": "unknown-123",
            "instance_type": "unknown",
            "status": "running",
        }

        with pytest.raises(ValueError, match="Unsupported instance type"):
            await instance_manager.send_to_instance.fn(
                instance_manager, instance_id="unknown-123", message="Test"
            )

    @pytest.mark.asyncio
    async def test_send_to_multiple_instances_success(self, instance_manager):
        """Test sending message to multiple instances."""
        # Setup instances
        for i in range(1, 4):
            instance_manager.instances[f"inst-{i}"] = {
                "instance_id": f"inst-{i}",
                "instance_type": "claude",
                "status": "running",
            }

        instance_manager.tmux_manager.send_message = AsyncMock(
            return_value={"status": "message_sent"}
        )

        # Patch send_to_instance to be callable
        async def mock_send_to_instance(**kwargs):
            return {"status": "sent", "instance_id": kwargs["instance_id"]}

        with patch.object(instance_manager, "send_to_instance", side_effect=mock_send_to_instance):
            result = await instance_manager.send_to_multiple_instances.fn(
                instance_manager,
                instance_ids=["inst-1", "inst-2", "inst-3"],
                message="Broadcast message",
            )

            assert len(result["sent"]) == 3
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_send_to_multiple_instances_with_errors(self, instance_manager):
        """Test sending to multiple instances with some failures."""
        instance_manager.instances["inst-1"] = {
            "instance_id": "inst-1",
            "instance_type": "claude",
            "status": "running",
        }
        # inst-2 doesn't exist
        instance_manager.instances["inst-3"] = {
            "instance_id": "inst-3",
            "instance_type": "claude",
            "status": "running",
        }

        instance_manager.tmux_manager.send_message = AsyncMock(
            return_value={"status": "message_sent"}
        )

        # Patch send_to_instance to simulate errors for non-existent instance
        async def mock_send_to_instance(**kwargs):
            if kwargs["instance_id"] == "inst-2":
                raise ValueError("Instance not found")
            return {"status": "sent"}

        with patch.object(instance_manager, "send_to_instance", side_effect=mock_send_to_instance):
            result = await instance_manager.send_to_multiple_instances.fn(
                instance_manager,
                instance_ids=["inst-1", "inst-2", "inst-3"],
                message="Test message",
            )

            assert len(result["sent"]) == 2
            assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_send_to_multiple_instances_empty_list(self, instance_manager):
        """Test sending to empty instance list."""
        result = await instance_manager.send_to_multiple_instances.fn(
            instance_manager, instance_ids=[], message="Test"
        )

        assert result["sent"] == []
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_send_to_instance_codex_type(self, instance_manager):
        """Test sending message to Codex instance."""
        instance_manager.instances["codex-1"] = {
            "instance_id": "codex-1",
            "instance_type": "codex",
            "status": "running",
        }

        instance_manager.tmux_manager.send_message = AsyncMock(
            return_value={"status": "message_sent"}
        )

        result = await instance_manager.send_to_instance.fn(
            instance_manager, instance_id="codex-1", message="Test codex message"
        )

        assert "status" in result

    @pytest.mark.asyncio
    async def test_send_with_custom_timeout(self, instance_manager):
        """Test sending message with custom timeout."""
        instance_manager.instances["inst-timeout"] = {
            "instance_id": "inst-timeout",
            "instance_type": "claude",
            "status": "running",
        }

        instance_manager.tmux_manager.send_message = AsyncMock(
            return_value={"status": "message_sent"}
        )

        result = await instance_manager.send_to_instance.fn(
            instance_manager,
            instance_id="inst-timeout",
            message="Long running task",
            timeout_seconds=300,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_reply_to_caller_success(self, instance_manager):
        """Test replying to caller instance."""
        instance_manager.instances["child-1"] = {
            "instance_id": "child-1",
            "parent_id": "parent-1",
            "status": "running",
        }

        instance_manager.shared_state_manager.add_pending_reply = AsyncMock()

        result = await instance_manager.reply_to_caller.fn(
            instance_manager,
            instance_id="child-1",
            reply_message="Task completed",
            correlation_id="corr-123",
        )

        assert "success" in result

    @pytest.mark.asyncio
    async def test_send_to_multiple_with_wait_for_responses(self, instance_manager):
        """Test sending to multiple instances and waiting for responses."""
        for i in range(1, 3):
            instance_manager.instances[f"inst-{i}"] = {
                "instance_id": f"inst-{i}",
                "instance_type": "claude",
                "status": "running",
            }

        instance_manager.tmux_manager.send_message = AsyncMock(
            return_value={"status": "response_received", "response": "Done"}
        )

        # Patch send_to_instance to be callable
        async def mock_send_to_instance(**kwargs):
            return {"status": "sent", "response": "Done"}

        with patch.object(instance_manager, "send_to_instance", side_effect=mock_send_to_instance):
            result = await instance_manager.send_to_multiple_instances.fn(
                instance_manager,
                instance_ids=["inst-1", "inst-2"],
                message="Execute task",
                wait_for_responses=True,
            )

            assert len(result["sent"]) == 2

    @pytest.mark.asyncio
    async def test_send_message_returns_none(self, instance_manager):
        """Test handling when tmux_manager.send_message returns None."""
        instance_manager.instances["inst-none"] = {
            "instance_id": "inst-none",
            "instance_type": "claude",
            "status": "running",
        }

        instance_manager.tmux_manager.send_message = AsyncMock(return_value=None)

        result = await instance_manager.send_to_instance.fn(
            instance_manager, instance_id="inst-none", message="Test"
        )

        assert result["status"] == "message_sent"


class TestTeamCoordination:
    """Test multi-instance collaboration."""

    @pytest.mark.asyncio
    async def test_spawn_team_from_template_success(self, instance_manager):
        """Test spawning team from template."""
        # Mock template file reading
        template_content = """
        ## Team Metadata
        supervisor_role: architect
        estimated_duration: 2-4 hours
        team_size: 3

        ## Supervisor Instructions
        You are the team supervisor.

        ## Team Members
        ### Backend Developer
        Role: backend_developer
        Responsibilities: API development

        ### Frontend Developer
        Role: frontend_developer
        Responsibilities: UI development
        """

        instance_manager.spawn_instance = AsyncMock(
            side_effect=["supervisor-1", "backend-1", "frontend-1"]
        )

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value=template_content):
                result = await instance_manager.spawn_team_from_template.fn(
                    instance_manager, template_name="test_team", task_description="Build a web app"
                )

                # Should have supervisor ID in the formatted message or be an error dict
                assert (isinstance(result, str) and "Supervisor ID:" in result) or (
                    isinstance(result, dict) and ("supervisor_id" in result or "error" in result)
                )

    @pytest.mark.asyncio
    async def test_coordinate_instances_sequential(self, instance_manager):
        """Test coordinating instances in sequential mode."""
        # Setup instances
        instance_manager.instances["coord-1"] = {"instance_id": "coord-1", "state": "running"}
        instance_manager.instances["p1"] = {"instance_id": "p1", "state": "running"}
        instance_manager.instances["p2"] = {"instance_id": "p2", "state": "running"}

        instance_manager.send_to_instance = AsyncMock(return_value={"status": "completed"})

        result = await instance_manager.coordinate_instances.fn(
            instance_manager,
            coordinator_id="coord-1",
            participant_ids=["p1", "p2"],
            task_description="Sequential task",
            coordination_type="sequential",
        )

        assert "task_id" in result or "status" in result

    @pytest.mark.asyncio
    async def test_coordinate_instances_parallel(self, instance_manager):
        """Test coordinating instances in parallel mode."""
        instance_manager.instances["coord-1"] = {"instance_id": "coord-1", "state": "running"}
        instance_manager.instances["p1"] = {"instance_id": "p1", "state": "running"}
        instance_manager.instances["p2"] = {"instance_id": "p2", "state": "running"}
        instance_manager.instances["p3"] = {"instance_id": "p3", "state": "running"}

        instance_manager.send_to_instance = AsyncMock(return_value={"status": "completed"})

        result = await instance_manager.coordinate_instances.fn(
            instance_manager,
            coordinator_id="coord-1",
            participant_ids=["p1", "p2", "p3"],
            task_description="Parallel task",
            coordination_type="parallel",
        )

        assert "task_id" in result or "status" in result

    @pytest.mark.asyncio
    async def test_broadcast_to_children_success(self, instance_manager):
        """Test broadcasting message to all children."""
        # Setup parent and children
        instance_manager.instances["parent-1"] = {
            "instance_id": "parent-1",
            "children": ["child-1", "child-2"],
        }
        instance_manager.instances["child-1"] = {
            "instance_id": "child-1",
            "parent_id": "parent-1",
            "instance_type": "claude",
        }
        instance_manager.instances["child-2"] = {
            "instance_id": "child-2",
            "parent_id": "parent-1",
            "instance_type": "claude",
        }

        instance_manager.tmux_manager.send_message = AsyncMock(
            return_value={"status": "message_sent"}
        )

        result = await instance_manager.broadcast_to_children.fn(
            instance_manager, parent_id="parent-1", message="Broadcast to all children"
        )

        assert "children_count" in result or "error" in result

    @pytest.mark.asyncio
    async def test_get_children_success(self, instance_manager):
        """Test retrieving all children of a parent."""
        instance_manager.instances["parent-1"] = {"instance_id": "parent-1", "id": "parent-1"}
        instance_manager.instances["child-1"] = {
            "instance_id": "child-1",
            "id": "child-1",
            "parent_instance_id": "parent-1",
            "name": "child-1",
            "status": "running",
        }
        instance_manager.instances["child-2"] = {
            "instance_id": "child-2",
            "id": "child-2",
            "parent_instance_id": "parent-1",
            "name": "child-2",
            "status": "running",
        }

        result = instance_manager.get_children.fn(instance_manager, "parent-1")

        assert len(result) == 2
        assert result[0]["id"] in ["child-1", "child-2"]

    @pytest.mark.asyncio
    async def test_get_children_empty(self, instance_manager):
        """Test getting children when parent has none."""
        instance_manager.instances["parent-no-kids"] = {"instance_id": "parent-no-kids"}

        result = instance_manager.get_children.fn(instance_manager, "parent-no-kids")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_instance_tree(self, instance_manager):
        """Test building instance hierarchy tree."""
        # Setup hierarchy
        instance_manager.instances["root"] = {
            "instance_id": "root",
            "name": "root",
            "status": "running",
        }
        instance_manager.instances["child1"] = {
            "instance_id": "child1",
            "parent_id": "root",
            "name": "child1",
            "status": "running",
        }
        instance_manager.instances["grandchild"] = {
            "instance_id": "grandchild",
            "parent_id": "child1",
            "name": "grandchild",
            "status": "running",
        }

        tree = instance_manager.get_instance_tree.fn(
            instance_manager,
        )

        assert isinstance(tree, str)
        assert "root" in tree

    @pytest.mark.asyncio
    async def test_coordinate_instances_consensus(self, instance_manager):
        """Test coordinating instances in consensus mode."""
        for i in range(1, 4):
            instance_manager.instances[f"p{i}"] = {"instance_id": f"p{i}", "state": "running"}
        instance_manager.instances["coord"] = {"instance_id": "coord", "state": "running"}

        instance_manager.send_to_instance = AsyncMock(return_value={"status": "completed"})

        result = await instance_manager.coordinate_instances.fn(
            instance_manager,
            coordinator_id="coord",
            participant_ids=["p1", "p2", "p3"],
            task_description="Consensus task",
            coordination_type="consensus",
        )

        assert "task_id" in result or "status" in result

    @pytest.mark.asyncio
    async def test_broadcast_to_children_with_responses(self, instance_manager):
        """Test broadcasting and waiting for responses."""
        instance_manager.instances["parent-1"] = {"instance_id": "parent-1"}
        instance_manager.instances["child-1"] = {
            "instance_id": "child-1",
            "parent_id": "parent-1",
            "instance_type": "claude",
        }

        instance_manager.tmux_manager.send_message = AsyncMock(
            return_value={"status": "message_sent", "response": "Done"}
        )

        result = await instance_manager.broadcast_to_children.fn(
            instance_manager, parent_id="parent-1", message="Execute task", wait_for_responses=True
        )

        assert "children_count" in result or "error" in result

    @pytest.mark.asyncio
    async def test_spawn_team_template_not_found(self, instance_manager):
        """Test spawning team when template doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(ValueError, match="Template not found"):
                await instance_manager.spawn_team_from_template.fn(
                    instance_manager, template_name="nonexistent", task_description="Test task"
                )


class TestErrorHandling:
    """Test exception recovery and error scenarios."""

    @pytest.mark.asyncio
    async def test_spawn_instance_failure(self, instance_manager):
        """Test handling spawn failure."""

        # Override spawn_instance (which is called by spawn_claude) to raise an exception
        async def mock_spawn_fail(*args, **kwargs):
            raise Exception("Spawn failed")

        instance_manager.spawn_instance = mock_spawn_fail

        with pytest.raises(Exception, match="Spawn failed"):
            await instance_manager.spawn_claude.fn(
                instance_manager, name="fail-instance", role="general"
            )

    @pytest.mark.asyncio
    async def test_send_to_terminated_instance(self, instance_manager):
        """Test sending message to terminated instance."""
        # Instance exists but not in running state
        with pytest.raises(ValueError, match="not found"):
            await instance_manager.send_to_instance.fn(
                instance_manager, instance_id="terminated-inst", message="Test"
            )

    @pytest.mark.asyncio
    async def test_get_instance_output_not_found(self, instance_manager):
        """Test getting output from non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            await instance_manager.get_instance_output.fn(
                instance_manager, instance_id="nonexistent"
            )

    @pytest.mark.asyncio
    async def test_terminate_instance_not_found(self, instance_manager):
        """Test terminating non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            await instance_manager.terminate_instance.fn(
                instance_manager, instance_id="nonexistent"
            )

    @pytest.mark.asyncio
    async def test_interrupt_instance_not_found(self, instance_manager):
        """Test interrupting non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            await instance_manager.interrupt_instance.fn(
                instance_manager, instance_id="nonexistent"
            )

    @pytest.mark.asyncio
    async def test_coordinate_with_nonexistent_participants(self, instance_manager):
        """Test coordination with some non-existent participants."""
        instance_manager.instances["coord"] = {"instance_id": "coord", "state": "running"}
        instance_manager.instances["p1"] = {"instance_id": "p1", "state": "running"}
        # p2 doesn't exist

        instance_manager.send_to_instance = AsyncMock(
            side_effect=[{"status": "ok"}, ValueError("not found")]
        )

        # Should raise ValueError for non-existent participant
        with pytest.raises(ValueError, match="not found"):
            await instance_manager.coordinate_instances.fn(
                instance_manager,
                coordinator_id="coord",
                participant_ids=["p1", "p2"],
                task_description="Test coordination",
            )

    def test_get_instance_status_not_found(self, instance_manager):
        """Test getting status of non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            instance_manager.get_instance_status.fn(instance_manager, "nonexistent")

    @pytest.mark.asyncio
    async def test_invalid_model_name(self, instance_manager):
        """Test spawning with invalid model name."""

        # Override the fixture's validate_model mock to actually validate
        def validate_model_strict(provider, model):
            valid_models = ["claude-sonnet-4-5", "claude-opus-4", "claude-haiku-4-5"]
            if model and model not in valid_models:
                raise ValueError(f"Invalid model: {model}")
            return model or "claude-sonnet-4-5"

        with patch(
            "src.orchestrator.instance_manager.validate_model", side_effect=validate_model_strict
        ):
            with pytest.raises(ValueError, match="Invalid model"):
                await instance_manager.spawn_claude.fn(
                    instance_manager, name="test", model="invalid-model-name"
                )


# ============================================================================
# Part 2/2: Instance Output, Termination, File Operations, Status Management
# ============================================================================


class TestInstanceOutput:
    """Test instance output retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_instance_output_basic(self, instance_manager):
        """Test basic instance output retrieval."""
        # Setup
        instance_id = "inst-123"
        instance_manager.instances[instance_id] = {
            "id": instance_id,
            "name": "test-instance",
            "state": "running",
            "last_activity": datetime.now().isoformat(),
        }

        instance_manager.tmux_manager.message_history[instance_id] = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        # Execute
        result = await instance_manager.get_instance_output.fn(
            instance_manager, instance_id, limit=100
        )

        # Assert
        assert "instance_id" in result
        assert result["instance_id"] == instance_id
        assert "output" in result

    @pytest.mark.asyncio
    async def test_get_instance_output_with_limit(self, instance_manager):
        """Test output retrieval with limit parameter."""
        # Setup
        instance_id = "inst-123"
        instance_manager.instances[instance_id] = {
            "id": instance_id,
            "last_activity": datetime.now().isoformat(),
        }

        # Add 10 messages
        instance_manager.tmux_manager.message_history[instance_id] = [
            {"role": "user", "content": f"Message {i}"} for i in range(10)
        ]

        # Execute
        result = await instance_manager.get_instance_output.fn(
            instance_manager, instance_id, limit=3
        )

        # Assert - should respect limit
        assert len(result["output"]) <= 3

    @pytest.mark.asyncio
    async def test_get_instance_output_no_history(self, instance_manager):
        """Test output retrieval when no message history exists."""
        # Setup
        instance_id = "inst-123"
        instance_manager.instances[instance_id] = {
            "id": instance_id,
            "last_activity": datetime.now().isoformat(),
        }

        # No message history for this instance

        # Execute
        result = await instance_manager.get_instance_output.fn(instance_manager, instance_id)

        # Assert
        assert result["instance_id"] == instance_id
        assert result["output"] == []

    @pytest.mark.asyncio
    async def test_get_instance_output_instance_not_found(self, instance_manager):
        """Test output retrieval for nonexistent instance."""
        # Execute & Assert
        with pytest.raises(ValueError, match="Instance .* not found"):
            await instance_manager.get_instance_output.fn(instance_manager, "nonexistent-inst")

    @pytest.mark.asyncio
    async def test_get_instance_output_message_types(self, instance_manager):
        """Test output correctly identifies user vs response messages."""
        # Setup
        instance_id = "inst-123"
        instance_manager.instances[instance_id] = {
            "id": instance_id,
            "last_activity": datetime.now().isoformat(),
        }

        instance_manager.tmux_manager.message_history[instance_id] = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer"},
        ]

        # Execute
        result = await instance_manager.get_instance_output.fn(instance_manager, instance_id)

        # Assert
        assert result["output"][0]["type"] == "user"
        assert result["output"][1]["type"] == "response"


class TestInstanceTermination:
    """Test instance termination methods."""

    @pytest.mark.asyncio
    async def test_terminate_instance_success(self, instance_manager):
        """Test successful instance termination."""
        # Setup
        instance_id = "inst-123"
        instance_manager.instances[instance_id] = {
            "id": instance_id,
            "name": "test-instance",
            "state": "running",
        }

        # Mock the internal terminate method
        with patch.object(
            instance_manager, "_terminate_instance_internal", new_callable=AsyncMock
        ) as mock_terminate:
            mock_terminate.return_value = True

            # Execute
            result = await instance_manager.terminate_instance.fn(
                instance_manager, instance_id, force=False
            )

            # Assert
            assert result["instance_id"] == instance_id
            assert result["status"] == "terminated"
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_terminate_instance_force(self, instance_manager):
        """Test forced instance termination."""
        # Setup
        instance_id = "inst-123"

        with patch.object(
            instance_manager, "_terminate_instance_internal", new_callable=AsyncMock
        ) as mock_terminate:
            mock_terminate.return_value = True

            # Execute
            result = await instance_manager.terminate_instance.fn(
                instance_manager, instance_id, force=True
            )

            # Assert
            assert result["success"] is True
            mock_terminate.assert_called_once_with(instance_id=instance_id, force=True)

    @pytest.mark.asyncio
    async def test_terminate_instance_failure(self, instance_manager):
        """Test instance termination failure."""
        # Setup
        instance_id = "inst-123"

        with patch.object(
            instance_manager, "_terminate_instance_internal", new_callable=AsyncMock
        ) as mock_terminate:
            mock_terminate.return_value = False

            # Execute
            result = await instance_manager.terminate_instance.fn(instance_manager, instance_id)

            # Assert
            assert result["status"] == "failed"
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_pending_replies_no_instance(self, instance_manager):
        """Test getting pending replies for nonexistent instance."""
        # Execute & Assert
        with pytest.raises(ValueError, match="Instance .* not found"):
            await instance_manager._get_pending_replies_internal("nonexistent-inst")

    @pytest.mark.asyncio
    async def test_get_pending_replies_drains_queue(self, instance_manager):
        """Test that get_pending_replies drains all available messages."""
        # Setup
        instance_id = "inst-123"
        instance_manager.instances[instance_id] = {"id": instance_id}

        # Explicitly set shared_state to None so we use local queue
        instance_manager.tmux_manager.shared_state = None

        # Initialize response_queues as a real dict (not MagicMock)
        instance_manager.tmux_manager.response_queues = {}

        queue = asyncio.Queue()
        await queue.put({"message": "reply1"})
        await queue.put({"message": "reply2"})
        await queue.put({"message": "reply3"})

        instance_manager.tmux_manager.response_queues[instance_id] = queue

        # Execute
        replies = await instance_manager._get_pending_replies_internal(instance_id, wait_timeout=0)

        # Assert
        assert len(replies) == 3

    @pytest.mark.asyncio
    async def test_get_pending_replies_no_queue(self, instance_manager):
        """Test getting replies when no queue exists for instance."""
        # Setup
        instance_id = "inst-123"
        instance_manager.instances[instance_id] = {"id": instance_id}
        # No queue in response_queues

        # Execute
        replies = await instance_manager._get_pending_replies_internal(instance_id)

        # Assert
        assert replies == []

    @pytest.mark.asyncio
    async def test_reply_to_caller(self, instance_manager):
        """Test reply_to_caller delegates to handler."""
        # Setup
        instance_id = "inst-123"
        reply_message = "Reply message"
        correlation_id = "corr-123"

        with patch.object(
            instance_manager, "handle_reply_to_caller", new_callable=AsyncMock
        ) as mock_handler:
            mock_handler.return_value = {"status": "success"}

            # Execute
            result = await instance_manager.reply_to_caller.fn(
                instance_manager,
                instance_id=instance_id,
                reply_message=reply_message,
                correlation_id=correlation_id,
            )

            # Assert
            assert result["status"] == "success"


class TestFileOperations:
    """Test file operation methods."""

    @pytest.mark.asyncio
    async def test_retrieve_instance_file_success(self, instance_manager):
        """Test successful file retrieval from instance workspace."""
        # Setup
        instance_id = "inst-123"
        filename = "output.json"
        destination = "/tmp/output.json"

        with patch.object(
            instance_manager, "_retrieve_instance_file_internal", new_callable=AsyncMock
        ) as mock_retrieve:
            mock_retrieve.return_value = destination

            # Execute
            result = await instance_manager.retrieve_instance_file.fn(
                instance_manager, instance_id, filename, destination
            )

            # Assert
            assert result == destination

    @pytest.mark.asyncio
    async def test_retrieve_instance_file_not_found(self, instance_manager):
        """Test file retrieval when file doesn't exist."""
        # Setup
        with patch.object(
            instance_manager, "_retrieve_instance_file_internal", new_callable=AsyncMock
        ) as mock_retrieve:
            mock_retrieve.return_value = None

            # Execute
            result = await instance_manager.retrieve_instance_file.fn(
                instance_manager, "inst-123", "missing.txt"
            )

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_retrieve_multiple_instance_files(self, instance_manager):
        """Test batch file retrieval from multiple instances."""
        # Setup
        retrievals = [
            {"instance_id": "inst-1", "filename": "file1.txt"},
            {"instance_id": "inst-2", "filename": "file2.json"},
        ]

        with patch.object(
            instance_manager, "_retrieve_instance_file_internal", new_callable=AsyncMock
        ) as mock_retrieve:
            mock_retrieve.side_effect = ["/tmp/file1.txt", "/tmp/file2.json"]

            # Execute
            result = await instance_manager.retrieve_multiple_instance_files.fn(
                instance_manager, retrievals
            )

            # Assert
            assert len(result["retrieved"]) == 2
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_list_instance_files_success(self, instance_manager):
        """Test listing files in instance workspace."""
        # Setup
        instance_id = "inst-123"
        expected_files = ["file1.txt", "file2.json", "subdir/file3.py"]

        with patch.object(
            instance_manager, "_list_instance_files_internal", new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = expected_files

            # Execute
            files = await instance_manager.list_instance_files.fn(instance_manager, instance_id)

            # Assert
            assert files == expected_files

    @pytest.mark.asyncio
    async def test_list_instance_files_not_found(self, instance_manager):
        """Test listing files when instance not found."""
        # Setup
        with patch.object(
            instance_manager, "_list_instance_files_internal", new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = None

            # Execute
            files = await instance_manager.list_instance_files.fn(
                instance_manager, "nonexistent-inst"
            )

            # Assert
            assert files is None

    @pytest.mark.asyncio
    async def test_get_children_internal_basic(self, instance_manager):
        """Test getting child instances of a parent."""
        # Setup
        parent_id = "parent-1"
        instance_manager.instances = {
            "child-1": {
                "id": "child-1",
                "parent_instance_id": parent_id,
                "name": "Child 1",
                "role": "worker",
                "state": "running",
                "instance_type": "claude",
            },
            "child-2": {
                "id": "child-2",
                "parent_instance_id": parent_id,
                "name": "Child 2",
                "role": "worker",
                "state": "idle",
                "instance_type": "claude",
            },
        }

        # Execute
        children = instance_manager._get_children_internal(parent_id)

        # Assert
        assert len(children) == 2

    @pytest.mark.asyncio
    async def test_get_children_excludes_terminated(self, instance_manager):
        """Test that terminated instances are excluded by default."""
        # Setup
        parent_id = "parent-1"
        instance_manager.instances = {
            "child-1": {
                "id": "child-1",
                "parent_instance_id": parent_id,
                "state": "running",
                "name": "Running",
                "role": "worker",
                "instance_type": "claude",
            },
            "child-2": {
                "id": "child-2",
                "parent_instance_id": parent_id,
                "state": "terminated",
                "name": "Terminated",
                "role": "worker",
                "instance_type": "claude",
            },
        }

        # Execute
        children = instance_manager._get_children_internal(parent_id, include_terminated=False)

        # Assert
        assert len(children) == 1

    @pytest.mark.asyncio
    async def test_get_children_mcp_tool(self, instance_manager):
        """Test the public get_children MCP tool."""
        # Setup
        parent_id = "parent-1"
        instance_manager.instances = {
            "child-1": {
                "id": "child-1",
                "parent_instance_id": parent_id,
                "state": "running",
                "name": "Child",
                "role": "worker",
                "instance_type": "claude",
            }
        }

        # Execute
        children = instance_manager.get_children.fn(instance_manager, parent_id)

        # Assert
        assert len(children) == 1


class TestStatusManagement:
    """Test instance status management methods."""

    def test_get_instance_status_single_instance(self, instance_manager):
        """Test getting status for a single instance."""
        # Setup
        instance_id = "inst-123"
        instance_manager.instances[instance_id] = {
            "id": instance_id,
            "name": "test-instance",
            "state": "running",
            "role": "general",
        }

        # Execute
        status = instance_manager._get_instance_status_internal(instance_id=instance_id)

        # Assert
        assert status["id"] == instance_id
        assert status["name"] == "test-instance"
        assert status["state"] == "running"

    def test_get_instance_status_not_found(self, instance_manager):
        """Test getting status for nonexistent instance raises error."""
        # Execute & Assert
        with pytest.raises(ValueError, match="Instance .* not found"):
            instance_manager._get_instance_status_internal(instance_id="nonexistent")

    def test_get_instance_status_all_instances(self, instance_manager):
        """Test getting status for all instances."""
        # Setup
        instance_manager.instances = {
            "inst-1": {
                "id": "inst-1",
                "name": "Instance 1",
                "state": "running",
                "role": "worker",
            },
            "inst-2": {
                "id": "inst-2",
                "name": "Instance 2",
                "state": "idle",
                "role": "helper",
            },
        }

        # Execute
        result = instance_manager._get_instance_status_internal()

        # Assert
        assert "instances" in result
        assert "total_instances" in result
        assert result["total_instances"] == 2

    def test_get_instance_status_summary_only(self, instance_manager):
        """Test getting minimal status summary."""
        # Setup
        instance_manager.instances = {
            "inst-1": {
                "id": "inst-1",
                "name": "Instance 1",
                "state": "running",
                "role": "worker",
            }
        }

        # Execute
        result = instance_manager._get_instance_status_internal(summary_only=True)

        # Assert
        assert "instances" in result
        assert "total_instances" in result

    @pytest.mark.asyncio
    async def test_get_live_instance_status(self, instance_manager):
        """Test getting live status with execution time."""
        # Setup
        instance_id = "inst-123"
        from orchestrator.compat import UTC

        created_at = datetime.now(UTC)
        instance_manager.instances[instance_id] = {
            "id": instance_id,
            "created_at": created_at.isoformat(),
            "state": "running",
            "last_activity": datetime.now(UTC).isoformat(),
            "name": "Test Instance",
            "role": "worker",
        }

        # Execute
        status = await instance_manager.get_live_instance_status.fn(instance_manager, instance_id)

        # Assert
        assert status["instance_id"] == instance_id
        assert status["state"] == "running"
        assert "execution_time" in status

    @pytest.mark.asyncio
    async def test_get_live_status_not_found(self, instance_manager):
        """Test live status for nonexistent instance."""
        # Execute & Assert
        with pytest.raises(ValueError, match="Instance .* not found"):
            await instance_manager.get_live_instance_status.fn(instance_manager, "nonexistent")
