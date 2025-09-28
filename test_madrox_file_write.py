#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestrator.instance_manager import InstanceManager
from src.orchestrator.simple_models import OrchestratorConfig

async def test_file_write():
    config = OrchestratorConfig()
    manager = InstanceManager(config.to_dict())
    
    # Spawn a test instance
    print("Spawning test instance...")
    instance_id = await manager.spawn_instance(
        name="file-writer",
        role="general"
    )
    print(f"Instance ID: {instance_id}")
    
    # Ask it to write to its workspace
    print("\nAsking to write a file to workspace...")
    result = await manager.send_to_instance(
        instance_id=instance_id,
        message="Please write a simple text file called test.txt with the content 'Hello from Madrox!' to your current directory",
        wait_for_response=True,
        timeout_seconds=30
    )
    
    print(f"\nResponse: {result}")
    
    # Check if file was created
    workspace_dir = Path(f"/tmp/claude_orchestrator/{instance_id}")
    test_file = workspace_dir / "test.txt"
    
    if test_file.exists():
        print(f"\n✅ File created successfully at: {test_file}")
        print(f"Content: {test_file.read_text()}")
    else:
        print(f"\n❌ File not found at: {test_file}")
        print(f"Workspace contents: {list(workspace_dir.iterdir())}")
    
    # Cleanup
    await manager.terminate_instance(instance_id)
    print("\nInstance terminated")

if __name__ == "__main__":
    asyncio.run(test_file_write())
