# Supervision Package Dependency Setup

This document explains how to add the Madrox Supervision package as a dependency in different scenarios.

## Repository Structure

The Madrox Supervision system is part of the `claude-orchestrator-mcp` package, which includes:

- **orchestrator**: Core instance management and orchestration
- **supervision**: Autonomous monitoring and supervision

Both modules are packaged together in the same distribution.

## Using Supervision in Your Code

### 1. Within the Same Repository

If you're working within the `madrox-supervision` repository, import directly:

```python
from supervision.integration import spawn_supervisor, attach_supervisor
from supervision.supervisor import SupervisorAgent, SupervisionConfig
from orchestrator.instance_manager import InstanceManager
```

### 2. As a Local Editable Package

To use the supervision package in another project during development:

```bash
# Navigate to your project
cd /path/to/your/project

# Add as editable dependency
uv add --editable /Users/nadavbarkai/dev/madrox-supervision

# Or add to pyproject.toml manually:
# [project.dependencies]
# claude-orchestrator-mcp = {path = "/Users/nadavbarkai/dev/madrox-supervision", editable = true}
```

Then in your code:
```python
from supervision.integration import spawn_supervisor
from orchestrator.instance_manager import InstanceManager
```

### 3. As a Git Dependency

To add the supervision package from a git repository:

```bash
# Add as git dependency
uv add git+https://github.com/yourorg/madrox-supervision.git

# Or specify a branch/tag
uv add git+https://github.com/yourorg/madrox-supervision.git@main
uv add git+https://github.com/yourorg/madrox-supervision.git@v1.0.0
```

In `pyproject.toml`:
```toml
[project]
dependencies = [
    "claude-orchestrator-mcp @ git+https://github.com/yourorg/madrox-supervision.git"
]
```

### 4. As a Published Package

Once published to PyPI:

```bash
uv add claude-orchestrator-mcp

# Or with version constraint
uv add "claude-orchestrator-mcp>=1.0.0"
```

## Package Configuration

The supervision package is configured in `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/supervision", "src/orchestrator"]

[project]
name = "claude-orchestrator-mcp"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.104.1",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    "httpx>=0.25.0",
    "anthropic>=0.8.0",
    "python-dotenv>=1.0.0",
    "mcp>=1.15.0",
    "mcp-python>=0.1.4",
    "aiohttp>=3.12.15",
    "sse-starlette>=3.0.2",
    "libtmux>=0.46.2",
    "psutil>=7.1.0",
]
```

## Development Setup

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/yourorg/madrox-supervision.git
cd madrox-supervision

# Install with all development dependencies
uv sync --all-groups

# Activate virtual environment
source .venv/bin/activate
```

### Installing in Another Project

For development across multiple projects:

```bash
# In your main project
cd /path/to/main/project

# Add supervision as editable dependency
uv add --editable /path/to/madrox-supervision

# This allows you to:
# - Edit supervision code
# - See changes immediately in your project
# - Test integration without rebuilding
```

## Import Patterns

### Basic Usage

```python
# Import integration layer (recommended)
from supervision.integration import (
    spawn_supervisor,
    attach_supervisor,
    spawn_supervised_network
)

# Import configuration
from supervision.supervisor import SupervisionConfig

# Import orchestrator
from orchestrator.instance_manager import InstanceManager
```

### Advanced Usage

```python
# Direct component access
from supervision.supervisor import SupervisorAgent
from supervision.tracking import ProgressTracker
from supervision.events import EventCollector, EventType
from supervision.analysis import PatternDetector
from supervision.coordination import CoordinationManager
```

### Type Hints

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supervision.supervisor import SupervisorAgent
    from orchestrator.instance_manager import InstanceManager

def setup_supervision(manager: 'InstanceManager') -> 'SupervisorAgent':
    # Your code here
    pass
```

## Dependency Management Best Practices

### 1. Version Pinning

For production deployments, pin specific versions:

```toml
[project]
dependencies = [
    "claude-orchestrator-mcp==1.0.0",  # Exact version
]
```

For development, use flexible constraints:

```toml
[project]
dependencies = [
    "claude-orchestrator-mcp>=1.0.0,<2.0.0",  # Major version range
]
```

### 2. Development Dependencies

Keep supervision in dev dependencies if only used for testing:

```toml
[dependency-groups]
dev = [
    "claude-orchestrator-mcp>=1.0.0",
]
```

### 3. Optional Dependencies

If supervision is optional in your project:

```toml
[project.optional-dependencies]
supervision = [
    "claude-orchestrator-mcp>=1.0.0",
]
```

Install with:
```bash
uv add "yourproject[supervision]"
```

## Python Version Requirements

The supervision package requires **Python 3.11+** for:

- Built-in generic types (`list[str]`, `dict[str, Any]`)
- Union type operator (`str | None`)
- Modern async features

Ensure your project meets this requirement:

```toml
[project]
requires-python = ">=3.11"
```

## Verifying Installation

After adding the dependency, verify it's working:

```python
# test_supervision_import.py
def test_imports():
    """Verify supervision package is properly installed."""
    try:
        from supervision.integration import spawn_supervisor
        from supervision.supervisor import SupervisorAgent, SupervisionConfig
        from orchestrator.instance_manager import InstanceManager

        print("✓ All imports successful")
        print(f"✓ SupervisionConfig: {SupervisionConfig}")
        print(f"✓ spawn_supervisor: {spawn_supervisor}")
        return True

    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    exit(0 if success else 1)
```

Run with:
```bash
uv run python test_supervision_import.py
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'supervision'`

**Solution**:
```bash
# Verify installation
uv pip list | grep claude-orchestrator-mcp

# Reinstall if needed
uv sync

# Check Python path
uv run python -c "import sys; print('\\n'.join(sys.path))"
```

### Version Conflicts

**Problem**: Dependency version conflicts

**Solution**:
```bash
# Check dependency tree
uv pip tree

# Update conflicting packages
uv add <package>@latest

# Or use specific compatible versions
uv add "package>=x.y.z,<x.y+1.0"
```

### Editable Install Issues

**Problem**: Changes not reflected in editable install

**Solution**:
```bash
# Reinstall in editable mode
uv pip install -e /path/to/madrox-supervision --force-reinstall

# Or remove and re-add
uv remove claude-orchestrator-mcp
uv add --editable /path/to/madrox-supervision
```

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Test with Supervision

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Setup Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv sync --all-groups

      - name: Run tests
        run: uv run pytest tests/
```

### Docker Integration

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-dev

# Copy application
COPY . .

# Run application
CMD ["uv", "run", "python", "main.py"]
```

## Summary

- **Same Repo**: Import directly from `supervision.*` and `orchestrator.*`
- **Development**: Use `uv add --editable /path/to/madrox-supervision`
- **Production**: Use `uv add claude-orchestrator-mcp` or git dependency
- **Requirements**: Python 3.11+ required
- **Verification**: Test imports with provided script

For more integration details, see [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md).
