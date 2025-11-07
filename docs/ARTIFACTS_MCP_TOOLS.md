# Artifacts Feature - MCP Tools Reference

## Overview

The Artifacts feature exposes MCP tools that enable Claude instances to programmatically collect and manage team artifacts during multi-agent orchestration workflows.

## Tool: `collect_team_artifacts`

### Description

Collects and aggregates artifacts from all instances in a team session, creating a persistent record of team outputs and execution state.

### Tool Definition

```python
@mcp.tool
async def collect_team_artifacts(team_session_id: str) -> dict[str, Any]:
    """
    Collect and aggregate artifacts from all team member instances.

    This tool aggregates outputs from all instances in a team coordination session,
    preserving workspace files, execution transcripts, and metadata in a persistent
    artifacts directory structure.

    Artifacts are organized hierarchically to maintain parent-child relationships
    and enable easy discovery of team outputs.

    Args:
        team_session_id: Unique identifier for the team coordination session.
                        All instances in the session must have been initialized
                        with this team_session_id.

    Returns:
        Dictionary containing:
        - status: "success" or "error"
        - team_session_id: Echo of input team session ID
        - artifacts_path: Absolute path to team artifacts directory
        - instances_count: Number of instances in team
        - instances: List of instance metadata
        - summary: Execution summary
        - error: Error message (if status is "error")

    Example:
        result = collect_team_artifacts("research-team-001")
        if result["status"] == "success":
            print(f"Artifacts: {result['artifacts_path']}")
    """
```

### Parameters

#### `team_session_id` (string, required)

**Type**: String

**Description**: Unique identifier for the team coordination session

**Requirements**:
- Must be non-empty
- Should be URL-safe (alphanumeric, hyphens, underscores)
- Recommended format: `{team-name}-{session-number}` or UUID
- All instances must use identical team_session_id

**Example Values**:
- `"research-team-001"`
- `"keygen-analysis-2025"`
- `"a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5"`

**Common Mistakes**:
- ❌ Using spaces: `"research team 001"` → Use hyphens instead
- ❌ Using special chars: `"team@001"` → Use alphanumeric only
- ❌ Mismatched IDs: Parent uses `"team-1"`, child uses `"team-2"` → Keep consistent

### Return Value

#### Success Response

```json
{
  "status": "success",
  "team_session_id": "research-team-001",
  "artifacts_path": "/Users/nadavbarkai/dev/madrox/artifacts/2025-11-06_14-32-45-research-team-001",
  "instances_count": 4,
  "instances": [
    {
      "instance_id": "parent-abc123",
      "name": "coordinator",
      "role": "architect",
      "model": "claude-sonnet-4-5",
      "status": "completed",
      "created_at": "2025-11-06T14:00:00Z",
      "terminated_at": "2025-11-06T14:30:00Z",
      "execution_time_seconds": 1800,
      "tokens_used": 45230,
      "cost": 0.45,
      "parent_instance_id": null,
      "children_count": 3
    },
    {
      "instance_id": "child-def456",
      "name": "researcher",
      "role": "data_scientist",
      "model": "claude-sonnet-4-5",
      "status": "completed",
      "created_at": "2025-11-06T14:05:00Z",
      "terminated_at": "2025-11-06T14:28:00Z",
      "execution_time_seconds": 1380,
      "tokens_used": 32100,
      "cost": 0.32,
      "parent_instance_id": "parent-abc123",
      "children_count": 0
    }
  ],
  "summary": {
    "total_instances": 4,
    "total_tokens": 125000,
    "total_cost": 1.25,
    "execution_start": "2025-11-06T14:00:00Z",
    "execution_end": "2025-11-06T14:32:00Z",
    "total_execution_time_seconds": 1920,
    "all_completed": true,
    "errors": []
  }
}
```

#### Error Response

```json
{
  "status": "error",
  "team_session_id": "research-team-001",
  "artifacts_path": null,
  "instances_count": 0,
  "error": "No instances found for team session 'research-team-001'"
}
```

### Response Fields

#### `status` (string)

**Possible Values**: `"success"` | `"error"`

- `"success"`: Artifacts collected successfully
- `"error"`: Failed to collect artifacts (see `error` field)

#### `team_session_id` (string)

Echo of the input `team_session_id` parameter. Useful for matching requests to responses.

#### `artifacts_path` (string | null)

**On Success**: Absolute filesystem path to the artifacts directory

```
/Users/nadavbarkai/dev/madrox/artifacts/2025-11-06_14-32-45-research-team-001
```

**On Error**: `null`

**Structure**: `{ARTIFACTS_DIR}/{timestamp}-{team_session_id}`

#### `instances_count` (integer)

Number of instances in the team session whose artifacts were collected.

- `> 0`: Successfully found and processed instances
- `0`: No instances found (usually indicates error)

#### `instances` (array)

List of instance metadata objects. Each instance includes:

- `instance_id`: Unique instance identifier
- `name`: Human-readable instance name
- `role`: Instance role (architect, developer, etc.)
- `model`: Claude model used
- `status`: Execution status (completed, error, timeout, etc.)
- `created_at`: ISO timestamp of instance creation
- `terminated_at`: ISO timestamp of instance termination
- `execution_time_seconds`: Total execution duration
- `tokens_used`: Tokens consumed by instance
- `cost`: Dollar cost of instance execution
- `parent_instance_id`: ID of parent instance (null for root)
- `children_count`: Number of child instances spawned

#### `summary` (object)

Aggregated team execution statistics:

- `total_instances`: Count of all instances
- `total_tokens`: Sum of all instance tokens
- `total_cost`: Sum of all instance costs
- `execution_start`: Earliest instance creation time
- `execution_end`: Latest instance termination time
- `total_execution_time_seconds`: Wall-clock duration
- `all_completed`: Boolean indicating if all instances completed successfully
- `errors`: Array of error strings from failed instances

#### `error` (string | undefined)

**Only present if `status` is `"error"`**

Human-readable error message describing what went wrong.

**Common Error Messages**:
- `"No instances found for team session '{id}'"` - Team session ID doesn't match any instances
- `"Team session ID cannot be empty"` - Empty string passed as team_session_id
- `"Failed to create artifacts directory: Permission denied"` - File system permission issue
- `"Artifact collection timed out"` - Operation took too long

## Usage Examples

### Example 1: Basic Team Artifact Collection

```python
# In parent instance or coordinator
result = collect_team_artifacts("research-team-001")

if result["status"] == "success":
    print(f"✅ Artifacts collected!")
    print(f"📁 Path: {result['artifacts_path']}")
    print(f"👥 Instances: {result['instances_count']}")

    # Print team summary
    summary = result["summary"]
    print(f"⏱️  Duration: {summary['total_execution_time_seconds']}s")
    print(f"💰 Total cost: ${summary['total_cost']:.2f}")
    print(f"📊 Total tokens: {summary['total_tokens']:,}")
else:
    print(f"❌ Error: {result['error']}")
```

### Example 2: Accessing Collected Artifacts Programmatically

```python
import json
from pathlib import Path

result = collect_team_artifacts("research-team-001")

if result["status"] == "success":
    artifacts_path = Path(result["artifacts_path"])

    # Load metadata
    metadata = json.loads((artifacts_path / "metadata.json").read_text())

    # Iterate through instances
    for instance_info in result["instances"]:
        instance_id = instance_info["instance_id"]
        instance_artifacts = artifacts_path / "instances" / instance_id

        # Read output transcript
        output_log = instance_artifacts / "output.log"
        if output_log.exists():
            lines = output_log.read_text().splitlines()
            print(f"{instance_id}: {len(lines)} output lines")

        # List workspace files
        workspace = instance_artifacts / "workspace"
        if workspace.exists():
            files = list(workspace.rglob("*"))
            print(f"{instance_id}: {len(files)} workspace files")
```

### Example 3: Finding Artifacts from Previous Sessions

```python
import json
from pathlib import Path
from datetime import datetime, timedelta

# Find artifacts from the last 24 hours
artifacts_dir = Path("artifacts")
cutoff_time = datetime.now() - timedelta(days=1)

for session_dir in artifacts_dir.iterdir():
    # Parse timestamp from directory name: 2025-11-06_14-32-45-team-id
    parts = session_dir.name.split("-")
    if len(parts) >= 3:
        date_part = parts[0]  # 2025-11-06
        time_part = parts[1]  # 14-32-45

        timestamp_str = f"{date_part} {time_part.replace('-', ':')}"
        session_time = datetime.fromisoformat(timestamp_str)

        if session_time > cutoff_time:
            metadata = json.loads(
                (session_dir / "metadata.json").read_text()
            )
            print(f"Found: {session_dir.name}")
            print(f"Instances: {len(metadata['instances'])}")
```

### Example 4: Team Spawn with Artifact Collection

```python
from orchestrator.instance_manager import InstanceManager

async def run_team_with_artifacts():
    manager = InstanceManager(config)
    team_session_id = "analysis-team-001"

    # Spawn coordinator
    coordinator_result = await manager.spawn_claude(
        name="coordinator",
        role="architect",
        parent_instance_id=None,
    )
    coordinator_id = coordinator_result["instance_id"]

    # Spawn team members
    team_members = [
        {"name": "analyzer", "role": "data_scientist"},
        {"name": "developer", "role": "backend_developer"},
        {"name": "writer", "role": "tech_writer"},
    ]

    for member in team_members:
        member["parent_instance_id"] = coordinator_id
        await manager.spawn_claude(**member)

    # Team works...
    # (instances process requests, create outputs, etc.)

    # Collect artifacts when complete
    result = collect_team_artifacts(team_session_id)

    return result
```

### Example 5: Conditional Artifact Collection Based on Status

```python
result = collect_team_artifacts("team-001")

if result["status"] == "success":
    summary = result["summary"]

    if summary["all_completed"]:
        print("✅ All instances completed successfully")
    else:
        print("⚠️  Some instances had errors:")
        for error in summary["errors"]:
            print(f"  - {error}")

    # Calculate metrics
    avg_tokens = summary["total_tokens"] / summary["total_instances"]
    print(f"Average tokens per instance: {avg_tokens:,.0f}")

    # Check cost
    if summary["total_cost"] > 10.00:
        print(f"⚠️  High cost: ${summary['total_cost']:.2f}")
```

## Error Handling

### Common Errors and Solutions

#### Error: No instances found for team session

**Cause**: Team session ID doesn't match any spawned instances

**Solution**:
```python
# Ensure all instances use the same team_session_id
team_id = "my-team-001"

# Parent spawn
parent = await manager.spawn_claude(
    name="parent",
    role="architect"
)

# Child spawn - must set parent and use same team_id
child = await manager.spawn_claude(
    name="child",
    role="developer",
    parent_instance_id=parent["instance_id"]
)

# Both instances should have been initialized with team_id
# (implementation detail handled internally)
```

#### Error: Failed to create artifacts directory

**Cause**: No write permissions or invalid path

**Solution**:
```python
# Check permissions
import os
artifacts_dir = "./artifacts"
if not os.path.exists(artifacts_dir):
    os.makedirs(artifacts_dir, mode=0o755)

# Verify writable
test_file = artifacts_dir / "test.txt"
test_file.write_text("test")
test_file.unlink()
```

#### Error: Artifact collection timed out

**Cause**: Too many instances or large workspaces

**Solution**:
- Reduce number of instances per team
- Archive old artifact directories
- Run artifact collection on separate thread/task

## Tool Input Validation

### Valid Input Examples

```python
# ✅ All valid
collect_team_artifacts("team-001")
collect_team_artifacts("research-team-2025-11-06")
collect_team_artifacts("a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5")
collect_team_artifacts("my_team_123")
```

### Invalid Input Examples

```python
# ❌ All invalid
collect_team_artifacts("")                    # Empty string
collect_team_artifacts("team with spaces")   # Contains spaces
collect_team_artifacts("team@001")           # Special characters
collect_team_artifacts(None)                 # None/null
```

## Integration with Workflow Patterns

### Pattern 1: Sequential Stages

```python
async def multi_stage_workflow():
    stages = {
        "analysis": ["parser", "analyzer", "validator"],
        "processing": ["processor", "optimizer"],
        "reporting": ["summarizer", "writer"],
    }

    all_artifacts = {}

    for stage_name, roles in stages.items():
        team_id = f"workflow-{stage_name}"

        # Spawn team for stage
        instances = await spawn_team(roles, team_id)

        # Team executes...

        # Collect artifacts for this stage
        artifacts = collect_team_artifacts(team_id)
        all_artifacts[stage_name] = artifacts

    return all_artifacts
```

### Pattern 2: Hierarchical Teams

```python
async def hierarchical_workflow():
    # Root coordinator
    root = await spawn_claude(
        name="root",
        role="architect"
    )

    # Sub-coordinators reporting to root
    for domain in ["frontend", "backend", "devops"]:
        sub_coord = await spawn_claude(
            name=f"{domain}-lead",
            role="architect",
            parent_instance_id=root["instance_id"]
        )

        # Team members under sub-coordinator
        for i in range(3):
            await spawn_claude(
                name=f"{domain}-dev-{i}",
                role="backend_developer" if domain == "backend" else "frontend_developer",
                parent_instance_id=sub_coord["instance_id"]
            )

    # Collect all team artifacts
    result = collect_team_artifacts("hierarchical-project")

    # Artifacts preserve the hierarchy
    return result
```

## Performance Considerations

### Collection Time

- **Small teams** (1-5 instances): < 1 second
- **Medium teams** (5-20 instances): 1-5 seconds
- **Large teams** (20-100 instances): 5-30 seconds

Factors affecting speed:
- Number of instances (linear)
- Size of workspace files (linear)
- File system speed (I/O bound)
- Network latency (for remote artifact storage)

### Storage Requirements

Per instance:
- Workspace: typically 1-100MB
- Output transcript: 100KB-10MB
- Metadata: < 10KB

**Estimate for team of 10 instances**: 50-1000MB

## Deprecated and Related Tools

### Related MCP Tools

- `terminate_instance`: Terminate a single instance (triggers artifact preservation)
- `get_instance_status`: Get instance metadata (included in artifact response)
- `list_instance_files`: List files in instance workspace

### Legacy Methods (Pre-MCP)

Previous artifact preservation was manual. MCP tool provides automated collection.

## Testing the Tool

### Unit Test Example

```python
import pytest
from orchestrator.instance_manager import InstanceManager

@pytest.mark.asyncio
async def test_collect_team_artifacts_success():
    manager = InstanceManager(test_config)

    # Spawn team
    instances = await manager.spawn_multiple_instances([...])

    # Collect artifacts
    result = manager.collect_team_artifacts("test-team")

    assert result["status"] == "success"
    assert result["instances_count"] == len(instances)
    assert Path(result["artifacts_path"]).exists()
```

### Integration Test Example

```python
@pytest.mark.asyncio
async def test_full_workflow_with_artifacts():
    manager = InstanceManager(config)
    team_id = "integration-test"

    # Full workflow execution...

    # Verify artifacts collection
    result = manager.collect_team_artifacts(team_id)

    assert result["status"] == "success"
    assert result["summary"]["all_completed"]

    # Verify artifact structure
    artifacts_path = Path(result["artifacts_path"])
    assert (artifacts_path / "metadata.json").exists()
    assert (artifacts_path / "instances").is_dir()
```

## Monitoring and Logging

The `collect_team_artifacts` tool logs to the orchestrator log:

```
2025-11-06 14:32:45 INFO  - Collecting artifacts for team: research-team-001
2025-11-06 14:32:45 INFO  - Found 4 instances in team session
2025-11-06 14:32:46 INFO  - Created artifacts directory: /path/to/artifacts/2025-11-06_14-32-45-...
2025-11-06 14:32:47 INFO  - Artifact collection complete: 4/4 instances processed
2025-11-06 14:32:47 INFO  - Total artifacts size: 245.3 MB
```

View logs:

```bash
tail -f /tmp/madrox_logs/orchestrator.log | grep "artifacts"
```

## API Compatibility

### HTTP Mode

In HTTP/SSE transport mode, the tool is available via REST:

```bash
curl -X POST http://localhost:8001/tools/collect_team_artifacts \
  -H "Content-Type: application/json" \
  -d '{"team_session_id": "team-001"}'
```

### STDIO Mode

In STDIO transport mode (Codex CLI), the tool is available through standard MCP protocol.

## See Also

- [ARTIFACTS_FEATURE.md](ARTIFACTS_FEATURE.md) - Overall feature documentation
- [ARTIFACTS_CONFIGURATION.md](ARTIFACTS_CONFIGURATION.md) - Configuration options
- [ARTIFACTS_METADATA.md](ARTIFACTS_METADATA.md) - Metadata format reference
- [API_REFERENCE.md](API_REFERENCE.md) - Complete API documentation
