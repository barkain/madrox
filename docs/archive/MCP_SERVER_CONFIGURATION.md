# MCP Server Configuration for Child Instances

## Overview

When spawning child Claude instances, you can specify which MCP servers they should have access to. This allows fine-grained control over what tools and capabilities each child instance can use.

## Important Limitation

⚠️ **Configuration Merging**: Child instances **inherit the user's global MCP configuration** and **add** any servers specified via `mcp_servers` parameter. Complete MCP isolation is not currently possible due to Claude CLI's configuration merge behavior.

- `enable_madrox=False` → Instance will NOT have Madrox MCP, but WILL have user's global MCP servers
- `enable_madrox=True` → Instance will have Madrox MCP + user's global MCP servers
- `mcp_servers={...}` → Additional servers are added to global + Madrox (if enabled)

For true isolation, use the lightweight environment without any global MCP configuration or use Codex instances instead.

## How It Works

1. **Parent specifies MCP servers**: When spawning a child, the parent includes an `mcp_servers` parameter
2. **Dynamic configuration**: Before starting the Claude CLI in the tmux session, Madrox runs `claude mcp add` commands
3. **Automatic Madrox inclusion**: If `enable_madrox=True`, the Madrox server is automatically added (unless explicitly configured)

## Configuration Format

The `mcp_servers` parameter is a dictionary mapping server names to their configurations:

```python
mcp_servers = {
    "server_name": {
        "transport": "http",  # or "stdio" (optional - auto-detected if "command" is present)
        "url": "http://localhost:PORT/mcp"  # for http transport
        # OR
        "command": "npx",  # for stdio transport
        "args": ["-y", "@modelcontextprotocol/server-filesystem"]
    }
}
```

**Note**: The `transport` field is optional. If `command` is present, transport defaults to `"stdio"`. Otherwise, it defaults to `"http"`.

## Quick Start: Using Prebuilt Configs

Madrox includes prebuilt MCP server configurations in `resources/mcp_configs/`. Use the helper to load them easily:

```python
from orchestrator.mcp_loader import get_mcp_servers

# Quick way: Load multiple prebuilt configs
mcp_servers = get_mcp_servers("playwright", "github", "memory")

instance_id = await manager.spawn_instance(
    name="agent",
    role="general",
    enable_madrox=True,
    mcp_servers=mcp_servers
)
```

Available prebuilt configs: `playwright`, `puppeteer`, `github`, `filesystem`, `sqlite`, `postgres`, `brave-search`, `google-drive`, `slack`, `memory`

See `resources/mcp_configs/README.md` for full documentation.

## Example Usage

### Basic: Spawn with Madrox Only

```python
spawn_claude(
    name="worker",
    role="general",
    enable_madrox=True  # Automatically adds Madrox MCP server
)
```

This generates:
```bash
claude mcp add madrox http://localhost:8001/mcp --transport http --scope local
```

### Advanced: Multiple MCP Servers

```python
spawn_claude(
    name="data-processor",
    role="data_analyst",
    enable_madrox=True,
    mcp_servers={
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
        },
        "database": {
            "transport": "http",
            "url": "http://localhost:5432/mcp"
        }
    }
)
```

This generates:
```bash
claude mcp add madrox http://localhost:8001/mcp --transport http --scope local
claude mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /data --transport stdio --scope local
claude mcp add database http://localhost:5432/mcp --transport http --scope local
```

### Browser Automation: Playwright (Headless)

```python
spawn_claude(
    name="web-scraper",
    role="data_analyst",
    enable_madrox=True,
    mcp_servers={
        "playwright": {
            "transport": "stdio",
            "command": "npx",
            "args": ["@playwright/mcp@latest"]
        }
    }
)
```

This generates:
```bash
claude mcp add madrox http://localhost:8001/mcp --transport http --scope local
claude mcp add playwright npx @playwright/mcp@latest --transport stdio --scope local
```

**Note**: Playwright MCP runs in headless mode by default. The child instance will have access to browser automation tools for web scraping, testing, and interaction.

### Custom Madrox URL (Multi-Server Setup)

```python
spawn_claude(
    name="remote-worker",
    role="backend_developer",
    enable_madrox=True,
    mcp_servers={
        "madrox": {
            "transport": "http",
            "url": "http://remote-server:8002/mcp"  # Override default
        }
    }
)
```

## Technical Details

### Implementation Flow

1. **Tmux session created**: A new tmux session is created for the instance
2. **MCP configuration**: `_configure_mcp_servers()` runs `claude mcp add` for each server
3. **Claude CLI started**: The Claude CLI process starts with access to configured MCP servers

### Automatic Madrox Addition

If `enable_madrox=True` and `"madrox"` is not explicitly in `mcp_servers`, Madrox is automatically added:

```python
if enable_madrox and "madrox" not in mcp_servers:
    mcp_servers["madrox"] = {
        "transport": "http",
        "url": f"http://localhost:{server_port}/mcp"
    }
```

### Scope

All MCP servers are added with `--scope local`, meaning they only affect the current tmux session and don't pollute the user's global Claude configuration.

## Bidirectional Messaging

When `enable_madrox=True`, child instances automatically get access to:

- `reply_to_caller`: Reply to the coordinator/parent that sent you a message
- `spawn_claude`: Spawn sub-children (if needed for hierarchical networks)
- `send_to_instance`: Send messages to other instances
- `get_children`: List your child instances
- `broadcast_to_children`: Send messages to all children

## Benefits

1. **Granular control**: Parents decide exactly what tools children can access
2. **Security**: Children only get capabilities they need
3. **Flexibility**: Different MCP servers for different instance types
4. **No global pollution**: `--scope local` keeps MCP config session-specific
5. **Automatic Madrox**: Bidirectional messaging works by default

## Related Documentation

- [Bidirectional Messaging Design](BIDIRECTIONAL_MESSAGING_DESIGN.md)
- [Testing Results](BIDIRECTIONAL_TESTING_RESULTS.md)
