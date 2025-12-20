# MCP Server Configurations

This directory contains reusable MCP (Model Context Protocol) server configurations that can be used when spawning Claude instances.

## Available MCP Servers

### Browser Automation
- **playwright.json** - Playwright MCP server for browser automation and web scraping
- **puppeteer.json** - Puppeteer MCP server for browser automation

### File & Data Access
- **filesystem.json** - Filesystem operations (requires allowed directory path)
- **sqlite.json** - SQLite database operations
- **postgres.json** - PostgreSQL database operations

### External Services
- **github.json** - GitHub repository operations (requires GitHub token)
- **google-drive.json** - Google Drive file operations (requires OAuth)
- **slack.json** - Slack workspace operations (requires Slack bot token)
- **brave-search.json** - Web search via Brave Search API (requires API key)

### AI Capabilities
- **memory.json** - Persistent memory/knowledge graph storage

## Usage

### Option 1: Using Configuration Files

Load a configuration file and pass it when spawning an instance:

```python
import json
from pathlib import Path

# Load MCP config
config_path = Path(__file__).parent / "resources/mcp_configs/playwright.json"
with open(config_path) as f:
    mcp_def = json.load(f)

# Spawn instance with MCP server
instance_id = await manager.spawn_instance(
    name="browser-agent",
    role="general",
    mcp_servers={
        mcp_def["name"]: mcp_def["config"]
    }
)
```

### Option 2: Direct Configuration

Pass MCP server configuration directly:

```python
instance_id = await manager.spawn_instance(
    name="browser-agent",
    role="general",
    mcp_servers={
        "playwright": {
            "command": "npx",
            "args": ["@playwright/mcp@latest"]
        }
    }
)
```

### Option 3: Multiple MCP Servers

Combine multiple MCP servers:

```python
instance_id = await manager.spawn_instance(
    name="full-stack-agent",
    role="general",
    mcp_servers={
        "playwright": {
            "command": "npx",
            "args": ["@playwright/mcp@latest"]
        },
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"]
        },
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"]
        }
    }
)
```

## Configuration Format

Each MCP configuration file has the following structure:

```json
{
  "name": "server-name",
  "description": "Description of the MCP server",
  "config": {
    "command": "npx",
    "args": ["package-name", "arg1", "arg2"]
  },
  "env": {
    "ENV_VAR": "value"
  },
  "notes": "Additional notes about usage"
}
```

## Transport Types

Madrox supports two transport types:

1. **stdio** (default when `command` is present) - Process-based communication
   ```python
   {
       "command": "npx",
       "args": ["@playwright/mcp@latest"]
   }
   ```

2. **http** - HTTP-based communication
   ```python
   {
       "transport": "http",
       "url": "http://localhost:8001/mcp"
   }
   ```

## Environment Variables

Some MCP servers require environment variables. You can set them when spawning:

```python
instance_id = await manager.spawn_instance(
    name="github-agent",
    role="general",
    mcp_servers={
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"]
        }
    },
    environment_vars={
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token_here"
    }
)
```

## Creating Custom MCP Configs

To add a new MCP server configuration:

1. Create a JSON file in this directory
2. Follow the configuration format above
3. Include clear notes about any required environment variables or setup
4. Document the MCP server's capabilities

## Notes

- The `transport` field is optional - if `command` is present, it defaults to `stdio`
- The Madrox MCP server is automatically added to all instances unless explicitly configured
- MCP servers are loaded when the Claude instance initializes (may take 30-60 seconds)
- Each instance gets an isolated workspace directory
