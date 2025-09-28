#!/usr/bin/env python3
"""Test script for bypass isolation functionality in Madrox."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestrator.instance_manager import InstanceManager
from src.orchestrator.simple_models import OrchestratorConfig
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_bypass_isolation():
    """Test file creation with bypass_isolation enabled."""

    # Create config and manager
    config = OrchestratorConfig()
    manager = InstanceManager(config.to_dict())

    try:
        # Test 1: Normal isolated instance
        logger.info("=== Test 1: Isolated Instance ===")
        isolated_id = await manager.spawn_instance(
            name="isolated-writer",
            role="general",
            bypass_isolation=False  # Default behavior
        )
        logger.info(f"Created isolated instance: {isolated_id}")

        # Ask it to write a file (should go to workspace)
        result = await manager.send_to_instance(
            instance_id=isolated_id,
            message="Write a file called 'isolated_test.txt' with content 'This is from isolated instance'. Use the Write tool.",
            wait_for_response=True,
            timeout_seconds=30
        )
        logger.info("Isolated instance response received")

        # Check if file exists in workspace
        files = await manager.list_instance_files(isolated_id)
        logger.info(f"Files in isolated workspace: {files}")

        # Test 2: Bypass isolation instance
        logger.info("\n=== Test 2: Bypass Isolation Instance ===")
        bypass_id = await manager.spawn_instance(
            name="bypass-writer",
            role="general",
            bypass_isolation=True  # Enable bypass
        )
        logger.info(f"Created bypass instance: {bypass_id}")

        # Ask it to write a file to current directory
        current_dir = Path.cwd()
        result = await manager.send_to_instance(
            instance_id=bypass_id,
            message=f"Write a file called 'bypass_test.txt' with content 'This is from bypass instance - full filesystem access!' to the current directory. Use the Write tool.",
            wait_for_response=True,
            timeout_seconds=30
        )
        logger.info("Bypass instance response received")

        # Check if file exists in current directory
        bypass_file = Path("bypass_test.txt")
        if bypass_file.exists():
            logger.info(f"✓ File created in current directory: {bypass_file}")
            with open(bypass_file, 'r') as f:
                content = f.read()
                logger.info(f"File content: {content}")
        else:
            logger.error("✗ File not found in current directory")

        # Test 3: Bypass instance writing to absolute path
        logger.info("\n=== Test 3: Absolute Path Writing ===")
        test_path = "/tmp/madrox_absolute_test.txt"
        result = await manager.send_to_instance(
            instance_id=bypass_id,
            message=f"Write a file to the absolute path '{test_path}' with content 'Absolute path test from Madrox'. Use the Write tool.",
            wait_for_response=True,
            timeout_seconds=30
        )

        # Check if file exists at absolute path
        if Path(test_path).exists():
            logger.info(f"✓ File created at absolute path: {test_path}")
            with open(test_path, 'r') as f:
                content = f.read()
                logger.info(f"File content: {content}")
        else:
            logger.error(f"✗ File not found at {test_path}")

        # Cleanup
        logger.info("\n=== Cleanup ===")
        await manager.terminate_instance(isolated_id)
        await manager.terminate_instance(bypass_id)

        # Remove test files
        if bypass_file.exists():
            bypass_file.unlink()
            logger.info("Removed bypass_test.txt")

        if Path(test_path).exists():
            Path(test_path).unlink()
            logger.info(f"Removed {test_path}")

        logger.info("\nTest completed successfully!")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_bypass_isolation())