# Artifact Collection System - Design Document

## Executive Summary

The artifact collection system currently fails because:
1. **Configuration Gap**: `artifacts_dir` and `preserve_artifacts` are defined in `OrchestratorConfig` but not read from environment variables
2. **Workspace Deletion**: Child workspaces are deleted after termination (line 1286-1295 of tmux_instance_manager.py)
3. **Preservation Success**: Artifacts ARE preserved to `/tmp/madrox_artifacts/{instance_id}/` before deletion
4. **Collection Failure**: `collect_team_artifacts` tries to read from deleted workspaces instead of preserved artifacts
5. **Filtering Issue**: `_get_children_internal()` filters out terminated instances, leaving nothing to collect

---

## Current Implementation Analysis

### 1. Configuration Flow

**File: `/path/to/user/dev/madrox/src/orchestrator/simple_models.py`**

Lines 250-251: OrchestratorConfig defines artifact fields:
```python
artifacts_dir: str = "/tmp/madrox_artifacts",
preserve_artifacts: bool = True,
```

**File: `/path/to/user/dev/madrox/run_orchestrator.py`**

Lines 85-93: Config is loaded from environment variables, but **artifacts_dir and preserve_artifacts are missing**:
```python
config = OrchestratorConfig(
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    server_host=os.getenv("ORCHESTRATOR_HOST", "localhost"),
    server_port=int(os.getenv("ORCHESTRATOR_PORT", "8001")),
    max_concurrent_instances=int(os.getenv("MAX_INSTANCES", "10")),
    workspace_base_dir=os.getenv("WORKSPACE_DIR", "/tmp/claude_orchestrator"),
    log_dir=os.getenv("LOG_DIR", "/tmp/madrox_logs"),
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    # MISSING: artifacts_dir and preserve_artifacts
)
```

### 2. Artifact Preservation Flow (WORKING CORRECTLY)

**File: `/path/to/user/dev/madrox/src/orchestrator/tmux_instance_manager.py`**

**Method: `terminate_instance` (lines 1204-1303)**
1. Line 1275: Calls `_preserve_artifacts(instance_id)` BEFORE cleanup
2. Lines 1286-1295: Deletes workspace AFTER preservation

**Method: `_preserve_artifacts` (lines 1071-1202)**
1. Line 1091: Checks if preservation is enabled
2. Lines 1103-1108: Creates artifacts directory structure:
   ```python
   artifacts_base = Path(self.config.get("artifacts_dir", "/tmp/madrox_artifacts"))
   instance_artifacts_dir = artifacts_base / instance_id
   ```
3. Lines 1123-1145: Copies files matching artifact patterns
4. Lines 1148-1171: Generates metadata JSON with instance info
5. Returns success with artifacts_dir path

**Artifacts are stored at:** `/tmp/madrox_artifacts/{instance_id}/`

### 3. Artifact Collection Flow (BROKEN)

**File: `/path/to/user/dev/madrox/src/orchestrator/instance_manager.py`**

**Method: `collect_team_artifacts` (lines 1866-2043)**

**Problem 1:** Line 1887 - Calls `_get_children_internal()` which filters out terminated instances
```python
children = self._get_children_internal(team_supervisor_id)
```

**Method: `_get_children_internal` (lines 985-1009)**

**Problem 2:** Line 998 - Explicitly excludes terminated instances:
```python
if (
    instance.get("parent_instance_id") == parent_id
    and instance.get("state") != "terminated"  # <-- PROBLEM
):
```

**Problem 3:** Lines 1921-1929 - Tries to read from deleted workspace:
```python
child_instance = self.instances[child_id]
child_workspace = Path(child_instance.get("workspace_dir", ""))

if not child_workspace.exists():  # <-- FAILS: workspace was deleted
    logger.warning(f"Child workspace does not exist for {child_id}")
    collection_errors.append(...)
    continue
```

---

## Solution Design

### Phase 1: Environment Variable Configuration

**File: `/path/to/user/dev/madrox/run_orchestrator.py`**

**Line 85-93:** Update `OrchestratorConfig` initialization to include artifact settings:

```python
config = OrchestratorConfig(
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    server_host=os.getenv("ORCHESTRATOR_HOST", "localhost"),
    server_port=int(os.getenv("ORCHESTRATOR_PORT", "8001")),
    max_concurrent_instances=int(os.getenv("MAX_INSTANCES", "10")),
    workspace_base_dir=os.getenv("WORKSPACE_DIR", "/tmp/claude_orchestrator"),
    log_dir=os.getenv("LOG_DIR", "/tmp/madrox_logs"),
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    # NEW: Add artifact configuration
    artifacts_dir=os.getenv("ARTIFACTS_DIR", "/tmp/madrox_artifacts"),
    preserve_artifacts=os.getenv("PRESERVE_ARTIFACTS", "true").lower() == "true",
)
```

**Environment Variables:**
- `ARTIFACTS_DIR`: Directory for preserved artifacts (default: `/tmp/madrox_artifacts`)
- `PRESERVE_ARTIFACTS`: Enable/disable preservation (default: `true`)

### Phase 2: Support Terminated Children Retrieval

**File: `/path/to/user/dev/madrox/src/orchestrator/instance_manager.py`**

**Method: `_get_children_internal` (line 985-1009)**

Add optional parameter to include terminated instances:

```python
def _get_children_internal(
    self,
    parent_id: str,
    include_terminated: bool = False  # NEW PARAMETER
) -> list[dict[str, Any]]:
    """Internal method to get all child instances of a parent.

    Args:
        parent_id: Parent instance ID
        include_terminated: If True, include terminated instances (default: False)

    Returns:
        List of child instance details
    """
    children = []
    for instance_id, instance in self.instances.items():
        is_child = instance.get("parent_instance_id") == parent_id

        # Apply terminated filter based on parameter
        if include_terminated:
            include = is_child
        else:
            include = is_child and instance.get("state") != "terminated"

        if include:
            children.append({
                "id": instance_id,
                "name": instance.get("name"),
                "role": instance.get("role"),
                "state": instance.get("state"),
                "instance_type": instance.get("instance_type"),
            })
    return children
```

**Note:** The public `get_children` tool (line 1012-1021) maintains backward compatibility by not passing `include_terminated`.

### Phase 3: Fix Artifact Collection Logic

**File: `/path/to/user/dev/madrox/src/orchestrator/instance_manager.py`**

**Method: `collect_team_artifacts` (lines 1866-2043)**

**Changes needed:**

1. **Line 1887:** Include terminated instances:
```python
# OLD: children = self._get_children_internal(team_supervisor_id)
children = self._get_children_internal(team_supervisor_id, include_terminated=True)
```

2. **Lines 1919-1967:** Replace workspace reading logic with preserved artifact reading:

```python
for child in children:
    child_id = child["id"]
    child_name = child.get("name", "unknown")
    child_state = child.get("state")

    try:
        # Determine source directory for artifacts
        artifacts_base = Path(self.config.get("artifacts_dir", "/tmp/madrox_artifacts"))

        # Check if artifacts were preserved (for terminated instances)
        preserved_artifacts_dir = artifacts_base / child_id

        # Get child's current workspace (for running instances)
        child_instance = self.instances.get(child_id)
        child_workspace = Path(child_instance.get("workspace_dir", "")) if child_instance else None

        # Determine source directory priority:
        # 1. Preserved artifacts (if exists) - for terminated instances
        # 2. Workspace (if exists) - for running instances
        source_dir = None
        source_type = None

        if preserved_artifacts_dir.exists():
            source_dir = preserved_artifacts_dir
            source_type = "preserved"
        elif child_workspace and child_workspace.exists():
            source_dir = child_workspace
            source_type = "workspace"
        else:
            logger.warning(
                f"No artifacts found for child {child_id} (state: {child_state})",
                extra={
                    "child_id": child_id,
                    "checked_preserved": str(preserved_artifacts_dir),
                    "checked_workspace": str(child_workspace) if child_workspace else None,
                }
            )
            collection_errors.append({
                "child_id": child_id,
                "error": f"No artifacts found (state: {child_state})"
            })
            continue

        logger.debug(
            f"Collecting artifacts for {child_id} from {source_type}",
            extra={"child_id": child_id, "source": str(source_dir), "type": source_type}
        )

        # Create child's artifacts subdirectory in team collection
        child_artifacts_dir = team_artifacts_dir / child_id
        child_artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Copy files from source_dir (rest remains same)
        child_files_copied = 0
        import fnmatch

        for item in source_dir.rglob("*"):
            if not item.is_file():
                continue

            # Skip metadata files from preserved artifacts
            if item.name == "_metadata.json" and source_type == "preserved":
                continue

            filename = item.name
            matches_pattern = any(
                fnmatch.fnmatch(filename, pattern) for pattern in artifact_patterns
            )

            if matches_pattern:
                try:
                    relative_path = item.relative_to(source_dir)
                    target_path = child_artifacts_dir / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target_path)
                    child_files_copied += 1
                    total_files_collected += 1
                except Exception as e:
                    logger.warning(f"Failed to copy artifact {item}: {e}")
                    collection_errors.append({
                        "file": str(item),
                        "error": str(e),
                        "child_id": child_id
                    })

        # Create child metadata file (rest remains same)
        child_metadata = {
            "child_id": child_id,
            "child_name": child_name,
            "state": child_state,  # NEW: Include state
            "instance_type": child.get("instance_type"),
            "role": child.get("role"),
            "files_collected": child_files_copied,
            "source_type": source_type,  # NEW: Track source
            "source_dir": str(source_dir),  # NEW: Track source path
        }

        child_metadata_path = child_artifacts_dir / "_metadata.json"
        child_metadata_path.write_text(json.dumps(child_metadata, indent=2))

        member_summaries.append({
            "child_id": child_id,
            "child_name": child_name,
            "state": child_state,  # NEW
            "files_collected": child_files_copied,
            "artifacts_dir": str(child_artifacts_dir),
            "source_type": source_type,  # NEW
        })

    except Exception as e:
        logger.error(f"Failed to collect artifacts from child {child_id}: {e}")
        collection_errors.append({"child_id": child_id, "error": str(e)})
```

---

## Implementation Summary

### Modified Files

1. **`run_orchestrator.py`** (lines 85-93)
   - Add `artifacts_dir` from `ARTIFACTS_DIR` env var
   - Add `preserve_artifacts` from `PRESERVE_ARTIFACTS` env var

2. **`instance_manager.py`** (lines 985-1009)
   - Add `include_terminated` parameter to `_get_children_internal()`
   - Update filtering logic to optionally include terminated instances

3. **`instance_manager.py`** (lines 1866-2043)
   - Update `collect_team_artifacts` to call `_get_children_internal(team_supervisor_id, include_terminated=True)`
   - Replace workspace-only logic with preserved artifacts priority
   - Check preserved artifacts first, fall back to workspace for running instances
   - Update metadata to track source type and state

---

## Edge Cases and Risks

### Edge Cases

1. **Partially Terminated Team**
   - **Scenario**: Some children terminated, others still running
   - **Solution**: Priority logic checks preserved artifacts first, then workspace
   - **Result**: Collects from both sources seamlessly

2. **No Preserved Artifacts**
   - **Scenario**: `preserve_artifacts=false` or preservation failed
   - **Solution**: Falls back to workspace for running instances
   - **Result**: Warning logged, continues with available sources

3. **Artifacts Exist But Empty**
   - **Scenario**: Child had no matching files
   - **Solution**: `files_collected=0` in metadata
   - **Result**: No error, documented in manifest

4. **Concurrent Termination**
   - **Scenario**: Child terminates while collection is running
   - **Solution**: Check both preserved and workspace locations
   - **Result**: Graceful degradation with error tracking

### Risks

1. **Backward Compatibility** - LOW RISK
   - `_get_children_internal()` default behavior unchanged
   - Existing callers unaffected
   - Only `collect_team_artifacts` uses new parameter

2. **Performance** - LOW RISK
   - Additional file system checks (2 per child: preserved + workspace)
   - Mitigated by early returns and parallel processing

3. **Race Conditions** - MEDIUM RISK
   - If workspace deleted DURING read (unlikely due to preservation timing)
   - Mitigated by try-catch blocks and fallback logic

4. **Disk Space** - LOW RISK
   - Preserved artifacts consume additional space
   - Addressed by existing artifact patterns filtering
   - Can be cleaned up manually from `/tmp/madrox_artifacts/`

---

## Testing Recommendations

1. **Unit Tests**
   - Test `_get_children_internal()` with `include_terminated=True/False`
   - Test artifact source priority logic
   - Test empty/missing artifact scenarios

2. **Integration Tests**
   - Spawn team, terminate some children, collect artifacts
   - Verify both preserved and workspace sources work
   - Check manifest JSON structure

3. **Environment Variable Tests**
   - Test with custom `ARTIFACTS_DIR`
   - Test with `PRESERVE_ARTIFACTS=false`
   - Verify defaults work correctly

---

## API Signatures

### Modified Methods

```python
def _get_children_internal(
    self,
    parent_id: str,
    include_terminated: bool = False
) -> list[dict[str, Any]]:
    """Get all child instances of a parent.

    Args:
        parent_id: Parent instance ID
        include_terminated: If True, include terminated instances (default: False)

    Returns:
        List of child instance details
    """
```

### Unchanged Public API

```python
@mcp.tool
def get_children(self, parent_id: str) -> list[dict[str, Any]]:
    """Public API - unchanged, excludes terminated by default"""
    return self._get_children_internal(parent_id)

@mcp.tool
async def collect_team_artifacts(
    self,
    team_supervisor_id: str
) -> dict[str, Any]:
    """Public API - unchanged signature, improved implementation"""
```

---

## Success Criteria Verification

1. ✅ **Artifacts collected from terminated children**
   - Solution: `include_terminated=True` parameter
   - Location: Preserved artifacts directory

2. ✅ **Artifacts collected from running children**
   - Solution: Workspace fallback logic
   - Location: Current workspace

3. ✅ **Team manifest includes all members**
   - Solution: Include terminated in children list
   - Content: Full member summaries with state

4. ✅ **No workspace access errors**
   - Solution: Check preserved artifacts first
   - Fallback: Graceful degradation with logging

5. ✅ **Environment variable configuration**
   - Solution: Read `ARTIFACTS_DIR` and `PRESERVE_ARTIFACTS`
   - Defaults: `/tmp/madrox_artifacts` and `true`

---

## Next Steps

1. **Implementation Team**: Backend developer to implement changes
2. **Testing Team**: QA specialist to write tests
3. **Documentation Team**: Update user-facing docs
4. **Code Review**: Security and performance review before merge

---

**Design Document Version:** 1.0
**Author:** Solutions Architect
**Date:** 2025-11-07
**Status:** Ready for Implementation
