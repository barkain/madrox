#!/usr/bin/env python3
"""Demo: Claude parent spawns Codex child to discuss Argentina's weather."""

import asyncio
import json
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def call_tool(session: ClientSession, tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool and return the result."""
    result = await session.call_tool(tool_name, arguments=arguments)
    return json.loads(result.content[0].text) if result.content else {}

async def main():
    """Run the demo."""
    # Connect to madrox HTTP server via MCP adapter
    server_params = StdioServerParameters(
        command="curl",
        args=[
            "-X", "POST",
            "http://localhost:8001/mcp/call_tool",
            "-H", "Content-Type: application/json",
            "-d", "@-"
        ]
    )
    
    print("🌍 Weather Discussion Demo: Claude Parent + Codex Child")
    print("=" * 60)
    print()
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Step 1: Spawn Claude parent
            print("📍 Step 1: Spawning Claude parent instance...")
            parent_result = await call_tool(session, "spawn_claude", {
                "name": "weather-expert-claude",
                "role": "general",
                "bypass_isolation": True,
                "enable_madrox": True
            })
            parent_id = parent_result.get("instance_id")
            print(f"✅ Claude parent spawned: {parent_id}")
            print()
            
            await asyncio.sleep(3)
            
            # Step 2: Ask parent to spawn Codex child
            print("📍 Step 2: Asking Claude parent to spawn Codex child...")
            spawn_message = """Please use the madrox MCP tools to spawn a Codex child instance named 'codex-weather-researcher'. 
            
Use these exact parameters:
- name: "codex-weather-researcher"
- model: "codex-1"
- bypass_isolation: true

After spawning, send it this message: "Research current weather conditions in Buenos Aires, Argentina. Include temperature, conditions, and any notable weather patterns."

Wait for the response and then reply back to me with what the Codex child found."""
            
            send_result = await call_tool(session, "send_to_instance", {
                "instance_id": parent_id,
                "message": spawn_message,
                "wait_for_response": True,
                "timeout_seconds": 120
            })
            print(f"✅ Parent received spawn request")
            print()
            
            await asyncio.sleep(5)
            
            # Step 3: Check parent's output
            print("📍 Step 3: Getting Claude parent's response...")
            output_result = await call_tool(session, "get_instance_output", {
                "instance_id": parent_id,
                "limit": 50
            })
            
            messages = output_result.get("messages", [])
            if messages:
                print(f"📨 Parent output ({len(messages)} messages):")
                for msg in messages[-5:]:  # Show last 5 messages
                    print(f"   [{msg.get('timestamp', 'N/A')}] {msg.get('content', '')[:200]}")
            print()
            
            # Step 4: Get list of children
            print("📍 Step 4: Checking for spawned children...")
            children_result = await call_tool(session, "get_children", {
                "parent_id": parent_id
            })
            children = children_result.get("children", [])
            print(f"✅ Found {len(children)} child instance(s)")
            for child in children:
                print(f"   - {child.get('name')} ({child.get('instance_id')}) - {child.get('instance_type')}")
            print()
            
            # Step 5: Test direct communication
            if children:
                child_id = children[0].get("instance_id")
                print(f"📍 Step 5: Sending follow-up to Codex child ({child_id})...")
                
                followup_result = await call_tool(session, "send_to_instance", {
                    "instance_id": child_id,
                    "message": "What's the seasonal context? Is this typical weather for this time of year in Argentina?",
                    "wait_for_response": True,
                    "timeout_seconds": 60
                })
                
                print(f"✅ Codex child response status: {followup_result.get('status')}")
                if followup_result.get("response"):
                    print(f"💬 Response preview: {followup_result.get('response')[:300]}...")
            
            print()
            print("=" * 60)
            print("✅ Demo completed!")
            print()
            print("Instance tree:")
            tree_result = await call_tool(session, "get_instance_tree", {})
            print(tree_result.get("tree", "No tree available"))

if __name__ == "__main__":
    asyncio.run(main())
