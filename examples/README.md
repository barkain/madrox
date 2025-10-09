# Madrox Supervision Examples

This directory contains comprehensive examples demonstrating how to integrate and use the Madrox Supervision system.

## Available Examples

### 1. Supervision Integration (`supervision_integration_example.py`)

Comprehensive examples covering all supervision integration patterns:

- **Basic Supervision**: Autonomous monitoring of a Madrox network
- **Supervised Network**: Creating a complete supervised development team
- **Embedded Supervision**: Supervision without dedicated Claude instance
- **Manual Control**: Full lifecycle control over supervision
- **Custom Configurations**: Different configurations for various scenarios

**Run it:**
```bash
uv run python examples/supervision_integration_example.py
```

### 2. Playwright Integration (`playwright_spawn.py`, `playwright_web_scraper.py`)

Examples of spawning instances with Playwright MCP server for browser automation.

**Run it:**
```bash
uv run python examples/playwright_spawn.py
uv run python examples/playwright_web_scraper.py
```

### 3. MCP Server Configuration (`spawn_with_mcp_configs.py`)

Demonstrates spawning instances with custom MCP server configurations.

**Run it:**
```bash
uv run python examples/spawn_with_mcp_configs.py
```

## Quick Start

### Prerequisites

```bash
# Install the package with all dependencies
uv sync --all-groups

# Activate virtual environment
source .venv/bin/activate
```

### Running Examples

#### Run All Supervision Examples

```bash
uv run python examples/supervision_integration_example.py
```

This will demonstrate:
1. Basic autonomous supervision
2. Supervised team creation
3. Embedded supervision mode
4. Manual supervision control
5. Custom configuration patterns

#### Run Individual Patterns

You can modify `supervision_integration_example.py` to run specific examples:

```python
# In main(), comment out examples you don't want to run
async def main():
    # await example_basic_supervision()
    # await example_supervised_network()
    await example_embedded_supervision()  # Only run this one
    # await example_manual_control()
    # await example_custom_configuration()
```

## Example Patterns

### Pattern 1: Basic Autonomous Supervision

```python
from supervision.integration import spawn_supervisor
from supervision.supervisor import SupervisionConfig
from orchestrator.instance_manager import InstanceManager

# Setup
manager = InstanceManager(config)

# Spawn supervisor
supervisor_id, supervisor = await spawn_supervisor(
    instance_manager=manager,
    config=SupervisionConfig(
        stuck_threshold_seconds=180,
        evaluation_interval_seconds=20
    )
)

# Supervisor now monitors autonomously
```

### Pattern 2: Supervised Team

```python
from supervision.integration import spawn_supervised_network

# Create complete supervised team
network = await spawn_supervised_network(
    instance_manager=manager,
    participant_configs=[
        {"name": "dev1", "role": "frontend_developer"},
        {"name": "dev2", "role": "backend_developer"},
        {"name": "tester", "role": "testing_specialist"},
    ]
)

supervisor_id = network["supervisor_id"]
participant_ids = network["participant_ids"]
```

### Pattern 3: Embedded Supervision

```python
from supervision.integration import attach_supervisor

# Attach without spawning instance
supervisor = await attach_supervisor(
    instance_manager=manager,
    config=SupervisionConfig(enable_auto_intervention=False)
)

# Manual start/stop control
await supervisor.start()
# ... your logic ...
await supervisor.stop()
```

### Pattern 4: Manual Control

```python
from supervision.supervisor import SupervisorAgent, SupervisionConfig

# Create agent manually
supervisor = SupervisorAgent(
    instance_manager=manager,
    config=SupervisionConfig()
)

# Full control
await supervisor.start()

# Check issues
issues = await supervisor.get_detected_issues()

# Get interventions
interventions = supervisor.get_interventions()

await supervisor.stop()
```

## Configuration Examples

### Development Configuration

Fast feedback for development:

```python
SupervisionConfig(
    stuck_threshold_seconds=60,      # 1 minute
    evaluation_interval_seconds=5,   # Check every 5 seconds
    max_concurrent_helpers=5
)
```

### Production Configuration

Conservative settings for production:

```python
SupervisionConfig(
    stuck_threshold_seconds=600,     # 10 minutes
    evaluation_interval_seconds=60,  # Check every minute
    max_concurrent_helpers=3
)
```

### Monitoring-Only Configuration

Observation without automatic intervention:

```python
SupervisionConfig(
    enable_auto_intervention=False,
    enable_progress_tracking=True,
    enable_pattern_analysis=True
)
```

### High-Throughput Configuration

For busy networks with many instances:

```python
SupervisionConfig(
    evaluation_interval_seconds=15,
    max_concurrent_helpers=10,
    helper_timeout_seconds=300
)
```

## Logging

All examples use structured logging. To adjust log levels:

```python
import logging

# Set supervision logging level
logging.getLogger("supervision").setLevel(logging.DEBUG)

# Set orchestrator logging level
logging.getLogger("orchestrator").setLevel(logging.INFO)

# Set root logging level
logging.basicConfig(level=logging.INFO)
```

## Troubleshooting

### ImportError: No module named 'supervision'

```bash
# Ensure package is installed
uv sync

# Verify installation
uv pip list | grep claude-orchestrator-mcp
```

### Supervisor Not Detecting Issues

- Check `evaluation_interval_seconds`: May be too long
- Verify `stuck_threshold_seconds`: May be too high
- Ensure instances are actually stuck/stalled

### Too Many Interventions

- Increase `stuck_threshold_seconds`
- Reduce `max_concurrent_helpers`
- Set `enable_auto_intervention=False` for manual control

### Resource Issues

- Reduce `max_concurrent_helpers`
- Increase `evaluation_interval_seconds`
- Use `attach_supervisor()` instead of `spawn_supervisor()` to avoid extra instance

## Next Steps

1. **Read the Integration Guide**: See [INTEGRATION_GUIDE.md](../INTEGRATION_GUIDE.md) for detailed documentation

2. **Check Dependency Setup**: See [DEPENDENCY_SETUP.md](../DEPENDENCY_SETUP.md) for installation instructions

3. **Explore the API**: Check the source code in `src/supervision/` for advanced usage

4. **Run Tests**: Execute `pytest tests/` to see supervision in action

5. **Build Your Integration**: Use these examples as a starting point for your own implementation

## Additional Resources

- **Main Documentation**: `../README.md`
- **Integration Guide**: `../INTEGRATION_GUIDE.md`
- **Dependency Setup**: `../DEPENDENCY_SETUP.md`
- **API Reference**: See integration guide for complete API surface

## Support

For issues or questions:

- Check the integration guide
- Review example code
- Examine test cases in `tests/`
- Review source code in `src/supervision/`
