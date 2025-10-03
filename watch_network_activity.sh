#!/bin/bash
# Watch all instance activity in real-time

INSTANCES=(
    "8f09e67e-73dc-4850-8a6e-335b045dbee4:main_orchestrator"
    "a8aca09f-488c-40d4-a81a-88b8b57e9474:backend_dev_1"
    "09255de6-631f-4b5b-8048-b81f18267188:backend_dev_2"
    "9180f19a-4158-4a03-aebb-20d138a48c23:tester_1_1"
    "3d763299-02c0-4483-abc0-55931feeed0c:tester_1_2"
    "a7de6da9-4367-4ece-a79a-60cfe0129876:tester_2_1"
    "ba2ffb27-80f8-48cc-b1a1-4fcd18b7a41d:tester_2_2"
)

echo "=== Madrox Network Activity Monitor ==="
echo "Time: $(date)"
echo

for inst in "${INSTANCES[@]}"; do
    IFS=: read -r id name <<< "$inst"

    log_dir="/tmp/madrox_logs/instances/$id"

    if [ -d "$log_dir" ]; then
        echo ">>> $name ($id)"

        # Show message count
        msg_count=$(wc -l < "$log_dir/communication.jsonl" 2>/dev/null || echo "0")
        echo "  Messages: $msg_count"

        # Show last activity
        if [ -f "$log_dir/communication.jsonl" ]; then
            echo "  Last activity:"
            tail -1 "$log_dir/communication.jsonl" | python3 -m json.tool 2>/dev/null | grep -E "(timestamp|event_type|direction)" | head -3
        fi

        echo
    else
        echo ">>> $name ($id) - No logs yet"
        echo
    fi
done

echo "=== Summary ==="
total_messages=0
for inst in "${INSTANCES[@]}"; do
    IFS=: read -r id name <<< "$inst"
    log_dir="/tmp/madrox_logs/instances/$id"
    if [ -f "$log_dir/communication.jsonl" ]; then
        count=$(wc -l < "$log_dir/communication.jsonl")
        total_messages=$((total_messages + count))
    fi
done

echo "Total messages across network: $total_messages"
