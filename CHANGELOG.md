# Changelog

All notable changes to Madrox will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

#### STDIO MCP Tool Discovery & Cross-Process Visibility

**Problem 1: Tool Discovery (1/27 tools visible)**
- Child instances using STDIO transport could only discover 1 out of 27 available MCP tools
- FastMCP's `mount()` copied unbound instance methods with `self` parameter in signature
- Tool registration failed for methods requiring instance binding

**Solution 1: Bound Methods via Descriptor Protocol**
- Uses Python descriptor protocol (`__get__`) to bind methods before registration
- Pre-binds instance methods to `self.manager`, removing `self` from signature
- All 27 tools now discoverable via STDIO transport (Codex instances)

**Problem 2: Cross-Process Visibility**
- Teams spawned by STDIO children were not visible in parent HTTP server
- Environment variables not reaching Python subprocesses correctly
- Each STDIO subprocess created isolated Manager daemons

**Solution 2: Transport Architecture by Instance Type**
- **Claude children**: HTTP transport → centralized visibility via parent HTTP server
- **Codex children**: STDIO transport with bound methods → required (Codex only supports STDIO)
- Both instance types have full access to all 27 Madrox orchestration tools

### Technical Details

**Files Changed**:
- `src/orchestrator/mcp_server.py` - Bound method registration using descriptor protocol
- `src/orchestrator/tmux_instance_manager.py` - Transport selection by instance type (HTTP for Claude, STDIO for Codex)
- `src/orchestrator/instance_manager.py` - Cross-process instance status via shared metadata
- `src/orchestrator/server.py` - Orphaned tmux session cleanup on startup

**Architecture**:
```
Supervisor (HTTP) → Parent HTTP Server → Spawns all children
├── Claude children (HTTP): 29 tools (27 Madrox + 2 MCP protocol)
└── Codex children (STDIO): 27 tools (bound methods via descriptor protocol)
```

**Code Example** (STDIO tool registration):
```python
# Get original unbound method
original_func = tool_func.fn

# Bind to manager instance using descriptor protocol
bound_method = original_func.__get__(self.manager, type(self.manager))

# Register bound method (self already pre-bound)
self.mcp.tool()(bound_method)
```

**Results**:
- ✅ STDIO tool discovery: 27/27 tools for Codex instances
- ✅ HTTP tool discovery: 29/29 tools for Claude instances
- ✅ Cross-process visibility: All instances visible with parent-child hierarchy
- ✅ Mixed teams: Claude + Codex teams fully functional
- ✅ Bidirectional messaging: `reply_to_caller` working across all instances

**Trade-offs**:
- Claude HTTP latency: 300-400ms (vs STDIO 1-2ms)
- Acceptable for reliable cross-process visibility
- Codex maintains STDIO performance advantages

**Backward Compatibility**: No breaking changes, all existing code continues to work

**Branch**: [feature/fix-stdio-tool-discovery](https://github.com/anthropics/madrox/tree/feature/fix-stdio-tool-discovery)

---

## [Previous Releases]

For changes prior to this release, see git commit history.
