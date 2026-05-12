# Changelog

All notable changes to Madrox will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.0] - 2026-05-12

### Fixed

- **Eliminated inter-instance communication latency** — Response detection now races the bidirectional queue against pane polling concurrently (`asyncio.wait` with `FIRST_COMPLETED`). Previously sequential: waited the full `timeout_seconds` (30-180s) on an empty queue before falling back to polling. Typical response time dropped from minutes to seconds.
- **Fixed `_extract_response` instance_id bug** — Was using the first instance in the dict instead of the target instance, corrupting response extraction for any instance that wasn't the first spawned. Now uses diff-based extraction against the baseline output.
- **Fixed false-positive prompt detection** — Removed `⏵⏵` and `bypass permissions` from Claude prompt indicators (they're the persistent status bar, always visible). Added stale prompt counting to distinguish old prompts from new ones. Only checks the last non-status-bar line.
- **Root instances now use `reply_to_caller`** — Instances spawned without `parent_instance_id` were told "Do NOT use reply_to_caller." Now instructed to use it for `[MSG:]` messages, routing replies to the coordinator queue.
- **Correlation-aware queue consumption** — Queue replies now verify `correlation_id` matches the current `message_id`. Stale replies from previous messages are discarded. Queue is drained before each new send.
- **Queue preference on simultaneous completion** — When both queue and pane polling complete in the same event-loop turn, the queue result (cleaner text) is preferred.
- **Restored `response_time` and `estimated_tokens`** in the return dict for backward compatibility.

---

## [1.7.5] - 2026-05-11

### Fixed

- **Python 3.14 compatibility** — Bumped `uvloop` from `==0.21.0` to `>=0.22.1` (ships cp314 wheels). Made uvloop import graceful so the server starts with the default event loop if uvloop is unavailable.
- **Plugin startup reliability** — Raised health-check timeout from 15s to 60s (configurable via `MADROX_HEALTHCHECK_TIMEOUT`). On timeout, the last 20 lines of `backend.log` are now printed to stderr for diagnostics.

---

## [1.7.4] - 2026-05-11

### Added

- **Suspend/resume model for idle instance memory management** — Instances now auto-suspend after 30 minutes idle (configurable via `instance_timeout_minutes`). Suspension kills the tmux process (freeing 200-500MB per instance) but preserves the instance record, workspace, and conversation context. When a message is sent to a suspended instance, it auto-resumes transparently using `--continue`. Dashboard shows suspended instances with purple styling.

---

## [1.7.3] - 2026-05-10

### Fixed

- **`spawn_claude` / `spawn_codex` initial_prompt is now synchronous** — Added `wait_for_response` parameter (default: `false`) to both spawn tools. When `true`, the initial prompt response is captured and returned directly instead of fire-and-forget. Previously, `initial_prompt` was injected via raw keystrokes with a 2-second sleep and no output capture, forcing callers to manually retry with `send_to_instance`. Now reuses the existing `send_message()` two-phase response detection (bidirectional queue + pane polling fallback).

---

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
