# Artifacts Directory Feature Documentation

## Overview

The Artifacts Directory feature adds persistent storage for Madrox team workflows, preventing critical data loss when teams complete their work. This feature implements a dedicated artifacts storage layer that automatically captures and preserves all outputs from multi-agent orchestration sessions.

## Problem Statement

When Madrox teams complete their assigned work, valuable outputs are often lost because:
- Instance workspace directories are temporary (`/tmp/claude_orchestrator/{instance_id}`)
- No centralized collection mechanism exists for team artifacts
- Child instance outputs aren't automatically aggregated
- Workflow results aren't persisted beyond the session

## Solution Architecture

### Directory Structure

```
artifacts/
├── {timestamp}/
│   ├── metadata.json          # Team composition and execution metadata
│   ├── instances/
│   │   ├── {parent_id}/
│   │   │   ├── workspace/     # Parent instance workspace files
│   │   │   └── output.log     # Parent output transcript
│   │   └── {child_id}/
│   │       ├── workspace/     # Child instance workspace files
│   │       └── output.log     # Child output transcript
│   └── summary.md             # Execution summary and results
└── {earlier_timestamp}/
    └── ...
```

### Key Components

1. **Artifacts Directory Root**: Configurable location for all team artifacts (default: `./artifacts`)
2. **Timestamp-based Organization**: Each team run creates a timestamped subdirectory
3. **Hierarchical Instance Structure**: Maintains parent-child relationships
4. **Metadata Preservation**: Captures team composition, roles, and execution details
5. **Output Aggregation**: Collects transcripts and workspace files from all instances

## Features

### 1. Automatic Artifact Preservation

The system automatically preserves:
- **Instance Workspaces**: All files created in instance workspace directories
- **Output Transcripts**: Complete terminal output for each instance
- **Metadata**: Team composition, roles, execution timestamps
- **Summary**: Execution results and key findings
- **Hierarchical Structure**: Maintains parent-child instance relationships

### 2. Per-Instance Preservation

Each instance's artifacts include:
- Complete workspace directory contents
- Full output transcript from execution
- Instance metadata (role, model, execution time)
- Resource usage statistics

### 3. Team-Level Collection

Aggregates all team member outputs:
- Hierarchical instance structure preservation
- Execution summary combining all results
- Cross-instance artifact indexing
- Resource usage aggregation

## API Reference

### Methods

#### `_preserve_artifacts(instance_id: str, output_text: str, team_session_id: str | None = None)`

Preserves artifacts for a single instance when it terminates.

**Parameters:**
- `instance_id` (str): The ID of the instance being terminated
- `output_text` (str): Complete output transcript from the instance
- `team_session_id` (str, optional): Team coordination session ID for grouping related instances

**Returns:** None

**Behavior:**
1. Creates timestamp-based artifact directory structure
2. Copies instance workspace to artifacts directory
3. Saves output transcript
4. Records instance metadata (role, model, execution time)
5. Updates team session summary

**Example:**
```python
coordinator._preserve_artifacts(
    instance_id="abc-123-def",
    output_text=full_transcript,
    team_session_id="team-session-001"
)
```

#### `collect_team_artifacts(team_session_id: str)`

Collects and aggregates artifacts from all team member instances.

**Parameters:**
- `team_session_id` (str): Team coordination session identifier

**Returns:**
- `dict` with keys:
  - `status` (str): "success" or "error"
  - `team_session_id` (str): The team session ID
  - `artifacts_path` (str): Directory path containing all team artifacts
  - `instances_count` (int): Number of instances in team
  - `metadata` (dict): Team execution metadata
  - `error` (str, optional): Error message if status is "error"

**Behavior:**
1. Locates all instances in team session
2. Aggregates metadata from all instances
3. Generates execution summary
4. Creates index of all artifacts
5. Returns comprehensive team artifacts information

**Example:**
```python
result = coordinator.collect_team_artifacts("team-session-001")
if result["status"] == "success":
    print(f"Artifacts saved to: {result['artifacts_path']}")
    print(f"Team size: {result['instances_count']}")
```

### MCP Tool Exposure

The `collect_team_artifacts` method is exposed as an MCP tool for Claude instances:

```python
@mcp.tool
async def collect_team_artifacts(team_session_id: str) -> dict[str, Any]:
    """Collect and aggregate artifacts from all team member instances."""
```

This allows any instance in the network to trigger team artifact collection.

## Configuration

### Environment Variables

```bash
# Artifacts directory root location
ARTIFACTS_DIR=/path/to/artifacts

# Default: ./artifacts (relative to madrox directory)
```

### Config File Settings

In `config.py` or configuration loader:

```python
config = {
    "artifacts_dir": "/path/to/artifacts",
    "artifacts_enabled": True,
    "artifacts_compress": False,  # Future: gzip compression
    "artifacts_retention_days": None  # Future: auto-cleanup
}
```

## Usage Guide

### Basic Team Workflow with Artifacts

```python
from orchestrator.instance_manager import InstanceManager

# Initialize with artifacts enabled
config = {
    "artifacts_dir": "./team_artifacts",
    "artifacts_enabled": True
}
manager = InstanceManager(config)

# Create team session
team_session_id = "research-team-001"

# Spawn team members
instances = await manager.spawn_multiple_instances([
    {"name": "researcher", "role": "data_scientist", "parent_instance_id": coordinator_id},
    {"name": "analyzer", "role": "architect", "parent_instance_id": coordinator_id},
    {"name": "writer", "role": "tech_writer", "parent_instance_id": coordinator_id},
])

# Work happens...
# Instances create files, generate outputs, etc.

# When complete, collect team artifacts
result = await coordinator.collect_team_artifacts(team_session_id)

print(f"Team artifacts saved to: {result['artifacts_path']}")
print(f"Instances processed: {result['instances_count']}")
```

### Accessing Team Artifacts

After workflow completion:

```
artifacts/
└── 2025-11-06_14-32-45-team-research-001/
    ├── metadata.json
    ├── instances/
    │   ├── coordinator-parent/
    │   │   ├── workspace/
    │   │   │   ├── analysis_results.json
    │   │   │   └── final_report.md
    │   │   └── output.log
    │   ├── researcher-data_scientist/
    │   │   ├── workspace/
    │   │   │   ├── data.csv
    │   │   │   └── analysis.ipynb
    │   │   └── output.log
    │   └── writer-tech_writer/
    │       ├── workspace/
    │       │   └── documentation.md
    │       └── output.log
    └── summary.md
```

### Programmatic Access to Artifacts

```python
import json
from pathlib import Path

# Load team artifacts metadata
artifacts_path = Path("./artifacts/2025-11-06_14-32-45")
metadata = json.loads((artifacts_path / "metadata.json").read_text())

# Iterate through instances
for instance_dir in (artifacts_path / "instances").iterdir():
    output_log = instance_dir / "output.log"
    workspace = instance_dir / "workspace"

    # Process instance artifacts
    print(f"Instance: {instance_dir.name}")
    print(f"Output lines: {len(output_log.read_text().splitlines())}")
    print(f"Workspace files: {len(list(workspace.rglob('*')))}")
```

## MCP Integration

### Exposing Artifact Collection via MCP

Teams can trigger artifact collection through MCP tools:

```python
# Any instance in the network can call:
result = coordinator.collect_team_artifacts("team-session-id")

# Result is formatted for MCP response:
{
    "status": "success",
    "team_session_id": "team-session-id",
    "artifacts_path": "/full/path/to/artifacts",
    "instances_count": 5,
    "metadata": {
        "created_at": "2025-11-06T14:32:45Z",
        "instances": [
            {"id": "parent-123", "role": "architect", "status": "completed"},
            {"id": "child-456", "role": "developer", "status": "completed"},
            # ... more instances
        ]
    }
}
```

## Implementation Details

### Workspace Preservation

When an instance terminates:
1. Check if instance workspace exists at `{workspace_base}/{instance_id}`
2. Create target directory in artifacts: `artifacts/{timestamp}/instances/{instance_id}/workspace`
3. Copy entire workspace recursively: `cp -r {source} {target}`
4. Handle permission errors gracefully
5. Log preservation status

### Output Transcript Capture

The output transcript is captured from the instance's tmux pane or logs:
1. Retrieve final pane content from tmux session
2. Save to `output.log` in instance artifact directory
3. Include all terminal output and formatting
4. Preserve execution metadata (timestamps, resource usage)

### Metadata Collection

For each instance, collect:
```json
{
  "instance_id": "abc-123",
  "name": "researcher",
  "role": "data_scientist",
  "model": "claude-sonnet-4-5",
  "parent_instance_id": "parent-123",
  "created_at": "2025-11-06T14:00:00Z",
  "terminated_at": "2025-11-06T14:30:00Z",
  "status": "completed",
  "tokens_used": 45230,
  "cost": 0.45,
  "error": null
}
```

## Error Handling

### Missing Instance Workspace

If instance workspace directory doesn't exist:
- Log warning with instance ID
- Still preserve output transcript
- Continue with other instances in team
- Don't block team artifact collection

### Permission Errors

If unable to copy workspace due to permissions:
- Log detailed error with instance ID
- Attempt to preserve readable files
- Record partial artifact status
- Return status indicating partial success

### Team Session Not Found

If team session ID has no instances:
- Return status: "error"
- Message: "No instances found for team session"
- Empty artifacts directory

## Storage Considerations

### Disk Space

Artifacts storage depends on:
- Number of instances in team (1-100+)
- Size of workspace files (typically 1-100MB per instance)
- Output transcript length (typically 100KB-10MB)
- Typical team: 5-10 instances = 50-500MB per session

**Recommendation**: Allocate 10GB+ for production artifact storage

### Retention Policy

Current implementation: indefinite storage

Future enhancements:
```python
# Planned configuration
config = {
    "artifacts_retention_days": 30,  # Auto-delete after 30 days
    "artifacts_compress": True,       # Gzip old artifacts
    "artifacts_max_size_gb": 100      # Enforced disk quota
}
```

### Cleanup

Manual cleanup of old artifacts:

```python
import shutil
from pathlib import Path

artifacts_dir = Path("./artifacts")
for old_session in artifacts_dir.glob("2025-10-*"):
    shutil.rmtree(old_session)
    print(f"Deleted: {old_session}")
```

## Examples

### Example 1: Research Team Workflow

```python
# Setup
coordinator = SupervisionCoordinator(...)
team_id = "research-team-001"

# Spawn research team
instances = [
    {"name": "literature-review", "role": "data_scientist"},
    {"name": "experimental-design", "role": "architect"},
    {"name": "implementation", "role": "backend_developer"},
    {"name": "documentation", "role": "tech_writer"},
]

for config in instances:
    config["parent_instance_id"] = coordinator.id

results = await manager.spawn_multiple_instances(instances)

# Team works on research project...
# Each instance creates files, runs experiments, generates output

# Collect final artifacts
team_artifacts = coordinator.collect_team_artifacts(team_id)

# Access results
print(f"Research artifacts saved to: {team_artifacts['artifacts_path']}")

# Load the comprehensive summary
import json
metadata = json.loads(
    Path(team_artifacts['artifacts_path']) / "metadata.json".read_text()
)
```

### Example 2: Multi-Stage Pipeline

```python
# Stage 1: Analysis
analysis_team = ["parser", "analyzer", "validator"]
analysis_artifacts = await run_stage(analysis_team, "analysis-stage")

# Stage 2: Processing (uses outputs from stage 1)
processing_team = ["processor", "optimizer", "evaluator"]
processing_artifacts = await run_stage(processing_team, "processing-stage")

# Stage 3: Reporting
reporting_team = ["summarizer", "reporter", "doc-writer"]
reporting_artifacts = await run_stage(reporting_team, "reporting-stage")

# Collect all stages
all_artifacts = [analysis_artifacts, processing_artifacts, reporting_artifacts]
for artifacts in all_artifacts:
    print(f"Stage artifacts: {artifacts['artifacts_path']}")
```

## Troubleshooting

### Artifacts Directory Not Created

**Symptom**: `collect_team_artifacts` returns empty path

**Solution**:
1. Check `ARTIFACTS_DIR` environment variable or config
2. Verify write permissions on artifacts directory parent
3. Check disk space availability
4. Review logs: `tail -f /tmp/madrox_logs/orchestrator.log`

### Missing Instance Files

**Symptom**: Some instances missing from team artifacts

**Solution**:
1. Verify instances terminated properly
2. Check instance workspace still exists
3. Review artifact preservation logs
4. Ensure team session ID was passed correctly

### Large Artifact Directories

**Symptom**: Artifacts consuming excessive disk space

**Solution**:
1. Review individual workspace contents
2. Consider moving old artifacts to archive storage
3. Implement retention policy
4. Monitor workspace sizes during execution

## Future Enhancements

1. **Compression**: Auto-gzip large artifact directories
2. **Deduplication**: Share common files across team artifacts
3. **Indexing**: Full-text search over artifact contents
4. **Retention Policy**: Auto-cleanup of old artifacts
5. **Streaming Upload**: Export artifacts to cloud storage (S3, GCS)
6. **Differential Backup**: Only store changed files between versions
7. **Artifact Versioning**: Track changes to critical outputs
8. **Analysis Reports**: Auto-generate artifact statistics and summaries

## Testing

### Unit Tests

```python
def test_preserve_artifacts_creates_directory():
    """Test that artifacts directory structure is created."""

def test_preserve_artifacts_copies_workspace():
    """Test that workspace files are copied to artifacts."""

def test_collect_team_artifacts_aggregates():
    """Test that team artifacts are properly aggregated."""

def test_collect_team_artifacts_missing_instances():
    """Test handling of missing instances."""
```

### Integration Tests

```python
async def test_team_workflow_artifact_collection():
    """Test full workflow from team spawn to artifact collection."""
```

## API Endpoints (HTTP Mode)

```
POST /artifacts/collect/{team_session_id}
  Description: Trigger team artifact collection
  Response: {status, artifacts_path, instances_count, metadata}

GET /artifacts/list
  Description: List all artifact sessions
  Response: [list of artifact directories with metadata]

GET /artifacts/{session_id}/metadata
  Description: Get session metadata
  Response: {created_at, instances, summary}
```

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [API_REFERENCE.md](API_REFERENCE.md) - Complete API reference
- [FEATURES.md](FEATURES.md) - Other feature documentation
