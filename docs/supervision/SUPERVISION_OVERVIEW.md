# Autonomous Supervision for Madrox

**Branch**: `feature/autonomous-supervision`
**Worktree Location**: `../madrox-supervision/`

## Overview

This feature branch implements autonomous supervision for Madrox networks, enabling self-monitoring, issue detection, and self-healing without user intervention.

### Problem Solved

Current Madrox networks require the user to act as the monitoring system. When the main Claude agent finishes responding, there's no autonomy - instances can get stuck, wait for input, or encounter problems without detection or resolution.

This feature adds a **Supervisor Agent** pattern that autonomously:
- Monitors network health and progress
- Detects stuck, waiting, idle, or troubled instances
- Makes decisions and executes remediation actions
- Escalates unresolvable issues to the user

---

## Quick Start

### Working in the Supervision Worktree

```bash
# Switch to supervision worktree
cd ../madrox-supervision

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv sync --all-groups

# Run tests
pytest tests/ -v

# Return to main worktree
cd ../madrox
```

---

## Documents

### 📋 Design Documents

1. **[docs/AUTONOMOUS_SUPERVISION_DESIGN.md](docs/AUTONOMOUS_SUPERVISION_DESIGN.md)**
   - Complete architecture design
   - Component specifications
   - Integration plan
   - Performance considerations
   - Future enhancements

2. **[IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)**
   - 5-week implementation plan
   - Phase-by-phase task breakdown
   - Code examples for each phase
   - Novel implementation ideas
   - Risk mitigation strategies

---

## Architecture Summary

### Core Components

```
┌─────────────────────────────────────────────┐
│         Supervision Layer                    │
│  ┌───────────────────────────────────────┐  │
│  │ Supervisor Agent                      │  │
│  │ (Autonomous Monitor)                  │  │
│  └───────────────────────────────────────┘  │
│                    ↓                         │
│  ┌──────────────────────────────┐           │
│  │ Event Bus (Pub/Sub)          │           │
│  │ - InstanceStateChanged        │           │
│  │ - MessageExchange             │           │
│  │ - ProgressUpdate              │           │
│  │ - HealthCheck                 │           │
│  └──────────────────────────────┘           │
│         ↓                ↓                   │
│  ┌─────────────┐  ┌─────────────┐          │
│  │ Progress    │  │ Decision    │          │
│  │ Tracker     │  │ Engine      │          │
│  └─────────────┘  └─────────────┘          │
│                         ↓                    │
│                  ┌─────────────┐            │
│                  │ Action      │            │
│                  │ Executor    │            │
│                  └─────────────┘            │
└─────────────────────────────────────────────┘
```

### Key Features

✅ **Event-Driven Monitoring**: Real-time network activity tracking
✅ **Progress Analysis**: Granular state beyond simple state machines
✅ **Autonomous Decisions**: Rule-based interventions without user input
✅ **Self-Healing**: Automatic remediation actions
✅ **Deadlock Detection**: Identify and break circular dependencies
✅ **Load Balancing**: Redistribute work across idle instances

---

## Implementation Phases

### Phase 1: Core Infrastructure
- Event bus with pub/sub pattern
- Event emission from existing components
- **Transcript analysis system (primary monitoring)**
- Progress tracker with metrics
- Optional MCP tools: report_status, log_checkpoint (supplementary)

### Phase 2: Supervisor Agent
- Supervisor system prompt
- Auto-spawn logic
- Decision engine with rules
- Action executor

### Phase 3: Detection & Remediation
- Stuck detection heuristic
- Waiting detection
- Error loop detection
- Deadlock detection
- Remediation testing

### Phase 4: Testing & Documentation
- Unit tests (>85% coverage)
- Integration tests
- Performance benchmarks
- Documentation
- Example workflows

---

## Key Design Decisions

### 1. Transcript Analysis (Primary Monitoring)
**Core Feature**: Analyze terminal output and message transcripts for progress signals instead of requiring explicit instrumentation. Leverages existing tmux output and conversation logs.

### 2. Predictive Stuck Detection
Predict when instances will get stuck before they fully stall

### 3. Peer Consultation
Supervisor consults peer instances before intervening

### 4. Adaptive Thresholds
Learn optimal detection thresholds from network behavior

### 5. Network Health Score
Single metric (0.0-1.0) for overall network health

### 6. Self-Healing History
Track and learn from past remediation actions

---

## Usage Example

```python
# Spawn supervised network
coordinator_id = await manager.spawn_supervised_network(
    coordinator_config={
        "name": "reverse-engineering-lead",
        "role": "architect"
    },
    supervision_config=SupervisionConfig(
        stuck_threshold_seconds=300,
        waiting_threshold_seconds=120,
        max_interventions_per_instance=3
    )
)

# Supervisor monitors automatically:
# 1. Detects stuck analyzer (no progress >5min)
# 2. Sends status check message
# 3. If no response, spawns debugger helper
# 4. Detects decompiler waiting for work
# 5. Assigns next work item
# 6. Detects circular dependency
# 7. Breaks deadlock by coordinating instances
```

---

## Key Metrics & Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Mean Time to Detect (MTTD)** | <2 min | Issue occurrence → detection |
| **Mean Time to Resolve (MTTR)** | <5 min | Detection → resolution |
| **Autonomous Resolution Rate** | >70% | Issues resolved without escalation |
| **False Positive Rate** | <5% | Incorrect detections / total |
| **Supervision Overhead** | <25% | CPU/memory increase |
| **Network Uptime** | >95% | % time productively working |

---

## Development Workflow

### Starting Development

```bash
# Switch to supervision worktree
cd ../madrox-supervision

# Create feature branch (if needed)
git checkout -b feature/event-bus

# Make changes
# ... edit files ...

# Run tests
pytest tests/ -v

# Commit
git add .
git commit -m "feat: implement event bus with pub/sub pattern"

# Push
git push origin feature/autonomous-supervision
```

### Syncing with Main

```bash
# In supervision worktree
git fetch origin
git merge origin/main

# Resolve conflicts if any
pytest tests/ -v
```

---

## Status

**Current Phase**: Design Complete ✅
**Next Phase**: Phase 1 - Core Infrastructure
**Branch Status**: Active Development

---

## Quick Links

- **[Full Design Doc](docs/AUTONOMOUS_SUPERVISION_DESIGN.md)** - Complete architecture
- **[Implementation Roadmap](IMPLEMENTATION_ROADMAP.md)** - Phased implementation plan
- **[Main Madrox README](README.md)** - Project documentation
