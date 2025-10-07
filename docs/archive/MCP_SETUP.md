# Testing Madrox as an MCP Server with Claude Code

## Quick Start

The MCP server is currently running on `http://localhost:8001`. Here's how to integrate it with Claude Code:

## 1. Server is Running ✅

The server is already running in the background on port 8001. You can verify it's working by visiting:
- http://localhost:8001 (server info)
- http://localhost:8001/health (health check)
- http://localhost:8001/tools (list available tools)

## 2. Configure Claude Code

To use this MCP server in Claude Code, you need to add it to your Claude Desktop configuration:

### Option A: Add to Claude Desktop Config (Recommended)

Edit your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the Madrox server configuration (remove the `env` block if you don't need an Anthropic API key):

```json
{
  "mcpServers": {
    "madrox": {
      "command": "uv",
      "args": ["run", "python", "run_orchestrator.py"],
      "cwd": "path/to/madrox",
      "env": {
        "ANTHROPIC_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

> ℹ️ Run `command -v uv` in your terminal to confirm the exact path to the
> binary and replace the `command` value above. Claude launches MCP servers
> with a very short `PATH`, so the absolute path prevents “No such file or
> directory (os error 2)” startup failures.

### Option B: Use Direct HTTP Connection

Since the server is already running, you can also configure it as an HTTP MCP server (the MCP adapter is mounted at `/mcp`). Claude subscribers typically do **not** need an API key for this mode.

```json
{
  "mcpServers": {
    "madrox": {
      "url": "http://localhost:8001/mcp",
      "transport": "http"
    }
  }
}
```

## 3. Register with Claude CLI

Register the server with the Claude CLI:

```bash
# Register the MCP server
claude mcp add madrox http://localhost:8001/mcp --transport http

# Optional: add API key if needed for spawned instances
claude mcp add madrox http://localhost:8001/mcp --transport http \
  -e ANTHROPIC_API_KEY=your-api-key
```

**Note:** Model selection happens when spawning instances via MCP tools, not during registration.

For ad-hoc conversations outside MCP you can launch the CLI directly:

```bash
claude --model claude-sonnet-4-20250514
claude --model claude-opus-4-1-20250805
claude --model claude-3-5-haiku-20241022
```

## 4. Available MCP Tools

Once configured, you'll have access to these tools in Claude:

- **`spawn_claude`** - Create new Claude instances with specific roles:
  - architect, frontend_developer, backend_developer, data_scientist, devops, designer, qa_engineer, security, project_manager, general

- **`send_to_instance`** - Send messages to specific instances

- **`get_instance_output`** - Retrieve output from instances

- **`coordinate_instances`** - Orchestrate multiple instances for complex tasks

- **`terminate_instance`** - Clean up instances when done

## 5. Testing the Integration

In a new Claude Code chat, you can test the integration:

```
Can you use the madrox MCP server to spawn a frontend developer instance and ask it about React best practices?
```

Or try orchestrating multiple instances:

```
Use the madrox server to coordinate an architect and backend developer to design a REST API.
```

## 6. Monitoring

You can monitor the server:
- Check server logs in the terminal where it's running
- Use the test script: `uv run python test_mcp_server.py`
- Check health endpoint: `curl http://localhost:8001/health`

## 7. Stopping the Server

To stop the server, use:
```bash
# Find the process
ps aux | grep "run_orchestrator.py"

# Or if you know the background job ID (340264):
kill 49198
```

## Troubleshooting

1. **Server not starting**: Check if port 8001 is already in use
2. **API key issues**: Ensure ANTHROPIC_API_KEY is set in your environment
3. **Connection refused**: Make sure the server is running (`uv run python run_orchestrator.py`) and that your HTTP configuration points to `/mcp`
4. **MCP tools not showing**: Restart Claude Desktop after updating config

## Current Status

✅ Server is running on http://localhost:8001 (MCP adapter at /mcp)
✅ All health checks passing
✅ MCP tools are available and functional
✅ Test instance spawn/terminate working

The server is ready for use with Claude Code!
