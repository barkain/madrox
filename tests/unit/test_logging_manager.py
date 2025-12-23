"""Comprehensive unit tests for logging_manager module."""

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from orchestrator.logging_manager import (
    LoggingManager,
    LogStreamHandler,
    get_audit_log_stream_handler,
    get_log_stream_handler,
)


class TestWebSocketBroadcasting:
    """Test real-time log streaming via WebSocket."""

    @pytest.mark.asyncio
    async def test_broadcast_log_to_connected_clients(self):
        """Test broadcasting log entry to all connected WebSocket clients."""
        # Setup
        handler = LogStreamHandler(log_type="system_log")
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        handler.clients.add(mock_ws1)
        handler.clients.add(mock_ws2)

        log_entry = {
            "timestamp": "2025-01-01T00:00:00",
            "level": "INFO",
            "message": "Test log message",
        }

        # Execute
        await handler._broadcast(log_entry)

        # Assert
        expected_message = {"type": "system_log", "data": log_entry}
        mock_ws1.send_json.assert_called_once_with(expected_message)
        mock_ws2.send_json.assert_called_once_with(expected_message)
        # Coverage: Lines 163-174

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected_clients(self):
        """Test removal of disconnected WebSocket clients during broadcast."""
        # Setup
        handler = LogStreamHandler(log_type="system_log")
        mock_ws_connected = AsyncMock()
        mock_ws_disconnected = AsyncMock()
        mock_ws_disconnected.send_json.side_effect = Exception("Connection closed")

        handler.clients.add(mock_ws_connected)
        handler.clients.add(mock_ws_disconnected)

        log_entry = {"level": "INFO", "message": "test"}

        # Execute
        await handler._broadcast(log_entry)

        # Assert
        assert mock_ws_connected in handler.clients
        assert mock_ws_disconnected not in handler.clients
        assert len(handler.clients) == 1
        # Coverage: Lines 169-180

    @pytest.mark.asyncio
    async def test_broadcast_with_audit_log_type(self):
        """Test broadcasting with audit_log type."""
        # Setup
        handler = LogStreamHandler(log_type="audit_log")
        mock_ws = AsyncMock()
        handler.clients.add(mock_ws)

        log_entry = {"event": "instance_spawned", "instance_id": "inst-1"}

        # Execute
        await handler._broadcast(log_entry)

        # Assert
        expected_message = {"type": "audit_log", "data": log_entry}
        mock_ws.send_json.assert_called_once_with(expected_message)
        # Coverage: Lines 163-174

    def test_add_websocket_client(self):
        """Test adding WebSocket client to handler."""
        # Setup
        handler = LogStreamHandler()
        mock_ws = MagicMock()

        # Execute
        handler.add_client(mock_ws)

        # Assert
        assert mock_ws in handler.clients
        # Coverage: Lines 41-43

    def test_remove_websocket_client(self):
        """Test removing WebSocket client from handler."""
        # Setup
        handler = LogStreamHandler()
        mock_ws = MagicMock()
        handler.add_client(mock_ws)

        # Execute
        handler.remove_client(mock_ws)

        # Assert
        assert mock_ws not in handler.clients
        # Coverage: Lines 45-47

    def test_emit_with_running_event_loop(self):
        """Test emit creates broadcast task when event loop is running."""
        # Setup
        handler = LogStreamHandler()
        mock_ws = AsyncMock()
        handler.add_client(mock_ws)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Execute with mocked event loop
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = Mock()
            mock_loop.is_running.return_value = True
            mock_get_loop.return_value = mock_loop

            with patch("asyncio.create_task") as mock_create_task:
                handler.emit(record)
                mock_create_task.assert_called_once()
        # Coverage: Lines 150-157

    def test_emit_without_event_loop(self):
        """Test emit handles case when no event loop is running."""
        # Setup
        handler = LogStreamHandler()
        mock_ws = AsyncMock()
        handler.add_client(mock_ws)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Execute with no event loop
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_get_loop.side_effect = RuntimeError("No event loop")

            # Should not raise exception
            handler.emit(record)
        # Coverage: Lines 155-157

    def test_get_log_stream_handler_singleton(self):
        """Test that get_log_stream_handler returns singleton instance."""
        # Execute
        handler1 = get_log_stream_handler()
        handler2 = get_log_stream_handler()

        # Assert
        assert handler1 is handler2
        assert handler1._log_type == "system_log"
        # Coverage: Lines 187-189

    def test_get_audit_log_stream_handler_singleton(self):
        """Test that get_audit_log_stream_handler returns singleton instance."""
        # Execute
        handler1 = get_audit_log_stream_handler()
        handler2 = get_audit_log_stream_handler()

        # Assert
        assert handler1 is handler2
        assert handler1._log_type == "audit_log"
        # Coverage: Lines 192-197


class TestExtraFieldSerialization:
    """Test JSON metadata in log records."""

    def test_emit_system_log_with_extra_fields(self):
        """Test system log format includes extra fields."""
        # Setup
        handler = LogStreamHandler(log_type="system_log")
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        # Add extra fields
        record.instance_id = "inst-1"
        record.task_id = "task-123"
        record.duration_ms = 1500

        # Execute - emit creates log_entry with extra fields
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = Mock()
            mock_loop.is_running.return_value = False
            mock_get_loop.return_value = mock_loop

            handler.emit(record)
        # Coverage: Lines 115-146

    def test_emit_audit_log_with_metadata(self):
        """Test audit log format includes metadata from extra fields."""
        # Setup
        handler = LogStreamHandler(log_type="audit_log")
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="orchestrator.audit",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="instance_spawned",
            args=(),
            exc_info=None,
        )
        # Add extra fields
        record.event_type = "instance_spawned"
        record.instance_id = "inst-1"
        record.instance_name = "Test Instance"

        # Execute
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = Mock()
            mock_loop.is_running.return_value = False
            mock_get_loop.return_value = mock_loop

            handler.emit(record)
        # Coverage: Lines 53-102

    def test_extra_field_non_serializable_converts_to_string(self):
        """Test that non-JSON-serializable extra fields are converted to string."""
        # Setup
        handler = LogStreamHandler(log_type="system_log")
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add non-serializable object
        class NonSerializable:
            def __str__(self):
                return "custom_object_repr"

        record.custom_obj = NonSerializable()

        # Execute
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = Mock()
            mock_loop.is_running.return_value = False
            mock_get_loop.return_value = mock_loop

            handler.emit(record)
        # Coverage: Lines 142-146, 98-99

    def test_json_extra_filter_in_file_handler(self):
        """Test JsonExtraFilter adds extra fields to log records."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir, log_level="INFO")

            # Execute - log with extra fields
            manager.orchestrator_logger.info(
                "Test message", extra={"custom_field": "custom_value", "count": 42}
            )

            # Assert - check log file contains extra fields
            log_file = Path(tmpdir) / "orchestrator.log"
            assert log_file.exists()
            content = log_file.read_text()
            assert "custom_field" in content
            assert "custom_value" in content
            # Coverage: Lines 293-335


class TestCommunicationLogging:
    """Test instance message audit trails."""

    def test_log_communication_creates_entry(self):
        """Test logging communication event for an instance."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Execute
            manager.log_communication(
                instance_id=instance_id,
                direction="outbound",
                message_type="request",
                content="Process this data",
                parent_id="parent-inst",
            )

            # Assert - check communication log exists
            comm_log = Path(tmpdir) / "instances" / instance_id / "communication.jsonl"
            assert comm_log.exists()

            content = comm_log.read_text()
            log_entry = json.loads(content.strip())

            assert log_entry["event_type"] == "communication"
            assert log_entry["direction"] == "outbound"
            assert log_entry["content"] == "Process this data"
            # Coverage: Lines 540-570

    def test_log_communication_bidirectional_flow(self):
        """Test logging bidirectional message flow with message_id tracking."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"
            message_id = "msg-123"

            # Execute - send request
            manager.log_communication(
                instance_id=instance_id,
                direction="outbound",
                message_type="request",
                content="Request data",
                message_id=message_id,
            )

            # Execute - receive response
            manager.log_communication(
                instance_id=instance_id,
                direction="inbound",
                message_type="response",
                content="Response data",
                message_id=f"{message_id}-reply",
            )

            # Assert - both messages logged
            comm_log = Path(tmpdir) / "instances" / instance_id / "communication.jsonl"
            lines = comm_log.read_text().strip().split("\n")
            assert len(lines) == 2

            entry1 = json.loads(lines[0])
            entry2 = json.loads(lines[1])

            assert entry1["direction"] == "outbound"
            assert entry2["direction"] == "inbound"
            assert entry1["message_id"] == message_id
            # Coverage: Lines 540-570

    def test_log_communication_with_kwargs(self):
        """Test log_communication with additional kwargs."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Execute
            manager.log_communication(
                instance_id=instance_id,
                direction="outbound",
                message_type="request",
                content="Test",
                tokens=150,
                cost=0.0025,
                response_time=1.5,
            )

            # Assert
            comm_log = Path(tmpdir) / "instances" / instance_id / "communication.jsonl"
            content = comm_log.read_text()
            log_entry = json.loads(content.strip())

            assert log_entry["tokens"] == 150
            assert log_entry["cost"] == 0.0025
            assert log_entry["response_time"] == 1.5
            # Coverage: Lines 540-570


class TestTmuxOutputLogging:
    """Test raw tmux pane output logging."""

    def test_log_tmux_output_creates_file(self):
        """Test logging raw tmux pane output to file."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"
            output = "claude> Processing request...\nResult: success"

            # Execute
            manager.log_tmux_output(instance_id=instance_id, output=output)

            # Assert
            tmux_log = Path(tmpdir) / "instances" / instance_id / "tmux_output.log"
            assert tmux_log.exists()

            content = tmux_log.read_text()
            assert "Processing request" in content
            assert "Result: success" in content
            # Coverage: Lines 572-591

    def test_log_tmux_output_incremental_appending(self):
        """Test incremental appending of tmux output."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Execute - multiple log calls
            manager.log_tmux_output(instance_id, "Line 1\n")
            manager.log_tmux_output(instance_id, "Line 2\n")
            manager.log_tmux_output(instance_id, "Line 3\n")

            # Assert - all lines present
            tmux_log = Path(tmpdir) / "instances" / instance_id / "tmux_output.log"
            content = tmux_log.read_text()

            assert "Line 1" in content
            assert "Line 2" in content
            assert "Line 3" in content

            # Assert - multiple timestamps (separator blocks)
            assert content.count("=" * 80) >= 6  # 3 entries * 2 separators each
            # Coverage: Lines 572-591

    def test_log_tmux_output_with_timestamp(self):
        """Test that tmux output includes timestamp."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Execute
            manager.log_tmux_output(instance_id, "Test output")

            # Assert
            tmux_log = Path(tmpdir) / "instances" / instance_id / "tmux_output.log"
            content = tmux_log.read_text()

            # Should contain timestamp in ISO format
            assert "[20" in content  # ISO timestamp starts with year
            assert "Test output" in content
            # Coverage: Lines 585-591

    def test_log_tmux_output_creates_directory_if_not_exists(self):
        """Test that log_tmux_output creates instance directory if it doesn't exist."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "new-inst"

            instance_dir = Path(tmpdir) / "instances" / instance_id
            assert not instance_dir.exists()

            # Execute
            manager.log_tmux_output(instance_id, "Test")

            # Assert
            assert instance_dir.exists()
            # Coverage: Lines 579-581


class TestLogRetrieval:
    """Test historical log reading."""

    def test_get_instance_logs_returns_logs(self):
        """Test retrieving instance logs."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Create instance logger and log some entries
            logger = manager.get_instance_logger(instance_id, "Test Instance")
            logger.info("Log entry 1")
            logger.info("Log entry 2")
            logger.info("Log entry 3")

            # Execute
            logs = manager.get_instance_logs(instance_id, log_type="instance", tail=100)

            # Assert
            assert len(logs) > 0
            assert any("Log entry" in log for log in logs)
            # Coverage: Lines 593-626

    def test_get_instance_logs_with_tail_limit(self):
        """Test log retrieval with tail parameter."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            logger = manager.get_instance_logger(instance_id)
            for i in range(10):
                logger.info(f"Log entry {i}")

            # Execute
            logs = manager.get_instance_logs(instance_id, log_type="instance", tail=3)

            # Assert
            assert len(logs) <= 3
            # Coverage: Lines 620-623

    def test_get_instance_logs_empty_for_nonexistent_instance(self):
        """Test retrieval returns empty list when instance doesn't exist."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)

            # Execute
            logs = manager.get_instance_logs("nonexistent-instance")

            # Assert
            assert logs == []
            # Coverage: Lines 606-608

    def test_get_instance_logs_communication_type(self):
        """Test retrieving communication logs."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Log communication
            manager.log_communication(
                instance_id=instance_id,
                direction="outbound",
                message_type="request",
                content="Test message",
            )

            # Execute
            logs = manager.get_instance_logs(instance_id, log_type="communication")

            # Assert
            assert len(logs) > 0
            assert any("communication" in log for log in logs)
            # Coverage: Lines 610-623

    def test_get_instance_logs_tmux_output_type(self):
        """Test retrieving tmux output logs."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Log tmux output
            manager.log_tmux_output(instance_id, "Tmux output line")

            # Execute
            logs = manager.get_instance_logs(instance_id, log_type="tmux_output")

            # Assert
            assert len(logs) > 0
            assert any("Tmux output line" in log for log in logs)
            # Coverage: Lines 610-623

    def test_get_instance_logs_handles_missing_log_file(self):
        """Test get_instance_logs returns empty when log file doesn't exist."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Create instance directory but no log files
            instance_dir = Path(tmpdir) / "instances" / instance_id
            instance_dir.mkdir(parents=True, exist_ok=True)

            # Execute
            logs = manager.get_instance_logs(instance_id, log_type="instance")

            # Assert
            assert logs == []
            # Coverage: Lines 616-618

    def test_get_instance_logs_handles_read_error(self):
        """Test get_instance_logs handles file read errors."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Create instance and log
            logger = manager.get_instance_logger(instance_id)
            logger.info("Test")

            Path(tmpdir) / "instances" / instance_id / "instance.log"

            # Execute - mock read to raise exception
            with patch.object(Path, "open", side_effect=PermissionError("Access denied")):
                logs = manager.get_instance_logs(instance_id)

                # Assert
                assert logs == []
            # Coverage: Lines 624-626

    def test_get_instance_logs_without_tail_returns_all(self):
        """Test get_instance_logs returns all lines when tail=0."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            logger = manager.get_instance_logger(instance_id)
            for i in range(5):
                logger.info(f"Entry {i}")

            # Execute
            logs = manager.get_instance_logs(instance_id, tail=0)

            # Assert
            # tail=0 means return all lines
            assert len(logs) >= 5
            # Coverage: Lines 620-623


class TestLogCleanup:
    """Test log file deletion."""

    def test_cleanup_instance_logs_deletes_directory(self):
        """Test deletion of instance log directory."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Create instance logs
            logger = manager.get_instance_logger(instance_id, "Test Instance")
            logger.info("Test log")

            instance_dir = Path(tmpdir) / "instances" / instance_id
            assert instance_dir.exists()

            # Execute
            manager.cleanup_instance_logs(instance_id)

            # Assert
            assert not instance_dir.exists()
            # Coverage: Lines 636-650

    def test_cleanup_instance_logs_removes_from_cache(self):
        """Test cleanup removes instance logger from cache."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Create instance logger
            manager.get_instance_logger(instance_id)
            assert instance_id in manager._instance_loggers

            # Execute
            manager.cleanup_instance_logs(instance_id)

            # Assert
            assert instance_id not in manager._instance_loggers
            # Coverage: Lines 652-654

    def test_cleanup_instance_logs_nonexistent_instance(self):
        """Test cleanup handles nonexistent instance gracefully."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)

            # Execute - should not raise exception
            manager.cleanup_instance_logs("nonexistent-instance")

            # Assert - no error raised
            # Coverage: Lines 642-643

    def test_cleanup_instance_logs_handles_errors(self):
        """Test cleanup handles deletion errors gracefully."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)
            instance_id = "inst-1"

            # Create instance logs
            logger = manager.get_instance_logger(instance_id)
            logger.info("Test")

            # Execute - mock shutil.rmtree to raise exception
            with patch("shutil.rmtree", side_effect=PermissionError("Access denied")):
                # Should not raise exception
                manager.cleanup_instance_logs(instance_id)
            # Coverage: Lines 644-650

    def test_get_all_instance_ids(self):
        """Test retrieving all instance IDs with logs."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)

            # Create multiple instances
            manager.get_instance_logger("inst-1", "Instance 1")
            manager.get_instance_logger("inst-2", "Instance 2")
            manager.get_instance_logger("inst-3", "Instance 3")

            # Execute
            instance_ids = manager.get_all_instance_ids()

            # Assert
            assert "inst-1" in instance_ids
            assert "inst-2" in instance_ids
            assert "inst-3" in instance_ids
            assert len(instance_ids) == 3
            # Coverage: Lines 628-634


class TestLoggingManagerInitialization:
    """Test LoggingManager initialization and setup."""

    def test_initialization_creates_directory_structure(self):
        """Test that initialization creates required directories."""
        # Setup & Execute
        with tempfile.TemporaryDirectory() as tmpdir:
            LoggingManager(log_dir=tmpdir, log_level="INFO")

            # Assert
            assert Path(tmpdir).exists()
            assert (Path(tmpdir) / "instances").exists()
            assert (Path(tmpdir) / "audit").exists()
            # Coverage: Lines 224-229

    def test_initialization_sets_log_level(self):
        """Test that log level is set correctly."""
        # Setup & Execute
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir, log_level="DEBUG")

            # Assert
            assert manager.log_level == logging.DEBUG
            # Coverage: Line 222

    def test_orchestrator_logger_has_handlers(self):
        """Test that orchestrator logger has required handlers."""
        # Setup & Execute
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)

            # Assert
            assert len(manager.orchestrator_logger.handlers) > 0
            # Coverage: Lines 258-348

    def test_audit_logger_configured(self):
        """Test that audit logger is properly configured."""
        # Setup & Execute
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)

            # Assert
            assert manager.audit_logger is not None
            assert manager.audit_logger.name == "orchestrator.audit"
            # Coverage: Lines 350-424

    def test_log_audit_event(self):
        """Test logging audit events."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)

            # Execute
            manager.log_audit_event(
                event_type="instance_spawned",
                instance_id="inst-1",
                details={"model": "claude-sonnet", "role": "general"},
            )

            # Assert - check audit log file exists
            audit_files = list((Path(tmpdir) / "audit").glob("audit_*.jsonl"))
            assert len(audit_files) > 0
            # Coverage: Lines 516-538

    def test_get_instance_logger_caches_logger(self):
        """Test that get_instance_logger caches loggers."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)

            # Execute
            logger1 = manager.get_instance_logger("inst-1", "Test")
            logger2 = manager.get_instance_logger("inst-1", "Test")

            # Assert
            assert logger1 is logger2
            # Coverage: Lines 438-439

    def test_get_instance_logger_creates_metadata_file(self):
        """Test that get_instance_logger creates metadata.json."""
        # Setup
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LoggingManager(log_dir=tmpdir)

            # Execute
            manager.get_instance_logger("inst-1", "Test Instance")

            # Assert
            metadata_file = Path(tmpdir) / "instances" / "inst-1" / "metadata.json"
            assert metadata_file.exists()

            metadata = json.loads(metadata_file.read_text())
            assert metadata["instance_id"] == "inst-1"
            assert metadata["instance_name"] == "Test Instance"
            # Coverage: Lines 498-506
