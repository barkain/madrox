"""WebSocket log streaming handler for dual-panel logging system.

This module provides a custom logging.Handler that streams log messages
to connected WebSocket clients in real-time, supporting both system logs
and audit logs with proper categorization.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any


class LogStreamHandler(logging.Handler):
    """Custom logging handler that streams logs to WebSocket clients.

    This handler intercepts log messages from the Python logging system and
    broadcasts them to all connected WebSocket clients. It automatically
    categorizes logs as either system logs or audit logs based on:
    - record.is_audit flag in extra dict
    - Logger name starting with 'audit.'
    - Message starting with '[AUDIT]'
    """

    def __init__(self, level: int = logging.NOTSET):
        """Initialize the log stream handler.

        Args:
            level: Minimum logging level to handle
        """
        super().__init__(level)
        self._websocket_clients: set[Any] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def add_client(self, websocket: Any):
        """Add a WebSocket client to receive log streams.

        Args:
            websocket: WebSocket connection to add
        """
        self._websocket_clients.add(websocket)

    def remove_client(self, websocket: Any):
        """Remove a WebSocket client from log streams.

        Args:
            websocket: WebSocket connection to remove
        """
        self._websocket_clients.discard(websocket)

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the event loop for async operations.

        Args:
            loop: Event loop to use for sending messages
        """
        self._loop = loop

    def emit(self, record: logging.LogRecord):
        """Process and stream a log record to WebSocket clients.

        Args:
            record: Log record to process
        """
        try:
            # Determine if this is an audit log
            is_audit = self._is_audit_log(record)

            # Format the log message
            message_data = self._format_log_message(record, is_audit)

            # Send to all connected clients
            if self._websocket_clients and message_data:
                self._broadcast_message(message_data)

        except Exception as e:
            # Don't let handler errors break the logging system
            self.handleError(record)

    def _is_audit_log(self, record: logging.LogRecord) -> bool:
        """Determine if a log record is an audit log.

        Args:
            record: Log record to check

        Returns:
            True if this is an audit log, False otherwise
        """
        # Check for explicit is_audit flag
        if hasattr(record, 'is_audit') and record.is_audit:
            return True

        # Check logger name for 'audit.' prefix
        if record.name.startswith('audit.') or 'audit' in record.name.split('.'):
            return True

        # Check message for [AUDIT] prefix
        message = record.getMessage()
        if message.startswith('[AUDIT]'):
            return True

        return False

    def _format_log_message(self, record: logging.LogRecord, is_audit: bool) -> dict[str, Any]:
        """Format a log record into a WebSocket message.

        Args:
            record: Log record to format
            is_audit: Whether this is an audit log

        Returns:
            Formatted message dictionary
        """
        timestamp = datetime.fromtimestamp(record.created).isoformat() + 'Z'

        if is_audit:
            # Format as audit log
            message_data = {
                "type": "audit_log",
                "data": {
                    "timestamp": timestamp,
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
            }

            # Add audit-specific fields if present
            if hasattr(record, 'action'):
                message_data['data']['action'] = record.action

            if hasattr(record, 'metadata'):
                message_data['data']['metadata'] = record.metadata

            # Include instance_id and event_type if available
            if hasattr(record, 'instance_id'):
                message_data['data']['instance_id'] = record.instance_id

            if hasattr(record, 'event_type'):
                message_data['data']['event_type'] = record.event_type

        else:
            # Format as system log
            message_data = {
                "type": "system_log",
                "data": {
                    "timestamp": timestamp,
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                }
            }

            # Add extra context fields if present
            if hasattr(record, 'instance_id'):
                message_data['data']['instance_id'] = record.instance_id

            if hasattr(record, 'instance_name'):
                message_data['data']['instance_name'] = record.instance_name

        return message_data

    def _broadcast_message(self, message_data: dict[str, Any]):
        """Broadcast a message to all connected WebSocket clients.

        Args:
            message_data: Message to broadcast
        """
        if not self._loop:
            # No event loop set, can't send async messages
            return

        # Schedule the broadcast on the event loop
        asyncio.run_coroutine_threadsafe(
            self._async_broadcast(message_data),
            self._loop
        )

    async def _async_broadcast(self, message_data: dict[str, Any]):
        """Asynchronously broadcast a message to all WebSocket clients.

        Args:
            message_data: Message to broadcast
        """
        # Create a copy of clients to avoid modification during iteration
        clients_to_remove = set()

        for client in list(self._websocket_clients):
            try:
                await client.send_json(message_data)
            except Exception:
                # Client disconnected or error, mark for removal
                clients_to_remove.add(client)

        # Remove failed clients
        for client in clients_to_remove:
            self._websocket_clients.discard(client)


def audit_log(
    logger: logging.Logger,
    message: str,
    action: str | None = None,
    metadata: dict[str, Any] | None = None,
    level: int = logging.INFO,
    **kwargs
):
    """Convenience function for logging audit events.

    This function makes it easy to log audit events with proper formatting
    and metadata. The log will be automatically routed to the audit log stream.

    Args:
        logger: Logger to use (can be any logger)
        message: Audit message
        action: Action type (e.g., 'instance_spawn', 'message_sent')
        metadata: Additional metadata dictionary
        level: Log level (default: INFO)
        **kwargs: Additional fields to include in the log

    Example:
        >>> audit_log(
        ...     logger,
        ...     "Instance main-orchestrator spawned",
        ...     action="instance_spawn",
        ...     metadata={"instance_id": "abc123", "role": "orchestrator"}
        ... )
    """
    extra = {
        'is_audit': True,
        'action': action,
        'metadata': metadata or {},
    }
    extra.update(kwargs)

    logger.log(level, message, extra=extra)


# Global log stream handler instance
_log_stream_handler: LogStreamHandler | None = None


def get_log_stream_handler() -> LogStreamHandler:
    """Get or create the global LogStreamHandler instance.

    Returns:
        Global LogStreamHandler instance
    """
    global _log_stream_handler
    if _log_stream_handler is None:
        _log_stream_handler = LogStreamHandler(level=logging.DEBUG)
    return _log_stream_handler


def setup_log_streaming(event_loop: asyncio.AbstractEventLoop | None = None):
    """Setup log streaming by attaching the handler to the root logger.

    This should be called once at application startup to enable log streaming.

    Args:
        event_loop: Event loop to use for async operations. If None, uses current loop.

    Example:
        >>> loop = asyncio.get_event_loop()
        >>> setup_log_streaming(loop)
    """
    handler = get_log_stream_handler()

    # Set event loop
    if event_loop is None:
        try:
            event_loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop in current thread
            pass

    if event_loop:
        handler.set_event_loop(event_loop)

    # Attach to root logger
    root_logger = logging.getLogger()

    # Check if handler is already attached
    if handler not in root_logger.handlers:
        root_logger.addHandler(handler)
