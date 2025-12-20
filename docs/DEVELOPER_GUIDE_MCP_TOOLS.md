# Developer Guide: Working with MCP Tools in Madrox

**Last Updated**: 2025-11-08
**Applies to**: Madrox v0.x and later

---

## Table of Contents

- [Overview](#overview)
- [MCP Transport Architecture](#mcp-transport-architecture)
- [Adding New MCP Tools](#adding-new-mcp-tools)
- [Tool Registration Flow](#tool-registration-flow)
- [Testing Tool Discovery](#testing-tool-discovery)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

Madrox uses the Model Context Protocol (MCP) to expose orchestration capabilities as tools that can be discovered and used by AI instances. This guide explains how the MCP tool system works and how to add new tools.

### Key Concepts

- **MCP Tools**: Python methods decorated with `@mcp.tool` that become discoverable via MCP protocol
- **Dual Transport**: Madrox supports both HTTP/SSE and STDIO transports for different use cases
- **Automatic Discovery**: Child instances can query available tools via `tools/list` or `list_mcp_resources()`
- **Dynamic Registration**: Tools registered once in `instance_manager.py` are automatically available in both transports

---

## MCP Transport Architecture

Madrox implements two MCP server transports to support different client types:

### 1. HTTP/SSE Transport (Port 8001)

**Used by**:
- Claude Code clients
- Web UI
- External API clients

**Implementation**:
- `src/orchestrator/server.py` - FastAPI server
- `src/orchestrator/mcp_adapter.py` - MCP protocol adapter
- Exposes tools via HTTP endpoint at `http://localhost:8001/mcp`

**How it works**:
```python
# MCPAdapter reads tools directly from module-level mcp instance
tools_dict = await self.manager.mcp.get_tools()
```

### 2. STDIO Transport (Subprocess Pipes)

**Used by**:
- Codex child instances (Codex only supports STDIO)
- Subprocess communication requiring high performance

**Implementation**:
- `src/orchestrator/mcp_server.py` - OrchestrationMCPServer
- Uses JSON-RPC over stdin/stdout
- Dynamically binds tools using Python descriptor protocol

**How it works**:
```python
# Create STDIO MCP instance
self.mcp = FastMCP("claude-orchestrator-stdio")

# Dynamically register bound tools from module-level mcp
self._register_bound_tools()  # Uses descriptor protocol to bind self
```

**Bound Method Registration** (Descriptor Protocol):
```python
def _register_bound_tools(self):
    # Get all tools from module-level mcp
    source_tools = self.manager.mcp._tool_manager._tools

    for tool_name, tool_func in source_tools.items():
        original_func = tool_func.fn

        # Bind method to self.manager using descriptor protocol
        bound_method = original_func.__get__(self.manager, type(self.manager))

        # Register bound method (self already pre-bound)
        self.mcp.tool()(bound_method)
```

### Why Two Transports?

- **HTTP**: Used by Claude children - provides centralized visibility via parent HTTP server
- **STDIO**: Required for Codex (Codex only supports STDIO), high-performance (1-2ms latency)

**Architecture Decision**:
- **Claude children**: HTTP transport for cross-process visibility
- **Codex children**: STDIO transport with bound methods (required by Codex)
- Both get full access to all 27 Madrox tools

**Important**: Tools only need to be registered once in `instance_manager.py` - both transports handle them automatically (HTTP reads directly, STDIO binds dynamically).

---

## Adding New MCP Tools

### Step 1: Define the Tool Method

Add your tool method to `src/orchestrator/instance_manager.py` in the `InstanceManager` class:

```python
@mcp.tool
async def your_new_tool(
    self,
    required_param: str,
    optional_param: int = 100,
) -> dict[str, Any]:
    """Brief description of what your tool does.

    More detailed explanation if needed. This docstring becomes
    the tool description visible to AI agents.

    Args:
        required_param: Description of this parameter
        optional_param: Description with default value

    Returns:
        Dictionary with results/status
    """
    # Your implementation here
    result = await self._do_something(required_param, optional_param)
    return {"status": "success", "result": result}
```

### Step 2: That's It!

**No other changes needed.** The tool is automatically:
- ✅ Registered in the module-level `mcp` instance
- ✅ Available via HTTP transport (port 8001)
- ✅ Available via STDIO transport (child instances)
- ✅ Discoverable via `tools/list` queries
- ✅ Documented via docstring

### Type Annotations Matter

MCP uses type annotations to generate the input schema:

```python
@mcp.tool
async def example_tool(
    self,
    name: str,                    # Required string
    count: int = 5,              # Optional int with default
    options: dict[str, Any] | None = None,  # Optional dict
) -> dict[str, Any]:
    ...
```

This generates an OpenAPI-style schema that AI agents use to understand how to call your tool.

---

## Tool Registration Flow

Understanding how tools flow through the system:

### 1. Tool Definition (`instance_manager.py`)

```python
# Module-level FastMCP instance
mcp = FastMCP("claude-orchestrator")

class InstanceManager:
    def __init__(self, config):
        self.mcp = mcp  # Reference module-level instance

    @mcp.tool  # Decorator registers tool on module-level mcp
    async def spawn_claude(...):
        ...
```

**Result**: Tool registered in module-level `mcp` instance

### 2. HTTP Transport (`server.py` → `mcp_adapter.py`)

```python
class MCPAdapter:
    async def _build_tools_list(self):
        # Get tools from module-level mcp
        tools_dict = await self.manager.mcp.get_tools()
        return [tool.to_mcp_tool() for tool in tools_dict.values()]
```

**Result**: HTTP clients can discover and call tool via REST API

### 3. STDIO Transport (`mcp_server.py`)

```python
class OrchestrationMCPServer:
    def __init__(self, config):
        self.manager = InstanceManager(config.to_dict())
        self.mcp = FastMCP("claude-orchestrator-stdio")

        # Mount module-level mcp (copies all tool registrations)
        self.mcp.mount(self.manager.mcp)
```

**Result**: Child instances can discover and call tool via STDIO

### Visual Flow

```
┌─────────────────────────────────────────────────────────────┐
│ instance_manager.py                                         │
│                                                              │
│ mcp = FastMCP("claude-orchestrator")  ← Module-level        │
│                                                              │
│ @mcp.tool                                                    │
│ async def spawn_claude(...):                                │
│     ...                                                      │
└────────────────┬────────────────────────────────────────────┘
                 │ (Single source of truth)
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
┌──────────────┐  ┌──────────────────┐
│ HTTP Server  │  │ STDIO Server     │
│              │  │                  │
│ Reads from   │  │ Mounts           │
│ manager.mcp  │  │ manager.mcp      │
│              │  │                  │
│ Returns all  │  │ Inherits all     │
│ 27+ tools    │  │ 27+ tools        │
└──────────────┘  └──────────────────┘
```

---

## Testing Tool Discovery

### Test 1: HTTP Transport (External Client)

```bash
# Query HTTP endpoint
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'

# Should return all tools including your new tool
```

### Test 2: STDIO Transport (Child Instance)

```python
# Spawn a test child instance
child_id = await spawn_claude(name="test-child", role="general")

# From child, discover tools
# The child should see all tools via its STDIO connection
result = await list_mcp_resources()

# Verify your new tool appears in the list
assert "your_new_tool" in [tool["name"] for tool in result["resources"]]
```

### Test 3: Autonomous Agent Test

Best way to verify tool discovery works:

```python
# Give child a task that requires your tool
child_id = await spawn_claude(
    name="autonomous-tester",
    role="general",
    initial_prompt="Use your_new_tool to accomplish X. Discover it first via available tools."
)

# Monitor the child's output
output = await get_instance_output(child_id)

# The child should:
# 1. Discover your_new_tool via tools/list
# 2. Understand the parameters from the schema
# 3. Call the tool successfully
# 4. Complete the task autonomously
```

---

## Best Practices

### 1. Tool Naming

**Good**:
- `spawn_claude` - Clear action + object
- `get_instance_status` - Clear getter pattern
- `broadcast_to_children` - Descriptive action

**Avoid**:
- `do_thing` - Too vague
- `x` - Not descriptive
- `spawn_claude_instance_helper` - Too verbose

### 2. Parameter Design

**Use clear, typed parameters**:
```python
@mcp.tool
async def good_tool(
    self,
    instance_id: str,              # Clear, required
    timeout_seconds: int = 180,    # Clear default
    options: dict[str, Any] | None = None,  # Optional complex param
) -> dict[str, Any]:
    ...
```

**Avoid**:
```python
async def bad_tool(self, *args, **kwargs):  # No type hints!
    ...
```

### 3. Return Values

**Always return structured data**:
```python
return {
    "success": True,
    "instance_id": instance_id,
    "status": "spawned",
    "metadata": {...}
}
```

**Avoid returning bare strings or None** - makes it harder for AI agents to parse results.

### 4. Error Handling

**Raise clear exceptions**:
```python
if instance_id not in self.instances:
    raise ValueError(
        f"Instance {instance_id} not found. "
        f"Available instances: {list(self.instances.keys())}"
    )
```

AI agents can understand and recover from clear error messages.

### 5. Documentation

**Write clear docstrings**:
```python
@mcp.tool
async def coordinate_instances(
    self,
    coordinator_id: str,
    participant_ids: list[str],
    task_description: str,
) -> dict[str, Any]:
    """Coordinate multiple instances for a complex task.

    This tool enables a coordinator instance to delegate work to
    multiple participant instances and collect their results.

    Args:
        coordinator_id: ID of the coordinating instance
        participant_ids: List of participant instance IDs
        task_description: Description of the task to coordinate

    Returns:
        Dictionary with:
        - task_id: Unique identifier for this coordination task
        - status: Current status (running, completed, failed)
        - results: Results from each participant

    Raises:
        ValueError: If coordinator or participant instances not found
        RuntimeError: If instances are not in valid state

    Example:
        result = await coordinate_instances(
            coordinator_id="abc123",
            participant_ids=["def456", "ghi789"],
            task_description="Analyze dataset and generate report"
        )
    """
```

The docstring becomes the tool's documentation visible to AI agents.

---

## Troubleshooting

### Issue: Tool Not Appearing in Child Instance

**Symptoms**: HTTP transport sees tool, but child instance doesn't

**Diagnosis**:
```python
# From child instance
tools = await list_mcp_resources()
print(f"Discovered {len(tools)} tools")

# Should see 27+ tools
# If less, there's a discovery issue
```

**Solution**: Verify the mount operation in `mcp_server.py`:
```python
# Should have this line:
self.mcp.mount(self.manager.mcp)
```

### Issue: Tool Execution Fails

**Symptoms**: Tool discovered but execution fails

**Common Causes**:
1. **Type mismatch**: Check parameter types match annotations
2. **Missing await**: Async methods must be awaited
3. **Instance state**: Tool assumes instance in certain state

**Debug**:
```python
@mcp.tool
async def your_tool(self, param: str) -> dict[str, Any]:
    logger.debug(f"Tool called with param={param}, type={type(param)}")

    try:
        result = await self._implementation(param)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Tool failed: {e}", exc_info=True)
        raise
```

### Issue: Schema Generation Fails

**Symptoms**: Tool appears but agents can't understand parameters

**Cause**: Missing or incorrect type annotations

**Fix**:
```python
# ❌ Bad - no type hints
async def bad_tool(self, x, y=None):
    ...

# ✅ Good - full type hints
async def good_tool(
    self,
    x: str,
    y: int | None = None
) -> dict[str, Any]:
    ...
```

### Issue: Tool Not Discoverable After Adding

**Checklist**:
- [ ] Tool has `@mcp.tool` decorator
- [ ] Tool is method of `InstanceManager` class
- [ ] Decorator uses module-level `mcp` (not class instance)
- [ ] Server was restarted after adding tool
- [ ] Type annotations are complete

**Restart server**:
```bash
# Kill and restart orchestrator
pkill -f "madrox"
madrox start
```

---

## Advanced Topics

### Custom Tool Schemas

For complex schemas, you can customize the generated schema:

```python
from pydantic import BaseModel, Field

class SpawnConfig(BaseModel):
    name: str = Field(..., description="Instance name")
    role: str = Field("general", description="Role type")
    model: str | None = Field(None, description="Model to use")

@mcp.tool
async def spawn_with_config(
    self,
    config: SpawnConfig,
) -> dict[str, Any]:
    """Spawn instance with detailed configuration."""
    return await self.spawn_instance(**config.dict())
```

### Streaming Tools

For long-running operations, consider implementing progress updates:

```python
@mcp.tool
async def long_running_task(
    self,
    task_id: str,
) -> dict[str, Any]:
    """Start long-running task."""
    # Create job for async execution
    job_id = str(uuid.uuid4())
    self.jobs[job_id] = {
        "task_id": task_id,
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
    }

    # Start background task
    asyncio.create_task(self._execute_task(job_id, task_id))

    return {
        "job_id": job_id,
        "status": "started",
        "check_status_with": "get_job_status",
    }
```

Then agents can poll for updates:
```python
status = await get_job_status(job_id=job_id)
```

---

## Migration Notes

### Before Fix (Pre-2025-11-08)

Adding a new tool required:
1. Add `@mcp.tool` in `instance_manager.py`
2. **Manually** create bound wrapper in `mcp_server.py:_register_bound_tools()`

**Problem**: Easy to forget step 2, causing STDIO discovery failures.

### After Fix (2025-11-08+)

Adding a new tool requires:
1. Add `@mcp.tool` in `instance_manager.py`
2. **Done!** - mount() automatically includes it

**Benefit**: Single source of truth, no manual registration needed.

---

## Related Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
- [API_REFERENCE.md](./API_REFERENCE.md) - Complete API documentation
- [TOOL_DISCOVERY_BUG.md](./TOOL_DISCOVERY_BUG.md) - Details on the 2025-11-08 fix

---

## Support

For questions or issues:
1. Check the [Troubleshooting](#troubleshooting) section above
2. Review existing tools in `instance_manager.py` for examples
3. File an issue on GitHub with reproduction steps

**Last Updated**: 2025-11-08
