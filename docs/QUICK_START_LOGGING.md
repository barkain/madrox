# Quick Start: Backend Logging Infrastructure

## TL;DR

The backend logging infrastructure streams logs in real-time to WebSocket clients. System logs and audit logs are automatically categorized and sent via `/ws/monitor`.

## For Backend Developers

### Log a System Event

```python
import logging

logger = logging.getLogger("madrox.your_module")
logger.info("Something happened", extra={"instance_id": "abc123"})
```

→ Appears in **System Logs Panel**

### Log an Audit Event

```python
from src.orchestrator import audit_log
import logging

logger = logging.getLogger("audit.your_module")
audit_log(
    logger,
    "User performed action",
    action="action_type",
    metadata={"key": "value"}
)
```

→ Appears in **Audit Logs Panel**

## For Frontend Developers

### Connect to WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/monitor');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'system_log') {
    // Display in system panel
    console.log('System:', msg.data.message);
  }
  else if (msg.type === 'audit_log') {
    // Display in audit panel
    console.log('Audit:', msg.data.message, msg.data.action);
  }
};
```

### Message Format

**System Log**:
```json
{
  "type": "system_log",
  "data": {
    "timestamp": "2025-10-08T18:30:45.123Z",
    "level": "INFO",
    "logger": "madrox.server",
    "message": "Instance spawned",
    "module": "server",
    "function": "spawn_instance",
    "line": 142
  }
}
```

**Audit Log**:
```json
{
  "type": "audit_log",
  "data": {
    "timestamp": "2025-10-08T18:30:45.123Z",
    "level": "INFO",
    "logger": "audit.instance",
    "message": "Instance spawned",
    "action": "instance_spawn",
    "metadata": {
      "instance_id": "abc123"
    }
  }
}
```

## Testing

```bash
# Run tests
pytest tests/test_log_streaming.py -v

# Run demo
python examples/demo_log_streaming.py
```

## Common Actions (Audit Logs)

Use these standard action names:

- `instance_spawn` - Instance created
- `instance_terminate` - Instance stopped
- `message_sent` - Message sent to instance
- `message_received` - Response received
- `state_change` - State transition
- `coordination_start` - Coordination began
- `coordination_complete` - Coordination finished
- `error` - Error occurred
- `timeout` - Operation timed out

## Architecture

```
┌─────────────────┐
│  Python Logger  │
└────────┬────────┘
         │
         v
┌─────────────────────┐
│ LogStreamHandler    │  ← Categorizes logs
└────────┬────────────┘
         │
         v
┌─────────────────────┐
│  WebSocket Clients  │  ← Receives formatted messages
└─────────────────────┘
         │
         v
┌─────────────────────┐
│  Frontend Panels    │  ← Displays in UI
└─────────────────────┘
```

## Files

- **Handler**: `src/orchestrator/log_stream_handler.py`
- **Tests**: `tests/test_log_streaming.py`
- **Demo**: `examples/demo_log_streaming.py`
- **Docs**: `docs/log-streaming.md`

## Need More Info?

See `docs/log-streaming.md` for comprehensive documentation.
