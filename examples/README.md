# Madrox Examples

This directory contains examples demonstrating how to use the Madrox multi-agent orchestration system.

## Available Examples

### 1. Basic Usage Examples

#### Simple HTTP API (`demo_simple.py`)
Basic example using direct HTTP requests to spawn instances and send messages.

**Best for:** Learning the HTTP API, understanding basic orchestration

**Run it:**
```bash
# Start the server first
uv run python run_orchestrator.py

# In another terminal
uv run python examples/demo_simple.py
```

#### MCP Client with Parent-Child Spawning (`demo_weather_chat.py`)
Demonstrates using the MCP client to spawn a Claude parent that creates a Codex child instance.

**Best for:** Understanding MCP protocol, hierarchical orchestration

**Run it:**
```bash
uv run python examples/demo_weather_chat.py
```

### 2. MCP Server Integration

#### MCP Configuration Examples (`spawn_with_mcp_configs.py`)
Shows various ways to spawn instances with custom MCP server configurations.

**Best for:** Learning how to add MCP servers (Playwright, custom servers, etc.)

**Run it:**
```bash
uv run python examples/spawn_with_mcp_configs.py
```

#### JSON MCP Configuration (`spawn_with_json_mcp_servers.py`)
Alternative approach using JSON strings for MCP server configuration.

**Best for:** Programmatic MCP server configuration

**Run it:**
```bash
uv run python examples/spawn_with_json_mcp_servers.py
```

### 3. Playwright Integration

#### Playwright Spawn Test (`playwright_spawn.py`)
Quick test to verify Playwright MCP integration works correctly.

**Best for:** Testing Playwright setup, browser automation verification

**Run it:**
```bash
uv run python examples/playwright_spawn.py
```

#### Web Scraping Example (`playwright_web_scraper.py`)
Spawns a Claude instance with Playwright for web scraping tasks.

**Best for:** Browser automation, web scraping use cases

**Run it:**
```bash
uv run python examples/playwright_web_scraper.py
```

### 4. Supervision System

#### Comprehensive Supervision Patterns (`supervision_integration_example.py`)
Complete examples covering all supervision integration patterns:

- **Basic Supervision**: Autonomous monitoring of a Madrox network
- **Supervised Network**: Creating a complete supervised development team
- **Embedded Supervision**: Supervision without dedicated Claude instance
- **Manual Control**: Full lifecycle control over supervision
- **Custom Configurations**: Different configurations for various scenarios

**Best for:** Understanding the supervision system, implementing automated monitoring

**Run it:**
```bash
uv run python examples/supervision_integration_example.py
```

## Quick Start

### Prerequisites

```bash
# Install dependencies
uv sync --all-groups

# Start the Madrox server
uv run python run_orchestrator.py
```

### Running Examples

Each example can be run independently:

```bash
# Basic HTTP example
uv run python examples/demo_simple.py

# MCP client example
uv run python examples/demo_weather_chat.py

# Supervision patterns
uv run python examples/supervision_integration_example.py
```

## Example Workflow

1. **Start with `demo_simple.py`** to understand basic concepts
2. **Try `demo_weather_chat.py`** to see MCP protocol in action
3. **Explore `spawn_with_mcp_configs.py`** to learn about MCP server integration
4. **Review `supervision_integration_example.py`** for advanced monitoring

## Configuration

### Environment Variables

```bash
# Server configuration
export ORCHESTRATOR_PORT=8001
export MAX_INSTANCES=10

# Optional: API key if not using OAuth
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

### Custom MCP Servers

To add custom MCP servers to spawned instances, see the MCP configuration examples.

## Troubleshooting

### Server Not Running

```bash
# Ensure server is started
uv run python run_orchestrator.py

# Check server health
curl http://localhost:8001/health
```

### Import Errors

```bash
# Ensure dependencies are installed
uv sync --all-groups

# Verify installation
uv pip list | grep claude
```

### Connection Errors

- Verify server is running on correct port (default: 8001)
- Check firewall settings
- Ensure no other service is using port 8001

## Next Steps

1. **Read the Setup Guide**: See [docs/SETUP.md](../docs/SETUP.md) for installation
2. **Check API Reference**: See [docs/API_REFERENCE.md](../docs/API_REFERENCE.md) for complete API
3. **Explore Tests**: Run `pytest tests/` to see more usage patterns
4. **Build Your Integration**: Use these examples as templates

## Additional Resources

- **Main Documentation**: [README.md](../README.md)
- **Architecture Guide**: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
- **API Reference**: [docs/API_REFERENCE.md](../docs/API_REFERENCE.md)
- **Troubleshooting**: [docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)
