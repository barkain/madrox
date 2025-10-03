# Madrox API Endpoints

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
