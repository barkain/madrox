#!/bin/bash
set -e

echo "=== Testing Transport Auto-Detection ==="
echo

# Test 1: Terminal mode (should start HTTP)
echo "Test 1: Terminal mode detection"
uv run python run_orchestrator.py 2>&1 | head -20 &
PID1=$!
sleep 3
if ps -p $PID1 > /dev/null 2>&1; then
    echo "✅ Server started in terminal mode (HTTP)"
    kill $PID1 2>/dev/null || true
    wait $PID1 2>/dev/null || true
else
    echo "❌ Server failed to start"
fi
echo

# Test 2: Piped mode (should start STDIO)
echo "Test 2: Piped mode detection"
RESPONSE=$(echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | uv run python run_orchestrator.py 2>&1 | grep -o '{"jsonrpc".*}' | head -1)
if [[ $RESPONSE == *"serverInfo"* ]]; then
    echo "✅ STDIO mode responded to piped input"
else
    echo "❌ STDIO mode failed"
    echo "Response: $RESPONSE"
fi
echo

# Test 3: Environment override to STDIO
echo "Test 3: Environment override (MADROX_TRANSPORT=stdio)"
RESPONSE=$(echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | MADROX_TRANSPORT=stdio uv run python run_orchestrator.py 2>&1 | grep -o '{"jsonrpc".*}' | head -1)
if [[ $RESPONSE == *"serverInfo"* ]]; then
    echo "✅ Environment override to STDIO works"
else
    echo "❌ STDIO override failed"
fi
echo

# Test 4: Environment override to HTTP
echo "Test 4: Environment override (MADROX_TRANSPORT=http)"
MADROX_TRANSPORT=http uv run python run_orchestrator.py 2>&1 | head -10 &
PID4=$!
sleep 2
if ps -p $PID4 > /dev/null 2>&1; then
    echo "✅ Environment override to HTTP works"
    kill $PID4 2>/dev/null || true
    wait $PID4 2>/dev/null || true
else
    echo "❌ HTTP override failed"
fi
echo

echo "=== Auto-detection tests completed ==="
