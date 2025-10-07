#!/bin/bash
set -e

# Madrox MCP Server Docker Entrypoint
# Handles initialization, environment validation, and graceful shutdown

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Trap SIGTERM and SIGINT for graceful shutdown
shutdown() {
    log_info "Received shutdown signal, stopping Madrox gracefully..."

    # Kill child processes gracefully
    if [ -n "$PID" ]; then
        kill -TERM "$PID" 2>/dev/null || true
        wait "$PID" 2>/dev/null || true
    fi

    log_info "Madrox stopped successfully"
    exit 0
}

trap shutdown SIGTERM SIGINT

# Validate required environment variables
log_info "Validating environment configuration..."

if [ -z "$ANTHROPIC_API_KEY" ]; then
    log_error "ANTHROPIC_API_KEY is not set. Please provide a valid API key."
    exit 1
fi

# Validate API key format (basic check)
if [[ ! "$ANTHROPIC_API_KEY" =~ ^sk-ant- ]]; then
    log_warn "ANTHROPIC_API_KEY format may be invalid (should start with 'sk-ant-')"
fi

# Set default values if not provided
export ORCHESTRATOR_HOST=${ORCHESTRATOR_HOST:-0.0.0.0}
export ORCHESTRATOR_PORT=${ORCHESTRATOR_PORT:-8001}
export MAX_INSTANCES=${MAX_INSTANCES:-10}
export WORKSPACE_DIR=${WORKSPACE_DIR:-/tmp/claude_orchestrator}
export LOG_DIR=${LOG_DIR:-/logs}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

log_info "Configuration:"
log_info "  Host: $ORCHESTRATOR_HOST"
log_info "  Port: $ORCHESTRATOR_PORT"
log_info "  Max Instances: $MAX_INSTANCES"
log_info "  Workspace: $WORKSPACE_DIR"
log_info "  Log Directory: $LOG_DIR"
log_info "  Log Level: $LOG_LEVEL"

# Create required directories
log_info "Initializing directories..."
mkdir -p "$WORKSPACE_DIR" "$LOG_DIR" /data

# Set proper permissions (already owned by madrox user)
chmod 755 "$WORKSPACE_DIR" "$LOG_DIR" /data

# Initialize SQLite database if it doesn't exist
DB_PATH="${DATABASE_URL#sqlite:///}"
DB_PATH="${DB_PATH:-/data/claude_orchestrator.db}"

if [ ! -f "$DB_PATH" ]; then
    log_info "Initializing SQLite database at $DB_PATH..."
    sqlite3 "$DB_PATH" "VACUUM;" || true
else
    log_info "Using existing database at $DB_PATH"
fi

# Validate database is accessible
if ! sqlite3 "$DB_PATH" "SELECT 1;" >/dev/null 2>&1; then
    log_error "Cannot access SQLite database at $DB_PATH"
    exit 1
fi

# Check for tmux availability (required for instance management)
if ! command -v tmux >/dev/null 2>&1; then
    log_error "tmux is not installed but required for instance management"
    exit 1
fi

# Health check: Verify Python and required modules
log_info "Verifying Python environment..."
python -c "import fastapi, uvicorn, anthropic, mcp" 2>/dev/null || {
    log_error "Required Python packages are not installed"
    exit 1
}

log_info "Environment validation complete"
log_info "Starting Madrox MCP Server..."
log_info "===================="

# Execute the main command and capture PID
exec "$@" &
PID=$!

# Wait for the process
wait "$PID"
