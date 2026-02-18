#!/usr/bin/env python3
"""Simple demo: spawn a Claude instance and send it a task.

Prerequisites:
    ./start.sh --be      # start Madrox backend on :8001

Usage:
    uv run python examples/demo_simple.py
"""

import time

import requests

URL = "http://localhost:8001"


def call_tool(tool_name: str, args: dict) -> dict:
    """Execute an MCP tool via the REST API."""
    resp = requests.post(f"{URL}/tools/execute", json={"tool": tool_name, "arguments": args})
    resp.raise_for_status()
    return resp.json()


print("🌍 Weather Discussion Demo: Claude Parent + Codex Child")
print("=" * 70)
print()

# Step 1: Spawn Claude parent
print("📍 Step 1: Spawning Claude parent...")
parent = call_tool(
    "spawn_claude",
    {
        "name": "weather-claude-parent",
        "role": "general",
        "bypass_isolation": True,
    },
)
parent_id = parent["instance_id"]
print(f"   ✅ Parent spawned: {parent_id}")
print()

time.sleep(5)

# Step 2: Ask parent to spawn Codex child
print("📍 Step 2: Asking parent to spawn Codex child...")
spawn_request = (
    "You have access to madrox MCP tools. Please:\n\n"
    "1. Use spawn_codex to create a child instance with these parameters:\n"
    '   - name: "codex-weather-child"\n'
    "   - bypass_isolation: true\n\n"
    "2. Send it this message: \"What's the current weather like in Buenos Aires, "
    "Argentina? Include temperature and conditions. When done, use reply_to_caller "
    'to send your findings back to me."\n\n'
    "3. Wait for its response using get_pending_replies and tell me what it said.\n\n"
    "Use the madrox tools to do this."
)

result = call_tool(
    "send_to_instance",
    {
        "instance_id": parent_id,
        "message": spawn_request,
        "wait_for_response": True,
        "timeout_seconds": 120,
    },
)
print(f"   ✅ Request sent, status: {result.get('status')}")
if result.get("response"):
    print(f"   📨 Parent's response:\n{result['response'][:400]}...")
print()

time.sleep(8)

# Step 3: Check for children
print("📍 Step 3: Checking for spawned children...")
children_resp = call_tool("get_children", {"parent_id": parent_id})
children = children_resp.get("children", [])
print(f"   ✅ Found {len(children)} child(ren)")
for child in children:
    print(f"      - {child['name']} ({child['instance_type']})")
print()

# Step 4: Print instance tree
print("📍 Step 4: Instance tree")
tree = call_tool("get_instance_tree", {})
print(tree.get("tree", "No tree available"))
print()

print("=" * 70)
print("✅ Demo completed!")
