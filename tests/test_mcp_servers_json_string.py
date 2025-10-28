"""Test MCP servers parameter as JSON string.

This test verifies that the spawn_claude and spawn_codex tools accept
mcp_servers as a JSON string parameter, which solves the MCP protocol
limitation that prevents passing nested dictionaries.
"""

import asyncio
import json

import httpx
import pytest

BASE_URL = "http://localhost:8001"


@pytest.mark.asyncio
async def test_spawn_claude_with_json_string_mcp_servers():
    """Test spawning Claude instance with mcp_servers as JSON string.

    This test verifies:
    1. The spawn_claude tool accepts mcp_servers as a JSON string
    2. The JSON string is parsed correctly by TmuxInstanceManager
    3. The MCP servers are configured in the spawned instance
    """
    print("\n" + "=" * 80)
    print("TEST: Spawn Claude with JSON string mcp_servers parameter")
    print("=" * 80)

    # Mock MCP server configuration
    mcp_servers_config = {"test_server": {"transport": "http", "url": "http://localhost:9999/mcp"}}

    # Convert to JSON string (simulating what MCP protocol does)
    mcp_servers_json = json.dumps(mcp_servers_config)

    async with httpx.AsyncClient(timeout=180.0) as client:
        print("\n[1/4] Spawning Claude instance with JSON string mcp_servers...")
        print(f"mcp_servers JSON: {mcp_servers_json}")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_claude",
                    "arguments": {
                        "name": "json-string-test",
                        "role": "general",
                        "mcp_servers": mcp_servers_json,  # Pass as JSON string
                    },
                },
            },
        )

        result = response.json()
        assert "result" in result, f"Expected result, got: {result}"

        # Extract instance ID from response
        instance_text = result["result"]["content"][0]["text"]
        import re

        match = re.search(r"ID: ([a-f0-9-]+)", instance_text)
        assert match, f"Could not find instance ID in response: {instance_text}"
        instance_id = match.group(1)
        print(f"✅ Spawned: {instance_id}")

        # Wait for initialization
        print("\n[2/4] Waiting for instance initialization (5s)...")
        await asyncio.sleep(5)

        # Check instance status to verify mcp_servers was parsed
        print("\n[3/4] Checking instance status...")
        response = await client.get(f"{BASE_URL}/instances/{instance_id}/status")
        assert response.status_code == 200

        instance_status = response.json()
        print(f"Instance state: {instance_status.get('state')}")

        # Verify mcp_servers was parsed from JSON string to dict
        mcp_servers = instance_status.get("mcp_servers", {})
        print(f"MCP servers configured: {list(mcp_servers.keys())}")

        # Should have both Madrox (auto-added) and test_server
        assert isinstance(mcp_servers, dict), f"mcp_servers should be dict, got {type(mcp_servers)}"
        assert "madrox" in mcp_servers, "Madrox should be auto-added"
        assert "test_server" in mcp_servers, "test_server should be present"
        assert mcp_servers["test_server"]["url"] == "http://localhost:9999/mcp"

        print("✅ JSON string was correctly parsed to dictionary")
        print(f"✅ Configured MCP servers: {list(mcp_servers.keys())}")

        # Cleanup
        print("\n[4/4] Terminating instance...")
        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "terminate_instance",
                    "arguments": {
                        "instance_id": instance_id,
                        "force": True,
                    },
                },
            },
        )
        print("✅ Instance terminated")


@pytest.mark.asyncio
async def test_spawn_claude_with_empty_string_mcp_servers():
    """Test that empty JSON string defaults to empty dict."""
    print("\n" + "=" * 80)
    print("TEST: Spawn Claude with empty string mcp_servers")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=180.0) as client:
        print("\n[1/3] Spawning Claude instance with empty mcp_servers string...")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_claude",
                    "arguments": {
                        "name": "empty-string-test",
                        "role": "general",
                        "mcp_servers": "",  # Empty string
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

        await asyncio.sleep(5)

        # Check that it defaults to empty dict (only Madrox present)
        print("\n[2/3] Checking instance has only Madrox...")
        response = await client.get(f"{BASE_URL}/instances/{instance_id}/status")
        instance_status = response.json()

        mcp_servers = instance_status.get("mcp_servers", {})
        print(f"MCP servers: {list(mcp_servers.keys())}")

        assert isinstance(mcp_servers, dict)
        assert "madrox" in mcp_servers
        assert len(mcp_servers) == 1  # Only Madrox

        print("✅ Empty string correctly handled as empty dict")

        # Cleanup
        print("\n[3/3] Terminating instance...")
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


@pytest.mark.asyncio
async def test_spawn_claude_with_invalid_json_mcp_servers():
    """Test that invalid JSON string is handled gracefully."""
    print("\n" + "=" * 80)
    print("TEST: Spawn Claude with invalid JSON mcp_servers")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=180.0) as client:
        print("\n[1/3] Spawning Claude instance with invalid JSON...")

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_claude",
                    "arguments": {
                        "name": "invalid-json-test",
                        "role": "general",
                        "mcp_servers": "{invalid json}",  # Invalid JSON
                    },
                },
            },
        )

        result = response.json()
        instance_text = result["result"]["content"][0]["text"]
        import re

        match = re.search(r"ID: ([a-f0-9-]+)", instance_text)
        instance_id = match.group(1)
        print(f"✅ Spawned: {instance_id} (despite invalid JSON)")

        await asyncio.sleep(5)

        # Check that it falls back to empty dict
        print("\n[2/3] Checking instance falls back to empty dict...")
        response = await client.get(f"{BASE_URL}/instances/{instance_id}/status")
        instance_status = response.json()

        mcp_servers = instance_status.get("mcp_servers", {})
        print(f"MCP servers: {list(mcp_servers.keys())}")

        assert isinstance(mcp_servers, dict)
        assert "madrox" in mcp_servers
        assert len(mcp_servers) == 1  # Only Madrox (invalid JSON ignored)

        print("✅ Invalid JSON correctly handled as empty dict")

        # Cleanup
        print("\n[3/3] Terminating instance...")
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


if __name__ == "__main__":
    """Run tests manually without pytest."""
    import sys

    print("\n" + "=" * 80)
    print("Running MCP Servers JSON String Tests")
    print("=" * 80)
    print("\nThese tests verify that spawn_claude accepts mcp_servers as a JSON string,")
    print("solving the MCP protocol limitation that prevents nested dictionaries.")
    print("\nStarting tests...")

    try:
        asyncio.run(test_spawn_claude_with_json_string_mcp_servers())
        asyncio.run(test_spawn_claude_with_empty_string_mcp_servers())
        asyncio.run(test_spawn_claude_with_invalid_json_mcp_servers())

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ TEST FAILED")
        print("=" * 80)
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
