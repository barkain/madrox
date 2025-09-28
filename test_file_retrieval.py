#!/usr/bin/env python3
"""Test script for file retrieval functionality in Madrox."""

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


async def test_file_operations():
    """Test file creation and retrieval from Madrox instances."""

    # Create config and manager
    config = OrchestratorConfig()
    manager = InstanceManager(config.to_dict())

    try:
        # Spawn a test instance
        logger.info("Spawning test instance...")
        instance_id = await manager.spawn_instance(
            name="poet",
            role="general"
        )
        logger.info(f"Created instance: {instance_id}")

        # Send message to create a poem file
        logger.info("Asking instance to write a poem...")
        result = await manager.send_to_instance(
            instance_id=instance_id,
            message=(
                "Write a haiku poem about coding and save it to a file called 'haiku.txt'. "
                "Use the Write tool to create the file. After writing, use Read to verify."
            ),
            wait_for_response=True,
            timeout_seconds=30
        )

        if result:
            logger.info(f"Instance response: {result.get('response', result)[:200]}...")

        # List files in the instance workspace
        logger.info("\nListing files in instance workspace...")
        files = await manager.list_instance_files(instance_id)
        if files:
            logger.info(f"Files found: {files}")
        else:
            logger.info("No files found in workspace")

        # Retrieve the poem file
        if files and 'haiku.txt' in files:
            logger.info("\nRetrieving haiku.txt...")
            retrieved_path = await manager.retrieve_instance_file(
                instance_id=instance_id,
                filename='haiku.txt',
                destination_path='.'
            )

            if retrieved_path:
                logger.info(f"File retrieved to: {retrieved_path}")

                # Read and display the content
                with open(retrieved_path, 'r') as f:
                    content = f.read()
                    logger.info(f"\nPoem content:\n{content}")
            else:
                logger.error("Failed to retrieve file")

        # Cleanup
        logger.info("\nTerminating instance...")
        await manager.terminate_instance(instance_id)
        logger.info("Test completed!")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_file_operations())