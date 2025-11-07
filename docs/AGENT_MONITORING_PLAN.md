# Enhanced Agent Monitoring System - Implementation Plan

**Created**: 2025-01-15
**Status**: Planning Phase
**Branch**: `feature/agent-activity-monitoring`

## Overview

Build an **independent monitoring service** that incrementally reads agent logs and produces structured summaries with "on track" inference using Claude Haiku 4.5. This will eventually replace the existing Knark monitoring system but is implemented as a standalone system on the main branch.

## Requirements

### User Requirements
- **Visibility**: Real-time insight into what each Madrox agent is doing
- **Activity Summary**: Concrete, concise statement of current agent activity
- **On-Track Inference**: Determine if agent is aligned with assigned task
- **Incremental Processing**: Read logs incrementally without reprocessing

### Technical Requirements
- **Polling Interval**: 10-15 seconds
- **LLM Model**: Claude Haiku 4.5 (~$0.001 per summary)
- **UI Integration**: WebSocket endpoint for real-time updates
- **Architecture**: Independent service (eventual Knark replacement)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 Independent Monitoring Process               │
│  ┌────────────────────┐        ┌──────────────────────┐     │
│  │ IncrementalReader  │───────>│   SummaryGenerator   │     │
│  │ (reads new logs)   │        │   (LLM-based)        │     │
│  └────────────────────┘        └──────────────────────┘     │
│           │                              │                    │
│           v                              v                    │
│  ┌────────────────────┐        ┌──────────────────────┐     │
│  │  PositionTracker   │        │  StructuredSummary   │     │
│  │  (cursor state)    │        │  (JSON storage)      │     │
│  └────────────────────┘        └──────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                           │
                           v
               ┌───────────────────────┐
               │ Existing Madrox Logs  │
               │ - tmux_output.log     │
               │ - instance.log        │
               │ - communication.jsonl │
               └───────────────────────┘
```

## Data Models

### AgentSummary

```python
@dataclass
class AgentSummary:
    """Real-time agent activity summary."""
    instance_id: str
    instance_name: str
    timestamp: datetime
    current_activity: str  # Concise statement (1-2 sentences)
    on_track_status: OnTrackStatus  # Enum
    confidence_score: float  # 0.0-1.0

    # Contextual metadata
    assigned_task: str
    parent_instance_id: str | None
    role: str

    # Activity indicators
    last_tool_used: str | None
    recent_tools: list[str]  # Last 5 tools
    output_preview: str  # Last 200 chars
    idle_duration_seconds: float

    # Alignment indicators
    drift_reasons: list[str]
    alignment_keywords: list[str]

    # Recommendations
    recommended_action: str | None
```

### OnTrackStatus

```python
class OnTrackStatus(Enum):
    ON_TRACK = "on_track"      # Working on assigned task
    DRIFTING = "drifting"      # Minor deviation
    OFF_TRACK = "off_track"    # Significant misalignment
    BLOCKED = "blocked"        # Stuck/waiting/error
    UNKNOWN = "unknown"        # Insufficient data
```

### LogPosition

```python
@dataclass
class LogPosition:
    """Tracks reading position for incremental consumption."""
    instance_id: str
    log_type: str  # "tmux_output", "instance", "communication"
    file_path: str
    last_byte_offset: int  # File position for seeking
    last_line_number: int
    last_read_timestamp: datetime
    checksum: str  # MD5 for log rotation detection
```

## Implementation Phases

### Phase 1: Core Infrastructure

**Files to Create:**
- `src/orchestrator/monitoring/__init__.py`
- `src/orchestrator/monitoring/models.py`
- `src/orchestrator/monitoring/position_tracker.py`
- `src/orchestrator/monitoring/log_reader.py`
- `src/orchestrator/monitoring/config.py`

**Key Features:**
- Data models for summaries and position tracking
- Byte-offset based incremental reading
- Log rotation detection with checksums
- JSON-based position persistence in `/tmp/madrox_logs/monitoring_state/`

**Deliverables:**
- Position tracking persists across restarts
- Efficient log reading without re-reading entire files
- Handles log rotation gracefully

### Phase 2: LLM Integration

**Files to Create:**
- `src/orchestrator/monitoring/summary_generator.py`

**Key Features:**
- Claude Haiku 4.5 API integration
- Prompt engineering for activity analysis
- Structured JSON output parsing
- "On track" inference with confidence scores
- Retry logic and error handling

**Prompt Strategy:**
```
Analyze this agent's recent activity:
- Agent Context: Role, assigned task, parent agent
- Recent Terminal Output: Last N lines
- Previous Summary: For context continuity

Analysis Required:
1. Current Activity (1-2 sentences)
2. On-Track Status (ON_TRACK/DRIFTING/OFF_TRACK/BLOCKED/UNKNOWN)
3. Tool Usage (identify tools being used)
4. Drift Indicators (if not on track, explain why)
5. Recommended Action (what should supervisor do?)

Output Format: JSON
```

**Deliverables:**
- Semantic understanding of agent activity
- Accurate on-track inference
- Actionable drift indicators

### Phase 3: Background Monitoring Service

**Files to Create:**
- `src/orchestrator/monitoring/service.py`

**Files to Modify:**
- `src/orchestrator/instance_manager.py` - Add MonitoringService initialization

**Key Features:**
- Asyncio background polling loop (10-15 second intervals)
- Parallel instance processing with `asyncio.gather()`
- Summary persistence:
  - `/tmp/madrox_logs/summaries/{instance_id}/latest_summary.json`
  - `/tmp/madrox_logs/summaries/{instance_id}/summary_history.jsonl`
- MCP tool exposure:
  - `get_agent_summary(instance_id, include_history=False)`
  - `get_all_agent_summaries()`

**Monitoring Loop:**
1. Get all active instances (not terminated/error)
2. For each instance in parallel:
   - Read new log content via IncrementalLogReader
   - Skip if no new content
   - Generate summary via SummaryGenerator
   - Store summary in memory and disk
   - Emit summary event for WebSocket
3. Wait for next poll interval (10-15 seconds)

**Deliverables:**
- Automatic background monitoring
- MCP tools for accessing summaries
- Historical summary tracking

### Phase 4: WebSocket Streaming

**Files to Modify:**
- `src/orchestrator/server.py` - Add `/ws/agent_summaries` endpoint

**Key Features:**
- WebSocket endpoint: `ws://localhost:8001/ws/agent_summaries`
- Real-time summary broadcasting to connected clients
- Automatic updates on new summaries
- Connection management and error handling

**WebSocket Message Format:**
```json
{
  "type": "summaries_update",
  "data": {
    "summaries": {
      "instance_id_1": { /* AgentSummary */ },
      "instance_id_2": { /* AgentSummary */ }
    },
    "count": 2,
    "timestamp": "2025-01-15T10:23:45Z"
  }
}
```

**Deliverables:**
- Real-time UI updates
- Web UI integration capability

### Phase 5: Testing & Documentation

**Files to Create:**
- `tests/monitoring/test_position_tracker.py`
- `tests/monitoring/test_log_reader.py`
- `tests/monitoring/test_summary_generator.py`
- `tests/monitoring/test_service.py`
- `docs/MONITORING.md` - User-facing documentation

**Test Coverage:**
- Position tracking persistence across restarts
- Log rotation handling
- Incremental reading efficiency
- LLM summary generation (with mocks)
- Background service lifecycle
- MCP tool responses
- WebSocket streaming

**Documentation:**
- Architecture overview
- Usage examples for MCP tools
- WebSocket integration guide
- Configuration options
- Troubleshooting guide

**Deliverables:**
- Comprehensive test suite (>80% coverage)
- User and developer documentation

## Directory Structure

```
src/orchestrator/monitoring/
├── __init__.py
├── models.py                    # AgentSummary, OnTrackStatus, LogPosition
├── position_tracker.py          # PositionTracker, PositionState
├── log_reader.py                # IncrementalLogReader
├── summary_generator.py         # SummaryGenerator (LLM integration)
├── service.py                   # MonitoringService (background loop)
└── config.py                    # MonitoringConfig

tests/monitoring/
├── __init__.py
├── test_position_tracker.py
├── test_log_reader.py
├── test_summary_generator.py
└── test_service.py

/tmp/madrox_logs/
├── summaries/
│   └── {instance_id}/
│       ├── latest_summary.json
│       └── summary_history.jsonl
└── monitoring_state/
    └── monitor_positions.json
```

## Configuration

```python
@dataclass
class MonitoringConfig:
    """Configuration for monitoring service."""
    poll_interval_seconds: int = 12  # 10-15 seconds
    summary_dir: str = "/tmp/madrox_logs/summaries"
    state_dir: str = "/tmp/madrox_logs/monitoring_state"
    model: str = "claude-haiku-4-5"
    max_log_lines_per_read: int = 200
    error_backoff_seconds: int = 10
    enable_streaming: bool = True  # WebSocket
```

## Key Technical Decisions

### Decision 1: Separate Independent Process
**Chosen**: Background asyncio task within InstanceManager
**Rationale**:
- Shares LoggingManager and instance metadata
- No IPC overhead
- Simpler deployment
- Can be extracted later if needed

### Decision 2: LLM for "On Track" Inference
**Chosen**: Claude Haiku 4.5 with structured JSON output
**Rationale**:
- Semantic understanding of terminal output vs. task
- Handles unstructured log formats
- Cost-efficient (~$0.001 per agent per summary)
- Detects subtle drift patterns

**Alternative Rejected**: Rule-based keyword matching (too brittle)

### Decision 3: tmux_output.log as Primary Source
**Chosen**: Read from `tmux_output.log` via `log_tmux_output()`
**Rationale**:
- Complete terminal history with tool details
- Already captured by existing system
- Contains messages, responses, tool names, errors

**Alternative Rejected**: `communication.jsonl` (lacks terminal output details)

### Decision 4: Incremental Reading with File Seeking
**Chosen**: Track byte offset + line number, use `file.seek()`
**Rationale**:
- Efficient for large log files
- Handles log rotation with checksum validation
- State persists across restarts
- Minimal memory footprint

### Decision 5: WebSocket for Real-Time UI
**Chosen**: Add `/ws/agent_summaries` endpoint
**Rationale**:
- Real-time visibility without polling
- Consistent with existing `/ws/monitor` pattern
- Efficient for multiple UI clients

## Integration with InstanceManager

```python
# src/orchestrator/instance_manager.py

class InstanceManager:
    def __init__(self, config: dict[str, Any]):
        # ... existing code ...

        # Initialize monitoring service
        self.monitoring_service = MonitoringService(
            instance_manager=self,
            config=MonitoringConfig(
                poll_interval_seconds=12,
                summary_dir="/tmp/madrox_logs/summaries",
                state_dir="/tmp/madrox_logs/monitoring_state",
            ),
        )

        # Start monitoring in background
        asyncio.create_task(self.monitoring_service.start())
```

## MCP Tool Examples

### Get Single Agent Summary

```python
# Tool: get_agent_summary
result = await manager.get_agent_summary(
    instance_id="abc123",
    include_history=True
)

# Returns:
{
    "summary": {
        "instance_id": "abc123",
        "current_activity": "Implementing React authentication form",
        "on_track_status": "ON_TRACK",
        "confidence_score": 0.92,
        "assigned_task": "Build React authentication UI",
        "drift_reasons": [],
        "recommended_action": "no action needed"
    },
    "history": [...]  # Last 10 summaries
}
```

### Get All Agent Summaries

```python
# Tool: get_all_agent_summaries
result = await manager.get_all_agent_summaries()

# Returns:
{
    "summaries": {
        "abc123": { /* AgentSummary */ },
        "def456": { /* AgentSummary */ }
    },
    "count": 2,
    "timestamp": "2025-01-15T10:23:45Z"
}
```

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| **CPU Overhead** | <3% per 10 agents | Mostly LLM API calls |
| **Memory** | ~5 MB per agent | Position tracking + history |
| **Latency** | 5-10 seconds | Log write → summary |
| **Cost** | ~$0.001 per summary | Claude Haiku pricing |
| **Scalability** | Linear to 50+ agents | Adaptive polling extends to 100+ |
| **Poll Interval** | 10-15 seconds | Configurable |

## Example Summary Output

```json
{
  "instance_id": "abc123",
  "instance_name": "frontend-developer-swift-heron",
  "timestamp": "2025-01-15T10:23:45Z",
  "current_activity": "Implementing React component for user authentication form with validation logic",
  "on_track_status": "ON_TRACK",
  "confidence_score": 0.92,
  "assigned_task": "Build React authentication UI with form validation",
  "parent_instance_id": "supervisor-xyz",
  "role": "frontend_developer",
  "last_tool_used": "Write",
  "recent_tools": ["Read", "Grep", "Write", "Bash"],
  "output_preview": "Created LoginForm.tsx with useState hooks for form state management...",
  "idle_duration_seconds": 2.3,
  "drift_reasons": [],
  "alignment_keywords": ["React", "authentication", "form", "validation"],
  "recommended_action": "no action needed"
}
```

## Future Enhancements

### Post-MVP Features
1. **Adaptive Polling**: Adjust interval based on agent activity
2. **Alert System**: Notify when agents go OFF_TRACK or BLOCKED
3. **Summary Analytics**: Track agent productivity and patterns
4. **Multi-Agent Coordination**: Detect coordination issues between agents
5. **Custom Drift Rules**: User-defined heuristics for specific projects

### Integration with Knark
- This system will eventually replace Knark
- Current Knark branch: Not merged to main
- Migration path: Run both systems in parallel initially
- Gradual feature parity then deprecate Knark

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **LLM API Rate Limits** | Summary generation delays | Exponential backoff, queue management |
| **Log File Lock Conflicts** | Read failures | Read-only access, retry logic |
| **Memory Growth** | OOM with many agents | Limit history size, periodic cleanup |
| **Position State Corruption** | Lost read positions | Checksum validation, backup state |
| **WebSocket Connection Drops** | UI not updating | Automatic reconnection, heartbeat |

## Success Metrics

- **Accuracy**: >90% on-track inference accuracy (manual validation)
- **Latency**: <10 seconds from log write to summary
- **Coverage**: 100% of active agents monitored
- **Uptime**: Monitoring service >99.9% uptime
- **Cost**: <$0.10 per 100 summaries (Haiku efficiency)

## Timeline Estimate

- **Phase 1 (Core)**: 3-5 days
- **Phase 2 (LLM)**: 2-3 days
- **Phase 3 (Service)**: 3-4 days
- **Phase 4 (WebSocket)**: 1-2 days
- **Phase 5 (Testing/Docs)**: 2-3 days

**Total**: ~2 weeks for full implementation

## Next Steps

1. ✅ Create this plan document
2. ✅ Create feature branch: `feature/agent-activity-monitoring`
3. Begin Phase 1: Core Infrastructure
4. Iterate through phases with testing at each step
5. Integration testing with real agent networks
6. Documentation and final polish

---

**Document Version**: 1.0
**Last Updated**: 2025-01-15
**Status**: Ready for Implementation
