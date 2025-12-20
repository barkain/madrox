#!/bin/bash
set -e

# Navigate to repository root (two levels up from scripts/tests/)
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

echo "=== Testing Concurrent HTTP and STDIO Transports ==="
echo

# Start HTTP server in background
echo "Starting HTTP server..."
MADROX_TRANSPORT=http uv run python run_orchestrator.py 2>&1 | grep -v "DeprecationWarning" > /tmp/http_server.log &
HTTP_PID=$!
sleep 5

# Check HTTP server is running
if ! ps -p $HTTP_PID > /dev/null; then
    echo "❌ HTTP server failed to start"
    exit 1
fi
echo "✅ HTTP server running (PID: $HTTP_PID)"

# Test HTTP endpoint
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health)
if [ "$HTTP_STATUS" = "200" ]; then
    echo "✅ HTTP server responding (status: $HTTP_STATUS)"
else
    echo "❌ HTTP server not responding (status: $HTTP_STATUS)"
    kill $HTTP_PID 2>/dev/null || true
    exit 1
fi

# Test STDIO transport (doesn't interfere with HTTP)
echo
echo "Testing STDIO transport while HTTP is running..."
STDIO_RESPONSE=$(echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | uv run python run_orchestrator.py 2>&1 | grep -o '{"jsonrpc".*}' | head -1)

if [[ $STDIO_RESPONSE == *"serverInfo"* ]]; then
    echo "✅ STDIO transport works independently"
else
    echo "❌ STDIO transport failed"
    echo "Response: $STDIO_RESPONSE"
    kill $HTTP_PID 2>/dev/null || true
    exit 1
fi

# Clean up
echo
echo "Cleaning up..."
kill $HTTP_PID 2>/dev/null || true
wait $HTTP_PID 2>/dev/null || true
echo "✅ HTTP server stopped"

echo
echo "=== Concurrent transport test PASSED ==="
echo "✅ Both HTTP and STDIO transports work independently"
echo "✅ No conflicts or interference between transports"
