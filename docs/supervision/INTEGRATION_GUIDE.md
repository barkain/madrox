# Madrox Supervision Integration Guide

This guide explains how to integrate the Madrox Supervision system into your Madrox orchestrator deployments.

## Overview

The Supervision package provides autonomous monitoring and progress tracking for Madrox instance networks. It enables:

- **Autonomous Network Monitoring**: Detects stuck instances, progress stalls, and coordination failures
- **Intelligent Interventions**: Automatically resolves issues through strategic helper spawning
- **Real-time Progress Tracking**: Monitors task completion and network health
- **Event-driven Analysis**: Comprehensive event tracking and pattern analysis

## Architecture

The Supervision system consists of several key components:

```
supervision/
├── supervisor/          # Core supervisor agent and configuration
├── tracking/           # Progress and performance tracking
├── events/             # Event system for monitoring
├── analysis/           # Pattern detection and analysis
├── coordination/       # Multi-instance coordination
└── integration/        # Integration layer for Madrox
```

### Key Modules

- **SupervisorAgent**: Main autonomous monitoring agent
- **ProgressTracker**: Tracks task progress across instances
- **EventCollector**: Collects and stores system events
- **PatternDetector**: Detects anomalies and issues
- **CoordinationManager**: Manages multi-instance coordination

## Integration Points

### 1. InstanceManager Integration

The Supervision system integrates with the Madrox `InstanceManager` through a clean API boundary:

```python
from supervision.integration import spawn_supervisor, attach_supervisor
from supervision.supervisor import SupervisionConfig

# Spawn a supervisor for an existing manager
supervisor_id, supervisor = await spawn_supervisor(
    instance_manager=manager,
    config=SupervisionConfig(
        stuck_threshold_seconds=300,
        evaluation_interval_seconds=30,
        max_stall_count=3,
        enable_auto_intervention=True
    )
)
```

### 2. API Surface

#### Core Integration Functions

**`spawn_supervisor()`** - Creates a new supervisor Claude instance
```python
async def spawn_supervisor(
    instance_manager: InstanceManager,
    config: SupervisionConfig | None = None,
    auto_start: bool = True,
) -> tuple[str, SupervisorAgent]:
    """
    Spawns a supervisor instance with autonomous monitoring capabilities.

    Args:
        instance_manager: The InstanceManager to monitor
        config: Supervision configuration (uses defaults if None)
        auto_start: Automatically start the supervision loop

    Returns:
        Tuple of (supervisor_instance_id, supervisor_agent)
    """
```

**`attach_supervisor()`** - Attaches supervision without spawning
```python
async def attach_supervisor(
    instance_manager: InstanceManager,
    config: SupervisionConfig | None = None,
) -> SupervisorAgent:
    """
    Attaches a supervisor agent to an existing InstanceManager without spawning
    a dedicated Claude instance.

    Args:
        instance_manager: The InstanceManager to monitor
        config: Supervision configuration (uses defaults if None)

    Returns:
        Initialized SupervisorAgent (not started)
    """
```

**`spawn_supervised_network()`** - Creates a complete supervised network
```python
async def spawn_supervised_network(
    instance_manager: InstanceManager,
    participant_configs: list[dict[str, Any]],
    supervision_config: SupervisionConfig | None = None,
) -> dict[str, Any]:
    """
    Spawns a complete supervised network with participants and supervisor.

    Args:
        instance_manager: The InstanceManager
        participant_configs: List of participant instance configurations
        supervision_config: Supervision configuration

    Returns:
        Dictionary with supervisor_id, supervisor_agent, and participant_ids
    """
```

#### Configuration

**`SupervisionConfig`** - Main configuration dataclass
```python
@dataclass
class SupervisionConfig:
    # Thresholds
    stuck_threshold_seconds: int = 300  # 5 minutes
    evaluation_interval_seconds: int = 30
    max_stall_count: int = 3

    # Behavior
    enable_auto_intervention: bool = True
    enable_progress_tracking: bool = True
    enable_pattern_analysis: bool = True

    # Coordination
    max_concurrent_helpers: int = 3
    helper_timeout_seconds: int = 600
```

## Usage Patterns

### Pattern 1: Basic Supervision

Add autonomous monitoring to an existing Madrox network:

```python
from orchestrator.instance_manager import InstanceManager
from supervision.integration import spawn_supervisor
from supervision.supervisor import SupervisionConfig

# Initialize instance manager
manager = InstanceManager(config={
    "workspace_base_dir": "/tmp/madrox",
    "log_dir": "/tmp/madrox_logs"
})

# Spawn supervisor with custom configuration
supervisor_id, supervisor = await spawn_supervisor(
    instance_manager=manager,
    config=SupervisionConfig(
        stuck_threshold_seconds=180,
        evaluation_interval_seconds=20,
        enable_auto_intervention=True
    )
)

# Supervisor now autonomously monitors all instances
# It will automatically detect and resolve issues
```

### Pattern 2: Supervised Network Creation

Create a complete supervised network from scratch:

```python
from supervision.integration import spawn_supervised_network

# Define your team
network = await spawn_supervised_network(
    instance_manager=manager,
    participant_configs=[
        {
            "name": "frontend-dev",
            "role": "frontend_developer",
            "system_prompt": "You are a React specialist"
        },
        {
            "name": "backend-dev",
            "role": "backend_developer",
            "system_prompt": "You are a Python/FastAPI expert"
        },
        {
            "name": "tester",
            "role": "testing_specialist"
        }
    ],
    supervision_config=SupervisionConfig(
        stuck_threshold_seconds=300,
        max_concurrent_helpers=2
    )
)

# Access network components
supervisor_id = network["supervisor_id"]
participant_ids = network["participant_ids"]
supervisor_agent = network["supervisor_agent"]
```

### Pattern 3: Embedded Supervision

Embed supervision directly in your orchestrator without spawning:

```python
from supervision.integration import attach_supervisor

# Attach supervisor to existing manager
supervisor = await attach_supervisor(
    instance_manager=manager,
    config=SupervisionConfig(
        evaluation_interval_seconds=60,
        enable_auto_intervention=False  # Manual control
    )
)

# Start supervision manually
await supervisor.start()

# Your orchestrator logic here...
# Supervisor runs in background

# Stop when done
await supervisor.stop()
```

### Pattern 4: Manual Supervision Control

Full control over supervision lifecycle:

```python
from supervision.supervisor import SupervisorAgent, SupervisionConfig

# Create supervisor agent
config = SupervisionConfig(
    stuck_threshold_seconds=240,
    evaluation_interval_seconds=30,
    enable_auto_intervention=True
)

supervisor = SupervisorAgent(
    instance_manager=manager,
    config=config
)

# Start supervision
await supervisor.start()

# Check status
issues = await supervisor.get_detected_issues()
for issue in issues:
    print(f"Issue: {issue.description} (Severity: {issue.severity})")

# Get intervention history
interventions = supervisor.get_interventions()

# Stop supervision
await supervisor.stop()
```

## Event System Integration

The supervision system uses an event-driven architecture:

```python
from supervision.events import EventCollector, EventType

# Event collector is automatically integrated
# Events are captured from:
# - Instance status changes
# - Tool executions
# - Message exchanges
# - Progress updates

# Access events through supervisor
events = await supervisor.event_collector.get_events(
    instance_id="some-instance",
    event_types=[EventType.STATUS_CHANGE, EventType.TOOL_CALL]
)
```

## Progress Tracking Integration

Monitor task progress across your network:

```python
# Progress tracking is automatic when enabled
# Access through supervisor agent

progress = await supervisor.progress_tracker.get_progress("instance-id")
print(f"Tasks completed: {progress.tasks_completed}")
print(f"Active tasks: {progress.active_tasks}")
print(f"Stalled: {progress.is_stalled}")
```

## Logging and Observability

The supervision system uses structured logging:

```python
import logging

# Configure supervision logging
logging.getLogger("supervision").setLevel(logging.INFO)

# Logs include structured context:
# - Instance IDs
# - Issue detection
# - Intervention actions
# - Pattern analysis results
```

Log output example:
```
INFO - Spawning supervisor instance for autonomous network monitoring
INFO - Supervisor instance spawned - supervisor_id=abc123, stuck_threshold=300
INFO - Supervisor agent started - autonomous monitoring active
INFO - Detected stuck instance - instance_id=xyz789, last_activity=320s ago
INFO - Spawning helper instance for intervention - stuck_instance=xyz789
```

## Testing Integration

Test your supervision integration:

```python
import pytest
from supervision.integration import spawn_supervisor
from orchestrator.instance_manager import InstanceManager

@pytest.mark.asyncio
async def test_supervision_integration():
    # Setup
    config = {"workspace_base_dir": "/tmp/test_madrox"}
    manager = InstanceManager(config)

    # Spawn supervisor
    supervisor_id, supervisor = await spawn_supervisor(
        instance_manager=manager,
        auto_start=False
    )

    # Verify integration
    assert supervisor_id is not None
    assert supervisor.instance_manager is manager

    # Test supervision start/stop
    await supervisor.start()
    assert supervisor.is_running

    await supervisor.stop()
    assert not supervisor.is_running
```

## Best Practices

### 1. Configuration Tuning

- **Development**: Use shorter intervals for faster feedback
  ```python
  SupervisionConfig(
      evaluation_interval_seconds=10,
      stuck_threshold_seconds=120
  )
  ```

- **Production**: Use longer intervals to reduce overhead
  ```python
  SupervisionConfig(
      evaluation_interval_seconds=60,
      stuck_threshold_seconds=600
  )
  ```

### 2. Resource Management

- Limit concurrent helpers to avoid resource exhaustion:
  ```python
  SupervisionConfig(max_concurrent_helpers=3)
  ```

- Set appropriate helper timeouts:
  ```python
  SupervisionConfig(helper_timeout_seconds=600)  # 10 minutes
  ```

### 3. Event Storage

- Configure event retention based on your needs
- Events are stored in-memory by default
- For production, consider implementing persistent storage

### 4. Error Handling

Always handle supervisor lifecycle properly:

```python
supervisor_id, supervisor = None, None
try:
    supervisor_id, supervisor = await spawn_supervisor(manager)
    # Your logic here
finally:
    if supervisor:
        await supervisor.stop()
```

## Troubleshooting

### Supervisor Not Detecting Issues

- Check evaluation interval: May be too long
- Verify stuck threshold: May be too high
- Check instance manager integration: Ensure proper event flow

### Too Many Interventions

- Increase stuck threshold
- Reduce sensitivity in pattern detection
- Limit max concurrent helpers

### Performance Impact

- Increase evaluation interval
- Disable pattern analysis if not needed:
  ```python
  SupervisionConfig(enable_pattern_analysis=False)
  ```
- Use `attach_supervisor()` instead of `spawn_supervisor()` to avoid extra instance

## Migration Guide

### From Manual Monitoring

**Before:**
```python
# Manual monitoring loop
while True:
    for instance_id in manager.instances:
        status = await manager.get_instance_status(instance_id)
        if is_stuck(status):
            # Manual intervention
            await spawn_helper(instance_id)
    await asyncio.sleep(60)
```

**After:**
```python
# Autonomous supervision
supervisor_id, supervisor = await spawn_supervisor(
    instance_manager=manager,
    config=SupervisionConfig(evaluation_interval_seconds=60)
)
# Supervisor handles everything automatically
```

### From Custom Solutions

If you have custom monitoring solutions:

1. **Identify your monitoring logic** - What issues do you detect?
2. **Map to SupervisionConfig** - Configure thresholds accordingly
3. **Extend if needed** - Inherit from SupervisorAgent for custom behavior
4. **Gradual migration** - Run both systems in parallel initially

## API Reference

### Complete API Surface

```python
# Integration Layer
from supervision.integration import (
    spawn_supervisor,           # Spawn supervisor instance
    attach_supervisor,          # Attach without spawning
    spawn_supervised_network,   # Create supervised network
)

# Core Components
from supervision.supervisor import (
    SupervisorAgent,           # Main supervisor agent
    SupervisionConfig,         # Configuration dataclass
    DetectedIssue,            # Issue representation
    InterventionRecord,       # Intervention tracking
    InterventionType,         # Intervention types enum
    IssueSeverity,           # Severity levels enum
)

# Events
from supervision.events import (
    EventCollector,           # Event collection
    EventType,               # Event types enum
)

# Tracking
from supervision.tracking import (
    ProgressTracker,         # Progress tracking
    PerformanceMetrics,      # Performance metrics
)

# Analysis
from supervision.analysis import (
    PatternDetector,         # Pattern detection
    NetworkAnalyzer,        # Network analysis
)

# Coordination
from supervision.coordination import (
    CoordinationManager,     # Coordination management
)
```

## Support and Documentation

- **Source Code**: `/path/to/user/dev/madrox-supervision/`
- **Tests**: `/path/to/user/dev/madrox-supervision/tests/`
- **Examples**: See usage patterns above

## Changelog

### Version 1.0.0
- Initial release
- Core supervision functionality
- InstanceManager integration
- Event-driven architecture
- Progress tracking
- Pattern detection
- Autonomous interventions
