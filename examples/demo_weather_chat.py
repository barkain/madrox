#!/usr/bin/env python3
"""Demo: Claude + Codex multi-model team discussing weather.

Spawns a Claude parent and Codex child, sends each a task,
then shows the instance tree and terminal output.

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
    print()
    print("  Madrox Demo: Claude + Codex Weather Team")
    print("  " + "=" * 44)
    print()

    # 1. Spawn Claude parent
    print("  [1/5] Spawning Claude parent...")
    parent = call_tool(
        "spawn_claude",
        {"name": "weather-lead", "role": "general", "bypass_isolation": True},
    )
    parent_id = parent["instance_id"]
    print(f"        Claude: {parent['name']} ({parent_id[:8]}...)")

    # 2. Spawn Codex child
    print("  [2/5] Spawning Codex child...")
    child = call_tool(
        "spawn_codex",
        {"name": "weather-researcher", "bypass_isolation": True, "parent_instance_id": parent_id},
    )
    child_id = child["instance_id"]
    print(f"        Codex:  {child.get('name')} ({child_id[:8]}...)")
    print()

    # 3. Send tasks (fire-and-forget)
    print("  [3/5] Sending tasks...")
    call_tool(
        "send_to_instance",
        {
            "instance_id": child_id,
            "message": "What is the current weather in Buenos Aires, Argentina? Be concise.",
            "wait_for_response": False,
        },
    )
    print("        -> Codex: research Buenos Aires weather")

    call_tool(
        "send_to_instance",
        {
            "instance_id": parent_id,
            "message": "What should someone pack for a summer trip to Buenos Aires? Be concise.",
            "wait_for_response": False,
        },
    )
    print("        -> Claude: packing recommendations")
    print()

    # 4. Wait for instances to process
    print("  [4/5] Waiting 30s for responses...", end="", flush=True)
    for i in range(30):
        time.sleep(1)
        if (i + 1) % 5 == 0:
            print(f" {i + 1}s", end="", flush=True)
    print(" done")
    print()

    # 5. Show results
    print("  [5/5] Results")
    print("  " + "-" * 44)
    print()

    # Instance tree
    tree = call_tool("get_instance_tree", {})
    tree_str = tree if isinstance(tree, str) else str(tree)
    print("  Instance tree:")
    for line in tree_str.strip().split("\n"):
        print(f"    {line}")
    print()

    # Terminal output from each instance
    for name, iid in [
        ("Claude (weather-lead)", parent_id),
        ("Codex (weather-researcher)", child_id),
    ]:
        print(f"  Terminal — {name}:")
        print("  " + "." * 44)
        try:
            content = call_tool("get_tmux_pane_content", {"instance_id": iid, "lines": 30})
            text = content if isinstance(content, str) else str(content)
            # Show last 15 non-empty lines
            lines = [ln for ln in text.strip().split("\n") if ln.strip()]
            for line in lines[-15:]:
                print(f"    {line[:100]}")
        except Exception as e:
            print(f"    (error: {e})")
        print()

    print("  " + "=" * 44)
    print("  Done. Instances are still running.")
    print()


if __name__ == "__main__":
    main()
