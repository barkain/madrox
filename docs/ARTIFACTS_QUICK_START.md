# Artifacts Feature - Quick Start Guide

## TL;DR - 5-Minute Setup

### 1. Enable Artifacts (One Line)

```bash
export ARTIFACTS_DIR=./artifacts
python run_orchestrator.py
```

### 2. Spawn a Team

```python
# In Claude Code or any instance
result = await manager.spawn_multiple_instances([
    {"name": "coordinator", "role": "architect"},
    {"name": "dev1", "role": "backend_developer"},
    {"name": "dev2", "role": "backend_developer"},
])
```

### 3. Collect Artifacts

```python
# After team completes
artifacts = collect_team_artifacts("my-team-001")
print(f"✅ Saved to: {artifacts['artifacts_path']}")
```

### 4. Access Results

```bash
# View results
ls -la artifacts/2025-11-06_14-32-45-my-team-001/
cat artifacts/2025-11-06_14-32-45-my-team-001/summary.md
```

---

## Step-by-Step Tutorial

### Step 1: Configure Artifacts Storage

Choose where to store team artifacts:

```bash
# Option A: Local directory (development)
export ARTIFACTS_DIR=./artifacts

# Option B: Dedicated location (production)
export ARTIFACTS_DIR=/var/lib/madrox/artifacts

# Option C: Cloud storage (advanced)
export ARTIFACTS_DIR=/mnt/s3/madrox/artifacts
```

Create the directory if needed:
```bash
mkdir -p $ARTIFACTS_DIR
```

### Step 2: Start Madrox Server

```bash
cd ~/dev/madrox
python run_orchestrator.py
```

You should see:
```
INFO: Artifacts feature initialized
INFO: Artifacts directory: ./artifacts
```

### Step 3: Spawn a Team

In your Claude Code instance or script:

```python
from orchestrator.instance_manager import InstanceManager

manager = InstanceManager(config)

# Spawn team
results = await manager.spawn_multiple_instances([
    {
        "name": "lead",
        "role": "architect"
    },
    {
        "name": "backend",
        "role": "backend_developer"
    },
    {
        "name": "qa",
        "role": "qa_engineer"
    }
])

for result in results["spawned"]:
    print(f"✅ Spawned: {result['name']} ({result['instance_id']})")
```

### Step 4: Let Team Work

Team instances execute their assigned tasks:
- Create files in workspace
- Process data
- Generate outputs
- Communicate with parent

### Step 5: Collect Artifacts

When complete, collect all team outputs:

```python
result = collect_team_artifacts("my-team-session")

if result["status"] == "success":
    print(f"✅ Team artifacts collected")
    print(f"📁 Location: {result['artifacts_path']}")
    print(f"👥 Instances: {result['instances_count']}")
    print(f"💰 Total cost: ${result['summary']['total_cost']:.2f}")
else:
    print(f"❌ Error: {result['error']}")
```

### Step 6: Explore Artifacts

```bash
# View directory structure
tree artifacts/2025-11-06_14-32-45-my-team-session

# Read summary
cat artifacts/2025-11-06_14-32-45-my-team-session/summary.md

# List instance outputs
ls artifacts/2025-11-06_14-32-45-my-team-session/instances/

# View specific instance output
head -50 artifacts/2025-11-06_14-32-45-my-team-session/instances/*/output.log

# Check what files were created
find artifacts/2025-11-06_14-32-45-my-team-session -name "*.md" -o -name "*.json"
```

---

## Common Tasks

### Task 1: Extract Specific Instance Output

```python
import json
from pathlib import Path

artifacts_path = "artifacts/2025-11-06_14-32-45-my-team-session"
instance_id = "550e8400-e29b-41d4-a716-446655440001"

# Read instance metadata
metadata = json.loads(
    Path(f"{artifacts_path}/instances/{instance_id}/metadata.json").read_text()
)

print(f"Instance: {metadata['name']}")
print(f"Role: {metadata['role']}")
print(f"Tokens: {metadata['tokens_used']:,}")
print(f"Cost: ${metadata['cost']:.2f}")

# Read output transcript
output = Path(f"{artifacts_path}/instances/{instance_id}/output.log").read_text()
print(f"\nOutput:\n{output[:500]}...")  # First 500 chars
```

### Task 2: Find Cost Breakdown

```python
import json
from pathlib import Path

artifacts_path = "artifacts/2025-11-06_14-32-45-my-team-session"
metadata = json.loads(Path(f"{artifacts_path}/metadata.json").read_text())

print("Cost Breakdown")
print("=" * 50)

for instance in metadata['instances']:
    print(f"{instance['name']:20} | ${instance['cost']:.2f}")

print("-" * 50)
print(f"{'TOTAL':20} | ${metadata['execution_summary']['total_cost']:.2f}")
```

### Task 3: Generate Report

```python
import json
from pathlib import Path
from datetime import datetime

artifacts_path = Path("artifacts/2025-11-06_14-32-45-my-team-session")
metadata = json.loads((artifacts_path / "metadata.json").read_text())
summary = metadata['execution_summary']

report = f"""
# Team Execution Report
Generated: {datetime.now().isoformat()}

## Team Info
- Session ID: {metadata['team_session_id']}
- Total Instances: {summary['total_instances']}
- All Completed: {summary['all_completed']}

## Performance
- Total Duration: {summary['total_execution_time_seconds']} seconds
- Total Tokens: {summary['total_tokens']:,}
- Total Cost: ${summary['total_cost']:.2f}

## Instance Details
"""

for inst in metadata['instances']:
    report += f"""
- **{inst['name']}** ({inst['role']})
  - Status: {inst['status']}
  - Tokens: {inst['tokens_used']:,}
  - Cost: ${inst['cost']:.2f}
  - Duration: {inst['execution_time_seconds']}s
"""

print(report)

# Save report
(artifacts_path / "REPORT.md").write_text(report)
print(f"Report saved to {artifacts_path}/REPORT.md")
```

### Task 4: Archive Old Artifacts

```bash
# Find artifacts older than 30 days
find ./artifacts -maxdepth 1 -type d -mtime +30

# Compress to tar.gz
tar -czf ./artifacts_archive/old_artifacts.tar.gz \
    ./artifacts/2025-10-*

# Remove original
rm -rf ./artifacts/2025-10-*
```

### Task 5: Compare Two Team Sessions

```python
import json
from pathlib import Path

def load_metadata(path):
    return json.loads(Path(f"{path}/metadata.json").read_text())

session1 = load_metadata("artifacts/2025-11-06_14-32-45-team-a")
session2 = load_metadata("artifacts/2025-11-06_15-10-20-team-b")

print("Session Comparison")
print("=" * 60)
print(f"Session ID          | {session1['team_session_id']:30} | {session2['team_session_id']:30}")
print(f"Instances          | {session1['total_instances']:30} | {session2['total_instances']:30}")
print(f"Total Tokens       | {session1['execution_summary']['total_tokens']:30} | {session2['execution_summary']['total_tokens']:30}")
print(f"Total Cost         | ${session1['execution_summary']['total_cost']:<29.2f} | ${session2['execution_summary']['total_cost']:<29.2f}")
```

---

## Configuration Variations

### For Development (Lots of Artifacts)

```bash
# Save everything, keep for a week
export ARTIFACTS_DIR=./artifacts
export ARTIFACTS_ENABLED=true
export ARTIFACTS_COMPRESS=false
export ARTIFACTS_RETENTION_DAYS=7
export ARTIFACTS_PATTERNS="*"
```

### For Production (Space-Constrained)

```bash
# Selective archival, auto-compress, cleanup old
export ARTIFACTS_DIR=/var/artifacts
export ARTIFACTS_ENABLED=true
export ARTIFACTS_COMPRESS=true
export ARTIFACTS_RETENTION_DAYS=30
export ARTIFACTS_MAX_SIZE_GB=500
export ARTIFACTS_PATTERNS="*.py,*.md,*.json,requirements.txt"
export ARTIFACTS_EXCLUDE_PATTERNS=".git,__pycache__,node_modules"
```

### For Research (Preserve Everything)

```bash
# Keep all outputs, no auto-delete
export ARTIFACTS_DIR=/research/artifacts
export ARTIFACTS_ENABLED=true
export ARTIFACTS_COMPRESS=false
export ARTIFACTS_RETENTION_DAYS=null
export ARTIFACTS_PATTERNS="*"
export ARTIFACTS_EXCLUDE_PATTERNS=""
```

---

## Troubleshooting

### Problem: Artifacts directory empty

```bash
# Check configuration
echo $ARTIFACTS_DIR

# Verify directory exists and is writable
touch $ARTIFACTS_DIR/test.txt && rm $ARTIFACTS_DIR/test.txt

# Check orchestrator is running
curl http://localhost:8001/status

# Check logs
tail -f /tmp/madrox_logs/orchestrator.log | grep artifacts
```

### Problem: Missing instance artifacts

**Symptom**: Some instances missing from artifacts

```python
# Verify instances were tracked
result = collect_team_artifacts("my-team")
print(f"Expected: 5, Got: {result['instances_count']}")

# Check which instances are missing
# Review logs for "Failed to preserve artifacts" messages
```

**Solution**:
- Ensure all instances use same `team_session_id`
- Check instance workspace directory exists
- Verify disk space available

### Problem: Artifacts too large

**Symptom**: Disk space rapidly consumed

```bash
# Check artifact sizes
du -sh artifacts/*

# Find largest instances
du -s artifacts/*/instances/* | sort -rn | head
```

**Solution**:
```bash
# Enable compression
export ARTIFACTS_COMPRESS=true

# Or reduce retention
export ARTIFACTS_RETENTION_DAYS=14

# Or exclude patterns
export ARTIFACTS_EXCLUDE_PATTERNS=".git,node_modules,__pycache__"
```

---

## Example: End-to-End Workflow

### Research Paper Analysis Team

```python
import asyncio
from orchestrator.instance_manager import InstanceManager

async def analyze_research_paper():
    # Setup
    manager = InstanceManager(config)
    team_id = "paper-analysis-001"

    # Spawn team
    print("📚 Spawning research team...")
    results = await manager.spawn_multiple_instances([
        {
            "name": "paper-reader",
            "role": "data_scientist",
            "parent_instance_id": None
        },
        {
            "name": "methodology-analyst",
            "role": "architect",
            "parent_instance_id": None
        },
        {
            "name": "implementation-planner",
            "role": "backend_developer",
            "parent_instance_id": None
        },
        {
            "name": "documentation-writer",
            "role": "tech_writer",
            "parent_instance_id": None
        }
    ])

    # Wait for completion
    print("⏳ Team working on analysis...")
    await asyncio.sleep(300)  # Wait 5 minutes

    # Collect artifacts
    print("📦 Collecting team artifacts...")
    artifacts = collect_team_artifacts(team_id)

    if artifacts["status"] == "success":
        print(f"✅ Success!")
        print(f"📁 Path: {artifacts['artifacts_path']}")
        print(f"👥 Instances: {artifacts['instances_count']}")
        print(f"💰 Cost: ${artifacts['summary']['total_cost']:.2f}")

        # Load and print summary
        import json
        from pathlib import Path

        metadata = json.loads(
            Path(artifacts['artifacts_path']) / "metadata.json"
        ).read_text()

        print("\n📊 Instance Details:")
        for inst in metadata['instances']:
            print(f"  - {inst['name']:25} | {inst['role']:20} | ${inst['cost']:.2f}")

        return artifacts['artifacts_path']
    else:
        print(f"❌ Error: {artifacts['error']}")
        return None

# Run workflow
if __name__ == "__main__":
    artifacts_path = asyncio.run(analyze_research_paper())
```

---

## Next Steps

1. **Basic Setup**: Follow the 5-minute setup above
2. **Spawn Team**: Create your first multi-instance team
3. **Explore Results**: Check the artifacts directory structure
4. **Read Full Docs**: See [ARTIFACTS_FEATURE.md](ARTIFACTS_FEATURE.md) for detailed info
5. **Customize**: Adjust configuration in [ARTIFACTS_CONFIGURATION.md](ARTIFACTS_CONFIGURATION.md)
6. **Integrate**: Use MCP tools per [ARTIFACTS_MCP_TOOLS.md](ARTIFACTS_MCP_TOOLS.md)

---

## API Cheat Sheet

```python
# Enable artifacts
export ARTIFACTS_DIR=./artifacts

# Collect team artifacts
result = collect_team_artifacts("team-session-id")

# Check result
if result["status"] == "success":
    path = result["artifacts_path"]
    count = result["instances_count"]
    cost = result["summary"]["total_cost"]

# Common metadata access
import json
from pathlib import Path

metadata = json.loads(
    Path(result["artifacts_path"]) / "metadata.json").read_text()
)

# Iterate instances
for inst in metadata['instances']:
    print(inst['name'], inst['cost'])
```

---

## Frequently Asked Questions

### Q: When should I call collect_team_artifacts?

**A**: After all team instances are done working. Usually:
- When coordinator finishes
- When all child instances complete
- On workflow cleanup

### Q: Can I collect artifacts multiple times?

**A**: Yes. Each call creates a new timestamped directory. Good for saving intermediate checkpoints.

### Q: Will artifacts be deleted automatically?

**A**: Only if `ARTIFACTS_RETENTION_DAYS` is set. Otherwise, artifacts persist indefinitely.

### Q: How do I share artifacts with others?

**A**:
- Compress: `tar -gz artifacts/{session_dir}`
- Copy files to shared drive
- Archive to cloud storage
- Generate summary report

### Q: Can I access artifacts while instances are still running?

**A**: Not recommended. Workspace copying might conflict with active writes. Best to collect after instances terminate.

---

## Performance Tips

1. **Filter files**: Use `ARTIFACTS_PATTERNS` to exclude unnecessary files
2. **Compression**: Enable for production deployments
3. **Lazy loading**: Load metadata.json before reading workspaces
4. **Batch collection**: Collect multiple sessions in one operation
5. **Archive old**: Move old artifacts to cold storage

---

See Also:
- [ARTIFACTS_FEATURE.md](ARTIFACTS_FEATURE.md) - Complete feature documentation
- [ARTIFACTS_MCP_TOOLS.md](ARTIFACTS_MCP_TOOLS.md) - API tool reference
- [ARTIFACTS_CONFIGURATION.md](ARTIFACTS_CONFIGURATION.md) - Configuration options
- [ARTIFACTS_METADATA.md](ARTIFACTS_METADATA.md) - Metadata format reference
