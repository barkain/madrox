# Madrox API Endpoints

## Network Hierarchy Endpoint

### GET /network/hierarchy

Get complete network topology showing all instances and their parent-child relationships.

**Response:**
```json
{
  "total_instances": 3,
  "root_instances": [
    {
      "id": "48cbbfda-f75a-43b2-9bc0-a1ff173b1dee",
      "name": "parent-coordinator-aka-NetworkRoot",
      "type": "claude",
      "role": "architect",
      "state": "running",
      "parent_id": null,
      "children": [
        {
          "id": "1e65b11a-807f-40a0-a226-c87af93cdd70",
          "name": "child-worker-1-aka-Analyzer",
          "type": "claude",
          "role": "security_analyst",
          "state": "running",
          "parent_id": "48cbbfda-f75a-43b2-9bc0-a1ff173b1dee",
          "children": [],
          "created_at": "2025-10-03T10:59:47.198432+00:00",
          "total_tokens": 0,
          "total_cost": 0.0,
          "request_count": 0
        }
      ],
      "created_at": "2025-10-03T10:59:25.422151+00:00",
      "total_tokens": 0,
      "total_cost": 0.0,
      "request_count": 0
    }
  ],
  "all_instances": [...]
}
```

**Fields:**
- `total_instances`: Total number of active instances
- `root_instances`: Array of instances with no parent (top-level coordinators)
- `all_instances`: Flat array of all instances for easy iteration

**Instance Object:**
- `id`: Instance UUID
- `name`: Human-readable instance name
- `type`: Instance type (claude, codex)
- `role`: Assigned role (architect, security_analyst, etc.)
- `state`: Current state (running, idle, busy, terminated)
- `parent_id`: Parent instance ID (null for root instances)
- `children`: Array of child instances (recursive structure)
- `created_at`: ISO timestamp of creation
- `total_tokens`: Total tokens used
- `total_cost`: Total cost in USD
- `request_count`: Number of requests processed

**Example:**
```bash
curl "http://localhost:8001/network/hierarchy"
```

**Use Cases:**
- Visualize multi-agent network topology
- Monitor hierarchical coordination patterns
- Track resource usage across instance tree
- Debug parent-child communication issues

---

## Log Streaming Endpoints

Madrox provides HTTP endpoints to access logging data from the orchestrator and instances.

### GET /logs/audit

Get audit trail logs from the Madrox orchestrator.

**Query Parameters:**
- `limit` (int, optional): Maximum number of log entries to return. Default: 100
- `since` (str, optional): ISO timestamp to filter logs from a specific time

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2025-10-03T13:45:59.868017",
      "level": "INFO",
      "event": "instance_spawn",
      "instance_id": "9e240be1-3989-47a1-b3a0-59a616d7923f",
      "details": {
        "instance_name": "logging-test-aka-LogVerifier",
        "role": "general"
      }
    }
  ],
  "total": 2,
  "file": "/tmp/madrox_logs/audit/audit_20251003.jsonl"
}
```

**Example:**
```bash
curl "http://localhost:8001/logs/audit?limit=10"
```

### GET /logs/instances/{instance_id}

Get instance-specific logs (human-readable format).

**Path Parameters:**
- `instance_id` (str, required): Instance UUID

**Query Parameters:**
- `limit` (int, optional): Maximum number of log entries. Default: 100
- `since` (str, optional): ISO timestamp filter

**Response:**
```json
{
  "logs": [
    "2025-10-03 13:45:59 - INFO - Instance created with role: general",
    "2025-10-03 13:46:11 - INFO - Instance initialization completed"
  ],
  "total": 3,
  "instance_id": "9e240be1-3989-47a1-b3a0-59a616d7923f",
  "file": "/tmp/madrox_logs/instances/9e240be1.../instance.log"
}
```

**Example:**
```bash
curl "http://localhost:8001/logs/instances/9e240be1-3989-47a1-b3a0-59a616d7923f?limit=50"
```

### GET /logs/communication/{instance_id}

Get communication logs for a specific instance (structured JSON format).

**Path Parameters:**
- `instance_id` (str, required): Instance UUID

**Query Parameters:**
- `limit` (int, optional): Maximum number of log entries. Default: 100
- `since` (str, optional): ISO timestamp filter

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2025-10-03T13:45:59.867838",
      "event_type": "unknown",
      "message": "Instance created with role: general, type: claude"
    }
  ],
  "total": 3,
  "instance_id": "9e240be1-3989-47a1-b3a0-59a616d7923f",
  "file": "/tmp/madrox_logs/instances/9e240be1.../communication.jsonl"
}
```

**Example:**
```bash
curl "http://localhost:8001/logs/communication/9e240be1-3989-47a1-b3a0-59a616d7923f"
```

## Use Cases

### Monitor Network Activity
```bash
# Get recent audit logs
curl "http://localhost:8001/logs/audit?limit=20"
```

### Debug Instance Issues
```bash
# Get instance logs
INSTANCE_ID="9e240be1-3989-47a1-b3a0-59a616d7923f"
curl "http://localhost:8001/logs/instances/$INSTANCE_ID"
```

### Track Communication Patterns
```bash
# Get communication logs with timestamp filter
curl "http://localhost:8001/logs/communication/$INSTANCE_ID?since=2025-10-03T13:00:00"
```

### Real-Time Monitoring Script
```bash
#!/bin/bash
# Monitor audit logs in real-time
while true; do
  curl -s "http://localhost:8001/logs/audit?limit=5" | jq '.logs[-1]'
  sleep 2
done
```

## Error Responses

**404 Not Found:**
```json
{
  "detail": "No logs found for instance {instance_id}"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Error reading log file: {error_message}"
}
```
