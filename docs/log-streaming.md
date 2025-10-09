# Log Streaming Infrastructure

## Overview

The backend logging infrastructure provides real-time streaming of system and audit logs to WebSocket clients for the dual-panel logging system. This enables the frontend to display live logs as they occur, categorized into system logs and audit logs.

## Architecture

### Components

1. **LogStreamHandler** (`src/orchestrator/log_stream_handler.py`)
   - Custom Python `logging.Handler` that intercepts log messages
   - Automatically categorizes logs as system or audit logs
   - Broadcasts formatted messages to all connected WebSocket clients
   - Thread-safe and async-compatible

2. **WebSocket Integration** (`src/orchestrator/server.py`)
   - Modified `/ws/monitor` endpoint to register clients with LogStreamHandler
   - Automatic client registration/deregistration
   - Cleanup on disconnection

3. **Helper Functions**
   - `audit_log()`: Convenience function for logging audit events
   - `setup_log_streaming()`: One-time initialization at startup
   - `get_log_stream_handler()`: Singleton accessor

## Log Categorization

Logs are automatically categorized as **audit logs** if ANY of these conditions are met:

1. `record.is_audit` flag is `True` (set via `extra` dict)
2. Logger name starts with `'audit.'`
3. Message starts with `'[AUDIT]'`

Otherwise, logs are categorized as **system logs**.

## Message Format

### System Log Message

```json
{
  "type": "system_log",
  "data": {
    "timestamp": "2025-10-08T18:30:45.123Z",
    "level": "INFO",
    "logger": "madrox.server",
    "message": "Instance spawned successfully",
    "module": "server",
    "function": "spawn_instance",
    "line": 142,
    "instance_id": "abc123",  // Optional extra fields
    "instance_name": "main-orchestrator"
  }
}
```

### Audit Log Message

```json
{
  "type": "audit_log",
  "data": {
    "timestamp": "2025-10-08T18:30:45.123Z",
    "level": "INFO",
    "logger": "audit.instance",
    "message": "Instance main-orchestrator spawned",
    "action": "instance_spawn",
    "metadata": {
      "instance_id": "abc123",
      "role": "orchestrator",
      "model": "claude-4-sonnet"
    },
    "instance_id": "abc123",  // Optional
    "event_type": "spawn"     // Optional
  }
}
```

## Usage

### Setup (Application Startup)

The log streaming is automatically set up when the server starts:

```python
from src.orchestrator.log_stream_handler import setup_log_streaming
import asyncio

# In server startup code
loop = asyncio.get_event_loop()
setup_log_streaming(loop)
```

This is already integrated in `server.py:905` in the `start_server()` method.

### Logging System Events

Use standard Python logging for system events:

```python
import logging

logger = logging.getLogger("madrox.instance_manager")

# Standard logging - automatically captured and streamed
logger.info("Instance spawned successfully")
logger.warning("High memory usage detected", extra={"memory_mb": 512})
logger.error("Failed to connect to instance", extra={"instance_id": "abc123"})
```

### Logging Audit Events

Use the `audit_log()` helper function for audit events:

```python
from src.orchestrator import audit_log
import logging

logger = logging.getLogger("audit.instance")

# Audit log with action and metadata
audit_log(
    logger,
    "Instance main-orchestrator spawned",
    action="instance_spawn",
    metadata={
        "instance_id": "abc-123",
        "role": "orchestrator",
        "model": "claude-4-sonnet"
    }
)

# Audit log with custom level
audit_log(
    logger,
    "Instance terminated unexpectedly",
    action="instance_terminate",
    metadata={"instance_id": "abc-123", "reason": "crash"},
    level=logging.ERROR
)
```

### Alternative: Use Audit Logger Directly

```python
import logging

# Create logger with 'audit.' prefix
logger = logging.getLogger("audit.instance")

# Log with is_audit flag
logger.info(
    "User logged in",
    extra={
        "is_audit": True,
        "action": "user_login",
        "metadata": {"user_id": "user123"}
    }
)
```

### WebSocket Client Management

WebSocket clients are automatically registered when they connect to `/ws/monitor`:

```python
# In WebSocket endpoint handler
@app.websocket("/ws/monitor")
async def monitor_websocket(websocket: WebSocket):
    await websocket.accept()

    # Register client for log streaming
    log_handler = get_log_stream_handler()
    log_handler.add_client(websocket)

    try:
        # ... existing monitoring code ...
    finally:
        # Cleanup on disconnect
        log_handler.remove_client(websocket)
```

## Best Practices

### 1. Use Appropriate Log Levels

- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages (normal operation)
- `WARNING`: Warning messages (potential issues)
- `ERROR`: Error messages (failures)
- `CRITICAL`: Critical errors (system instability)

### 2. Use Descriptive Logger Names

```python
# Good - hierarchical and descriptive
logging.getLogger("madrox.instance_manager")
logging.getLogger("madrox.tmux.pane_capture")
logging.getLogger("audit.instance")
logging.getLogger("audit.coordination")

# Bad - too generic
logging.getLogger("manager")
logging.getLogger("audit")
```

### 3. Include Context in Extra Fields

```python
# Good - includes relevant context
logger.info(
    "Instance spawned",
    extra={
        "instance_id": instance_id,
        "instance_name": name,
        "role": role,
        "model": model
    }
)

# Bad - no context
logger.info("Instance spawned")
```

### 4. Use audit_log() for All Audit Events

```python
# Good - using helper function
audit_log(
    logger,
    "Instance spawned",
    action="instance_spawn",
    metadata={"instance_id": "abc123"}
)

# Bad - manual extra fields (error-prone)
logger.info(
    "Instance spawned",
    extra={
        "is_audit": True,  # Easy to forget
        "action": "instance_spawn",
        "metadata": {"instance_id": "abc123"}
    }
)
```

### 5. Choose Appropriate Actions for Audit Logs

Use consistent action names:

- **instance_spawn** - Instance created
- **instance_terminate** - Instance stopped
- **message_sent** - Message sent to instance
- **message_received** - Response received from instance
- **state_change** - Instance state changed
- **coordination_start** - Coordination task started
- **coordination_complete** - Coordination task finished
- **error** - Error occurred
- **timeout** - Operation timed out

## Testing

Run the test suite:

```bash
pytest tests/test_log_streaming.py -v
```

Run the demo:

```bash
python examples/demo_log_streaming.py
```

## Integration Points

### 1. Server Startup (server.py:905)

```python
async def start_server(self):
    # ... existing code ...

    # Setup log streaming
    from .log_stream_handler import setup_log_streaming
    setup_log_streaming(asyncio.get_event_loop())

    # ... rest of startup ...
```

### 2. WebSocket Endpoint (server.py:134-335)

```python
@app.websocket("/ws/monitor")
async def monitor_websocket(websocket: WebSocket):
    await websocket.accept()

    # Add client to log stream
    log_handler = get_log_stream_handler()
    log_handler.add_client(websocket)

    try:
        # ... monitoring code ...
    finally:
        log_handler.remove_client(websocket)
```

### 3. Audit Logger (logging_manager.py:141)

```python
def _setup_audit_logger(self):
    # Changed from "orchestrator.audit" to "audit.orchestrator"
    logger = logging.getLogger("audit.orchestrator")
    # ... rest of setup ...
```

## Performance Considerations

1. **Asynchronous Broadcasting**: Log messages are broadcast asynchronously to avoid blocking the logging thread
2. **Failed Client Removal**: Clients that fail to receive messages are automatically removed
3. **Singleton Handler**: Only one LogStreamHandler instance exists, reducing overhead
4. **Minimal Formatting**: Log formatting is lightweight and efficient

## Troubleshooting

### Logs Not Appearing in Frontend

1. Check if log streaming is set up: `setup_log_streaming()` should be called at startup
2. Verify WebSocket client is registered: `log_handler.add_client(websocket)` in endpoint
3. Check logger level: Logger must be at appropriate level (e.g., `INFO` or `DEBUG`)
4. Verify logger name: For audit logs, must start with `'audit.'`

### WebSocket Connection Issues

1. Check client cleanup: Ensure `remove_client()` is called in `finally` block
2. Verify event loop: LogStreamHandler needs event loop for async operations
3. Check for exceptions: Review handler error logs

### Performance Issues

1. Reduce log verbosity: Use appropriate log levels
2. Limit connected clients: Too many WebSocket clients can cause overhead
3. Check network latency: Slow clients may cause message backlog

## File Locations

- **Handler Implementation**: `/Users/nadavbarkai/dev/madrox/src/orchestrator/log_stream_handler.py`
- **Server Integration**: `/Users/nadavbarkai/dev/madrox/src/orchestrator/server.py`
- **Tests**: `/Users/nadavbarkai/dev/madrox/tests/test_log_streaming.py`
- **Demo**: `/Users/nadavbarkai/dev/madrox/examples/demo_log_streaming.py`
- **Documentation**: `/Users/nadavbarkai/dev/madrox/docs/log-streaming.md`

## Future Enhancements

Potential improvements:

1. **Log Filtering**: Allow clients to subscribe to specific log levels or loggers
2. **Batching**: Batch multiple log messages to reduce WebSocket overhead
3. **Compression**: Compress log data for large messages
4. **Replay**: Allow new clients to request recent log history
5. **Metrics**: Track log streaming performance and errors
