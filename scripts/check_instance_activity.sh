#!/bin/bash
# Quick script to check Madrox instance activity

echo "=== Madrox Instance Activity Check ==="
echo "Time: $(date)"
echo

echo "=== Tmux Sessions (Claude instances) ==="
tmux list-sessions 2>/dev/null | grep madrox | wc -l | xargs echo "Active sessions:"
echo

echo "=== Recent Instance Activity ==="
tail -20 /tmp/madrox_debug_logs/*.log 2>/dev/null | grep -E "(INFO|WARNING|ERROR)" | tail -10
echo

echo "=== Instance States ==="
if [ -f "network_monitor_history.json" ]; then
    python3 -c "
import json
try:
    with open('network_monitor_history.json') as f:
        history = json.load(f)
    if history:
        latest = history[-1]
        print(f\"Last update: {latest['timestamp']}\")
        print(f\"Total instances: {len(latest['instances'])}\")
        print()
        for inst in latest['instances']:
            print(f\"  {inst['name']:<25} {inst['state']:<12} msgs:{inst['message_count']:<4} uptime:{inst['uptime_seconds']}s\")
except Exception as e:
    print(f'Error: {e}')
"
else
    echo "No monitor history file found"
fi
