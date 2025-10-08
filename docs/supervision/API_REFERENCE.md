# Supervision API Reference

Complete API reference for the Madrox Supervision system.

## Quick Start

```python
from supervision.integration import spawn_supervisor
from supervision.supervisor import SupervisionConfig
from orchestrator.instance_manager import InstanceManager

# Create instance manager
manager = InstanceManager(config)

# Spawn supervisor with configuration
supervisor_id, supervisor = await spawn_supervisor(
    instance_manager=manager,
    config=SupervisionConfig(
        stuck_threshold_seconds=300,
        evaluation_interval_seconds=30
    )
)
```

## Integration API

### `spawn_supervisor()`

Spawns a supervisor Claude instance for autonomous network monitoring.

```python
async def spawn_supervisor(
    instance_manager: InstanceManager,
    config: SupervisionConfig | None = None,
    auto_start: bool = True,
) -> tuple[str, SupervisorAgent]
```

**Parameters:**
- `instance_manager`: The InstanceManager to monitor
- `config`: Supervision configuration (uses defaults if None)
- `auto_start`: Automatically start the supervision loop (default: True)

**Returns:**
- Tuple of `(supervisor_instance_id, supervisor_agent)`

**Example:**
```python
supervisor_id, supervisor = await spawn_supervisor(
    instance_manager=manager,
    config=SupervisionConfig(stuck_threshold_seconds=180)
)
```

---

### `attach_supervisor()`

Attaches a supervisor agent without spawning a dedicated Claude instance.

```python
async def attach_supervisor(
    instance_manager: InstanceManager,
    config: SupervisionConfig | None = None,
) -> SupervisorAgent
```

**Parameters:**
- `instance_manager`: The InstanceManager to monitor
- `config`: Supervision configuration (uses defaults if None)

**Returns:**
- Initialized `SupervisorAgent` (not started)

**Example:**
```python
supervisor = await attach_supervisor(manager)
await supervisor.start()  # Manual start
```

---

### `spawn_supervised_network()`

Creates a complete supervised network with participants and supervisor.

```python
async def spawn_supervised_network(
    instance_manager: InstanceManager,
    participant_configs: list[dict[str, Any]],
    supervision_config: SupervisionConfig | None = None,
) -> dict[str, Any]
```

**Parameters:**
- `instance_manager`: The InstanceManager
- `participant_configs`: List of participant instance configurations
- `supervision_config`: Supervision configuration (uses defaults if None)

**Returns:**
- Dictionary with keys:
  - `supervisor_id`: Supervisor instance ID
  - `supervisor_agent`: SupervisorAgent instance
  - `participant_ids`: List of participant instance IDs
  - `network_size`: Total network size (participants + supervisor)

**Example:**
```python
network = await spawn_supervised_network(
    instance_manager=manager,
    participant_configs=[
        {"name": "dev1", "role": "frontend_developer"},
        {"name": "dev2", "role": "backend_developer"},
    ]
)
```

## Configuration

### `SupervisionConfig`

Configuration dataclass for supervisor behavior.

```python
@dataclass
class SupervisionConfig:
    # Detection thresholds
    stuck_threshold_seconds: int = 300  # 5 minutes
    waiting_threshold_seconds: int = 120  # 2 minutes
    error_loop_threshold: int = 3  # consecutive errors

    # Intervention limits
    max_interventions_per_instance: int = 3
    intervention_cooldown_seconds: int = 60

    # Evaluation cycle
    evaluation_interval_seconds: int = 30

    # Performance targets
    network_efficiency_target: float = 0.70  # 70% productive time

    # Escalation
    escalate_after_failed_interventions: int = 3
```

**Field Descriptions:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `stuck_threshold_seconds` | int | 300 | Time threshold to consider instance stuck |
| `waiting_threshold_seconds` | int | 120 | Time threshold for waiting detection |
| `error_loop_threshold` | int | 3 | Number of consecutive errors before intervention |
| `max_interventions_per_instance` | int | 3 | Maximum interventions per instance |
| `intervention_cooldown_seconds` | int | 60 | Cooldown between interventions |
| `evaluation_interval_seconds` | int | 30 | How often to evaluate network |
| `network_efficiency_target` | float | 0.70 | Target network efficiency (0.0-1.0) |
| `escalate_after_failed_interventions` | int | 3 | Failed interventions before escalation |

**Example Configurations:**

**Development - Fast Feedback:**
```python
SupervisionConfig(
    stuck_threshold_seconds=60,
    evaluation_interval_seconds=10,
    max_interventions_per_instance=5
)
```

**Production - Conservative:**
```python
SupervisionConfig(
    stuck_threshold_seconds=600,
    evaluation_interval_seconds=60,
    max_interventions_per_instance=3
)
```

**Monitoring - Minimal Intervention:**
```python
SupervisionConfig(
    stuck_threshold_seconds=900,
    max_interventions_per_instance=1,
    intervention_cooldown_seconds=300
)
```

## Core Classes

### `SupervisorAgent`

Main autonomous supervisor agent class.

```python
class SupervisorAgent:
    def __init__(
        self,
        instance_manager: InstanceManager,
        config: SupervisionConfig
    )

    async def start() -> None
    async def stop() -> None
    async def get_detected_issues() -> list[DetectedIssue]
    def get_interventions() -> list[InterventionRecord]
    @property
    def is_running() -> bool
```

**Methods:**

#### `start()`
Starts the supervision loop.
```python
await supervisor.start()
```

#### `stop()`
Stops the supervision loop.
```python
await supervisor.stop()
```

#### `get_detected_issues()`
Returns list of currently detected issues.
```python
issues = await supervisor.get_detected_issues()
for issue in issues:
    print(f"{issue.instance_id}: {issue.description}")
```

#### `get_interventions()`
Returns history of interventions performed.
```python
interventions = supervisor.get_interventions()
```

#### `is_running` (property)
Check if supervisor is currently running.
```python
if supervisor.is_running:
    print("Supervision active")
```

## Data Models

### `DetectedIssue`

Represents a detected issue in the network.

```python
@dataclass(frozen=True)
class DetectedIssue:
    instance_id: str
    issue_type: str
    severity: IssueSeverity
    description: str
    detected_at: datetime
    confidence: float  # 0.0-1.0
    evidence: dict[str, Any] = field(default_factory=dict)
```

**Example:**
```python
issue = DetectedIssue(
    instance_id="worker-1",
    issue_type="stuck",
    severity=IssueSeverity.ERROR,
    description="Instance stuck for 320 seconds",
    detected_at=datetime.now(UTC),
    confidence=0.95,
    evidence={"last_activity": 320}
)
```

---

### `InterventionRecord`

Record of a supervisor intervention.

```python
@dataclass
class InterventionRecord:
    intervention_id: str
    intervention_type: InterventionType
    target_instance_id: str
    timestamp: datetime
    reason: str
    action_taken: str
    success: bool | None = None  # None = pending
    details: dict[str, Any] = field(default_factory=dict)
```

**Example:**
```python
intervention = InterventionRecord(
    intervention_id="int-123",
    intervention_type=InterventionType.SPAWN_HELPER,
    target_instance_id="stuck-worker",
    timestamp=datetime.now(UTC),
    reason="Instance stuck for 300+ seconds",
    action_taken="Spawned helper instance",
    success=True,
    details={"helper_id": "helper-456"}
)
```

## Enums

### `IssueSeverity`

Severity levels for detected issues.

```python
class IssueSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
```

**Usage:**
```python
if issue.severity == IssueSeverity.CRITICAL:
    # Handle critical issue
    pass
```

---

### `InterventionType`

Types of supervisor interventions.

```python
class InterventionType(Enum):
    STATUS_CHECK = "status_check"
    PROVIDE_GUIDANCE = "provide_guidance"
    REASSIGN_WORK = "reassign_work"
    SPAWN_HELPER = "spawn_helper"
    BREAK_DEADLOCK = "break_deadlock"
    ESCALATE = "escalate"
```

**Usage:**
```python
if intervention.intervention_type == InterventionType.SPAWN_HELPER:
    print(f"Helper spawned: {intervention.details['helper_id']}")
```

## Advanced Components

### Event System

```python
from supervision.events import EventBus, Event, EventType

# Access through supervisor (automatically integrated)
events = await supervisor.event_collector.get_events(
    instance_id="worker-1",
    event_types=[EventType.STATUS_CHANGE]
)
```

### Progress Tracking

```python
from supervision.tracking import ProgressTracker, ProgressSnapshot

# Access through supervisor
progress = await supervisor.progress_tracker.get_progress("instance-id")
print(f"Tasks completed: {progress.tasks_completed}")
print(f"Is stalled: {progress.is_stalled}")
```

### Analysis

```python
from supervision.analysis import TranscriptAnalyzer, AnalysisResult

# Integrated into supervisor - access results via:
issues = await supervisor.get_detected_issues()
```

## Usage Patterns

### Pattern 1: Basic Autonomous Monitoring

```python
from supervision.integration import spawn_supervisor
from supervision.supervisor import SupervisionConfig

manager = InstanceManager(config)
supervisor_id, supervisor = await spawn_supervisor(
    instance_manager=manager,
    config=SupervisionConfig(
        stuck_threshold_seconds=180,
        evaluation_interval_seconds=20
    )
)
# Supervisor runs autonomously
```

### Pattern 2: Manual Control

```python
from supervision.integration import attach_supervisor

supervisor = await attach_supervisor(manager)

# Manual lifecycle
await supervisor.start()
# ... do work ...
await supervisor.stop()
```

### Pattern 3: Supervised Team

```python
from supervision.integration import spawn_supervised_network

network = await spawn_supervised_network(
    instance_manager=manager,
    participant_configs=[
        {"name": "dev1", "role": "frontend_developer"},
        {"name": "dev2", "role": "backend_developer"},
    ],
    supervision_config=SupervisionConfig()
)

supervisor = network["supervisor_agent"]
participants = network["participant_ids"]
```

### Pattern 4: Issue Monitoring

```python
# Start supervisor
supervisor_id, supervisor = await spawn_supervisor(manager)

# Periodically check issues
while True:
    issues = await supervisor.get_detected_issues()

    for issue in issues:
        if issue.severity == IssueSeverity.CRITICAL:
            # Custom handling
            logger.critical(f"Critical issue: {issue.description}")

    await asyncio.sleep(30)
```

### Pattern 5: Intervention Analysis

```python
# Get intervention history
interventions = supervisor.get_interventions()

# Analyze effectiveness
successful = [i for i in interventions if i.success]
failed = [i for i in interventions if i.success is False]

logger.info(f"Success rate: {len(successful)/len(interventions)*100}%")

# By type
helper_spawns = [
    i for i in interventions
    if i.intervention_type == InterventionType.SPAWN_HELPER
]
```

## Error Handling

```python
from supervision.integration import spawn_supervisor

try:
    supervisor_id, supervisor = await spawn_supervisor(manager)

    # Use supervisor
    await asyncio.sleep(60)

except Exception as e:
    logger.error(f"Supervision error: {e}")

finally:
    if supervisor:
        await supervisor.stop()
```

## Testing Integration

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_supervision():
    # Mock manager
    manager = AsyncMock(spec=InstanceManager)

    # Create supervisor
    supervisor_id, supervisor = await spawn_supervisor(
        instance_manager=manager,
        auto_start=False
    )

    # Test operations
    await supervisor.start()
    assert supervisor.is_running

    await supervisor.stop()
    assert not supervisor.is_running
```

## Complete Import Reference

```python
# Integration layer (main API)
from supervision.integration import (
    spawn_supervisor,
    attach_supervisor,
    spawn_supervised_network,
)

# Configuration and core
from supervision.supervisor import (
    SupervisorAgent,
    SupervisionConfig,
    DetectedIssue,
    InterventionRecord,
    InterventionType,
    IssueSeverity,
)

# Events (optional, advanced)
from supervision.events import (
    EventBus,
    Event,
    EventType,
)

# Tracking (optional, advanced)
from supervision.tracking import (
    ProgressTracker,
    ProgressSnapshot,
    TaskStatus,
)

# Analysis (optional, advanced)
from supervision.analysis import (
    TranscriptAnalyzer,
    AnalysisResult,
    AnalysisStatus,
)

# Orchestrator
from orchestrator.instance_manager import InstanceManager
```

## Version Compatibility

- **Python**: Requires 3.11+
- **Orchestrator**: Compatible with Madrox orchestrator v0.1.0+
- **Dependencies**: See `pyproject.toml` for complete list

## See Also

- [Integration Guide](./INTEGRATION_GUIDE.md) - Comprehensive integration documentation
- [Dependency Setup](./DEPENDENCY_SETUP.md) - Installation and setup instructions
- [Examples](./examples/README.md) - Code examples and patterns
