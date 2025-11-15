# Madrox Launcher Scripts

Convenience wrapper scripts for starting the Madrox orchestrator in different modes.

## Scripts

### madrox-server
Starts the Madrox HTTP server (for Claude Code clients)

**Usage:**
```bash
# Basic usage
./scripts/bin/madrox-server

# With custom configuration
MAX_INSTANCES=8 MADROX_TRANSPORT=http ./scripts/bin/madrox-server

# With custom port
ORCHESTRATOR_PORT=8002 ./scripts/bin/madrox-server
```

**Environment Variables:**
- `ORCHESTRATOR_PORT` - Server port (default: 8001)
- `MAX_INSTANCES` - Maximum concurrent instances (default: 10)
- `MADROX_TRANSPORT` - Transport mode: `http` or `stdio` (default: http)

**Equivalent Command:**
```bash
MAX_INSTANCES=8 MADROX_TRANSPORT=http uv run python run_orchestrator.py
```

### madrox-mcp
Starts the Madrox MCP server in STDIO mode (for Codex CLI clients)

**Usage:**
```bash
# Basic usage
./scripts/bin/madrox-mcp

# With custom configuration
MAX_INSTANCES=5 ./scripts/bin/madrox-mcp
```

**Environment Variables:**
- `MAX_INSTANCES` - Maximum concurrent instances (default: 10)
- `MADROX_TRANSPORT` - Automatically set to `stdio`
- `MADROX_HTTP_SERVER` - HTTP server URL for proxying (default: http://localhost:8001)

**Equivalent Command:**
```bash
uv run python scripts/bin/run_orchestrator_stdio.py
```

**Note:** This script is typically used via MCP client configuration, not run directly.

## Installation

Both scripts automatically:
1. Detect the repository root
2. Use `uv run` if available, otherwise fall back to system Python
3. Handle virtual environment activation

No additional setup required beyond having `uv` installed or a Python environment with dependencies.

## Codex CLI Configuration

To use `madrox-mcp` with Codex CLI, add to `~/.codex/config.toml`:

```toml
[mcp_servers.madrox]
command = "/path/to/madrox/scripts/bin/madrox-mcp"
```

Or with absolute path resolution:

```toml
[mcp_servers.madrox]
command = "bash"
args = ["-c", "cd /path/to/madrox && ./scripts/bin/madrox-mcp"]
```
