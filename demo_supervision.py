"""Live demonstration of Supervisor Agent monitoring real Madrox instances.

This script shows supervision in action:
1. Spawns real Claude instances via Madrox
2. Attaches supervisor to monitor them
3. Shows autonomous detection and monitoring
4. Demonstrates network health reporting
"""

import asyncio
import sys
from pathlib import Path

# Add both src directories to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "madrox" / "src"))

import logging
from orchestrator.instance_manager import InstanceManager
from supervision.integration import spawn_supervisor
from supervision.supervisor import SupervisionConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Run supervision demonstration."""

    print("=" * 80)
    print("MADROX AUTONOMOUS SUPERVISION - LIVE DEMONSTRATION")
    print("=" * 80)
    print()

    # Initialize InstanceManager
    print("📦 Initializing Madrox InstanceManager...")
    config = {
        "workspace_base_dir": "/tmp/claude_orchestrator",
        "log_dir": "/tmp/madrox_logs",
        "log_level": "INFO"
    }
    manager = InstanceManager(config)
    print("✅ InstanceManager ready")
    print()

    # Spawn worker instances
    print("🚀 Spawning 3 worker instances...")
    worker_ids = []

    for i, role in enumerate(["frontend_developer", "backend_developer", "testing_specialist"], 1):
        print(f"  Spawning worker-{i} ({role})...")
        instance_id = await manager.spawn_instance(
            name=f"worker-{i}",
            role=role,
            enable_madrox=False,
            bypass_isolation=False,
            wait_for_ready=True
        )
        worker_ids.append(instance_id)
        print(f"  ✅ worker-{i}: {instance_id[:12]}...")

    print(f"\n✅ All 3 workers spawned successfully")
    print()

    # Configure and spawn supervisor
    print("🔍 Spawning Supervisor Agent...")
    supervision_config = SupervisionConfig(
        stuck_threshold_seconds=120,        # 2 minutes
        waiting_threshold_seconds=60,       # 1 minute
        error_loop_threshold=3,
        max_interventions_per_instance=3,
        evaluation_interval_seconds=10,     # Check every 10 seconds (fast for demo)
    )

    supervisor_id, supervisor = await spawn_supervisor(
        instance_manager=manager,
        config=supervision_config,
        auto_start=True  # Start monitoring immediately
    )

    print(f"✅ Supervisor spawned: {supervisor_id[:12]}...")
    print(f"✅ Monitoring active with {supervision_config.evaluation_interval_seconds}s evaluation interval")
    print()

    # Show initial network status
    print("📊 Initial Network Status:")
    status = manager.get_instance_status()
    print(f"  Total instances: {status['total_instances']}")
    print(f"  Active instances: {status['active_instances']}")
    print()

    # Let supervisor run and monitor
    print("⏱️  Running supervision for 30 seconds...")
    print("  (Supervisor is detecting instances and monitoring health)")
    print()

    for i in range(6):
        await asyncio.sleep(5)

        # Get active instances
        active = await supervisor._get_active_instances()
        health = supervisor.get_network_health_summary()

        print(f"  [{i*5}s] Active instances: {len(active)}, "
              f"Interventions: {health['total_interventions']}, "
              f"Issues: {health['active_issues']}")

    print()

    # Show final health summary
    print("=" * 80)
    print("📈 FINAL NETWORK HEALTH REPORT")
    print("=" * 80)

    health = supervisor.get_network_health_summary()

    print(f"\n🔍 Supervision Summary:")
    print(f"  Total Interventions: {health['total_interventions']}")
    print(f"  Successful: {health['successful_interventions']}")
    print(f"  Failed: {health['failed_interventions']}")
    print(f"  Active Issues: {health['active_issues']}")
    print(f"  Instances Monitored: {len(health['instances_intervened'])}")
    print(f"  Supervisor Running: {health['running']}")

    print(f"\n📊 Progress Snapshot:")
    snapshot = health['progress_snapshot']
    print(f"  Total Tasks: {snapshot['total_tasks']}")
    print(f"  Completed: {snapshot['completed']}")
    print(f"  In Progress: {snapshot['in_progress']}")
    print(f"  Blocked: {snapshot['blocked']}")
    print(f"  Failed: {snapshot['failed']}")
    print(f"  Completion: {snapshot['completion_percentage']:.1f}%")

    print(f"\n👥 Instances Status:")
    for instance_id in worker_ids + [supervisor_id]:
        inst = status['instances'].get(instance_id, {})
        name = inst.get('name', 'unknown')
        state = inst.get('state', 'unknown')
        role = inst.get('role', 'unknown')
        print(f"  {name:20} [{state:12}] ({role})")

    print()

    # Show intervention history if any
    if supervisor.intervention_history:
        print("📝 Intervention History:")
        for intervention in supervisor.intervention_history:
            print(f"  - {intervention.intervention_type.value}: "
                  f"{intervention.target_instance_id[:12]}... "
                  f"at {intervention.timestamp.strftime('%H:%M:%S')}")
    else:
        print("✅ No interventions needed - all instances healthy!")

    print()

    # Cleanup
    print("🧹 Cleaning up...")

    # Stop supervisor
    await supervisor.stop()
    print("  ✅ Supervisor stopped")

    # Terminate all instances
    for instance_id in worker_ids + [supervisor_id]:
        await manager.terminate_instance(instance_id, force=True)
    print(f"  ✅ Terminated {len(worker_ids) + 1} instances")

    print()
    print("=" * 80)
    print("🎉 DEMONSTRATION COMPLETE")
    print("=" * 80)
    print()
    print("Key Features Demonstrated:")
    print("  ✅ Autonomous instance spawning")
    print("  ✅ Supervisor monitoring and detection")
    print("  ✅ Real-time network health tracking")
    print("  ✅ Progress snapshot aggregation")
    print("  ✅ Clean shutdown and cleanup")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        sys.exit(1)
