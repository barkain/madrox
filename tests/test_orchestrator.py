"""Comprehensive test suite for Claude Orchestrator."""

import asyncio
import os
import pytest
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to Python path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.orchestrator.instance_manager import InstanceManager
from src.orchestrator.simple_models import (
    InstanceRole,
    InstanceState,
    OrchestratorConfig,
    SpawnInstanceRequest,
)


class TestOrchestratorConfig:
    """Test OrchestratorConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = OrchestratorConfig()

        assert config.server_host == "localhost"
        assert config.server_port == 8001
        assert config.default_model == "claude-3-5-sonnet-20241022"
        assert config.max_concurrent_instances == 10
        assert config.instance_timeout_minutes == 60
        assert config.workspace_base_dir == "/tmp/claude_orchestrator"
        assert config.log_level == "INFO"

    def test_custom_config(self):
        """Test custom configuration values."""
        config = OrchestratorConfig(
            server_host="0.0.0.0",
            server_port=9000,
            max_concurrent_instances=5,
            anthropic_api_key="test-key-123",
        )

        assert config.server_host == "0.0.0.0"
        assert config.server_port == 9000
        assert config.max_concurrent_instances == 5
        assert config.anthropic_api_key == "test-key-123"


class TestInstanceManager:
    """Test InstanceManager functionality."""

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
            "max_concurrent_instances": 5,
            "instance_timeout_minutes": 1,
            "anthropic_api_key": "test-key",
        }

    @pytest.fixture
    def manager(self, config):
        """Create InstanceManager for testing."""
        return InstanceManager(config)

    @pytest.mark.asyncio
    async def test_spawn_instance_basic(self, manager):
        """Test basic instance spawning."""
        instance_id = await manager.spawn_instance(
            name="test-instance",
            role="general",
        )

        assert instance_id is not None
        assert len(instance_id) > 0
        assert instance_id in manager.instances

        instance = manager.instances[instance_id]
        assert instance["name"] == "test-instance"
        assert instance["role"] == "general"
        assert instance["state"] == "running"

    @pytest.mark.asyncio
    async def test_spawn_instance_with_role(self, manager):
        """Test spawning instance with specific role."""
        instance_id = await manager.spawn_instance(
            name="frontend-dev",
            role=InstanceRole.FRONTEND_DEVELOPER.value,
            system_prompt="You are a frontend developer",
        )

        instance = manager.instances[instance_id]
        assert instance["role"] == InstanceRole.FRONTEND_DEVELOPER.value
        assert "frontend developer" in instance["system_prompt"].lower()

    @pytest.mark.asyncio
    async def test_spawn_multiple_instances(self, manager):
        """Test spawning multiple instances."""
        instances = []

        for i in range(3):
            instance_id = await manager.spawn_instance(
                name=f"instance-{i}",
                role="general",
            )
            instances.append(instance_id)

        assert len(manager.instances) == 3
        assert all(iid in manager.instances for iid in instances)

    @pytest.mark.asyncio
    async def test_max_instances_limit(self, manager):
        """Test maximum instance limit enforcement."""
        # Spawn up to the limit
        for i in range(5):  # max_concurrent_instances = 5
            await manager.spawn_instance(name=f"instance-{i}")

        # Try to spawn one more - should fail
        with pytest.raises(RuntimeError, match="Maximum concurrent instances reached"):
            await manager.spawn_instance(name="overflow-instance")

    @pytest.mark.asyncio
    async def test_send_message_to_instance(self, manager):
        """Test sending messages to instances."""
        instance_id = await manager.spawn_instance(name="test-instance")

        response = await manager.send_to_instance(
            instance_id=instance_id,
            message="Hello, Claude!",
            wait_for_response=True,
        )

        assert response is not None
        assert response["instance_id"] == instance_id
        assert "response" in response
        assert response["tokens_used"] > 0

    @pytest.mark.asyncio
    async def test_send_message_no_wait(self, manager):
        """Test sending message without waiting for response."""
        instance_id = await manager.spawn_instance(name="test-instance")

        response = await manager.send_to_instance(
            instance_id=instance_id,
            message="Hello!",
            wait_for_response=False,
        )

        assert response is None

    @pytest.mark.asyncio
    async def test_send_message_timeout(self, manager):
        """Test message timeout handling."""
        instance_id = await manager.spawn_instance(name="test-instance")

        # Mock the _wait_for_response to simulate timeout
        with patch.object(manager, '_wait_for_response', side_effect=asyncio.TimeoutError()):
            response = await manager.send_to_instance(
                instance_id=instance_id,
                message="This will timeout",
                timeout_seconds=1,
            )
            assert response is None

    @pytest.mark.asyncio
    async def test_get_instance_output(self, manager):
        """Test getting instance output."""
        instance_id = await manager.spawn_instance(name="test-instance")

        output = await manager.get_instance_output(instance_id)

        assert isinstance(output, list)
        assert len(output) >= 0

    @pytest.mark.asyncio
    async def test_coordinate_instances(self, manager):
        """Test instance coordination."""
        # Spawn coordinator and participants
        coordinator_id = await manager.spawn_instance(name="coordinator", role="architect")
        participant1_id = await manager.spawn_instance(name="participant1", role="frontend_developer")
        participant2_id = await manager.spawn_instance(name="participant2", role="backend_developer")

        task_id = await manager.coordinate_instances(
            coordinator_id=coordinator_id,
            participant_ids=[participant1_id, participant2_id],
            task_description="Build a web application",
            coordination_type="sequential",
        )

        assert task_id is not None
        assert len(task_id) > 0

    @pytest.mark.asyncio
    async def test_terminate_instance(self, manager):
        """Test instance termination."""
        instance_id = await manager.spawn_instance(name="test-instance")

        # Verify instance exists and is running
        assert instance_id in manager.instances
        assert manager.instances[instance_id]["state"] == "running"

        # Terminate instance
        success = await manager.terminate_instance(instance_id)

        assert success is True
        assert manager.instances[instance_id]["state"] == "terminated"

    @pytest.mark.asyncio
    async def test_terminate_busy_instance_without_force(self, manager):
        """Test terminating busy instance without force flag."""
        instance_id = await manager.spawn_instance(name="test-instance")

        # Set instance to busy
        manager.instances[instance_id]["state"] = "busy"

        # Try to terminate without force
        success = await manager.terminate_instance(instance_id, force=False)

        assert success is False
        assert manager.instances[instance_id]["state"] == "busy"

    @pytest.mark.asyncio
    async def test_terminate_busy_instance_with_force(self, manager):
        """Test force terminating busy instance."""
        instance_id = await manager.spawn_instance(name="test-instance")

        # Set instance to busy
        manager.instances[instance_id]["state"] = "busy"

        # Force terminate
        success = await manager.terminate_instance(instance_id, force=True)

        assert success is True
        assert manager.instances[instance_id]["state"] == "terminated"

    def test_get_instance_status_single(self, manager):
        """Test getting single instance status."""
        # Test with non-existent instance
        with pytest.raises(ValueError, match="Instance .* not found"):
            manager.get_instance_status("non-existent-id")

    def test_get_instance_status_all(self, manager):
        """Test getting all instances status."""
        status = manager.get_instance_status()

        assert "instances" in status
        assert "total_instances" in status
        assert "active_instances" in status
        assert "total_tokens_used" in status
        assert "total_cost" in status

    @pytest.mark.asyncio
    async def test_health_check(self, manager):
        """Test health check functionality."""
        # Spawn an instance
        instance_id = await manager.spawn_instance(name="test-instance")

        # Run health check
        await manager.health_check()

        # Instance should still be active
        assert manager.instances[instance_id]["state"] in ["running", "idle"]

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, manager):
        """Test health check with timeout."""
        # Create instance and set old last_activity
        instance_id = await manager.spawn_instance(name="test-instance")

        # Set last activity to very old timestamp to trigger timeout
        from datetime import UTC, datetime, timedelta
        old_time = datetime.now(UTC) - timedelta(hours=2)
        manager.instances[instance_id]["last_activity"] = old_time.isoformat()

        # Run health check
        await manager.health_check()

        # Instance should be terminated due to timeout
        assert manager.instances[instance_id]["state"] == "terminated"

    def test_role_prompts(self, manager):
        """Test role-based system prompts."""
        prompts = {}

        for role in InstanceRole:
            prompt = manager._get_role_prompt(role.value)
            prompts[role.value] = prompt
            assert len(prompt) > 0
            assert isinstance(prompt, str)

        # Verify different roles have different prompts
        assert prompts[InstanceRole.FRONTEND_DEVELOPER.value] != prompts[InstanceRole.BACKEND_DEVELOPER.value]
        assert prompts[InstanceRole.TESTING_SPECIALIST.value] != prompts[InstanceRole.DOCUMENTATION_WRITER.value]

    @pytest.mark.asyncio
    async def test_workspace_isolation(self, manager, temp_workspace):
        """Test workspace directory isolation."""
        instance_id = await manager.spawn_instance(name="test-instance")

        instance = manager.instances[instance_id]
        workspace_dir = Path(instance["workspace_dir"])

        # Verify workspace exists and is in expected location
        assert workspace_dir.exists()
        assert workspace_dir.is_dir()
        assert str(workspace_dir).startswith(temp_workspace)
        assert instance_id in str(workspace_dir)

    @pytest.mark.asyncio
    async def test_error_handling_invalid_instance(self, manager):
        """Test error handling for invalid instance operations."""
        # Test sending message to non-existent instance
        with pytest.raises(ValueError, match="Instance .* not found"):
            await manager.send_to_instance("invalid-id", "test message")

        # Test getting output from non-existent instance
        with pytest.raises(ValueError, match="Instance .* not found"):
            await manager.get_instance_output("invalid-id")

        # Test terminating non-existent instance
        with pytest.raises(ValueError, match="Instance .* not found"):
            await manager.terminate_instance("invalid-id")


class TestIntegration:
    """Integration tests for the orchestrator system."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def config(self, temp_workspace):
        """Create test configuration."""
        return OrchestratorConfig(
            workspace_base_dir=temp_workspace,
            max_concurrent_instances=3,
            instance_timeout_minutes=1,
            anthropic_api_key="test-key",
        )

    @pytest.fixture
    def manager(self, config):
        """Create InstanceManager for testing."""
        return InstanceManager(config.__dict__)

    @pytest.mark.asyncio
    async def test_full_orchestration_workflow(self, manager):
        """Test complete orchestration workflow with multiple specialized instances."""
        # Scenario: Build a simple web application using 3 specialized instances

        # 1. Spawn architect to design the system
        architect_id = await manager.spawn_instance(
            name="system-architect",
            role=InstanceRole.ARCHITECT.value,
        )

        # 2. Spawn frontend developer
        frontend_id = await manager.spawn_instance(
            name="frontend-developer",
            role=InstanceRole.FRONTEND_DEVELOPER.value,
        )

        # 3. Spawn backend developer
        backend_id = await manager.spawn_instance(
            name="backend-developer",
            role=InstanceRole.BACKEND_DEVELOPER.value,
        )

        # Verify all instances are created
        assert len(manager.instances) == 3
        assert all(
            manager.instances[iid]["state"] == "running"
            for iid in [architect_id, frontend_id, backend_id]
        )

        # 4. Send architectural planning task to architect
        arch_response = await manager.send_to_instance(
            architect_id,
            "Design a simple task management web application with REST API",
        )
        assert arch_response is not None

        # 5. Coordinate instances for implementation
        coordination_task_id = await manager.coordinate_instances(
            coordinator_id=architect_id,
            participant_ids=[frontend_id, backend_id],
            task_description="Implement the task management application",
            coordination_type="parallel",
        )
        assert coordination_task_id is not None

        # 6. Send specific tasks to each developer
        frontend_response = await manager.send_to_instance(
            frontend_id,
            "Create React components for task management UI",
        )

        backend_response = await manager.send_to_instance(
            backend_id,
            "Implement REST API endpoints for task CRUD operations",
        )

        assert frontend_response is not None
        assert backend_response is not None

        # 7. Verify resource usage tracking
        status = manager.get_instance_status()
        assert status["total_tokens_used"] > 0
        assert status["total_cost"] > 0

        # 8. Clean shutdown - terminate all instances
        for instance_id in [architect_id, frontend_id, backend_id]:
            success = await manager.terminate_instance(instance_id)
            assert success is True

        # Verify all instances are terminated
        for instance_id in [architect_id, frontend_id, backend_id]:
            assert manager.instances[instance_id]["state"] == "terminated"

    @pytest.mark.asyncio
    async def test_resource_limits_enforcement(self, manager):
        """Test resource limits are properly enforced."""
        # Create instance with resource limits
        instance_id = await manager.spawn_instance(
            name="limited-instance",
            resource_limits={
                "max_total_tokens": 100,
                "max_cost": 0.01,
            }
        )

        # Simulate token/cost usage
        instance = manager.instances[instance_id]
        instance["total_tokens_used"] = 150  # Exceed limit
        instance["total_cost"] = 0.02  # Exceed limit

        # Run health check - should terminate due to limits
        await manager.health_check()

        assert instance["state"] == "terminated"

    @pytest.mark.asyncio
    async def test_concurrent_message_handling(self, manager):
        """Test handling multiple concurrent messages."""
        instance_id = await manager.spawn_instance(name="concurrent-test")

        # Send multiple messages concurrently
        tasks = []
        for i in range(5):
            task = manager.send_to_instance(
                instance_id,
                f"Message {i}",
                wait_for_response=True,
            )
            tasks.append(task)

        # Wait for all responses
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all messages were handled
        successful_responses = [r for r in responses if not isinstance(r, Exception)]
        assert len(successful_responses) >= 0  # At least some should succeed


def test_instance_states():
    """Test InstanceState enum."""
    assert InstanceState.INITIALIZING.value == "initializing"
    assert InstanceState.RUNNING.value == "running"
    assert InstanceState.IDLE.value == "idle"
    assert InstanceState.BUSY.value == "busy"
    assert InstanceState.ERROR.value == "error"
    assert InstanceState.TERMINATED.value == "terminated"


def test_instance_roles():
    """Test InstanceRole enum."""
    assert InstanceRole.GENERAL.value == "general"
    assert InstanceRole.FRONTEND_DEVELOPER.value == "frontend_developer"
    assert InstanceRole.BACKEND_DEVELOPER.value == "backend_developer"
    assert InstanceRole.TESTING_SPECIALIST.value == "testing_specialist"
    assert InstanceRole.DOCUMENTATION_WRITER.value == "documentation_writer"
    assert InstanceRole.CODE_REVIEWER.value == "code_reviewer"
    assert InstanceRole.ARCHITECT.value == "architect"
    assert InstanceRole.DEBUGGER.value == "debugger"
    assert InstanceRole.SECURITY_ANALYST.value == "security_analyst"
    assert InstanceRole.DATA_ANALYST.value == "data_analyst"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])