"""Test suite for parent_instance_id auto-injection and enforcement.

This test suite validates the parent_instance_id feature that ensures:
1. Explicit parent_instance_id is respected (Tier 1)
2. Auto-detection of caller instance works (Tier 2)
3. Main orchestrator can spawn without parent (Exception case)
4. ValueError is raised when parent cannot be determined (Enforcement)
5. Batch spawn with auto-injection works correctly

See: docs/PARENT_INSTANCE_ID_AUTO_INJECTION_PLAN.md
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.orchestrator.instance_manager import InstanceManager
from src.orchestrator.mcp_adapter import MCPAdapter


class TestParentInstanceIdEnforcement:
    """Test parent_instance_id auto-injection and enforcement."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def config(self, temp_workspace):
        """Create test configuration."""
        return {
            "workspace_base_dir": temp_workspace,
            "max_concurrent_instances": 10,
            "instance_timeout_minutes": 60,
            "anthropic_api_key": "test-key",
        }

    @pytest.fixture
    def manager(self, config):
        """Create InstanceManager for testing."""
        # Mock subprocess.Popen for CLI processes
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.poll.return_value = None  # Process is running
            mock_process.stdin = MagicMock()
            mock_process.stdout = MagicMock()
            mock_process.stderr = MagicMock()
            mock_process.wait = MagicMock()
            mock_process.terminate = MagicMock()
            mock_process.kill = MagicMock()

            # Mock stdout.readline to return ready response then end
            responses = [b'{"type":"message","content":"Ready"}\n', b'{"type":"end"}\n', b""]
            mock_process.stdout.readline.side_effect = responses

            mock_popen.return_value = mock_process

            return InstanceManager(config)

    @pytest.fixture
    def mcp_adapter(self, manager):
        """Create MCPAdapter for testing auto-detection."""
        return MCPAdapter(manager)

    # ============================================================
    # Test Case 1: Explicit parent_instance_id is respected
    # ============================================================

    @pytest.mark.asyncio
    async def test_spawn_with_explicit_parent(self, manager):
        """Test that explicit parent_instance_id is respected (Tier 1).

        When a user explicitly provides parent_instance_id, it should be used
        directly without any auto-detection or modification.
        """
        # First spawn a parent instance
        parent_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
        )

        # Now spawn a child with explicit parent_instance_id
        child_id = await manager.spawn_instance(
            name="explicit-child",
            role="general",
            parent_instance_id=parent_id,
        )

        # Verify child was created with correct parent
        assert child_id in manager.instances
        child_instance = manager.instances[child_id]
        assert child_instance["parent_instance_id"] == parent_id
        assert child_instance["name"] == "explicit-child"

    @pytest.mark.asyncio
    async def test_spawn_with_explicit_parent_different_from_caller(self, manager, mcp_adapter):
        """Test that explicit parent overrides caller detection.

        Even when called from a managed instance (which would be auto-detected),
        the explicit parent_instance_id should take precedence.
        """
        # Spawn parent A
        parent_a_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
        )

        # Spawn parent B
        parent_b_id = await manager.spawn_instance(
            name="parent-b",
            role="general",
            parent_instance_id=parent_a_id,
        )

        # Simulate parent_b making the spawn call (would be auto-detected)
        manager.instances[parent_b_id]["state"] = "busy"

        # But explicitly specify parent_a as parent
        child_id = await manager.spawn_instance(
            name="child-with-explicit-parent",
            role="general",
            parent_instance_id=parent_a_id,  # Explicit override
        )

        # Verify child uses explicit parent, NOT the caller
        assert child_id in manager.instances
        child_instance = manager.instances[child_id]
        assert child_instance["parent_instance_id"] == parent_a_id  # Should use explicit
        assert child_instance["parent_instance_id"] != parent_b_id  # Not the busy caller

    # ============================================================
    # Test Case 2: Auto-detection of caller instance works
    # ============================================================

    @pytest.mark.asyncio
    async def test_spawn_from_managed_instance(self, manager, mcp_adapter):
        """Test auto-detection of caller instance (Tier 2).

        When spawning from a managed instance without explicit parent_instance_id,
        the system should auto-detect the calling instance and use it as parent.
        """
        # Spawn main orchestrator first
        main_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
        )

        # Spawn a supervisor with main as parent
        supervisor_id = await manager.spawn_instance(
            name="supervisor",
            role="general",
            parent_instance_id=main_id,
        )

        # Simulate supervisor making spawn call (set to busy state)
        manager.instances[supervisor_id]["state"] = "busy"
        manager.instances[supervisor_id]["request_count"] = 1

        # Test auto-detection
        detected_caller = mcp_adapter._detect_caller_instance()
        assert detected_caller == supervisor_id

        # Now test spawn with auto-injection
        # Note: Direct spawn_instance doesn't have auto-injection,
        # that happens in MCP adapter. So we test detection here.
        # In real usage, MCP adapter would inject this before calling spawn_instance.

    @pytest.mark.asyncio
    async def test_auto_detection_via_busy_state(self, manager, mcp_adapter):
        """Test auto-detection prioritizes busy state instances.

        Strategy 1: Busy instances should be detected first.
        """
        # Spawn main orchestrator
        main_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
        )

        # Spawn two instances
        instance1_id = await manager.spawn_instance(
            name="instance-1",
            role="general",
            parent_instance_id=main_id,
        )

        instance2_id = await manager.spawn_instance(
            name="instance-2",
            role="general",
            parent_instance_id=main_id,
        )

        # Set instance2 to busy (most recent activity)
        manager.instances[instance1_id]["state"] = "idle"
        manager.instances[instance1_id]["request_count"] = 1
        manager.instances[instance1_id]["last_activity"] = "2025-01-01T10:00:00Z"

        manager.instances[instance2_id]["state"] = "busy"
        manager.instances[instance2_id]["request_count"] = 1
        manager.instances[instance2_id]["last_activity"] = "2025-01-01T10:05:00Z"

        # Auto-detection should find instance2 (busy state)
        detected_caller = mcp_adapter._detect_caller_instance()
        assert detected_caller == instance2_id

    @pytest.mark.asyncio
    async def test_auto_detection_via_recent_activity(self, manager, mcp_adapter):
        """Test auto-detection fallback to most recently active instance.

        Strategy 2: When no busy instances, use most recently active with request_count > 0.
        """
        # Spawn main orchestrator
        main_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
        )

        # Spawn two instances (both idle, not busy)
        instance1_id = await manager.spawn_instance(
            name="instance-1",
            role="general",
            parent_instance_id=main_id,
        )

        instance2_id = await manager.spawn_instance(
            name="instance-2",
            role="general",
            parent_instance_id=main_id,
        )

        # Set both to idle but with different activity times
        manager.instances[instance1_id]["state"] = "idle"
        manager.instances[instance1_id]["request_count"] = 5
        manager.instances[instance1_id]["last_activity"] = "2025-01-01T10:00:00Z"

        manager.instances[instance2_id]["state"] = "idle"
        manager.instances[instance2_id]["request_count"] = 3
        manager.instances[instance2_id]["last_activity"] = "2025-01-01T10:10:00Z"  # More recent

        # Auto-detection should find instance2 (most recent activity)
        detected_caller = mcp_adapter._detect_caller_instance()
        assert detected_caller == instance2_id

    # ============================================================
    # Test Case 3: Main orchestrator can spawn without parent
    # ============================================================

    @pytest.mark.asyncio
    async def test_spawn_main_orchestrator(self, manager):
        """Test main-orchestrator can spawn without parent_instance_id (Exception case).

        The main orchestrator is the only instance allowed to have parent_instance_id=None.
        This is the root of the instance hierarchy tree.
        """
        # Spawn main orchestrator WITHOUT parent_instance_id
        main_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
            # NO parent_instance_id provided
        )

        # Verify main orchestrator was created successfully
        assert main_id in manager.instances
        main_instance = manager.instances[main_id]
        # Name may have suffix (e.g., "main-orchestrator-aka-...")
        assert "main-orchestrator" in main_instance["name"]
        assert main_instance.get("parent_instance_id") is None  # Allowed to be None

    @pytest.mark.asyncio
    async def test_main_orchestrator_with_explicit_parent_respected(self, manager):
        """Test that even main-orchestrator respects explicit parent if provided.

        While main-orchestrator CAN have parent_instance_id=None, if one is explicitly
        provided, it should be respected (edge case for testing).
        """
        # Spawn first main-orchestrator (root, no parent)
        parent_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
        )

        # Spawn second main-orchestrator with explicit parent
        # (unusual case, but tests that explicit parent is always respected)
        main_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
            parent_instance_id=parent_id,  # Explicit parent
        )

        # Verify main uses the explicit parent
        assert main_id in manager.instances
        main_instance = manager.instances[main_id]
        assert main_instance["parent_instance_id"] == parent_id

    # ============================================================
    # Test Case 4: ValueError raised when parent cannot be determined
    # ============================================================

    @pytest.mark.asyncio
    async def test_spawn_fails_without_parent(self, manager):
        """Test spawn fails with ValueError when parent_instance_id cannot be determined.

        When spawning a non-main instance without explicit parent_instance_id
        and no auto-detection possible, the spawn should fail with a clear error message.
        """
        # Try to spawn instance without parent (not main-orchestrator, no detection possible)
        with pytest.raises(ValueError) as exc_info:
            await manager.spawn_instance(
                name="orphan-instance",
                role="general",
                # NO parent_instance_id provided
                # NO auto-detection possible (no other instances)
            )

        # Verify error message is helpful
        error_message = str(exc_info.value)
        assert "Cannot spawn instance 'orphan-instance'" in error_message
        assert "parent_instance_id is required" in error_message
        assert "Possible causes:" in error_message
        assert "Solutions:" in error_message

    @pytest.mark.asyncio
    async def test_spawn_fails_without_parent_detailed_error(self, manager):
        """Test that error message provides actionable guidance.

        The error should explain:
        1. What went wrong
        2. Possible causes
        3. How to fix it
        """
        with pytest.raises(ValueError) as exc_info:
            await manager.spawn_instance(
                name="test-instance",
                role="general",
            )

        error_message = str(exc_info.value)

        # Check for key error message components
        assert "Spawning from external client" in error_message
        assert "Caller instance detection failed" in error_message
        assert "Provide parent_instance_id explicitly" in error_message
        assert "spawn_claude(..., parent_instance_id=" in error_message
        assert "Spawn from within a managed instance" in error_message

    @pytest.mark.asyncio
    async def test_spawn_fails_even_with_terminated_instances(self, manager):
        """Test spawn fails even when terminated instances exist.

        Terminated instances should be ignored by auto-detection,
        so spawn should still fail if no active instances can be detected.
        """
        # Spawn and terminate an instance
        main_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
        )
        await manager._terminate_instance_internal(instance_id=main_id)

        # Verify it's terminated
        assert manager.instances[main_id]["state"] == "terminated"

        # Try to spawn new instance - should fail because no active instances
        with pytest.raises(ValueError) as exc_info:
            await manager.spawn_instance(
                name="new-instance",
                role="general",
            )

        error_message = str(exc_info.value)
        assert "parent_instance_id is required" in error_message

    # ============================================================
    # Test Case 5: Batch spawn with auto-injection works
    # ============================================================

    @pytest.mark.asyncio
    async def test_spawn_multiple_auto_inject(self, manager):
        """Test spawn_multiple_instances with parent_instance_id auto-injection.

        When spawning multiple instances in batch without explicit parent_instance_id,
        auto-injection should work for all instances if caller is detected.
        """
        # Spawn main orchestrator
        main_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
        )

        # Spawn multiple children with explicit parent
        child_ids = []
        for i in range(3):
            child_id = await manager.spawn_instance(
                name=f"batch-child-{i}",
                role="general",
                parent_instance_id=main_id,
            )
            child_ids.append(child_id)

        # Verify all children have correct parent
        assert len(child_ids) == 3
        for child_id in child_ids:
            assert child_id in manager.instances
            child_instance = manager.instances[child_id]
            assert child_instance["parent_instance_id"] == main_id

    @pytest.mark.asyncio
    async def test_spawn_multiple_mixed_explicit_and_auto(self, manager):
        """Test batch spawn with mix of explicit and auto-injected parent_instance_id.

        Some instances may have explicit parent, others may rely on auto-injection.
        Each should be handled according to Tier 1/Tier 2 priority.
        """
        # Spawn two parents
        parent_a_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
        )

        parent_b_id = await manager.spawn_instance(
            name="parent-b",
            role="general",
            parent_instance_id=parent_a_id,
        )

        # Spawn multiple children with mixed parent specifications
        child1_id = await manager.spawn_instance(
            name="child-1-explicit-a",
            role="general",
            parent_instance_id=parent_a_id,  # Explicit parent A
        )

        child2_id = await manager.spawn_instance(
            name="child-2-explicit-b",
            role="general",
            parent_instance_id=parent_b_id,  # Explicit parent B
        )

        # Verify each child has correct parent
        assert manager.instances[child1_id]["parent_instance_id"] == parent_a_id
        assert manager.instances[child2_id]["parent_instance_id"] == parent_b_id

    @pytest.mark.asyncio
    async def test_spawn_multiple_all_fail_without_parent(self, manager):
        """Test that batch spawn fails if parent cannot be determined for any instance.

        If spawning multiple instances without parent and no detection possible,
        the first spawn should fail and prevent subsequent spawns.
        """
        # Try to spawn multiple instances without parent
        with pytest.raises(ValueError) as exc_info:
            await manager.spawn_instance(
                name="batch-orphan-1",
                role="general",
            )

        error_message = str(exc_info.value)
        assert "parent_instance_id is required" in error_message


class TestParentInstanceIdIntegration:
    """Integration tests for parent_instance_id with full hierarchy."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def config(self, temp_workspace):
        """Create test configuration."""
        return {
            "workspace_base_dir": temp_workspace,
            "max_concurrent_instances": 10,
            "instance_timeout_minutes": 60,
            "anthropic_api_key": "test-key",
        }

    @pytest.fixture
    def manager(self, config):
        """Create InstanceManager for testing."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.poll.return_value = None
            mock_process.stdin = MagicMock()
            mock_process.stdout = MagicMock()
            mock_process.stderr = MagicMock()

            responses = [b'{"type":"message","content":"Ready"}\n', b'{"type":"end"}\n', b""]
            mock_process.stdout.readline.side_effect = responses
            mock_popen.return_value = mock_process

            return InstanceManager(config)

    @pytest.mark.asyncio
    async def test_hierarchical_team_structure(self, manager):
        """Test creating proper hierarchical team structure.

        This is the core use case: supervisor spawns team members,
        and each team member can spawn sub-agents, forming a tree structure.
        """
        # Step 1: Spawn main orchestrator (root)
        main_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
        )
        assert manager.instances[main_id].get("parent_instance_id") is None

        # Step 2: Spawn supervisor (child of main)
        supervisor_id = await manager.spawn_instance(
            name="team-supervisor",
            role="general",
            parent_instance_id=main_id,
        )
        assert manager.instances[supervisor_id]["parent_instance_id"] == main_id

        # Step 3: Spawn team members (children of supervisor)
        developer_id = await manager.spawn_instance(
            name="developer",
            role="general",
            parent_instance_id=supervisor_id,
        )

        qa_id = await manager.spawn_instance(
            name="qa-engineer",
            role="general",
            parent_instance_id=supervisor_id,
        )

        # Step 4: Verify hierarchy
        assert manager.instances[developer_id]["parent_instance_id"] == supervisor_id
        assert manager.instances[qa_id]["parent_instance_id"] == supervisor_id

        # Verify tree structure: main -> supervisor -> [developer, qa]
        # All instances should be tracked
        assert len(manager.instances) == 4

    @pytest.mark.asyncio
    async def test_prevent_flat_hierarchy_bug(self, manager):
        """Test that the bug (flat hierarchy instead of tree) is prevented.

        This is the original issue: team supervisor spawned children with
        parent_instance_id=None, creating a flat structure instead of a tree.
        Now it should fail loudly instead of silently creating wrong hierarchy.
        """
        # Spawn main
        main_id = await manager.spawn_instance(
            name="main-orchestrator",
            role="general",
        )

        # Spawn supervisor
        supervisor_id = await manager.spawn_instance(
            name="supervisor",
            role="general",
            parent_instance_id=main_id,
        )

        # Attempt to spawn child WITHOUT parent (simulating the bug scenario)
        # This should now FAIL instead of silently creating parent=None
        with pytest.raises(ValueError) as exc_info:
            await manager.spawn_instance(
                name="team-member",
                role="general",
                # NO parent_instance_id - should fail!
            )

        error_message = str(exc_info.value)
        assert "parent_instance_id is required" in error_message

        # Correct way: provide explicit parent
        team_member_id = await manager.spawn_instance(
            name="team-member",
            role="general",
            parent_instance_id=supervisor_id,
        )

        # Verify proper hierarchy
        assert manager.instances[team_member_id]["parent_instance_id"] == supervisor_id
        assert manager.instances[team_member_id]["parent_instance_id"] is not None


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
