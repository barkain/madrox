# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Setup
```bash
# Install dependencies
uv sync --all-groups

# Activate virtual environment
source .venv/bin/activate
```

### Running the Server
```bash
# Start MCP server (preferred method)
python run_orchestrator.py

# Alternative direct start
uv run python -c "from src.orchestrator.server import main; import asyncio; asyncio.run(main())"
```

### Testing
```bash
# Run full test suite (26 tests)
uv run pytest tests/test_orchestrator.py -v

# Run with coverage
uv run pytest tests/test_orchestrator.py -v --cov=src/orchestrator --cov-report=html

# Run single test
uv run pytest tests/test_orchestrator.py::TestInstanceManager::test_spawn_instance_basic -v

# Run integration demo
uv run python tests/integration_demo.py
```

### Code Quality
```bash
# Format and lint
uv run ruff format src/ tests/
uv run ruff check src/ tests/

# Type checking
uv run mypy src/
```

## Architecture

### Core Components

**Madrox** is an MCP (Model Context Protocol) server that orchestrates multiple Claude CLI instances as separate processes. The architecture follows a manager-worker pattern where a central InstanceManager spawns and controls multiple isolated Claude Code CLI processes.

**Key Components:**

1. **InstanceManager** (`src/orchestrator/instance_manager.py`) - Central orchestrator that:
   - Spawns Claude Code CLI processes using `subprocess.Popen`
   - Manages process lifecycle and state transitions
   - Communicates via stdin/stdout using JSON streaming format
   - Handles message routing and response buffering
   - Tracks resource usage and enforces limits

2. **MCP Server** (`src/orchestrator/server.py`) - FastAPI-based server exposing orchestration capabilities as MCP tools. Handles tool registration, request validation, and response formatting.

3. **Data Models** - Dual model system:
   - `models.py`: SQLAlchemy models for database persistence (future capability)
   - `simple_models.py`: Lightweight Pydantic-free models for current runtime use

### Instance Lifecycle

Instances follow a state machine pattern:
- `initializing` → `running` → `busy` (when processing) → `idle` → `terminated`
- Error states: `error`, `timeout`
- Resource enforcement triggers automatic termination

### Role System

10 predefined roles with specialized system prompts:
- `architect`: System design and architecture
- `frontend_developer`: React/Vue/Angular expertise
- `backend_developer`: API and server development
- `data_scientist`: ML/AI and data analysis
- `devops`: Infrastructure and deployment
- `designer`: UI/UX design
- `qa_engineer`: Testing and quality
- `security`: Security analysis
- `project_manager`: Project coordination
- `general`: Default general purpose

### Resource Management

Each instance tracks:
- Token usage (per-instance and global)
- Cost accumulation
- Request counts
- Timeout monitoring (configurable, default 60 minutes)
- Resource limits enforcement via health checks

### Workspace Isolation

Each instance gets an isolated workspace directory:
- Base: `/tmp/claude_orchestrator/` (configurable)
- Instance workspace: `{base}/{instance_id}/`
- Automatic cleanup on termination

### Claude CLI Process Communication

Each Claude/Codex instance runs as a separate interactive tmux session:
- **Command**: `claude --permission-mode bypassPermissions --dangerously-skip-permissions` (interactive mode)
- **Communication**: Terminal I/O via tmux panes, not JSON streaming
- **Output Capture**: Use `get_tmux_pane_content()` for detailed terminal output
- **Limitation**: Tool event tracking via JSON not available in interactive mode
- **Monitoring**: Use `live_status` API for execution time, state, and last activity

### Message Flow

1. Client sends request to MCP server
2. Server validates and routes to TmuxInstanceManager
3. TmuxInstanceManager sends message to Claude/Codex tmux session via terminal
4. Instance processes request in interactive mode (rich terminal UI)
5. TmuxInstanceManager monitors tmux pane output for response completion
6. Response extracted from terminal output and returned to client
7. Resource tracking updated based on activity

### Live Status API

Real-time instance monitoring endpoint:
- **Endpoint**: `GET /instances/{id}/live_status`
- **MCP Tool**: `get_live_instance_status`
- **Returns**: execution_time, state, last_activity, event_counts, last_output
- **Use Case**: Monitor long-running operations, track instance uptime
- **Note**: Tool-level details require `get_tmux_pane_content()` for terminal inspection

### Coordination Patterns

Three coordination types supported:
- `parallel`: Multiple instances work simultaneously
- `sequential`: Pipeline of instance operations
- `hierarchical`: Parent-child delegation trees

## Configuration

Environment variables:
- `ORCHESTRATOR_PORT`: Server port (default: 8001)
- `MAX_INSTANCES`: Concurrent instance limit (default: 10)
- `WORKSPACE_DIR`: Base workspace path
- `LOG_LEVEL`: Logging verbosity

Note: ANTHROPIC_API_KEY is no longer required as the system now spawns Claude Code CLI processes that use the user's existing Claude authentication.

## Documentation

For comprehensive documentation beyond this development guide, see:

- **[docs/SETUP.md](docs/SETUP.md)** - Complete installation and setup guide with MCP client configuration
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Detailed system architecture, components, and design patterns
- **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)** - Complete API reference for all MCP tools and HTTP endpoints
- **[docs/FEATURES.md](docs/FEATURES.md)** - Feature documentation with usage patterns and examples
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Debugging guide and common issue resolution

## Testing Strategy

Tests use pytest with async support. Key test patterns:
- Fixture-based setup with `manager` fixture
- Async test methods with `@pytest.mark.asyncio`
- Mock `subprocess.Popen` for CLI process simulation
- Mock stdin/stdout communication with JSON responses
- Resource limit enforcement validation
- Concurrent operation testing

## Development Notes

- Python 3.11+ required for modern syntax (datetime.UTC, type unions)
- Heavy async/await usage - maintain async patterns
- Resource cleanup critical - always terminate tmux sessions properly
- Health checks run automatically - implement cleanup in new features
- MCP protocol compliance required for Claude CLI integration
- Each instance runs in isolated tmux session - ensure proper session management
- Interactive terminal I/O, not JSON streaming - parse terminal output for responses
- Process termination uses graceful shutdown (SIGTERM) with fallback to SIGKILL
- **Tool tracking limitation**: Claude CLI `--output-format stream-json` only works with `--print` (non-interactive mode)
- Madrox uses interactive tmux for bidirectional communication - incompatible with `--print` mode
- Use `get_tmux_pane_content()` for detailed tool execution inspection
- Use `live_status` API for execution time and state monitoring