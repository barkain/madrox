#!/usr/bin/env python3
"""Demo: Claude parent spawns Codex child to discuss Argentina's weather.

Prerequisites:
    ./start.sh --be      # start Madrox backend on :8001

Usage:
    uv run python examples/demo_weather_chat.py
"""

import time

import requests

URL = "http://localhost:8001"


def call_tool(tool_name: str, args: dict) -> dict:
    """Execute an MCP tool via the REST API."""
    resp = requests.post(f"{URL}/tools/execute", json={"tool": tool_name, "arguments": args})
    resp.raise_for_status()
    return resp.json()


def main():
    print("🌍 Weather Discussion Demo: Claude Parent + Codex Child")
    print("=" * 60)
    print()

    # Step 1: Spawn Claude parent
    print("📍 Step 1: Spawning Claude parent instance...")
    parent_result = call_tool(
        "spawn_claude",
        {
            "name": "weather-expert-claude",
            "role": "general",
            "bypass_isolation": True,
            "enable_madrox": True,
        },
    )
    parent_id = parent_result.get("instance_id")
    print(f"   ✅ Claude parent spawned: {parent_id}")
    print()

    time.sleep(3)

    # Step 2: Ask parent to spawn Codex child and research weather
    print("📍 Step 2: Asking Claude parent to spawn Codex child...")
    spawn_message = (
        "You have access to madrox MCP tools. Please:\n\n"
        '1. Use spawn_codex to create a child instance named "codex-weather-researcher" '
        "with bypass_isolation: true\n"
        '2. Send it this message: "Research current weather conditions in Buenos Aires, '
        "Argentina. Include temperature, conditions, and any notable weather patterns. "
        'When done, use reply_to_caller to send your findings back to me."\n'
        "3. Wait for its response using get_pending_replies and tell me what it said."
    )

    send_result = call_tool(
        "send_to_instance",
        {
            "instance_id": parent_id,
            "message": spawn_message,
            "wait_for_response": True,
            "timeout_seconds": 120,
        },
    )
    print(f"   ✅ Parent responded (status: {send_result.get('status')})")
    if send_result.get("response"):
        preview = send_result["response"][:400]
        print(f"   📨 Response preview: {preview}...")
    print()

    # Step 3: Check for spawned children
    print("📍 Step 3: Checking for spawned children...")
    children_result = call_tool("get_children", {"parent_id": parent_id})
    children = children_result.get("children", [])
    print(f"   ✅ Found {len(children)} child instance(s)")
    for child in children:
        print(
            f"      - {child.get('name')} ({child.get('instance_id')}) [{child.get('instance_type')}]"
        )
    print()

    # Step 4: Send follow-up to Codex child directly
    if children:
        child_id = children[0].get("instance_id")
        print(f"📍 Step 4: Sending follow-up to Codex child ({child_id[:8]}...)...")

        followup_result = call_tool(
            "send_to_instance",
            {
                "instance_id": child_id,
                "message": "What's the seasonal context? Is this typical weather for this time of year in Argentina?",
                "wait_for_response": True,
                "timeout_seconds": 60,
            },
        )

        print(f"   ✅ Codex child response status: {followup_result.get('status')}")
        if followup_result.get("response"):
            print(f"   💬 Response: {followup_result['response'][:300]}...")
    print()

    # Step 5: Print instance tree
    print("📍 Step 5: Instance tree")
    tree_result = call_tool("get_instance_tree", {})
    print(tree_result.get("tree", "No tree available"))
    print()

    print("=" * 60)
    print("✅ Demo completed!")


if __name__ == "__main__":
    main()
