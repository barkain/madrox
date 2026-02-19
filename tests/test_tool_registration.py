#!/usr/bin/env python3
"""Quick test to verify all 28 tools are registered in STDIO proxy mode."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from orchestrator.mcp_server import OrchestrationMCPServer


async def test_tool_registration():
    """Test that all 28 tools are properly registered."""
    print("Testing STDIO proxy tool registration...")
    print()

    # Create the proxy MCP server (no InstanceManager needed)
    print("Creating OrchestrationMCPServer proxy...")
    server = OrchestrationMCPServer(parent_url="http://localhost:8001")

    # Get the list of registered tools
    print("Checking registered tools...")
    tools = await server.mcp.get_tools()

    print(f"\nRegistered {len(tools)} tools")
    print()
    print("Tool List:")
    for i, tool_name in enumerate(sorted(tools.keys()), 1):
        print(f"  {i:2d}. {tool_name}")

    expected_count = 28
    if len(tools) == expected_count:
        print(f"\nPASSED: All {expected_count} tools registered correctly!")
        return True
    else:
        print(f"\nFAILED: Expected {expected_count} tools, got {len(tools)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_tool_registration())
    sys.exit(0 if success else 1)
