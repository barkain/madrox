#!/usr/bin/env python3
"""
Debug script to test Madrox hierarchical network (1-2-2 topology).
Tests autonomous task processing and monitors for idle/stuck states.

Topology:
- 1 Main orchestrator instance
- 2 Backend developer instances (children of main)
- 2 Testing specialist instances (children of each backend dev)

Task: Build a complete REST API with tests (>5 min complexity)
"""

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from orchestrator.instance_manager import InstanceManager
from orchestrator.simple_models import OrchestratorConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug_network.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class NetworkMonitor:
    """Monitor instance network for idle/stuck states."""

    def __init__(self, manager: InstanceManager):
        self.manager = manager
        self.monitoring = True
        self.status_history = []

    async def monitor_loop(self, interval: int = 5):
        """Continuously monitor instance states."""
        logger.info("Starting network monitor...")

        while self.monitoring:
            try:
                timestamp = datetime.now().isoformat()

                # Get all instance statuses directly from manager
                all_instances = self.manager.instances

                status_snapshot = {
                    'timestamp': timestamp,
                    'instances': []
                }

                for inst_id, instance in all_instances.items():
                    # Get recent output
                    try:
                        output = await self.manager.get_instance_output(inst_id, limit=5)
                    except Exception:
                        output = []

                    uptime = 0
                    if instance.get('created_at'):
                        created_at = datetime.fromisoformat(instance['created_at'])
                        uptime = (datetime.now(UTC) - created_at).total_seconds()

                    inst_status = {
                        'id': inst_id,
                        'name': instance.get('name', 'unknown'),
                        'state': instance.get('state', 'unknown'),
                        'role': instance.get('role', 'unknown'),
                        'parent_id': instance.get('parent_instance_id'),
                        'uptime_seconds': int(uptime),
                        'message_count': instance.get('message_count', 0),
                        'recent_output_count': len(output),
                        'last_output': output[0] if output else None
                    }

                    status_snapshot['instances'].append(inst_status)

                    # Detect potential stuck states
                    if instance.get('state') == 'busy' and uptime > 120:
                        logger.warning(
                            f"Instance {inst_id} ({instance.get('name')}) busy for {uptime}s - possible stuck state"
                        )

                    if instance.get('state') == 'idle' and instance.get('message_count', 0) == 0 and uptime > 30:
                        logger.warning(
                            f"Instance {inst_id} ({instance.get('name')}) idle with no messages processed"
                        )

                self.status_history.append(status_snapshot)

                # Log summary
                logger.info(f"Network status: {len(all_instances)} instances - " +
                           f"States: {[i['state'] for i in status_snapshot['instances']]}")

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Monitor error: {e}", exc_info=True)
                await asyncio.sleep(interval)

    def stop(self):
        """Stop monitoring."""
        self.monitoring = False

    def save_history(self, filepath: str = "network_monitor_history.json"):
        """Save monitoring history to file."""
        with open(filepath, 'w') as f:
            json.dump(self.status_history, f, indent=2)
        logger.info(f"Saved monitoring history to {filepath}")


async def spawn_network(manager: InstanceManager) -> dict[str, str]:
    """Spawn 1-2-2 hierarchical network.

    Returns:
        dict mapping instance names to IDs
    """
    logger.info("Spawning hierarchical network (1-2-2)...")

    # Level 1: Main orchestrator
    logger.info("Spawning main orchestrator...")
    main_id = await manager.spawn_instance(
        name="main_orchestrator",
        role="architect",
        enable_madrox=True
    )
    logger.info(f"Main orchestrator spawned: {main_id}")

    # Wait for main to initialize
    await asyncio.sleep(2)

    # Level 2: Two backend developers
    logger.info("Spawning backend developers...")
    backend_ids = []

    for i in range(2):
        backend_id = await manager.spawn_instance(
            name=f"backend_dev_{i+1}",
            role="backend_developer",
            parent_instance_id=main_id,
            enable_madrox=True
        )
        backend_ids.append(backend_id)
        logger.info(f"Backend dev {i+1} spawned: {backend_id}")
        await asyncio.sleep(1)

    # Level 3: Two testing specialists per backend dev
    logger.info("Spawning testing specialists...")
    tester_ids = []

    for i, backend_id in enumerate(backend_ids):
        for j in range(2):
            tester_id = await manager.spawn_instance(
                name=f"tester_{i+1}_{j+1}",
                role="testing_specialist",
                parent_instance_id=backend_id,
                enable_madrox=True
            )
            tester_ids.append(tester_id)
            logger.info(f"Tester {i+1}_{j+1} spawned: {tester_id}")
            await asyncio.sleep(1)

    network = {
        'main': main_id,
        'backend_1': backend_ids[0],
        'backend_2': backend_ids[1],
        'tester_1_1': tester_ids[0],
        'tester_1_2': tester_ids[1],
        'tester_2_1': tester_ids[2],
        'tester_2_2': tester_ids[3]
    }

    logger.info(f"Network topology: {json.dumps(network, indent=2)}")
    return network


async def assign_complex_task(manager: InstanceManager, network: dict[str, str]):
    """Assign a complex task requiring >5 minutes to complete."""

    main_id = network['main']

    task_prompt = """
    Build a complete REST API for a task management system with the following requirements:

    1. API Endpoints (delegate to backend developers):
       - POST /tasks - Create new task
       - GET /tasks - List all tasks with filtering
       - GET /tasks/{id} - Get specific task
       - PUT /tasks/{id} - Update task
       - DELETE /tasks/{id} - Delete task
       - GET /tasks/stats - Get task statistics

    2. Data Model:
       - Task: id, title, description, status, priority, created_at, updated_at
       - Status: pending, in_progress, completed, cancelled
       - Priority: low, medium, high, urgent

    3. Testing Requirements (delegate to testing specialists):
       - Unit tests for each endpoint
       - Integration tests for workflows
       - Performance tests for list endpoint
       - Validation tests for input data

    4. Implementation Details:
       - Use FastAPI framework
       - SQLAlchemy for database (SQLite)
       - Pydantic for validation
       - Proper error handling
       - OpenAPI documentation

    Coordinate with your backend developers to implement the API, and have them
    coordinate with their testing specialists to ensure comprehensive test coverage.

    Report back with:
    - Implementation summary
    - Test results
    - Any issues encountered
    """

    logger.info("Assigning complex task to main orchestrator...")

    response = await manager.send_to_instance(
        instance_id=main_id,
        message=task_prompt,
        wait_for_response=False  # Don't block
    )

    logger.info(f"Task assigned. Response: {response}")
    return response.get('job_id') if response else None


async def main():
    """Main debug workflow."""

    logger.info("=" * 80)
    logger.info("Madrox Hierarchical Network Debug Test")
    logger.info("=" * 80)

    # Initialize configuration
    config = OrchestratorConfig(
        workspace_base_dir="/tmp/madrox_debug_network",
        log_dir="/tmp/madrox_debug_logs",
        log_level="DEBUG",
        max_concurrent_instances=20
    )

    # Initialize manager
    manager = InstanceManager(config.to_dict())
    monitor = NetworkMonitor(manager)

    try:
        # Start monitoring in background
        monitor_task = asyncio.create_task(monitor.monitor_loop(interval=10))

        # Spawn network
        network = await spawn_network(manager)

        logger.info("\nNetwork spawned successfully!")
        logger.info(f"Total instances: {len(network)}")

        # Wait for all instances to be ready
        logger.info("\nWaiting for instances to initialize...")
        await asyncio.sleep(5)

        # Assign complex task
        job_id = await assign_complex_task(manager, network)

        logger.info(f"\nTask assigned (Job ID: {job_id})")
        logger.info("Monitoring for 10 minutes...")
        logger.info("Watch for idle/stuck states in the logs")

        # Monitor for 10 minutes
        await asyncio.sleep(600)

        logger.info("\n" + "=" * 80)
        logger.info("Test complete - checking final states...")
        logger.info("=" * 80)

        # Get final status
        all_instances = manager.instances
        for inst_id, instance in all_instances.items():
            uptime = 0
            if instance.get('created_at'):
                created_at = datetime.fromisoformat(instance['created_at'])
                uptime = (datetime.now(UTC) - created_at).total_seconds()

            logger.info(f"\nInstance: {instance.get('name')}")
            logger.info(f"  State: {instance.get('state')}")
            logger.info(f"  Messages: {instance.get('message_count', 0)}")
            logger.info(f"  Uptime: {int(uptime)}s")

            # Get output
            try:
                output = await manager.get_instance_output(inst_id, limit=10)
                if output:
                    logger.info(f"  Recent output ({len(output)} messages):")
                    for msg in output[:3]:
                        logger.info(f"    - {msg.get('type')}: {msg.get('content', '')[:100]}")
            except Exception as e:
                logger.warning(f"  Could not get output: {e}")

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")

    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)

    finally:
        # Stop monitoring
        monitor.stop()
        monitor.save_history()

        # Cleanup
        logger.info("\nCleaning up instances...")
        all_instances = list(manager.instances.items())
        for inst_id, instance in all_instances:
            try:
                await manager.terminate_instance(inst_id)
                logger.info(f"Terminated {instance.get('name')}")
            except Exception as e:
                logger.error(f"Error terminating {instance.get('name')}: {e}")

        logger.info("\nDebug test complete. Check debug_network.log and network_monitor_history.json")


if __name__ == "__main__":
    asyncio.run(main())
