# Codex MCP Configuration Solution

## Problem

Codex CLI doesn't support the `--mcp-config` flag that Claude Code uses. We needed a Codex-specific solution for configuring MCP servers in child instances.

## Solution

### Codex Uses `codex mcp add` Commands

Unlike Claude Code which uses JSON config files, **Codex stores MCP configuration in `~/.codex/config.toml`** and provides CLI commands to manage it:

```bash
codex mcp add <NAME> <COMMAND> [ARGS...] [--env KEY=VALUE]
```

### Implementation

Modified `_configure_mcp_servers()` in `tmux_instance_manager.py` to handle Codex and Claude differently:

**For Codex:**
- Runs `codex mcp add` commands in the tmux pane before starting the Codex CLI
- Supports stdio MCP servers with command + args
- Supports environment variables via `--env` flag
- Does NOT support HTTP MCP servers (Codex limitation)

**For Claude:**
- Creates `.claude_mcp_config.json` file
- Uses `--mcp-config` flag when starting Claude CLI
- Supports both HTTP and stdio MCP servers

## Code Changes

### Modified Files

1. **src/orchestrator/tmux_instance_manager.py** (lines 60-169)
   - Split `_configure_mcp_servers()` into Codex and Claude branches
   - Codex branch: sends `codex mcp add` commands to tmux pane
   - Claude branch: writes JSON config file (unchanged)

2. **src/orchestrator/mcp_adapter.py** (lines 584-587, 1294)
   - Added `mcp_servers` parameter to `spawn_codex_instance` tool

### New Files

- **tests/test_codex_mcp_config.py** - Tests for Codex MCP configuration

## Usage

### Spawn Codex with Playwright

```python
spawn_codex_instance(
    name="codex-browser",
    sandbox_mode="workspace-write",
    parent_instance_id="parent-id",
    mcp_servers={
        "playwright": {
            "command": "npx",
            "args": ["@playwright/mcp@latest"]
        }
    }
)
```

### Using MCP Loader

```python
from orchestrator.mcp_loader import get_mcp_servers

mcp_servers = get_mcp_servers("playwright", "memory")

spawn_codex_instance(
    name="codex-agent",
    mcp_servers=mcp_servers
)
```

### With Environment Variables

```python
spawn_codex_instance(
    name="codex-github",
    mcp_servers={
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": "your_token_here"
            }
        }
    }
)
```

## How It Works

1. **Spawn requested** - User calls `spawn_codex_instance` with `mcp_servers`
2. **Tmux session created** - Session created in isolated workspace
3. **MCP commands executed** - `codex mcp add` commands run in the pane:
   ```bash
   codex mcp add playwright npx @playwright/mcp@latest
   codex mcp add memory npx @modelcontextprotocol/server-memory
   ```
4. **Codex CLI started** - `codex --sandbox workspace-write` starts
5. **MCP servers available** - Codex loads configured MCP servers

## Limitations

### Codex Does NOT Support:
1. **HTTP MCP servers** - Only stdio transport is supported
2. **Per-instance MCP config** - MCP servers are added globally to `~/.codex/config.toml`
   - This means MCP servers persist across Codex sessions
   - If you need true isolation, you'd need separate Codex config files

### Workaround for HTTP Servers (like Madrox)

Currently, if you enable Madrox for a Codex instance, it will skip the HTTP Madrox server with a warning. To use Madrox with Codex, you'd need:
1. A stdio version of the Madrox MCP server, or
2. Manually configure Madrox in the global `~/.codex/config.toml`

## Testing

All tests pass ✅:

```bash
pytest tests/test_codex_mcp_config.py -v
```

Test coverage:
- ✅ Codex uses `codex mcp add` commands
- ✅ Environment variables are passed correctly
- ✅ HTTP servers are skipped with warning
- ✅ Claude instances still use JSON config files

## Configuration Format Comparison

### Claude (JSON Config File)

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    },
    "madrox": {
      "type": "http",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

### Codex (TOML Config File)

```toml
[mcp_servers.playwright]
command = "npx"
args = ["@playwright/mcp@latest"]

[mcp_servers.memory]
command = "npx"
args = ["@modelcontextprotocol/server-memory"]
```

## Next Steps

1. ✅ Restart Madrox server to apply changes
2. ✅ Test spawning Codex with Playwright MCP
3. ✅ Verify Codex instance has access to Playwright tools
4. Consider: Add cleanup to remove MCP servers when instance terminates (optional)

## Summary

- **Codex**: Uses `codex mcp add` commands + TOML config
- **Claude**: Uses JSON config file + `--mcp-config` flag
- **Both supported**: Can now spawn both Claude and Codex instances with custom MCP servers
- **Limitation**: Codex doesn't support HTTP MCP servers yet
