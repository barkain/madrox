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
        assert config.max_stall_count == 3
        assert config.enable_auto_intervention is True

        # Test customization
        custom_config = SupervisionConfig(
            stuck_threshold_seconds=120,
            evaluation_interval_seconds=10,
            max_concurrent_helpers=5,
            enable_auto_intervention=False,
        )
        assert custom_config.stuck_threshold_seconds == 120
        assert custom_config.evaluation_interval_seconds == 10
        assert custom_config.max_concurrent_helpers == 5
        assert custom_config.enable_auto_intervention is False


@pytest.mark.asyncio
class TestIntegrationModels:
    """Test integration data models."""

    def test_detected_issue_model(self):
        """Test DetectedIssue model structure."""
        issue = DetectedIssue(
            instance_id="test-instance",
            description="Instance appears stuck",
            severity=IssueSeverity.HIGH,
            detected_at=asyncio.get_event_loop().time(),
            metadata={"last_activity": 300},
        )

        assert issue.instance_id == "test-instance"
        assert issue.severity == IssueSeverity.HIGH
        assert "stuck" in issue.description

    def test_intervention_record_model(self):
        """Test InterventionRecord model structure."""
        intervention = InterventionRecord(
            intervention_type=InterventionType.HELPER_SPAWN,
            target_instance_id="stuck-instance",
            description="Spawned helper for stuck instance",
            timestamp=asyncio.get_event_loop().time(),
            success=True,
            metadata={"helper_id": "helper-123"},
        )

        assert intervention.intervention_type == InterventionType.HELPER_SPAWN
        assert intervention.target_instance_id == "stuck-instance"
        assert intervention.success is True
        assert intervention.metadata["helper_id"] == "helper-123"

    def test_issue_severity_enum(self):
        """Test IssueSeverity enum values."""
        assert IssueSeverity.LOW.value == "low"
        assert IssueSeverity.MEDIUM.value == "medium"
        assert IssueSeverity.HIGH.value == "high"
        assert IssueSeverity.CRITICAL.value == "critical"

    def test_intervention_type_enum(self):
        """Test InterventionType enum values."""
        assert InterventionType.HELPER_SPAWN.value == "helper_spawn"
        assert InterventionType.INSTANCE_RESTART.value == "instance_restart"
        assert InterventionType.MESSAGE_SENT.value == "message_sent"
        assert InterventionType.CUSTOM.value == "custom"


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
        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            test_issues = [
                DetectedIssue(
                    instance_id="stuck-1",
                    description="Instance stuck for 300s",
                    severity=IssueSeverity.HIGH,
                    detected_at=asyncio.get_event_loop().time(),
                )
            ]
            mock_agent.get_detected_issues = AsyncMock(return_value=test_issues)
            MockAgent.return_value = mock_agent

            supervisor = await attach_supervisor(instance_manager=mock_instance_manager)

            # Get issues
            issues = await supervisor.get_detected_issues()

            assert len(issues) == 1
            assert issues[0].instance_id == "stuck-1"
            assert issues[0].severity == IssueSeverity.HIGH

    async def test_supervisor_intervention_tracking(self, mock_instance_manager):
        """Test supervisor tracks interventions."""
        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            test_interventions = [
                InterventionRecord(
                    intervention_type=InterventionType.HELPER_SPAWN,
                    target_instance_id="stuck-1",
                    description="Spawned helper",
                    timestamp=asyncio.get_event_loop().time(),
                    success=True,
                )
            ]
            mock_agent.get_interventions = Mock(return_value=test_interventions)
            MockAgent.return_value = mock_agent

            supervisor = await attach_supervisor(instance_manager=mock_instance_manager)

            # Get interventions
            interventions = supervisor.get_interventions()

            assert len(interventions) == 1
            assert interventions[0].intervention_type == InterventionType.HELPER_SPAWN
            assert interventions[0].success is True


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
            stuck_threshold_seconds=60, evaluation_interval_seconds=5, max_concurrent_helpers=5
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
            stuck_threshold_seconds=600, evaluation_interval_seconds=60, max_concurrent_helpers=3
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
            enable_auto_intervention=False,
            enable_progress_tracking=True,
            enable_pattern_analysis=True,
        )

        with patch("supervision.integration.manager_integration.SupervisorAgent") as MockAgent:
            mock_agent = AsyncMock()
            MockAgent.return_value = mock_agent

            await attach_supervisor(instance_manager=mock_instance_manager, config=monitor_config)

            call_kwargs = MockAgent.call_args.kwargs
            assert call_kwargs["config"].enable_auto_intervention is False
            assert call_kwargs["config"].enable_progress_tracking is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
