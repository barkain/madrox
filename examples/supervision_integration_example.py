"""Comprehensive Supervision Integration Examples.

This module demonstrates various patterns for integrating the Madrox Supervision
system with the orchestrator.
"""

import asyncio
import logging
from pathlib import Path

from orchestrator.instance_manager import InstanceManager
from supervision.integration import (
    attach_supervisor,
    spawn_supervised_network,
    spawn_supervisor,
)
from supervision.supervisor import SupervisionConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def example_basic_supervision():
    """Example 1: Basic autonomous supervision of a Madrox network."""
    logger.info("=" * 60)
    logger.info("Example 1: Basic Autonomous Supervision")
    logger.info("=" * 60)

    # Initialize instance manager
    config = {
        "workspace_base_dir": "/tmp/madrox_supervision_example",
        "log_dir": "/tmp/madrox_logs",
        "log_level": "INFO"
    }
    manager = InstanceManager(config)

    # Spawn some worker instances
    logger.info("Spawning worker instances...")
    worker1_id = await manager.spawn_instance(
        name="data-processor",
        role="general",
        system_prompt="You are a data processing specialist."
    )
    logger.info(f"Spawned worker 1: {worker1_id}")

    worker2_id = await manager.spawn_instance(
        name="validator",
        role="general",
        system_prompt="You validate and verify data quality."
    )
    logger.info(f"Spawned worker 2: {worker2_id}")

    # Spawn supervisor with custom configuration
    logger.info("Spawning supervisor...")
    supervisor_id, supervisor = await spawn_supervisor(
        instance_manager=manager,
        config=SupervisionConfig(
            stuck_threshold_seconds=180,  # 3 minutes
            evaluation_interval_seconds=20,  # Check every 20 seconds
            enable_auto_intervention=True,
            max_concurrent_helpers=2
        )
    )
    logger.info(f"Supervisor spawned: {supervisor_id}")
    logger.info("Autonomous monitoring is now active!")

    # Simulate some work
    logger.info("\nSending tasks to workers...")
    await manager.send_to_instance(
        worker1_id,
        "Process this dataset: [1, 2, 3, 4, 5]",
        wait_for_response=False
    )
    await manager.send_to_instance(
        worker2_id,
        "Validate the results from the data processor",
        wait_for_response=False
    )

    # Let supervision run for a while
    logger.info("\nLetting supervision run for 30 seconds...")
    await asyncio.sleep(30)

    # Check for detected issues
    issues = await supervisor.get_detected_issues()
    logger.info(f"\nDetected issues: {len(issues)}")
    for issue in issues:
        logger.info(f"  - {issue.description} (Severity: {issue.severity})")

    # Get intervention history
    interventions = supervisor.get_interventions()
    logger.info(f"\nInterventions performed: {len(interventions)}")
    for intervention in interventions:
        logger.info(f"  - {intervention.intervention_type}: {intervention.description}")

    # Stop supervision
    logger.info("\nStopping supervision...")
    await supervisor.stop()
    logger.info("Supervision stopped")

    # Cleanup
    await manager.terminate_instance(worker1_id)
    await manager.terminate_instance(worker2_id)
    await manager.terminate_instance(supervisor_id)


async def example_supervised_network():
    """Example 2: Create a complete supervised development team."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Supervised Development Team")
    logger.info("=" * 60)

    # Initialize instance manager
    config = {
        "workspace_base_dir": "/tmp/madrox_team_example",
        "log_dir": "/tmp/madrox_logs",
        "log_level": "INFO"
    }
    manager = InstanceManager(config)

    # Spawn supervised network with specialized roles
    logger.info("Spawning supervised development team...")
    network = await spawn_supervised_network(
        instance_manager=manager,
        participant_configs=[
            {
                "name": "frontend-developer",
                "role": "frontend_developer",
                "system_prompt": "You are a React and TypeScript expert focused on UI development."
            },
            {
                "name": "backend-developer",
                "role": "backend_developer",
                "system_prompt": "You are a Python/FastAPI expert focused on API development."
            },
            {
                "name": "qa-engineer",
                "role": "testing_specialist",
                "system_prompt": "You write comprehensive tests and ensure quality."
            }
        ],
        supervision_config=SupervisionConfig(
            stuck_threshold_seconds=300,
            evaluation_interval_seconds=30,
            max_concurrent_helpers=2
        )
    )

    supervisor_id = network["supervisor_id"]
    participant_ids = network["participant_ids"]
    supervisor = network["supervisor_agent"]

    logger.info(f"Team spawned successfully!")
    logger.info(f"  Supervisor: {supervisor_id}")
    logger.info(f"  Participants: {participant_ids}")
    logger.info(f"  Total network size: {network['network_size']}")

    # Assign tasks to team members
    logger.info("\nAssigning tasks to team...")
    for idx, participant_id in enumerate(participant_ids):
        task = f"Work on feature #{idx + 1}"
        await manager.send_to_instance(
            participant_id,
            task,
            wait_for_response=False
        )
        logger.info(f"  Assigned task to {participant_id}: {task}")

    # Monitor progress
    logger.info("\nMonitoring team progress for 45 seconds...")
    await asyncio.sleep(45)

    # Get team status
    logger.info("\nTeam Status:")
    for participant_id in participant_ids:
        status = await manager.get_instance_status(participant_id)
        logger.info(f"  {participant_id}: {status.get('status', 'unknown')}")

    # Check supervisor insights
    issues = await supervisor.get_detected_issues()
    logger.info(f"\nSupervisor detected {len(issues)} issues")

    # Cleanup
    logger.info("\nCleaning up team...")
    await supervisor.stop()
    for participant_id in participant_ids:
        await manager.terminate_instance(participant_id)
    await manager.terminate_instance(supervisor_id)


async def example_embedded_supervision():
    """Example 3: Embed supervision without spawning dedicated instance."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Embedded Supervision (No Dedicated Instance)")
    logger.info("=" * 60)

    # Initialize instance manager
    config = {
        "workspace_base_dir": "/tmp/madrox_embedded_example",
        "log_dir": "/tmp/madrox_logs",
        "log_level": "INFO"
    }
    manager = InstanceManager(config)

    # Attach supervisor without spawning
    logger.info("Attaching embedded supervisor...")
    supervisor = await attach_supervisor(
        instance_manager=manager,
        config=SupervisionConfig(
            evaluation_interval_seconds=15,
            enable_auto_intervention=False,  # Manual intervention control
            enable_progress_tracking=True
        )
    )
    logger.info("Supervisor attached (not started yet)")

    # Spawn some workers
    logger.info("\nSpawning workers...")
    workers = []
    for i in range(3):
        worker_id = await manager.spawn_instance(
            name=f"worker-{i}",
            role="general"
        )
        workers.append(worker_id)
        logger.info(f"  Spawned: {worker_id}")

    # Start supervision manually
    logger.info("\nStarting supervision...")
    await supervisor.start()
    logger.info("Supervision active (embedded mode)")

    # Do some work
    logger.info("\nAssigning tasks...")
    for worker_id in workers:
        await manager.send_to_instance(
            worker_id,
            "Process data batch",
            wait_for_response=False
        )

    # Monitor with manual control
    logger.info("\nMonitoring for 30 seconds...")
    await asyncio.sleep(30)

    # Check issues manually
    issues = await supervisor.get_detected_issues()
    if issues:
        logger.info(f"\nFound {len(issues)} issues - manual intervention required")
        for issue in issues:
            logger.info(f"  Issue: {issue.description}")
            # Manual intervention logic here
            logger.info(f"  -> Taking manual action for {issue.instance_id}")

    # Stop supervision
    logger.info("\nStopping embedded supervision...")
    await supervisor.stop()
    logger.info("Supervision stopped")

    # Cleanup workers
    for worker_id in workers:
        await manager.terminate_instance(worker_id)


async def example_manual_control():
    """Example 4: Full manual control over supervision lifecycle."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Manual Supervision Control")
    logger.info("=" * 60)

    from supervision.supervisor import SupervisorAgent

    # Initialize instance manager
    config = {
        "workspace_base_dir": "/tmp/madrox_manual_example",
        "log_dir": "/tmp/madrox_logs",
        "log_level": "INFO"
    }
    manager = InstanceManager(config)

    # Create supervisor agent manually
    logger.info("Creating supervisor agent with manual control...")
    supervision_config = SupervisionConfig(
        stuck_threshold_seconds=120,
        evaluation_interval_seconds=10,
        enable_auto_intervention=True,
        enable_progress_tracking=True,
        enable_pattern_analysis=True
    )

    supervisor = SupervisorAgent(
        instance_manager=manager,
        config=supervision_config
    )
    logger.info("Supervisor agent created (not started)")

    # Spawn workers
    logger.info("\nSpawning workers...")
    worker1 = await manager.spawn_instance(name="worker1", role="general")
    worker2 = await manager.spawn_instance(name="worker2", role="general")
    logger.info(f"  Workers: {worker1}, {worker2}")

    # Start supervision with full control
    logger.info("\nStarting supervision with manual control...")
    await supervisor.start()
    logger.info("Supervision started")

    # Send tasks
    await manager.send_to_instance(worker1, "Task 1", wait_for_response=False)
    await manager.send_to_instance(worker2, "Task 2", wait_for_response=False)

    # Monitoring loop with manual checks
    logger.info("\nManual monitoring loop...")
    for i in range(5):
        await asyncio.sleep(10)

        # Get current issues
        issues = await supervisor.get_detected_issues()
        logger.info(f"\nCheck #{i + 1}:")
        logger.info(f"  Detected issues: {len(issues)}")

        for issue in issues:
            logger.info(f"    - {issue.instance_id}: {issue.description}")

        # Get intervention history
        interventions = supervisor.get_interventions()
        logger.info(f"  Total interventions: {len(interventions)}")

        # Manual decision making
        if len(issues) > 2:
            logger.info("  -> Too many issues, taking manual action")
            # Custom intervention logic here
            break

    # Stop supervision
    logger.info("\nStopping supervision...")
    await supervisor.stop()
    logger.info("Supervision stopped")

    # Cleanup
    await manager.terminate_instance(worker1)
    await manager.terminate_instance(worker2)


async def example_custom_configuration():
    """Example 5: Custom supervision configurations for different scenarios."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 5: Custom Supervision Configurations")
    logger.info("=" * 60)

    # Development configuration - fast feedback
    dev_config = SupervisionConfig(
        stuck_threshold_seconds=60,  # 1 minute
        evaluation_interval_seconds=5,  # Check every 5 seconds
        max_stall_count=2,
        enable_auto_intervention=True,
        max_concurrent_helpers=5
    )
    logger.info("Development config:")
    logger.info(f"  Stuck threshold: {dev_config.stuck_threshold_seconds}s")
    logger.info(f"  Evaluation interval: {dev_config.evaluation_interval_seconds}s")

    # Production configuration - conservative
    prod_config = SupervisionConfig(
        stuck_threshold_seconds=600,  # 10 minutes
        evaluation_interval_seconds=60,  # Check every minute
        max_stall_count=5,
        enable_auto_intervention=True,
        max_concurrent_helpers=3
    )
    logger.info("\nProduction config:")
    logger.info(f"  Stuck threshold: {prod_config.stuck_threshold_seconds}s")
    logger.info(f"  Evaluation interval: {prod_config.evaluation_interval_seconds}s")

    # Monitoring-only configuration - no interventions
    monitor_config = SupervisionConfig(
        stuck_threshold_seconds=300,
        evaluation_interval_seconds=30,
        enable_auto_intervention=False,  # No automatic fixes
        enable_progress_tracking=True,
        enable_pattern_analysis=True
    )
    logger.info("\nMonitoring-only config:")
    logger.info(f"  Auto intervention: {monitor_config.enable_auto_intervention}")
    logger.info(f"  Progress tracking: {monitor_config.enable_progress_tracking}")

    # High-throughput configuration - multiple helpers
    high_throughput_config = SupervisionConfig(
        stuck_threshold_seconds=180,
        evaluation_interval_seconds=15,
        max_concurrent_helpers=10,  # Many helpers
        helper_timeout_seconds=300,  # 5 minutes per helper
        enable_auto_intervention=True
    )
    logger.info("\nHigh-throughput config:")
    logger.info(f"  Max concurrent helpers: {high_throughput_config.max_concurrent_helpers}")
    logger.info(f"  Helper timeout: {high_throughput_config.helper_timeout_seconds}s")

    logger.info("\nConfiguration examples complete!")


async def main():
    """Run all examples."""
    logger.info("Starting Supervision Integration Examples")
    logger.info("=" * 60)

    try:
        # Run examples sequentially
        await example_basic_supervision()
        await asyncio.sleep(2)

        await example_supervised_network()
        await asyncio.sleep(2)

        await example_embedded_supervision()
        await asyncio.sleep(2)

        await example_manual_control()
        await asyncio.sleep(2)

        await example_custom_configuration()

        logger.info("\n" + "=" * 60)
        logger.info("All examples completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
