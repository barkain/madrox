"""Example: Spawning Claude instances with MCP servers using JSON string parameter.

This example demonstrates how to pass MCP server configurations to spawned
instances using the JSON string format, which solves the MCP protocol limitation
that prevents passing nested dictionaries.
"""

import asyncio
import json

import httpx

BASE_URL = "http://localhost:8001"


async def example_single_http_server():
    """Example 1: Spawn instance with single HTTP MCP server."""
    print("\n" + "=" * 80)
    print("Example 1: Single HTTP MCP Server")
    print("=" * 80)

    # Configure Armando MCP server
    mcp_config = {"armando": {"transport": "http", "url": "http://localhost:8002/mcp"}}

    # Convert to JSON string (required by MCP protocol)
    mcp_json = json.dumps(mcp_config)

    async with httpx.AsyncClient(timeout=180.0) as client:
        print("\nSpawning instance with Armando MCP server...")
        print(f"Config: {mcp_json}")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_claude",
                    "arguments": {
                        "name": "armando-enabled-agent",
                        "role": "general",
                        "mcp_servers": mcp_json,
                    },
                },
            },
        )

        result = response.json()
        instance_text = result["result"]["content"][0]["text"]

        # Extract instance ID
        import re

        match = re.search(r"ID: ([a-f0-9-]+)", instance_text)
        instance_id = match.group(1)

        print(f"✅ Spawned instance: {instance_id}")

        # Wait for initialization
        await asyncio.sleep(5)

        # Verify MCP servers
        print("\nVerifying MCP server configuration...")
        status_response = await client.get(f"{BASE_URL}/instances/{instance_id}/status")
        status = status_response.json()

        mcp_servers = status.get("mcp_servers", {})
        print(f"Configured MCP servers: {list(mcp_servers.keys())}")
        print("✅ Both Madrox (auto-added) and Armando are configured")

        # Cleanup
        print("\nCleaning up...")
        await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "terminate_instance",
                    "arguments": {"instance_id": instance_id, "force": True},
                },
            },
        )
        print("✅ Instance terminated")


async def example_multiple_servers():
    """Example 2: Spawn instance with multiple MCP servers."""
    print("\n" + "=" * 80)
    print("Example 2: Multiple MCP Servers")
    print("=" * 80)

    # Configure multiple MCP servers
    mcp_config = {
        "armando": {"transport": "http", "url": "http://localhost:8002/mcp"},
        "playwright": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@playwright/mcp-server"],
        },
    }

    mcp_json = json.dumps(mcp_config)

    async with httpx.AsyncClient(timeout=180.0) as client:
        print("\nSpawning instance with multiple MCP servers...")
        print(f"Config: {json.dumps(mcp_config, indent=2)}")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_claude",
                    "arguments": {
                        "name": "multi-mcp-agent",
                        "role": "general",
                        "mcp_servers": mcp_json,
                    },
                },
            },
        )

        result = response.json()
        instance_text = result["result"]["content"][0]["text"]

        import re

        match = re.search(r"ID: ([a-f0-9-]+)", instance_text)
        instance_id = match.group(1)

        print(f"✅ Spawned instance: {instance_id}")

        await asyncio.sleep(5)

        # Verify configuration
        print("\nVerifying MCP server configuration...")
        status_response = await client.get(f"{BASE_URL}/instances/{instance_id}/status")
        status = status_response.json()

        mcp_servers = status.get("mcp_servers", {})
        print(f"Configured MCP servers: {list(mcp_servers.keys())}")
        print("✅ Madrox, Armando, and Playwright are all configured")

        # Cleanup
        print("\nCleaning up...")
        await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "terminate_instance",
                    "arguments": {"instance_id": instance_id, "force": True},
                },
            },
        )
        print("✅ Instance terminated")


async def example_codex_with_mcp_servers():
    """Example 3: Spawn Codex instance with MCP servers."""
    print("\n" + "=" * 80)
    print("Example 3: Codex with MCP Servers")
    print("=" * 80)

    mcp_config = {"armando": {"transport": "http", "url": "http://localhost:8002/mcp"}}

    mcp_json = json.dumps(mcp_config)

    async with httpx.AsyncClient(timeout=180.0) as client:
        print("\nSpawning Codex instance with Armando MCP...")
        print(f"Config: {mcp_json}")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_codex",
                    "arguments": {
                        "name": "codex-with-armando",
                        "model": "gpt-5-codex",
                        "sandbox_mode": "workspace-write",
                        "mcp_servers": mcp_json,
                    },
                },
            },
        )

        result = response.json()
        instance_text = result["result"]["content"][0]["text"]

        import re

        match = re.search(r"ID: ([a-f0-9-]+)", instance_text)
        instance_id = match.group(1)

        print(f"✅ Spawned Codex instance: {instance_id}")

        await asyncio.sleep(5)

        # Verify configuration
        print("\nVerifying MCP server configuration...")
        status_response = await client.get(f"{BASE_URL}/instances/{instance_id}/status")
        status = status_response.json()

        mcp_servers = status.get("mcp_servers", {})
        print(f"Configured MCP servers: {list(mcp_servers.keys())}")
        print("✅ Madrox and Armando configured for Codex")

        # Cleanup
        print("\nCleaning up...")
        await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "terminate_instance",
                    "arguments": {"instance_id": instance_id, "force": True},
                },
            },
        )
        print("✅ Instance terminated")


async def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("MCP Servers JSON String Parameter Examples")
    print("=" * 80)
    print(
        "\nThese examples demonstrate how to pass MCP server configurations"
        "\nto spawned instances using JSON string format."
    )
    print("\nMake sure Madrox orchestrator is running on http://localhost:8001")
    print("Optional: Start Armando MCP on http://localhost:8002 to see HTTP examples")

    try:
        # Example 1: Single HTTP server
        await example_single_http_server()

        # Example 2: Multiple servers
        await example_multiple_servers()

        # Example 3: Codex with MCP servers
        await example_codex_with_mcp_servers()

        print("\n" + "=" * 80)
        print("✅ All examples completed successfully")
        print("=" * 80)

    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ Example failed")
        print("=" * 80)
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
