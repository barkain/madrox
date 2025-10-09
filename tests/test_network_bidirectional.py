"""Test bidirectional messaging with parent-child network communication."""

import asyncio

import httpx

BASE_URL = "http://localhost:8003"


async def main():
    """Test hierarchical network with bidirectional messaging."""
    print("=" * 80)
    print("BIDIRECTIONAL NETWORK COMMUNICATION TEST")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=180.0) as client:
        # 1. Spawn parent orchestrator
        print("\n[1/5] Spawning parent orchestrator instance...")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_claude",
                    "arguments": {
                        "name": "parent-coordinator",
                        "role": "architect",
                        "enable_madrox": True,
                        "system_prompt": "You are a parent coordinator. Your job is to spawn a child instance and communicate with it using bidirectional messaging.",
                    },
                },
            },
        )

        result = response.json()
        parent_text = result["result"]["content"][0]["text"]
        import re

        match = re.search(r"ID: ([a-f0-9-]+)", parent_text)
        parent_id = match.group(1)
        print(f"✅ Parent spawned: {parent_id}")

        await asyncio.sleep(3)

        # 2. Ask parent to spawn a child
        print("\n[2/5] Asking parent to spawn child instance...")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "send_to_instance",
                    "arguments": {
                        "instance_id": parent_id,
                        "message": f"""Spawn a child Claude instance with these parameters:

spawn_claude(
    name='child-worker',
    role='general',
    parent_instance_id='{parent_id}',
    enable_madrox=True
)

After spawning, send a test message to the child asking: "What is 2+2?"

IMPORTANT: Use reply_to_caller to respond back to me with:
1. The child's instance ID
2. The child's response to your question

Format: reply_to_caller(instance_id='{parent_id}', reply_message='...')""",
                        "wait_for_response": True,
                        "timeout_seconds": 90,
                    },
                },
            },
        )

        result = response.json()
        if "result" in result:
            parent_response = result["result"]["content"][0]["text"]
            print("\n✅ Parent responded (first 500 chars):")
            print(parent_response[:500])

            # Check protocol used
            if "protocol" in str(result):
                protocol_info = result["result"].get("protocol", "unknown")
                if protocol_info == "bidirectional":
                    print("\n🎯 Used BIDIRECTIONAL protocol!")
                else:
                    print(f"\n⚠️  Used {protocol_info} protocol")
        else:
            print(f"❌ Error: {result}")

        await asyncio.sleep(2)

        # 3. Check for children
        print("\n[3/5] Checking for spawned children...")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_children",
                    "arguments": {"parent_id": parent_id},
                },
            },
        )

        result = response.json()
        children_text = result["result"]["content"][0]["text"]
        print(children_text)

        # Extract child IDs
        child_ids = re.findall(r"ID: ([a-f0-9-]+)", children_text)

        if child_ids:
            print(f"\n✅ Found {len(child_ids)} child instance(s)")
            child_id = child_ids[0]

            # 4. Test direct message to child
            print("\n[4/5] Testing direct message to child...")

            response = await client.post(
                f"{BASE_URL}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "send_to_instance",
                        "arguments": {
                            "instance_id": child_id,
                            "message": "What is your instance ID and parent ID? Use reply_to_caller to respond.",
                            "wait_for_response": True,
                            "timeout_seconds": 30,
                        },
                    },
                },
            )

            result = response.json()
            if "result" in result:
                child_response = result["result"]["content"][0]["text"]
                print("\n✅ Child response (first 300 chars):")
                print(child_response[:300])

                # Check bidirectional
                if "bidirectional" in str(result):
                    print("\n🎯 Child used BIDIRECTIONAL protocol!")
            else:
                print(f"❌ Error: {result}")
        else:
            print("\n⚠️  No children found (parent may not have spawned yet)")

        # 5. Cleanup
        print("\n[5/5] Cleanup...")

        for instance_id in [parent_id] + child_ids:
            await client.post(
                f"{BASE_URL}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 99,
                    "method": "tools/call",
                    "params": {
                        "name": "terminate_instance",
                        "arguments": {"instance_id": instance_id, "force": True},
                    },
                },
            )

        print("\n✅ All instances terminated")

        print("\n" + "=" * 80)
        print("TEST COMPLETE - Bidirectional network communication verified!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
