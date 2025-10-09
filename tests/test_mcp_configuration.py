"""Test MCP server configuration for spawned instances."""

import asyncio

import httpx

BASE_URL = "http://localhost:8001"


async def test_1_empty_madrox():
    """Test 1: Spawn empty Madrox (no MCP servers) and check /mcp."""
    print("\n" + "=" * 80)
    print("TEST 1: Empty Madrox (enable_madrox=False)")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=180.0) as client:
        # Spawn instance without Madrox MCP
        print("\n[1/3] Spawning instance WITHOUT Madrox MCP...")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_claude",
                    "arguments": {
                        "name": "empty-instance",
                        "role": "general",
                        "enable_madrox": False,  # No Madrox
                        "mcp_servers": {},  # No additional servers
                    },
                },
            },
        )

        result = response.json()
        instance_text = result["result"]["content"][0]["text"]
        import re

        match = re.search(r"ID: ([a-f0-9-]+)", instance_text)
        instance_id = match.group(1)
        print(f"✅ Spawned: {instance_id}")

        # Wait for initialization
        await asyncio.sleep(5)

        # Ask it to run /mcp
        print("\n[2/3] Asking instance to run /mcp command...")

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
                        "message": "Run the /mcp command and show me what MCP servers you have configured.",
                        "wait_for_response": True,
                        "timeout_seconds": 30,
                    },
                },
            },
        )

        result = response.json()
        response_text = result["result"]["content"][0]["text"]
        print("\n📋 Instance response (first 500 chars):")
        print(response_text[:500])

        # Cleanup
        print("\n[3/3] Terminating instance...")
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
        print("✅ Instance terminated")


async def test_2_madrox_enabled():
    """Test 2: Spawn Madrox with enable_madrox=True and check /mcp."""
    print("\n" + "=" * 80)
    print("TEST 2: Madrox with enable_madrox=True")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=180.0) as client:
        # Spawn instance with Madrox MCP
        print("\n[1/3] Spawning instance WITH Madrox MCP...")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_claude",
                    "arguments": {
                        "name": "madrox-instance",
                        "role": "general",
                        "enable_madrox": True,  # Enable Madrox
                    },
                },
            },
        )

        result = response.json()
        instance_text = result["result"]["content"][0]["text"]
        import re

        match = re.search(r"ID: ([a-f0-9-]+)", instance_text)
        instance_id = match.group(1)
        print(f"✅ Spawned: {instance_id}")

        # Wait for initialization
        await asyncio.sleep(5)

        # Ask it to run /mcp
        print("\n[2/3] Asking instance to run /mcp command...")

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
                        "message": "Run the /mcp command and list all MCP servers you have access to. Show me the madrox server specifically.",
                        "wait_for_response": True,
                        "timeout_seconds": 30,
                    },
                },
            },
        )

        result = response.json()
        response_text = result["result"]["content"][0]["text"]
        print("\n📋 Instance response (first 800 chars):")
        print(response_text[:800])

        # Verify it has reply_to_caller tool
        print("\n[2.5/3] Checking if instance can see reply_to_caller tool...")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "send_to_instance",
                    "arguments": {
                        "instance_id": instance_id,
                        "message": "Search for 'reply_to_caller' in your available tools. Do you have this tool?",
                        "wait_for_response": True,
                        "timeout_seconds": 30,
                    },
                },
            },
        )

        result = response.json()
        response_text = result["result"]["content"][0]["text"]
        print("\n📋 Tool check response (first 500 chars):")
        print(response_text[:500])

        # Cleanup
        print("\n[3/3] Terminating instance...")
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
        print("✅ Instance terminated")


async def test_3_playwright_headless():
    """Test 3: Spawn with Playwright and do web interaction."""
    print("\n" + "=" * 80)
    print("TEST 3: Playwright Headless Browser Automation")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=240.0) as client:
        # Spawn instance with Playwright
        print("\n[1/4] Spawning instance with Playwright MCP (headless)...")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_claude",
                    "arguments": {
                        "name": "web-scraper",
                        "role": "data_analyst",
                        "enable_madrox": True,
                        "mcp_servers": {
                            "playwright": {
                                "transport": "stdio",
                                "command": "npx",
                                "args": ["@playwright/mcp@latest"],
                            }
                        },
                    },
                },
            },
        )

        result = response.json()
        instance_text = result["result"]["content"][0]["text"]
        import re

        match = re.search(r"ID: ([a-f0-9-]+)", instance_text)
        instance_id = match.group(1)
        print(f"✅ Spawned: {instance_id}")

        # Wait for initialization and MCP server setup
        print("\n[2/4] Waiting for Playwright initialization (10 seconds)...")
        await asyncio.sleep(10)

        # Check MCP servers
        print("\n[3/4] Checking configured MCP servers...")

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
                        "message": "Run /mcp and show me all configured MCP servers. List the playwright server specifically.",
                        "wait_for_response": True,
                        "timeout_seconds": 30,
                    },
                },
            },
        )

        result = response.json()
        response_text = result["result"]["content"][0]["text"]
        print("\n📋 MCP servers (first 600 chars):")
        print(response_text[:600])

        # Do web interaction
        print("\n[4/4] Performing web interaction with Playwright...")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "send_to_instance",
                    "arguments": {
                        "instance_id": instance_id,
                        "message": """Use your Playwright browser tools to:
1. Navigate to https://example.com
2. Extract the page title
3. Extract the main heading (h1)

Use the browser_navigate and browser_snapshot tools. Work in headless mode.""",
                        "wait_for_response": True,
                        "timeout_seconds": 60,
                    },
                },
            },
        )

        result = response.json()
        response_text = result["result"]["content"][0]["text"]
        print("\n📋 Web scraping result (first 1000 chars):")
        print(response_text[:1000])

        # Cleanup
        print("\n[Cleanup] Terminating instance...")
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
        print("✅ Instance terminated")


async def main():
    """Run all three tests."""
    print("\n" + "=" * 80)
    print("MCP CONFIGURATION INTEGRATION TESTS")
    print("=" * 80)

    try:
        await test_1_empty_madrox()
        await asyncio.sleep(2)

        await test_2_madrox_enabled()
        await asyncio.sleep(2)

        await test_3_playwright_headless()

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
