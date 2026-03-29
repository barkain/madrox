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

set -e

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")" && pwd)}"
LOG_DIR="${LOG_DIR:-/tmp/madrox_logs}/$$"
mkdir -p "$LOG_DIR"

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

cleanup() {
  [ -n "$FE_PID" ] && kill "$FE_PID" 2>/dev/null
  [ -n "$BE_PID" ] && kill "$BE_PID" 2>/dev/null
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

# --- 1. Start HTTP backend ---
echo "Starting Madrox HTTP backend on port $BE_PORT..." >&2
MADROX_TRANSPORT=http uv run --directory "$PLUGIN_ROOT" python run_orchestrator.py \
  >"$LOG_DIR/backend.log" 2>&1 &
BE_PID=$!

# Wait for backend to be ready
echo "Waiting for backend health check..." >&2
for i in $(seq 1 30); do
  if curl -sf "http://localhost:$BE_PORT/health" >/dev/null 2>&1; then
    echo "Backend ready on port $BE_PORT." >&2
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Backend failed to start within 15 seconds." >&2
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

# --- 3. Run STDIO MCP proxy (foreground) ---
# This process owns stdout for the MCP protocol
echo "Madrox dashboard available at: http://localhost:$FE_PORT" >&2
exec uv run --directory "$PLUGIN_ROOT" python run_orchestrator.py
