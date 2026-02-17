# Instance ID Confusion Fix - October 16, 2025

## Executive Summary

Fixed bug where child instances incorrectly called `get_main_instance_id()` tool, causing unwanted "main-orchestrator" instances to auto-spawn. Root cause was unclear system prompt instructions combined with auto-spawning behavior in the tool implementation. Solution: deprecated the problematic tool and enhanced system prompts with explicit warnings.

## Problem Statement

During counting game demonstration with hierarchical network (supervisor + 3 children), an unwanted "main-orchestrator" instance appeared in the network tree:

```
network-supervisor (0f2937c3...) [idle] (claude)
├── main-orchestrator (38d0616e...) [idle] (claude)  # ❌ Unwanted!
├── claude-child-1 (0f1e23ea...) [running] (claude)
├── codex-child-1 (0c6c07ab...) [running] (codex)
└── codex-child-2 (e50e768f...) [running] (codex)
```

**User Feedback**: "who spawned the extra supervisor?"

## Root Causes Identified

### Issue #1: get_main_instance_id Tool Auto-Spawning
**Location**: `src/orchestrator/mcp_adapter.py:1122-1132` (original)

**Problem**: The tool implementation called `ensure_main_instance()` which auto-spawned a "main-orchestrator" instance if it didn't exist.

```python
# OLD CODE - Auto-spawning behavior
elif tool_name == "get_main_instance_id":
    # Ensure main instance is spawned
    main_id = await self.manager.ensure_main_instance()  # ❌ AUTO-SPAWNS!
    result = {
        "content": [{
            "type": "text",
            "text": f"Main instance ID: {main_id}\n\n..."
        }]
    }
```

**Why It Was Called**: claude-child-1 incorrectly thought it needed the "main instance ID" to use in `reply_to_caller`, when it should have used its own instance_id.

### Issue #2: Unclear System Prompt
**Location**: `src/orchestrator/tmux_instance_manager.py:1368-1373` (original)

**Problem**: System prompt didn't explicitly warn against calling `get_main_instance_id()` or clarify the difference between "main instance ID" and "your own instance_id".

```python
# OLD CODE - Insufficient warning
f"IMPORTANT: Always use your own instance_id ('{instance['id']}') when calling reply_to_caller.\n"
f"Do NOT use the correlation_id as the instance_id parameter.\n\n"
```

**Missing Clarity**:
- No mention of `get_main_instance_id()` being deprecated
- No explicit example showing correct usage
- No warning about using other instances' IDs

## Investigation Process

### Step 1: Identify Unwanted Instance
```bash
# Instance tree showed unwanted main-orchestrator
get_instance_tree()
# Output: main-orchestrator (38d0616e...) present

# Check instance status
get_instance_status(instance_id="38d0616e...")
# Created: 2025-10-16T18:19:29 (during counting game)
```

### Step 2: Trace Tool Call
```bash
# Examine claude-child-1 tmux output
get_tmux_pane_content(instance_id="claude-child-1")
# Found: Called get_main_instance_id() tool
# Found: Used returned ID in reply_to_caller (incorrect!)
```

### Step 3: Root Cause Analysis
```python
# Traced through code:
# 1. claude-child-1 called get_main_instance_id()
# 2. Tool called ensure_main_instance()
# 3. ensure_main_instance() spawned "main-orchestrator"
# 4. claude-child-1 used wrong ID in reply_to_caller
```

## Solutions Implemented

### Fix #1: Deprecate get_main_instance_id Tool
**Location**: `src/orchestrator/mcp_adapter.py:1122-1136`

**Approach**: Return deprecation error instead of spawning instance.

```python
# NEW CODE - Deprecation instead of auto-spawn
# DEPRECATED: get_main_instance_id tool removed
# Child instances should use their own instance_id in reply_to_caller, not main instance ID
# This tool was causing unwanted auto-spawning of main orchestrator instances
elif tool_name == "get_main_instance_id":
    result = {
        "content": [{
            "type": "text",
            "text": "⚠️ DEPRECATED: This tool has been removed.\n\n"
            "Use your own instance_id in reply_to_caller, not the main instance ID.\n"
            "Your instance_id is already provided in your system prompt.",
        }],
        "isError": True,
    }
```

**Benefits**:
- Prevents unwanted instance spawning
- Provides clear error message with guidance
- Maintains backward compatibility (doesn't crash)

### Fix #2: Enhanced System Prompt
**Location**: `src/orchestrator/tmux_instance_manager.py:1368-1378`

**Approach**: Add explicit warnings and correct usage example.

```python
# NEW CODE - Explicit warnings and example
f"CRITICAL: When calling reply_to_caller, ALWAYS use YOUR OWN instance_id.\n"
f"- Your instance_id: '{instance['id']}'\n"
f"- Do NOT call get_main_instance_id() - that tool is deprecated\n"
f"- Do NOT use correlation_id as the instance_id parameter\n"
f"- Do NOT use any other instance's ID\n\n"
f"Correct usage:\n"
f"  reply_to_caller(\n"
f"    instance_id='{instance['id']}',  # YOUR ID, not main/parent/coordinator\n"
f"    reply_message='your response',\n"
f"    correlation_id='correlation-id-from-message'\n"
f"  )\n\n"
```

**Benefits**:
- Explicit deprecation warning
- Clear example with actual instance_id
- Prevents confusion between different ID types

## Testing

### Test Case: Hierarchical Network with Counting Game
```bash
# 1. Restart server with fixes
pkill -f "run_orchestrator.py"
MADROX_TRANSPORT=http python run_orchestrator.py &

# 2. Spawn supervisor + children
supervisor = spawn_claude(name="network-supervisor")
send_to_instance(supervisor, "Spawn 2 Codex + 1 Claude children", wait_for_response=false)

# 3. Wait for spawning
sleep 15

# 4. Verify network tree
get_instance_tree()
```

**Expected Result**:
```
network-supervisor (7c2237df...) [idle] (claude)
├── claude-child-1 (978ec6bd...) [running] (claude)
├── codex-child-1 (0f068ae2...) [running] (codex)
└── codex-child-2 (eb216348...) [running] (codex)
```

**✅ Verification Results**:
- Only 4 instances exist (supervisor + 3 children)
- No unwanted "main-orchestrator" instance
- codex-child-1 used correct instance_id in reply_to_caller:
  ```
  reply_to_caller(instance_id='0f068ae2-f0d3-4418-b0a2-d55f1ff43ed1', ...)
  # Response: {"success": true, "delivered_to": "coordinator"}
  ```
- No calls to get_main_instance_id() observed in tmux output

## Files Modified

### 1. `src/orchestrator/mcp_adapter.py`
**Lines**: 1122-1136

**Changes**:
- Deprecated `get_main_instance_id` tool
- Returns error message instead of auto-spawning
- Added explanation and guidance

**Diff**:
```diff
- elif tool_name == "get_main_instance_id":
-     # Ensure main instance is spawned
-     main_id = await self.manager.ensure_main_instance()
-     result = {"content": [{"type": "text", "text": f"Main instance ID: {main_id}..."}]}
+ # DEPRECATED: get_main_instance_id tool removed
+ elif tool_name == "get_main_instance_id":
+     result = {
+         "content": [{
+             "type": "text",
+             "text": "⚠️ DEPRECATED: This tool has been removed...",
+         }],
+         "isError": True,
+     }
```

### 2. `src/orchestrator/tmux_instance_manager.py`
**Lines**: 1368-1378

**Changes**:
- Enhanced Codex system prompt with explicit warnings
- Added correct usage example with actual instance_id
- Clarified difference between instance_id types

**Diff**:
```diff
- f"IMPORTANT: Always use your own instance_id ('{instance['id']}') when calling reply_to_caller.\n"
- f"Do NOT use the correlation_id as the instance_id parameter.\n\n"
+ f"CRITICAL: When calling reply_to_caller, ALWAYS use YOUR OWN instance_id.\n"
+ f"- Your instance_id: '{instance['id']}'\n"
+ f"- Do NOT call get_main_instance_id() - that tool is deprecated\n"
+ f"- Do NOT use correlation_id as the instance_id parameter\n"
+ f"- Do NOT use any other instance's ID\n\n"
+ f"Correct usage:\n"
+ f"  reply_to_caller(\n"
+ f"    instance_id='{instance['id']}',  # YOUR ID, not main/parent/coordinator\n"
+ f"    reply_message='your response',\n"
+ f"    correlation_id='correlation-id-from-message'\n"
+ f"  )\n\n"
```

## Performance Impact

- **No performance degradation** - Deprecation is just error return
- **Fewer unwanted instances** - Prevents resource waste from auto-spawning
- **Clearer error messages** - Faster debugging when tool is mistakenly called

## Architecture Context

### Instance Identity Model

**Correct Pattern**:
```python
# Child instance using its own ID
reply_to_caller(
    instance_id='<my-own-instance-id>',  # ✅ Correct
    reply_message='response',
    correlation_id='<from-incoming-message>'
)
```

**Incorrect Patterns (Now Prevented)**:
```python
# Using main instance ID (auto-spawns unwanted instance)
main_id = get_main_instance_id()  # ❌ Deprecated, returns error
reply_to_caller(instance_id=main_id, ...)  # ❌ Wrong ID

# Using parent instance ID (wrong recipient)
reply_to_caller(instance_id='<parent-id>', ...)  # ❌ Wrong ID

# Using correlation_id (wrong parameter)
reply_to_caller(instance_id='<correlation-id>', ...)  # ❌ Wrong ID
```

### Why Each Instance Uses Its Own ID

**Architectural Reason**: The `reply_to_caller` tool uses the provided `instance_id` to identify which instance's response queue to put the reply in. Each instance has its own response queue managed by the orchestrator.

**Message Flow**:
1. Coordinator sends message to child instance (child_id: "abc123")
2. Message includes correlation_id for tracking
3. Child processes message and calls:
   ```python
   reply_to_caller(
       instance_id='abc123',  # Child's own ID (identifies response queue)
       reply_message='result',
       correlation_id='xyz'    # Correlation for request matching
   )
   ```
4. Orchestrator puts reply in child's response queue (keyed by "abc123")
5. Coordinator reads reply from that queue

**If Wrong ID Used**: Reply goes to wrong queue, never received by coordinator.

## Related Documentation

- [IPC_FIXES_2025_10_16.md](IPC_FIXES_2025_10_16.md) - Codex STDIO IPC fixes
- [NON_BLOCKING_NETWORK_SPAWN.md](NON_BLOCKING_NETWORK_SPAWN.md) - Network spawn optimization
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [API_REFERENCE.md](API_REFERENCE.md) - MCP tool reference

## Future Improvements

1. **Remove get_main_instance_id Entirely**: After migration period, remove tool completely
2. **Validation Hook**: Add pre-tool-call validation that warns when instance_id mismatch detected
3. **Better Error Messages**: Include instance_id in all error messages for easier debugging
4. **Instance ID Registry**: Track all valid instance IDs for validation purposes

## Commit Message

```
fix: prevent unwanted instance spawning from get_main_instance_id tool

Fixed bug where child instances incorrectly called get_main_instance_id(),
causing unwanted "main-orchestrator" instances to auto-spawn during normal
operations.

Root causes:
1. get_main_instance_id tool auto-spawned instance if not existing
2. System prompt didn't explicitly warn against calling the tool
3. Child instances confused "main instance ID" with "own instance_id"

Solution:
1. Deprecated get_main_instance_id tool - returns error instead of spawning
2. Enhanced Codex system prompt with explicit warnings and usage example

Result: No unwanted instance spawning, child instances correctly use their
own instance_id in reply_to_caller calls.

Files modified:
- src/orchestrator/mcp_adapter.py (lines 1122-1136)
- src/orchestrator/tmux_instance_manager.py (lines 1368-1378)

Verified: Counting game with 2-level network (supervisor + 3 children)
produces only expected instances, no unwanted main-orchestrator spawning.
```

## References

- Previous commit: `5ac5223` - Codex IPC fixes
- User feedback: "who spawned the extra supervisor?"
- Implementation date: October 16, 2025
- Related feature: Bidirectional messaging with `reply_to_caller` tool
