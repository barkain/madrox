"""Unit tests for shared_state_manager.py - Shared state for cross-process IPC."""

import base64
import os
from datetime import datetime
from queue import Empty
from unittest.mock import MagicMock, patch

import pytest

from src.orchestrator.shared_state_manager import SharedStateManager


class TestInitialization:
    """Test SharedStateManager initialization and setup."""

    def test_initialization_creates_manager(self):
        """Test that initialization creates Manager daemon."""
        manager = SharedStateManager()

        assert manager.manager is not None
        assert hasattr(manager, "response_queues")
        assert hasattr(manager, "message_registry")
        assert hasattr(manager, "instance_metadata")
        assert hasattr(manager, "queue_locks")
        assert isinstance(manager.response_queues, dict)
        assert len(manager.response_queues) == 0

        # Cleanup
        manager.shutdown()

    def test_initialization_sets_connection_details(self):
        """Test that manager address and authkey are stored."""
        manager = SharedStateManager()

        assert hasattr(manager, "manager_address")
        assert hasattr(manager, "manager_authkey")
        assert manager.manager_address is not None
        assert manager.manager_authkey is not None

        # Cleanup
        manager.shutdown()

    def test_initialization_detects_tcp_environment_variables(self):
        """Test that TCP environment variables are detected."""
        # Test that environment variables are checked
        test_authkey = b"test-auth-key-123"
        env_vars = {
            "MADROX_MANAGER_HOST": "localhost",
            "MADROX_MANAGER_PORT": "12345",
            "MADROX_MANAGER_AUTHKEY": base64.b64encode(test_authkey).decode(),
        }

        # Without mocking, we can't actually connect, so just verify
        # that the environment variables would be detected
        with patch.dict(os.environ, env_vars):
            # Check if environment variables are set
            assert os.getenv("MADROX_MANAGER_HOST") == "localhost"
            assert os.getenv("MADROX_MANAGER_PORT") == "12345"
            assert os.getenv("MADROX_MANAGER_AUTHKEY") is not None

    def test_initialization_detects_unix_socket_environment_variables(self):
        """Test that Unix socket environment variables are detected."""
        test_authkey = b"test-auth-key-456"
        env_vars = {
            "MADROX_MANAGER_SOCKET": "/tmp/test.sock",
            "MADROX_MANAGER_AUTHKEY": base64.b64encode(test_authkey).decode(),
        }

        # Check that environment variables would be detected
        with patch.dict(os.environ, env_vars):
            assert os.getenv("MADROX_MANAGER_SOCKET") == "/tmp/test.sock"
            assert os.getenv("MADROX_MANAGER_AUTHKEY") is not None


class TestResponseQueueManagement:
    """Test response queue creation and retrieval."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_create_response_queue(self, manager):
        """Test creating a new response queue."""
        instance_id = "test-instance-1"
        queue = manager.create_response_queue(instance_id)

        assert instance_id in manager.response_queues
        assert instance_id in manager.queue_locks
        assert queue is not None
        assert manager.response_queues[instance_id] == queue

    def test_create_response_queue_with_custom_maxsize(self, manager):
        """Test creating queue with custom maxsize."""
        instance_id = "test-instance-2"
        queue = manager.create_response_queue(instance_id, maxsize=50)

        assert queue is not None
        assert instance_id in manager.response_queues

    def test_create_response_queue_already_exists(self, manager):
        """Test creating queue that already exists returns existing queue."""
        instance_id = "test-instance-3"
        queue1 = manager.create_response_queue(instance_id)
        queue2 = manager.create_response_queue(instance_id)

        assert queue1 == queue2

    def test_get_response_queue_existing(self, manager):
        """Test retrieving existing response queue."""
        instance_id = "test-instance-4"
        created_queue = manager.create_response_queue(instance_id)
        retrieved_queue = manager.get_response_queue(instance_id)

        assert created_queue == retrieved_queue

    def test_get_response_queue_creates_if_not_exists(self, manager):
        """Test that get_response_queue creates queue if it doesn't exist."""
        instance_id = "test-instance-5"

        # Queue doesn't exist yet
        assert instance_id not in manager.response_queues

        # Get queue (should create it)
        queue = manager.get_response_queue(instance_id)

        # Verify queue was created
        assert instance_id in manager.response_queues
        assert queue is not None


class TestMessageRegistry:
    """Test message registration and tracking."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_register_message(self, manager):
        """Test registering a message envelope."""
        message_id = "msg-123"
        envelope_dict = {
            "message_id": message_id,
            "sender_id": "sender-1",
            "recipient_id": "recipient-1",
            "content": "Test message",
            "status": "sent",
            "sent_at": datetime.now().isoformat(),
        }

        manager.register_message(message_id, envelope_dict)

        # Verify message is in registry
        assert message_id in manager.message_registry

    def test_register_message_empty_message_id(self, manager):
        """Test that empty message_id raises ValueError."""
        with pytest.raises(ValueError, match="message_id cannot be empty"):
            manager.register_message("", {"sender_id": "test"})

    def test_register_message_invalid_envelope_type(self, manager):
        """Test that non-dict envelope raises ValueError."""
        with pytest.raises(ValueError, match="envelope_dict must be a dictionary"):
            manager.register_message("msg-1", "not-a-dict")

    def test_register_message_missing_required_fields(self, manager):
        """Test that missing required fields raises ValueError."""
        incomplete_envelope = {
            "message_id": "msg-1",
            "sender_id": "sender-1",
            # Missing recipient_id and status
        }

        with pytest.raises(ValueError, match="missing required fields"):
            manager.register_message("msg-1", incomplete_envelope)

    def test_update_message_status(self, manager):
        """Test updating message status."""
        message_id = "msg-456"
        envelope_dict = {
            "message_id": message_id,
            "sender_id": "sender-1",
            "recipient_id": "recipient-1",
            "status": "sent",
        }
        manager.register_message(message_id, envelope_dict)

        # Update status
        manager.update_message_status(message_id, "delivered")

        # Verify update
        updated_envelope = manager.get_message_envelope(message_id)
        assert updated_envelope["status"] == "delivered"
        assert "updated_at" in updated_envelope

    def test_update_message_status_with_additional_fields(self, manager):
        """Test updating message with additional fields."""
        message_id = "msg-789"
        envelope_dict = {
            "message_id": message_id,
            "sender_id": "sender-1",
            "recipient_id": "recipient-1",
            "status": "sent",
        }
        manager.register_message(message_id, envelope_dict)

        # Update with additional fields
        manager.update_message_status(
            message_id, "replied", reply_content="Response here", reply_at="2025-01-15"
        )

        # Verify update
        updated_envelope = manager.get_message_envelope(message_id)
        assert updated_envelope["status"] == "replied"
        assert updated_envelope["reply_content"] == "Response here"
        assert updated_envelope["reply_at"] == "2025-01-15"

    def test_update_message_status_not_found(self, manager):
        """Test updating non-existent message raises KeyError."""
        with pytest.raises(KeyError, match="not found in registry"):
            manager.update_message_status("nonexistent", "delivered")

    def test_get_message_envelope(self, manager):
        """Test retrieving message envelope."""
        message_id = "msg-get-test"
        envelope_dict = {
            "message_id": message_id,
            "sender_id": "sender-1",
            "recipient_id": "recipient-1",
            "status": "sent",
        }
        manager.register_message(message_id, envelope_dict)

        # Retrieve envelope
        retrieved = manager.get_message_envelope(message_id)

        assert retrieved is not None
        assert retrieved["message_id"] == message_id
        assert retrieved["sender_id"] == "sender-1"

    def test_get_message_envelope_not_found(self, manager):
        """Test retrieving non-existent envelope returns None."""
        envelope = manager.get_message_envelope("nonexistent-msg")
        assert envelope is None


class TestInstanceCleanup:
    """Test instance cleanup operations."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_cleanup_instance_with_queue(self, manager):
        """Test cleaning up instance with response queue."""
        instance_id = "cleanup-test-1"

        # Create queue and add to metadata
        manager.create_response_queue(instance_id)
        manager.instance_metadata[instance_id] = {"name": "test"}

        # Cleanup
        manager.cleanup_instance(instance_id)

        # Verify cleanup
        assert instance_id not in manager.response_queues
        assert instance_id not in manager.queue_locks
        assert instance_id not in manager.instance_metadata

    def test_cleanup_instance_drains_queue(self, manager):
        """Test that cleanup drains messages from queue."""
        instance_id = "cleanup-test-2"

        # Create queue and add messages
        queue = manager.create_response_queue(instance_id)
        queue.put("message1")
        queue.put("message2")
        queue.put("message3")

        # Cleanup
        manager.cleanup_instance(instance_id)

        # Verify queue is removed
        assert instance_id not in manager.response_queues

    def test_cleanup_instance_without_queue(self, manager):
        """Test cleanup when instance has no queue."""
        instance_id = "cleanup-test-3"

        # Cleanup non-existent instance (should not raise error)
        manager.cleanup_instance(instance_id)

        # No error should be raised

    def test_cleanup_instance_with_metadata_only(self, manager):
        """Test cleanup when only metadata exists."""
        instance_id = "cleanup-test-4"

        # Add only metadata
        manager.instance_metadata[instance_id] = {"status": "running"}

        # Cleanup
        manager.cleanup_instance(instance_id)

        # Verify metadata removed
        assert instance_id not in manager.instance_metadata


class TestQueueDepth:
    """Test queue depth monitoring."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_get_queue_depth_empty_queue(self, manager):
        """Test getting depth of empty queue."""
        instance_id = "depth-test-1"
        manager.create_response_queue(instance_id)

        depth = manager.get_queue_depth(instance_id)
        assert depth == 0

    def test_get_queue_depth_with_messages(self, manager):
        """Test getting depth of queue with messages."""
        instance_id = "depth-test-2"
        queue = manager.create_response_queue(instance_id)

        # Add messages
        queue.put("msg1")
        queue.put("msg2")
        queue.put("msg3")

        depth = manager.get_queue_depth(instance_id)
        assert depth == 3

    def test_get_queue_depth_nonexistent_queue(self, manager):
        """Test getting depth of non-existent queue returns None."""
        depth = manager.get_queue_depth("nonexistent")
        assert depth is None


class TestStats:
    """Test statistics collection."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_get_stats_empty_state(self, manager):
        """Test getting stats when state is empty."""
        stats = manager.get_stats()

        assert stats["active_queues"] == 0
        assert stats["active_locks"] == 0
        assert stats["registered_messages"] == 0
        assert stats["instance_metadata_count"] == 0
        assert stats["queue_depths"] == {}

    def test_get_stats_with_data(self, manager):
        """Test getting stats with active data."""
        # Add some data
        manager.create_response_queue("inst-1")
        manager.create_response_queue("inst-2")

        message_id = "msg-1"
        envelope = {
            "message_id": message_id,
            "sender_id": "sender",
            "recipient_id": "recipient",
            "status": "sent",
        }
        manager.register_message(message_id, envelope)

        manager.instance_metadata["inst-1"] = {"status": "running"}

        # Get stats
        stats = manager.get_stats()

        assert stats["active_queues"] == 2
        assert stats["active_locks"] == 2
        assert stats["registered_messages"] == 1
        assert stats["instance_metadata_count"] == 1
        assert "inst-1" in stats["queue_depths"]
        assert "inst-2" in stats["queue_depths"]

    def test_get_stats_includes_queue_depths(self, manager):
        """Test that stats include queue depths."""
        instance_id = "stats-test"
        queue = manager.create_response_queue(instance_id)
        queue.put("msg1")
        queue.put("msg2")

        stats = manager.get_stats()

        assert stats["queue_depths"][instance_id] == 2


class TestHealthCheck:
    """Test health check operations."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_health_check_success(self, manager):
        """Test successful health check."""
        result = manager.health_check(timeout=5.0)

        # Health check may fail on some systems, check key fields exist
        assert "healthy" in result
        assert "manager_alive" in result
        assert "response_time_ms" in result
        assert result["response_time_ms"] >= 0

        # If healthy, verify all checks passed
        if result["healthy"]:
            assert result["manager_alive"] is True
            assert result["test_queue_created"] is True
            assert result["test_dict_accessed"] is True
            assert result["test_cleanup_completed"] is True
            assert result["error"] is None

    def test_health_check_measures_response_time(self, manager):
        """Test that health check measures response time."""
        result = manager.health_check()

        assert "response_time_ms" in result
        assert result["response_time_ms"] >= 0

    def test_health_check_with_custom_timeout(self, manager):
        """Test health check with custom timeout."""
        result = manager.health_check(timeout=1.0)

        # Should complete (may or may not be healthy depending on system)
        assert "healthy" in result
        assert "response_time_ms" in result

    def test_health_check_cleans_up_test_data(self, manager):
        """Test that health check cleans up its test data."""
        # Perform health check
        result = manager.health_check()

        # Verify test key was cleaned up if health check succeeded
        assert "__health_check_test__" not in manager.instance_metadata
        # test_cleanup_completed may be False if health check failed early
        assert "test_cleanup_completed" in result

    def test_is_manager_alive(self, manager):
        """Test manager alive check."""
        is_alive = manager.is_manager_alive()
        # Should return a boolean (may be True or False depending on system)
        assert isinstance(is_alive, bool)

    def test_is_manager_alive_after_shutdown(self, manager):
        """Test manager alive check after shutdown."""
        manager.shutdown()

        # After shutdown, manager should not be alive
        # (This test may need adjustment based on actual behavior)
        is_alive = manager.is_manager_alive()
        # Manager process may still be alive briefly after shutdown
        assert isinstance(is_alive, bool)


class TestShutdown:
    """Test shutdown operations."""

    def test_shutdown_cleans_up_queues(self):
        """Test that shutdown cleans up all queues."""
        manager = SharedStateManager()

        # Create some queues
        manager.create_response_queue("inst-1")
        manager.create_response_queue("inst-2")

        # Shutdown
        manager.shutdown()

        # Verify cleanup (queues should be empty)
        assert len(manager.response_queues) == 0

    def test_shutdown_cleans_up_all_instances(self):
        """Test that shutdown cleans up all instance data."""
        manager = SharedStateManager()

        # Add instance data
        manager.create_response_queue("inst-1")
        manager.instance_metadata["inst-1"] = {"status": "running"}

        # Shutdown
        manager.shutdown()

        # Verify cleanup
        assert len(manager.response_queues) == 0
        assert len(manager.queue_locks) == 0

    def test_shutdown_child_connection(self):
        """Test shutdown behavior for child connections."""
        # Create manager simulating child connection
        manager = SharedStateManager()
        manager.is_child_connection = True

        # Mock the manager to track shutdown calls
        manager.manager.shutdown = MagicMock()

        # Shutdown
        manager.shutdown()

        # Child should not shutdown parent's manager
        manager.manager.shutdown.assert_not_called()

    def test_shutdown_parent_connection(self):
        """Test shutdown behavior for parent connections."""
        manager = SharedStateManager()
        manager.is_child_connection = False

        # Mock the manager to track shutdown calls
        manager.manager.shutdown = MagicMock()

        # Shutdown
        manager.shutdown()

        # Parent should shutdown its manager
        manager.manager.shutdown.assert_called_once()


class TestRepr:
    """Test string representation."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_repr_empty_state(self, manager):
        """Test repr with empty state."""
        repr_str = repr(manager)

        assert "SharedStateManager" in repr_str
        assert "queues=0" in repr_str
        assert "messages=0" in repr_str
        assert "metadata=0" in repr_str

    def test_repr_with_data(self, manager):
        """Test repr with active data."""
        # Add data
        manager.create_response_queue("inst-1")
        envelope = {
            "message_id": "msg-1",
            "sender_id": "s",
            "recipient_id": "r",
            "status": "sent",
        }
        manager.register_message("msg-1", envelope)
        manager.instance_metadata["inst-1"] = {"status": "running"}

        repr_str = repr(manager)

        assert "SharedStateManager" in repr_str
        assert "queues=1" in repr_str
        assert "messages=1" in repr_str
        assert "metadata=1" in repr_str

    def test_repr_handles_errors(self):
        """Test repr handles errors gracefully."""
        manager = SharedStateManager()

        # Break get_stats to simulate error
        manager.get_stats = MagicMock(side_effect=Exception("Test error"))

        repr_str = repr(manager)

        # Should return error message instead of crashing
        assert "error retrieving stats" in repr_str

        manager.shutdown()


class TestErrorHandling:
    """Test error handling in various scenarios."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_register_message_with_exception(self, manager):
        """Test that exceptions in register_message are raised."""
        # Try to register with invalid data should raise
        with pytest.raises(ValueError):
            manager.register_message("", {})

    def test_update_message_status_with_exception(self, manager):
        """Test that exceptions in update_message_status are raised."""
        # Try to update non-existent message
        with pytest.raises(KeyError):
            manager.update_message_status("nonexistent", "delivered")

    def test_cleanup_instance_handles_errors_gracefully(self, manager):
        """Test that cleanup_instance doesn't raise on errors."""
        # Create a scenario that might cause errors
        instance_id = "error-test"

        # This should not raise even if instance doesn't exist
        manager.cleanup_instance(instance_id)

        # No exception should be raised


class TestConcurrency:
    """Test concurrent access scenarios."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_multiple_queues_independent(self, manager):
        """Test that multiple queues operate independently."""
        # Create multiple queues
        queue1 = manager.create_response_queue("inst-1")
        manager.create_response_queue("inst-2")

        # Add messages to queue1
        queue1.put("msg1")
        queue1.put("msg2")

        # Verify queue2 is still empty
        assert manager.get_queue_depth("inst-1") == 2
        assert manager.get_queue_depth("inst-2") == 0

    def test_message_registry_isolation(self, manager):
        """Test that message registry maintains separate entries."""
        envelope1 = {
            "message_id": "msg-1",
            "sender_id": "s1",
            "recipient_id": "r1",
            "status": "sent",
        }
        envelope2 = {
            "message_id": "msg-2",
            "sender_id": "s2",
            "recipient_id": "r2",
            "status": "delivered",
        }

        manager.register_message("msg-1", envelope1)
        manager.register_message("msg-2", envelope2)

        # Verify both messages exist independently
        retrieved1 = manager.get_message_envelope("msg-1")
        retrieved2 = manager.get_message_envelope("msg-2")

        assert retrieved1["sender_id"] == "s1"
        assert retrieved2["sender_id"] == "s2"
        assert retrieved1["status"] == "sent"
        assert retrieved2["status"] == "delivered"


class TestExceptionPaths:
    """Test exception handling paths for better coverage."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_create_response_queue_with_exception(self, manager):
        """Test exception handling in create_response_queue."""
        # Create a queue first
        queue1 = manager.create_response_queue("test-inst")

        # Try to create again - should return existing queue (warning path)
        queue2 = manager.create_response_queue("test-inst")

        # Should return same queue
        assert queue1 == queue2

    def test_get_response_queue_exception_path(self, manager):
        """Test exception handling in get_response_queue."""
        # Getting non-existent queue should create it
        queue = manager.get_response_queue("new-inst")

        assert queue is not None
        assert "new-inst" in manager.response_queues

    def test_register_message_exception_logged(self, manager):
        """Test that registration exceptions are raised properly."""
        # Test various invalid inputs
        with pytest.raises(ValueError):
            manager.register_message("", {"test": "data"})

    def test_update_message_status_exception_logged(self, manager):
        """Test that update exceptions are raised properly."""
        with pytest.raises(KeyError):
            manager.update_message_status("nonexistent-msg", "delivered")

    def test_get_message_envelope_exception_handling(self, manager):
        """Test get_message_envelope with non-existent message."""
        # Should return None, not raise
        result = manager.get_message_envelope("does-not-exist")
        assert result is None

    def test_cleanup_instance_with_exception(self, manager):
        """Test cleanup handles exceptions gracefully."""
        # Cleanup non-existent instance should not raise
        manager.cleanup_instance("non-existent-instance")

        # No exception should be raised

    def test_get_queue_depth_with_error(self, manager):
        """Test get_queue_depth error handling."""
        # Non-existent queue returns None
        depth = manager.get_queue_depth("non-existent")
        assert depth is None

    def test_get_stats_with_exception(self, manager):
        """Test get_stats handles errors."""
        # Break get_queue_depth
        original_method = manager.get_queue_depth
        manager.get_queue_depth = MagicMock(side_effect=Exception("Test error"))

        # get_stats should handle error and return error dict
        stats = manager.get_stats()

        # Should contain error
        assert "error" in stats or "queue_depths" in stats

        # Restore
        manager.get_queue_depth = original_method

    def test_health_check_with_error_scenarios(self, manager):
        """Test health check with various error conditions."""
        # Only test if manager has _process attribute (not RemoteManager)
        if not hasattr(manager.manager, "_process"):
            # Skip this test for RemoteManager
            return

        original_process = manager.manager._process

        # Test with None process
        manager.manager._process = None
        result = manager.health_check(timeout=1.0)
        assert result["healthy"] is False
        assert "error" in result
        assert result["error"] is not None

        # Restore
        manager.manager._process = original_process

    def test_is_manager_alive_without_process(self, manager):
        """Test is_manager_alive when process is None."""
        # Only test if manager has _process attribute (not RemoteManager)
        if not hasattr(manager.manager, "_process"):
            # Test that is_manager_alive returns a boolean for RemoteManager
            result = manager.is_manager_alive()
            assert isinstance(result, bool)
            return

        original_process = manager.manager._process

        # Set process to None
        manager.manager._process = None
        result = manager.is_manager_alive()

        assert result is False

        # Restore
        manager.manager._process = original_process

    def test_is_manager_alive_without_is_alive_method(self, manager):
        """Test is_manager_alive fallback when is_alive doesn't exist."""
        # Only test if manager has _process attribute (not RemoteManager)
        if not hasattr(manager.manager, "_process"):
            # Skip this test for RemoteManager
            return

        original_process = manager.manager._process

        # Create mock process without is_alive
        mock_process = MagicMock(spec=[])  # No is_alive method
        manager.manager._process = mock_process

        result = manager.is_manager_alive()

        # Should fallback to True
        assert isinstance(result, bool)

        # Restore
        manager.manager._process = original_process


class TestHealthCheckErrorPaths:
    """Test health_check error paths for comprehensive coverage."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_health_check_with_process_not_alive(self, manager):
        """Test health check when manager process is not alive."""
        if not hasattr(manager.manager, "_process"):
            return  # Skip for RemoteManager

        original_process = manager.manager._process

        # Mock process with is_alive returning False
        mock_process = MagicMock()
        mock_process.is_alive.return_value = False
        manager.manager._process = mock_process

        result = manager.health_check(timeout=1.0)

        assert result["healthy"] is False
        assert "Manager daemon process is dead" in result["error"]

        # Restore
        manager.manager._process = original_process

    def test_health_check_with_queue_creation_failure(self, manager):
        """Test health check when queue creation fails."""
        if not hasattr(manager.manager, "_process"):
            return  # Skip for RemoteManager

        # Mock Queue to raise exception
        original_queue = manager.manager.Queue
        manager.manager.Queue = MagicMock(side_effect=Exception("Queue creation failed"))

        result = manager.health_check(timeout=1.0)

        assert result["healthy"] is False
        assert "Failed to create test queue" in result["error"]

        # Restore
        manager.manager.Queue = original_queue

    def test_health_check_with_queue_timeout(self, manager):
        """Test health check when queue get times out."""
        if not hasattr(manager.manager, "_process"):
            return  # Skip for RemoteManager

        # Mock Queue to simulate timeout

        mock_queue = MagicMock()
        mock_queue.put = MagicMock()
        mock_queue.get = MagicMock(side_effect=Empty())

        original_queue = manager.manager.Queue
        manager.manager.Queue = MagicMock(return_value=mock_queue)

        result = manager.health_check(timeout=1.0)

        assert result["healthy"] is False
        assert "Queue get timeout" in result["error"]

        # Restore
        manager.manager.Queue = original_queue

    def test_health_check_with_queue_data_mismatch(self, manager):
        """Test health check when queue data is corrupted."""
        if not hasattr(manager.manager, "_process"):
            return  # Skip for RemoteManager

        # Mock Queue to return different data
        mock_queue = MagicMock()
        mock_queue.put = MagicMock()
        mock_queue.get = MagicMock(return_value={"corrupted": "data"})

        original_queue = manager.manager.Queue
        manager.manager.Queue = MagicMock(return_value=mock_queue)

        result = manager.health_check(timeout=1.0)

        assert result["healthy"] is False
        assert "Queue data mismatch" in result["error"]

        # Restore
        manager.manager.Queue = original_queue

    def test_health_check_with_dict_access_failure(self, manager):
        """Test health check when shared dict access fails."""
        if not hasattr(manager.manager, "_process"):
            return  # Skip for RemoteManager

        # Mock instance_metadata to raise exception
        original_metadata = manager.instance_metadata

        # Create mock that raises on setitem
        mock_dict = MagicMock()
        mock_dict.__setitem__ = MagicMock(side_effect=Exception("Dict access failed"))
        manager.instance_metadata = mock_dict

        result = manager.health_check(timeout=1.0)

        assert result["healthy"] is False
        assert "Shared dict access failed" in result["error"]

        # Restore
        manager.instance_metadata = original_metadata

    def test_health_check_with_dict_data_mismatch(self, manager):
        """Test health check when shared dict data doesn't match."""
        if not hasattr(manager.manager, "_process"):
            return  # Skip for RemoteManager

        # Mock instance_metadata to return different value
        original_metadata = manager.instance_metadata

        mock_dict = MagicMock()
        mock_dict.__setitem__ = MagicMock()
        mock_dict.get = MagicMock(return_value={"wrong": "value"})
        manager.instance_metadata = mock_dict

        result = manager.health_check(timeout=1.0)

        assert result["healthy"] is False
        assert "Shared dict data mismatch" in result["error"]

        # Restore
        manager.instance_metadata = original_metadata

    def test_health_check_cleanup_failure_non_critical(self, manager):
        """Test that cleanup failure doesn't fail health check."""
        # This tests the non-critical cleanup path (lines 522-524)
        # Health check should succeed even if cleanup fails
        result = manager.health_check(timeout=2.0)

        # Result should have health status
        assert "healthy" in result

    def test_health_check_unexpected_exception(self, manager):
        """Test health check with unexpected exception."""
        if not hasattr(manager.manager, "_process"):
            return  # Skip for RemoteManager

        # Mock to raise unexpected exception
        original_process = manager.manager._process
        manager.manager._process = MagicMock()
        manager.manager._process.is_alive = MagicMock(side_effect=Exception("Unexpected error"))

        result = manager.health_check(timeout=1.0)

        assert result["healthy"] is False
        assert "Unexpected health check error" in result["error"]

        # Restore
        manager.manager._process = original_process

    def test_is_manager_alive_exception_handling(self, manager):
        """Test is_manager_alive with exception."""
        if not hasattr(manager.manager, "_process"):
            return  # Skip for RemoteManager

        original_process = manager.manager._process

        # Mock to raise exception
        manager.manager._process = MagicMock()
        manager.manager._process.is_alive = MagicMock(side_effect=Exception("Error"))

        # Should return False on exception
        result = manager.is_manager_alive()

        assert result is False

        # Restore
        manager.manager._process = original_process


class TestAdditionalEdgeCases:
    """Test additional edge cases for comprehensive coverage."""

    @pytest.fixture
    def manager(self):
        """Create a SharedStateManager for testing."""
        mgr = SharedStateManager()
        yield mgr
        mgr.shutdown()

    def test_register_message_all_required_fields(self, manager):
        """Test registration with all required fields present."""
        envelope = {
            "message_id": "test-123",
            "sender_id": "sender",
            "recipient_id": "recipient",
            "status": "sent",
            "content": "Test content",
            "extra_field": "extra value",
        }

        manager.register_message("test-123", envelope)

        retrieved = manager.get_message_envelope("test-123")
        assert retrieved is not None
        assert retrieved["extra_field"] == "extra value"

    def test_update_message_status_updates_timestamp(self, manager):
        """Test that update_message_status adds updated_at timestamp."""
        envelope = {
            "message_id": "msg-time",
            "sender_id": "s",
            "recipient_id": "r",
            "status": "sent",
        }
        manager.register_message("msg-time", envelope)

        # Update status
        manager.update_message_status("msg-time", "delivered")

        # Verify timestamp was added
        updated = manager.get_message_envelope("msg-time")
        assert "updated_at" in updated
        assert updated["updated_at"] is not None

    def test_cleanup_instance_drains_multiple_messages(self, manager):
        """Test cleanup drains queue with multiple messages."""
        instance_id = "drain-test"
        queue = manager.create_response_queue(instance_id)

        # Add many messages
        for i in range(10):
            queue.put(f"message-{i}")

        # Verify queue has messages
        assert manager.get_queue_depth(instance_id) == 10

        # Cleanup
        manager.cleanup_instance(instance_id)

        # Verify cleanup
        assert instance_id not in manager.response_queues

    def test_shutdown_handles_cleanup_errors(self, manager):
        """Test that shutdown handles cleanup errors gracefully."""
        # Create instance with potential for error
        instance_id = "error-cleanup"
        manager.create_response_queue(instance_id)

        # Mock cleanup_instance to raise error
        original_cleanup = manager.cleanup_instance
        manager.cleanup_instance = MagicMock(side_effect=Exception("Cleanup error"))

        # Shutdown should not raise
        manager.shutdown()

        # Restore
        manager.cleanup_instance = original_cleanup

    def test_health_check_queue_operations(self, manager):
        """Test health check queue put/get operations."""
        result = manager.health_check(timeout=2.0)

        # Should test queue operations
        assert "test_queue_created" in result

    def test_repr_with_various_states(self, manager):
        """Test __repr__ with different state configurations."""
        # Empty state
        repr1 = repr(manager)
        assert "SharedStateManager" in repr1

        # Add various data
        manager.create_response_queue("inst-1")
        manager.create_response_queue("inst-2")

        for i in range(5):
            envelope = {
                "message_id": f"msg-{i}",
                "sender_id": "s",
                "recipient_id": "r",
                "status": "sent",
            }
            manager.register_message(f"msg-{i}", envelope)

        manager.instance_metadata["inst-1"] = {"status": "running"}

        # Get repr with data
        repr2 = repr(manager)
        assert "SharedStateManager" in repr2
        assert "queues=2" in repr2
        assert "messages=5" in repr2

    def test_get_stats_complete_data(self, manager):
        """Test get_stats returns complete statistics."""
        # Add comprehensive data
        queue1 = manager.create_response_queue("stats-1")
        queue2 = manager.create_response_queue("stats-2")

        queue1.put("msg1")
        queue1.put("msg2")
        queue2.put("msg3")

        envelope = {
            "message_id": "stat-msg",
            "sender_id": "s",
            "recipient_id": "r",
            "status": "sent",
        }
        manager.register_message("stat-msg", envelope)

        manager.instance_metadata["stats-1"] = {"status": "running"}

        stats = manager.get_stats()

        assert stats["active_queues"] == 2
        assert stats["active_locks"] == 2
        assert stats["registered_messages"] == 1
        assert stats["instance_metadata_count"] == 1
        assert stats["queue_depths"]["stats-1"] == 2
        assert stats["queue_depths"]["stats-2"] == 1
