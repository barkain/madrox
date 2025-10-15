#!/usr/bin/env python3
"""Simple demo using direct HTTP requests."""

import requests
import json
import time

BASE_URL = "http://localhost:8001"

def spawn_claude(name: str, enable_madrox: bool = False) -> dict:
    """Spawn a Claude instance."""
    response = requests.post(f"{BASE_URL}/spawn", json={
        "name": name,
        "role": "general",
        "bypass_isolation": True,
        "enable_madrox": enable_madrox
    })
    return response.json()

def send_message(instance_id: str, message: str, wait: bool = True) -> dict:
    """Send message to instance."""
    response = requests.post(f"{BASE_URL}/send", json={
        "instance_id": instance_id,
        "message": message,
        "wait_for_response": wait,
        "timeout_seconds": 90
    })
    return response.json()

def get_output(instance_id: str) -> dict:
    """Get instance output."""
    response = requests.get(f"{BASE_URL}/output/{instance_id}?limit=20")
    return response.json()

def get_children(parent_id: str) -> dict:
    """Get child instances."""
    response = requests.get(f"{BASE_URL}/children/{parent_id}")
    return response.json()

print("🌍 Weather Discussion Demo: Claude Parent + Codex Child")
print("=" * 70)
print()

# Step 1: Spawn Claude parent
print("📍 Step 1: Spawning Claude parent with madrox enabled...")
parent = spawn_claude("weather-claude-parent", enable_madrox=True)
parent_id = parent["instance_id"]
print(f"✅ Parent spawned: {parent_id}")
print()

time.sleep(5)

# Step 2: Ask parent to spawn Codex child
print("📍 Step 2: Asking parent to spawn Codex child...")
spawn_request = """You have access to madrox MCP tools. Please:

1. Use spawn_codex to create a child instance with these parameters:
   - name: "codex-weather-child"
   - model: "gpt-5-codex"
   - bypass_isolation: true (allows command execution without approval)
   - enable_madrox: true (gives it access to madrox tools including reply_to_caller)

2. Send it this message: "What's the current weather like in Buenos Aires, Argentina? Include temperature and conditions. When done, use reply_to_caller to send your findings back to me."

3. Wait for its response using get_pending_replies and tell me what it said.

Use the madrox tools to do this."""

result = send_message(parent_id, spawn_request, wait=True)
print(f"✅ Request sent, status: {result.get('status')}")
if result.get('response'):
    print(f"📨 Parent's response:\n{result['response'][:400]}...")
print()

time.sleep(8)

# Step 3: Check for children
print("📍 Step 3: Checking for spawned children...")
children_resp = get_children(parent_id)
children = children_resp.get("children", [])
print(f"✅ Found {len(children)} child(ren)")
for child in children:
    print(f"   - {child['name']} ({child['instance_type']})")
print()

# Step 4: Get parent output
print("📍 Step 4: Retrieving parent's conversation...")
output = get_output(parent_id)
messages = output.get("messages", [])
print(f"📨 Last {min(3, len(messages))} messages:")
for msg in messages[-3:]:
    content = msg.get("content", "")
    print(f"\n{content[:500]}...")
print()

print("=" * 70)
print("✅ Demo completed!")

