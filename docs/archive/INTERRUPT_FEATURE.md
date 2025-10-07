# Interrupt Instance Feature

## Overview

The `interrupt_instance` MCP tool allows you to send an interrupt signal (Ctrl+C / Escape) to a running Madrox instance to stop its current task **without terminating the instance**.

This is similar to pressing Escape or Ctrl+C in Claude Code - it stops the current operation but keeps the session alive and ready for new commands.

---

## Use Cases

| Scenario | Before | After |
|----------|--------|-------|
| **Long-running task** | Had to terminate instance and lose all context | Stop task, keep context, send new message |
| **Wrong direction** | Wait for completion or kill instance | Interrupt and redirect immediately |
| **Stuck process** | Force terminate losing all state | Gentle interrupt preserving state |
| **Cost control** | Watch tokens accumulate helplessly | Stop expensive operation mid-flight |

---

## API Reference

### MCP Tool: `interrupt_instance`

**Description:** Send interrupt signal (Ctrl+C / Escape) to stop current task without terminating the instance

**Parameters:**
```json
{
  "instance_id": "abc123-def456-..."  // Required: Instance ID to interrupt
}
```

**Returns:**
```json
{
  "success": true,
  "instance_id": "abc123-def456-...",
  "message": "Interrupt signal sent successfully",
  "timestamp": "2025-10-01T..."
}
```

**Error Response:**
```json
{
  "success": false,
  "instance_id": "abc123-def456-...",
  "error": "Instance is terminated, cannot interrupt",
  "timestamp": "2025-10-01T..."
}
```

---

### MCP Tool: `interrupt_multiple_instances`

**Description:** Send interrupt signal to multiple instances in parallel

**Parameters:**
```json
{
  "instance_ids": ["abc123", "def456", "ghi789"]  // Required: Array of instance IDs
}
```

**Returns:**
```json
{
  "content": [{
    "type": "text",
    "text": "⏸️ Interrupted 3/3 instances successfully:\n  - abc123\n  - def456\n  - ghi789"
  }]
}
```

**Partial Success Response:**
```json
{
  "content": [{
    "type": "text",
    "text": "⏸️ Interrupted 2/3 instances successfully:\n  - abc123\n  - def456\n\n❌ Errors (1):\n  - ghi789: Instance is terminated, cannot interrupt"
  }]
}
```

---

## Usage Examples

### Example 1: Stop Long-Running Analysis

```python
# Spawn instance
result = spawn_claude(name="analyst", role="data_analyst")
instance_id = result["id"]

# Send task that takes too long
send_to_instance(
    instance_id=instance_id,
    message="Analyze this 10GB dataset in detail...",
    wait_for_response=False  # Don't wait
)

# Oh no, this will take forever! Interrupt it
interrupt_instance(instance_id=instance_id)

# Send a better task
send_to_instance(
    instance_id=instance_id,
    message="Just give me a summary of the first 1000 rows"
)
```

### Example 2: Redirect Instance Mid-Task

```python
# Instance is working on wrong task
send_to_instance(
    instance_id=worker_id,
    message="Write comprehensive documentation for all 500 functions...",
    wait_for_response=False
)

# Realize this isn't what you wanted
interrupt_instance(instance_id=worker_id)

# Give correct task
send_to_instance(
    instance_id=worker_id,
    message="Only document the 5 public API functions"
)
```

### Example 3: Emergency Stop for Cost Control

```python
# Instance is making too many expensive API calls
for instance in expensive_instances:
    interrupt_instance(instance_id=instance["id"])
    # Instance stops but remains available
```

### Example 4: Batch Interrupt (Parallel)

```python
# Stop all worker instances at once
worker_ids = ["worker-1", "worker-2", "worker-3", "worker-4"]

# Send interrupt to all in parallel (faster than sequential)
result = interrupt_multiple_instances(instance_ids=worker_ids)

# Result shows:
# ⏸️ Interrupted 4/4 instances successfully:
#   - worker-1
#   - worker-2
#   - worker-3
#   - worker-4
```

### Example 5: Emergency "Stop All" Button

```python
# User hits emergency stop - halt everything!
status = get_instance_status()
all_busy_instances = [
    inst_id
    for inst_id, inst in status["instances"].items()
    if inst["state"] == "busy"
]

# Stop them all immediately
interrupt_multiple_instances(instance_ids=all_busy_instances)

# All instances now idle and ready for new instructions
```

---

## Comparison with Other Control Methods

| Method | Instance State After | Context Preserved | Parallel Support | Use Case |
|--------|---------------------|-------------------|------------------|----------|
| `interrupt_instance()` | ✅ Running (idle) | ✅ Yes | ❌ Single only | Stop one task |
| `interrupt_multiple_instances()` | ✅ Running (idle) | ✅ Yes | ✅ Parallel | Stop many tasks |
| `terminate_instance()` | ❌ Terminated | ❌ No | ❌ Single only | Kill one instance |
| `terminate_multiple_instances()` | ❌ Terminated | ❌ No | ✅ Parallel | Kill many instances |
| `send_to_instance()` | ✅ Running (busy) | ✅ Yes | ❌ Single only | Send message |
| `send_to_multiple_instances()` | ✅ Running (busy) | ✅ Yes | ✅ Parallel | Broadcast message |
| Timeout | ⏱️ Varies | ✅ Yes | N/A | Automatic safety |

---

## Implementation Details

### How It Works

1. **Locate tmux session** for the instance
2. **Send Ctrl+C** signal via `tmux send-keys`
3. **Update state** to `idle`
4. **Instance ready** for next message

### Technical Flow

```
┌─────────────────┐
│ Busy Instance   │  Running task...
└────────┬────────┘
         │
         │ interrupt_instance(id)
         ↓
    ┌─────────┐
    │ Send    │
    │ Ctrl+C  │ → tmux send-keys C-c
    └────┬────┘
         │
         ↓
┌─────────────────┐
│ Idle Instance   │  Ready for new message
└─────────────────┘
```

### State Transitions

```
Running/Busy → [interrupt] → Idle
Idle         → [interrupt] → Idle (no-op)
Terminated   → [interrupt] → Error
```

---

## Error Handling

**Instance not found:**
```
ValueError: Instance abc123 not found
```

**Instance terminated:**
```json
{
  "success": false,
  "error": "Instance is terminated, cannot interrupt"
}
```

**No tmux session:**
```json
{
  "success": false,
  "error": "No tmux session found for instance abc123"
}
```

---

## Best Practices

### ✅ Do

- Interrupt instances that are taking too long
- Use for cost control on expensive operations
- Interrupt when you realize the task is wrong
- Keep instances alive for context preservation

### ❌ Don't

- Interrupt idle instances (unnecessary)
- Use as replacement for proper timeout values
- Spam interrupt signals rapidly
- Expect instant response (may take 1-2 seconds)

---

## Keyboard Shortcuts (Future Enhancement)

**Proposed:** Add keyboard shortcut in Claude Code interface
- `Cmd+Shift+Esc` - Interrupt current Madrox instance
- `Ctrl+C` - Interrupt focused instance

---

## Changelog

**Version 1.0.0** (2025-10-01)
- ✅ Initial implementation
- ✅ Single instance interrupt (`interrupt_instance`)
- ✅ Batch interrupt support (`interrupt_multiple_instances`)
- ✅ Parallel execution for batch operations
- ✅ MCP tool registration (both tools)
- ✅ tmux signal handling
- ✅ State management
- ✅ Comprehensive error handling
- ✅ Full documentation with examples

---

## Related Features

- [`send_to_instance`](./API.md#send_to_instance) - Send messages
- [`terminate_instance`](./API.md#terminate_instance) - Kill instances
- [`get_instance_status`](./API.md#get_instance_status) - Check state

---

*Requested by: User feedback for Escape key functionality*
*Implemented: 2025-10-01*
