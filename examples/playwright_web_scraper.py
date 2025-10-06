"""Example: Spawn a Claude instance with Playwright for web scraping."""

import asyncio
import httpx

BASE_URL = "http://localhost:8001"


async def main():
    """Spawn a web scraper instance with Playwright MCP."""
    print("=" * 80)
    print("PLAYWRIGHT WEB SCRAPER EXAMPLE")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=180.0) as client:
        # Spawn instance with Playwright MCP
        print("\n[1/2] Spawning web scraper with Playwright (headless)...")

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
                                "args": ["@playwright/mcp@latest"]
                            }
                        },
                        "system_prompt": "You are a web scraping specialist. Use Playwright to navigate websites, extract data, and analyze web content. Always work in headless mode for efficiency."
                    },
                },
            },
        )

        result = response.json()
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return

        instance_text = result["result"]["content"][0]["text"]
        import re
        match = re.search(r"ID: ([a-f0-9-]+)", instance_text)
        if not match:
            print(f"❌ Could not extract instance ID from: {instance_text}")
            return

        instance_id = match.group(1)
        print(f"✅ Spawned web scraper: {instance_id}")

        # Give it time to initialize and add MCP servers
        await asyncio.sleep(5)

        # Send a scraping task
        print(f"\n[2/2] Sending web scraping task...")

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
                        "message": """Navigate to https://example.com and extract:
1. The page title
2. All heading text (h1, h2, h3)
3. Any links on the page

Use your Playwright tools to accomplish this. Take a screenshot if helpful.""",
                        "wait_for_response": True,
                        "timeout_seconds": 60,
                    },
                },
            },
        )

        result = response.json()
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            response_text = result["result"]["content"][0]["text"]
            print(f"\n✅ Scraping result (first 1000 chars):")
            print(response_text[:1000])

        # Cleanup
        print(f"\n[Cleanup] Terminating instance...")
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
        print("\n" + "=" * 80)
        print("PLAYWRIGHT EXAMPLE COMPLETE")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
