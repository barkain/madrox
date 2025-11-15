#!/usr/bin/env python3
"""Quick test to verify all 27 tools are registered in STDIO mode."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.orchestrator.mcp_server import OrchestrationMCPServer
from src.orchestrator.simple_models import OrchestratorConfig


async def test_tool_registration():
    """Test that all 27 tools are properly registered."""
    print("🧪 Testing STDIO tool registration...")
    print()

    # Create a minimal config for testing
    config = OrchestratorConfig(
        workspace_base_dir="/tmp/test_madrox_workspace",
        log_dir="/tmp/test_madrox_logs",
        log_level="INFO",
    )

    # Create the MCP server
    print("📦 Creating OrchestrationMCPServer...")
    server = OrchestrationMCPServer(config)

    # Get the list of registered tools
    print("🔍 Checking registered tools...")
    tools = await server.mcp.get_tools()

    print(f"\n✅ SUCCESS! Registered {len(tools)} tools")
    print()
    print("📋 Tool List:")
    for i, tool_name in enumerate(sorted(tools.keys()), 1):
        print(f"  {i:2d}. {tool_name}")

    # Expected count
    expected_count = 27
    if len(tools) == expected_count:
        print(f"\n✅ PASSED: All {expected_count} tools registered correctly!")
        return True
    else:
        print(f"\n❌ FAILED: Expected {expected_count} tools, got {len(tools)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_tool_registration())
    sys.exit(0 if success else 1)
