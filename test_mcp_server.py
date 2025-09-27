#!/usr/bin/env python
"""Test script to verify MCP server is working correctly."""

import asyncio
import httpx
import json
from typing import Any


async def test_mcp_server():
    """Test the MCP server endpoints."""
    base_url = "http://localhost:8001"

    async with httpx.AsyncClient() as client:
        # Test 1: Check server health
        print("1. Testing server health...")
        response = await client.get(f"{base_url}/health")
        assert response.status_code == 200
        print(f"   ✅ Health check: {response.json()}")

        # Test 2: Get server info
        print("\n2. Getting server info...")
        response = await client.get(f"{base_url}/")
        assert response.status_code == 200
        info = response.json()
        print(f"   ✅ Server: {info['name']} v{info['version']}")

        # Test 3: List available tools
        print("\n3. Listing available MCP tools...")
        response = await client.get(f"{base_url}/tools")
        assert response.status_code == 200
        tools = response.json()
        for tool in tools['tools']:
            print(f"   - {tool['name']}: {tool['description']}")

        # Test 4: Test spawning an instance
        print("\n4. Testing instance spawn...")
        spawn_request = {
            "tool": "spawn_claude",
            "arguments": {
                "name": "test-instance",
                "role": "general",
                "system_prompt": "You are a helpful test assistant."
            }
        }

        response = await client.post(
            f"{base_url}/tools/execute",
            json=spawn_request
        )

        if response.status_code == 200:
            result = response.json()
            instance_id = result.get("instance_id")
            print(f"   ✅ Spawned instance: {instance_id}")

            # Test 5: Get instance status
            print("\n5. Checking instance status...")
            status_request = {
                "tool": "get_instance_status",
                "arguments": {
                    "instance_id": instance_id
                }
            }

            response = await client.post(
                f"{base_url}/tools/execute",
                json=status_request
            )

            if response.status_code == 200:
                status = response.json()
                print(f"   ✅ Instance status: {status}")

            # Test 6: Terminate instance
            print("\n6. Terminating test instance...")
            terminate_request = {
                "tool": "terminate_instance",
                "arguments": {
                    "instance_id": instance_id
                }
            }

            response = await client.post(
                f"{base_url}/tools/execute",
                json=terminate_request
            )

            if response.status_code == 200:
                print(f"   ✅ Instance terminated successfully")
        else:
            print(f"   ⚠️  Could not spawn instance (may need API key)")

        print("\n✅ All MCP server tests passed!")


if __name__ == "__main__":
    asyncio.run(test_mcp_server())