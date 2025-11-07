# Parent Instance ID Auto-Injection Guide

Complete guide to Madrox's automatic parent instance detection and mandatory enforcement system.

---

## Overview

Madrox automatically manages instance hierarchies through intelligent parent instance ID detection. This ensures proper tree-structured networks where every supervised instance (except the main orchestrator) has a parent.

**Key Benefits:**
- ✅ Eliminates manual parent ID tracking
- ✅ Ensures proper hierarchy formation (no flat networks)
- ✅ Simplifies multi-level delegation
- ✅ Detects configuration errors immediately with helpful guidance

---

## Core Concepts

### What is Parent Instance ID?

The `parent_instance_id` defines the hierarchical relationship between instances:

```
Parent (Supervisor)
  └── Child (Worker)
       └── Grandchild (Sub-worker)
```

**Benefits of Proper Hierarchy:**
- **Bidirectional Communication**: Children can reply to parents via `reply_to_caller()`
- **Cascade Operations**: Terminating parent automatically cleans up children
- **Structured Coordination**: Parent can broadcast to all children
- **Resource Tracking**: Monitor resource usage per team/subtree
- **Network Visibility**: Query hierarchy to understand team structure

### Two-Tier Auto-Detection System

Madrox uses a two-tier system to automatically determine `parent_instance_id`:

#### Tier 1: Explicit Parent (Highest Priority)

If you provide `parent_instance_id` when spawning, it's **always used**:

```python
# Explicit parent is always respected
worker = await spawn_claude(
    name="worker",
    role="developer",
    parent_instance_id="supervisor-abc123"  # ✅ Will use this
)
```

**When to use explicit parent:**
- Spawning from external API client
- Wanting specific parent (not the caller)
- Implementing custom coordination patterns
- Testing with predetermined hierarchies

#### Tier 2: Auto-Detected Caller (Automatic)

If `parent_instance_id` is omitted, Madrox **auto-detects** the calling instance:

```python
# No parent_instance_id provided
worker = await spawn_claude(
    name="worker",
    role="developer"
    # Madrox detects caller and uses as parent ✅
)
```

**When auto-detection works:**
- Spawning from within a managed instance
- Instance is executing (in "busy" state)
- Instance has recent activity history

#### Tier 3: Mandatory Enforcement (Error Handling)

If parent cannot be determined and instance is not main orchestrator:

```python
# Parent cannot be determined
worker = await spawn_claude(
    name="worker",
    role="developer"
)
# ❌ ValueError: parent_instance_id required but could not be determined
# Exception message provides clear solutions
```

**Only exception:** Main orchestrator instance named `"main-orchestrator"` is allowed `parent_instance_id=None`

---

## Auto-Detection Strategies

### Strategy 1: Busy State Detection (Primary)

**How it works:**
1. Scans all managed instances
2. Identifies instances in "busy" state (actively executing)
3. Selects most recently active busy instance
4. Uses that instance as parent

**Characteristics:**
- ✅ Most reliable detection method
- ✅ Works when supervisor actively processing
- ✅ Prevents race conditions
- ❌ Fails if supervisor not in busy state

**Example:**
```python
# Supervisor actively executing when child spawns
# Example: Supervisor processing message and calling spawn_claude
await send_to_instance(
    supervisor_id,
    """Analyze data and spawn results processor:
    spawn_claude(name="processor", role="data_analyst")
    # Supervisor in busy state → auto-detected as parent ✅
    """
)
```

### Strategy 2: Activity-Based Detection (Fallback)

**How it works:**
1. Scans all managed instances
2. Filters instances with `request_count > 0` (has history)
3. Excludes terminated instances
4. Selects most recently active instance
5. Uses that instance as parent

**Characteristics:**
- ✅ Works when supervisor not actively busy
- ✅ Detects instances with interaction history
- ❌ Less reliable than busy state
- ❌ May select wrong instance in edge cases

**Example:**
```python
# Supervisor recently active (has request history)
# But not currently in busy state
await spawn_claude(
    name="worker",
    role="developer"
)
# Most recently active instance detected as parent ✅
```

---

## Detection Decision Matrix

| Scenario | Tier 1 | Tier 2 | Result | Parent ID |
|----------|--------|--------|--------|-----------|
| **User provides explicit parent** | ✅ abc123 | - | Uses explicit | abc123 |
| **Child spawns from busy supervisor** | ❌ None | ✅ xyz789 | Uses detected | xyz789 |
| **Child spawns from inactive supervisor** | ❌ None | ✅ xyz789 | Uses detected | xyz789 |
| **External client, no parent** | ❌ None | ❌ Fails | **Error** | None (invalid) |
| **Main orchestrator spawn** | ❌ None | ❌ Can't detect | **Allowed** | None (valid) |
| **Explicit overrides auto-detect** | ✅ abc123 | ✅ xyz789 | Uses explicit | abc123 |

---

## Common Use Cases

### Use Case 1: Supervisor Spawns Team

**Scenario:** Supervisor spawns multiple worker instances

```python
# Supervisor internally spawns workers
await send_to_instance(
    supervisor_id,
    """Spawn 3 workers:
    spawn_claude(name="worker-1", role="developer")
    # Auto-detected parent: supervisor ✅

    spawn_claude(name="worker-2", role="developer")
    # Auto-detected parent: supervisor ✅

    spawn_claude(name="worker-3", role="developer")
    # Auto-detected parent: supervisor ✅
    """
)

# Result: Hierarchical structure
# supervisor
#   ├── worker-1
#   ├── worker-2
#   └── worker-3
```

**Why it works:**
- Supervisor is in "busy" state executing the message
- All spawns detected with supervisor as parent
- Auto-detection succeeds for all instances

### Use Case 2: Batch Spawning

**Scenario:** Spawn multiple instances with single call

```python
# All instances auto-detect same parent
instances = await spawn_multiple_instances([
    {"name": "analyst-1", "role": "data_analyst"},
    {"name": "analyst-2", "role": "data_analyst"},
    {"name": "analyst-3", "role": "data_analyst"}
])

# Result: All three have same auto-detected parent
# parent
#   ├── analyst-1
#   ├── analyst-2
#   └── analyst-3
```

**How auto-injection works:**
- MCP adapter detects caller instance
- Applies same parent to all instances in batch
- All instances properly linked to coordinator

### Use Case 3: Multi-Level Hierarchy

**Scenario:** Create 3-level organizational structure

```python
# Level 1: CTO spawns level 2
await send_to_instance(
    cto_id,
    """Spawn engineering lead:
    spawn_claude(name="engineering-lead", role="architect")
    # Auto-parent: cto ✅
    """
)

# Level 2: Engineering lead spawns level 3
await send_to_instance(
    engineering_lead_id,
    """Spawn 3 developers:
    spawn_claude(name="backend-dev", role="backend_developer")
    # Auto-parent: engineering-lead ✅

    spawn_claude(name="frontend-dev", role="frontend_developer")
    # Auto-parent: engineering-lead ✅
    """
)

# Result: Proper 3-level tree
# cto
# └── engineering-lead
#     ├── backend-dev
#     └── frontend-dev
```

### Use Case 4: External Client Spawn

**Scenario:** External API client spawns instance

```python
# ❌ FAILS: External client cannot auto-detect
instance = await spawn_claude(
    name="worker",
    role="developer"
)
# ValueError: parent_instance_id required but could not be determined

# ✅ WORKS: Provide explicit parent
main = await spawn_claude(name="main-orchestrator", role="general")
instance = await spawn_claude(
    name="worker",
    role="developer",
    parent_instance_id=main  # Explicit parent required
)
```

**Why external clients fail:**
- No managed instance making the call
- Caller detection can't correlate HTTP request to instance
- Must provide explicit `parent_instance_id`

### Use Case 5: Custom Coordination Pattern

**Scenario:** Spawn child with specific parent (not caller)

```python
# Create coordinator
coordinator = await spawn_claude(name="coordinator", role="architect")

# Create worker with explicit parent (not the spawning instance)
worker = await spawn_claude(
    name="worker",
    role="developer",
    parent_instance_id=coordinator  # Explicit, overrides auto-detect
)

# Result: Worker reports to coordinator, not to spawning instance
```

---

## Error Messages & Solutions

### Error: parent_instance_id required

**Full Message:**
```
ValueError: Cannot spawn instance 'worker': parent_instance_id is required but could not be determined.
This instance is not the main orchestrator and no parent was detected.

Possible causes:
  1. Spawning from external client without explicit parent_instance_id
  2. Caller instance detection failed (instance not in 'busy' state)
  3. Spawning before any managed instances exist

Solutions:
  1. Provide parent_instance_id explicitly: spawn_claude(..., parent_instance_id='abc123')
  2. Spawn from within a managed instance (auto-detection will work)
  3. First spawn the main orchestrator, then use it as parent
```

**How to fix:**

**Option 1: Provide explicit parent**
```python
main = await spawn_claude(name="main-orchestrator", role="general")
worker = await spawn_claude(
    name="worker",
    role="developer",
    parent_instance_id=main
)
```

**Option 2: Spawn from managed instance**
```python
# Supervisor spawns worker internally
await send_to_instance(
    supervisor_id,
    """Spawn a worker:
    spawn_claude(name="worker", role="developer")
    # Auto-detection works ✅
    """
)
```

**Option 3: Use main as parent**
```python
main = await spawn_claude(name="main-orchestrator", role="general")

# All children use main as parent
worker = await spawn_claude(
    name="worker",
    role="developer",
    parent_instance_id=main
)
```

---

## Troubleshooting Guide

### Symptom: Instances have wrong parent

**Possible Causes:**
1. Explicit parent provided but wrong
2. Auto-detection selected wrong instance
3. Multiple managers creating same instance name

**Debug Steps:**
```python
# Check instance hierarchy
tree = manager.get_instance_tree()
print(tree)

# Check specific parent-child relationship
children = manager.get_children(parent_id)
print(f"Parent {parent_id} has {len(children)} children")

# Check instance details
status = manager.get_instance_status(instance_id)
print(f"Instance parent_id: {status.get('parent_id')}")
```

**Fix:**
```python
# Terminate and respawn with correct parent
await manager.terminate_instance(wrong_instance_id)
await manager.spawn_instance(
    name="correct-instance",
    role="developer",
    parent_instance_id=correct_parent_id
)
```

### Symptom: Batch spawn creates flat structure

**Possible Causes:**
1. Auto-detection failed for batch
2. Each instance got different parent
3. No caller detected for batch operation

**Debug Steps:**
```python
# Check each instance's parent
for instance_id in instance_ids:
    status = manager.get_instance_status(instance_id)
    print(f"{status['name']}: parent={status.get('parent_id')}")

# Check network topology
tree = manager.get_instance_tree()
```

**Fix:**
```python
# Spawn with explicit parent for all
instances = await spawn_multiple_instances([
    {
        "name": "worker-1",
        "role": "developer",
        "parent_instance_id": supervisor_id  # Explicit for all
    },
    {
        "name": "worker-2",
        "role": "developer",
        "parent_instance_id": supervisor_id  # Explicit for all
    }
])
```

### Symptom: Auto-detection doesn't work

**Possible Causes:**
1. Spawning from external client (no managed instance calling)
2. Supervisor not in "busy" state when child spawns
3. Supervisor has no request history

**Debug Steps:**
```python
# Check instance state
status = manager.get_instance_status(supervisor_id)
print(f"State: {status['state']}")  # Should be 'busy' for detection
print(f"Requests: {status['request_count']}")  # Should be > 0 for fallback
```

**Fix:**
```python
# Option 1: Spawn from message handler (supervisor will be busy)
await send_to_instance(
    supervisor_id,
    "spawn_claude(name='worker', role='developer')"  # Auto-detect works ✅
)

# Option 2: Provide explicit parent
await spawn_claude(
    name="worker",
    role="developer",
    parent_instance_id=supervisor_id  # Explicit ✅
)
```

---

## Implementation Details

### Where Auto-Detection Happens

**Location 1: MCP Adapter** (`src/orchestrator/mcp_adapter.py:258-349`)
- Detects caller instance from HTTP/MCP transport
- Injects parent_instance_id before passing to InstanceManager
- Handles auto-detection for both single and batch spawns

**Location 2: Instance Manager** (`src/orchestrator/instance_manager.py:570-591`)
- Validates parent_instance_id requirement
- Raises exception if parent cannot be determined (non-main-orchestrator)
- Logs final parent assignment for audit trail

### Detection Logic Flow

```
spawn_claude(name="worker")
    ↓
MCP Adapter: detect_caller_instance()
    ├─ Strategy 1: Find busy instances → Found supervisor ✅
    │   └─ parent_instance_id = supervisor
    │
    └─ Strategy 2: Find recently active → Use most recent ✅
        └─ parent_instance_id = supervisor

InstanceManager: spawn_instance()
    ├─ Check: parent_instance_id provided or detected? ✅
    ├─ Check: Is main orchestrator? ❌
    └─ Create instance with parent_instance_id
        └─ Instance properly linked to parent ✅
```

### Auto-Detection Timing

**When detection happens:**
1. **Tier 1 check**: When spawn_claude is called (explicit parent check)
2. **Tier 2 detection**: When request reaches MCP adapter (caller detection)
3. **Tier 3 validation**: When InstanceManager creates instance (enforcement)

**Critical: Detection happens at request time, not at instance creation time**

This means:
- ✅ Supervisor must be calling spawn at request time
- ✅ Caller state examined when MCP request arrives
- ❌ Background tasks cannot rely on auto-detection (not in "busy" state)

---

## Best Practices

### DO: Spawn from Message Handlers

✅ **Good**: Auto-detection works
```python
# Supervisor receives message and spawns
await send_to_instance(
    supervisor_id,
    """Spawn workers:
    spawn_claude(name="worker-1", role="developer")  # Auto-detected ✅
    spawn_claude(name="worker-2", role="developer")  # Auto-detected ✅
    """
)
```

### DO: Provide Explicit Parent for External Clients

✅ **Good**: Explicit parent always works
```python
main = await spawn_claude(name="main-orchestrator", role="general")

# External client spawning
worker = await spawn_claude(
    name="worker",
    role="developer",
    parent_instance_id=main  # Explicit ✅
)
```

### DO: Use Batch Spawning with Auto-Detection

✅ **Good**: All instances get same parent
```python
# Supervisor spawns batch (auto-detection applies to all)
instances = await spawn_multiple_instances([
    {"name": "worker-1", "role": "developer"},  # Auto-parent: supervisor
    {"name": "worker-2", "role": "developer"},  # Auto-parent: supervisor
    {"name": "worker-3", "role": "developer"},  # Auto-parent: supervisor
])
```

### DON'T: Rely on Auto-Detection from Background Tasks

❌ **Bad**: Auto-detection won't work
```python
# Background task spawning child (not in busy state)
async def background_task():
    await spawn_claude(name="worker", role="developer")
    # ❌ Auto-detection fails (not in busy state)

asyncio.create_task(background_task())  # Runs in background
```

❌ **Good**: Provide explicit parent
```python
async def background_task(parent_id):
    await spawn_claude(
        name="worker",
        role="developer",
        parent_instance_id=parent_id  # Explicit ✅
    )

asyncio.create_task(background_task(supervisor_id))
```

### DON'T: Create Flat Hierarchies

❌ **Bad**: All children of main
```python
# All instances end up with main as parent (flat)
main = await spawn_claude(name="main-orchestrator")
for i in range(10):
    await spawn_claude(f"worker-{i}", parent_instance_id=main)
# Result: Flat structure with 10 children of main
```

✅ **Good**: Hierarchical structure
```python
main = await spawn_claude(name="main-orchestrator")
supervisor = await spawn_claude(
    name="supervisor",
    parent_instance_id=main
)

# Supervisor spawns its own workers (auto-detected)
for i in range(10):
    await send_to_instance(
        supervisor_id,
        f"spawn_claude(name='worker-{i}', role='developer')"
    )
# Result: Proper hierarchy (main → supervisor → 10 workers)
```

---

## FAQ

### Q: Why is parent_instance_id mandatory?

**A:** Mandatory parent ID ensures:
1. **Proper Hierarchy**: Prevents flat networks (bug that prompted this feature)
2. **Clear Relationships**: Every supervised instance knows its parent
3. **Cascade Operations**: Terminating parent cleans up all children
4. **Bidirectional Communication**: Children can reply to parents

Without mandatory parents, supervisors couldn't reliably coordinate or communicate with workers.

### Q: Can I have instances without parents?

**A:** Only the main orchestrator can have no parent:
```python
# ✅ Allowed
main = await spawn_claude(name="main-orchestrator", role="general")

# ❌ Not allowed
orphan = await spawn_claude(name="orphan", role="developer")
# ValueError: parent_instance_id required
```

All other instances must have a parent.

### Q: How do I get auto-detection to work?

**A:** Auto-detection works when:
1. Spawning from within a managed instance
2. Instance is making the call (busy state or recent activity)
3. Not spawning from external API client

**To ensure auto-detection:**
```python
# Spawn from inside supervisor's message handler
await send_to_instance(
    supervisor_id,
    "spawn_claude(name='worker', role='developer')"  # Auto-detect ✅
)
```

### Q: What if I want different parent than caller?

**A:** Provide explicit parent:
```python
supervisor = await spawn_claude(name="supervisor", role="architect")
coordinator = await spawn_claude(name="coordinator", role="architect")

# Spawn worker with coordinator as parent (not supervisor)
worker = await spawn_claude(
    name="worker",
    role="developer",
    parent_instance_id=coordinator  # Explicit parent ✅
)
```

### Q: How do I query the hierarchy?

**A:** Use instance management tools:
```python
# Get network tree
tree = manager.get_instance_tree()
print(tree)

# Get children of specific parent
children = manager.get_children(parent_id)
print(f"Parent has {len(children)} children")

# Get specific instance status
status = manager.get_instance_status(instance_id)
print(f"Parent: {status['parent_id']}")
```

---

## Summary

| Aspect | Details |
|--------|---------|
| **Tier 1** | Explicit `parent_instance_id` if provided |
| **Tier 2** | Auto-detected caller if omitted |
| **Tier 3** | Error if detection fails (except main-orchestrator) |
| **Strategies** | Busy state (primary) + Activity (fallback) |
| **Exception** | Main orchestrator allowed `parent_instance_id=None` |
| **When it works** | Spawning from managed instances |
| **When it fails** | External clients without explicit parent |

**Key Takeaway:** Madrox ensures proper hierarchical structure by automatically determining parent IDs, with immediate error reporting if determination fails. This eliminates flat hierarchies and ensures all supervised instances are properly linked to their coordinators.

---

## See Also

- [API Reference - spawn_claude](API_REFERENCE.md#spawn_claude) - spawn_claude parameters and examples
- [Features Guide](FEATURES.md#automatic-parent-instance-detection) - Parent detection overview
- [Design Document](DESIGN.md) - System architecture and design
