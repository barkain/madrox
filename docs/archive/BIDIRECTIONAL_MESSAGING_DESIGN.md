# Bidirectional Messaging Protocol Design

## Problem Statement

Current Madrox communication is unidirectional:
- Instances receive messages via `send_to_instance()`
- Instances output to their own pane
- Coordinator must poll panes to get responses
- No explicit request-response correlation

## Design Philosophy: Lightweight & Zero Dependencies

**Core Principles:**
- **In-memory only**: Use `asyncio.Queue` for runtime message routing
- **No database**: No SQLAlchemy, no persistent storage
- **Minimal deps**: Standard library only (asyncio, uuid, datetime)
- **Ephemeral**: Message tracking lives only during server runtime
- **Fast**: Direct queue operations, no DB round-trips

**Comparison to Hephaestus:**

| Aspect | Hephaestus | Madrox |
|--------|------------|--------|
| Storage | PostgreSQL/SQLite | In-memory dict/Queue |
| Persistence | Survives restarts | Runtime only |
| Dependencies | SQLAlchemy, Alembic | Standard library |
| Audit trail | Full historical log | Current session only |
| Use case | Long-running workflows | Ephemeral orchestration |

## Proposed Solution

Implement lightweight bidirectional messaging using asyncio primitives:

### 1. Message Response Tool

Add MCP tool `reply_to_caller` for instances to explicitly respond back:

```python
{
    "name": "reply_to_caller",
    "description": "Reply back to the instance/coordinator that sent you a message",
    "input_schema": {
        "type": "object",
        "properties": {
            "reply_message": {"type": "string", "description": "Your reply content"},
            "correlation_id": {"type": "string", "description": "Message ID from the incoming message"},
            "instance_id": {"type": "string", "description": "Your instance ID"}
        },
        "required": ["reply_message", "instance_id"]
    }
}
```

### 2. In-Memory Message Queue System

Implement per-instance message queues using stdlib asyncio:

```python
# Standard library only - no dependencies
import asyncio
from datetime import datetime
from uuid import uuid4

class TmuxInstanceManager:
    def __init__(self, ...):
        # Response queues: instance_id -> asyncio.Queue of replies
        self.response_queues: dict[str, asyncio.Queue] = {}

        # Message registry: message_id -> MessageEnvelope
        self.message_registry: dict[str, MessageEnvelope] = {}
```

### 3. Enhanced send_message Flow

```
1. Coordinator sends message with unique message_id
2. Message delivered to instance pane (existing)
3. Instance uses send_response() tool to reply
4. Response queued in coordinator's response_queue
5. send_to_instance() returns response (or times out)
```

### 4. Implementation Components

#### A. Message ID Generation
```python
import uuid
from datetime import datetime

def generate_message_id(sender_id: str) -> str:
    timestamp = datetime.now().isoformat()
    unique_id = uuid.uuid4().hex[:8]
    return f"{sender_id[:8]}_{timestamp}_{unique_id}"
```

#### B. Response Queue Management
```python
async def send_message(
    self,
    instance_id: str,
    message: str,
    wait_for_response: bool = True,
    timeout_seconds: int = 30,
) -> dict[str, Any] | None:
    # Generate message ID
    message_id = generate_message_id("coordinator")

    # Create response queue if needed
    if instance_id not in self.response_queues:
        self.response_queues[instance_id] = asyncio.Queue()

    # Track message
    self.message_tracking[message_id] = {
        "sender_id": "coordinator",
        "recipient_id": instance_id,
        "timestamp": datetime.now(),
        "status": "sent"
    }

    # Format and send message with ID
    formatted_message = f"[MSG:{message_id}] {message}"
    # ... send to pane ...

    if not wait_for_response:
        return {"status": "sent", "message_id": message_id}

    # Wait for response
    try:
        response = await asyncio.wait_for(
            self.response_queues[instance_id].get(),
            timeout=timeout_seconds
        )
        return response
    except asyncio.TimeoutError:
        return {"status": "timeout", "message_id": message_id}
```

#### C. Response Handling (New MCP Tool)
```python
async def handle_send_response(
    self,
    instance_id: str,
    message: str,
    in_response_to: str | None = None,
):
    """Handle send_response tool call from instance."""

    # Find parent instance or coordinator
    instance = self.instances.get(instance_id)
    parent_id = instance.get("parent_instance_id") if instance else None

    # Queue response
    if parent_id and parent_id in self.response_queues:
        await self.response_queues[parent_id].put({
            "sender_id": instance_id,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "in_response_to": in_response_to
        })

    # Update message tracking
    if in_response_to and in_response_to in self.message_tracking:
        self.message_tracking[in_response_to]["status"] = "responded"

    # Log communication
    self.logging_manager.log_communication(
        instance_id=instance_id,
        direction="outbound",
        message_type="response",
        content=message[:200],
        parent_id=parent_id
    )

    return {"status": "delivered", "to": parent_id}
```

### 5. Backward Compatibility

Maintain existing polling behavior as fallback:
- If instance doesn't use `send_response()`, fall back to pane polling
- Gradual migration: instances can opt into bidirectional messaging
- Main instance gets special handling for orchestration

### 6. Main Instance Communication

Special case for main orchestrator instance:
```python
# Main instance can receive responses from children
# and send messages to children bidirectionally

async def ensure_main_instance(self):
    # ... existing code ...

    # Initialize response queue for main instance
    self.response_queues[self.main_instance_id] = asyncio.Queue()

    # Main instance prompt includes send_response tool
    system_prompt = """
    You are the main orchestrator instance.

    When child instances message you:
    - They will send messages using send_message tool
    - You will receive them in your pane with [MSG:id] prefix
    - You can respond using send_response tool

    Example:
    Child: [MSG:abc123] I need help with X
    You: Use send_response(message="Here's help", in_response_to="abc123", instance_id="{self.main_instance_id}")
    """
```

### 7. Testing Strategy

1. **Unit Tests**: Test message queue operations
2. **Integration Tests**: Test coordinator <-> instance bidirectional flow
3. **E2E Tests**: Test main instance <-> child <-> coordinator chains
4. **Compatibility Tests**: Ensure fallback polling still works

## Migration Path

1. ✅ Implement response queues and message tracking
2. ✅ Add `send_response` MCP tool
3. ✅ Update `send_message` to support wait_for_response
4. ✅ Update instance prompts to use `send_response`
5. ✅ Test bidirectional flow
6. ✅ Document new pattern
7. ⏳ Gradual rollout with feature flag
