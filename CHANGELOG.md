# Changelog

All notable changes to Madrox will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [1.9.1] - 2026-08-03

### Fixed

- **Grok spawned the wrong model and failed** — Grok documents the short model flag only (`grok -p "Hello" -m my-model`), but the harness inherited `--model`, which the CLI did not pick up. The requested model was silently ignored and the CLI ran its own default; nothing errored. The pinned default made it worse: `grok-build-0.1` is not a real model id (per [the xAI docs](https://docs.x.ai/build/overview) the model behind Grok Build is `grok-4.5`), so the fallback landed on an older model that not every account can use.
- **No harness pins a model any longer** — when the caller does not name a model, Madrox passes no model flag and the CLI uses its own current default. A pinned id goes stale as soon as a vendor ships a new model, and a stale id breaks spawning rather than degrading. An explicit `model=` is still forwarded verbatim, and a default can still be pinned deliberately via `default:` in `config/models.yaml` or `MADROX_MODEL_<HARNESS>`. This reverses the "defaults always applied" behaviour introduced in 1.9.0.
- **The dashboard is started on demand instead of per session** — `start_plugin.sh` launched a Next.js *development* server for every session whether or not the dashboard was ever opened. With many concurrent sessions those dominated the machine's process and memory load. The proxy now starts it on the first `get_dashboard_url` call, spawned as its own child so the existing tree-killing cleanup still reaps it.
- **`uv sync` no longer blocks session startup** — every session synced the same `PLUGIN_ROOT`, and uv takes a project lock, so concurrent launches serialised behind one another. The call was guarded against failure but not against blocking, so a session could sit there until Claude Code abandoned the MCP handshake — leaving a log directory and `session_ports.env` but no `backend.log` and nothing on stderr to explain it. The sync is now skipped when `uv.lock` and `pyproject.toml` are unchanged since the last successful run, and bounded by a watchdog (`MADROX_SYNC_TIMEOUT`, default 20s).
- **Spawning survives a deleted working directory** — the spawn start method records `os.getcwd()` for the child, so once the directory a session was launched from was removed (routine, since sessions run in throwaway worktrees) every `multiprocessing.Manager`/`Process` spawn died with `FileNotFoundError` from `get_preparation_data`.

### Note

The "severe subprocess leak" described in 1.8.2 overstates what was wrong. The cleanup trap and `reap_orphans` work correctly — the processes observed were live sessions' stacks, each parented by a live `claude`, not orphans. The real problem was the weight of a per-session stack, which the dashboard and `uv sync` changes above address.

---

## [1.9.0] - 2026-08-01

### Added

- **Grok Build support** — `spawn_grok` launches xAI's Grok Build CLI as a first-class harness alongside Claude Code and Codex. It runs in yolo mode by default (`--always-approve`, the flag behind the `/yolo` slash command), matching how Claude (`--dangerously-skip-permissions`) and Codex (`--dangerously-bypass-approvals-and-sandbox`) instances are launched. MCP servers are registered with `grok mcp add --scope project` for both stdio and HTTP transports, so registrations stay inside the instance workspace, and dead sessions are recovered with `grok --resume`.
- **Harness registry** (`src/orchestrator/harnesses.py`) — one class per CLI agent holding its executable, yolo flags, model flag, launch/resume commands, MCP registration style and terminal ready/idle/trust markers. Adding a harness is now a subclass plus a spawn tool; the MCP adapter derives spawn routing from the registry.
- **Configurable harness defaults** — `config/models.yaml` gained per-harness `command` (executable override) and `extra_args`, plus env overrides: `MADROX_MODEL_<HARNESS>` (default model), `MADROX_<HARNESS>_BIN` (executable) and `MADROX_MODELS_CONFIG` (alternate config file). Defaults can change without touching code.

### Changed

- **Default models refreshed and always applied** — Claude defaults to `claude-opus-5`, Codex to `gpt-5.6-sol`, Grok to `grok-build-0.1`. Defaults are now resolved inside `spawn_instance`, a single choke point shared by the MCP tools, the HTTP/SSE adapter and direct calls; previously the HTTP adapter path spawned with `model=None` and silently got the CLI's own default. Spawn results now report the resolved `model`. Model ids are still never validated against an allowlist, so a model released today works without a Madrox update.
- **Stale hardcoded model ids removed** — `claude-4-sonnet-20250514` no longer appears as a default in the REST spawn path, `SpawnInstanceRequest` or `OrchestratorConfig`; these default to `None`, meaning "use the harness default".
- **`config.validate_model()` replaced by `config.resolve_model()`** — one resolution function instead of two with different failure modes. `resolve_model()` never raises: a missing or malformed `config/models.yaml` degrades to the CLI's own default instead of failing the spawn.

### Fixed

- **Failed CLI startup no longer reports a healthy instance** — when a pane-driven CLI (Codex, Grok) never became ready, bootstrap was skipped but the spawn still marked the instance `idle`, so every later message was typed into a bare shell. Startup now raises, and the instance is marked `error` with the reason.
- **Grok MCP registration used the wrong CLI syntax** — registrations were built as `grok mcp add --scope project -t stdio <name> <cmd>`, but the documented syntax takes no transport flag for stdio and requires a `--` separator, while HTTP uses `--transport` rather than `-t`. Since this call registers the auto-injected `madrox` server, every Grok instance started with no orchestrator tools — unable to call `reply_to_caller` or spawn children. Grok also has no CLI flag for environment variables, so stdio servers now run under `env` instead of having their environment dropped.
- **Backend rejections are reported on the default spawn path** — error surfacing only ran when both `wait_for_response` and `initial_prompt` were given, but `wait_for_response` defaults to `false`; in that case the prompt was typed into the pane and never checked. Spawning with a model the backend rejects returned `status: "spawned"` while the error sat unread in the terminal. The bootstrap now scans the pane and the spawn result reports `status: "failed"` with `error_message`.
- **HTTP/SSE spawns get the same result shape as the MCP tools** — the adapter called `spawn_instance()` directly instead of the shared `_spawn_harness_instance()` helper, so that transport silently dropped `status`, `error_message`, the resolved `model` and `wait_for_response`. Both transports now go through one path.
- **`spawn_grok` no longer discards `role` and `system_prompt`** — pane-delivered harnesses have no `--system-prompt` flag and only ever received the identity briefing, so both parameters were accepted and thrown away. Role and custom prompts are now delivered with the briefing.
- **Role prompts are actually loaded** — `_get_role_prompt()` resolved `resources/prompts` one directory short of the repository root, so *every* role silently fell back to the generic assistant prompt. Friendlier spellings (`security`, `qa_engineer`, `data_scientist`, `reviewer`, `docs`, …) now map to the canonical role ids, and `CLAUDE.md` lists the roles that actually ship — it previously documented six that never existed.
- **Operator-supplied config values are shell-quoted** — the new `command`/`extra_args` settings were interpolated into a shell-joined command unquoted, so `extra_args: ["--rules", "Use pytest only"]` split into four arguments and an executable path containing a space broke the invocation.
- **Malformed model config degrades instead of crashing** — a syntactically valid `config/models.yaml` whose top level is not a mapping (a list, a bare string) raised `AttributeError` from `get_harness_config()`, outside the handler meant to catch it.

### Performance

- **Spawns no longer block the event loop** — MCP-server registration and multiline message delivery paced themselves with blocking `time.sleep()` inside async code, stalling every other instance for the duration (up to seconds for a large message). Both now yield with `await asyncio.sleep()`, and the per-MCP-server pause dropped from 200ms to 50ms.
- **Codex config written once per spawn** — workspace pre-trust and HTTP MCP servers each did their own `~/.codex/config.toml` load/dump (once *per server*); they now share a single batched read-modify-write that skips the write entirely when nothing changed.
- **Cheaper response polling** — the idle-prompt scan over the full pane ran on every 300ms poll; it now runs only after output has settled, and stops at the last content line instead of building a filtered list of every line.

### Internal

- Session startup and crash recovery were two near-identical 250-line methods; they are now one harness-driven path (`_start_cli_session`), cutting ~290 lines from `tmux_instance_manager/core.py`. Duplicated bootstrap prompt blocks, session-env setup, CLI-ready polling and the three spawn tools were deduplicated the same way. Module-level imports replaced repeated function- and loop-level imports.

---

## [1.8.2] - 2026-06-20

### Fixed

- **Severe subprocess leak — orphaned orchestrator stacks (#30)** — Every plugin session leaked its entire stack (HTTP backend, `multiprocessing.Manager` daemon, `resource_tracker`, frontend) to `launchd`. Over many sessions these accumulated into the hundreds, exhausting RAM and pinning swap. Fixed at the source in `start_plugin.sh`:
  - The STDIO proxy is no longer started with `exec` (which destroyed the cleanup `trap`); it runs as a child so the shell tears the backend/frontend down on session end.
  - `cleanup()` now terminates each managed process *tree* (TERM → grace → KILL), reaching the `multiprocessing` children that `uv run` indirection previously hid.
  - On startup, `reap_orphans` reclaims processes left by previous sessions that died uncleanly (e.g. SIGKILL) — scoped across all installed versions, so an updated plugin also cleans up orphans left by the version it replaced.
  - The venv is synced up front (`uv sync`) and the backend/proxy launch `.venv/bin/python` directly, so the launcher shell is their parent. A new parent-death watchdog in the backend self-terminates it (running the lifespan teardown that kills the Manager daemon) if it is orphaned to PID 1.

---

## [1.8.1] - 2026-06-16

### Fixed

- **Codex backend failures are no longer silent** (#28) — When a Codex instance hits a backend error (e.g. the Bedrock proxy 404ing an unknown model, a JSON-RPC error, or a stream failure), the spawn / `send_to_instance` result now reports `status: "failed"` with the terminal error surfaced in `error` / `error_message`, and `get_instance_status` exposes the same message. Previously these failures returned `status: "completed"` with an empty `response` and `error_message: null`, only diagnosable by scraping the tmux pane. Empty output with no detectable error is also flagged as a failure.

### Changed

- **Removed the static model allowlist** (#28) — `spawn_claude` / `spawn_codex` no longer validate model names against a hard-coded list. Any model string is forwarded to the underlying CLI/backend as-is; only the provider default (from `config/models.yaml`) is used when no model is given. The allowlist produced false rejections and gave false confidence for Codex models, whose valid ids are served by an AWS Bedrock proxy that changes independently of Madrox. Documented the Codex Bedrock routing and the new error behavior in `docs/TROUBLESHOOTING.md`.

---

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
