"""Test bidirectional messaging protocol."""

import asyncio
import json
import logging
import sys
from datetime import datetime

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8002"


async def test_spawn_instance():
    """Test spawning a Claude instance."""
    logger.info("=" * 80)
    logger.info("TEST 1: Spawning Claude instance")
    logger.info("=" * 80)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "spawn_claude",
                    "arguments": {
                        "name": "test-bidirectional",
                        "role": "general",
                        "wait_for_ready": True,
                    },  # Madrox is always enabled
                },
            },
        )

        result = response.json()
        logger.info(f"Response: {json.dumps(result, indent=2)}")

        if "result" in result and "content" in result["result"]:
            content = result["result"]["content"][0]["text"]
            # Extract instance ID from response
            import re

            match = re.search(r"ID: ([a-f0-9-]+)", content)
            if match:
                instance_id = match.group(1)
                logger.info(f"✅ Instance spawned: {instance_id}")
                return instance_id
            else:
                logger.error("Failed to extract instance ID")
                return None
        else:
            logger.error(f"Failed to spawn instance: {result}")
            return None


async def test_multiline_message(instance_id: str):
    """Test sending multiline message (should not hang terminal)."""
    logger.info("=" * 80)
    logger.info("TEST 2: Multiline message handling")
    logger.info("=" * 80)

    multiline_message = """Please analyze this code:

def calculate(x, y):
    result = x + y
    return result

Tell me what this function does."""

    async with httpx.AsyncClient(timeout=120.0) as client:
        start_time = datetime.now()

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "send_to_instance",
                    "arguments": {
                        "instance_id": instance_id,
                        "message": multiline_message,
                        "wait_for_response": True,
                        "timeout_seconds": 60,
                    },
                },
            },
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        result = response.json()

        logger.info(f"Response received in {elapsed:.2f}s")

        if "result" in result:
            content = result["result"]["content"][0]["text"]
            logger.info(f"Response preview: {content[:200]}...")

            # Check which protocol was used
            if "bidirectional" in content:
                logger.info("✅ Used BIDIRECTIONAL protocol")
            elif "polling" in content or "fallback" in content:
                logger.info("⚠️  Used POLLING FALLBACK protocol")
            else:
                logger.info("ℹ️  Protocol unknown from response")

            return True
        else:
            logger.error(f"Failed to send message: {result}")
            return False


async def test_bidirectional_protocol(instance_id: str):
    """Test explicit bidirectional protocol with reply_to_caller."""
    logger.info("=" * 80)
    logger.info("TEST 3: Bidirectional protocol (instructing instance to use reply_to_caller)")
    logger.info("=" * 80)

    # Instruct the instance to use reply_to_caller tool
    message = """IMPORTANT: When you respond to this message, use the reply_to_caller tool instead of just outputting text.

Example:
reply_to_caller(
    instance_id="your-instance-id",
    reply_message="Your response here",
    correlation_id="message-id-from-my-request"
)

Now, please confirm you understand by using reply_to_caller to respond with: "Understood - using bidirectional protocol"
"""

    async with httpx.AsyncClient(timeout=120.0) as client:
        start_time = datetime.now()

        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "send_to_instance",
                    "arguments": {
                        "instance_id": instance_id,
                        "message": message,
                        "wait_for_response": True,
                        "timeout_seconds": 60,
                    },
                },
            },
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        result = response.json()

        logger.info(f"Response received in {elapsed:.2f}s")

        if "result" in result:
            content = result["result"]["content"][0]["text"]
            logger.info(f"Full response:\n{content}")

            # Check protocol
            if "bidirectional" in content.lower():
                logger.info("✅ BIDIRECTIONAL protocol confirmed!")
            else:
                logger.info("⚠️  Did not detect bidirectional protocol marker")

            return True
        else:
            logger.error(f"Failed: {result}")
            return False


async def test_get_instance_status(instance_id: str):
    """Get instance status to verify it's still running."""
    logger.info("=" * 80)
    logger.info("TEST 4: Get instance status")
    logger.info("=" * 80)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_instance_status",
                    "arguments": {"instance_id": instance_id},
                },
            },
        )

        result = response.json()

        if "result" in result:
            status_text = result["result"]["content"][0]["text"]
            logger.info(f"Status:\n{status_text}")
            return True
        else:
            logger.error(f"Failed to get status: {result}")
            return False


async def cleanup_instance(instance_id: str):
    """Terminate the test instance."""
    logger.info("=" * 80)
    logger.info("CLEANUP: Terminating test instance")
    logger.info("=" * 80)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "terminate_instance",
                    "arguments": {"instance_id": instance_id, "force": True},
                },
            },
        )

        result = response.json()
        logger.info(f"Cleanup result: {json.dumps(result, indent=2)}")


async def main():
    """Run all tests."""
    try:
        # Test 1: Spawn instance
        instance_id = await test_spawn_instance()
        if not instance_id:
            logger.error("❌ Failed to spawn instance, aborting tests")
            return

        await asyncio.sleep(2)

        # Test 2: Multiline message
        success = await test_multiline_message(instance_id)
        if not success:
            logger.error("❌ Multiline test failed")

        await asyncio.sleep(2)

        # Test 3: Bidirectional protocol
        success = await test_bidirectional_protocol(instance_id)
        if not success:
            logger.error("❌ Bidirectional test failed")

        await asyncio.sleep(2)

        # Test 4: Status check
        await test_get_instance_status(instance_id)

        # Cleanup
        await cleanup_instance(instance_id)

        logger.info("=" * 80)
        logger.info("✅ ALL TESTS COMPLETED")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Test suite failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
