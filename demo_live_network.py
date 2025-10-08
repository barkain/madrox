"""Live demonstration: Real Madrox network with active supervision.

This spawns real Claude instances, gives them work, and shows the supervisor
monitoring them in real-time.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "madrox" / "src"))

import logging
from orchestrator.instance_manager import InstanceManager
from supervision.integration import spawn_supervisor, spawn_supervised_network
from supervision.supervisor import SupervisionConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    print("\n" + "=" * 80)
    print("🚀 MADROX SUPERVISED NETWORK - LIVE DEMONSTRATION")
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

    # Spawn supervised network
    print("🌐 Spawning supervised network (3 workers + 1 supervisor)...")
    print("   This will take ~30 seconds for Claude instances to initialize...\n")

    network = await spawn_supervised_network(
        instance_manager=manager,
        participant_configs=[
            {
                "name": "code-analyzer",
                "role": "backend_developer",
                "bypass_isolation": False,
                "enable_madrox": False,
            },
            {
                "name": "code-tester",
                "role": "testing_specialist",
                "bypass_isolation": False,
                "enable_madrox": False,
            },
            {
                "name": "code-reviewer",
                "role": "code_reviewer",
                "bypass_isolation": False,
                "enable_madrox": False,
            },
        ],
        supervision_config=SupervisionConfig(
            stuck_threshold_seconds=60,
            waiting_threshold_seconds=30,
            evaluation_interval_seconds=5,  # Check every 5 seconds
        )
    )

    supervisor = network["supervisor_agent"]
    supervisor_id = network["supervisor_id"]
    participant_ids = network["participant_ids"]

    print(f"✅ Network spawned successfully!")
    print(f"   Supervisor: {supervisor_id[:12]}...")
    print(f"   Workers: {len(participant_ids)}")
    for i, pid in enumerate(participant_ids, 1):
        print(f"     {i}. {pid[:12]}...")
    print()

    # Give workers some tasks
    print("📝 Assigning tasks to workers...")

    tasks = [
        ("code-analyzer", "Analyze this Python function for potential bugs:\n\ndef calculate_total(items):\n    total = 0\n    for item in items:\n        total += item['price']\n    return total"),
        ("code-tester", "Write pytest tests for a function that validates email addresses"),
        ("code-reviewer", "Review this code and provide feedback:\n\nclass UserManager:\n    def __init__(self):\n        self.users = {}\n    def add_user(self, name, email):\n        self.users[name] = email"),
    ]

    for i, (worker_name, task) in enumerate(tasks):
        worker_id = participant_ids[i]
        print(f"   → Sending task to {worker_name}...")
        await manager.send_to_instance(
            instance_id=worker_id,
            message=task,
            wait_for_response=False
        )

    print("✅ All tasks assigned\n")

    # Monitor the network
    print("=" * 80)
    print("🔍 MONITORING NETWORK (60 seconds)")
    print("=" * 80)
    print()

    for i in range(12):  # 12 checks over 60 seconds
        await asyncio.sleep(5)

        # Get current status
        status = manager.get_instance_status()
        health = supervisor.get_network_health_summary()
        active = await supervisor._get_active_instances()

        # Print update
        print(f"[{(i+1)*5:2d}s] ", end="")
        print(f"Active: {len(active)}/{len(participant_ids)+1} | ", end="")
        print(f"Interventions: {health['total_interventions']} | ", end="")
        print(f"Issues: {health['active_issues']}")

        # Show instance states
        if (i + 1) % 3 == 0:  # Every 15 seconds, show details
            print()
            for pid in participant_ids:
                inst = status['instances'].get(pid, {})
                name = inst.get('name', 'unknown')
                state = inst.get('state', 'unknown')
                print(f"      {name:20} [{state}]")
            print()

    # Final report
    print("\n" + "=" * 80)
    print("📊 FINAL NETWORK REPORT")
    print("=" * 80 + "\n")

    health = supervisor.get_network_health_summary()
    status = manager.get_instance_status()

    print("🔍 Supervision Summary:")
    print(f"   Total Interventions: {health['total_interventions']}")
    print(f"   Successful: {health['successful_interventions']}")
    print(f"   Failed: {health['failed_interventions']}")
    print(f"   Active Issues: {health['active_issues']}")

    print(f"\n📈 Progress Tracking:")
    snapshot = health['progress_snapshot']
    print(f"   Total Tasks: {snapshot['total_tasks']}")
    print(f"   Completed: {snapshot['completed']}")
    print(f"   In Progress: {snapshot['in_progress']}")
    print(f"   Blocked: {snapshot['blocked']}")

    print(f"\n👥 Instance States:")
    all_instances = participant_ids + [supervisor_id]
    for inst_id in all_instances:
        inst = status['instances'].get(inst_id, {})
        name = inst.get('name', 'unknown')
        state = inst.get('state', 'unknown')
        role = inst.get('role', 'unknown')
        is_supervisor = ' [SUPERVISOR]' if inst_id == supervisor_id else ''
        print(f"   {name:20} [{state:12}] ({role}){is_supervisor}")

    if supervisor.intervention_history:
        print(f"\n📝 Intervention History:")
        for intervention in supervisor.intervention_history[-5:]:  # Last 5
            target = intervention.target_instance_id[:12]
            itype = intervention.intervention_type.value
            time = intervention.timestamp.strftime('%H:%M:%S')
            print(f"   [{time}] {itype:20} → {target}...")

    # Cleanup
    print("\n🧹 Cleaning up...")
    await supervisor.stop()

    for inst_id in all_instances:
        try:
            await manager.terminate_instance(inst_id, force=True)
        except:
            pass

    print("✅ All instances terminated\n")

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
