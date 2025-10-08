"""Quick demo: Attach supervisor to existing instances."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "madrox" / "src"))

import logging
from orchestrator.instance_manager import InstanceManager
from supervision.supervisor import SupervisorAgent, SupervisionConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    print("\n" + "=" * 80)
    print("🔍 SUPERVISION DEMO - Monitoring Existing Instances")
    print("=" * 80 + "\n")

    # Initialize manager
    print("📦 Initializing InstanceManager...")
    config = {
        "workspace_base_dir": "/tmp/claude_orchestrator",
        "log_dir": "/tmp/madrox_logs",
        "log_level": "INFO"
    }
    manager = InstanceManager(config)
    print("✅ InstanceManager ready\n")

    # Get existing instances
    status = manager.get_instance_status()
    instances = status.get("instances", {})
    active_ids = [
        iid for iid, inst in instances.items()
        if inst.get("state") in ["running", "busy", "idle"]
    ]

    print(f"📊 Found {len(active_ids)} active instances:")
    for iid in active_ids[:5]:  # Show first 5
        inst = instances[iid]
        print(f"   - {inst.get('name', 'unknown'):20} [{inst.get('state', 'unknown'):10}] {iid[:12]}...")
    print()

    if not active_ids:
        print("⚠️  No active instances found. Spawn some first!")
        return

    # Create and start supervisor
    print("🤖 Creating supervisor agent...")
    supervision_config = SupervisionConfig(
        stuck_threshold_seconds=120,
        waiting_threshold_seconds=60,
        error_loop_threshold=3,
        max_interventions_per_instance=3,
        evaluation_interval_seconds=5,  # Fast evaluation
    )

    supervisor = SupervisorAgent(
        instance_manager=manager,
        config=supervision_config
    )
    print("✅ Supervisor created\n")

    # Start monitoring
    print("▶️  Starting autonomous monitoring...")
    await supervisor.start()
    print(f"✅ Supervisor monitoring {len(active_ids)} instances\n")

    # Monitor for 30 seconds
    print("🔍 Monitoring for 30 seconds...")
    print("   (Supervisor evaluates every 5 seconds)\n")

    for i in range(6):  # 6 checks over 30 seconds
        await asyncio.sleep(5)

        # Get health summary
        health = supervisor.get_network_health_summary()
        active = await supervisor._get_active_instances()

        print(f"[{(i+1)*5:2d}s] ", end="")
        print(f"Active: {len(active):2d} | ", end="")
        print(f"Interventions: {health['total_interventions']:2d} | ", end="")
        print(f"Issues: {health['active_issues']:2d}")

    # Final report
    print("\n" + "=" * 80)
    print("📊 SUPERVISION SUMMARY")
    print("=" * 80 + "\n")

    health = supervisor.get_network_health_summary()

    print("🔍 Monitoring Results:")
    print(f"   Total Interventions: {health['total_interventions']}")
    print(f"   Successful: {health['successful_interventions']}")
    print(f"   Failed: {health['failed_interventions']}")
    print(f"   Active Issues: {health['active_issues']}")

    if supervisor.intervention_history:
        print(f"\n📝 Recent Interventions:")
        for intervention in supervisor.intervention_history[-5:]:
            target = intervention.target_instance_id[:12]
            itype = intervention.intervention_type.value
            time = intervention.timestamp.strftime('%H:%M:%S')
            success = "✅" if intervention.success else "❌"
            print(f"   [{time}] {success} {itype:20} → {target}...")
    else:
        print("\n✅ No interventions needed - all instances healthy!")

    print(f"\n📈 Progress Tracking:")
    snapshot = health['progress_snapshot']
    print(f"   Total Tasks: {snapshot['total_tasks']}")
    print(f"   Completed: {snapshot['completed']}")
    print(f"   In Progress: {snapshot['in_progress']}")
    print(f"   Blocked: {snapshot['blocked']}")

    # Cleanup
    print("\n⏹️  Stopping supervisor...")
    await supervisor.stop()
    print("✅ Supervisor stopped\n")

    print("=" * 80)
    print("🎉 DEMONSTRATION COMPLETE")
    print("=" * 80)
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        raise
