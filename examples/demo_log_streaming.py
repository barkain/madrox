#!/usr/bin/env python3
"""Demo script showing the log streaming infrastructure.

This script demonstrates:
1. Setting up the log stream handler
2. Logging system messages
3. Logging audit events
4. How logs are categorized and formatted
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.log_stream_handler import (
    audit_log,
    get_log_stream_handler,
    setup_log_streaming,
)


class MockWebSocket:
    """Mock WebSocket for demo purposes."""

    async def send_json(self, data):
        """Print JSON messages in a readable format."""
        import json

        msg_type = data.get("type", "unknown")
        timestamp = data.get("data", {}).get("timestamp", "")

        if msg_type == "system_log":
            log_data = data["data"]
            print(f"\n[SYSTEM LOG] {timestamp}")
            print(f"  Level: {log_data['level']}")
            print(f"  Logger: {log_data['logger']}")
            print(f"  Message: {log_data['message']}")
            print(f"  Location: {log_data['module']}.{log_data['function']}:{log_data['line']}")

        elif msg_type == "audit_log":
            log_data = data["data"]
            print(f"\n[AUDIT LOG] {timestamp}")
            print(f"  Level: {log_data['level']}")
            print(f"  Logger: {log_data['logger']}")
            print(f"  Message: {log_data['message']}")
            if "action" in log_data:
                print(f"  Action: {log_data['action']}")
            if "metadata" in log_data:
                print(f"  Metadata: {json.dumps(log_data['metadata'], indent=4)}")


async def demo_log_streaming():
    """Demonstrate the log streaming infrastructure."""
    print("=" * 80)
    print("Log Streaming Infrastructure Demo")
    print("=" * 80)

    # 1. Setup log streaming
    print("\n1. Setting up log streaming...")
    loop = asyncio.get_event_loop()
    setup_log_streaming(loop)
    print("   ✓ Log streaming configured")

    # 2. Add mock WebSocket client
    print("\n2. Adding WebSocket client...")
    handler = get_log_stream_handler()
    mock_ws = MockWebSocket()
    handler.add_client(mock_ws)
    print("   ✓ WebSocket client connected")

    # 3. Create loggers
    print("\n3. Creating loggers...")
    system_logger = logging.getLogger("madrox.server")
    system_logger.setLevel(logging.INFO)
    audit_logger = logging.getLogger("audit.instance")
    audit_logger.setLevel(logging.INFO)
    print("   ✓ Loggers created")

    # 4. Generate system logs
    print("\n4. Generating system logs...")
    print("-" * 80)

    system_logger.info("Server starting on port 8001")
    await asyncio.sleep(0.1)

    system_logger.info(
        "Instance spawned successfully", extra={"instance_id": "abc-123", "instance_name": "main-orchestrator"}
    )
    await asyncio.sleep(0.1)

    system_logger.warning("High memory usage detected", extra={"memory_mb": 512})
    await asyncio.sleep(0.1)

    # 5. Generate audit logs
    print("\n5. Generating audit logs...")
    print("-" * 80)

    audit_log(
        audit_logger,
        "Instance main-orchestrator spawned",
        action="instance_spawn",
        metadata={"instance_id": "abc-123", "role": "orchestrator", "model": "claude-4-sonnet"},
    )
    await asyncio.sleep(0.1)

    audit_log(
        audit_logger,
        "Message sent to instance abc-123",
        action="message_sent",
        metadata={
            "instance_id": "abc-123",
            "message_length": 150,
            "priority": 1,
        },
    )
    await asyncio.sleep(0.1)

    audit_log(
        audit_logger,
        "Instance abc-123 terminated",
        action="instance_terminate",
        metadata={"instance_id": "abc-123", "reason": "task_complete", "uptime_seconds": 300},
        level=logging.WARNING,
    )
    await asyncio.sleep(0.1)

    # 6. Demonstrate mixed logging
    print("\n6. Mixed system and audit logging...")
    print("-" * 80)

    system_logger.info("Processing coordination task")
    await asyncio.sleep(0.05)

    audit_log(
        audit_logger,
        "Coordination task started",
        action="coordination_start",
        metadata={"coordinator_id": "coord-1", "participants": ["abc-123", "def-456"]},
    )
    await asyncio.sleep(0.05)

    system_logger.info("Sending messages to 2 participants")
    await asyncio.sleep(0.05)

    audit_log(
        audit_logger,
        "Coordination task completed",
        action="coordination_complete",
        metadata={"coordinator_id": "coord-1", "duration_seconds": 5.2, "status": "success"},
    )
    await asyncio.sleep(0.1)

    # 7. Cleanup
    print("\n7. Cleaning up...")
    handler.remove_client(mock_ws)
    print("   ✓ WebSocket client disconnected")

    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print("\nKey Points:")
    print("  • System logs include module/function/line information")
    print("  • Audit logs include action and metadata fields")
    print("  • Logs are automatically categorized based on logger name or flags")
    print("  • All logs are streamed in real-time to WebSocket clients")
    print("  • The system supports multiple concurrent WebSocket connections")


if __name__ == "__main__":
    asyncio.run(demo_log_streaming())
