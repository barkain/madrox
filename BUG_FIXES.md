# Bug Fixes - Codex HTTP Transport & Model Validation

## Issues Found

### 1. Invalid Codex Model Names
**Error**: `400 Bad Request: {"detail":"Unsupported model"}`

**Root Cause**:
- `spawn_codex` documentation misleading - mentioned "gpt-5-codex, gpt-4, gpt-4o" but didn't warn about invalid legacy names
- Parent Claude instance tried to spawn Codex with `model="codex-1"` (invalid)
- Codex CLI only accepts OpenAI GPT models: gpt-5-codex, gpt-4o, gpt-4, o3

**Fix Applied** (`src/orchestrator/instance_manager.py:576-618`):
- Updated docstring with clear model options
- Added validation for legacy Codex model names ("codex", "codex-1", "codex-mini")
- Better error messages guiding users to correct model names

### 2. MCP Client Handshake Failure
**Error**:
```
MCP client for `madrox` failed to start: handshaking with MCP server failed:
Send message error Transport [rmcp::transport::worker::WorkerTransport] error:
Transport channel closed, when send initialized notification
```

**Root Cause**:
- Madrox HTTP server was running but MCP adapter endpoint may have issues
- Possible race condition during initialization
- Transport channel closed before initialization complete

**Status**: Needs investigation
- HTTP server starts successfully (:8001)
- MCP adapter endpoint responds to `/health`
- Issue may be timing-related or protocol version mismatch

## Testing Summary

### ✅ Completed Tests
- HTTP transport: ✅ PASS (health, root, MCP adapter)
- STDIO transport: ✅ PASS (initialize, tools/list with 26 tools)
- Auto-detection: ✅ PASS (piped input, environment override)
- Concurrent transports: ✅ PASS (no interference)
- Code quality: ✅ PASS (ruff format/lint)

### Model Validation Test
```python
# Now correctly rejects invalid models
spawn_codex(name="test", model="codex-1")
# ❌ ValueError: Invalid model 'codex-1'. Codex CLI uses OpenAI GPT models,
#    not legacy Codex models. Try: gpt-5-codex (default), gpt-4o, gpt-4, or o3.

# Correct usage
spawn_codex(name="test", model="gpt-5-codex")  # ✅
spawn_codex(name="test", model="gpt-4o")       # ✅
spawn_codex(name="test")                        # ✅ Uses default from config
```

## Recommendations

### For Users
1. **Always specify valid model names**:
   - Codex: `gpt-5-codex`, `gpt-4o`, `gpt-4`, `o3`
   - Claude: `claude-sonnet-4-20250514`, etc.

2. **Check MCP server health** before spawning:
   ```bash
   curl http://localhost:8001/health
   ```

3. **Use correct spawn methods**:
   - `spawn_claude()` for Claude models
   - `spawn_codex()` for OpenAI GPT models

### For Developers
1. **MCP transport investigation needed**:
   - Add retry logic for MCP handshake
   - Verify protocol version compatibility
   - Check for race conditions in server startup

2. **Additional validation**:
   - Add real-time model availability check
   - Validate against OpenAI API model list

3. **Better error messages**:
   - Include available models in error response
   - Add link to documentation
