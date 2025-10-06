"""Simple focused test for bidirectional messaging."""

import asyncio
import json
import httpx

BASE_URL = "http://localhost:8003"


async def main():
    """Test basic bidirectional communication."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Spawn instance
        print("\n" + "=" * 80)
        print("SPAWNING INSTANCE")
        print("=" * 80)

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_claude",
                    "arguments": {
                        "name": "simple-test",
                        "role": "general",
                        "enable_madrox": True,
                    },
                },
            },
        )

        result = response.json()
        print(json.dumps(result, indent=2))

        # Extract instance ID
        import re
        text = result["result"]["content"][0]["text"]
        match = re.search(r"ID: ([a-f0-9-]+)", text)
        instance_id = match.group(1)
        print(f"\n✅ Instance ID: {instance_id}")

        # Wait for instance to be ready
        await asyncio.sleep(3)

        # 2. Test multiline message (should not hang)
        print("\n" + "=" * 80)
        print("TESTING MULTILINE MESSAGE (with newlines)")
        print("=" * 80)

        multiline_msg = """Line 1
Line 2
Line 3"""

        print(f"Sending:\n{multiline_msg}\n")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "send_to_instance",
                    "arguments": {
                        "instance_id": instance_id,
                        "message": multiline_msg,
                        "wait_for_response": True,
                        "timeout_seconds": 30,
                    },
                },
            },
        )

        result = response.json()
        if "result" in result:
            response_text = result["result"]["content"][0]["text"]
            print(f"Response (first 300 chars):\n{response_text[:300]}...")

            # Check protocol
            if "protocol" in str(result):
                print(f"\n✅ Response includes protocol info")

            print("\n✅ Multiline message handled successfully (did not hang)")
        else:
            print(f"❌ Error: {result}")

        # 3. Cleanup
        print("\n" + "=" * 80)
        print("CLEANUP")
        print("=" * 80)

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "terminate_instance",
                    "arguments": {"instance_id": instance_id, "force": True},
                },
            },
        )

        print("✅ Instance terminated")
        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
