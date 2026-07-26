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

### Plugin Mode (Claude Code)

Madrox can be installed as a Claude Code plugin. The plugin is configured via `.mcp.json` and managed by `start_plugin.sh`.

```bash
# Install from within Claude Code
/plugin install /path/to/madrox
```

**How it works:**
- Claude Code runs `start_plugin.sh` on startup
- The script starts the HTTP backend (port 8001) and Next.js frontend dashboard (port 3002) in the background
- Waits for the backend health check to pass
- Runs a STDIO MCP proxy in the foreground (Claude Code connects to this)
- On exit, background processes are cleaned up automatically
- The STDIO server is a proxy — all tool calls are forwarded to the HTTP backend via HTTP

**`/madrox:dashboard` skill:** Opens the Madrox Monitor dashboard at http://localhost:3002 in the browser. Defined in `skills/dashboard/SKILL.md`.

### Running the Server

The server supports two transport modes that are auto-detected:

**HTTP/SSE Transport (Claude Code):**
```bash
# Start HTTP server (default when running in terminal)
python run_orchestrator.py

# Server starts on http://localhost:8001
# Uses Server-Sent Events (SSE) for MCP protocol
```

**STDIO Transport (Codex CLI):**
```bash
# STDIO mode is auto-activated when stdin is piped
# Used by Codex CLI MCP client configuration

# Force STDIO mode via environment variable
MADROX_TRANSPORT=stdio python run_orchestrator.py

# Example Codex CLI config (~/.codex/config.toml):
# [mcp_servers.madrox]
# command = "python"
# args = ["/path/to/madrox/run_orchestrator.py"]
# env = { MADROX_TRANSPORT = "stdio" }
```

**Quick Start with start.sh:**
```bash
# Start both backend (port 8001) and frontend dashboard (port 3002)
./start.sh

# Start only the backend
./start.sh --be

# Start only the frontend
./start.sh --fe
```
Note: When backgrounding the backend, set `MADROX_TRANSPORT=http` to prevent STDIO auto-detection.

**Transport Auto-Detection:**
- Terminal input (stdin.isatty()) → HTTP server on port 8001
- Piped input → STDIO server for MCP protocol
- Override with `MADROX_TRANSPORT=stdio` or `MADROX_TRANSPORT=http`

### Testing
```bash
# Run full test suite
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ -v --cov=src/orchestrator --cov-report=html

# Run specific test files
uv run pytest tests/test_llm_summarizer.py -v
uv run pytest tests/test_monitoring_service.py -v
uv run pytest tests/test_mcp_tools_integration.py -v

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

1. **TmuxInstanceManager** (`src/orchestrator/tmux_instance_manager.py`) - Central orchestrator that:
   - Spawns Claude Code CLI processes in isolated tmux sessions
   - Manages process lifecycle and state transitions
   - Communicates via terminal I/O using tmux send-keys and capture-pane
   - Handles message routing and response parsing from terminal output
   - Tracks resource usage and enforces limits

2. **MCP Server** (`src/orchestrator/server.py`) - FastAPI-based server exposing orchestration capabilities as MCP tools. Handles tool registration, request validation, and response formatting.

3. **LLMSummarizer** (`src/orchestrator/llm_summarizer.py`) - Optional activity summarization service:
   - Generates natural language summaries of instance activity via OpenRouter API
   - Supports multiple free and paid LLM models (Gemini, DeepSeek, Claude, etc.)
   - Robust error handling with automatic fallback summaries
   - Configurable via OPENROUTER_API_KEY environment variable

4. **Data Models** - Dual model system:
   - `models.py`: SQLAlchemy models for database persistence (future capability)
   - `simple_models.py`: Lightweight Pydantic-free models for current runtime use

5. **Harness registry** (`src/orchestrator/harnesses.py`) - One class per CLI agent
   (`ClaudeHarness`, `CodexHarness`, `GrokHarness`) holding everything that differs
   between them: executable, yolo/full-autonomy flags, model flag, launch and resume
   commands, MCP registration style, and the terminal markers that mean "ready" /
   "idle" / "trust prompt". The manager code is harness-agnostic — there are no
   `if instance_type == "codex"` branches outside this module.

### Harnesses and Models

Supported harnesses (the `instance_type` / spawn tool):

| Harness | Tool | CLI | Yolo mode | Default model |
|---------|------|-----|-----------|---------------|
| Claude Code | `spawn_claude` | `claude` | `--permission-mode bypassPermissions --dangerously-skip-permissions` | `claude-opus-5` |
| Codex | `spawn_codex` | `codex` | `--dangerously-bypass-approvals-and-sandbox` | `gpt-5.6-sol` |
| Grok Build | `spawn_grok` | `grok` | `--always-approve` (the `/yolo` switch) | `grok-build-0.1` |

Model ids are never validated against an allowlist — any string is forwarded to the
CLI, so newly released models work without a code change. When a caller omits
`model`, the harness default is resolved in `spawn_instance` (a single choke point
shared by the MCP tools, the HTTP adapter and direct calls) from:

1. `MADROX_MODEL_<HARNESS>` env var (e.g. `MADROX_MODEL_CLAUDE`)
2. `<harness>.default` in `config/models.yaml`
3. nothing — the CLI picks its own default

`config/models.yaml` also accepts `command:` (executable override) and `extra_args:`
per harness; `MADROX_MODELS_CONFIG` points at a different config file and
`MADROX_<HARNESS>_BIN` overrides one executable.

**Adding a harness**: subclass `Harness`, add it to `_HARNESS_CLASSES`, and add a
`spawn_<name>` tool in `instance_manager/spawning.py` (the MCP adapter derives its
spawn routing from the registry automatically).

### Instance Lifecycle

Instances follow a state machine pattern:
- `initializing` → `running` → `busy` (when processing) → `idle` → `terminated`
- Error states: `error`, `timeout`
- Resource enforcement triggers automatic termination (only if explicit limits configured)

**Persistent Instances**: Instances survive backend restarts by default. State is persisted to `{log_dir}/state/instances.json` via atomic writes. On startup, live tmux sessions are reconnected; dead sessions are recovered with the harness's resume command (`claude --continue`, `codex resume --last`, `grok --resume`) to preserve conversation context.

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
- Timeout monitoring (disabled by default for persistent instances; set `instance_timeout_minutes` > 0 to enable)
- Resource limits enforcement via health checks (token/cost limits only)

### Workspace Isolation

Each instance gets an isolated workspace directory:
- Base: `/tmp/madrox_logs/artifacts/{session_id}/` (configurable via `ARTIFACTS_DIR`)
- Instance workspace: `{base}/{instance_id}/`
- Workspaces persist across backend restarts (stable `session_id` reused)
- Conversation context stored by Claude CLI in `~/.claude/projects/` keyed by workspace path

### State Persistence

Instance state is persisted to disk for reliability across backend restarts:

- **StateStore** (`src/orchestrator/state_store.py`): JSON file with atomic writes (fcntl locking + temp file rename)
- **Location**: `{log_dir}/state/instances.json` and `server.json`
- **Saved on**: every state mutation (spawn, idle/busy transitions, terminate)
- **Server state**: stable `session_id` reused across restarts to keep workspace paths consistent
- **On startup**: `_reconnect_or_cleanup_sessions()` reconnects live tmux sessions, recovers dead ones, kills orphans
- **Recovery**: dead sessions respawned with the harness resume command (`claude --continue` / `codex resume --last` / `grok --resume`)
- **Shutdown**: `shutdown()` saves state but does NOT terminate instances — tmux sessions survive for reconnection

**MCP Tools for persistence:**
- `list_persisted_instances`: discover previous instances available to resume
- `resume_instance(instance_id, name?, model?)`: spawn new instance continuing a previous one's conversation

### CLI Process Communication

Each instance runs as a separate interactive tmux session:
- **Command**: built by its harness, always in full-autonomy mode when `bypass_isolation` is set (e.g. `claude --permission-mode bypassPermissions --dangerously-skip-permissions`)
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

### Terminal REST Endpoint

- **Endpoint**: `GET /instances/{instance_id}/terminal?lines=N`
- **Returns**: Raw tmux pane content for the instance
- **Use Case**: Used by the Madrox Monitor dashboard's terminal viewer

### Instance Communication

- **Parent-child**: Parent spawns children and communicates via `send_to_instance` / `reply_to_caller`
- **Peer discovery**: `get_peers` allows sibling instances (same parent) to discover each other for direct peer-to-peer messaging without routing through the parent

### Coordination Patterns

Three coordination types supported:
- `parallel`: Multiple instances work simultaneously
- `sequential`: Pipeline of instance operations
- `hierarchical`: Parent-child delegation trees

## Configuration

Environment variables:
- `MADROX_TRANSPORT`: Transport mode - `http` (default for terminal) or `stdio` (auto for piped)
- `ORCHESTRATOR_PORT`: HTTP server port (default: 8001, HTTP mode only)
- `ORCHESTRATOR_HOST`: HTTP server host (default: localhost, HTTP mode only)
- `MAX_INSTANCES`: Concurrent instance limit (default: 10)
- `WORKSPACE_DIR`: Base workspace path (default: /tmp/claude_orchestrator)
- `LOG_DIR`: Log directory (default: /tmp/madrox_logs). State files stored in `{LOG_DIR}/state/`
- `LOG_LEVEL`: Logging verbosity (default: INFO)
- `OPENROUTER_API_KEY`: Optional API key for LLM-based activity summarization (OpenRouter)
- `ARTIFACTS_DIR`: Base artifacts directory (default: /tmp/madrox_logs/artifacts)

**Transport Modes:**
- **HTTP/SSE**: Used by Claude Code clients, provides web UI and REST API
- **STDIO**: Used by Codex CLI clients, MCP protocol over stdin/stdout

**Dashboard (Madrox Monitor):**
- Runs on port 3002 (started via `./start.sh` or `./start.sh --fe`)
- Provides real-time network graph visualization of instance hierarchy
- Includes terminal viewers for each instance

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