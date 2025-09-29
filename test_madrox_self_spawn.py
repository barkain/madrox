#!/usr/bin/env python3
"""Test script to verify Claude madrox can spawn its own sub-madrox instances."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.orchestrator.instance_manager import InstanceManager
from src.orchestrator.simple_models import OrchestratorConfig


async def main():
    """Test madrox self-spawning capability."""
    print("🧪 Testing Madrox Self-Spawn Capability")
    print("=" * 60)

    # Create configuration
    config = OrchestratorConfig(
        workspace_base_dir="/tmp/madrox_self_spawn_test",
        max_concurrent_instances=5,
        anthropic_api_key="test-key",
    )

    # Initialize instance manager
    manager = InstanceManager(config.to_dict())

    try:
        # Spawn a Claude instance WITH madrox enabled
        print("\n📋 Spawning parent Claude instance with madrox enabled...")
        parent_id = await manager.spawn_instance(
            name="Parent-Madrox",
            role="general",
            system_prompt="You are a parent madrox instance. You can spawn child madrox instances.",
            enable_madrox=True,
        )
        print(f"   ✅ Parent instance spawned: {parent_id[:8]}...")

        # Check the command template includes --mcp-server
        parent_instance = manager.instances[parent_id]
        cmd_template = parent_instance.get("cmd_template", [])
        print(f"\n   📝 Command template: {' '.join(cmd_template)}")

        has_mcp_server = "--mcp-server" in cmd_template
        if has_mcp_server:
            print("   ✅ MCP server flag found in command template")
            mcp_index = cmd_template.index("--mcp-server")
            mcp_value = cmd_template[mcp_index + 1]
            print(f"   📍 MCP server config: {mcp_value}")
        else:
            print("   ❌ MCP server flag NOT found in command template")
            return 1

        # Spawn a Claude instance WITHOUT madrox enabled (for comparison)
        print("\n📋 Spawning child Claude instance WITHOUT madrox...")
        child_id = await manager.spawn_instance(
            name="Child-NoMadrox",
            role="general",
            system_prompt="You are a regular child instance without madrox capability.",
            enable_madrox=False,
        )
        print(f"   ✅ Child instance spawned: {child_id[:8]}...")

        # Check the child command template does NOT include --mcp-server
        child_instance = manager.instances[child_id]
        child_cmd_template = child_instance.get("cmd_template", [])

        has_mcp_server_child = "--mcp-server" in child_cmd_template
        if not has_mcp_server_child:
            print("   ✅ MCP server flag correctly NOT in child command template")
        else:
            print("   ❌ MCP server flag unexpectedly found in child command template")
            return 1

        # Verify instance states
        status = manager.get_instance_status()
        print(f"\n📊 System Status:")
        print(f"   Total instances: {status['total_instances']}")
        print(f"   Active instances: {status['active_instances']}")

        for instance_id, instance in status['instances'].items():
            enable_madrox = instance.get('enable_madrox', False)
            madrox_status = "WITH madrox" if enable_madrox else "without madrox"
            print(f"   🔸 {instance['name']}: {instance['state']} ({madrox_status})")

        # Cleanup
        print("\n🧹 Cleaning up...")
        await manager.terminate_instance(parent_id)
        await manager.terminate_instance(child_id)
        print("   ✅ Instances terminated")

        print("\n🎉 Test PASSED!")
        print("=" * 60)
        print("\n✅ Claude madrox can now spawn sub-madrox instances")
        print("✅ enable_madrox=True adds --mcp-server flag to Claude CLI")
        print("✅ enable_madrox=False does NOT add --mcp-server flag")

        return 0

    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)