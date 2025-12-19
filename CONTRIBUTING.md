# Contributing to Madrox

Welcome! Thank you for your interest in contributing to Madrox. Madrox is an MCP (Model Context Protocol) server that orchestrates multiple Claude CLI instances as separate processes, enabling powerful multi-agent workflows and coordinated task execution.

We welcome contributions from developers, researchers, and community members.

## Development Setup

For detailed setup instructions, see [CLAUDE.md](CLAUDE.md).

**Quick Start:**

```bash
# Install dependencies
uv sync --all-groups

# Activate virtual environment
source .venv/bin/activate

# Run the server
python run_orchestrator.py
```

**Prerequisites:**
- Python 3.11+
- Git
- Tmux (for instance management)

## Pull Request Guidelines

### Branch Naming Conventions

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `docs/description` - Documentation updates

### PR Process

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/your-feature`
3. Make changes and run tests
4. Commit with clear messages: `git commit -m "feat: Add new feature"`
5. Push and create a PR

### Before Submitting

- Run tests: `uv run pytest tests/ -v`
- Format code: `uv run ruff format src/ tests/`
- Check linting: `uv run ruff check src/ tests/`

## Code Style Guidelines

### Formatting and Linting

We use **ruff** for code formatting and linting:

```bash
# Format code
uv run ruff format src/ tests/

# Check linting
uv run ruff check src/ tests/`
```

### Type Hints

Type hints are **required** for all code. Use Python 3.11+ syntax:

```python
def spawn_instance(
    instance_id: str,
    role: str,
    timeout: int | None = None,
) -> Instance | None:
    pass
```

### Type Checking

```bash
uv run mypy src/
```

## Testing Requirements

We use **pytest** with async support.

### Running Tests

```bash
# Full test suite
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ -v --cov=src/orchestrator --cov-report=html

# Single test
uv run pytest tests/test_orchestrator.py::TestInstanceManager::test_spawn_instance_basic -v
```

### Coverage

- Aim for >80% coverage on new code
- Critical paths require 100% coverage
- Use `@pytest.mark.asyncio` for async tests

## Issue Reporting Guidelines

### Bug Reports

Create an issue with:

- **Description**: Clear description of the bug
- **Steps to Reproduce**: Numbered steps
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: OS, Python version, Madrox version

### Feature Requests

Create an issue with:

- **Use Case**: Problem this solves
- **Proposed Solution**: How it should work
- **Alternatives**: Other approaches considered

### Labels

- `bug` - Something broken
- `enhancement` - New feature
- `documentation` - Docs update
- `question` - Usage question

## License

By contributing, you agree your contributions will be licensed under the project's license.

---

Thank you for contributing to Madrox!
