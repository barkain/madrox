"""Comprehensive unit tests for instance_manager.py to achieve 85%+ coverage."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.orchestrator.compat import UTC
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
        "artifacts_dir": "/tmp/test_artifacts",
    }


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
                    mock_state_mgr.instance_metadata = {}
                    mock_tmux_mgr = MagicMock()
                    mock_tmux_mgr.message_history = {}
                    mock_tmux_mgr.instances = {}
                    mock_tmux_mgr.response_queues = {}
                    mock_tmux_mgr.shared_state = None
                    mock_tmux_mgr.tmux_sessions = {}

                    # Mock async methods
                    instance_counter = {"count": 0}

                    async def mock_spawn_instance(*args, **kwargs):
                        instance_counter["count"] += 1
                        instance_id = f"inst-{instance_counter['count']}"
                        instance_data = {
                            "id": instance_id,
                            "instance_id": instance_id,
                            "name": kwargs.get("name", "test"),
                            "state": "running",
                            "instance_type": kwargs.get("instance_type", "claude"),
                            "parent_instance_id": kwargs.get("parent_instance_id"),
                            "role": kwargs.get("role", "general"),
                            "created_at": datetime.now(UTC).isoformat(),
                            "last_activity": datetime.now(UTC).isoformat(),
                            "total_tokens_used": 0,
                            "total_cost": 0.0,
                            "workspace_dir": f"/tmp/test_workspace/{instance_id}",
                            "resource_limits": {},
                        }
                        mock_tmux_mgr.instances[instance_id] = instance_data
                        return instance_id

                    mock_tmux_mgr.spawn_instance = AsyncMock(side_effect=mock_spawn_instance)
                    mock_tmux_mgr.send_message = AsyncMock(return_value={"status": "message_sent"})
                    mock_tmux_mgr.terminate_instance = AsyncMock(return_value=True)
                    mock_tmux_mgr.interrupt_instance = AsyncMock(return_value={"success": True})
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


class TestInstanceManagerInitialization:
    """Test InstanceManager initialization."""

    def test_initialization_creates_workspace(self, mock_config):
        """Test that initialization creates workspace directory."""
        with patch("pathlib.Path.mkdir"):
            with patch("src.orchestrator.instance_manager.LoggingManager"):
                with patch("src.orchestrator.shared_state_manager.SharedStateManager"):
                    with patch("src.orchestrator.instance_manager.TmuxInstanceManager"):
                        manager = InstanceManager(mock_config)

                        # Verify workspace was created
                        assert manager.workspace_base == Path(mock_config["workspace_base_dir"])

    def test_initialization_sets_config(self, instance_manager, mock_config):
        """Test that config is properly stored."""
        assert instance_manager.config == mock_config

    def test_initialization_creates_resource_tracking(self, instance_manager):
        """Test that resource tracking variables are initialized."""
        assert instance_manager.total_tokens_used == 0
        assert instance_manager.total_cost == 0.0

    def test_initialization_creates_empty_instances(self, instance_manager):
        """Test that instances dict starts empty."""
        # Only instances spawned manually should be present
        # The fixture creates manager without pre-spawned instances
        assert len([k for k in instance_manager.instances.keys() if k.startswith("inst-")]) == 0

    def test_initialization_creates_jobs_dict(self, instance_manager):
        """Test that jobs dictionary is initialized."""
        assert instance_manager.jobs == {}

    def test_initialization_creates_main_message_inbox(self, instance_manager):
        """Test that main message inbox is initialized."""
        assert instance_manager.main_message_inbox == []
        assert instance_manager._last_main_message_index == -1


class TestSpawnInstance:
    """Test spawn_instance method."""

    @pytest.mark.asyncio
    async def test_spawn_instance_basic(self, instance_manager):
        """Test basic instance spawning."""
        instance_id = await instance_manager.spawn_instance(name="test-basic", role="general")

        assert instance_id.startswith("inst-")
        assert instance_id in instance_manager.instances
        assert instance_manager.instances[instance_id]["name"] == "test-basic"
        assert instance_manager.instances[instance_id]["role"] == "general"

    @pytest.mark.asyncio
    async def test_spawn_instance_all_roles(self, instance_manager):
        """Test spawning with all 10 role types."""
        roles = [
            "general",
            "frontend_developer",
            "backend_developer",
            "testing_specialist",
            "documentation_writer",
            "code_reviewer",
            "architect",
            "debugger",
            "security_analyst",
            "data_analyst",
        ]

        for role in roles:
            instance_id = await instance_manager.spawn_instance(name=f"test-{role}", role=role)
            assert instance_manager.instances[instance_id]["role"] == role

    @pytest.mark.asyncio
    async def test_spawn_instance_with_parent(self, instance_manager):
        """Test spawning child instance with parent tracking."""
        # Create parent first
        parent_id = await instance_manager.spawn_instance(name="parent", role="general")

        # Create child
        child_id = await instance_manager.spawn_instance(
            name="child", role="general", parent_instance_id=parent_id
        )

        assert instance_manager.instances[child_id]["parent_instance_id"] == parent_id

    @pytest.mark.asyncio
    async def test_spawn_instance_invalid_parent(self, instance_manager):
        """Test spawning with non-existent parent raises error."""
        with pytest.raises(ValueError, match="parent_instance_id .* does not exist"):
            await instance_manager.spawn_instance(
                name="orphan", role="general", parent_instance_id="nonexistent"
            )

    @pytest.mark.asyncio
    async def test_spawn_instance_root_level(self, instance_manager):
        """Test spawning root-level instance (no parent)."""
        instance_id = await instance_manager.spawn_instance(
            name="root", role="general", parent_instance_id=None
        )

        assert instance_manager.instances[instance_id]["parent_instance_id"] is None

    @pytest.mark.asyncio
    async def test_spawn_instance_with_model(self, instance_manager):
        """Test spawning with specific model."""
        instance_id = await instance_manager.spawn_instance(
            name="haiku-test", role="general", model="claude-haiku-4-5"
        )

        assert instance_id in instance_manager.instances

    @pytest.mark.asyncio
    async def test_spawn_instance_with_system_prompt(self, instance_manager):
        """Test spawning with custom system prompt."""
        custom_prompt = "You are a specialized testing agent."
        instance_id = await instance_manager.spawn_instance(
            name="custom", role="general", system_prompt=custom_prompt
        )

        assert instance_id in instance_manager.instances

    @pytest.mark.asyncio
    async def test_spawn_instance_bypass_isolation(self, instance_manager):
        """Test spawning with bypass_isolation flag."""
        instance_id = await instance_manager.spawn_instance(
            name="bypass", role="general", bypass_isolation=True
        )

        assert instance_id in instance_manager.instances


class TestGetRolePrompt:
    """Test _get_role_prompt method."""

    def test_get_role_prompt_from_file(self, instance_manager):
        """Test loading role prompt from file."""
        test_prompt = "You are a test role."
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value=test_prompt):
                prompt = instance_manager._get_role_prompt("general")
                assert prompt == test_prompt

    def test_get_role_prompt_fallback(self, instance_manager):
        """Test fallback when file doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            prompt = instance_manager._get_role_prompt("general")
            assert "helpful AI assistant" in prompt

    def test_get_role_prompt_all_roles(self, instance_manager):
        """Test fallback prompts for all roles."""
        roles = [
            "general",
            "frontend_developer",
            "backend_developer",
            "testing_specialist",
            "documentation_writer",
            "code_reviewer",
            "architect",
            "debugger",
            "security_analyst",
            "data_analyst",
        ]

        with patch("pathlib.Path.exists", return_value=False):
            for role in roles:
                prompt = instance_manager._get_role_prompt(role)
                assert isinstance(prompt, str)
                assert len(prompt) > 0

    def test_get_role_prompt_error_handling(self, instance_manager):
        """Test error handling when file read fails."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", side_effect=Exception("Read error")):
                prompt = instance_manager._get_role_prompt("general")
                assert "expertise" in prompt


class TestSendToInstance:
    """Test send_to_instance method."""

    @pytest.mark.asyncio
    async def test_send_to_instance_success(self, instance_manager):
        """Test sending message to instance."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        result = await instance_manager.send_to_instance.fn(
            instance_manager, instance_id=instance_id, message="Test message"
        )

        assert "status" in result

    @pytest.mark.asyncio
    async def test_send_to_instance_not_found(self, instance_manager):
        """Test sending to non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            await instance_manager.send_to_instance.fn(
                instance_manager, instance_id="nonexistent", message="Test"
            )

    @pytest.mark.asyncio
    async def test_send_to_instance_wait_for_response(self, instance_manager):
        """Test sending with wait_for_response flag."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        instance_manager.tmux_manager.send_message = AsyncMock(
            return_value={"status": "completed", "response": "Done"}
        )

        result = await instance_manager.send_to_instance.fn(
            instance_manager,
            instance_id=instance_id,
            message="Test",
            wait_for_response=True,
            timeout_seconds=30,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_send_to_instance_timeout(self, instance_manager):
        """Test sending with custom timeout."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        result = await instance_manager.send_to_instance.fn(
            instance_manager,
            instance_id=instance_id,
            message="Long task",
            timeout_seconds=300,
        )

        assert result is not None


class TestGetInstanceStatus:
    """Test get_instance_status methods."""

    def test_get_instance_status_single(self, instance_manager):
        """Test getting status for single instance."""
        # Manually add instance
        instance_manager.instances["test-123"] = {
            "id": "test-123",
            "name": "test",
            "state": "running",
            "role": "general",
        }

        status = instance_manager._get_instance_status_internal(instance_id="test-123")

        assert status["id"] == "test-123"
        assert status["name"] == "test"

    def test_get_instance_status_all(self, instance_manager):
        """Test getting status for all instances."""
        instance_manager.instances["inst-1"] = {
            "id": "inst-1",
            "name": "Instance 1",
            "state": "running",
            "role": "general",
        }
        instance_manager.instances["inst-2"] = {
            "id": "inst-2",
            "name": "Instance 2",
            "state": "idle",
            "role": "general",
        }

        result = instance_manager._get_instance_status_internal()

        assert "instances" in result
        assert "total_instances" in result
        assert result["total_instances"] == 2
        assert "total_tokens_used" in result
        assert "total_cost" in result

    def test_get_instance_status_summary_only(self, instance_manager):
        """Test getting summary without full data."""
        instance_manager.instances["inst-1"] = {
            "id": "inst-1",
            "name": "Instance 1",
            "state": "running",
            "role": "general",
        }

        result = instance_manager._get_instance_status_internal(summary_only=True)

        assert "instances" in result
        assert "total_instances" in result
        assert "active_instances" in result
        # Should not have full cost/token data
        assert "total_cost" not in result

    def test_get_instance_status_not_found(self, instance_manager):
        """Test getting status for non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            instance_manager._get_instance_status_internal(instance_id="nonexistent")

    def test_get_instance_status_active_count(self, instance_manager):
        """Test active instance counting."""
        instance_manager.instances["inst-1"] = {
            "id": "inst-1",
            "state": "running",
            "role": "general",
            "name": "Active",
        }
        instance_manager.instances["inst-2"] = {
            "id": "inst-2",
            "state": "terminated",
            "role": "general",
            "name": "Terminated",
        }

        result = instance_manager._get_instance_status_internal()

        assert result["active_instances"] == 1


class TestTerminateInstance:
    """Test instance termination."""

    @pytest.mark.asyncio
    async def test_terminate_instance_success(self, instance_manager):
        """Test successful termination."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        result = await instance_manager.terminate_instance.fn(
            instance_manager, instance_id=instance_id
        )

        assert result["success"] is True
        assert result["status"] == "terminated"

    @pytest.mark.asyncio
    async def test_terminate_instance_force(self, instance_manager):
        """Test forced termination."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        result = await instance_manager.terminate_instance.fn(
            instance_manager, instance_id=instance_id, force=True
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_terminate_instance_not_found(self, instance_manager):
        """Test terminating non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            await instance_manager._terminate_instance_internal("nonexistent")

    @pytest.mark.asyncio
    async def test_terminate_instance_unsupported_type(self, instance_manager):
        """Test terminating unsupported instance type."""
        instance_manager.instances["unknown"] = {
            "id": "unknown",
            "instance_type": "unknown",
        }

        with pytest.raises(ValueError, match="Unsupported instance type"):
            await instance_manager._terminate_instance_internal("unknown")


class TestInterruptInstance:
    """Test instance interruption."""

    @pytest.mark.asyncio
    async def test_interrupt_instance_success(self, instance_manager):
        """Test interrupting instance."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        result = await instance_manager.interrupt_instance.fn(
            instance_manager, instance_id=instance_id
        )

        assert "success" in result

    @pytest.mark.asyncio
    async def test_interrupt_instance_not_found(self, instance_manager):
        """Test interrupting non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            await instance_manager._interrupt_instance_internal("nonexistent")


class TestGetChildren:
    """Test child instance retrieval."""

    def test_get_children_basic(self, instance_manager):
        """Test getting children of a parent."""
        instance_manager.instances["parent"] = {"id": "parent"}
        instance_manager.instances["child-1"] = {
            "id": "child-1",
            "parent_instance_id": "parent",
            "name": "Child 1",
            "role": "worker",
            "state": "running",
            "instance_type": "claude",
        }
        instance_manager.instances["child-2"] = {
            "id": "child-2",
            "parent_instance_id": "parent",
            "name": "Child 2",
            "role": "worker",
            "state": "running",
            "instance_type": "claude",
        }

        children = instance_manager._get_children_internal("parent")

        assert len(children) == 2

    def test_get_children_exclude_terminated(self, instance_manager):
        """Test that terminated children are excluded by default."""
        instance_manager.instances["parent"] = {"id": "parent"}
        instance_manager.instances["child-1"] = {
            "id": "child-1",
            "parent_instance_id": "parent",
            "state": "running",
            "name": "Running",
            "role": "worker",
            "instance_type": "claude",
        }
        instance_manager.instances["child-2"] = {
            "id": "child-2",
            "parent_instance_id": "parent",
            "state": "terminated",
            "name": "Terminated",
            "role": "worker",
            "instance_type": "claude",
        }

        children = instance_manager._get_children_internal("parent", include_terminated=False)

        assert len(children) == 1
        assert children[0]["id"] == "child-1"

    def test_get_children_include_terminated(self, instance_manager):
        """Test including terminated children."""
        instance_manager.instances["parent"] = {"id": "parent"}
        instance_manager.instances["child-1"] = {
            "id": "child-1",
            "parent_instance_id": "parent",
            "state": "terminated",
            "name": "Terminated",
            "role": "worker",
            "instance_type": "claude",
        }

        with patch("pathlib.Path.exists", return_value=False):
            children = instance_manager._get_children_internal("parent", include_terminated=True)

            assert len(children) == 1


class TestGetInstanceTree:
    """Test instance tree building."""

    def test_get_instance_tree_single_root(self, instance_manager):
        """Test tree with single root."""
        instance_manager.instances["root"] = {
            "id": "root",
            "name": "Root",
            "state": "running",
        }

        tree = instance_manager.get_instance_tree.fn(instance_manager)

        assert isinstance(tree, str)
        assert "Root" in tree

    def test_get_instance_tree_hierarchy(self, instance_manager):
        """Test tree with parent-child hierarchy."""
        instance_manager.instances["root"] = {
            "id": "root",
            "name": "Root",
            "state": "running",
            "instance_type": "claude",
        }
        instance_manager.instances["child"] = {
            "id": "child",
            "parent_instance_id": "root",
            "name": "Child",
            "state": "running",
            "instance_type": "claude",
        }

        tree = instance_manager.get_instance_tree.fn(instance_manager)

        assert "Root" in tree
        assert "Child" in tree

    def test_get_instance_tree_no_instances(self, instance_manager):
        """Test tree when no instances exist."""
        tree = instance_manager.get_instance_tree.fn(instance_manager)

        assert tree == "No instances running"


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, instance_manager):
        """Test health check terminates timed-out instances."""
        old_time = datetime.now(UTC) - timedelta(minutes=120)
        instance_data = {
            "id": "old-inst",
            "state": "running",
            "instance_type": "claude",
            "last_activity": old_time.isoformat(),
            "total_tokens_used": 0,
            "total_cost": 0.0,
            "resource_limits": {},
        }
        instance_manager.instances["old-inst"] = instance_data
        # Also add to tmux_manager instances
        instance_manager.tmux_manager.instances["old-inst"] = instance_data

        await instance_manager.health_check()

        # Should have called terminate on the timed-out instance
        instance_manager.tmux_manager.terminate_instance.assert_called()

    @pytest.mark.asyncio
    async def test_health_check_token_limit(self, instance_manager):
        """Test health check terminates instances exceeding token limit."""
        instance_data = {
            "id": "limit-inst",
            "state": "running",
            "instance_type": "claude",
            "last_activity": datetime.now(UTC).isoformat(),
            "total_tokens_used": 200000,
            "total_cost": 0.0,
            "resource_limits": {"max_total_tokens": 100000},
        }
        instance_manager.instances["limit-inst"] = instance_data
        # Also add to tmux_manager instances
        instance_manager.tmux_manager.instances["limit-inst"] = instance_data

        await instance_manager.health_check()

        instance_manager.tmux_manager.terminate_instance.assert_called()

    @pytest.mark.asyncio
    async def test_health_check_cost_limit(self, instance_manager):
        """Test health check terminates instances exceeding cost limit."""
        instance_data = {
            "id": "cost-inst",
            "state": "running",
            "instance_type": "claude",
            "last_activity": datetime.now(UTC).isoformat(),
            "total_tokens_used": 0,
            "total_cost": 150.0,
            "resource_limits": {"max_cost": 100.0},
        }
        instance_manager.instances["cost-inst"] = instance_data
        # Also add to tmux_manager instances
        instance_manager.tmux_manager.instances["cost-inst"] = instance_data

        await instance_manager.health_check()

        instance_manager.tmux_manager.terminate_instance.assert_called()

    @pytest.mark.asyncio
    async def test_health_check_skips_terminated(self, instance_manager):
        """Test health check skips terminated instances."""
        instance_manager.instances["terminated"] = {
            "id": "terminated",
            "state": "terminated",
            "last_activity": datetime.now(UTC).isoformat(),
        }

        # Reset mock call count
        instance_manager.tmux_manager.terminate_instance.reset_mock()

        await instance_manager.health_check()

        # Should not try to terminate already terminated instance
        instance_manager.tmux_manager.terminate_instance.assert_not_called()


class TestJobStatus:
    """Test job status tracking."""

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, instance_manager):
        """Test getting status for non-existent job."""
        result = await instance_manager.get_job_status.fn(instance_manager, job_id="nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_job_status_completed(self, instance_manager):
        """Test getting status for completed job."""
        instance_manager.jobs["job-123"] = {"job_id": "job-123", "status": "completed"}

        result = await instance_manager.get_job_status.fn(
            instance_manager, job_id="job-123", wait_for_completion=False
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_job_status_wait(self, instance_manager):
        """Test waiting for job completion."""
        instance_manager.jobs["job-456"] = {"job_id": "job-456", "status": "running"}

        # Simulate job completing after 0.5 seconds
        async def complete_job():
            await asyncio.sleep(0.5)
            instance_manager.jobs["job-456"]["status"] = "completed"

        asyncio.create_task(complete_job())

        result = await instance_manager.get_job_status.fn(
            instance_manager, job_id="job-456", wait_for_completion=True, max_wait=2
        )

        assert result["status"] == "completed"


class TestGetInstanceOutput:
    """Test instance output retrieval."""

    @pytest.mark.asyncio
    async def test_get_instance_output_basic(self, instance_manager):
        """Test basic output retrieval."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        instance_manager.tmux_manager.message_history[instance_id] = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        result = await instance_manager.get_instance_output.fn(
            instance_manager, instance_id=instance_id
        )

        assert result["instance_id"] == instance_id
        assert len(result["output"]) == 2

    @pytest.mark.asyncio
    async def test_get_instance_output_no_history(self, instance_manager):
        """Test output when no history exists."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        result = await instance_manager.get_instance_output.fn(
            instance_manager, instance_id=instance_id
        )

        assert result["output"] == []

    @pytest.mark.asyncio
    async def test_get_instance_output_with_limit(self, instance_manager):
        """Test output retrieval with limit."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        instance_manager.tmux_manager.message_history[instance_id] = [
            {"role": "user", "content": f"Message {i}"} for i in range(10)
        ]

        result = await instance_manager.get_instance_output.fn(
            instance_manager, instance_id=instance_id, limit=3
        )

        assert len(result["output"]) <= 3


class TestGetTmuxPaneContent:
    """Test tmux pane content capture."""

    @pytest.mark.asyncio
    async def test_get_tmux_pane_content_success(self, instance_manager):
        """Test capturing pane content."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        # Mock tmux session
        mock_pane = MagicMock()
        mock_pane.cmd.return_value.stdout = ["Line 1", "Line 2", "Line 3"]
        mock_window = MagicMock()
        mock_window.panes = [mock_pane]
        mock_session = MagicMock()
        mock_session.windows = [mock_window]

        instance_manager.tmux_manager.tmux_sessions[instance_id] = mock_session

        result = await instance_manager.get_tmux_pane_content.fn(
            instance_manager, instance_id=instance_id, lines=100
        )

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_tmux_pane_content_not_found(self, instance_manager):
        """Test capturing pane for non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            await instance_manager.get_tmux_pane_content.fn(
                instance_manager, instance_id="nonexistent"
            )

    @pytest.mark.asyncio
    async def test_get_tmux_pane_content_no_session(self, instance_manager):
        """Test capturing when no tmux session exists."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        # Clear tmux session
        instance_manager.tmux_manager.tmux_sessions = {}

        with pytest.raises(RuntimeError, match="No tmux session found"):
            await instance_manager.get_tmux_pane_content.fn(
                instance_manager, instance_id=instance_id
            )


class TestReplyToCaller:
    """Test reply_to_caller functionality."""

    @pytest.mark.asyncio
    async def test_reply_to_caller_success(self, instance_manager):
        """Test successful reply to caller."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        result = await instance_manager.reply_to_caller.fn(
            instance_manager,
            instance_id=instance_id,
            reply_message="Done",
            correlation_id="corr-123",
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_handle_reply_to_caller_no_shared_state(self, instance_manager):
        """Test reply handling without shared state."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        # Disable shared state
        instance_manager.shared_state_manager = None

        result = await instance_manager.handle_reply_to_caller(
            instance_id=instance_id, reply_message="Done"
        )

        # Should delegate to tmux manager
        assert "success" in result


class TestGetPendingReplies:
    """Test getting pending replies."""

    @pytest.mark.asyncio
    async def test_get_pending_replies_not_found(self, instance_manager):
        """Test getting replies for non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            await instance_manager._get_pending_replies_internal("nonexistent")

    @pytest.mark.asyncio
    async def test_get_pending_replies_empty(self, instance_manager):
        """Test getting replies when queue is empty."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        instance_manager.tmux_manager.shared_state = None
        instance_manager.tmux_manager.response_queues = {}

        replies = await instance_manager._get_pending_replies_internal(instance_id)

        assert replies == []

    @pytest.mark.asyncio
    async def test_get_pending_replies_drains_queue(self, instance_manager):
        """Test draining all messages from queue."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        instance_manager.tmux_manager.shared_state = None
        instance_manager.tmux_manager.response_queues = {}

        queue = asyncio.Queue()
        await queue.put({"message": "reply1"})
        await queue.put({"message": "reply2"})

        instance_manager.tmux_manager.response_queues[instance_id] = queue

        replies = await instance_manager._get_pending_replies_internal(instance_id, wait_timeout=0)

        assert len(replies) == 2


class TestBroadcastToChildren:
    """Test broadcasting messages to children."""

    @pytest.mark.asyncio
    async def test_broadcast_to_children_success(self, instance_manager):
        """Test broadcasting to all children."""
        parent_id = await instance_manager.spawn_instance(name="parent", role="general")

        # Add children
        await instance_manager.spawn_instance(
            name="child-1", role="general", parent_instance_id=parent_id
        )
        await instance_manager.spawn_instance(
            name="child-2", role="general", parent_instance_id=parent_id
        )

        # Mock the send_to_instance method to return properly
        async def mock_send(instance_id, message, wait_for_response=False):
            return {"status": "sent"}

        # Patch the internal method being called
        with patch.object(instance_manager, "send_to_instance", side_effect=mock_send):
            result = await instance_manager.broadcast_to_children.fn(
                instance_manager, parent_id=parent_id, message="Broadcast message"
            )

            assert result["children_count"] == 2

    @pytest.mark.asyncio
    async def test_broadcast_to_children_no_children(self, instance_manager):
        """Test broadcasting when parent has no children."""
        parent_id = await instance_manager.spawn_instance(name="parent", role="general")

        result = await instance_manager.broadcast_to_children.fn(
            instance_manager, parent_id=parent_id, message="Test"
        )

        assert result["children_count"] == 0
        assert result["results"] == []


class TestCoordinateInstances:
    """Test instance coordination."""

    @pytest.mark.asyncio
    async def test_coordinate_instances_sequential(self, instance_manager):
        """Test sequential coordination."""
        coord_id = await instance_manager.spawn_instance(name="coord", role="general")
        p1_id = await instance_manager.spawn_instance(name="p1", role="general")
        p2_id = await instance_manager.spawn_instance(name="p2", role="general")

        result = await instance_manager.coordinate_instances.fn(
            instance_manager,
            coordinator_id=coord_id,
            participant_ids=[p1_id, p2_id],
            task_description="Sequential task",
            coordination_type="sequential",
        )

        assert "task_id" in result

    @pytest.mark.asyncio
    async def test_coordinate_instances_invalid_participant(self, instance_manager):
        """Test coordination with non-existent participant."""
        coord_id = await instance_manager.spawn_instance(name="coord", role="general")

        with pytest.raises(ValueError, match="not found"):
            await instance_manager.coordinate_instances.fn(
                instance_manager,
                coordinator_id=coord_id,
                participant_ids=["nonexistent"],
                task_description="Test",
            )


class TestFileOperations:
    """Test file operation methods."""

    @pytest.mark.asyncio
    async def test_retrieve_instance_file_internal_success(self, instance_manager):
        """Test internal file retrieval."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        # Mock file operations
        with patch("pathlib.Path.exists", return_value=True):
            with patch("shutil.copy2"):
                result = await instance_manager._retrieve_instance_file_internal(
                    instance_id, "test.txt"
                )

                assert result is not None

    @pytest.mark.asyncio
    async def test_retrieve_instance_file_not_found(self, instance_manager):
        """Test retrieving non-existent file."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        with patch("pathlib.Path.exists", return_value=False):
            result = await instance_manager._retrieve_instance_file_internal(
                instance_id, "missing.txt"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_list_instance_files_internal_success(self, instance_manager):
        """Test listing instance files."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.rglob") as mock_rglob:
                mock_file = MagicMock()
                mock_file.is_file.return_value = True
                mock_file.relative_to.return_value = Path("test.txt")
                mock_rglob.return_value = [mock_file]

                result = await instance_manager._list_instance_files_internal(instance_id)

                assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_list_instance_files_no_workspace(self, instance_manager):
        """Test listing files when workspace doesn't exist."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        with patch("pathlib.Path.exists", return_value=False):
            result = await instance_manager._list_instance_files_internal(instance_id)

            assert result == []


class TestEnsureMainInstance:
    """Test main instance management."""

    @pytest.mark.asyncio
    async def test_ensure_main_instance_creates(self, instance_manager):
        """Test that ensure_main_instance creates instance."""
        main_id = await instance_manager.ensure_main_instance()

        assert main_id is not None
        assert instance_manager.main_instance_id == main_id

    @pytest.mark.asyncio
    async def test_ensure_main_instance_idempotent(self, instance_manager):
        """Test that ensure_main_instance is idempotent."""
        main_id_1 = await instance_manager.ensure_main_instance()
        main_id_2 = await instance_manager.ensure_main_instance()

        assert main_id_1 == main_id_2

    def test_get_main_instance_id_none(self, instance_manager):
        """Test getting main instance ID when not set."""
        result = instance_manager.get_main_instance_id.fn(instance_manager)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_main_instance_id_set(self, instance_manager):
        """Test getting main instance ID after creation."""
        await instance_manager.ensure_main_instance()

        result = instance_manager.get_main_instance_id.fn(instance_manager)

        assert result is not None


class TestShutdown:
    """Test shutdown functionality."""

    @pytest.mark.asyncio
    async def test_shutdown_terminates_all(self, instance_manager):
        """Test shutdown terminates all instances."""
        # Spawn some instances
        await instance_manager.spawn_instance(name="test-1", role="general")
        await instance_manager.spawn_instance(name="test-2", role="general")

        await instance_manager.shutdown()

        # Should have called terminate for each instance
        assert instance_manager.tmux_manager.terminate_instance.call_count >= 2


class TestTemplateOperations:
    """Test template-based team spawning."""

    @pytest.mark.asyncio
    async def test_parse_template_metadata(self, instance_manager):
        """Test parsing template metadata."""
        template_content = """
        Team Size: 5 instances
        Estimated Duration: 2-4 hours

        ### Technical Lead
        **Role**: `architect`
        """

        metadata = instance_manager._parse_template_metadata(template_content)

        assert metadata["team_size"] == 5
        assert metadata["supervisor_role"] == "architect"
        assert "hours" in metadata["duration"]

    def test_extract_section(self, instance_manager):
        """Test extracting markdown sections."""
        content = """
        ## Team Structure
        Content here

        ## Workflow Phases
        More content
        """

        section = instance_manager._extract_section(content, "## Team Structure")

        assert "Content here" in section
        # The extraction stops at the next ## header, so check it properly
        # Based on the implementation, it should break at the next ##
        lines = section.split("\n")
        # First line should have content
        assert any("Content here" in line for line in lines)

    @pytest.mark.asyncio
    async def test_spawn_team_template_not_found(self, instance_manager):
        """Test spawning team with non-existent template."""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(ValueError, match="Template not found"):
                await instance_manager.spawn_team_from_template.fn(
                    instance_manager,
                    template_name="nonexistent",
                    task_description="Test task",
                )


class TestLiveStatus:
    """Test live status functionality."""

    @pytest.mark.asyncio
    async def test_get_live_instance_status(self, instance_manager):
        """Test getting live status with execution time."""
        instance_id = await instance_manager.spawn_instance(name="test", role="general")

        status = await instance_manager.get_live_instance_status.fn(
            instance_manager, instance_id=instance_id
        )

        assert status["instance_id"] == instance_id
        assert "execution_time" in status
        assert "state" in status
        assert "last_activity" in status

    @pytest.mark.asyncio
    async def test_get_live_status_not_found(self, instance_manager):
        """Test live status for non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            await instance_manager.get_live_instance_status.fn(
                instance_manager, instance_id="nonexistent"
            )
