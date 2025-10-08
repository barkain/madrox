"""Tests for the log streaming infrastructure."""

import asyncio
import json
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.orchestrator.log_stream_handler import (
    LogStreamHandler,
    audit_log,
    get_log_stream_handler,
    setup_log_streaming,
)


class TestLogStreamHandler:
    """Test the LogStreamHandler class."""

    def test_handler_initialization(self):
        """Test handler can be initialized."""
        handler = LogStreamHandler(level=logging.DEBUG)
        assert handler is not None
        assert handler.level == logging.DEBUG
        assert len(handler._websocket_clients) == 0

    def test_add_remove_client(self):
        """Test adding and removing WebSocket clients."""
        handler = LogStreamHandler()
        mock_ws = MagicMock()

        # Add client
        handler.add_client(mock_ws)
        assert mock_ws in handler._websocket_clients
        assert len(handler._websocket_clients) == 1

        # Remove client
        handler.remove_client(mock_ws)
        assert mock_ws not in handler._websocket_clients
        assert len(handler._websocket_clients) == 0

    def test_set_event_loop(self):
        """Test setting the event loop."""
        handler = LogStreamHandler()
        loop = asyncio.new_event_loop()
        handler.set_event_loop(loop)
        assert handler._loop == loop
        loop.close()

    def test_is_audit_log_with_flag(self):
        """Test audit log detection via is_audit flag."""
        handler = LogStreamHandler()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.is_audit = True
        assert handler._is_audit_log(record) is True

    def test_is_audit_log_with_logger_name(self):
        """Test audit log detection via logger name."""
        handler = LogStreamHandler()
        record = logging.LogRecord(
            name="audit.test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        assert handler._is_audit_log(record) is True

    def test_is_audit_log_with_message_prefix(self):
        """Test audit log detection via message prefix."""
        handler = LogStreamHandler()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="[AUDIT] Test message",
            args=(),
            exc_info=None,
        )
        # getMessage() is called automatically, so [AUDIT] prefix is detected
        assert handler._is_audit_log(record) is True

    def test_is_audit_log_system(self):
        """Test system log detection."""
        handler = LogStreamHandler()
        record = logging.LogRecord(
            name="madrox.server",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        assert handler._is_audit_log(record) is False

    def test_format_system_log_message(self):
        """Test formatting a system log message."""
        handler = LogStreamHandler()
        record = logging.LogRecord(
            name="madrox.server",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Server started",
            args=(),
            exc_info=None,
        )
        record.funcName = "start_server"
        record.module = "server"

        message = handler._format_log_message(record, is_audit=False)

        assert message["type"] == "system_log"
        assert message["data"]["level"] == "INFO"
        assert message["data"]["logger"] == "madrox.server"
        assert message["data"]["message"] == "Server started"
        assert message["data"]["module"] == "server"
        assert message["data"]["function"] == "start_server"
        assert message["data"]["line"] == 42
        assert "timestamp" in message["data"]

    def test_format_audit_log_message(self):
        """Test formatting an audit log message."""
        handler = LogStreamHandler()
        record = logging.LogRecord(
            name="audit.instance",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Instance spawned",
            args=(),
            exc_info=None,
        )
        record.action = "instance_spawn"
        record.metadata = {"instance_id": "abc123", "role": "orchestrator"}

        message = handler._format_log_message(record, is_audit=True)

        assert message["type"] == "audit_log"
        assert message["data"]["level"] == "INFO"
        assert message["data"]["logger"] == "audit.instance"
        assert message["data"]["message"] == "Instance spawned"
        assert message["data"]["action"] == "instance_spawn"
        assert message["data"]["metadata"] == {"instance_id": "abc123", "role": "orchestrator"}
        assert "timestamp" in message["data"]

    @pytest.mark.asyncio
    async def test_async_broadcast(self):
        """Test asynchronous broadcasting to WebSocket clients."""
        handler = LogStreamHandler()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        handler.add_client(mock_ws1)
        handler.add_client(mock_ws2)

        message = {"type": "system_log", "data": {"message": "test"}}
        await handler._async_broadcast(message)

        mock_ws1.send_json.assert_awaited_once_with(message)
        mock_ws2.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_async_broadcast_removes_failed_clients(self):
        """Test that failed clients are removed during broadcast."""
        handler = LogStreamHandler()
        mock_ws_good = AsyncMock()
        mock_ws_bad = AsyncMock()
        mock_ws_bad.send_json.side_effect = Exception("Connection lost")

        handler.add_client(mock_ws_good)
        handler.add_client(mock_ws_bad)

        message = {"type": "system_log", "data": {"message": "test"}}
        await handler._async_broadcast(message)

        # Good client should receive message
        mock_ws_good.send_json.assert_awaited_once()

        # Bad client should be removed
        assert mock_ws_bad not in handler._websocket_clients
        assert mock_ws_good in handler._websocket_clients


class TestAuditLogHelper:
    """Test the audit_log convenience function."""

    def test_audit_log_basic(self, caplog):
        """Test basic audit_log usage."""
        logger = logging.getLogger("test.audit")
        logger.setLevel(logging.INFO)

        with caplog.at_level(logging.INFO):
            audit_log(
                logger,
                "Instance spawned",
                action="instance_spawn",
                metadata={"instance_id": "test123"},
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.is_audit is True
        assert record.action == "instance_spawn"
        assert record.metadata == {"instance_id": "test123"}
        assert record.getMessage() == "Instance spawned"

    def test_audit_log_with_extra_fields(self, caplog):
        """Test audit_log with additional fields."""
        logger = logging.getLogger("test.audit")
        logger.setLevel(logging.INFO)

        with caplog.at_level(logging.INFO):
            audit_log(
                logger,
                "User action",
                action="user_login",
                metadata={"user_id": "user123"},
                instance_id="inst456",
                session_id="sess789",
            )

        record = caplog.records[0]
        assert record.is_audit is True
        assert record.instance_id == "inst456"
        assert record.session_id == "sess789"

    def test_audit_log_different_levels(self, caplog):
        """Test audit_log with different log levels."""
        logger = logging.getLogger("test.audit")
        logger.setLevel(logging.DEBUG)

        with caplog.at_level(logging.DEBUG):
            audit_log(logger, "Warning audit", action="warning_event", level=logging.WARNING)

        record = caplog.records[0]
        assert record.levelname == "WARNING"
        assert record.is_audit is True


class TestLogStreamingSetup:
    """Test the log streaming setup functions."""

    def test_get_log_stream_handler_singleton(self):
        """Test that get_log_stream_handler returns singleton."""
        handler1 = get_log_stream_handler()
        handler2 = get_log_stream_handler()
        assert handler1 is handler2

    def test_setup_log_streaming(self):
        """Test setup_log_streaming attaches handler to root logger."""
        loop = asyncio.new_event_loop()

        # Get the handler before setup
        handler = get_log_stream_handler()
        root_logger = logging.getLogger()

        # Remove handler if already present (from previous tests)
        if handler in root_logger.handlers:
            root_logger.removeHandler(handler)

        # Setup log streaming
        setup_log_streaming(loop)

        # Verify handler is attached
        assert handler in root_logger.handlers
        assert handler._loop == loop

        # Cleanup
        root_logger.removeHandler(handler)
        loop.close()

    def test_setup_log_streaming_no_duplicate(self):
        """Test that setup_log_streaming doesn't add duplicate handlers."""
        loop = asyncio.new_event_loop()
        root_logger = logging.getLogger()

        # Setup twice
        setup_log_streaming(loop)
        initial_count = root_logger.handlers.count(get_log_stream_handler())
        setup_log_streaming(loop)
        final_count = root_logger.handlers.count(get_log_stream_handler())

        # Should still only have one instance
        assert initial_count == final_count

        # Cleanup
        handler = get_log_stream_handler()
        if handler in root_logger.handlers:
            root_logger.removeHandler(handler)
        loop.close()


@pytest.mark.asyncio
async def test_integration_system_log_flow():
    """Integration test: system log flows through handler to WebSocket."""
    # Setup
    handler = LogStreamHandler()
    loop = asyncio.get_event_loop()
    handler.set_event_loop(loop)

    mock_ws = AsyncMock()
    handler.add_client(mock_ws)

    logger = logging.getLogger("madrox.test")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Generate log
    logger.info("Test system log", extra={"instance_id": "test123"})

    # Give async broadcast time to complete
    await asyncio.sleep(0.1)

    # Verify
    mock_ws.send_json.assert_called_once()
    call_args = mock_ws.send_json.call_args[0][0]
    assert call_args["type"] == "system_log"
    assert call_args["data"]["message"] == "Test system log"
    assert call_args["data"]["instance_id"] == "test123"

    # Cleanup
    logger.removeHandler(handler)


@pytest.mark.asyncio
async def test_integration_audit_log_flow():
    """Integration test: audit log flows through handler to WebSocket."""
    # Setup
    handler = LogStreamHandler()
    loop = asyncio.get_event_loop()
    handler.set_event_loop(loop)

    mock_ws = AsyncMock()
    handler.add_client(mock_ws)

    logger = logging.getLogger("audit.test")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Generate audit log using helper
    audit_log(
        logger,
        "Instance spawned",
        action="instance_spawn",
        metadata={"instance_id": "test456"},
    )

    # Give async broadcast time to complete
    await asyncio.sleep(0.1)

    # Verify
    mock_ws.send_json.assert_called_once()
    call_args = mock_ws.send_json.call_args[0][0]
    assert call_args["type"] == "audit_log"
    assert call_args["data"]["message"] == "Instance spawned"
    assert call_args["data"]["action"] == "instance_spawn"
    assert call_args["data"]["metadata"]["instance_id"] == "test456"

    # Cleanup
    logger.removeHandler(handler)
