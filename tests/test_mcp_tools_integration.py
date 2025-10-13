"""Integration test for MCP tool auto-discovery and direct decoration."""

import asyncio
import logging

from src.orchestrator.instance_manager import InstanceManager, mcp
from src.orchestrator.simple_models import OrchestratorConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_mcp_tool_auto_discovery():
    """Test that all MCP tools are auto-discovered and registered."""
    logger.info("=" * 80)
    logger.info("Testing MCP Tool Auto-Discovery and Direct Decoration")
    logger.info("=" * 80)

    # Verify module-level mcp instance exists
    logger.info(f"\n1. Module-level FastMCP instance: {mcp}")
    logger.info(f"   MCP name: {mcp.name}")

    # Check that tools are registered
    tools = await mcp.get_tools()
    logger.info(f"\n2. Registered MCP tools ({len(tools)} total):")
    for tool_name in tools:
        logger.info(f"   - {tool_name}")

    # Verify expected tools are present
    expected_tools = {
        "spawn_claude",
        "spawn_multiple_instances",
        "send_to_instance_tool",
        "get_instance_output_tool",
        "coordinate_instances_tool",
        "terminate_instance_tool",
        "terminate_multiple_instances",
        "get_instance_status_tool",
        "reply_to_caller",
    }

    registered_tool_names = set(tools)
    missing_tools = expected_tools - registered_tool_names
    extra_tools = registered_tool_names - expected_tools

    logger.info("\n3. Tool Registration Verification:")
    logger.info(f"   Expected tools: {len(expected_tools)}")
    logger.info(f"   Registered tools: {len(registered_tool_names)}")

    if missing_tools:
        logger.error(f"   ❌ Missing tools: {missing_tools}")
    else:
        logger.info("   ✅ All expected tools registered")

    if extra_tools:
        logger.info(f"   ℹ️  Additional tools: {extra_tools}")

    # Initialize instance manager and verify it uses the same mcp
    config = OrchestratorConfig()
    manager = InstanceManager(config.to_dict())

    logger.info("\n4. InstanceManager Integration:")
    logger.info(f"   Manager's mcp is module-level mcp: {manager.mcp is mcp}")

    logger.info("\n" + "=" * 80)
    logger.info("✅ MCP Tool Auto-Discovery Test Complete")
    logger.info("=" * 80)

    return len(missing_tools) == 0


async def test_mcp_tools_functionality():
    """Test actual functionality of MCP tools by spawning a network."""
    logger.info("\n" + "=" * 80)
    logger.info("Testing MCP Tools Functionality")
    logger.info("=" * 80)

    config = OrchestratorConfig(
        max_concurrent_instances=10,
        workspace_base_dir="/tmp/claude_orchestrator_test",
    )
    manager = InstanceManager(config.to_dict())

    try:
        # Test 1: spawn_claude tool (call through spawn_instance directly, not MCP wrapper)
        logger.info("\n1. Testing spawn_instance (implementation method)...")
        main_id = await manager.spawn_instance(
            name="test-main",
            role="general",
            bypass_isolation=True,
            enable_madrox=True,
            wait_for_ready=True,
        )
        logger.info(f"   ✅ Spawned main instance: {main_id}")

        # Test 2: Spawn additional workers
        logger.info("\n2. Testing spawn_instance for multiple workers...")
        worker_ids = []
        for i, role in enumerate(["backend_developer", "frontend_developer"], 1):
            worker_id = await manager.spawn_instance(
                name=f"worker-{i}",
                role=role,
                bypass_isolation=True,
                wait_for_ready=True,
            )
            worker_ids.append(worker_id)
        logger.info(f"   ✅ Spawned {len(worker_ids)} worker instances")

        # Test 3: get_instance_status (implementation method)
        logger.info("\n3. Testing get_instance_status...")
        status = manager.get_instance_status(instance_id=None)
        logger.info(f"   ✅ Total instances: {status['total_instances']}")
        logger.info(f"   ✅ Active instances: {status['active_instances']}")

        # Test 4: send_to_instance (non-blocking)
        logger.info("\n4. Testing send_to_instance (non-blocking)...")
        send_result = await manager.send_to_instance(
            instance_id=main_id,
            message="Echo test message",
            wait_for_response=False,
        )
        logger.info(f"   ✅ Message sent: {send_result}")

        # Test 5: get_instance_output
        logger.info("\n5. Testing get_instance_output...")
        output = await manager.get_instance_output(
            instance_id=main_id,
            limit=10,
        )
        logger.info(f"   ✅ Retrieved {len(output)} messages")

        # Test 6: terminate_instance (for workers)
        logger.info("\n6. Testing terminate_instance...")
        terminated_count = 0
        for worker_id in worker_ids:
            success = await manager.terminate_instance(worker_id, force=True)
            if success:
                terminated_count += 1
        logger.info(f"   ✅ Terminated {terminated_count} worker instances")

        # Test 7: terminate_instance (main)
        logger.info("\n7. Testing terminate_instance (main)...")
        success = await manager.terminate_instance(main_id, force=True)
        logger.info(f"   ✅ Terminated main instance: {success}")

        logger.info("\n" + "=" * 80)
        logger.info("✅ All MCP Tools Functionality Tests Passed")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        return False


async def main():
    """Run all integration tests."""
    logger.info("\n" + "=" * 80)
    logger.info("MCP Tool Integration Test Suite")
    logger.info("=" * 80)

    # Test 1: Auto-discovery
    discovery_passed = await test_mcp_tool_auto_discovery()

    # Test 2: Functionality
    functionality_passed = await test_mcp_tools_functionality()

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("Test Summary")
    logger.info("=" * 80)
    logger.info(f"Auto-Discovery Test: {'✅ PASSED' if discovery_passed else '❌ FAILED'}")
    logger.info(f"Functionality Test: {'✅ PASSED' if functionality_passed else '❌ FAILED'}")

    if discovery_passed and functionality_passed:
        logger.info("\n🎉 All tests passed! MCP tools are working correctly.")
        return 0
    else:
        logger.error("\n❌ Some tests failed. See details above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
