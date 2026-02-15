# MCP Servers Parameter - JSON String Format

## Problem Statement

The MCP (Model Context Protocol) has a limitation: **tool parameters must be scalar types** (string, number, boolean). Complex nested objects like dictionaries cannot be passed directly through the MCP protocol.

This created a challenge when trying to pass MCP server configurations to spawned instances:

```python
# ❌ This doesn't work - nested dict not supported by MCP protocol
mcp__madrox__spawn_claude(
    name="orchestrator",
    mcp_servers={  # ← This nested structure causes issues
        "armando": {
            "transport": "http",
            "url": "http://localhost:8002/mcp"
        }
    }
)
```

## Solution: JSON String Parameter

Madrox now accepts `mcp_servers` as a **JSON string** parameter, which is then parsed internally.

### Usage

```python
import json

# ✅ Pass mcp_servers as JSON string
mcp__madrox__spawn_claude(
    name="orchestrator",
    role="general",
    model="claude-sonnet-4-5",
    mcp_servers=json.dumps({
        "armando": {
            "transport": "http",
            "url": "http://localhost:8002/mcp"
        },
        "playwright": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@playwright/mcp-server"]
        }
    })
)
```

### How It Works

1. **Client side**: Convert Python dict to JSON string using `json.dumps()`
2. **MCP protocol**: Passes the string parameter (scalar type, no issues)
3. **Madrox server**: Receives the string and parses it back to a dict
4. **Instance configuration**: Uses the parsed dict to configure MCP servers

The parsing happens in `TmuxInstanceManager._configure_mcp_servers()`:

```python
# Handle case where mcp_servers might be a JSON string (from MCP protocol)
if isinstance(mcp_servers, str):
    try:
        import json
        mcp_servers = json.loads(mcp_servers)
        # Update instance dict with parsed value
        instance["mcp_servers"] = mcp_servers
    except json.JSONDecodeError:
        logger.error(f"Invalid mcp_servers JSON string: {mcp_servers}")
        mcp_servers = {}
```

## Configuration Format

### HTTP Transport

For HTTP-based MCP servers (like Armando):

```json
{
  "armando": {
    "transport": "http",
    "url": "http://localhost:8002/mcp"
  }
}
```

Optional bearer token:

```json
{
  "armando": {
    "transport": "http",
    "url": "http://localhost:8002/mcp",
    "bearer_token": "your_token_here"
  }
}
```

### STDIO Transport

For STDIO-based MCP servers (like Playwright):

```json
{
  "playwright": {
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@playwright/mcp-server"]
  }
}
```

Optional environment variables:

```json
{
  "playwright": {
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@playwright/mcp-server"],
    "env": {
      "DEBUG": "true"
    }
  }
}
```

## Examples

### Example 1: Single HTTP Server

```python
import json
from mcp import Client

# Configure Armando MCP for evolution tools
config = {
    "armando": {
        "transport": "http",
        "url": "http://localhost:8002/mcp"
    }
}

result = mcp__madrox__spawn_claude(
    name="evolution_orchestrator",
    role="general",
    mcp_servers=json.dumps(config)
)

orchestrator_id = result["instance_id"]
```

### Example 2: Multiple MCP Servers

```python
import json

# Configure multiple MCP servers
config = {
    "armando": {
        "transport": "http",
        "url": "http://localhost:8002/mcp"
    },
    "playwright": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@playwright/mcp-server"]
    },
    "filesystem": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
    }
}

result = mcp__madrox__spawn_claude(
    name="full_stack_agent",
    role="general",
    mcp_servers=json.dumps(config)
)
```

### Example 3: Codex with MCP Servers

Works the same for Codex instances:

```python
import json

config = {
    "armando": {
        "transport": "http",
        "url": "http://localhost:8002/mcp"
    }
}

result = mcp__madrox__spawn_codex(
    name="codex_with_armando",
    model="gpt-5-codex",
    sandbox_mode="workspace-write",
    mcp_servers=json.dumps(config)
)
```

## Automatic Madrox MCP

**Important**: The Madrox MCP server is **always automatically added** to spawned instances, regardless of what you pass in `mcp_servers`.

This means:
- Child instances can always communicate back to parent via Madrox tools
- You don't need to explicitly include Madrox in your config
- If you do include it, your config will be overridden by the auto-config

Auto-configuration:
- **Claude instances**: HTTP transport to parent's port
- **Codex instances**: STDIO transport with subprocess spawning

## Error Handling

### Invalid JSON String

If the JSON string is malformed, it's logged and treated as empty dict:

```python
# ❌ Invalid JSON - will be ignored
mcp__madrox__spawn_claude(
    name="test",
    mcp_servers="{invalid json}"
)
# Result: Only Madrox MCP will be configured
```

### Empty String

Empty string is treated as empty dict:

```python
# Same as not passing mcp_servers at all
mcp__madrox__spawn_claude(
    name="test",
    mcp_servers=""
)
# Result: Only Madrox MCP will be configured
```

### None/Omitted

If `mcp_servers` is not provided or is `None`, it defaults to empty dict:

```python
# These are equivalent
mcp__madrox__spawn_claude(name="test")
mcp__madrox__spawn_claude(name="test", mcp_servers=None)
mcp__madrox__spawn_claude(name="test", mcp_servers=json.dumps({}))
# Result: Only Madrox MCP will be configured
```

## Verification

After spawning, verify MCP servers are configured correctly:

```python
import json

# 1. Spawn instance
config = {"armando": {"transport": "http", "url": "http://localhost:8002/mcp"}}
result = mcp__madrox__spawn_claude(
    name="test_instance",
    mcp_servers=json.dumps(config)
)
instance_id = result["instance_id"]

# 2. Check instance status
status = mcp__madrox__get_instance_status(instance_id=instance_id)

# 3. Verify mcp_servers field
mcp_servers = status.get("mcp_servers", {})
print(f"Configured MCP servers: {list(mcp_servers.keys())}")
# Expected: ['madrox', 'armando']

# 4. Ask instance to list its MCP servers
mcp__madrox__send_to_instance(
    instance_id=instance_id,
    message="List all available MCP servers you have access to"
)
```

## Troubleshooting

### "Server 'armando' not found. Available servers: madrox"

This means the MCP server configuration didn't work. Common causes:

1. **Forgot to use `json.dumps()`**
   ```python
   # ❌ Wrong - passing dict directly
   mcp_servers={"armando": {...}}

   # ✅ Correct - convert to JSON string
   mcp_servers=json.dumps({"armando": {...}})
   ```

2. **Invalid JSON string**
   - Check logs for "Invalid mcp_servers JSON string" errors
   - Verify your JSON is valid using `json.loads()` test

3. **MCP server URL is wrong**
   - Verify the URL is correct and server is running
   - For HTTP: test with `curl -X POST <url>`
   - For STDIO: test command manually in terminal

### Instance spawns but MCP tools don't work

1. **Check instance has access**
   ```python
   # Send test message
   mcp__madrox__get_tmux_pane_content(instance_id, lines=50)
   # Look for MCP server initialization messages
   ```

2. **Verify server is reachable**
   - HTTP servers: Check they're listening on specified port
   - STDIO servers: Check command and args are correct

3. **Check Claude Code version**
   - Ensure you're using a recent version that supports MCP
   - Update if necessary: `brew upgrade claude-code`

## API Reference

### spawn_claude

```python
def spawn_claude(
    name: str,
    role: str = "general",
    system_prompt: str | None = None,
    model: str | None = None,
    bypass_isolation: bool = True,
    parent_instance_id: str | None = None,
    wait_for_ready: bool = True,
    initial_prompt: str | None = None,
    mcp_servers: str | None = None,  # ← JSON string parameter
) -> dict[str, Any]
```

**Parameters:**
- `mcp_servers` (str | None): JSON string of MCP server configurations
  - Format: `'{"server_name": {"transport": "http", "url": "..."}}'`
  - Parsed internally to dict
  - Defaults to empty dict if None or empty string
  - Invalid JSON is logged and treated as empty dict

**Returns:**
- `dict` with `instance_id`, `status`, and `name`

### spawn_codex

```python
def spawn_codex(
    name: str,
    model: str | None = None,
    sandbox_mode: str = "workspace-write",
    profile: str | None = None,
    initial_prompt: str | None = None,
    bypass_isolation: bool = False,
    parent_instance_id: str | None = None,
    mcp_servers: str | None = None,  # ← JSON string parameter
) -> dict[str, Any]
```

**Parameters:**
- Same `mcp_servers` format as `spawn_claude`

## Testing

Run the test suite to verify JSON string parameter handling:

```bash
# Run all MCP JSON string tests
pytest tests/test_mcp_servers_json_string.py -v

# Run specific test
pytest tests/test_mcp_servers_json_string.py::test_spawn_claude_with_json_string_mcp_servers -v

# Run manually without pytest
python tests/test_mcp_servers_json_string.py
```

Tests verify:
1. ✅ Valid JSON string is parsed correctly
2. ✅ Empty string defaults to empty dict
3. ✅ Invalid JSON is handled gracefully
4. ✅ Configured servers appear in instance status
5. ✅ Madrox is always auto-added

## Migration Guide

If you were using the initial prompt workaround, you can now migrate:

### Before (Initial Prompt Workaround)

```python
orchestrator_task = """
CRITICAL SETUP: Configure Armando MCP server:
- Server name: armando
- URL: http://localhost:8002/mcp

Then execute: <task>
"""

mcp__madrox__spawn_claude(
    name="orchestrator",
    initial_prompt=orchestrator_task
)
```

### After (JSON String Parameter)

```python
import json

config = {
    "armando": {
        "transport": "http",
        "url": "http://localhost:8002/mcp"
    }
}

mcp__madrox__spawn_claude(
    name="orchestrator",
    mcp_servers=json.dumps(config),
    initial_prompt="<task>"  # Just the task, no setup instructions
)
```

**Benefits:**
- ✅ Cleaner separation of configuration and task
- ✅ Guaranteed to work (not relying on AI self-configuration)
- ✅ Faster initialization (no manual setup needed)
- ✅ Easier to debug (explicit configuration)

## Related Documentation

- [MCP Server Configuration Guide](MCP_SERVER_CONFIGURATION.md)
- [Architecture Overview](ARCHITECTURE.md)
- [API Reference](API_REFERENCE.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
