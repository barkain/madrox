# STDIO Transport Support

This document describes the native STDIO transport implementation for Madrox MCP server.

## Overview

Madrox now supports **dual transport modes**:

1. **HTTP/SSE Transport** - For Claude Code clients (existing functionality)
2. **STDIO Transport** - For Codex CLI clients (new functionality)

Both transports share the same `TmuxInstanceManager` backend and provide identical MCP tool functionality.

## Auto-Detection

The transport mode is automatically detected on startup:

```bash
# Terminal input (stdin.isatty() == True) → HTTP server
python run_orchestrator.py

# Piped input (stdin.isatty() == False) → STDIO server
echo '{"jsonrpc":"2.0",...}' | python run_orchestrator.py
```

## Manual Override

Force a specific transport using the `MADROX_TRANSPORT` environment variable:

```bash
# Force STDIO mode
MADROX_TRANSPORT=stdio python run_orchestrator.py

# Force HTTP mode
MADROX_TRANSPORT=http python run_orchestrator.py
```

## Codex CLI Configuration

Add Madrox to your Codex CLI configuration file (`~/.codex/config.toml`):

```toml
[mcp_servers.madrox]
command = "python"
args = ["/absolute/path/to/madrox/run_orchestrator.py"]
env = { MADROX_TRANSPORT = "stdio" }

# Optional: Configure environment variables
# env = {
#   MADROX_TRANSPORT = "stdio",
#   MAX_INSTANCES = "20",
#   WORKSPACE_DIR = "/tmp/madrox_workspace",
#   LOG_LEVEL = "DEBUG"
# }
```

### Verification

After configuring, verify Madrox is available in Codex:

```bash
# List available MCP servers
codex mcp list

# Test Madrox connection
codex mcp test madrox
```

## Testing

Two test scripts are provided:

### STDIO Transport Test

```bash
python test_stdio_transport.py
```

Expected output:
```
✅ STDIO transport test PASSED
✅ Tools list retrieved: 26 tools available
```

### HTTP Transport Test

```bash
python test_http_transport.py
```

Expected output:
```
✅ HTTP health endpoint test PASSED
✅ HTTP root endpoint test PASSED
✅ HTTP MCP adapter test PASSED
```

## Architecture

### STDIO Transport Flow

```
Codex CLI → stdin → run_orchestrator.py → OrchestrationMCPServer
                                            ↓
                                       FastMCP.run_stdio_async()
                                            ↓
                                       InstanceManager (shared)
                                            ↓
                                       TmuxInstanceManager
                                            ↓
                                       Claude/Codex Instances
```

### HTTP Transport Flow

```
Claude Code → HTTP → run_orchestrator.py → ClaudeOrchestratorServer
                                              ↓
                                         FastAPI + MCPAdapter
                                              ↓
                                         InstanceManager (shared)
                                              ↓
                                         TmuxInstanceManager
                                              ↓
                                         Claude/Codex Instances
```

## Key Features

- **Zero Breaking Changes**: HTTP transport remains unchanged
- **Shared Backend**: Both transports use the same `TmuxInstanceManager`
- **Auto-Detection**: Transparent transport selection based on stdin
- **Protocol Compliance**: Full MCP protocol support via FastMCP library
- **All Tools Available**: Both transports expose identical MCP tool set (26 tools)

## Implementation Details

### Files Modified

1. **`run_orchestrator.py`**
   - Added transport auto-detection logic
   - Added `start_stdio_server()` function
   - Added `MADROX_TRANSPORT` environment variable support

2. **`CLAUDE.md`**
   - Updated "Running the Server" section
   - Updated "Configuration" section
   - Added transport mode documentation

### Files Used (Existing)

1. **`src/orchestrator/mcp_server.py`**
   - Existing `OrchestrationMCPServer` class
   - Uses FastMCP's `run_stdio_async()` method

2. **`src/orchestrator/instance_manager.py`**
   - Existing `InstanceManager` with FastMCP decorators
   - Shared by both transports

3. **`src/orchestrator/server.py`**
   - Existing `ClaudeOrchestratorServer` for HTTP transport
   - Unchanged

## Dependencies

No new dependencies required. Uses existing `fastmcp>=2.12.4` which includes STDIO support.

## Troubleshooting

### STDIO mode not starting

Check that `MADROX_TRANSPORT=stdio` is set or that stdin is piped:

```bash
# Verify environment
env | grep MADROX_TRANSPORT

# Test with echo pipe
echo '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | python run_orchestrator.py
```

### HTTP mode not starting

Ensure port 8001 is available:

```bash
# Check if port is in use
lsof -i :8001

# Use different port
ORCHESTRATOR_PORT=8002 python run_orchestrator.py
```

### Tools not available

Verify FastMCP version:

```bash
python -c "import fastmcp; print(fastmcp.__version__)"
# Should be >= 2.12.4
```

## Future Enhancements

Potential improvements for STDIO transport:

1. **Performance Metrics**: Add STDIO-specific latency tracking
2. **Connection Management**: Implement graceful reconnection
3. **Logging**: Enhance STDIO-specific debug logging
4. **Documentation**: Add more Codex CLI usage examples
