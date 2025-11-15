#!/usr/bin/env python3
"""Live integration test for Supervisor Agent with real Madrox instances.

This test spawns actual Madrox instances, attaches the supervisor,
and validates real intervention execution and network monitoring.
"""

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add supervision src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from supervision.integration.manager_integration import (
    attach_supervisor,
)
from supervision.supervisor.agent import (
    DetectedIssue,
    InterventionType,
    IssueSeverity,
    SupervisionConfig,
    SupervisorAgent,
)

# Import real TmuxInstanceManager from Madrox
sys.path.insert(0, "/path/to/user/dev/madrox/src")
from orchestrator.tmux_instance_manager import TmuxInstanceManager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class LiveTestResults:
    """Track test results for reporting."""

    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []

    def record_pass(self, test_name: str):
        """Record a passing test."""
        self.tests_run += 1
        self.tests_passed += 1
        logger.info(f"✅ PASS: {test_name}")

    def record_fail(self, test_name: str, error: str):
        """Record a failing test."""
        self.tests_run += 1
        self.tests_failed += 1
        self.failures.append((test_name, error))
        logger.error(f"❌ FAIL: {test_name}: {error}")

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("SUPERVISOR AGENT LIVE TEST RESULTS")
        print("=" * 80)
        print(f"Tests run: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")

        if self.failures:
            print("\nFailures:")
            for test_name, error in self.failures:
                print(f"  - {test_name}: {error}")

        print("=" * 80)


async def test_spawn_real_instances(manager: TmuxInstanceManager, results: LiveTestResults):
    """Test 1: Spawn real Madrox instances."""
    test_name = "Spawn real Madrox instances"
    logger.info(f"\n{'=' * 60}\nRunning: {test_name}\n{'=' * 60}")

    try:
        # Spawn 3 instances with different roles (non-blocking)
        instance_1 = await manager.spawn_instance(
            name="test-worker-1",
            role="general",
            system_prompt="You are a helpful test assistant.",
            wait_for_ready=False,  # Non-blocking spawn
        )
        logger.info(f"Spawned instance 1: {instance_1}")

        instance_2 = await manager.spawn_instance(
            name="test-worker-2",
            role="general",
            system_prompt="You are a helpful test assistant.",
            wait_for_ready=False,  # Non-blocking spawn
        )
        logger.info(f"Spawned instance 2: {instance_2}")

        instance_3 = await manager.spawn_instance(
            name="test-worker-3",
            role="general",
            system_prompt="You are a helpful test assistant.",
            wait_for_ready=False,  # Non-blocking spawn
        )
        logger.info(f"Spawned instance 3: {instance_3}")

        # Wait for instances to initialize in background
        logger.info("Waiting 10 seconds for instances to initialize...")
        await asyncio.sleep(10)

        # Verify instances are in manager
        status = manager.get_instance_status()
        assert instance_1 in status["instances"], "Instance 1 not found in status"
        assert instance_2 in status["instances"], "Instance 2 not found in status"
        assert instance_3 in status["instances"], "Instance 3 not found in status"

        results.record_pass(test_name)
        return [instance_1, instance_2, instance_3]

    except Exception as e:
        results.record_fail(test_name, str(e))
        raise


async def test_attach_supervisor_to_network(manager: TmuxInstanceManager, results: LiveTestResults):
    """Test 2: Attach supervisor to running network."""
    test_name = "Attach supervisor to network"
    logger.info(f"\n{'=' * 60}\nRunning: {test_name}\n{'=' * 60}")

    try:
        # Create supervision config
        config = SupervisionConfig(
            stuck_threshold_seconds=60,
            waiting_threshold_seconds=30,
            evaluation_interval_seconds=10,
            max_interventions_per_instance=5,
            intervention_cooldown_seconds=5,
        )

        # Attach supervisor
        supervisor = await attach_supervisor(
            instance_manager=manager,
            config=config,
        )

        # Verify supervisor was created
        assert supervisor is not None, "Supervisor is None"
        assert isinstance(supervisor, SupervisorAgent), "Supervisor is not SupervisorAgent"
        assert supervisor.manager == manager, "Supervisor manager mismatch"
        assert not supervisor.running, "Supervisor should not be running yet"

        logger.info("Supervisor successfully attached")

        results.record_pass(test_name)
        return supervisor

    except Exception as e:
        results.record_fail(test_name, str(e))
        raise


async def test_supervisor_detects_instances(
    manager: TmuxInstanceManager,
    supervisor: SupervisorAgent,
    instance_ids: list[str],
    results: LiveTestResults,
):
    """Test 3: Supervisor detects active instances."""
    test_name = "Supervisor detects active instances"
    logger.info(f"\n{'=' * 60}\nRunning: {test_name}\n{'=' * 60}")

    try:
        # Check current instance states
        status = manager.get_instance_status()
        logger.info("Current instance states:")
        for instance_id in instance_ids:
            if instance_id in status["instances"]:
                state = status["instances"][instance_id].get("state")
                logger.info(f"  {instance_id}: {state}")
            else:
                logger.info(f"  {instance_id}: NOT FOUND")

        # Wait for instances to transition to running state
        max_wait = 20
        for i in range(max_wait):
            active_instances = await supervisor._get_active_instances()

            if len(active_instances) >= len(instance_ids):
                logger.info(f"All instances active after {i + 1} seconds")
                break

            logger.info(
                f"Waiting for instances to be active ({len(active_instances)}/{len(instance_ids)})..."
            )
            await asyncio.sleep(1)

        logger.info(f"Active instances detected: {active_instances}")
        logger.info(f"Expected instances: {instance_ids}")

        # Verify all test instances are detected
        for instance_id in instance_ids:
            assert instance_id in active_instances, f"Instance {instance_id} not detected"

        logger.info(f"Successfully detected {len(active_instances)} active instances")

        results.record_pass(test_name)

    except Exception as e:
        results.record_fail(test_name, str(e))
        raise


async def test_supervisor_fetches_transcripts(
    manager: TmuxInstanceManager,
    supervisor: SupervisorAgent,
    instance_ids: list[str],
    results: LiveTestResults,
):
    """Test 4: Supervisor can fetch instance transcripts."""
    test_name = "Supervisor fetches transcripts"
    logger.info(f"\n{'=' * 60}\nRunning: {test_name}\n{'=' * 60}")

    try:
        # Fetch transcript for first instance
        instance_id = instance_ids[0]
        transcript = await manager.get_tmux_pane_content(instance_id, lines=50)

        logger.info(f"Transcript length: {len(transcript)} characters")
        logger.info(f"Transcript preview: {transcript[:200]}...")

        assert transcript is not None, "Transcript is None"
        assert len(transcript) > 0, "Transcript is empty"

        results.record_pass(test_name)

    except Exception as e:
        results.record_fail(test_name, str(e))
        raise


async def test_send_message_to_instance(
    manager: TmuxInstanceManager, instance_ids: list[str], results: LiveTestResults
):
    """Test 5: Send messages to instances."""
    test_name = "Send messages to instances"
    logger.info(f"\n{'=' * 60}\nRunning: {test_name}\n{'=' * 60}")

    try:
        # Send message to first instance
        instance_id = instance_ids[0]
        message = "Please respond with 'TEST ACKNOWLEDGED' to confirm you received this message."

        logger.info(f"Sending message to {instance_id}: {message}")

        # Send message without waiting for response
        await manager.send_to_instance(
            instance_id=instance_id,
            message=message,
            wait_for_response=False,
            timeout_seconds=10,
        )

        logger.info("Message sent successfully")

        # Wait a bit for instance to process
        await asyncio.sleep(2)

        # Fetch transcript to see if message was delivered
        transcript = await manager.get_tmux_pane_content(instance_id, lines=50)
        logger.info(f"Transcript after message: {transcript[-200:]}")

        results.record_pass(test_name)

    except Exception as e:
        results.record_fail(test_name, str(e))
        raise


async def test_supervisor_intervention_execution(
    manager: TmuxInstanceManager,
    supervisor: SupervisorAgent,
    instance_ids: list[str],
    results: LiveTestResults,
):
    """Test 6: Supervisor executes interventions."""
    test_name = "Supervisor executes interventions"
    logger.info(f"\n{'=' * 60}\nRunning: {test_name}\n{'=' * 60}")

    try:
        # Create a simulated issue
        issue = DetectedIssue(
            instance_id=instance_ids[0],
            issue_type="stuck",
            severity=IssueSeverity.WARNING,
            description="Test intervention - simulated stuck instance",
            detected_at=datetime.now(UTC),
            confidence=0.95,
            evidence={"test": "simulated issue"},
        )

        logger.info(f"Simulating issue: {issue.description}")

        # Handle the issue (should trigger intervention)
        await supervisor._handle_issue(issue)

        # Wait for intervention to complete
        await asyncio.sleep(2)

        # Verify intervention was recorded
        assert len(supervisor.intervention_history) > 0, "No interventions recorded"

        last_intervention = supervisor.intervention_history[-1]
        logger.info(f"Intervention executed: {last_intervention.intervention_type.value}")
        logger.info(f"Target: {last_intervention.target_instance_id}")
        logger.info(f"Reason: {last_intervention.reason}")
        logger.info(f"Action: {last_intervention.action_taken}")

        # Verify intervention details
        assert last_intervention.target_instance_id == instance_ids[0]
        assert last_intervention.intervention_type == InterventionType.STATUS_CHECK
        assert last_intervention.success is True

        results.record_pass(test_name)

    except Exception as e:
        results.record_fail(test_name, str(e))
        raise


async def test_supervisor_monitoring_loop(supervisor: SupervisorAgent, results: LiveTestResults):
    """Test 7: Supervisor monitoring loop."""
    test_name = "Supervisor monitoring loop"
    logger.info(f"\n{'=' * 60}\nRunning: {test_name}\n{'=' * 60}")

    try:
        # Start supervisor
        await supervisor.start()
        assert supervisor.running is True, "Supervisor not running after start"
        logger.info("Supervisor monitoring loop started")

        # Let it run for a few cycles
        logger.info("Monitoring network for 15 seconds...")
        await asyncio.sleep(15)

        # Get health summary
        health = supervisor.get_network_health_summary()
        logger.info(f"Network health summary: {health}")

        # Verify health summary structure
        assert "total_interventions" in health
        assert "progress_snapshot" in health
        assert "running" in health
        assert health["running"] is True

        # Stop supervisor
        await supervisor.stop()
        assert supervisor.running is False, "Supervisor still running after stop"
        logger.info("Supervisor monitoring loop stopped")

        results.record_pass(test_name)

    except Exception as e:
        results.record_fail(test_name, str(e))
        raise


async def test_supervisor_network_health(supervisor: SupervisorAgent, results: LiveTestResults):
    """Test 8: Network health reporting."""
    test_name = "Network health reporting"
    logger.info(f"\n{'=' * 60}\nRunning: {test_name}\n{'=' * 60}")

    try:
        health = supervisor.get_network_health_summary()

        logger.info("Network Health Summary:")
        logger.info(f"  Total interventions: {health['total_interventions']}")
        logger.info(f"  Successful interventions: {health['successful_interventions']}")
        logger.info(f"  Failed interventions: {health['failed_interventions']}")
        logger.info(f"  Active issues: {health['active_issues']}")
        logger.info(f"  Running: {health['running']}")

        # Verify structure
        assert isinstance(health["total_interventions"], int)
        assert isinstance(health["successful_interventions"], int)
        assert isinstance(health["failed_interventions"], int)
        assert isinstance(health["running"], bool)

        results.record_pass(test_name)

    except Exception as e:
        results.record_fail(test_name, str(e))
        raise


async def cleanup_instances(
    manager: TmuxInstanceManager, instance_ids: list[str], results: LiveTestResults
):
    """Clean up test instances."""
    test_name = "Cleanup test instances"
    logger.info(f"\n{'=' * 60}\nRunning: {test_name}\n{'=' * 60}")

    try:
        for instance_id in instance_ids:
            logger.info(f"Terminating instance: {instance_id}")
            await manager.terminate_instance(instance_id)

        # Wait for cleanup
        await asyncio.sleep(2)

        # Verify instances are terminated
        status = manager.get_instance_status()
        for instance_id in instance_ids:
            if instance_id in status["instances"]:
                state = status["instances"][instance_id].get("state")
                logger.info(f"Instance {instance_id} state after termination: {state}")

        logger.info("All instances cleaned up")
        results.record_pass(test_name)

    except Exception as e:
        results.record_fail(test_name, str(e))


async def main():
    """Run all live tests."""
    logger.info("=" * 80)
    logger.info("SUPERVISOR AGENT LIVE INTEGRATION TEST")
    logger.info("Testing with real Madrox instances")
    logger.info("=" * 80)

    results = LiveTestResults()
    manager = None
    instance_ids = []
    supervisor = None

    try:
        # Initialize TmuxInstanceManager
        config = {
            "workspace_base_dir": "/tmp/supervisor_live_test",
            "max_concurrent_instances": 10,
        }

        logger.info("\nInitializing TmuxInstanceManager...")
        manager = TmuxInstanceManager(config)
        logger.info("TmuxInstanceManager initialized")

        # Test 1: Spawn instances
        instance_ids = await test_spawn_real_instances(manager, results)

        # Test 2: Attach supervisor
        supervisor = await test_attach_supervisor_to_network(manager, results)

        # Test 3: Detect instances
        await test_supervisor_detects_instances(manager, supervisor, instance_ids, results)

        # Test 4: Fetch transcripts
        await test_supervisor_fetches_transcripts(manager, supervisor, instance_ids, results)

        # Test 5: Send messages
        await test_send_message_to_instance(manager, instance_ids, results)

        # Test 6: Intervention execution
        await test_supervisor_intervention_execution(manager, supervisor, instance_ids, results)

        # Test 7: Monitoring loop
        await test_supervisor_monitoring_loop(supervisor, results)

        # Test 8: Health reporting
        await test_supervisor_network_health(supervisor, results)

    except Exception as e:
        logger.error(f"Test suite failed with error: {e}", exc_info=True)

    finally:
        # Cleanup
        if manager and instance_ids:
            await cleanup_instances(manager, instance_ids, results)

    # Print results
    results.print_summary()

    # Return exit code
    return 0 if results.tests_failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
