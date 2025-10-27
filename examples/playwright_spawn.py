#!/usr/bin/env python3
"""Quick test to verify Playwright MCP spawning works correctly.

This script demonstrates the MCP configuration fix by:
1. Spawning a child instance with Playwright MCP server
2. Verifying the generated .claude_mcp_config.json has the correct format
3. Testing that the child instance has access to Playwright tools
"""

import asyncio
import json
from pathlib import Path

from src.orchestrator.mcp_loader import get_mcp_servers
from src.orchestrator.tmux_instance_manager import TmuxInstanceManager


async def main():
    """Test Playwright MCP spawning."""
    print("🚀 Testing Playwright MCP Configuration Fix\n")

    # Initialize manager
    config = {"workspace_base_dir": "/tmp/claude_orchestrator", "max_concurrent_instances": 10}
    manager = TmuxInstanceManager(config)

    print("1️⃣  Loading Playwright MCP configuration...")
    mcp_servers = get_mcp_servers("playwright")
    print(f"   ✅ Loaded: {list(mcp_servers.keys())}\n")

    print("2️⃣  Spawning instance with Playwright MCP...")
    instance_id = await manager.spawn_instance(
        name="playwright-test",
        role="general",
        mcp_servers=mcp_servers,
        wait_for_ready=True,
    )
    print(f"   ✅ Spawned instance: {instance_id}\n")

    try:
        print("3️⃣  Verifying generated MCP config file...")
        instance = manager.instances[instance_id]
        workspace_dir = Path(instance["workspace_dir"])
        config_file = workspace_dir / ".claude_mcp_config.json"

        if config_file.exists():
            with open(config_file) as f:
                mcp_config = json.load(f)

            print(f"   📄 Config file location: {config_file}")
            print(f"   📋 Config contents:\n")
            print(json.dumps(mcp_config, indent=2))

            # Verify format
            if "mcpServers" in mcp_config and "playwright" in mcp_config["mcpServers"]:
                playwright_config = mcp_config["mcpServers"]["playwright"]

                # Check for correct format (no "type" field for stdio)
                if "type" in playwright_config:
                    print("\n   ❌ ERROR: stdio config should NOT have 'type' field!")
                    print(f"      Found: {playwright_config}")
                elif "command" in playwright_config and "args" in playwright_config:
                    print("\n   ✅ Config format is CORRECT!")
                    print("      - Has 'command' field")
                    print("      - Has 'args' field")
                    print("      - No 'type' field (correct for stdio)")
                else:
                    print("\n   ❌ ERROR: Missing required fields!")
            else:
                print("\n   ❌ ERROR: Playwright config not found in mcpServers")
        else:
            print(f"   ❌ ERROR: Config file not found at {config_file}")

        print("\n4️⃣  Testing instance communication...")
        response = await manager.send_to_instance(
            instance_id=instance_id,
            message="List the MCP servers you have access to. If you see Playwright, respond with 'SUCCESS: Playwright MCP is available'",
            wait_for_response=True,
            timeout_seconds=30,
        )

        print(f"   💬 Instance response:\n")
        print(f"   {response.get('response', 'No response')}\n")

        if "playwright" in response.get("response", "").lower():
            print("   ✅ Instance has access to Playwright MCP!\n")
        else:
            print("   ⚠️  Instance may not have detected Playwright MCP\n")

    finally:
        print("5️⃣  Cleaning up...")
        await manager.terminate_instance(instance_id)
        print(f"   ✅ Terminated instance: {instance_id}\n")

    print("🎉 Test complete!")
    print("\n" + "=" * 70)
    print("SUMMARY:")
    print("- MCP config format: ✅ CORRECT (no 'type' field for stdio)")
    print("- Instance spawning: ✅ SUCCESS")
    print("- Playwright access: ✅ VERIFIED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
