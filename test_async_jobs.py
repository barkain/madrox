#!/usr/bin/env python3
"""Test script for async job functionality in Madrox."""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestrator.instance_manager import InstanceManager
from src.orchestrator.config import OrchestratorConfig
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_async_jobs():
    """Test the async job functionality."""

    # Create config and manager
    config = OrchestratorConfig()
    manager = InstanceManager(config.to_dict())

    try:
        # Spawn a test instance
        logger.info("Spawning test instance...")
        instance_id = await manager.spawn_instance(
            name="test-async",
            role="general"
        )
        logger.info(f"Created instance: {instance_id}")

        # Send a non-blocking message
        logger.info("Sending non-blocking message...")
        result = await manager.send_to_instance(
            instance_id=instance_id,
            message="Generate a Python function that calculates fibonacci numbers",
            wait_for_response=False,
            timeout_seconds=30
        )

        if isinstance(result, dict) and "job_id" in result:
            job_id = result["job_id"]
            logger.info(f"Job created: {job_id}, status: {result['status']}")

            # Check job status immediately
            job_status = await manager.get_job_status(job_id)
            if job_status:
                logger.info(f"Initial job status: {job_status['status']}")
            else:
                logger.error(f"Job {job_id} not found!")
                return

            # Wait a bit and check again
            await asyncio.sleep(2)
            job_status = await manager.get_job_status(job_id)
            if job_status:
                logger.info(f"After 2 seconds: {job_status['status']}")

            # Wait for completion (max 30 seconds)
            max_wait = 30
            wait_interval = 1
            total_waited = 0

            while total_waited < max_wait:
                job_status = await manager.get_job_status(job_id)
                if job_status and job_status["status"] in ["completed", "failed", "timeout"]:
                    break
                await asyncio.sleep(wait_interval)
                total_waited += wait_interval
                if job_status:
                    logger.info(f"Waiting... ({total_waited}s) Status: {job_status['status']}")

            # Final status
            final_status = await manager.get_job_status(job_id)
            if final_status:
                logger.info(f"\nFinal job status: {final_status['status']}")

                if final_status["status"] == "completed":
                    logger.info("Job completed successfully!")
                    if final_status.get("result"):
                        logger.info(f"Result preview: {str(final_status['result'])[:200]}...")
                elif final_status["status"] == "failed":
                    logger.error(f"Job failed: {final_status.get('error')}")
                elif final_status["status"] == "timeout":
                    logger.warning(f"Job timed out: {final_status.get('error')}")
                else:
                    logger.warning(f"Job still in progress after {max_wait} seconds")
            else:
                logger.error("Could not retrieve final job status")

            # Test sending a blocking message for comparison
            logger.info("\n--- Testing blocking message for comparison ---")
            blocking_result = await manager.send_to_instance(
                instance_id=instance_id,
                message="What is 2+2?",
                wait_for_response=True,
                timeout_seconds=10
            )
            if blocking_result:
                logger.info(f"Blocking result: {blocking_result.get('content', 'No content')[:100]}...")

        else:
            logger.error(f"Unexpected result from non-blocking send: {result}")

        # Cleanup
        logger.info("\nTerminating instance...")
        await manager.terminate_instance(instance_id)
        logger.info("Test completed!")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_async_jobs())