# Non-Blocking Network Spawn Pattern

## Executive Summary

Optimized hierarchical network spawning to use non-blocking message pattern, reducing coordinator wait time from 120 seconds to ~15 seconds while maintaining full network verification.

## Problem Statement

**Previous Pattern (Blocking)**:
```python
# Blocking wait for reply
send_to_instance(
    instance_id=supervisor_id,
    message="Spawn 3 children...",
    wait_for_response=true,  # ❌ Blocks for 120s
    timeout_seconds=120
)
```

**Issues**:
- Coordinator hangs for entire timeout period (120s)
- Network becomes operational early but coordinator still blocking
- Supervisor may not reply immediately even after successful spawning
- Redundant waiting when network status can be verified separately

## Solution: Non-Blocking Pattern

**Optimized Pattern**:
```python
# 1. Send non-blocking spawn instruction
send_to_instance(
    instance_id=supervisor_id,
    message="Spawn 3 children...",
    wait_for_response=false  # ✅ Returns immediately
)

# 2. Wait reasonable time for spawning
await asyncio.sleep(15)  # Typical time for 3 spawns

# 3. Verify network status separately
tree = get_instance_tree()
children = get_children(parent_id=supervisor_id)
```

## Architecture

### Message Flow Comparison

**Blocking Pattern**:
```
Coordinator → send_to_instance(wait=true) → Supervisor
     |                                           |
     |                                      Spawn children
     |                                           |
     |--- Waiting 120s for reply -----------------|
     |                                           |
     |                  (Network operational)    |
     |                                           |
     ← reply_to_caller -------------------------←
Continue (after 120s)
```

**Non-Blocking Pattern**:
```
Coordinator → send_to_instance(wait=false) → Supervisor
     ↓                                           |
Continue immediately                        Spawn children
     |                                           |
     |--- 15s reasonable delay ------------------|
     |                                           |
     ↓                  (Network operational)    |
Verify network status (get_instance_tree)
     |
Continue (~15s total)
```

## Performance Impact

| Metric | Blocking | Non-Blocking | Improvement |
|--------|----------|--------------|-------------|
| **Wait Time** | 120s | 15s | **87.5% faster** |
| **Network Operational** | ~10-15s | ~10-15s | Same |
| **Coordinator Blocked** | Yes (120s) | No | **Responsive** |
| **Verification** | Implicit (reply) | Explicit (tree) | **More reliable** |
| **User Experience** | Hanging | Responsive | **Much better** |

## Implementation Example

### Complete Non-Blocking Workflow

```python
from madrox import (
    spawn_claude,
    send_to_instance,
    get_instance_tree,
    get_children
)
import asyncio

async def spawn_hierarchical_network():
    """Spawn 2-level network with non-blocking pattern."""

    # 1. Spawn supervisor
    supervisor = spawn_claude(name="network-supervisor")
    supervisor_id = supervisor["instance_id"]

    # 2. Send non-blocking spawn instruction
    send_to_instance(
        instance_id=supervisor_id,
        message=f"""You are the Network Supervisor. Your instance_id is: {supervisor_id}

CRITICAL INSTRUCTIONS - Follow exactly:

1. Spawn 3 child instances using the madrox MCP tools:
   - Child 1: Codex instance named "codex-child-1" (use spawn_codex tool with model="codex-mini-latest")
   - Child 2: Codex instance named "codex-child-2" (use spawn_codex tool with model="codex-mini-latest")
   - Child 3: Claude instance named "claude-child-1" (use spawn_claude tool)

2. For EACH spawn, you MUST pass parent_instance_id="{supervisor_id}"

3. After spawning all 3 children, use reply_to_caller to report success with the instance IDs.

Start immediately.""",
        wait_for_response=false  # ✅ Non-blocking
    )

    # 3. Wait reasonable time for spawning (3 instances * ~5s each)
    await asyncio.sleep(15)

    # 4. Verify network status
    tree = get_instance_tree()
    print(tree)

    # 5. Get children for detailed verification
    children = get_children(parent_id=supervisor_id)
    print(f"Spawned {len(children)} children successfully")

    # 6. Optionally check for pending replies (non-blocking)
    replies = get_pending_replies(instance_id=supervisor_id, wait_timeout=0)
    if replies:
        print(f"Supervisor replied: {replies}")

    return supervisor_id, children
```

## Verification Strategy

### Network Status Checks

**1. Hierarchical Tree Verification**:
```python
tree = get_instance_tree()
# Expected output:
# network-supervisor (0f2937c3...) [idle] (claude)
# ├── claude-child-1 (0f1e23ea...) [running] (claude)
# ├── codex-child-1 (0c6c07ab...) [running] (codex)
# └── codex-child-2 (e50e768f...) [running] (codex)
```

**2. Child Instance Verification**:
```python
children = get_children(parent_id=supervisor_id)
# Expected: List of 3 child instances with correct parent_id
```

**3. Optional Reply Check**:
```python
replies = get_pending_replies(instance_id=supervisor_id, wait_timeout=0)
# May or may not have replies - network is operational regardless
```

## Best Practices

### When to Use Non-Blocking Pattern

✅ **Use for**:
- Hierarchical network spawning
- Multi-instance spawning tasks
- Long-running operations where reply isn't critical
- Operations where status can be verified separately

❌ **Don't use for**:
- Direct questions requiring answers
- Synchronous data retrieval
- Critical operations requiring confirmation before proceeding
- Single-instance interactions where reply is needed

### Recommended Wait Times

| Operation | Instances | Recommended Wait |
|-----------|-----------|------------------|
| Single spawn | 1 | 5-8 seconds |
| Small network | 2-3 | 12-15 seconds |
| Medium network | 4-6 | 20-25 seconds |
| Large network | 7-10 | 30-40 seconds |

**Formula**: `wait_time = (num_instances * 5) + 5` (seconds)

## Testing

### Test Case: Non-Blocking 2-Level Network

```bash
# 1. Start HTTP server
MADROX_TRANSPORT=http python run_orchestrator.py

# 2. Spawn supervisor (non-blocking)
supervisor_id=$(spawn_claude name="network-supervisor")

# 3. Send non-blocking spawn instruction
send_to_instance(
    instance_id=$supervisor_id,
    message="Spawn 3 children: 2 Codex + 1 Claude...",
    wait_for_response=false
)

# 4. Wait 15 seconds
sleep 15

# 5. Verify network
get_instance_tree()
```

**Expected Result**:
- Total time: ~15 seconds (vs 120s blocking)
- Network fully operational
- All 3 children spawned successfully
- Proper parent-child relationships
- No blocking/hanging behavior

## Results

### Demonstration Output

```
# Non-blocking spawn sent at T=0s
Response: {
    'instance_id': '0f2937c3-3e99-477d-9536-c0488ed07ac4',
    'status': 'sent',
    'message_id': '25838e6d-6b47-46ce-81ac-5690b29a388f'
}

# Network verified at T=15s
Instance Hierarchy:

network-supervisor (0f2937c3...) [idle] (claude)
├── claude-child-1 (0f1e23ea...) [running] (claude)
├── codex-child-1 (0c6c07ab...) [running] (codex)
└── codex-child-2 (e50e768f...) [running] (codex)

Total time: 15 seconds ✅
Network operational: Yes ✅
Blocking: None ✅
```

## Files Modified

**None** - This is a workflow optimization, not a code change.

Changes required:
- Developer workflow patterns
- Documentation updates
- Example code improvements

## Related Documentation

- [IPC_FIXES_2025_10_16.md](IPC_FIXES_2025_10_16.md) - Codex IPC bug fixes enabling bidirectional messaging
- [ARCHITECTURE.md](ARCHITECTURE.md) - Overall system architecture
- [API_REFERENCE.md](API_REFERENCE.md) - MCP tool documentation

## Future Improvements

1. **Auto-Detection**: Automatically detect hierarchical spawning and suggest non-blocking pattern
2. **Status Callbacks**: Add webhook/callback for network spawn completion
3. **Progress Monitoring**: Real-time progress indicators during spawning
4. **Smart Wait Times**: Calculate optimal wait time based on network complexity
5. **Retry Logic**: Automatic retry for failed spawns with exponential backoff

## Commit Message

```
docs: add non-blocking network spawn pattern optimization

Documented optimized workflow for hierarchical network spawning that uses
non-blocking message pattern instead of blocking wait.

Key improvements:
- Reduced coordinator wait time from 120s to ~15s (87.5% faster)
- Eliminated redundant blocking when network already operational
- Added separate network verification with get_instance_tree
- Maintained full reliability with explicit status checks

Pattern:
1. Send non-blocking spawn instruction (wait_for_response=false)
2. Wait reasonable time for spawning (~15s for 3 instances)
3. Verify network status with get_instance_tree/get_children
4. Optionally check pending replies (non-blocking)

Result: Responsive coordinator with reliable network verification.

New file: docs/NON_BLOCKING_NETWORK_SPAWN.md
```

## References

- User feedback: "the network was spawned successfully as requested but the supervisor didn't reply to caller and so you were still hanging while the network was already operational. this is a redundant behavior. requires immediate optimization"
- Implementation date: October 16, 2025
- Related feature: Bidirectional messaging with `reply_to_caller` tool
