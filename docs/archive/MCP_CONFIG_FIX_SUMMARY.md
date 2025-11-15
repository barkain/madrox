# MCP Configuration Fix Summary

## Problem Identified

The Madrox MCP server was generating incorrect configuration files for stdio-based MCP servers. When spawning child instances with MCP servers like Playwright, the generated `.claude_mcp_config.json` included a `"type": "stdio"` field, but Claude Code doesn't recognize this format.

### Incorrect Format (Before)
```json
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

### Correct Format (After)
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

**Key Insight**: Claude Code infers the transport type from the presence of the `"command"` field. The `"type"` field should only be used for HTTP transport.

## Changes Made

### 1. Fixed `_configure_mcp_servers` in `tmux_instance_manager.py`

**File**: `/path/to/user/dev/madrox/src/orchestrator/tmux_instance_manager.py`

#### Change 1: Auto-detect transport type (lines 85-89)
```python
# Before
transport = server_config.get("transport", "http")

# After
has_command = "command" in server_config
transport = server_config.get("transport", "stdio" if has_command else "http")
```

#### Change 2: Remove "type" field for stdio servers (lines 105-110)
```python
# Before
mcp_config["mcpServers"][server_name] = {
    "type": "stdio",
    "command": command,
    "args": args if isinstance(args, list) else [args]
}

# After
# Claude Code expects stdio servers WITHOUT a "type" field
# It infers stdio from the presence of "command"
mcp_config["mcpServers"][server_name] = {
    "command": command,
    "args": args if isinstance(args, list) else [args]
}
```

### 2. Created Reusable MCP Configurations

**Directory**: `/path/to/user/dev/madrox/resources/mcp_configs/`

Created JSON configuration files for common MCP servers:

- **Browser Automation**: `playwright.json`, `puppeteer.json`
- **File & Data**: `filesystem.json`, `sqlite.json`, `postgres.json`
- **External Services**: `github.json`, `google-drive.json`, `slack.json`, `brave-search.json`
- **AI Capabilities**: `memory.json`

Each config file has this structure:
```json
{
  "name": "server-name",
  "description": "Description of the MCP server",
  "config": {
    "command": "npx",
    "args": ["package-name", "arg1"]
  },
  "env": {
    "ENV_VAR": "value"
  },
  "notes": "Usage notes"
}
```

### 3. Created MCP Config Loader Utility

**File**: `/path/to/user/dev/madrox/src/orchestrator/mcp_loader.py`

New utility for loading and managing MCP configurations:

```python
from orchestrator.mcp_loader import get_mcp_servers

# Load multiple prebuilt configs
mcp_servers = get_mcp_servers("playwright", "github", "memory")

# Spawn instance with MCP servers
instance_id = await manager.spawn_instance(
    name="agent",
    mcp_servers=mcp_servers
)
```

Features:
- `list_available_configs()` - List all available MCP configs
- `load_config(name)` - Load a specific config
- `get_mcp_servers_dict(*names, **custom)` - Build mcp_servers dict
- `load_with_overrides(name, args_overrides, env_overrides)` - Customize configs

### 4. Added Tests

**Files**:
- `tests/test_mcp_stdio_config.py` - Tests for stdio config format
- `tests/test_mcp_loader.py` - Tests for MCP loader utility

All tests pass ✅

### 5. Updated Documentation

**Files**:
- `docs/MCP_SERVER_CONFIGURATION.md` - Added Quick Start section
- `resources/mcp_configs/README.md` - Complete MCP configs documentation
- `examples/spawn_with_mcp_configs.py` - Usage examples

## Usage Examples

### Basic: Load Playwright
```python
from orchestrator.mcp_loader import get_mcp_servers

mcp_servers = get_mcp_servers("playwright")

instance_id = await manager.spawn_instance(
    name="browser-agent",
    role="general",
    enable_madrox=True,
    mcp_servers=mcp_servers
)
```

### Advanced: Multiple MCP Servers
```python
mcp_servers = get_mcp_servers("playwright", "github", "memory")

instance_id = await manager.spawn_instance(
    name="full-stack-agent",
    mcp_servers=mcp_servers
)
```

### Custom: Override Arguments
```python
from orchestrator.mcp_loader import MCPConfigLoader

loader = MCPConfigLoader()

# Customize filesystem path
filesystem_config = loader.load_with_overrides(
    "filesystem",
    args_overrides=["-y", "@modelcontextprotocol/server-filesystem", "/custom/path"]
)

mcp_servers = {filesystem_config["name"]: filesystem_config["config"]}

instance_id = await manager.spawn_instance(
    name="file-agent",
    mcp_servers=mcp_servers
)
```

### Mix: Prebuilt + Custom
```python
mcp_servers = get_mcp_servers(
    "playwright",
    "memory",
    custom_api={"command": "python", "args": ["my_server.py"]}
)
```

## Testing the Fix

To verify the fix works:

1. **Run the tests**:
   ```bash
   pytest tests/test_mcp_stdio_config.py -v
   pytest tests/test_mcp_loader.py -v
   ```

2. **Spawn an instance with Playwright**:
   ```python
   from orchestrator.mcp_loader import get_mcp_servers

   mcp_servers = get_mcp_servers("playwright")

   instance_id = await manager.spawn_instance(
       name="test-agent",
       mcp_servers=mcp_servers
   )

   # Check that Playwright MCP is available
   response = await manager.send_to_instance(
       instance_id=instance_id,
       message="What MCP servers do you have access to?",
       wait_for_response=True
   )
   ```

3. **Inspect the generated config** (in instance workspace):
   ```bash
   cat /tmp/claude_orchestrator/{instance_id}/.claude_mcp_config.json
   ```

   Should show:
   ```json
   {
     "mcpServers": {
       "playwright": {
         "command": "npx",
         "args": ["@playwright/mcp@latest"]
       }
     }
   }
   ```

## Benefits

1. ✅ **Fixed stdio MCP format** - Matches Claude Code's expected format
2. ✅ **Auto-detection** - Transport type automatically detected from config
3. ✅ **Reusable configs** - 10+ prebuilt MCP server configurations
4. ✅ **Easy to use** - Simple `get_mcp_servers()` helper function
5. ✅ **Customizable** - Override arguments and environment variables
6. ✅ **Well-tested** - Comprehensive test coverage
7. ✅ **Documented** - Complete documentation and examples

## Files Modified

- `src/orchestrator/tmux_instance_manager.py` (lines 83-110)
- `docs/MCP_SERVER_CONFIGURATION.md`

## Files Created

- `src/orchestrator/mcp_loader.py`
- `resources/mcp_configs/*.json` (10 config files)
- `resources/mcp_configs/README.md`
- `examples/spawn_with_mcp_configs.py`
- `tests/test_mcp_stdio_config.py`
- `tests/test_mcp_loader.py`

## Next Steps

1. Update any existing code that spawns instances with MCP servers
2. Consider adding more prebuilt MCP configs as needed
3. Document any custom MCP servers your team uses
