#!/usr/bin/env python3
"""Quickstart: Spawn 3 agents, give each a task, collect results.

Prerequisites:
    ./start.sh          # start Madrox backend on :8001
    pip install requests # (or use uv)

Usage:
    python examples/quickstart_3_agents.py
"""

import requests

URL = "http://localhost:8001"


def call_tool(tool_name: str, args: dict) -> dict:
    """Execute an MCP tool via the REST API."""
    resp = requests.post(f"{URL}/tools/execute", json={"tool": tool_name, "arguments": args})
    resp.raise_for_status()
    return resp.json()


# 1. Spawn three agents in parallel
agents = call_tool(
    "spawn_multiple_instances",
    {
        "instances": [
            {"name": "researcher", "role": "general"},
            {"name": "writer", "role": "general"},
            {"name": "reviewer", "role": "general"},
        ]
    },
)

ids = [a["instance_id"] for a in agents["spawned"]]
print(f"Spawned: {ids}")

# 2. Send each a task (non-blocking)
tasks = {
    ids[0]: "List 3 pros and cons of microservices vs monoliths. Be brief.",
    ids[1]: "Write a one-paragraph project README intro for a task-manager CLI.",
    ids[2]: "Review this function and suggest one improvement:\ndef add(a,b): return a+b",
}

for agent_id, task in tasks.items():
    call_tool("send_to_instance", {"instance_id": agent_id, "message": task})
    print(f"Sent task to {agent_id[:8]}")

# 3. Print the instance tree
tree = call_tool("get_instance_tree", {})
print(f"\n{tree}")
