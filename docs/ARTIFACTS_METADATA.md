# Artifacts Feature - Metadata Format Reference

## Overview

This document specifies the JSON schema and format for all metadata files created by the Artifacts feature. Metadata provides essential information about team composition, execution context, and results.

## Directory Structure Reference

Before diving into metadata formats, here's the complete directory structure:

```
artifacts/
├── {timestamp}-{team_session_id}/
│   ├── metadata.json              # Team-level metadata
│   ├── summary.md                 # Execution summary (human-readable)
│   └── instances/
│       ├── {instance_id}/
│       │   ├── metadata.json      # Instance-level metadata
│       │   ├── output.log         # Terminal output transcript
│       │   └── workspace/         # Copied workspace files
│       │       ├── *.py
│       │       ├── *.md
│       │       └── ...
│       └── {another_instance_id}/
│           ├── metadata.json
│           ├── output.log
│           └── workspace/
```

## Team-Level Metadata

### File: `metadata.json`

Located at: `artifacts/{timestamp}-{team_session_id}/metadata.json`

Complete specification of team execution metadata.

#### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "Team Artifacts Metadata",
  "description": "Complete metadata for a team orchestration session",
  "required": [
    "version",
    "created_at",
    "team_session_id",
    "total_instances",
    "instances",
    "execution_summary"
  ],
  "properties": {
    "version": {
      "type": "string",
      "description": "Metadata schema version",
      "enum": ["1.0.0", "2.0.0"]
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp when artifacts were collected"
    },
    "team_session_id": {
      "type": "string",
      "description": "Unique team session identifier",
      "minLength": 1
    },
    "total_instances": {
      "type": "integer",
      "description": "Total number of instances in team",
      "minimum": 1
    },
    "instances": {
      "type": "array",
      "description": "List of instance metadata objects",
      "items": {
        "$ref": "#/definitions/InstanceMetadata"
      }
    },
    "execution_summary": {
      "$ref": "#/definitions/ExecutionSummary"
    },
    "system_info": {
      "$ref": "#/definitions/SystemInfo"
    },
    "errors": {
      "type": "array",
      "description": "Collection of errors encountered",
      "items": {
        "type": "string"
      }
    }
  },
  "definitions": {
    "InstanceMetadata": {
      "type": "object",
      "required": [
        "instance_id",
        "name",
        "role",
        "model",
        "status",
        "created_at",
        "terminated_at"
      ],
      "properties": {
        "instance_id": {
          "type": "string",
          "description": "Unique instance identifier (UUID)"
        },
        "name": {
          "type": "string",
          "description": "Human-readable instance name"
        },
        "role": {
          "type": "string",
          "description": "Instance role",
          "enum": [
            "architect",
            "frontend_developer",
            "backend_developer",
            "data_scientist",
            "devops",
            "designer",
            "qa_engineer",
            "security",
            "project_manager",
            "tech_writer",
            "general"
          ]
        },
        "model": {
          "type": "string",
          "description": "Claude model used",
          "examples": ["claude-sonnet-4-5", "claude-opus-4-1", "claude-haiku-4-5"]
        },
        "status": {
          "type": "string",
          "description": "Final instance status",
          "enum": ["completed", "error", "timeout", "terminated", "running"]
        },
        "created_at": {
          "type": "string",
          "format": "date-time",
          "description": "Instance creation timestamp"
        },
        "terminated_at": {
          "type": "string",
          "format": "date-time",
          "description": "Instance termination timestamp"
        },
        "execution_time_seconds": {
          "type": "integer",
          "description": "Total execution time in seconds",
          "minimum": 0
        },
        "tokens_used": {
          "type": "integer",
          "description": "Total tokens consumed by instance",
          "minimum": 0
        },
        "cost": {
          "type": "number",
          "description": "Dollar cost of instance execution",
          "minimum": 0
        },
        "parent_instance_id": {
          "type": ["string", "null"],
          "description": "Parent instance ID (null for root)"
        },
        "children_count": {
          "type": "integer",
          "description": "Number of child instances spawned",
          "minimum": 0
        },
        "error_message": {
          "type": ["string", "null"],
          "description": "Error message if status is error"
        }
      }
    },
    "ExecutionSummary": {
      "type": "object",
      "description": "Aggregated execution statistics",
      "properties": {
        "total_instances": {
          "type": "integer",
          "minimum": 1
        },
        "completed_instances": {
          "type": "integer",
          "minimum": 0
        },
        "failed_instances": {
          "type": "integer",
          "minimum": 0
        },
        "total_tokens": {
          "type": "integer",
          "minimum": 0
        },
        "total_cost": {
          "type": "number",
          "minimum": 0
        },
        "execution_start": {
          "type": "string",
          "format": "date-time"
        },
        "execution_end": {
          "type": "string",
          "format": "date-time"
        },
        "total_execution_time_seconds": {
          "type": "integer",
          "minimum": 0
        },
        "average_tokens_per_instance": {
          "type": "number",
          "minimum": 0
        },
        "all_completed": {
          "type": "boolean",
          "description": "True if all instances completed successfully"
        }
      }
    },
    "SystemInfo": {
      "type": "object",
      "description": "System information at collection time",
      "properties": {
        "madrox_version": {
          "type": "string"
        },
        "python_version": {
          "type": "string"
        },
        "os": {
          "type": "string"
        },
        "hostname": {
          "type": "string"
        }
      }
    }
  }
}
```

#### Example: Team Metadata

```json
{
  "version": "1.0.0",
  "created_at": "2025-11-06T14:32:45.123456Z",
  "team_session_id": "research-team-001",
  "total_instances": 4,
  "instances": [
    {
      "instance_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "coordinator",
      "role": "architect",
      "model": "claude-sonnet-4-5",
      "status": "completed",
      "created_at": "2025-11-06T14:00:00Z",
      "terminated_at": "2025-11-06T14:32:00Z",
      "execution_time_seconds": 1920,
      "tokens_used": 45230,
      "cost": 0.45,
      "parent_instance_id": null,
      "children_count": 3,
      "error_message": null
    },
    {
      "instance_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "researcher",
      "role": "data_scientist",
      "model": "claude-sonnet-4-5",
      "status": "completed",
      "created_at": "2025-11-06T14:05:00Z",
      "terminated_at": "2025-11-06T14:28:00Z",
      "execution_time_seconds": 1380,
      "tokens_used": 32100,
      "cost": 0.32,
      "parent_instance_id": "550e8400-e29b-41d4-a716-446655440000",
      "children_count": 0,
      "error_message": null
    },
    {
      "instance_id": "550e8400-e29b-41d4-a716-446655440002",
      "name": "analyzer",
      "role": "architect",
      "model": "claude-sonnet-4-5",
      "status": "completed",
      "created_at": "2025-11-06T14:07:00Z",
      "terminated_at": "2025-11-06T14:29:00Z",
      "execution_time_seconds": 1320,
      "tokens_used": 28500,
      "cost": 0.29,
      "parent_instance_id": "550e8400-e29b-41d4-a716-446655440000",
      "children_count": 0,
      "error_message": null
    },
    {
      "instance_id": "550e8400-e29b-41d4-a716-446655440003",
      "name": "writer",
      "role": "tech_writer",
      "model": "claude-sonnet-4-5",
      "status": "completed",
      "created_at": "2025-11-06T14:10:00Z",
      "terminated_at": "2025-11-06T14:31:00Z",
      "execution_time_seconds": 1260,
      "tokens_used": 19170,
      "cost": 0.19,
      "parent_instance_id": "550e8400-e29b-41d4-a716-446655440000",
      "children_count": 0,
      "error_message": null
    }
  ],
  "execution_summary": {
    "total_instances": 4,
    "completed_instances": 4,
    "failed_instances": 0,
    "total_tokens": 125000,
    "total_cost": 1.25,
    "execution_start": "2025-11-06T14:00:00Z",
    "execution_end": "2025-11-06T14:32:00Z",
    "total_execution_time_seconds": 1920,
    "average_tokens_per_instance": 31250,
    "all_completed": true
  },
  "system_info": {
    "madrox_version": "1.2.0",
    "python_version": "3.11.5",
    "os": "darwin",
    "hostname": "nadavbarkai-mbp"
  },
  "errors": []
}
```

## Instance-Level Metadata

### File: `instances/{instance_id}/metadata.json`

Located at: `artifacts/{timestamp}-{team_session_id}/instances/{instance_id}/metadata.json`

Individual instance metadata for detailed tracking.

#### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "Instance Artifacts Metadata",
  "description": "Complete metadata for a single instance",
  "required": [
    "version",
    "instance_id",
    "name",
    "role",
    "model",
    "status",
    "created_at",
    "terminated_at"
  ],
  "properties": {
    "version": {
      "type": "string",
      "enum": ["1.0.0"]
    },
    "instance_id": {
      "type": "string",
      "description": "Unique instance identifier"
    },
    "name": {
      "type": "string",
      "description": "Instance name"
    },
    "role": {
      "type": "string",
      "enum": [
        "architect",
        "frontend_developer",
        "backend_developer",
        "data_scientist",
        "devops",
        "designer",
        "qa_engineer",
        "security",
        "project_manager",
        "tech_writer",
        "general"
      ]
    },
    "model": {
      "type": "string"
    },
    "status": {
      "type": "string",
      "enum": ["completed", "error", "timeout", "terminated", "running"]
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "terminated_at": {
      "type": "string",
      "format": "date-time"
    },
    "execution_time_seconds": {
      "type": "integer",
      "minimum": 0
    },
    "tokens_used": {
      "type": "integer",
      "minimum": 0
    },
    "cost": {
      "type": "number",
      "minimum": 0
    },
    "parent_instance_id": {
      "type": ["string", "null"]
    },
    "children_instance_ids": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "List of child instance IDs"
    },
    "workspace": {
      "type": "object",
      "description": "Workspace information",
      "properties": {
        "path": {
          "type": "string",
          "description": "Original workspace path"
        },
        "files_count": {
          "type": "integer",
          "description": "Number of files preserved",
          "minimum": 0
        },
        "total_size_bytes": {
          "type": "integer",
          "description": "Total size of workspace in bytes",
          "minimum": 0
        },
        "file_types": {
          "type": "object",
          "description": "File type distribution",
          "additionalProperties": {
            "type": "integer"
          }
        }
      }
    },
    "output": {
      "type": "object",
      "description": "Output transcript information",
      "properties": {
        "file": {
          "type": "string",
          "description": "Output log filename"
        },
        "lines": {
          "type": "integer",
          "description": "Number of output lines",
          "minimum": 0
        },
        "size_bytes": {
          "type": "integer",
          "description": "Size of output log",
          "minimum": 0
        }
      }
    },
    "error": {
      "type": ["string", "null"],
      "description": "Error message if failed"
    },
    "environment": {
      "type": "object",
      "description": "Environment information",
      "properties": {
        "timezone": {
          "type": "string"
        },
        "language": {
          "type": "string"
        }
      }
    }
  }
}
```

#### Example: Instance Metadata

```json
{
  "version": "1.0.0",
  "instance_id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "researcher",
  "role": "data_scientist",
  "model": "claude-sonnet-4-5",
  "status": "completed",
  "created_at": "2025-11-06T14:05:00Z",
  "terminated_at": "2025-11-06T14:28:00Z",
  "execution_time_seconds": 1380,
  "tokens_used": 32100,
  "cost": 0.32,
  "parent_instance_id": "550e8400-e29b-41d4-a716-446655440000",
  "children_instance_ids": [],
  "workspace": {
    "path": "/tmp/claude_orchestrator/550e8400-e29b-41d4-a716-446655440001",
    "files_count": 12,
    "total_size_bytes": 245832,
    "file_types": {
      ".py": 3,
      ".md": 2,
      ".json": 4,
      ".csv": 2,
      ".txt": 1
    }
  },
  "output": {
    "file": "output.log",
    "lines": 523,
    "size_bytes": 78450
  },
  "error": null,
  "environment": {
    "timezone": "UTC",
    "language": "en_US"
  }
}
```

## Team Manifest Schema

### File: `manifest.json` (Optional)

An index file listing all instances for quick scanning.

```json
{
  "version": "1.0.0",
  "team_session_id": "research-team-001",
  "timestamp": "2025-11-06T14:32:45.123456Z",
  "instances_index": [
    {
      "instance_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "coordinator",
      "role": "architect",
      "status": "completed",
      "tokens_used": 45230,
      "cost": 0.45,
      "metadata_file": "instances/550e8400-e29b-41d4-a716-446655440000/metadata.json"
    },
    {
      "instance_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "researcher",
      "role": "data_scientist",
      "status": "completed",
      "tokens_used": 32100,
      "cost": 0.32,
      "metadata_file": "instances/550e8400-e29b-41d4-a716-446655440001/metadata.json"
    }
  ],
  "summary": {
    "total_instances": 4,
    "completed": 4,
    "failed": 0,
    "total_cost": 1.25
  }
}
```

## Timestamp Format Convention

### Directory Naming

```
artifacts/
├── 2025-11-06_14-32-45-research-team-001/
├── 2025-11-06_15-10-20-analysis-stage/
└── 2025-11-05_09-45-15-legacy-project/
```

**Format**: `YYYY-MM-DD_HH-MM-SS-{team_session_id}`

- Date: `YYYY-MM-DD`
- Time: `HH-MM-SS` (24-hour, UTC)
- Separator: `-` (dash)
- Team ID: appended with `-`

### ISO 8601 Timestamps

All timestamps in JSON use ISO 8601 format with timezone:

```
"created_at": "2025-11-06T14:05:00.123456Z"
"created_at": "2025-11-06T14:05:00+00:00"
```

## Summary File Format

### File: `summary.md`

Human-readable markdown summary of team execution.

```markdown
# Team Artifacts Summary

**Team Session ID**: research-team-001
**Created**: 2025-11-06 at 14:32:45 UTC
**Status**: ✅ All instances completed successfully

## Execution Statistics

- **Total Instances**: 4
- **Completed**: 4 ✅
- **Failed**: 0
- **Total Tokens**: 125,000
- **Total Cost**: $1.25
- **Duration**: 32 minutes

## Instance Breakdown

| Name | Role | Status | Tokens | Cost | Duration |
|------|------|--------|--------|------|----------|
| coordinator | architect | ✅ | 45,230 | $0.45 | 32m |
| researcher | data_scientist | ✅ | 32,100 | $0.32 | 23m |
| analyzer | architect | ✅ | 28,500 | $0.29 | 22m |
| writer | tech_writer | ✅ | 19,170 | $0.19 | 21m |

## Hierarchy

```
coordinator (root)
├── researcher
├── analyzer
└── writer
```

## Artifacts Location

- **Path**: `/Users/nadavbarkai/dev/madrox/artifacts/2025-11-06_14-32-45-research-team-001`
- **Size**: 1.2 GB
- **Instance Count**: 4
- **Workspace Files**: 47
- **Output Lines**: 2,145

## Notable Files

### From Coordinator
- `analysis_results.json` - Analysis findings
- `final_report.md` - Executive summary

### From Researcher
- `data_analysis.ipynb` - Jupyter notebook
- `dataset.csv` - Processed dataset

### From Analyzer
- `architecture_diagram.md` - System design
- `recommendations.txt` - Implementation notes

### From Writer
- `documentation.md` - API documentation
- `user_guide.md` - User manual

## Errors

None encountered during execution.

---

*Generated by Madrox Artifacts System v1.0.0*
```

## Metadata Field Descriptions

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Metadata schema version (semantic versioning) |
| `instance_id` | string | UUID identifying the instance |
| `name` | string | Human-readable name (e.g., "researcher") |
| `role` | string | Predefined role from role system |
| `model` | string | Claude model identifier |
| `status` | string | Final instance status |
| `created_at` | ISO 8601 | Instance creation timestamp |
| `terminated_at` | ISO 8601 | Instance termination timestamp |

### Resource Fields

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `tokens_used` | integer | tokens | Total tokens consumed |
| `cost` | number | USD | Dollar cost of instance |
| `execution_time_seconds` | integer | seconds | Wall-clock execution time |

### Relationship Fields

| Field | Type | Description |
|-------|------|-------------|
| `parent_instance_id` | string \| null | ID of parent (null for root) |
| `children_count` | integer | Number of spawned children |
| `children_instance_ids` | string[] | List of child IDs |

### Workspace Fields

| Field | Type | Description |
|-------|------|-------------|
| `files_count` | integer | Number of workspace files preserved |
| `total_size_bytes` | integer | Total workspace size |
| `file_types` | object | Map of extension to count |

## Status Field Values

| Status | Meaning | Artifacts |
|--------|---------|-----------|
| `completed` | Normal termination, all work done | ✅ Full |
| `error` | Instance encountered error | ⚠️ Partial |
| `timeout` | Exceeded time limit | ⚠️ Partial |
| `terminated` | Manually stopped | ⚠️ Partial |
| `running` | Still executing (shouldn't appear in completed artifacts) | ⚠️ Partial |

## Role Enumerations

Standard roles defined by Madrox role system:

```python
ROLES = [
    "architect",           # System design and architecture
    "frontend_developer",  # React/Vue/Angular expertise
    "backend_developer",   # API and server development
    "data_scientist",      # ML/AI and data analysis
    "devops",             # Infrastructure and deployment
    "designer",           # UI/UX design
    "qa_engineer",        # Testing and quality
    "security",           # Security analysis
    "project_manager",    # Project coordination
    "tech_writer",        # Technical documentation
    "general"             # Default general purpose
]
```

## Accessing Metadata Programmatically

### Python Examples

#### Load Team Metadata

```python
import json
from pathlib import Path

artifacts_path = Path("artifacts/2025-11-06_14-32-45-research-team-001")
metadata = json.loads((artifacts_path / "metadata.json").read_text())

# Access team info
print(f"Team: {metadata['team_session_id']}")
print(f"Total instances: {metadata['total_instances']}")
print(f"Total cost: ${metadata['execution_summary']['total_cost']:.2f}")
```

#### Iterate Instances

```python
for instance in metadata['instances']:
    print(f"{instance['name']:20} | {instance['role']:20} | ${instance['cost']:.2f}")
```

#### Filter By Status

```python
failed_instances = [
    i for i in metadata['instances']
    if i['status'] != 'completed'
]

if failed_instances:
    print(f"Failed instances: {len(failed_instances)}")
```

#### Calculate Metrics

```python
total_tokens = metadata['execution_summary']['total_tokens']
num_instances = metadata['total_instances']
avg_tokens = total_tokens / num_instances

print(f"Average tokens per instance: {avg_tokens:,.0f}")
```

### Querying with jq

```bash
# Get all instance names
jq '.instances[].name' metadata.json

# Filter completed instances
jq '.instances[] | select(.status == "completed")' metadata.json

# Calculate total cost
jq '.execution_summary.total_cost' metadata.json

# Get coordinator instance
jq '.instances[] | select(.role == "architect" and .parent_instance_id == null)' metadata.json
```

## Version History

### Version 1.0.0 (Current)

- Initial schema definition
- Team and instance level metadata
- Execution summary statistics
- System information capture

### Version 2.0.0 (Planned)

Planned enhancements:
- Performance metrics (response times, memory usage)
- Resource utilization details
- Error categorization
- Artifact integrity checksums
- Compliance audit trail

## Validation

### Schema Validation

```python
import jsonschema

schema = json.loads(TEAM_METADATA_SCHEMA)
metadata = json.loads(metadata_file.read_text())

jsonschema.validate(metadata, schema)
print("✅ Valid metadata")
```

### Common Validation Issues

```
ERROR: 'version' is a required property
→ Ensure version field is present

ERROR: 'status' is not one of ['completed', 'error', ...]
→ Use valid status values from enumeration

ERROR: 123.456 is not of type 'integer' for field 'tokens_used'
→ Ensure numeric fields have correct types
```

## Privacy and Security

### Data Included

- Instance IDs and names
- Roles and models used
- Token counts and costs
- Execution timestamps
- Workspace file listing
- Output log contents

### Data NOT Included

- Actual prompt contents
- API keys or credentials
- Internal communication
- Raw response payloads (only summary)

### Recommendations

- Protect artifact directories with appropriate file permissions
- Exclude sensitive files from workspace patterns
- Archive old artifacts to secure storage
- Implement access controls for cost data

## Archival and Long-Term Storage

### Archive Format

When archiving artifacts:

```
artifacts/
└── archive/
    └── 2025-11/
        ├── 2025-11-06_14-32-45-research-team-001.tar.gz
        ├── 2025-11-06_15-10-20-analysis-stage.tar.gz
        └── ...
```

### Metadata for Archived Sessions

Keep uncompressed copy of metadata.json for indexing:

```
archive_index.json
{
  "archived_sessions": [
    {
      "team_session_id": "research-team-001",
      "archived_at": "2025-12-06T00:00:00Z",
      "archive_file": "2025-11/2025-11-06_14-32-45-research-team-001.tar.gz",
      "total_cost": 1.25,
      "instances_count": 4
    }
  ]
}
```

## Related Documentation

- [ARTIFACTS_FEATURE.md](ARTIFACTS_FEATURE.md) - Feature overview
- [ARTIFACTS_MCP_TOOLS.md](ARTIFACTS_MCP_TOOLS.md) - Tool reference
- [ARTIFACTS_CONFIGURATION.md](ARTIFACTS_CONFIGURATION.md) - Configuration guide
