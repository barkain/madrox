# Parent Instance ID Auto-Injection - Implementation Plan

**Created**: 2025-11-06
**Status**: Planning
**Goal**: Make `parent_instance_id` automatic and mandatory for all spawns except Madrox main orchestrator

## TL;DR

**Problem**: Team supervisor spawned children without parent linkage, creating flat hierarchy instead of tree structure.

**Root Cause**: Caller detection failed, no fallback enforcement, spawned with `parent_instance_id=None`.

**Solution**: Two-tier auto-detection with **strict validation** (no silent fallback):
1. **Tier 1**: Use explicit `parent_instance_id` if provided
2. **Tier 2**: Auto-detect caller instance from MCP call
3. **Enforcement**: If both fail and not main-orchestrator → **raise exception** (no silent main fallback)

**Key Change**: Remove flawed main_instance_id fallback, enforce strict parent requirement with clear error messages.

### Decision Matrix

| Spawn Scenario | Tier 1 Explicit | Tier 2 Auto-Detect | Result |
|----------------|-----------------|-------------------|--------|
| **User provides parent** | ✅ parent=abc123 | - | Use abc123 |
| **Managed instance spawns** | ❌ None | ✅ Detect caller=xyz789 | Use xyz789 |
| **External client spawns** | ❌ None | ❌ Can't detect | ❌ **Exception** |
| **Main orchestrator** | ❌ None | ❌ Can't detect | ✅ Allow None |

**Critical**: No silent fallback to main_instance_id - fail loudly with actionable error message.

## Current State Analysis

### Existing Auto-Injection Logic

**Location**: `src/orchestrator/mcp_adapter.py:258-349`

#### Current Implementation (HTTP/SSE Transport):
```python
# Lines 258-289: Auto-detect caller instance
caller_instance_id = None

# Strategy 1: Find busy instances (actively making MCP calls)
busy_instances = []
for instance_id, instance_data in self.manager.instances.items():
    if instance_data.get("state") == "busy":
        busy_instances.append((instance_id, instance_data.get("last_activity")))

if busy_instances:
    busy_instances.sort(key=lambda x: x[1] if x[1] else "", reverse=True)
    caller_instance_id = busy_instances[0][0]
else:
    # Strategy 2: Fallback - most recently active instance with request_count > 0
    for instance_id, instance_data in self.manager.instances.items():
        if instance_data.get("state") != "terminated" and instance_data.get("request_count", 0) > 0:
            # Pick latest activity
            pass

# Lines 294-299: Auto-inject for spawn_claude
if tool_name == "spawn_claude":
    parent_id = tool_args.get("parent_instance_id")
    if not parent_id and caller_instance_id:
        parent_id = caller_instance_id
        logger.info(f"Auto-injected parent_instance_id={caller_instance_id}")

# Lines 328-333: Auto-inject for spawn_multiple_instances
elif tool_name == "spawn_multiple_instances":
    for instance_config in instances_config:
        parent_id = instance_config.get("parent_instance_id")
        if not parent_id and caller_instance_id:
            parent_id = caller_instance_id
```

#### Current Implementation (Instance Manager):
**Location**: `src/orchestrator/instance_manager.py:570-577`

```python
# Auto-assign main as parent if no parent specified
is_main_instance = name == "main-orchestrator"
parent_id = kwargs.get("parent_instance_id")

if parent_id is None and not is_main_instance and self.main_instance_id is not None:
    # Auto-assign main as parent
    kwargs["parent_instance_id"] = self.main_instance_id
    logger.debug(f"Auto-assigning main as parent for {name}")
```

### Problems with Current Implementation

1. **Dual Auto-Assignment Logic**: Both MCP adapter and InstanceManager try to auto-assign, creating confusion
2. **Inconsistent Behavior**: HTTP transport uses caller detection, direct calls use main_instance_id
3. **Caller Detection Unreliable**: Busy state detection can fail in edge cases
4. **Not Truly Mandatory**: Auto-injection only happens if caller detected, otherwise spawns with parent=None
5. **Flat Hierarchy Bug**: When caller detection fails, team members spawn without parent linkage

### Current Exception Handling

**Location**: `src/orchestrator/instance_manager.py:571`

```python
is_main_instance = name == "main-orchestrator"
```

Only the main orchestrator instance is allowed to have `parent_instance_id=None`.

## Problem Statement

**Issue**: Team supervisor spawned children with `parent_instance_id=None`, causing flat hierarchy instead of tree structure.

**Root Cause**: Caller instance detection failed, so auto-injection didn't happen.

**User Request**: Make `parent_instance_id` **mandatory** and **automatically set** for all spawns, with only one exception: Madrox main orchestrator.

## Proposed Solution

### Strategy: Two-Tier Auto-Detection with Mandatory Enforcement

#### Tier 1: Explicit Parent ID (Highest Priority)
```python
# User explicitly provides parent_instance_id
spawn_claude(name="child", role="dev", parent_instance_id="abc123")
```
**Result**: Use provided parent ID

#### Tier 2: Auto-Detected Caller Instance (HTTP/MCP Transport)
```python
# MCP adapter detects calling instance from busy state
# Auto-injects caller's ID as parent
```
**Result**: Use auto-detected caller as parent

#### Mandatory Enforcement: Raise Exception if Detection Fails
```python
# If parent_instance_id is still None after Tier 1 and Tier 2
# AND instance is not main orchestrator
# THEN raise exception (no silent fallback)
if parent_id is None and name != "main-orchestrator":
    raise ValueError(
        f"Cannot spawn instance '{name}': parent_instance_id is required. "
        f"Either provide parent_instance_id explicitly or spawn from a managed instance."
    )
```
**Result**: Spawn fails loudly, no artificial parent assignment

#### Exception: Main Orchestrator Only
```python
# ONLY the main orchestrator is allowed parent_instance_id=None
spawn_instance(name="main-orchestrator", role="general")
# parent_instance_id remains None (allowed)
```

## Implementation Plan

### Phase 1: Consolidate Auto-Detection Logic

**Goal**: Move all auto-detection logic to a single location

#### Changes to `src/orchestrator/mcp_adapter.py`

**Current**:
- Lines 258-289: Caller detection
- Lines 294-299: Auto-inject for spawn_claude
- Lines 328-333: Auto-inject for spawn_multiple_instances

**Proposed**: Extract to helper method

```python
def _detect_caller_instance(self) -> str | None:
    """Detect which managed instance is making the MCP tool call.

    Detection strategies (in order):
    1. Find busy instances (actively executing tools)
    2. Find most recently active instance with request_count > 0

    Returns:
        Instance ID of caller, or None if detection fails
    """
    # Strategy 1: Busy instances
    busy_instances = []
    for instance_id, instance_data in self.manager.instances.items():
        if instance_data.get("state") == "busy":
            busy_instances.append((instance_id, instance_data.get("last_activity")))

    if busy_instances:
        busy_instances.sort(key=lambda x: x[1] if x[1] else "", reverse=True)
        caller_id = busy_instances[0][0]
        logger.info(f"Auto-detected caller via busy state: {caller_id}")
        return caller_id

    # Strategy 2: Most recently active
    latest_activity = None
    caller_id = None
    for instance_id, instance_data in self.manager.instances.items():
        if instance_data.get("state") == "terminated":
            continue
        if instance_data.get("request_count", 0) == 0:
            continue

        last_activity = instance_data.get("last_activity")
        if last_activity and (latest_activity is None or last_activity > latest_activity):
            latest_activity = last_activity
            caller_id = instance_id

    if caller_id:
        logger.info(f"Auto-detected caller via activity: {caller_id}")
    else:
        logger.warning("Failed to auto-detect caller instance")

    return caller_id
```

**Usage in spawn_claude**:
```python
if tool_name == "spawn_claude":
    parent_id = tool_args.get("parent_instance_id")

    # Auto-detect caller if parent not provided
    if not parent_id:
        parent_id = self._detect_caller_instance()
        if parent_id:
            logger.info(f"Auto-injected parent_instance_id={parent_id}")

    # Pass to InstanceManager (will handle main fallback and validation)
    instance_id = await self.manager.spawn_instance(
        name=tool_args.get("name", "unnamed"),
        role=tool_args.get("role", "general"),
        parent_instance_id=parent_id,  # May still be None
        ...
    )
```

### Phase 2: Mandatory Parent ID Validation

**Goal**: Enforce parent_instance_id requirement in InstanceManager

#### Changes to `src/orchestrator/instance_manager.py:570-591`

**Current** (FLAWED - has silent fallback to main):
```python
is_main_instance = name == "main-orchestrator"
parent_id = kwargs.get("parent_instance_id")

if parent_id is None and not is_main_instance and self.main_instance_id is not None:
    kwargs["parent_instance_id"] = self.main_instance_id
    logger.debug(f"Auto-assigning main as parent for {name}")
```
**Problems**:
- Creates artificial parent-child relationship with main
- main_instance_id might be None (not always spawned)
- External spawns shouldn't be children of main

**Proposed** (STRICT - no fallback, fail loudly):
```python
is_main_instance = name == "main-orchestrator"
parent_id = kwargs.get("parent_instance_id")

# MANDATORY: Raise exception if no parent can be determined
if parent_id is None and not is_main_instance:
    raise ValueError(
        f"Cannot spawn instance '{name}': parent_instance_id is required but could not be determined. "
        f"This instance is not the main orchestrator and no parent was detected. "
        f"\n"
        f"Possible causes:\n"
        f"  1. Spawning from external client without explicit parent_instance_id\n"
        f"  2. Caller instance detection failed (instance not in 'busy' state)\n"
        f"  3. Spawning before any managed instances exist\n"
        f"\n"
        f"Solutions:\n"
        f"  1. Provide parent_instance_id explicitly: spawn_claude(..., parent_instance_id='abc123')\n"
        f"  2. Spawn from within a managed instance (auto-detection will work)\n"
        f"  3. First spawn the main orchestrator, then use it as parent\n"
    )

# Log final parent assignment
if parent_id:
    logger.info(f"Instance '{name}' will have parent: {parent_id}")
elif is_main_instance:
    logger.info(f"Instance '{name}' is main orchestrator (no parent)")
else:
    # Should never reach here due to exception above
    raise RuntimeError(f"Invalid state: instance '{name}' has no parent but is not main orchestrator")
```

**Key Change**: Remove main_instance_id fallback entirely, enforce strict parent requirement

### Phase 3: Update spawn_codex

**Goal**: Apply same logic to Codex instance spawning

#### Changes to `src/orchestrator/instance_manager.py:594-645`

Apply identical parent_instance_id detection and validation as spawn_claude.

### Phase 4: Update Documentation

#### Files to Update:

1. **docs/API_REFERENCE.md**
   - Update spawn_claude docs to explain automatic parent detection
   - Document exception cases when parent cannot be determined
   - Add examples showing explicit vs. auto-detected parent

2. **docs/FEATURES.md**
   - Add section on automatic parent instance detection
   - Explain hierarchical instance management

3. **templates/*.md** (All team templates)
   - Update instructions to note that parent_instance_id is now automatic
   - Remove explicit parent_instance_id from example calls (keep for clarity in docs)

4. **Create new doc: docs/PARENT_INSTANCE_ID_AUTO_INJECTION.md**
   - Detailed explanation of three-tier detection
   - When to provide explicit parent_instance_id
   - Troubleshooting guide for spawn failures

## Testing Strategy

### Unit Tests

**File**: `tests/test_parent_instance_id_auto_injection.py`

```python
import pytest
from src.orchestrator.instance_manager import InstanceManager

@pytest.mark.asyncio
async def test_spawn_with_explicit_parent():
    """Test explicit parent_instance_id is respected."""
    # Should use provided parent, not auto-detect
    pass

@pytest.mark.asyncio
async def test_spawn_auto_detects_caller():
    """Test auto-detection of caller instance (HTTP transport)."""
    # Should detect busy/active instance as parent
    pass

@pytest.mark.asyncio
async def test_spawn_fallback_to_main():
    """Test fallback to main_instance_id when caller not detected."""
    # Should use main_instance_id as parent
    pass

@pytest.mark.asyncio
async def test_spawn_main_orchestrator_no_parent():
    """Test main-orchestrator can spawn without parent."""
    # Should allow parent_instance_id=None for main-orchestrator
    pass

@pytest.mark.asyncio
async def test_spawn_fails_without_parent():
    """Test spawn fails if parent cannot be determined."""
    # Should raise ValueError with helpful message
    pass

@pytest.mark.asyncio
async def test_spawn_multiple_auto_inject_parent():
    """Test spawn_multiple_instances auto-injects parent for all."""
    # Should auto-detect parent for all instances in batch
    pass
```

### Integration Tests

**File**: `tests/integration/test_hierarchical_spawning.py`

Test real team spawning scenarios:
1. Supervisor spawns team members (should create proper hierarchy)
2. Team member spawns sub-agents (should use team member as parent)
3. External client spawns instance (should use main as parent)

## Rollout Strategy

### Phase 1: Implement with Warning (Non-Breaking)
- Implement auto-detection and main fallback
- If parent still None, LOG WARNING but allow spawn
- Monitor logs for cases where parent detection fails

### Phase 2: Strict Validation (Breaking Change)
- Change warning to exception
- Update all documentation
- Announce breaking change in release notes

## Exception Cases

### Case 1: Main Orchestrator
```python
# ALLOWED: Main orchestrator has no parent
spawn_instance(name="main-orchestrator", role="general")
# parent_instance_id = None
```

### Case 2: External Client Spawn (No Auto-Detection)
```python
# BEFORE: Would silently use main_instance_id as parent (wrong)
# AFTER: Fails with clear error message
spawn_claude(name="external-agent", role="analyst")
# ❌ ValueError: parent_instance_id is required

# CORRECT: Provide explicit parent
spawn_claude(name="external-agent", role="analyst", parent_instance_id="abc123")
# ✅ parent_instance_id = abc123
```

### Case 3: Team Member Spawn
```python
# Supervisor (instance abc123) spawns child
spawn_claude(name="developer", role="backend_developer")
# parent_instance_id = abc123 (auto-detected from caller)
```

### Case 4: Explicit Override
```python
# User wants specific parent (not caller)
spawn_claude(name="shared-agent", role="general", parent_instance_id="xyz789")
# parent_instance_id = xyz789 (explicit, not overridden)
```

## Backwards Compatibility

### Breaking Changes
- **None**: Existing code that explicitly provides `parent_instance_id` continues to work
- **Enhancement**: Code that omits `parent_instance_id` now gets automatic assignment instead of None

### Migration Path
1. Deploy with warning mode (Phase 1)
2. Monitor logs for 1-2 weeks
3. Fix any instances where detection fails
4. Enable strict validation (Phase 2)

## Success Metrics

- ✅ 100% of spawned instances have non-None parent (except main-orchestrator)
- ✅ Team hierarchies correctly formed (no flat structures)
- ✅ Spawn from managed instances succeeds (auto-detection works)
- ✅ Spawn from external clients fails with clear error (no silent incorrect parent)
- ✅ Clear error messages guide users to correct solution

## Timeline

- **Phase 1 (Code Changes)**: 2-3 hours
- **Phase 2 (Testing)**: 2-3 hours
- **Phase 3 (Documentation)**: 1-2 hours
- **Phase 4 (Rollout)**: 1 week monitoring

**Total**: ~1 day implementation + 1 week observation

## Next Steps

1. Create feature branch: `feature/mandatory-parent-instance-id`
2. Implement Phase 1: Consolidate auto-detection
3. Implement Phase 2: Mandatory validation
4. Write comprehensive tests
5. Update documentation
6. Deploy with warning mode
7. Monitor and adjust
8. Enable strict validation

---

**Status**: Ready for implementation
**Requires Review**: Yes (breaking change consideration)
