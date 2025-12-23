"""Test InstanceManager main instance inbox and monitoring functionality."""

import asyncio
from datetime import datetime
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
        with patch("src.orchestrator.instance_manager.LoggingManager"):
            with patch("src.orchestrator.shared_state_manager.SharedStateManager"):
                with patch(
                    "src.orchestrator.instance_manager.TmuxInstanceManager"
                ) as mock_tmux_mgr_class:
                    # Setup mock tmux manager
                    mock_tmux_mgr = MagicMock()
                    mock_tmux_mgr.message_history = {}
                    mock_tmux_mgr.instances = {}
                    mock_tmux_mgr.response_queues = {}
                    mock_tmux_mgr.tmux_sessions = {}

                    # Mock async methods
                    async def mock_spawn_instance(*args, **kwargs):
                        instance_id = f"inst-{len(mock_tmux_mgr.instances) + 1}"
                        instance_data = {
                            "id": instance_id,
                            "instance_id": instance_id,
                            "name": kwargs.get("name", "test"),
                            "state": "running",
                            "instance_type": "claude",
                            "created_at": datetime.now(UTC).isoformat(),
                            "last_activity": datetime.now(UTC).isoformat(),
                            "total_tokens_used": 0,
                            "total_cost": 0.0,
                        }
                        mock_tmux_mgr.instances[instance_id] = instance_data
                        return instance_id

                    mock_tmux_mgr.spawn_instance = AsyncMock(side_effect=mock_spawn_instance)
                    mock_tmux_mgr.send_message = AsyncMock(return_value={"status": "sent"})
                    mock_tmux_mgr.terminate_instance = AsyncMock(return_value=True)

                    mock_tmux_mgr_class.return_value = mock_tmux_mgr

                    manager = InstanceManager(mock_config)
                    yield manager

                    if hasattr(manager, "shutdown"):
                        try:
                            await manager.shutdown()
                        except Exception:  # noqa: E722
                            pass


class TestMainInstanceInbox:
    """Test main instance inbox functionality."""

    def test_main_message_inbox_initialized(self, instance_manager):
        """Test that main message inbox is initialized."""
        assert instance_manager.main_message_inbox == []
        assert instance_manager._last_main_message_index == -1

    def test_get_and_clear_main_inbox_empty(self, instance_manager):
        """Test getting messages from empty inbox."""
        messages = instance_manager.get_and_clear_main_inbox()

        assert messages == []

    def test_get_and_clear_main_inbox_with_messages(self, instance_manager):
        """Test getting and clearing messages from inbox."""
        # Add messages to inbox
        instance_manager.main_message_inbox = [
            {"content": "Message 1", "message_index": 0},
            {"content": "Message 2", "message_index": 1},
        ]

        messages = instance_manager.get_and_clear_main_inbox()

        # Should return all messages
        assert len(messages) == 2
        assert messages[0]["content"] == "Message 1"
        assert messages[1]["content"] == "Message 2"

        # Inbox should be cleared
        assert instance_manager.main_message_inbox == []

    def test_get_and_clear_main_inbox_idempotent(self, instance_manager):
        """Test that clearing inbox twice returns empty on second call."""
        instance_manager.main_message_inbox = [{"content": "Message"}]

        # First call
        messages1 = instance_manager.get_and_clear_main_inbox()
        assert len(messages1) == 1

        # Second call should return empty
        messages2 = instance_manager.get_and_clear_main_inbox()
        assert messages2 == []


class TestMainInstanceId:
    """Test main instance ID tracking."""

    def test_get_main_instance_id_none_initially(self, instance_manager):
        """Test that main instance ID is None initially."""
        result = instance_manager.get_main_instance_id.fn(instance_manager)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_main_instance_id_after_spawn(self, instance_manager):
        """Test getting main instance ID after spawning main instance."""
        # Spawn main instance
        main_id = await instance_manager.ensure_main_instance()

        result = instance_manager.get_main_instance_id.fn(instance_manager)

        assert result == main_id

    @pytest.mark.asyncio
    async def test_main_instance_id_persistence(self, instance_manager):
        """Test that main instance ID persists across calls."""
        main_id1 = await instance_manager.ensure_main_instance()
        main_id2 = await instance_manager.ensure_main_instance()

        assert main_id1 == main_id2


class TestMainInstanceMonitoring:
    """Test main instance monitoring functionality."""

    @pytest.mark.asyncio
    async def test_monitor_main_instance_no_main_instance(self, instance_manager):
        """Test monitor exits when no main instance set."""
        # Should return immediately when main_instance_id is None
        await instance_manager._monitor_main_messages()

        # Should not crash

    @pytest.mark.asyncio
    async def test_monitor_main_instance_terminated(self, instance_manager):
        """Test monitor stops when main instance is terminated."""
        # Spawn main instance
        main_id = await instance_manager.ensure_main_instance()

        # Mock _get_output_messages to avoid actual calls
        instance_manager._get_output_messages = AsyncMock(return_value=[])

        # Remove instance to simulate termination
        del instance_manager.instances[main_id]

        # Start monitor (should exit immediately)
        await instance_manager._monitor_main_messages()

        # Should have exited without error

    @pytest.mark.asyncio
    async def test_monitor_main_instance_processes_messages(self, instance_manager):
        """Test monitor processes new messages."""
        # Spawn main instance
        await instance_manager.ensure_main_instance()

        # Mock _get_output_messages to return test messages
        test_messages = [
            {"type": "user", "content": "Test message 1", "message_index": 0},
            {"type": "user", "content": "Test message 2", "message_index": 1},
            {"type": "assistant", "content": "Response", "message_index": 2},
        ]

        call_count = {"count": 0}

        async def mock_get_messages(instance_id, limit=100):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return test_messages
            # After first call, return empty to let monitor continue
            return []

        instance_manager._get_output_messages = AsyncMock(side_effect=mock_get_messages)

        # Start monitor in background and let it process one iteration
        monitor_task = asyncio.create_task(instance_manager._monitor_main_messages())

        # Wait a bit for processing
        await asyncio.sleep(0.5)

        # Cancel the monitor
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Should have added user messages to inbox (not assistant messages)
        assert len(instance_manager.main_message_inbox) >= 2

    @pytest.mark.asyncio
    async def test_monitor_main_instance_updates_last_index(self, instance_manager):
        """Test monitor updates last message index."""
        await instance_manager.ensure_main_instance()

        test_messages = [
            {"type": "user", "content": "Message", "message_index": 5},
        ]

        call_count = {"count": 0}

        async def mock_get_messages(instance_id, limit=100):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return test_messages
            return []

        instance_manager._get_output_messages = AsyncMock(side_effect=mock_get_messages)

        # Start monitor
        monitor_task = asyncio.create_task(instance_manager._monitor_main_messages())

        await asyncio.sleep(0.5)

        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Last index should be updated
        assert instance_manager._last_main_message_index >= 5

    @pytest.mark.asyncio
    async def test_monitor_main_instance_handles_errors(self, instance_manager):
        """Test monitor handles errors gracefully."""
        await instance_manager.ensure_main_instance()

        # Mock _get_output_messages to raise error
        call_count = {"count": 0}

        async def mock_get_messages_error(instance_id, limit=100):
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise Exception("Test error")
            return []

        instance_manager._get_output_messages = AsyncMock(side_effect=mock_get_messages_error)

        # Start monitor
        monitor_task = asyncio.create_task(instance_manager._monitor_main_messages())

        await asyncio.sleep(0.5)

        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Should have handled error and continued (not crashed)
        assert True  # If we get here, error was handled

    @pytest.mark.asyncio
    async def test_monitor_main_instance_skips_duplicate_messages(self, instance_manager):
        """Test monitor skips already-processed messages."""
        await instance_manager.ensure_main_instance()

        # Set last message index
        instance_manager._last_main_message_index = 5

        # Messages with lower indices should be skipped
        test_messages = [
            {"type": "user", "content": "Old message", "message_index": 3},
            {"type": "user", "content": "Already seen", "message_index": 5},
            {"type": "user", "content": "New message", "message_index": 6},
        ]

        call_count = {"count": 0}

        async def mock_get_messages(instance_id, limit=100):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return test_messages
            return []

        instance_manager._get_output_messages = AsyncMock(side_effect=mock_get_messages)

        # Start monitor
        monitor_task = asyncio.create_task(instance_manager._monitor_main_messages())

        await asyncio.sleep(0.5)

        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Should only have added message with index 6
        assert len(instance_manager.main_message_inbox) == 1
        assert instance_manager.main_message_inbox[0]["message_index"] == 6

    @pytest.mark.asyncio
    async def test_monitor_main_instance_skips_non_user_messages(self, instance_manager):
        """Test monitor only processes user-type messages."""
        await instance_manager.ensure_main_instance()

        test_messages = [
            {"type": "assistant", "content": "Response", "message_index": 1},
            {"type": "system", "content": "System message", "message_index": 2},
            {"type": "user", "content": "User message", "message_index": 3},
        ]

        call_count = {"count": 0}

        async def mock_get_messages(instance_id, limit=100):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return test_messages
            return []

        instance_manager._get_output_messages = AsyncMock(side_effect=mock_get_messages)

        # Start monitor
        monitor_task = asyncio.create_task(instance_manager._monitor_main_messages())

        await asyncio.sleep(0.5)

        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Should only have user message
        assert len(instance_manager.main_message_inbox) == 1
        assert instance_manager.main_message_inbox[0]["type"] == "user"
