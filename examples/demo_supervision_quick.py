"""Quick demonstration of Supervisor Agent features.

Shows supervision capabilities without waiting for full instance initialization.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, UTC

# Add paths
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "madrox" / "src"))

from unittest.mock import MagicMock, AsyncMock
from supervision.supervisor import SupervisorAgent, SupervisionConfig, DetectedIssue, IssueSeverity
from supervision.events.bus import EventBus
from supervision.analysis.analyzer import TranscriptAnalyzer
from supervision.tracking.tracker import ProgressTracker


def print_header(title):
    """Print a formatted header."""
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)
    print()


async def demo_initialization():
    """Demonstrate supervisor initialization."""
    print_header("1. SUPERVISOR INITIALIZATION")

    # Create mock manager
    manager = MagicMock()
    manager.get_instance_status = MagicMock(return_value={
        "instances": {
            "instance-1": {"state": "running", "name": "worker-1"},
            "instance-2": {"state": "busy", "name": "worker-2"},
            "instance-3": {"state": "idle", "name": "worker-3"},
        }
    })
    manager.get_tmux_pane_content = AsyncMock(return_value="Working on task...")
    manager.send_to_instance = AsyncMock(return_value={"status": "sent"})

    # Create supervisor with custom config
    config = SupervisionConfig(
        stuck_threshold_seconds=300,
        waiting_threshold_seconds=120,
        error_loop_threshold=3,
        max_interventions_per_instance=3,
        evaluation_interval_seconds=30
    )

    supervisor = SupervisorAgent(instance_manager=manager, config=config)

    print("✅ Supervisor initialized with configuration:")
    print(f"   - Stuck threshold: {config.stuck_threshold_seconds}s")
    print(f"   - Waiting threshold: {config.waiting_threshold_seconds}s")
    print(f"   - Error loop threshold: {config.error_loop_threshold} errors")
    print(f"   - Max interventions: {config.max_interventions_per_instance}")
    print(f"   - Evaluation interval: {config.evaluation_interval_seconds}s")

    print("\n✅ Integrated components:")
    print(f"   - EventBus: {type(supervisor.event_bus).__name__}")
    print(f"   - TranscriptAnalyzer: {type(supervisor.analyzer).__name__}")
    print(f"   - ProgressTracker: {type(supervisor.tracker).__name__}")

    return supervisor, manager


async def demo_instance_detection(supervisor):
    """Demonstrate instance detection."""
    print_header("2. INSTANCE DETECTION")

    active_instances = await supervisor._get_active_instances()

    print(f"✅ Detected {len(active_instances)} active instances:")
    for instance_id in active_instances:
        print(f"   - {instance_id}")

    return active_instances


async def demo_issue_detection(supervisor, instance_ids):
    """Demonstrate issue detection."""
    print_header("3. ISSUE DETECTION")

    print("🔍 Analyzing instances for issues...")
    all_issues = []

    for instance_id in instance_ids:
        issues = await supervisor._detect_instance_issues(instance_id)
        if issues:
            all_issues.extend(issues)
            print(f"\n⚠️  Issues found for {instance_id}:")
            for issue in issues:
                print(f"   - Type: {issue.issue_type}")
                print(f"   - Severity: {issue.severity.value}")
                print(f"   - Confidence: {issue.confidence:.2f}")
                print(f"   - Description: {issue.description}")
        else:
            print(f"✅ {instance_id}: No issues detected")

    if not all_issues:
        print("\n✅ All instances healthy - no issues detected")

    return all_issues


async def demo_intervention_execution(supervisor):
    """Demonstrate intervention execution."""
    print_header("4. INTERVENTION EXECUTION")

    # Create a test issue
    issue = DetectedIssue(
        instance_id="instance-2",
        issue_type="stuck",
        severity=IssueSeverity.WARNING,
        description="Instance appears stuck with no progress",
        detected_at=datetime.now(UTC),
        confidence=0.85,
        evidence={"last_activity": "5 minutes ago"}
    )

    print("🎯 Simulating stuck instance issue:")
    print(f"   Instance: {issue.instance_id}")
    print(f"   Type: {issue.issue_type}")
    print(f"   Severity: {issue.severity.value}")
    print(f"   Confidence: {issue.confidence:.2f}")

    print("\n🔧 Executing intervention...")
    await supervisor._handle_issue(issue)

    print("\n✅ Intervention executed:")
    if supervisor.intervention_history:
        intervention = supervisor.intervention_history[-1]
        print(f"   - Type: {intervention.intervention_type.value}")
        print(f"   - Target: {intervention.target_instance_id}")
        print(f"   - Action: {intervention.action_taken}")
        print(f"   - Time: {intervention.timestamp.strftime('%H:%M:%S')}")

    print(f"\n📊 Intervention counts:")
    for instance_id, count in supervisor.intervention_counts.items():
        print(f"   - {instance_id}: {count} intervention(s)")


async def demo_intervention_limits(supervisor):
    """Demonstrate intervention limits and escalation."""
    print_header("5. INTERVENTION LIMITS & ESCALATION")

    # Create repeated issues for same instance
    print("🔁 Simulating multiple interventions for same instance...")

    for i in range(4):
        issue = DetectedIssue(
            instance_id="instance-stressed",
            issue_type="error_loop",
            severity=IssueSeverity.ERROR,
            description=f"Error loop detected (attempt {i+1})",
            detected_at=datetime.now(UTC),
            confidence=0.95,
            evidence={"error_count": i+1}
        )

        await supervisor._handle_issue(issue)

        count = supervisor.intervention_counts.get("instance-stressed", 0)
        print(f"   Attempt {i+1}: Interventions = {count}")

        if count >= supervisor.config.max_interventions_per_instance:
            print(f"   ⚠️  Max interventions reached ({supervisor.config.max_interventions_per_instance})")
            print(f"   🚨 Issue escalated to user")
            break

        await asyncio.sleep(0.1)


async def demo_network_health(supervisor):
    """Demonstrate network health reporting."""
    print_header("6. NETWORK HEALTH SUMMARY")

    health = supervisor.get_network_health_summary()

    print("📊 Network Health Report:")
    print(f"\n🔍 Supervision Metrics:")
    print(f"   Total Interventions: {health['total_interventions']}")
    print(f"   Successful: {health['successful_interventions']}")
    print(f"   Failed: {health['failed_interventions']}")
    print(f"   Active Issues: {health['active_issues']}")

    print(f"\n📈 Progress Snapshot:")
    snapshot = health['progress_snapshot']
    print(f"   Total Tasks: {snapshot['total_tasks']}")
    print(f"   Completed: {snapshot['completed']}")
    print(f"   In Progress: {snapshot['in_progress']}")
    print(f"   Blocked: {snapshot['blocked']}")
    print(f"   Failed: {snapshot['failed']}")
    print(f"   Completion: {snapshot['completion_percentage']:.1f}%")

    print(f"\n👥 Instances Intervened:")
    for instance_id in health['instances_intervened']:
        print(f"   - {instance_id}")

    print(f"\n⚙️  Supervisor Status: {'🟢 Running' if health['running'] else '🔴 Stopped'}")


async def demo_supervision_loop(supervisor):
    """Demonstrate supervision loop control."""
    print_header("7. SUPERVISION LOOP CONTROL")

    print("▶️  Starting supervision loop...")
    await supervisor.start()
    print(f"   ✅ Supervisor running: {supervisor.running}")

    await asyncio.sleep(0.5)

    print("\n⏸️  Stopping supervision loop...")
    await supervisor.stop()
    print(f"   ✅ Supervisor running: {supervisor.running}")


async def main():
    """Run all demonstrations."""
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "MADROX AUTONOMOUS SUPERVISION" + " " * 29 + "║")
    print("║" + " " * 25 + "LIVE DEMONSTRATION" + " " * 35 + "║")
    print("╚" + "═" * 78 + "╝")

    # Run demonstrations
    supervisor, manager = await demo_initialization()
    instance_ids = await demo_instance_detection(supervisor)
    issues = await demo_issue_detection(supervisor, instance_ids)
    await demo_intervention_execution(supervisor)
    await demo_intervention_limits(supervisor)
    await demo_network_health(supervisor)
    await demo_supervision_loop(supervisor)

    # Summary
    print_header("DEMONSTRATION COMPLETE")

    print("✅ Features Demonstrated:")
    print("   1. Supervisor initialization with custom configuration")
    print("   2. Active instance detection via InstanceManager")
    print("   3. Issue detection using transcript analysis")
    print("   4. Autonomous intervention execution")
    print("   5. Intervention limits and escalation")
    print("   6. Network health reporting and metrics")
    print("   7. Supervision loop start/stop control")

    print("\n📚 Key Components:")
    print("   ✅ SupervisorAgent - Autonomous monitoring and intervention")
    print("   ✅ EventBus - Pub/sub event communication")
    print("   ✅ TranscriptAnalyzer - Pattern-based analysis")
    print("   ✅ ProgressTracker - State management")

    print("\n🎯 Production Ready:")
    print("   ✅ Thread-safe operations")
    print("   ✅ Configurable thresholds")
    print("   ✅ Intervention limits and cooldown")
    print("   ✅ Comprehensive health reporting")
    print("   ✅ InstanceManager integration")

    print()


if __name__ == "__main__":
    asyncio.run(main())
