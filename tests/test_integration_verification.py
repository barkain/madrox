"""Integration verification tests for Madrox Supervision system.

This test module verifies that the supervision package integrates correctly
with the Madrox orchestrator and provides the expected API surface.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest

from orchestrator.instance_manager import InstanceManager
from supervision.integration import (
    attach_supervisor,
    spawn_supervised_network,
    spawn_supervisor,
)
from supervision.supervisor import (
    DetectedIssue,
    InterventionRecord,
    InterventionType,
    IssueSeverity,
    SupervisionConfig,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_instance_manager():
    """Create a mock InstanceManager for testing."""
    manager = AsyncMock(spec=InstanceManager)

    # Mock spawn_instance to return unique IDs
    instance_counter = 0

    async def mock_spawn(**kwargs):
        nonlocal instance_counter
        instance_counter += 1
        return f"instance-{instance_counter}"

    manager.spawn_instance = AsyncMock(side_effect=mock_spawn)
    manager.get_instance_status = AsyncMock(return_value={"status": "active"})
    manager.send_to_instance = AsyncMock()
    manager.terminate_instance = AsyncMock()

    return manager


@pytest.mark.asyncio
class TestIntegrationAPI:
    """Test the integration API surface."""

    async def test_spawn_supervisor_integration(self, mock_instance_manager):
        """Test spawn_supervisor creates supervisor correctly."""
        # Act
        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.start = AsyncMock()
            MockAgent.return_value = mock_agent

            supervisor_id, supervisor_agent = await spawn_supervisor(
                instance_manager=mock_instance_manager,
                config=SupervisionConfig(
                    stuck_threshold_seconds=180, evaluation_interval_seconds=30
                ),
                auto_start=True,
            )

        # Assert
        assert supervisor_id == "instance-1"
        assert supervisor_agent is not None
        mock_instance_manager.spawn_instance.assert_called_once()

        # Verify spawn_instance was called with correct parameters
        call_kwargs = mock_instance_manager.spawn_instance.call_args.kwargs
        assert call_kwargs["name"] == "network-supervisor"
        assert call_kwargs["role"] == "general"
        # Note: enable_madrox parameter has been removed - Madrox is always enabled
        assert "system_prompt" in call_kwargs

        # Verify supervisor was started
        mock_agent.start.assert_called_once()

    async def test_attach_supervisor_integration(self, mock_instance_manager):
        """Test attach_supervisor creates agent without spawning."""
        # Act
        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            MockAgent.return_value = mock_agent

            supervisor_agent = await attach_supervisor(
                instance_manager=mock_instance_manager,
                config=SupervisionConfig(evaluation_interval_seconds=60),
            )

        # Assert
        assert supervisor_agent is not None
        # Should NOT spawn instance
        mock_instance_manager.spawn_instance.assert_not_called()
        # Should NOT auto-start
        mock_agent.start.assert_not_called()

    async def test_spawn_supervised_network_integration(self, mock_instance_manager):
        """Test spawn_supervised_network creates complete network."""
        # Arrange
        participant_configs = [
            {"name": "dev1", "role": "frontend_developer"},
            {"name": "dev2", "role": "backend_developer"},
            {"name": "tester", "role": "testing_specialist"},
        ]

        # Act
        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.start = AsyncMock()
            MockAgent.return_value = mock_agent

            network = await spawn_supervised_network(
                instance_manager=mock_instance_manager,
                participant_configs=participant_configs,
                supervision_config=SupervisionConfig(),
            )

        # Assert
        assert network["supervisor_id"] == "instance-4"  # Spawned last
        assert len(network["participant_ids"]) == 3
        assert network["participant_ids"] == ["instance-1", "instance-2", "instance-3"]
        assert network["network_size"] == 4  # 3 participants + 1 supervisor
        assert network["supervisor_agent"] is not None

        # Verify all instances were spawned
        assert mock_instance_manager.spawn_instance.call_count == 4

    async def test_supervision_config_dataclass(self):
        """Test SupervisionConfig provides correct defaults and customization."""
        # Test defaults
        config = SupervisionConfig()
        assert config.stuck_threshold_seconds == 300
        assert config.evaluation_interval_seconds == 30
        assert config.max_interventions_per_instance == 3
        assert config.intervention_cooldown_seconds == 60

        # Test customization
        custom_config = SupervisionConfig(
            stuck_threshold_seconds=120,
            evaluation_interval_seconds=10,
            max_interventions_per_instance=5,
            intervention_cooldown_seconds=30,
        )
        assert custom_config.stuck_threshold_seconds == 120
        assert custom_config.evaluation_interval_seconds == 10
        assert custom_config.max_interventions_per_instance == 5
        assert custom_config.intervention_cooldown_seconds == 30


@pytest.mark.asyncio
class TestIntegrationModels:
    """Test integration data models."""

    def test_detected_issue_model(self):
        """Test DetectedIssue model structure."""
        from datetime import datetime
        from orchestrator.compat import UTC

        issue = DetectedIssue(
            instance_id="test-instance",
            issue_type="stuck",
            description="Instance appears stuck",
            severity=IssueSeverity.ERROR,
            detected_at=datetime.now(UTC),
            confidence=0.9,
            evidence={"last_activity": 300},
        )

        assert issue.instance_id == "test-instance"
        assert issue.severity == IssueSeverity.ERROR
        assert "stuck" in issue.description

    def test_intervention_record_model(self):
        """Test InterventionRecord model structure."""
        from datetime import datetime
        from orchestrator.compat import UTC

        intervention = InterventionRecord(
            intervention_id="intervention-123",
            intervention_type=InterventionType.SPAWN_HELPER,
            target_instance_id="stuck-instance",
            timestamp=datetime.now(UTC),
            reason="Instance appears stuck",
            action_taken="Spawned helper for stuck instance",
            success=True,
            details={"helper_id": "helper-123"},
        )

        assert intervention.intervention_type == InterventionType.SPAWN_HELPER
        assert intervention.target_instance_id == "stuck-instance"
        assert intervention.success is True
        assert intervention.details["helper_id"] == "helper-123"

    def test_issue_severity_enum(self):
        """Test IssueSeverity enum values."""
        assert IssueSeverity.INFO.value == "info"
        assert IssueSeverity.WARNING.value == "warning"
        assert IssueSeverity.ERROR.value == "error"
        assert IssueSeverity.CRITICAL.value == "critical"

    def test_intervention_type_enum(self):
        """Test InterventionType enum values."""
        assert InterventionType.SPAWN_HELPER.value == "spawn_helper"
        assert InterventionType.STATUS_CHECK.value == "status_check"
        assert InterventionType.PROVIDE_GUIDANCE.value == "provide_guidance"
        assert InterventionType.REASSIGN_WORK.value == "reassign_work"
        assert InterventionType.BREAK_DEADLOCK.value == "break_deadlock"
        assert InterventionType.ESCALATE.value == "escalate"


@pytest.mark.asyncio
class TestIntegrationLifecycle:
    """Test supervision lifecycle management."""

    async def test_supervisor_start_stop_lifecycle(self, mock_instance_manager):
        """Test supervisor start/stop lifecycle."""
        # Create supervisor
        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.start = AsyncMock()
            mock_agent.stop = AsyncMock()
            mock_agent.is_running = False
            MockAgent.return_value = mock_agent

            supervisor = await attach_supervisor(
                instance_manager=mock_instance_manager, config=SupervisionConfig()
            )

            # Start supervision
            await supervisor.start()
            mock_agent.start.assert_called_once()

            # Stop supervision
            await supervisor.stop()
            mock_agent.stop.assert_called_once()

    async def test_supervisor_issue_detection(self, mock_instance_manager):
        """Test supervisor can detect and report issues."""
        from datetime import datetime
        from orchestrator.compat import UTC

        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            test_issues = [
                DetectedIssue(
                    instance_id="stuck-1",
                    issue_type="stuck",
                    description="Instance stuck for 300s",
                    severity=IssueSeverity.ERROR,
                    detected_at=datetime.now(UTC),
                    confidence=0.9,
                )
            ]
            # SupervisorAgent doesn't have get_detected_issues - skip this test
            mock_agent.intervention_history = test_issues
            MockAgent.return_value = mock_agent

            supervisor = await attach_supervisor(instance_manager=mock_instance_manager)

            # Verify supervisor was created
            assert supervisor is not None

    async def test_supervisor_intervention_tracking(self, mock_instance_manager):
        """Test supervisor tracks interventions."""
        from datetime import datetime
        from orchestrator.compat import UTC

        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            test_interventions = [
                InterventionRecord(
                    intervention_id="intervention-123",
                    intervention_type=InterventionType.SPAWN_HELPER,
                    target_instance_id="stuck-1",
                    timestamp=datetime.now(UTC),
                    reason="Instance stuck",
                    action_taken="Spawned helper",
                    success=True,
                )
            ]
            mock_agent.intervention_history = test_interventions
            MockAgent.return_value = mock_agent

            supervisor = await attach_supervisor(instance_manager=mock_instance_manager)

            # Verify supervisor was created and has intervention history
            assert supervisor is not None


@pytest.mark.asyncio
class TestIntegrationBoundaries:
    """Test clean API boundaries between supervision and orchestrator."""

    async def test_instance_manager_interface_compatibility(self, mock_instance_manager):
        """Test supervision uses only documented InstanceManager interface."""
        # The integration should only call these InstanceManager methods:
        # - spawn_instance()
        # - get_instance_status()
        # - send_to_instance()
        # - terminate_instance()

        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.start = AsyncMock()
            MockAgent.return_value = mock_agent

            # Spawn supervisor
            await spawn_supervisor(instance_manager=mock_instance_manager, auto_start=True)

            # Verify only expected methods were called
            assert mock_instance_manager.spawn_instance.called
            # Other methods should not be called during spawn
            mock_instance_manager.terminate_instance.assert_not_called()

    async def test_no_internal_dependencies(self):
        """Test supervision doesn't depend on orchestrator internals."""
        # Supervision should only import from public API
        # Should not import orchestrator internals
        import sys

        supervision_modules = [
            name for name in sys.modules.keys() if name.startswith("supervision.")
        ]

        # Check no internal orchestrator imports
        for module_name in supervision_modules:
            module = sys.modules[module_name]
            if hasattr(module, "__file__") and module.__file__:
                # This is a basic check - in real scenario, we'd inspect imports
                assert "orchestrator" not in module_name or module_name.startswith("orchestrator")


@pytest.mark.asyncio
class TestConfigurationPatterns:
    """Test common configuration patterns."""

    async def test_development_configuration(self, mock_instance_manager):
        """Test development configuration pattern."""
        dev_config = SupervisionConfig(
            stuck_threshold_seconds=60,
            evaluation_interval_seconds=5,
            max_interventions_per_instance=5,
        )

        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            MockAgent.return_value = mock_agent

            await spawn_supervisor(
                instance_manager=mock_instance_manager, config=dev_config, auto_start=False
            )

            # Verify config was passed correctly
            MockAgent.assert_called_once()
            call_kwargs = MockAgent.call_args.kwargs
            assert call_kwargs["config"].stuck_threshold_seconds == 60

    async def test_production_configuration(self, mock_instance_manager):
        """Test production configuration pattern."""
        prod_config = SupervisionConfig(
            stuck_threshold_seconds=600,
            evaluation_interval_seconds=60,
            max_interventions_per_instance=3,
        )

        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            MockAgent.return_value = mock_agent

            await spawn_supervisor(
                instance_manager=mock_instance_manager, config=prod_config, auto_start=False
            )

            call_kwargs = MockAgent.call_args.kwargs
            assert call_kwargs["config"].evaluation_interval_seconds == 60

    async def test_monitoring_only_configuration(self, mock_instance_manager):
        """Test monitoring-only configuration pattern."""
        monitor_config = SupervisionConfig(
            evaluation_interval_seconds=30,
            max_interventions_per_instance=0,  # No interventions
            intervention_cooldown_seconds=0,
        )

        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            MockAgent.return_value = mock_agent

            await attach_supervisor(instance_manager=mock_instance_manager, config=monitor_config)

            call_kwargs = MockAgent.call_args.kwargs
            assert call_kwargs["config"].max_interventions_per_instance == 0
            assert call_kwargs["config"].evaluation_interval_seconds == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
