# Madrox Logging Architecture

Comprehensive logging and audit system for full instance observability and compliance.

## Overview

Madrox provides enterprise-grade logging with:
- Per-instance isolated logs
- System-wide audit trail
- Structured JSON format for queries
- Automatic rotation and retention
- Performance and cost tracking

## Directory Structure

```
/tmp/madrox_logs/
├── orchestrator.log              # Main orchestrator events
├── instances/
│   └── {instance_id}/
│       ├── instance.log         # Lifecycle events
│       ├── communication.jsonl  # Message I/O
│       ├── tmux_output.log      # Raw CLI captures
│       └── metadata.json        # Instance config
└── audit/
    └── audit_{YYYYMMDD}.jsonl   # Daily audit trail
```

## Log Types

### 1. Orchestrator Log

**Location:** `/tmp/madrox_logs/orchestrator.log`

**Format:** JSON (one per line)

**Rotation:** 10MB max, 5 backups

**Content:**
```json
{
  "timestamp": "2025-10-03T12:30:45",
  "level": "INFO",
  "logger": "orchestrator.instance_manager",
  "message": "Logging manager initialized: /tmp/madrox_logs",
  "module": "instance_manager",
  "function": "__init__",
  "line": 43
}
```

**Purpose:** System-level events, errors, and operational status.

### 2. Instance Logs

#### instance.log

**Location:** `/tmp/madrox_logs/instances/{instance_id}/instance.log`

**Format:** Human-readable text

**Rotation:** 5MB max, 3 backups

**Content:**
```
2025-10-03 12:30:45 - INFO - Instance created with role: general, type: claude
2025-10-03 12:30:58 - INFO - Instance initialization completed successfully
2025-10-03 12:35:20 - INFO - Instance terminated (force=False)
```

**Purpose:** Instance lifecycle tracking for human review.

#### communication.jsonl

**Location:** `/tmp/madrox_logs/instances/{instance_id}/communication.jsonl`

**Format:** JSON Lines (one event per line)

**Rotation:** No rotation (full history)

**Content:**
```jsonl
{"timestamp": "2025-10-03T12:31:10.123", "event_type": "message_sent", "message_id": "msg-001", "direction": "outbound", "content": "What is 2+2?"}
{"timestamp": "2025-10-03T12:31:12.456", "event_type": "message_received", "message_id": "msg-001", "direction": "inbound", "content": "4", "tokens": 8, "cost": 0.00008, "response_time": 2.333}
```

**Purpose:** Complete message exchange history with performance metrics.

**Fields:**
- `timestamp`: ISO 8601 timestamp
- `event_type`: `message_sent` or `message_received`
- `message_id`: Unique message identifier (correlates request/response)
- `direction`: `outbound` (to instance) or `inbound` (from instance)
- `content`: Full message text
- `tokens`: Estimated token count
- `cost`: Estimated cost in USD
- `response_time`: Seconds to complete (inbound only)

#### tmux_output.log

**Location:** `/tmp/madrox_logs/instances/{instance_id}/tmux_output.log`

**Format:** Raw text with timestamps

**Rotation:** Append-only (no rotation)

**Content:**
```
================================================================================
[2025-10-03T12:31:12.456789]
================================================================================
╭─ Welcome to Claude Code ────────────────────────────────────────────────────╮
│                                                                              │
│ Your helpful coding assistant                                               │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯

⏺ What is 2+2?

Thinking...

4

💬──────────────────────────────
```

**Purpose:** Full tmux pane output for debugging non-responsive or stuck instances.

#### metadata.json

**Location:** `/tmp/madrox_logs/instances/{instance_id}/metadata.json`

**Format:** JSON (single file)

**Content:**
```json
{
  "instance_id": "abc123-def456-789",
  "instance_name": "data-processor",
  "created_at": "2025-10-03T12:30:45.123456",
  "log_directory": "/tmp/madrox_logs/instances/abc123-def456-789"
}
```

**Purpose:** Instance identification and configuration reference.

### 3. Audit Trail

**Location:** `/tmp/madrox_logs/audit/audit_{YYYYMMDD}.jsonl`

**Format:** JSON Lines

**Rotation:** Daily at midnight, 30-day retention

**Content:**
```jsonl
{"timestamp": "2025-10-03T12:30:45", "level": "INFO", "event": "instance_spawn", "logger": "orchestrator.audit", "event_type": "instance_spawn", "instance_id": "abc123", "details": {"instance_name": "data-processor", "role": "general", "instance_type": "claude", "model": null, "enable_madrox": true, "bypass_isolation": false}}
{"timestamp": "2025-10-03T12:31:12", "level": "INFO", "event": "message_exchange", "logger": "orchestrator.audit", "event_type": "message_exchange", "instance_id": "abc123", "details": {"message_id": "msg-001", "message_length": 12, "response_length": 1, "tokens": 8, "cost": 0.00008, "response_time_seconds": 2.333}}
{"timestamp": "2025-10-03T12:35:20", "level": "INFO", "event": "instance_terminate", "logger": "orchestrator.audit", "event_type": "instance_terminate", "instance_id": "abc123", "details": {"instance_name": "data-processor", "force": false, "final_state": "terminated", "total_requests": 5, "total_tokens": 450, "total_cost": 0.0045, "uptime_seconds": 275.0}}
```

**Events Tracked:**

| Event Type | When | Details Captured |
|------------|------|------------------|
| `instance_spawn` | Instance created | name, role, type, model, config |
| `message_exchange` | Request/response completed | message_id, lengths, tokens, cost, time |
| `instance_terminate` | Instance shutdown | stats, uptime, final totals |

**Purpose:** Compliance, analytics, debugging, cost tracking.

## Query API

### Get Instance Logs

```python
# Retrieve specific log type
logs = await manager.get_instance_logs(
    instance_id="abc123-def456-789",
    log_type="communication",  # or "instance", "tmux_output"
    tail=100  # last 100 lines, 0 for all
)

# Returns: list of log line strings
```

### Query Audit Trail

```python
# Get recent audit events
audit_entries = await manager.get_audit_logs(
    since="2025-10-03T00:00:00",  # optional ISO timestamp
    limit=100  # max entries to return
)

# Returns: list of audit entry dicts
# [
#   {"timestamp": "...", "event_type": "instance_spawn", "instance_id": "...", ...},
#   {"timestamp": "...", "event_type": "message_exchange", "instance_id": "...", ...}
# ]
```

### List Logged Instances

```python
# Get all instances with logs (including terminated)
instances = await manager.list_logged_instances()

# Returns: list of instance metadata dicts
# [
#   {"instance_id": "abc123", "instance_name": "worker-1", "created_at": "...", ...},
#   {"instance_id": "def456", "instance_name": "worker-2", "created_at": "...", ...}
# ]
```

## Configuration

### Environment Variables

```bash
export LOG_DIR="/var/log/madrox"  # Custom log directory
export LOG_LEVEL="DEBUG"           # DEBUG, INFO, WARNING, ERROR
```

### Programmatic Configuration

```python
from src.orchestrator.instance_manager import InstanceManager

config = {
    "log_dir": "/var/log/madrox",
    "log_level": "INFO",
    # ... other config
}

manager = InstanceManager(config)
```

## Log Rotation Details

| Log Type | Max Size | Backup Count | Strategy | Retention |
|----------|----------|--------------|----------|-----------|
| orchestrator.log | 10MB | 5 | Size-based | ~50MB total |
| instance.log | 5MB | 3 | Size-based | ~15MB per instance |
| communication.jsonl | ∞ | N/A | None | Lifetime |
| tmux_output.log | ∞ | N/A | None | Lifetime |
| audit_*.jsonl | ∞ | 30 days | Time-based | 30 days |

## Use Cases

### 1. Debugging Stuck Instance

```python
# Get raw tmux output to see what's displayed
logs = await manager.get_instance_logs(
    instance_id="stuck-instance",
    log_type="tmux_output",
    tail=50
)

# Check last few lines for error states, prompts, etc.
for line in logs:
    print(line)
```

### 2. Cost Analysis

```python
# Query all message exchanges
audit = await manager.get_audit_logs(
    since="2025-10-01T00:00:00",
    limit=10000
)

# Calculate total cost
total_cost = sum(
    entry["details"]["cost"]
    for entry in audit
    if entry["event_type"] == "message_exchange"
)

print(f"Total cost last 3 days: ${total_cost:.4f}")
```

### 3. Performance Metrics

```python
# Analyze response times
audit = await manager.get_audit_logs(limit=1000)

response_times = [
    entry["details"]["response_time_seconds"]
    for entry in audit
    if entry["event_type"] == "message_exchange"
]

avg_response = sum(response_times) / len(response_times)
print(f"Average response time: {avg_response:.2f}s")
```

### 4. Compliance Audit

```python
# Get complete activity for specific instance
instance_id = "production-instance-001"

# Lifecycle
lifecycle_logs = await manager.get_instance_logs(
    instance_id=instance_id,
    log_type="instance",
    tail=0  # all logs
)

# Communication history
comm_logs = await manager.get_instance_logs(
    instance_id=instance_id,
    log_type="communication",
    tail=0
)

# Generate audit report
# - When spawned
# - What messages sent/received
# - When terminated
# - Total resource usage
```

### 5. Error Investigation

```python
# Find errors in orchestrator logs
# (manually search orchestrator.log for level="ERROR")

# Or query audit trail for failed operations
audit = await manager.get_audit_logs(limit=1000)

errors = [
    entry for entry in audit
    if "error" in entry.get("details", {})
]

for error in errors:
    print(f"Error in {error['instance_id']}: {error['details']['error']}")
```

## Structured Log Parsing

All JSON logs can be parsed with standard tools:

### jq (Command Line)

```bash
# Count messages per instance
cat audit_20251003.jsonl | \
  jq -s 'group_by(.instance_id) | map({instance: .[0].instance_id, count: length})'

# Get all costs
cat audit_20251003.jsonl | \
  jq -s 'map(select(.event_type == "message_exchange") | .details.cost) | add'

# Find slow responses (>5s)
cat audit_20251003.jsonl | \
  jq 'select(.event_type == "message_exchange" and .details.response_time_seconds > 5)'
```

### Python

```python
import json

# Load and analyze communication log
with open("/tmp/madrox_logs/instances/abc123/communication.jsonl") as f:
    messages = [json.loads(line) for line in f]

# Group by message_id to correlate requests/responses
exchanges = {}
for msg in messages:
    mid = msg["message_id"]
    if mid not in exchanges:
        exchanges[mid] = {}
    exchanges[mid][msg["direction"]] = msg

# Calculate stats
for mid, exchange in exchanges.items():
    if "inbound" in exchange and "outbound" in exchange:
        print(f"Request: {exchange['outbound']['content'][:50]}")
        print(f"Response time: {exchange['inbound']['response_time']}s")
        print(f"Cost: ${exchange['inbound']['cost']}")
        print()
```

## Best Practices

1. **Regular Monitoring**: Check `orchestrator.log` for ERROR entries
2. **Disk Space**: Monitor `/tmp/madrox_logs/` size (communication logs grow unbounded)
3. **Audit Retention**: Archive old audit logs if needed beyond 30 days
4. **Query Optimization**: Use `since` and `limit` parameters to reduce query overhead
5. **Debugging**: Always check `tmux_output.log` for stuck instance diagnosis
6. **Cost Tracking**: Query audit trail daily for cost monitoring
7. **Cleanup**: Terminated instances keep logs - manually delete old instance directories if needed

## Security Considerations

- **Sensitive Data**: Logs contain full message content - secure appropriately
- **Access Control**: Restrict filesystem access to `/tmp/madrox_logs/`
- **Retention**: Implement data retention policy for compliance
- **Sanitization**: Consider log sanitization for PII/secrets in production

## Troubleshooting

### Logs Not Appearing

```python
# Check logging manager initialization
assert manager.logging_manager is not None

# Verify log directory permissions
import os
log_dir = manager.logging_manager.log_dir
assert os.access(log_dir, os.W_OK)
```

### Missing Instance Logs

```python
# Check if instance directory exists
instance_dir = manager.logging_manager.instances_dir / instance_id
assert instance_dir.exists()

# Verify metadata file
metadata_file = instance_dir / "metadata.json"
assert metadata_file.exists()
```

### Large Log Files

```bash
# Check sizes
du -sh /tmp/madrox_logs/*

# Compress old logs
gzip /tmp/madrox_logs/instances/*/communication.jsonl

# Archive and delete old instances
tar -czf old_instances_$(date +%Y%m%d).tar.gz /tmp/madrox_logs/instances/
rm -rf /tmp/madrox_logs/instances/abc123*
```

## Future Enhancements

- [ ] Log compression for communication.jsonl
- [ ] Centralized log aggregation (ELK, Splunk)
- [ ] Real-time log streaming API
- [ ] Log analytics dashboard
- [ ] Automated anomaly detection
- [ ] Export to common formats (CSV, Parquet)
