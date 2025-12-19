# Madrox Setup Guide

Comprehensive installation and setup guide for the Madrox multi-agent orchestration system.

## Overview

Madrox is a Model Context Protocol (MCP) server that enables hierarchical orchestration of Claude and Codex instances. This guide covers installation methods, configuration, and verification steps to get Madrox running on your system.

**What you'll learn:**
- System prerequisites and requirements
- Installation methods (Quick Start, Manual)
- MCP client configuration (Claude Desktop, Claude Code, Codex CLI)
- Initial configuration and verification
- Troubleshooting common issues

---

## Prerequisites

### System Requirements

**Required:**
- Python 3.11 or higher
- Operating System: macOS, Linux, or Windows with WSL2
- 2GB+ available RAM (4GB+ recommended)
- Internet connection for API calls

### API Keys

**Anthropic API Key:**
- Optional if you have Claude Desktop/CLI subscription (OAuth authentication works)
- Required if you don't have a subscription - get one at [console.anthropic.com](https://console.anthropic.com)

**Optional:**
- **OpenAI API Key** - For Codex instances (multi-model support)

### Dependencies

**Python packages (installed automatically):**
- FastAPI and uvicorn (HTTP server)
- Anthropic SDK (Claude API)
- `tmux` (session management for instances)

**System tools:**
- `uv` package manager (recommended) or `pip`
- `curl` for health checks
- `git` for cloning the repository

---

## Installation Methods

Choose the installation method that best fits your needs:

| Method | Best For | Setup Time | Auth Requirements |
|--------|----------|------------|-------------------|
| **Quick Start** | Development, testing | 5 minutes | OAuth or API key |
| **Manual** | Custom setups, debugging | 15 minutes | OAuth or API key |

---

## Quick Start

Fastest way to get Madrox running for development and testing.

### 1. Clone Repository

```bash
git clone https://github.com/nadavbarkai/madrox.git
cd madrox-containerization
```

### 2. Install Dependencies

Using `uv` (recommended):

```bash
cd src/orchestrator
uv sync --all-groups
```

Using `pip`:

```bash
cd src/orchestrator
pip install -r requirements.txt
```

### 3. Configure Environment

Set environment variables:

```bash
export ORCHESTRATOR_PORT=8001
export WORKSPACE_DIR="/tmp/claude_orchestrator"

# Optional: Set API key if not using Claude subscription
export ANTHROPIC_API_KEY="sk-ant-your-api-key-here"
```

### 4. Start Server

Using the launcher script:

```bash
python run_orchestrator.py
```

Or directly:

```bash
uv run python -c "
from src.orchestrator.server import main
import asyncio
asyncio.run(main())
"
```

The server will start on `http://localhost:8001`.

### 5. Verify Health

```bash
curl http://localhost:8001/health

# Expected output:
# {"status":"healthy","instances_active":0,"instances_total":0}
```

**Next:** [Connect MCP Client](#mcp-client-configuration)

---

## Manual Installation

Step-by-step manual setup for custom configurations.

### 1. System Dependencies

Install required system tools:

**macOS:**
```bash
brew install python@3.11 tmux
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.11 python3-pip tmux
```

**Arch Linux:**
```bash
sudo pacman -S python tmux
```

### 2. Install UV Package Manager

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or using pip:

```bash
pip install uv
```

### 3. Clone Repository

```bash
git clone https://github.com/nadavbarkai/madrox.git
cd madrox-containerization/src/orchestrator
```

### 4. Create Virtual Environment

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 5. Install Dependencies

```bash
uv sync --all-groups
```

This installs:
- Production dependencies
- Development tools
- Testing frameworks
- Example project dependencies

### 6. Configure Settings

Create configuration file:

```bash
mkdir -p ~/.madrox
cat > ~/.madrox/config.yaml <<EOF
server:
  host: localhost
  port: 8001

orchestrator:
  max_instances: 10
  workspace_dir: /tmp/claude_orchestrator
  log_dir: /tmp/madrox_logs

resources:
  max_tokens_per_instance: 100000
  max_total_cost: 100.0
  instance_timeout_minutes: 60
EOF
```

Set environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
export ORCHESTRATOR_PORT=8001
export WORKSPACE_DIR="/tmp/claude_orchestrator"
export LOG_DIR="/tmp/madrox_logs"
export LOG_LEVEL=INFO
```

### 7. Initialize Workspace

Create required directories:

```bash
mkdir -p /tmp/claude_orchestrator
mkdir -p /tmp/madrox_logs/instances
mkdir -p /tmp/madrox_logs/audit
```

### 8. Start Server

```bash
python run_orchestrator.py
```

Or with custom settings:

```bash
python run_orchestrator.py \
  --host 0.0.0.0 \
  --port 8001 \
  --log-level INFO
```

### 9. Verify Installation

```bash
# Test server
curl http://localhost:8001/health

# List tools
curl http://localhost:8001/tools

# Check logs
tail -f /tmp/madrox_logs/server.log
```

**Next:** [Connect MCP Client](#mcp-client-configuration)

---

## MCP Client Configuration

Connect Madrox to your preferred MCP client.

### Claude Desktop (macOS/Windows)

**1. Locate configuration file:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**2. Add Madrox server:**

**Option A - HTTP Transport (Server already running):**

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

**Option B - Stdio Transport (Auto-start server):**

```json
{
  "mcpServers": {
    "madrox": {
      "command": "/absolute/path/to/uv",
      "args": ["run", "python", "run_orchestrator.py"],
      "cwd": "/path/to/madrox",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-your-key-here"
      }
    }
  }
}
```

**Note:** Find `uv` path with: `command -v uv` or `which uv`

**3. Restart Claude Desktop**

The Madrox tools will appear in your conversations.

---

### Claude Code CLI

**1. Register MCP server:**

```bash
claude mcp add madrox http://localhost:8001/mcp --transport http
```

**Model mapping:**

| CLI Choice | Anthropic Model ID |
|------------|-------------------|
| `sonnet` | `claude-sonnet-4-20250514` |
| `opus` | `claude-opus-4-1-20250805` |
| `haiku` | `claude-3-5-haiku-20241022` |

**2. Verify registration:**

```bash
claude mcp list
```

You should see `madrox` in the list.

**3. Start using Madrox:**

```bash
# Start Claude session
claude

# Test Madrox tools
"Spawn a Claude instance with role 'frontend_developer' named 'react-expert'"
```

---

### Claude Code (VS Code Extension)

**1. Open VS Code Command Palette** (Cmd/Ctrl + Shift + P)

**2. Run:** `Claude: Edit Connection Settings`

**3. Add Madrox server:**

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

**4. Reload connections:**

Run: `Claude: Reload Connections`

---

### OpenAI Codex CLI

**One-command setup:**

```bash
# From Madrox directory
codex mcp add madrox $(pwd)/madrox-mcp

# Or with full path
codex mcp add madrox /absolute/path/to/madrox/madrox-mcp
```

**Verify installation:**

```bash
codex mcp list
```

**Test in Codex:**

```bash
codex

# Example commands:
"Spawn a Claude instance named 'helper' with role 'general'"
"Send 'analyze this code' to instance helper"
"Get status of all instances"
```

**See [CODEX_QUICK_SETUP.md](../CODEX_QUICK_SETUP.md) for detailed Codex configuration.**

---

## Configuration

### Environment Variables

Complete reference for all configuration options:

#### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key (optional with subscription) | `sk-ant-api03-...` |

#### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ORCHESTRATOR_HOST` | `localhost` | Server bind address |
| `ORCHESTRATOR_PORT` | `8001` | Server port |
| `LOG_LEVEL` | `INFO` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |

#### Resource Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_INSTANCES` | `10` | Maximum concurrent instances |
| `MAX_TOKENS_PER_INSTANCE` | `100000` | Token limit per instance |
| `MAX_TOTAL_COST` | `100.0` | Total cost limit (USD) |
| `INSTANCE_TIMEOUT_MINUTES` | `60` | Auto-terminate idle instances |

#### Storage & Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKSPACE_DIR` | `/tmp/claude_orchestrator` | Instance workspaces |
| `LOG_DIR` | `/tmp/madrox_logs` | Log storage directory |
| `DATABASE_URL` | `sqlite:///madrox.db` | Database connection string |

#### Optional - Monitoring & Multi-Model

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key for MonitoringService LLM summaries (enables intelligent instance activity summaries) |
| `OPENAI_API_KEY` | OpenAI API key for Codex instances |

### OpenRouter API Configuration (Optional)

Madrox can generate intelligent, natural language summaries of instance activities using the OpenRouter API and Claude. This enables monitoring teams to understand what instances are doing without reading raw logs.

#### Setup Steps

**1. Create OpenRouter Account**

Visit https://openrouter.ai and create a free account. No credit card required for initial API access.

**2. Get API Key**

- Log in to OpenRouter dashboard
- Navigate to API Keys section
- Create a new key or copy your default key
- Format: `sk-or-v1-xxxxxxxxxxxxx`

**3. Set Environment Variable**

```bash
# Local development
export OPENROUTER_API_KEY="sk-or-v1-your-api-key-here"

# Or add to .bashrc/.zshrc for persistence
echo 'export OPENROUTER_API_KEY="sk-or-v1-your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

**4. Verify Configuration**

```bash
# Check environment variable is set
echo $OPENROUTER_API_KEY

# Start orchestrator - LLM summaries will be automatically enabled
python run_orchestrator.py

# Check logs for confirmation
grep -i "openrouter\|llm" /tmp/madrox_logs/server.log
```

#### How It Works

Without OpenRouter API key:
- MonitoringService generates basic text summaries from logs
- No LLM processing, summaries are template-based

With OpenRouter API key:
- Instances' logs and outputs are sent to Claude via OpenRouter
- Claude analyzes activity and generates natural language summaries
- Summaries include key accomplishments, progress estimates, next steps
- Results are cached to minimize API calls
- Team-wide aggregation provides leadership visibility

#### Benefits

✅ **Automatic Monitoring** - No manual intervention required
✅ **Intelligent Insights** - Claude understands context and extracts meaning
✅ **Progress Tracking** - Know what instances have accomplished and what's next
✅ **Cost Optimization** - Caching and smart polling minimize API usage
✅ **Zero Configuration** - Just set the API key, everything else is automatic

#### Troubleshooting

**"OPENROUTER_API_KEY not set" error**

```bash
# Verify key is set
echo $OPENROUTER_API_KEY

# If empty, set it again
export OPENROUTER_API_KEY="sk-or-v1-your-key"

# Restart orchestrator
python run_orchestrator.py
```

**"OpenRouter API returned error" in logs**

- Check API key format (should start with `sk-or-v1-`)
- Verify API key is valid in OpenRouter dashboard
- Check OpenRouter service status at https://status.openrouter.ai
- Review rate limits and quota in OpenRouter dashboard

**Summaries still showing as "generic"**

- Ensure OPENROUTER_API_KEY is set before starting orchestrator
- Check logs: `tail -f /tmp/madrox_logs/server.log | grep -i "llm\|openrouter"`
- Expected log entry: `"LLMSummarizer initialized successfully"`

#### Optional Parameters

Once OPENROUTER_API_KEY is set, you can tune monitoring behavior:

```bash
# Model selection (default: anthropic/claude-haiku-4.5)
# See "Model Selection Guide" below for recommendations
export OPENROUTER_MODEL="google/gemini-2.0-flash-exp:free"  # Recommended: Free & fast

# Summary polling interval (seconds, default: 12)
export MONITORING_POLL_INTERVAL=12

# Cache age threshold (seconds, default: 60)
export MONITORING_CACHE_AGE=60
```

#### Model Selection Guide (2025)

Choose the best model for your monitoring needs:

**FREE MODELS (Recommended for high-volume monitoring):**
```bash
# Best free option - faster than Gemini 1.5, high quality
export OPENROUTER_MODEL="google/gemini-2.0-flash-exp:free"

# MIT licensed, good reasoning capabilities
export OPENROUTER_MODEL="deepseek/deepseek-r1:free"

# High concurrency support, cost efficient
export OPENROUTER_MODEL="minimax/minimax-m2:free"
```

**CHEAP MODELS (Ultra-low cost, pay-per-use):**
```bash
# Ultra-low latency, minimal cost per request
export OPENROUTER_MODEL="google/gemini-2.5-flash-lite"

# Fast with advanced reasoning
export OPENROUTER_MODEL="google/gemini-2.5-flash"
```

**QUALITY MODELS (Balanced cost/quality):**
```bash
# Default - 200K context, high quality (paid)
export OPENROUTER_MODEL="anthropic/claude-haiku-4.5"

# Advanced reasoning, higher cost (paid)
export OPENROUTER_MODEL="anthropic/claude-sonnet-4.5"
```

**Recommendation:** Start with `google/gemini-2.0-flash-exp:free` - it's completely free and provides excellent quality for monitoring summaries.

### MonitoringService Configuration

MonitoringService is automatically integrated with TmuxInstanceManager and starts when the orchestrator launches. Configure it with these environment variables:

**Basic Setup (Optional Monitoring)**

```bash
# MonitoringService runs by default without configuration
# Generates generic summaries without LLM enhancement
python run_orchestrator.py
```

**Enhanced Setup (LLM-Powered Summaries)**

```bash
# Get OpenRouter API key from https://openrouter.ai
export OPENROUTER_API_KEY="sk-or-v1-xxxxx"

# Start orchestrator - MonitoringService will use LLM for summaries
python run_orchestrator.py
```

**Advanced Configuration**

```bash
# Set monitoring poll interval (seconds)
export MONITORING_POLL_INTERVAL=12

# Set storage path for summaries
export MONITORING_STORAGE_PATH="/tmp/madrox_logs/summaries"

# Summary cache age threshold (seconds)
export MONITORING_CACHE_AGE=60
```

**Docker Configuration**

Add to `.env` file:

```bash
# Required for LLM summaries
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# Optional monitoring settings
MONITORING_POLL_INTERVAL=12
MONITORING_STORAGE_PATH=/tmp/madrox_logs/summaries
```

**Verify Monitoring is Active**

```bash
# Check if MonitoringService initialized
tail -f /tmp/madrox_logs/server.log | grep -i "monitoring"

# Expected output:
# "Starting MonitoringService..."
# "MonitoringService started (poll interval: 12s)"
```

**Access Monitoring Tools**

Once the orchestrator is running with MonitoringService enabled:

```python
# Get summary for single instance
summary = await get_agent_summary(instance_id="abc123")

# Get summaries for all instances
all_summaries = await get_all_agent_summaries()
```

### Configuration Methods

**Method 1 - Environment Variables:**

```bash
export ORCHESTRATOR_PORT=8001
export MAX_INSTANCES=20
export LOG_LEVEL=DEBUG
export OPENROUTER_API_KEY="sk-or-v1-xxxxx"  # For MonitoringService
```

**Method 2 - .env File (Docker):**

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-key
ORCHESTRATOR_PORT=8001
MAX_INSTANCES=10
LOG_LEVEL=INFO
```

**Method 3 - Configuration File:**

```yaml
# ~/.madrox/config.yaml
server:
  host: localhost
  port: 8001

orchestrator:
  max_instances: 10
  workspace_dir: /tmp/claude_orchestrator

resources:
  max_tokens_per_instance: 100000
  max_total_cost: 100.0
```

---

## Verification

Verify successful installation with these checks:

### 1. Server Health

```bash
curl http://localhost:8001/health

# Expected output:
{
  "status": "healthy",
  "instances_active": 0,
  "instances_total": 0,
  "uptime_seconds": 120
}
```

### 2. List Available Tools

```bash
curl http://localhost:8001/tools | jq

# Should return array of MCP tools:
# - spawn_claude
# - spawn_codex_instance
# - send_to_instance
# - get_instance_output
# - coordinate_instances
# - terminate_instance
# etc.
```

### 3. Test Instance Spawning

Using HTTP API:

```bash
curl -X POST http://localhost:8001/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "spawn_claude",
    "arguments": {
      "name": "test-instance",
      "role": "general"
    }
  }'

# Should return instance_id
```

### 4. Check Logs

```bash
# Server logs
tail -f /tmp/madrox_logs/server.log

# Audit trail
tail -f /tmp/madrox_logs/audit/audit-$(date +%Y-%m-%d).jsonl

# Docker logs
docker compose logs -f madrox
```

### 5. Run Test Suite

```bash
# Navigate to tests directory
cd tests

# Run unit tests
uv run pytest test_orchestrator.py -v

# Run integration demo
uv run python integration_demo.py
```

Expected output:
- **Unit tests:** 25/26 passing (86% coverage)
- **Integration demo:** Successfully spawns 3 instances, coordinates tasks

### 6. Verify MCP Connection

**Claude Desktop:**
- Open new conversation
- Type: `Can you list your available MCP tools?`
- Should see Madrox tools listed

**Claude Code CLI:**
```bash
claude --verbose

# In conversation:
"What MCP servers are available?"
```

Should show `madrox` in the list.

---

## Testing

### Run Test Suite

```bash
# All tests with coverage
uv run pytest tests/test_orchestrator.py -v --cov=src/orchestrator

# Specific test categories
uv run pytest tests/test_orchestrator.py::test_spawn_instance -v
uv run pytest tests/test_orchestrator.py::test_instance_limits -v
```

### Run Integration Demo

```bash
uv run python tests/integration_demo.py
```

This demonstrates:
1. Spawning 3 specialized instances (architect, frontend, backend)
2. Coordinating them to build a task management app
3. Retrieving and displaying outputs

### Run Stress Tests

```bash
# Comprehensive stress testing
uv run python tests/stress_test_suite.py
```

See [docs/STRESS_TESTING.md](STRESS_TESTING.md) for detailed testing scenarios.

---

## Next Steps

Now that Madrox is installed and running:

### Learn More

- **[README.md](../README.md)** - Feature overview and examples
- **[DESIGN.md](DESIGN.md)** - System architecture and design philosophy
- **[API_ENDPOINTS.md](API_ENDPOINTS.md)** - HTTP REST API reference
- **[MCP_SERVER_CONFIGURATION.md](MCP_SERVER_CONFIGURATION.md)** - Custom MCP servers for instances
- **[LOGGING.md](LOGGING.md)** - Comprehensive logging and audit system
- **[INTERRUPT_FEATURE.md](INTERRUPT_FEATURE.md)** - Task interruption capabilities

### Quick Examples

**Spawn a specialized instance:**

```python
instance_id = await manager.spawn_instance(
    name="React Developer",
    role="frontend_developer",
    system_prompt="You are a React expert specializing in TypeScript."
)
```

**Hierarchical orchestration:**

```python
# Spawn coordinator with Madrox access
coordinator = await manager.spawn_instance(
    name="Project Manager",
    role="general"
)

# Coordinator spawns its own children
await manager.send_to_instance(
    coordinator,
    "Spawn a frontend developer and backend developer as your children."
)

# Visualize network
tree = manager.get_instance_tree()
print(tree)
```

**Multi-model orchestration:**

```python
# Mix Claude and Codex instances
instances = await manager.spawn_multiple_instances([
    {"name": "claude-architect", "role": "architect"},
    {"name": "codex-coder", "instance_type": "codex"}
])
```

### Production Deployment

For production use:

1. **Use Docker deployment** for isolation and resource management
2. **Configure resource limits** to prevent runaway costs
3. **Enable audit logging** for compliance and debugging
4. **Set up monitoring** using health checks and metrics
5. **Configure backups** for database and logs
6. **Use reverse proxy** with HTTPS (Nginx/HAProxy)

See [docker/README.md](../docker/README.md) for production deployment guide.

---

## Troubleshooting

### Common Issues

#### Server Won't Start

**Symptom:** `run_orchestrator.py` fails immediately

**Solutions:**

1. **Check Python version:**
   ```bash
   python --version  # Should be 3.11+
   ```

2. **Verify dependencies:**
   ```bash
   uv sync --all-groups
   ```

3. **Check port availability:**
   ```bash
   lsof -i :8001  # Port should be free
   ```

4. **Verify API key format:**
   ```bash
   echo $ANTHROPIC_API_KEY  # Should start with sk-ant-
   ```

---

#### Instance Spawn Failures

**Symptom:** Spawning instances returns errors

**Solutions:**

1. **Check workspace permissions:**
   ```bash
   ls -ld /tmp/claude_orchestrator
   chmod 755 /tmp/claude_orchestrator
   ```

2. **Verify tmux installed:**
   ```bash
   which tmux
   ```

3. **Check API rate limits:**
   - Wait and retry
   - Check usage at console.anthropic.com

4. **Review logs:**
   ```bash
   tail -f /tmp/madrox_logs/server.log
   ```

---

#### MCP Connection Fails

**Symptom:** Claude Desktop/CLI can't connect to Madrox

**Solutions:**

1. **Verify server running:**
   ```bash
   curl http://localhost:8001/health
   ```

2. **Check MCP endpoint:**
   ```bash
   curl http://localhost:8001/mcp
   ```

3. **Verify configuration:**
   - URL should be `http://localhost:8001/mcp` (include `/mcp`)
   - Transport should be `http`

4. **Restart MCP client:**
   - Claude Desktop: Quit and relaunch
   - Claude CLI: Exit and restart session

---

#### Docker Issues

**Symptom:** Container won't start or is unhealthy

**Solutions:**

1. **Check container logs:**
   ```bash
   docker compose logs madrox
   ```

2. **Verify API key set:**
   ```bash
   docker compose exec madrox env | grep ANTHROPIC_API_KEY
   ```

3. **Test health inside container:**
   ```bash
   docker compose exec madrox curl -f http://localhost:8001/health
   ```

4. **Rebuild image:**
   ```bash
   docker compose down
   docker compose up -d --build
   ```

---

### Debug Mode

Enable verbose logging:

```bash
# Set debug level
export LOG_LEVEL=DEBUG

# Restart server
python run_orchestrator.py

# Or for Docker
echo "LOG_LEVEL=DEBUG" >> .env
docker compose restart
```

---

### Support Resources

- **Documentation:** [Main README](../README.md)
- **GitHub Issues:** Report bugs and feature requests
- **Health Endpoint:** `http://localhost:8001/health`
- **Tools Endpoint:** `http://localhost:8001/tools`

---

## Summary

You've successfully installed and configured Madrox! Here's what you accomplished:

✅ **Installed** Madrox using your preferred method (Quick Start, Docker, or Manual)
✅ **Configured** environment variables and resource limits
✅ **Connected** your MCP client (Claude Desktop, Claude Code, or Codex CLI)
✅ **Verified** installation with health checks and test suite
✅ **Ready** to orchestrate hierarchical multi-agent workflows

**Quick Reference:**

| Task | Command |
|------|---------|
| Start server | `python run_orchestrator.py` |
| Health check | `curl http://localhost:8001/health` |
| List tools | `curl http://localhost:8001/tools` |
| View logs | `tail -f /tmp/madrox_logs/server.log` |
| Run tests | `uv run pytest tests/ -v` |
| Docker start | `docker compose up -d` |
| Docker logs | `docker compose logs -f` |

**Next Steps:**
- Try the [integration demo](../tests/integration_demo.py)
- Explore [example workflows](../README.md#-see-it-in-action)
- Read the [architecture guide](DESIGN.md)
- Configure [custom MCP servers](MCP_SERVER_CONFIGURATION.md)

---

**Ready for production use with comprehensive testing, monitoring, and documentation!** 🚀
