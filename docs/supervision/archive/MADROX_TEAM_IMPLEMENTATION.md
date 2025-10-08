# Madrox Team Implementation Plan
## Autonomous Supervision Feature - Phase 1

**Objective**: Use a Madrox team to implement Phase 1 of the autonomous supervision system.

---

## Team Structure

### Team Composition

| Role | Instance Name | Primary Responsibilities | Key Deliverables |
|------|--------------|-------------------------|------------------|
| **Architect** | `supervision-architect` | System design, integration planning, coordination | Integration specs, API contracts |
| **Backend Developer 1** | `event-system-dev` | Event bus & event models implementation | `event_bus.py`, `events.py` |
| **Backend Developer 2** | `analyzer-dev` | Transcript analyzer implementation | `transcript_analyzer.py` |
| **Backend Developer 3** | `tracker-dev` | Progress tracker implementation | `progress_tracker.py` |
| **Backend Developer 4** | `integration-dev` | TmuxInstanceManager integration, MCP tools | Modified manager, MCP adapter |
| **Testing Specialist** | `supervision-tester` | Unit tests, integration tests | Test suite (>85% coverage) |
| **Code Reviewer** | `supervision-reviewer` | Code quality, best practices review | Review reports, refactoring suggestions |

**Total Team Size**: 7 instances

---

## Phase 1 Components Breakdown

### Component 1: Event Bus System
**Owner**: `event-system-dev` (Backend Developer 1)

**Files to Create**:
- `src/orchestrator/event_bus.py` - EventBus class with pub/sub
- `src/orchestrator/events.py` - NetworkEvent models

**Key Requirements**:
- In-memory `asyncio.Queue` based pub/sub
- Event types: InstanceStateChanged, MessageExchange, ProgressUpdate, HealthCheck
- Bounded event history (`deque(maxlen=1000)`)
- Subscribe/publish API
- Zero external dependencies

**Acceptance Criteria**:
- Can publish events to subscribers
- Supports wildcard subscriptions (`*`)
- Thread-safe async operations
- Memory bounded (no leaks)

---

### Component 2: Transcript Analyzer
**Owner**: `analyzer-dev` (Backend Developer 2)

**Files to Create**:
- `src/orchestrator/transcript_analyzer.py` - TranscriptAnalyzer class

**Key Requirements**:
- Analyze tmux pane content via `get_tmux_pane_content()`
- Pattern matching for progress signals (completion, active, blocked, error, tool_execution)
- Confidence scoring (0.0-1.0)
- Baseline pattern profiling
- Anomaly detection vs baseline

**Acceptance Criteria**:
- Extract 5+ signal types from transcript
- Calculate confidence scores
- Detect output volume anomalies
- Return `TranscriptAnalysis` model

---

### Component 3: Progress Tracker
**Owner**: `tracker-dev` (Backend Developer 3)

**Files to Create**:
- `src/orchestrator/progress_tracker.py` - ProgressTracker class

**Key Requirements**:
- Track per-instance progress state (ACTIVE, STUCK, WAITING, DEGRADED, ERROR_LOOP, IDLE, HEALTHY)
- Store metrics: last_activity, output_volume, tool_usage, error_count
- Update from transcript analysis results
- State transition logic

**Acceptance Criteria**:
- Maintain state for all instances
- Compute health metrics
- Detect stuck/waiting/error states
- Expose query API for supervisor

---

### Component 4: Integration Layer
**Owner**: `integration-dev` (Backend Developer 4)

**Files to Modify**:
- `src/orchestrator/tmux_instance_manager.py` - Emit events on state changes
- `src/orchestrator/mcp_adapter.py` - Add optional MCP tools

**New MCP Tools** (optional):
- `report_status(instance_id, status_message)` - Explicit status reporting
- `log_checkpoint(instance_id, checkpoint_name, details)` - Work checkpoints

**Key Requirements**:
- Emit events on: spawn, terminate, message_send, message_receive, state_change
- Integrate EventBus into instance lifecycle
- Add MCP tool definitions
- Backward compatible (no breaking changes)

**Acceptance Criteria**:
- Events emitted for all lifecycle operations
- MCP tools registered and functional
- No performance degradation
- Existing tests pass

---

### Component 5: Test Suite
**Owner**: `supervision-tester` (Testing Specialist)

**Files to Create**:
- `tests/test_event_bus.py` - Event bus tests
- `tests/test_transcript_analyzer.py` - Transcript analyzer tests
- `tests/test_progress_tracker.py` - Progress tracker tests
- `tests/integration/test_supervision_phase1.py` - Integration tests

**Key Requirements**:
- Unit tests for each component (>85% coverage)
- Integration tests for event flow
- Mock tmux pane content for analyzer tests
- Performance benchmarks (overhead <5%)

**Test Scenarios**:
1. Event bus pub/sub with multiple subscribers
2. Transcript pattern matching accuracy
3. Progress state transitions
4. Event emission from instance manager
5. End-to-end event flow

---

### Component 6: Architecture Review
**Owner**: `supervision-architect` (Architect)

**Responsibilities**:
1. Define API contracts between components
2. Review integration points
3. Ensure zero-dependency design
4. Coordinate team communication
5. Validate design compliance

**Deliverables**:
- API specification document
- Integration checklist
- Dependency verification report
- Team coordination summary

---

## Parallel Work Streams

### Stream A: Core Infrastructure
**Team**: `event-system-dev`, `analyzer-dev`, `tracker-dev`
**Dependencies**: None (fully parallel)

| Task | Owner |
|------|-------|
| Implement EventBus | `event-system-dev` |
| Implement TranscriptAnalyzer | `analyzer-dev` |
| Implement ProgressTracker | `tracker-dev` |

**Coordination**: `supervision-architect` reviews API contracts

---

### Stream B: Integration
**Team**: `integration-dev`
**Dependencies**: Stream A complete

| Task | Owner | Dependencies |
|------|-------|--------------|
| Integrate EventBus into TmuxInstanceManager | `integration-dev` | EventBus ready |
| Add MCP tools | `integration-dev` | EventBus ready |
| Event emission points | `integration-dev` | Event models ready |

---

### Stream C: Testing & Quality
**Team**: `supervision-tester`, `supervision-reviewer`
**Dependencies**: Stream A complete

| Task | Owner | Dependencies |
|------|-------|--------------|
| Unit tests | `supervision-tester` | Components ready |
| Integration tests | `supervision-tester` | Integration complete |
| Code review | `supervision-reviewer` | Implementation complete |
| Performance benchmarks | `supervision-tester` | Integration complete |

---

## Coordination Protocol

### Progress Monitoring
**Supervisor**: `supervision-architect`

**Check-ins**:
1. Each instance reports progress via `report_status` MCP tool
2. Architect monitors for blockers
3. Architect redistributes work if needed

### Handoff Points
| From | To | Artifact | Verification |
|------|-----|---------|--------------|
| `event-system-dev` | `integration-dev` | EventBus API | Unit tests pass |
| `analyzer-dev` | `tracker-dev` | TranscriptAnalysis model | Schema validated |
| Stream A | `integration-dev` | All components | API contracts met |
| `integration-dev` | `supervision-tester` | Integrated system | Manual smoke test |

---

## Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| **Test Coverage** | >85% | `pytest --cov` |
| **Memory Overhead** | <500KB for 20 instances | Profiling |
| **CPU Overhead** | <5% | Benchmarking |
| **Zero Dependencies** | Stdlib only | `pyproject.toml` audit |
| **Event Latency** | <10ms pub-to-sub | Performance tests |
| **Pattern Matching Accuracy** | >90% on test cases | Analyzer validation |

---

## Risk Mitigation

### Risk 1: Integration Conflicts
**Mitigation**: Architect reviews API contracts before implementation starts

### Risk 2: Performance Overhead
**Mitigation**: Tester runs benchmarks early, dev optimizes if needed

### Risk 3: Team Coordination
**Mitigation**: Architect monitors progress, redistributes work if stuck

### Risk 4: Design Drift
**Mitigation**: All implementations must reference AUTONOMOUS_SUPERVISION_DESIGN.md

---

## Spawn Configuration

```python
# Spawn supervised Madrox team for Phase 1 implementation
team_config = {
    "coordinator": {
        "name": "supervision-architect",
        "role": "architect",
        "initial_prompt": """You are the architect for implementing Phase 1 of
        the Madrox autonomous supervision system. Review the design documents in
        ../madrox-supervision/docs/ and coordinate the team implementation.
        Your role is to ensure API contracts are clear, monitor progress,
        and resolve integration blockers."""
    },
    "workers": [
        {
            "name": "event-system-dev",
            "role": "backend_developer",
            "initial_prompt": """Implement event_bus.py and events.py following
            AUTONOMOUS_SUPERVISION_DESIGN.md. Use asyncio.Queue, no external dependencies.
            Focus on pub/sub pattern with bounded event history."""
        },
        {
            "name": "analyzer-dev",
            "role": "backend_developer",
            "initial_prompt": """Implement transcript_analyzer.py with regex pattern
            matching for progress signals. Use get_tmux_pane_content() API.
            No external dependencies."""
        },
        {
            "name": "tracker-dev",
            "role": "backend_developer",
            "initial_prompt": """Implement progress_tracker.py for maintaining
            per-instance progress state. Support 7 states: ACTIVE, STUCK, WAITING,
            DEGRADED, ERROR_LOOP, IDLE, HEALTHY."""
        },
        {
            "name": "integration-dev",
            "role": "backend_developer",
            "initial_prompt": """Integrate EventBus into tmux_instance_manager.py.
            Emit events on state changes. Add optional MCP tools: report_status,
            log_checkpoint."""
        },
        {
            "name": "supervision-tester",
            "role": "testing_specialist",
            "initial_prompt": """Create comprehensive test suite for supervision
            Phase 1. Target >85% coverage. Include unit tests, integration tests,
            and performance benchmarks."""
        },
        {
            "name": "supervision-reviewer",
            "role": "code_reviewer",
            "initial_prompt": """Review all supervision Phase 1 code for quality,
            best practices, and design compliance. Ensure zero external dependencies
            and minimal overhead."""
        }
    ]
}
```

---

## Execution Plan

### Step 1: Spawn Team
```bash
# Spawn architect (coordinator)
madrox spawn supervision-architect --role architect

# Spawn parallel workers
madrox spawn event-system-dev --role backend_developer
madrox spawn analyzer-dev --role backend_developer
madrox spawn tracker-dev --role backend_developer
madrox spawn integration-dev --role backend_developer
madrox spawn supervision-tester --role testing_specialist
madrox spawn supervision-reviewer --role code_reviewer
```

### Step 2: Initialize Coordinator
Send architect initial context:
- Design documents location
- Team structure
- API contract requirements
- Coordination protocol

### Step 3: Parallel Stream A (Core Components)
Architect coordinates 3 parallel implementations:
- EventBus + Events models
- TranscriptAnalyzer
- ProgressTracker

### Step 4: Integration (Stream B)
After Stream A complete:
- Integration dev modifies TmuxInstanceManager
- Adds event emission points
- Implements optional MCP tools

### Step 5: Testing (Stream C)
After integration:
- Tester creates test suite
- Reviewer performs code review
- Tester runs performance benchmarks

### Step 6: Validation & Handoff
Architect validates:
- All tests pass (>85% coverage)
- Zero external dependencies
- Performance targets met (<5% overhead)
- Design compliance verified

---

## Expected Outcomes

**Deliverables**:
1. ✅ `event_bus.py` - Event bus implementation
2. ✅ `events.py` - Event model definitions
3. ✅ `transcript_analyzer.py` - Transcript analysis with pattern matching
4. ✅ `progress_tracker.py` - Progress state management
5. ✅ Modified `tmux_instance_manager.py` - Event emission integrated
6. ✅ Modified `mcp_adapter.py` - Optional MCP tools added
7. ✅ Comprehensive test suite (>85% coverage)
8. ✅ Performance benchmarks validating <5% overhead
9. ✅ Code review report from reviewer

**Quality Gates**:
- All tests pass
- Coverage >85%
- Zero external dependencies
- Performance overhead <5%
- Code review approved
