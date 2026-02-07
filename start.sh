#!/usr/bin/env bash
#
# Madrox — Start backend + frontend with a single command
#
# Usage:
#   ./start.sh          # Start both servers
#   ./start.sh --be     # Backend only  (port 8001)
#   ./start.sh --fe     # Frontend only (port 3002)
#

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BE_PID=""
FE_PID=""

cleanup() {
  echo ""
  echo "Shutting down..."
  [ -n "$FE_PID" ] && kill "$FE_PID" 2>/dev/null
  [ -n "$BE_PID" ] && kill "$BE_PID" 2>/dev/null
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

start_backend() {
  echo "Starting backend (port 8001)..."
  cd "$ROOT_DIR"

  # Activate venv if not already active
  if [ -z "$VIRTUAL_ENV" ] && [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
  fi

  MADROX_TRANSPORT=http python run_orchestrator.py &
  BE_PID=$!
}

start_frontend() {
  echo "Starting frontend (port 3002)..."
  cd "$ROOT_DIR/frontend"

  # Install deps if needed
  if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
  fi

  npx next dev -p 3002 &
  FE_PID=$!
}

# Parse args
case "${1:-}" in
  --be) start_backend ;;
  --fe) start_frontend ;;
  *)
    start_backend
    sleep 2  # Let backend bind before frontend starts
    start_frontend
    ;;
esac

echo ""
[ -n "$BE_PID" ] && echo "  Backend:   http://localhost:8001"
[ -n "$FE_PID" ] && echo "  Dashboard: http://localhost:3002"
echo ""
echo "  Press Ctrl+C to stop"
echo ""

wait
