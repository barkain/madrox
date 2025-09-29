# Madrox Quick Start Guide

Madrox provides two ways to run the orchestrator, depending on your use case:

## 1. MCP Server for Codex CLI (stdio)

This runs Madrox as an MCP server that integrates with OpenAI's Codex CLI.

### Setup
```bash
# From the Madrox directory
codex mcp add madrox $(pwd)/madrox-mcp
```

### Usage in Codex
```
"Spawn a Claude instance named 'helper' with role 'general'"
"Send 'hello world' to instance helper"
"Get status of all instances"
```

## 2. HTTP Server for Claude Code (FastAPI)

This runs Madrox as an HTTP server that Claude Code can connect to.

### Start the Server
```bash
# From the Madrox directory
./madrox-server

# Or with a custom port
ORCHESTRATOR_PORT=8002 ./madrox-server
```

The server will start on `http://localhost:8001` (or your specified port).

### Usage in Claude Code

Once the server is running, Claude Code can use the Madrox tools to spawn and manage instances.

## Both Methods Support

- **10 Predefined Roles**: general, architect, frontend_developer, backend_developer, testing_specialist, documentation_writer, code_reviewer, debugger, security_analyst, data_analyst
- **Custom System Prompts**: Define your own specialized behaviors
- **Instance Coordination**: Sequential, parallel, or consensus-based multi-agent workflows
- **Persistent Sessions**: Instances maintain context across messages
- **Workspace Isolation**: Each instance gets its own workspace directory

## Prerequisites

1. Install dependencies:
   ```bash
   uv sync --all-groups
   # Or if you don't have uv:
   pip install -r requirements.txt
   ```

2. Ensure Claude CLI is installed and authenticated

## Environment Variables (Optional)

- `MAX_INSTANCES`: Maximum concurrent instances (default: 10)
- `WORKSPACE_DIR`: Base directory for workspaces (default: /tmp/claude_orchestrator)
- `ORCHESTRATOR_PORT`: HTTP server port (default: 8001)
- `LOG_LEVEL`: Logging verbosity (default: INFO)

## Quick Test

### Test MCP Server
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | ./madrox-mcp
```

### Test HTTP Server
```bash
# In one terminal
./madrox-server

# In another terminal
curl http://localhost:8001/health
```

## Troubleshooting

If the scripts don't work:
1. Ensure they're executable: `chmod +x madrox-mcp madrox-server`
2. Check that dependencies are installed: `uv sync` or `pip install -e .`
3. Verify Claude CLI is available: `which claude`
4. Check logs for errors (stderr output for MCP, console output for HTTP)

## Next Steps

- See `STDIO_MCP_SETUP.md` for detailed MCP/Codex setup
- See `README.md` for full API documentation
- Run `pytest tests/` to verify your installation