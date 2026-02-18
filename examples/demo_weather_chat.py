#!/usr/bin/env python3
"""Demo: Claude parent + Codex child discuss Argentina's weather.

Shows Madrox's multi-model orchestration:
  1. Spawn a Claude instance as the team lead
  2. Spawn a Codex instance as a child researcher
  3. Send the Codex child a research task
  4. Forward findings to the Claude parent for analysis
  5. View the mixed-model instance tree

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


def extract_response(result: dict) -> str:
    """Extract the response text from a send_to_instance result."""
    response = result.get("response", "")
    if isinstance(response, dict):
        return response.get("response", str(response))
    return str(response) if response else ""


def main():
    print("🌍 Weather Discussion Demo: Claude + Codex")
    print("=" * 60)
    print()

    # Step 1: Spawn Claude parent with Madrox tools
    print("📍 Step 1: Spawning Claude parent (team lead)...")
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
    print(f"   ✅ Claude: {parent['name']} ({parent_id[:8]}...)")
    print()
    time.sleep(3)

    # Step 2: Spawn Codex child researcher
    print("📍 Step 2: Spawning Codex child (researcher)...")
    child = call_tool(
        "spawn_codex",
        {
            "name": "weather-researcher",
            "bypass_isolation": True,
            "parent_instance_id": parent_id,
        },
    )
    child_id = child["instance_id"]
    print(f"   ✅ Codex: {child.get('name', 'weather-researcher')} ({child_id[:8]}...)")
    print()
    time.sleep(5)

    # Step 3: Send research task to Codex child
    print("📍 Step 3: Sending research task to Codex child...")
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
    research_text = extract_response(research_result)
    print(f"   ✅ Codex responded (success: {research_result.get('success')})")
    if research_text:
        print(f"   📨 {research_text[:500]}")
    print()

    # Step 4: Forward findings to Claude parent for analysis
    print("📍 Step 4: Asking Claude parent to analyze...")
    analysis_result = call_tool(
        "send_to_instance",
        {
            "instance_id": parent_id,
            "message": (
                f"Your Codex researcher found this about Buenos Aires weather:\n\n"
                f"{research_text[:800] if research_text else '(no response yet)'}\n\n"
                f"Based on this, what would you recommend someone pack for a trip "
                f"to Buenos Aires this week? Be concise — 3-4 sentences."
            ),
            "wait_for_response": True,
            "timeout_seconds": 90,
        },
    )
    analysis_text = extract_response(analysis_result)
    print(f"   ✅ Claude responded (success: {analysis_result.get('success')})")
    if analysis_text:
        print(f"   📨 {analysis_text[:500]}")
    print()

    # Step 5: Show the mixed-model instance tree
    print("📍 Step 5: Instance tree")
    tree = call_tool("get_instance_tree", {})
    print(f"   {tree}" if isinstance(tree, str) else f"   {tree}")
    print()

    # Step 6: Show children of parent
    print("📍 Step 6: Children of Claude parent")
    children = call_tool("get_children", {"parent_id": parent_id})
    print(f"   Found {len(children)} child(ren)")
    for c in children:
        print(
            f"      - {c.get('name')} ({c.get('id', '')[:8]}...) "
            f"[{c.get('instance_type')}] [{c.get('state')}]"
        )
    print()

    print("=" * 60)
    print("✅ Demo completed! Claude + Codex team is still running.")


if __name__ == "__main__":
    main()
