# Madrox Quick Start

**Prerequisites:** Claude Code CLI installed and authenticated (`claude auth login`)

---

## 🚀 Setup (5 minutes)

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/your-org/madrox.git
cd madrox

# Install dependencies
uv sync --all-groups
```

### 2. Start the Madrox Server

```bash
# Start the HTTP MCP server
./madrox-server

# Server will start on http://localhost:8001
```

**Keep this terminal open.** The server needs to stay running.

### 3. Add Madrox to Claude Code

In a **new terminal**:

```bash
# Add the MCP server to Claude Code
claude mcp add madrox http://localhost:8001/mcp --transport http

# Verify it was added
claude mcp list
```

---

## ✅ Test It

In Claude Code, say:

```
"Spawn a Claude instance named 'helper' with role 'general'"
```

You should see Madrox spawn a new instance. Then try:

```
"Send 'what is 2+2?' to instance helper"
"Get status of all instances"
```

---

## 🎓 Real Example

Try this in Claude Code:

```
"Spawn an architect coordinator with Madrox enabled to help me
implement a REST API. The coordinator should spawn backend,
testing, and documentation specialists as needed."
```

The coordinator will orchestrate a multi-agent team for you!

---

## 🎯 What You Get

- **10 Predefined Roles**: general, architect, frontend_developer, backend_developer, testing_specialist, documentation_writer, code_reviewer, debugger, security_analyst, data_analyst
- **Custom System Prompts**: Define your own specialized behaviors
- **Hierarchical Orchestration**: Instances can spawn their own child instances
- **Multi-Model Support**: Mix Claude and Codex instances in the same workflow
- **Bidirectional Communication**: Parent-child coordination and status updates
- **Workspace Isolation**: Each instance gets its own workspace directory

---

## 🛑 Stop Everything

```bash
# Stop the server (Ctrl+C in the server terminal)
# Or find and kill the process:
ps aux | grep madrox-server
kill <PID>

# Remove from Claude Code (optional)
claude mcp remove madrox
```

---

## 🐛 Troubleshooting

### "Connection refused"
```bash
# Check if server is running
curl http://localhost:8001/health

# Restart the server
./madrox-server
```

### "Permission denied" on ./madrox-server
```bash
chmod +x madrox-server
```

### "Cannot find madrox MCP"
```bash
# Verify server is running first
curl http://localhost:8001/health

# Re-add to Claude Code
claude mcp add madrox http://localhost:8001/mcp --transport http
```

### Claude CLI not found
```bash
# Verify Claude CLI is installed
which claude

# If not installed, see: https://docs.anthropic.com/claude/docs/claude-cli
```

---

## 📊 Check Server Status

```bash
# Health check
curl http://localhost:8001/health

# List all instances
curl http://localhost:8001/instances

# Get specific instance status
curl http://localhost:8001/instances/<instance-id>

# View instance hierarchy
curl http://localhost:8001/network/hierarchy

# List available MCP tools
curl http://localhost:8001/tools
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# Customize server behavior
ORCHESTRATOR_PORT=8001 \
MAX_INSTANCES=20 \
WORKSPACE_DIR=/tmp/claude_orchestrator \
LOG_LEVEL=INFO \
./madrox-server
```

| Variable | Default | Description |
|----------|---------|-------------|
| `ORCHESTRATOR_PORT` | 8001 | HTTP server port |
| `MAX_INSTANCES` | 10 | Max concurrent instances |
| `WORKSPACE_DIR` | `/tmp/claude_orchestrator` | Instance workspace base |
| `LOG_LEVEL` | INFO | Logging verbosity |
| `LOG_DIR` | `/tmp/madrox_logs` | Log file directory |

---

## 🚀 Alternative: Codex CLI

If you're using OpenAI's Codex CLI instead of Claude Code:

```bash
# Add as STDIO MCP server
codex mcp add madrox $(pwd)/madrox-mcp

# Usage in Codex
# "Spawn a Claude instance named 'helper' with role 'general'"
```

---

## 📚 Next Steps

- **Full Documentation**: See `README.md` for all available MCP tools
- **Production Deployment**: See `docker/README.md` for containerized deployment
- **Advanced Setup**: See `STDIO_MCP_SETUP.md` for detailed MCP configuration
- **Examples**: Check `examples/` directory for usage patterns
- **Tests**: Run `pytest tests/` to verify your installation

---

**🎉 Done!** You now have hierarchical multi-agent orchestration in Claude Code.
