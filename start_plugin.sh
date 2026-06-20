#!/usr/bin/env bash
#
# Madrox Claude Code Plugin Startup Script
#
# Manages three processes:
#   1. HTTP backend server (background, dynamic port)
#   2. Next.js frontend dashboard (background, dynamic port)
#   3. STDIO MCP proxy (foreground, connected to Claude Code)
#
# STDOUT is reserved for the STDIO MCP protocol — all other output goes to stderr/logs.
#
# Process lifecycle (see issue #30 — subprocess leak):
#   - The STDIO proxy is run as a *child* (not via `exec`) so this shell — and its
#     cleanup trap — stays alive to tear down the backend/frontend when the session ends.
#   - cleanup() kills each managed process *tree* (TERM, grace, then KILL) so the
#     backend's multiprocessing.Manager daemon / resource_tracker children don't orphan.
#   - reap_orphans() reclaims processes left behind by previous sessions that died
#     uncleanly (e.g. SIGKILL), so orphans can't accumulate across runs.
#

set -e

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")" && pwd)}"
LOG_DIR="${LOG_DIR:-/tmp/madrox_logs}/$$"
mkdir -p "$LOG_DIR"

# Process-lifecycle helpers: kill_tree, tree_alive, shutdown_trees, reap_orphans
# shellcheck source=scripts/proc_lifecycle.sh
. "$PLUGIN_ROOT/scripts/proc_lifecycle.sh"

# Reclaim orphans left behind by previous sessions that died uncleanly.
reap_orphans || true

# --- Find free ports ---
find_free_port() {
  python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()"
}

BE_PORT=$(find_free_port)
FE_PORT=$(find_free_port)

export ORCHESTRATOR_PORT="$BE_PORT"

# Write port file for other tools (e.g. dashboard skill)
echo "BE_PORT=$BE_PORT" > "$LOG_DIR/session_ports.env"
echo "FE_PORT=$FE_PORT" >> "$LOG_DIR/session_ports.env"

echo "Session ports: backend=$BE_PORT, frontend=$FE_PORT" >&2

BE_PID=""
FE_PID=""
PROXY_PID=""
CLEANED=""

cleanup() {
  # Idempotent — runs at most once (EXIT trap may fire after a signal trap).
  [ -n "$CLEANED" ] && return
  CLEANED=1

  # TERM each tree, allow the backend to shut down gracefully (uvicorn lifespan
  # tears down the multiprocessing.Manager daemon), then KILL any survivors.
  shutdown_trees "$PROXY_PID" "$FE_PID" "$BE_PID"
  wait 2>/dev/null || true
}
trap cleanup EXIT
# Translate signals into a normal exit so the single EXIT trap does the cleanup.
trap 'exit 143' TERM
trap 'exit 130' INT

# --- Bootstrap the venv, then run python directly --------------------------
# Sync the project environment up front (creates .venv on first run, applies any
# dependency changes after a plugin update — the work `uv run` used to do on every
# invocation). We then launch the venv's python *directly* in both the backend and
# proxy below, so THIS shell is their parent. That keeps signal delivery simple and
# lets the backend's parent-death watchdog fire if this shell is killed — which it
# could NOT do behind a `uv run` wrapper (only `uv` would reparent to PID 1).
VENV_PYTHON="$PLUGIN_ROOT/.venv/bin/python"
echo "Syncing dependencies (uv sync)..." >&2
if ! uv sync --directory "$PLUGIN_ROOT" >"$LOG_DIR/uv-sync.log" 2>&1; then
  echo "WARNING: 'uv sync' failed; see $LOG_DIR/uv-sync.log" >&2
  tail -20 "$LOG_DIR/uv-sync.log" >&2
fi

# --- 1. Start HTTP backend ---
echo "Starting Madrox HTTP backend on port $BE_PORT..." >&2
if [ -x "$VENV_PYTHON" ]; then
  MADROX_TRANSPORT=http "$VENV_PYTHON" "$PLUGIN_ROOT/run_orchestrator.py" \
    >"$LOG_DIR/backend.log" 2>&1 &
else
  # Degraded fallback: venv could not be created. The backend still runs, but
  # behind `uv run` the parent-death watchdog won't apply to it (reap_orphans on
  # the next launch still bounds any leak).
  echo "WARNING: venv python missing — falling back to 'uv run' for backend" >&2
  MADROX_TRANSPORT=http uv run --directory "$PLUGIN_ROOT" python run_orchestrator.py \
    >"$LOG_DIR/backend.log" 2>&1 &
fi
BE_PID=$!

# Wait for backend to be ready (configurable timeout, default 60s)
HEALTHCHECK_TIMEOUT="${MADROX_HEALTHCHECK_TIMEOUT:-60}"
HEALTHCHECK_ITERATIONS=$(( HEALTHCHECK_TIMEOUT * 2 ))  # 0.5s per iteration
echo "Waiting for backend health check (timeout: ${HEALTHCHECK_TIMEOUT}s)..." >&2
for i in $(seq 1 "$HEALTHCHECK_ITERATIONS"); do
  if curl -sf "http://localhost:$BE_PORT/health" >/dev/null 2>&1; then
    echo "Backend ready on port $BE_PORT." >&2
    break
  fi
  if [ "$i" -eq "$HEALTHCHECK_ITERATIONS" ]; then
    echo "ERROR: Backend failed to start within ${HEALTHCHECK_TIMEOUT} seconds." >&2
    echo "Last 20 lines of backend log:" >&2
    tail -20 "$LOG_DIR/backend.log" >&2
    exit 1
  fi
  sleep 0.5
done

# --- 2. Start frontend dashboard ---
FRONTEND_DIR="$PLUGIN_ROOT/frontend"
if [ -d "$FRONTEND_DIR" ]; then
  # Install deps on first run
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "Installing frontend dependencies..." >&2
    npm install --prefix "$FRONTEND_DIR" >"$LOG_DIR/frontend-install.log" 2>&1
  fi

  echo "Starting Madrox dashboard on port $FE_PORT..." >&2
  (cd "$FRONTEND_DIR" && PORT=$FE_PORT NEXT_PUBLIC_BACKEND_PORT=$BE_PORT npx next dev -p "$FE_PORT") \
    >"$LOG_DIR/frontend.log" 2>&1 &
  FE_PID=$!
fi

# --- 3. Run STDIO MCP proxy (child, NOT exec) ---
# Running it as a child (rather than `exec`-ing) keeps this shell — and the
# cleanup trap — alive so the backend/frontend are torn down when the proxy
# exits or this script is signalled.
#
# The proxy speaks the MCP protocol over stdin/stdout, so it must inherit OUR
# stdin (Claude's pipe). In a non-interactive shell, a backgrounded command's
# stdin would otherwise be redirected from /dev/null; the explicit `0<&0`
# redirection suppresses that default and forwards our stdin to the proxy.
echo "Madrox dashboard available at: http://localhost:$FE_PORT" >&2
export MADROX_FRONTEND_PORT="$FE_PORT"
if [ -x "$VENV_PYTHON" ]; then
  "$VENV_PYTHON" "$PLUGIN_ROOT/run_orchestrator.py" 0<&0 &
else
  uv run --directory "$PLUGIN_ROOT" python run_orchestrator.py 0<&0 &
fi
PROXY_PID=$!

# Wait for the proxy. `wait` is interruptible by traps, so a SIGTERM/SIGINT here
# runs cleanup immediately; a clean proxy exit (Claude closes stdin) falls
# through to the EXIT trap.
wait "$PROXY_PID"
