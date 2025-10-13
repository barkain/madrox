# Log Streaming Infrastructure

## Overview

The backend logging infrastructure provides real-time streaming of system and audit logs to WebSocket clients for the dual-panel logging system. This enables the frontend to display live logs as they occur, categorized into system logs and audit logs.

## Architecture

### Components

1. **LogStreamHandler** (`src/orchestrator/logging_manager.py`)
   - Custom Python `logging.Handler` that intercepts log messages
   - Separate handlers for system and audit logs
   - Automatically formats messages according to log type
   - Broadcasts formatted messages to all connected WebSocket clients
   - Thread-safe and async-compatible

2. **WebSocket Endpoint** (`src/orchestrator/server.py`)
   - Single `/ws/logs` endpoint for both system and audit logs
   - Automatic client registration with both handlers
   - Cleanup on disconnection

3. **LoggingManager** (`src/orchestrator/logging_manager.py`)
   - Centralized logging configuration
   - Manages file handlers, console handlers, and WebSocket handlers
   - Separate audit logger configuration

## Log Types

### System Logs
- Source: `logging.getLogger("orchestrator.*")` loggers (excluding `orchestrator.audit`)
- Purpose: General application logs, debugging, errors
- File: `/tmp/madrox_logs/orchestrator.log`

### Audit Logs
- Source: `logging.getLogger("orchestrator.audit")`
- Purpose: Track important events (instance lifecycle, state changes)
- File: `/tmp/madrox_logs/audit/audit_YYYYMMDD.jsonl`

## Message Format

### System Log Message

```json
{
  "type": "system_log",
  "data": {
    "timestamp": "2025-10-13T09:27:24.339163",
    "level": "INFO",
    "logger": "orchestrator.server",
    "message": "Instance spawned successfully",
    "module": "server",
    "function": "spawn_instance",
    "line": 142,
    "instance_id": "abc123"  // Extra fields included directly
  }
}
```

### Audit Log Message

```json
{
  "type": "audit_log",
  "data": {
    "timestamp": "2025-10-13T09:27:24.339163",
    "level": "INFO",
    "logger": "orchestrator.audit",
    "message": "instance_spawn",
    "action": "instance_spawn",
    "metadata": {
      "instance_id": "97847539-c28b-4976-9d6c-56f7e274ec81",
      "details": {
        "instance_name": "test-instance",
        "role": "general",
        "instance_type": "claude",
        "model": null,
        "enable_madrox": true,
        "bypass_isolation": false
      }
    }
  }
}
```

**Key Differences:**
- Audit logs have `action` field (from `event_type` extra)
- Audit logs use `metadata` object for extra fields
- System logs include `module`, `function`, `line` fields
- System logs include extra fields directly at top level

## Usage

### Logging System Events

Use standard Python logging for system events:

```python
import logging

logger = logging.getLogger("orchestrator.instance_manager")

# Standard logging - automatically captured and streamed
logger.info("Instance spawned successfully")
logger.warning("High memory usage detected", extra={"memory_mb": 512})
logger.error("Failed to connect to instance", extra={"instance_id": "abc123"})
```

### Logging Audit Events

Use the `LoggingManager.log_audit_event()` method:

```python
from src.orchestrator.logging_manager import LoggingManager

logging_manager = LoggingManager()

# Log audit event
logging_manager.log_audit_event(
    event_type="instance_spawn",
    instance_id="abc-123",
    details={
        "instance_name": "test-instance",
        "role": "general",
        "instance_type": "claude",
        "model": "claude-sonnet-4",
        "enable_madrox": True,
        "bypass_isolation": False
    }
)

# Log instance termination
logging_manager.log_audit_event(
    event_type="instance_terminate",
    instance_id="abc-123",
    details={
        "instance_name": "test-instance",
        "force": False,
        "final_state": "terminated",
        "total_requests": 5,
        "total_tokens": 1234,
        "total_cost": 0.05,
        "uptime_seconds": 120.5
    }
)
```

### WebSocket Client Connection

Frontend connects to single endpoint for both log types:

```typescript
const ws = new WebSocket("ws://localhost:8001/ws/logs")

ws.onmessage = (event) => {
  const message = JSON.parse(event.data)

  switch (message.type) {
    case "system_log":
      // Handle system log
      addSystemLog(message.data)
      break

    case "audit_log":
      // Handle audit log
      addAuditLog(message.data)
      break
  }
}
```

## Implementation Details

### LogStreamHandler.emit()

The `emit()` method formats log records differently based on `_log_type`:

**For Audit Logs:**
1. Extract base fields: `timestamp`, `level`, `logger`, `message`
2. Extract `event_type` as `action` field
3. Collect remaining extra fields into `metadata` object
4. Exclude standard LogRecord attributes

**For System Logs:**
1. Extract base fields: `timestamp`, `level`, `logger`, `message`
2. Add context fields: `module`, `function`, `line`
3. Include all extra fields directly at top level

### Async Broadcasting

```python
# In emit() method
if self.clients:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self._broadcast(log_entry))
    except RuntimeError:
        pass  # No event loop, skip WebSocket broadcast
```

The broadcast is non-blocking and runs asynchronously to avoid blocking the logging thread.

### Client Management

```python
class LogStreamHandler(logging.Handler):
    def __init__(self, log_type: str = "system_log"):
        super().__init__()
        self.clients: set[WebSocket] = set()
        self._log_type = log_type

    def add_client(self, websocket: WebSocket):
        self.clients.add(websocket)

    def remove_client(self, websocket: WebSocket):
        self.clients.discard(websocket)
```

### Handler Singletons

```python
# Global singletons
_audit_log_stream_handler: LogStreamHandler | None = None

def get_log_stream_handler() -> LogStreamHandler:
    """Get singleton for system logs."""
    return LogStreamHandler.get_instance()

def get_audit_log_stream_handler() -> LogStreamHandler:
    """Get singleton for audit logs."""
    global _audit_log_stream_handler
    if _audit_log_stream_handler is None:
        _audit_log_stream_handler = LogStreamHandler(log_type="audit_log")
    return _audit_log_stream_handler
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
logging.getLogger("orchestrator.instance_manager")
logging.getLogger("orchestrator.tmux_manager")
logging.getLogger("orchestrator.server")

# Bad - too generic
logging.getLogger("manager")
logging.getLogger("server")
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

### 4. Use Consistent Audit Event Types

Standard event types:
- **instance_spawn** - Instance created
- **instance_terminate** - Instance stopped
- **message_sent** - Message sent to instance
- **message_received** - Response received from instance
- **state_change** - Instance state changed
- **error** - Error occurred
- **timeout** - Operation timed out

## Integration Points

### 1. LoggingManager Initialization (logging_manager.py:191-227)

```python
def __init__(self, log_dir: str | Path = "/tmp/madrox_logs", log_level: str = "INFO"):
    # Setup orchestrator logger with WebSocket handler
    self._setup_orchestrator_logger()

    # Setup audit logger with separate WebSocket handler
    self._setup_audit_logger()

    # Configure child loggers (exclude orchestrator.audit)
    for name in logging.Logger.manager.loggerDict.keys():
        if name.startswith("orchestrator.") and name != "orchestrator.audit":
            child_logger = logging.getLogger(name)
            child_logger.propagate = True
            child_logger.handlers.clear()
```

### 2. WebSocket Endpoint (server.py:346-412)

```python
@app.websocket("/ws/logs")
async def logs_websocket(websocket: WebSocket):
    await websocket.accept()

    # Register with both handlers
    log_handler = get_log_stream_handler()
    log_handler.add_client(websocket)

    audit_log_handler = get_audit_log_stream_handler()
    audit_log_handler.add_client(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        log_handler.remove_client(websocket)
        audit_log_handler.remove_client(websocket)
```

### 3. Audit Logger Setup (logging_manager.py:388-395)

```python
def _setup_audit_logger(self):
    logger = logging.getLogger("orchestrator.audit")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # File handler (JSONL format)
    # ...

    # WebSocket handler
    audit_stream_handler = get_audit_log_stream_handler()
    audit_stream_handler.setLevel(logging.INFO)
    logger.addHandler(audit_stream_handler)
```

## Performance Considerations

1. **Asynchronous Broadcasting**: Log messages are broadcast asynchronously to avoid blocking
2. **Failed Client Removal**: Clients that fail to receive messages are automatically removed
3. **Singleton Handlers**: Only one handler instance per log type, reducing overhead
4. **Minimal Formatting**: Log formatting is lightweight and efficient
5. **Event Loop Check**: Only creates tasks when event loop is running

## Troubleshooting

### Logs Not Appearing in Frontend

1. **Check WebSocket connection**: Verify connection to `ws://localhost:8001/ws/logs`
2. **Check logger configuration**: Ensure `orchestrator.audit` logger is not reconfigured
3. **Verify client registration**: Both handlers should have clients registered
4. **Check message format**: Ensure frontend expects correct schema

### Audit Logs Not Streaming

1. **Verify handler setup**: Check `get_audit_log_stream_handler()` is called
2. **Check logger propagation**: `orchestrator.audit` must have `propagate=False`
3. **Verify event_type field**: Should be set in `extra` dict
4. **Check message format**: Should have `action` and `metadata` fields

### WebSocket Connection Issues

1. **Check client cleanup**: Ensure `remove_client()` is called in `finally` block
2. **Verify event loop**: Handler needs running event loop for async operations
3. **Check for exceptions**: Review handler error logs
4. **Monitor client count**: Dead clients should be removed automatically

## File Locations

- **Handler Implementation**: `/Users/nadavbarkai/dev/madrox/src/orchestrator/logging_manager.py`
- **Server Integration**: `/Users/nadavbarkai/dev/madrox/src/orchestrator/server.py`
- **Documentation**: `/Users/nadavbarkai/dev/madrox/docs/log-streaming.md`
- **Frontend Integration**: `/Users/nadavbarkai/dev/madrox/frontend/hooks/use-log-websocket.ts`
- **Frontend Types**: `/Users/nadavbarkai/dev/madrox/frontend/types/index.ts`

## Frontend Integration

### TypeScript Types

```typescript
// System log format
export interface SystemLog {
  id: string
  timestamp: string
  level: SystemLogLevel
  logger: string
  message: string
  module: string
  function: string
  line: number
}

// Audit log format
export interface AuditLog {
  id: string
  timestamp: string
  level: AuditLogLevel
  logger: string
  message: string
  action?: string
  metadata?: Record<string, any>
}

// WebSocket message types
export interface SystemLogMessage {
  type: "system_log"
  data: Omit<SystemLog, "id">
}

export interface AuditLogMessage {
  type: "audit_log"
  data: Omit<AuditLog, "id">
}

export type LogWebSocketMessage = SystemLogMessage | AuditLogMessage
```

### WebSocket Hook

```typescript
const ws = new WebSocket(WS_URL)

ws.onmessage = (event) => {
  const message: LogWebSocketMessage = JSON.parse(event.data)

  switch (message.type) {
    case "system_log":
      const systemLog: SystemLog = {
        id: `sys-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        ...message.data
      }
      addSystemLog(systemLog)
      break

    case "audit_log":
      const auditLog: AuditLog = {
        id: `audit-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        ...message.data
      }
      addAuditLog(auditLog)
      break
  }
}
```

## Future Enhancements

Potential improvements:

1. **Log Filtering**: Allow clients to subscribe to specific log levels or loggers
2. **Batching**: Batch multiple log messages to reduce WebSocket overhead
3. **Compression**: Compress log data for large messages
4. **Replay**: Allow new clients to request recent log history
5. **Metrics**: Track log streaming performance and errors
6. **Log Retention**: Configurable retention policies for file-based logs
