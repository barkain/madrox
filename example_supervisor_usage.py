"""Example: Using Supervisor Agent with Madrox Networks

This script demonstrates how to integrate the autonomous supervision system
with a Madrox instance manager to monitor a network of Claude instances.
"""

import asyncio
import logging

from supervision.integration import spawn_supervisor, spawn_supervised_network
from supervision.supervisor import SupervisionConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_basic_supervision():
    """Example 1: Basic supervisor attachment to existing network."""
    logger.info("=== Example 1: Basic Supervision ===")

    # Assume we have an existing InstanceManager
    # from orchestrator.instance_manager import InstanceManager
    # manager = InstanceManager(config={...})

    # For demonstration, we'll use a mock manager
    from unittest.mock import MagicMock
    manager = MagicMock()

    # Configure supervision parameters
    config = SupervisionConfig(
        stuck_threshold_seconds=300,      # 5 minutes before considering stuck
        waiting_threshold_seconds=120,    # 2 minutes before considering idle
        error_loop_threshold=3,           # 3 errors before intervention
        max_interventions_per_instance=3, # Max 3 interventions before escalation
        evaluation_interval_seconds=30,   # Check network every 30 seconds
    )

    # Spawn supervisor instance
    supervisor_id, supervisor_agent = await spawn_supervisor(
        instance_manager=manager,
        config=config,
        auto_start=True,  # Automatically start monitoring
    )

    logger.info(f"Supervisor spawned: {supervisor_id}")

    # Supervisor is now running autonomously in the background
    # It will monitor all instances and intervene when needed

    # Get network health summary
    health = supervisor_agent.get_network_health_summary()
    logger.info(f"Network health: {health}")

    # Let it run for a while
    await asyncio.sleep(60)

    # Stop supervisor
    await supervisor_agent.stop()
    logger.info("Supervisor stopped")


async def example_supervised_network():
    """Example 2: Spawn a complete supervised network."""
    logger.info("=== Example 2: Supervised Network ===")

    from unittest.mock import MagicMock, AsyncMock
    manager = MagicMock()
    manager.spawn_instance = AsyncMock(return_value="mock-instance-id")

    # Define participant instances
    participants = [
        {
            "name": "frontend-developer",
            "role": "frontend_developer",
            "bypass_isolation": False,
        },
        {
            "name": "backend-developer",
            "role": "backend_developer",
            "bypass_isolation": False,
        },
        {
            "name": "testing-specialist",
            "role": "testing_specialist",
            "bypass_isolation": False,
        },
    ]

    # Spawn supervised network (participants + supervisor)
    network = await spawn_supervised_network(
        instance_manager=manager,
        participant_configs=participants,
        supervision_config=SupervisionConfig(
            evaluation_interval_seconds=30
        ),
    )

    logger.info(f"Network spawned:")
    logger.info(f"  Supervisor: {network['supervisor_id']}")
    logger.info(f"  Participants: {network['participant_ids']}")
    logger.info(f"  Network size: {network['network_size']}")

    # Supervisor is automatically monitoring all participants
    supervisor = network["supervisor_agent"]

    # Monitor for a while
    await asyncio.sleep(120)

    # Get health summary
    health = supervisor.get_network_health_summary()
    logger.info(f"Network health after 2 minutes: {health}")

    # Stop supervisor
    await supervisor.stop()


async def example_intervention_scenarios():
    """Example 3: Demonstrate intervention scenarios."""
    logger.info("=== Example 3: Intervention Scenarios ===")

    from unittest.mock import MagicMock, AsyncMock
    manager = MagicMock()
    manager.spawn_instance = AsyncMock(return_value="supervisor-instance")
    manager.send_to_instance = AsyncMock(return_value={"status": "sent"})
    manager.get_instance_status = MagicMock(return_value={
        "instances": {
            "instance-1": {"state": "busy", "name": "worker-1"},
            "instance-2": {"state": "idle", "name": "worker-2"},
        }
    })
    manager.get_tmux_pane_content = AsyncMock(return_value="Working on task...\nNo progress for 10 minutes")

    # Spawn supervisor
    supervisor_id, supervisor = await spawn_supervisor(
        instance_manager=manager,
        config=SupervisionConfig(
            stuck_threshold_seconds=60,  # Short threshold for demo
            evaluation_interval_seconds=10,
        ),
        auto_start=True,
    )

    logger.info("Supervisor monitoring for stuck instances...")

    # Let supervisor detect and intervene
    await asyncio.sleep(30)

    # Check intervention history
    health = supervisor.get_network_health_summary()
    logger.info(f"Interventions performed: {health['total_interventions']}")
    logger.info(f"Successful: {health['successful_interventions']}")

    await supervisor.stop()


async def main():
    """Run all examples."""
    # Note: These examples use mock managers for demonstration
    # In production, use real InstanceManager from Madrox

    try:
        await example_basic_supervision()
        await asyncio.sleep(2)

        await example_supervised_network()
        await asyncio.sleep(2)

        await example_intervention_scenarios()

    except Exception as e:
        logger.error(f"Error in examples: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
