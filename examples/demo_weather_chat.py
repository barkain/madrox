#!/usr/bin/env python3
"""Demo: Spawn two Claude instances that discuss Argentina's weather.

This demo shows Madrox's core capabilities:
  1. Spawning instances via the REST API
  2. Sending messages and waiting for responses
  3. Parent-child hierarchy (parent spawns child via MCP tools)
  4. Direct messaging to any instance
  5. Viewing the instance tree

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
    if not resp.ok:
        print(f"   ERROR [{resp.status_code}]: {resp.text}")
    resp.raise_for_status()
    return resp.json()


def main():
    print("🌍 Weather Discussion Demo")
    print("=" * 60)
    print()

    # Step 1: Spawn a Claude parent with Madrox tools
    print("📍 Step 1: Spawning Claude parent (with Madrox tools)...")
    parent = call_tool(
        "spawn_claude",
        {
            "name": "weather-lead",
            "role": "general",
            "bypass_isolation": True,
            "enable_madrox": True,
        },
    )
    parent_id = parent["instance_id"]
    print(f"   ✅ Spawned: {parent['name']} ({parent_id[:8]}...)")
    print()
    time.sleep(3)

    # Step 2: Spawn a second Claude as a child researcher
    print("📍 Step 2: Spawning child researcher...")
    child = call_tool(
        "spawn_claude",
        {
            "name": "weather-researcher",
            "role": "general",
            "bypass_isolation": True,
            "parent_instance_id": parent_id,
        },
    )
    child_id = child["instance_id"]
    print(f"   ✅ Spawned: {child['name']} ({child_id[:8]}...)")
    print()
    time.sleep(3)

    # Step 3: Send research task to child
    print("📍 Step 3: Sending research task to child...")
    research_result = call_tool(
        "send_to_instance",
        {
            "instance_id": child_id,
            "message": (
                "Research current weather conditions in Buenos Aires, Argentina. "
                "Include temperature, conditions, and any notable weather patterns. "
                "Be concise — 3-4 sentences max."
            ),
            "wait_for_response": True,
            "timeout_seconds": 90,
        },
    )
    response_text = research_result.get("response", "")
    if isinstance(response_text, dict):
        response_text = response_text.get("response", str(response_text))
    print(f"   ✅ Child responded (success: {research_result.get('success')})")
    if response_text:
        print(f"   📨 {response_text[:500]}")
    print()

    # Step 4: Ask parent to analyze the findings
    print("📍 Step 4: Asking parent to analyze...")
    analysis_prompt = (
        f"Your researcher found this about Buenos Aires weather:\n\n"
        f"{response_text[:800] if response_text else '(no response yet)'}\n\n"
        f"Based on this, what would you recommend someone pack for a trip "
        f"to Buenos Aires this week? Be concise — 3-4 sentences."
    )
    analysis_result = call_tool(
        "send_to_instance",
        {
            "instance_id": parent_id,
            "message": analysis_prompt,
            "wait_for_response": True,
            "timeout_seconds": 90,
        },
    )
    analysis_text = analysis_result.get("response", "")
    if isinstance(analysis_text, dict):
        analysis_text = analysis_text.get("response", str(analysis_text))
    print(f"   ✅ Parent responded (success: {analysis_result.get('success')})")
    if analysis_text:
        print(f"   📨 {analysis_text[:500]}")
    print()

    # Step 5: Show the instance tree
    print("📍 Step 5: Instance tree")
    tree = call_tool("get_instance_tree", {})
    print(f"   {tree}" if isinstance(tree, str) else f"   {tree}")
    print()

    # Step 6: Show children of parent
    print("📍 Step 6: Children of parent")
    children = call_tool("get_children", {"parent_id": parent_id})
    print(f"   Found {len(children)} child(ren)")
    for c in children:
        print(f"      - {c.get('name')} ({c.get('id', '')[:8]}...) [{c.get('state')}]")
    print()

    print("=" * 60)
    print("✅ Demo completed! Instances are still running.")
    print(f"   Terminate with: curl -X POST {URL}/tools/execute \\")
    print('     -H "Content-Type: application/json" \\')
    print(
        f'     -d \'{{"tool":"terminate_instance","arguments":{{"instance_id":"{parent_id}"}}}}\''
    )


if __name__ == "__main__":
    main()
