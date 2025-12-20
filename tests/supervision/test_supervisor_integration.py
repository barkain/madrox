"""Integration tests for Supervisor Agent with Madrox InstanceManager.

These tests validate the supervisor's ability to monitor and intervene
in real Madrox networks.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from supervision.integration.manager_integration import (
    attach_supervisor,
    spawn_supervised_network,
    spawn_supervisor,
)
from supervision.supervisor.agent import (
    DetectedIssue,
    IssueSeverity,
    SupervisionConfig,
    SupervisorAgent,
)


@pytest.fixture
def mock_instance_manager():
    """Create a mock InstanceManager for testing."""
    manager = MagicMock()

    # Mock spawn_instance
    manager.spawn_instance = AsyncMock(return_value="supervisor-test-id")

    # Mock send_to_instance
    manager.send_to_instance = AsyncMock(return_value={"status": "sent"})

    # Mock get_instance_status
    manager.get_instance_status = MagicMock(
        return_value={
            "instances": {
                "instance-1": {
                    "state": "busy",
                    "name": "worker-1",
                    "last_activity": datetime.now(UTC).isoformat(),
                },
                "instance-2": {
                    "state": "idle",
                    "name": "worker-2",
                    "last_activity": datetime.now(UTC).isoformat(),
                },
            },
            "total_instances": 2,
            "active_instances": 2,
        }
    )

    # Mock get_tmux_pane_content
    manager.get_tmux_pane_content = AsyncMock(
        return_value=("Working on task...\nRunning tests...\nCompleted successfully!")
    )

    return manager


@pytest.mark.asyncio
async def test_spawn_supervisor(mock_instance_manager):
    """Test spawning a supervisor instance."""
    config = SupervisionConfig(
        evaluation_interval_seconds=1,  # Fast for testing
        stuck_threshold_seconds=10,
    )

    supervisor_id, supervisor = await spawn_supervisor(
        instance_manager=mock_instance_manager,
        config=config,
        auto_start=False,  # Don't auto-start for this test
    )

    # Verify supervisor instance was spawned
    assert supervisor_id == "supervisor-test-id"
    assert isinstance(supervisor, SupervisorAgent)
    assert supervisor.config == config
    assert supervisor.manager == mock_instance_manager

    # Verify spawn was called with correct parameters
    mock_instance_manager.spawn_instance.assert_called_once()
    call_kwargs = mock_instance_manager.spawn_instance.call_args.kwargs
    assert call_kwargs["name"] == "network-supervisor"
    # Note: enable_madrox parameter has been removed - Madrox is always enabled
    assert "system_prompt" in call_kwargs


@pytest.mark.asyncio
async def test_attach_supervisor(mock_instance_manager):
    """Test attaching supervisor without spawning."""
    config = SupervisionConfig(evaluation_interval_seconds=1)

    supervisor = await attach_supervisor(
        instance_manager=mock_instance_manager,
        config=config,
    )

    # Verify supervisor was created but not spawned
    assert isinstance(supervisor, SupervisorAgent)
    assert supervisor.config == config
    assert supervisor.manager == mock_instance_manager
    assert not supervisor.running

    # Verify no spawn call
    mock_instance_manager.spawn_instance.assert_not_called()


@pytest.mark.asyncio
async def test_supervisor_detects_active_instances(mock_instance_manager):
    """Test supervisor can detect active instances."""
    supervisor = SupervisorAgent(
        instance_manager=mock_instance_manager,
        config=SupervisionConfig(),
    )

    active_instances = await supervisor._get_active_instances()

    # Should detect both instances
    assert len(active_instances) == 2
    assert "instance-1" in active_instances
    assert "instance-2" in active_instances


@pytest.mark.asyncio
async def test_supervisor_fetches_transcripts(mock_instance_manager):
    """Test supervisor can fetch instance transcripts."""
    supervisor = SupervisorAgent(
        instance_manager=mock_instance_manager,
        config=SupervisionConfig(),
    )

    # Detect issues for instance-1
    issues = await supervisor._detect_instance_issues("instance-1")

    # Verify transcript was fetched
    mock_instance_manager.get_tmux_pane_content.assert_called_once_with("instance-1", lines=200)

    # Issues list may be empty if transcript looks healthy
    assert isinstance(issues, list)


@pytest.mark.asyncio
async def test_supervisor_sends_intervention(mock_instance_manager):
    """Test supervisor sends intervention messages."""
    supervisor = SupervisorAgent(
        instance_manager=mock_instance_manager,
        config=SupervisionConfig(),
    )

    # Create a detected issue
    issue = DetectedIssue(
        instance_id="instance-1",
        issue_type="stuck",
        severity=IssueSeverity.WARNING,
        description="Instance appears stuck",
        detected_at=datetime.now(UTC),
        confidence=0.8,
        evidence={},
    )

    # Handle the issue
    await supervisor._handle_issue(issue)

    # Verify intervention was sent
    await asyncio.sleep(0.1)  # Give async tasks time to complete
    mock_instance_manager.send_to_instance.assert_called()

    # Check message content
    call_args = mock_instance_manager.send_to_instance.call_args
    assert call_args.kwargs["instance_id"] == "instance-1"
    assert "status check" in call_args.kwargs["message"].lower()


@pytest.mark.asyncio
async def test_supervisor_respects_intervention_limits(mock_instance_manager):
    """Test supervisor respects max intervention limits."""
    config = SupervisionConfig(
        max_interventions_per_instance=2,
        intervention_cooldown_seconds=0,  # No cooldown for testing
    )

    supervisor = SupervisorAgent(
        instance_manager=mock_instance_manager,
        config=config,
    )

    issue = DetectedIssue(
        instance_id="instance-1",
        issue_type="stuck",
        severity=IssueSeverity.WARNING,
        description="Stuck instance",
        detected_at=datetime.now(UTC),
        confidence=0.9,
        evidence={},
    )

    # First intervention - should succeed
    await supervisor._handle_issue(issue)
    assert supervisor.intervention_counts.get("instance-1", 0) == 1

    # Second intervention - should succeed
    await supervisor._handle_issue(issue)
    assert supervisor.intervention_counts.get("instance-1", 0) == 2

    # Third intervention - should escalate instead
    await supervisor._handle_issue(issue)
    # Count shouldn't increase beyond max
    assert supervisor.intervention_counts.get("instance-1", 0) == 2


@pytest.mark.asyncio
async def test_supervisor_respects_cooldown(mock_instance_manager):
    """Test supervisor respects intervention cooldown period."""
    config = SupervisionConfig(
        intervention_cooldown_seconds=60,  # 1 minute cooldown
    )

    supervisor = SupervisorAgent(
        instance_manager=mock_instance_manager,
        config=config,
    )

    issue = DetectedIssue(
        instance_id="instance-1",
        issue_type="stuck",
        severity=IssueSeverity.WARNING,
        description="Stuck instance",
        detected_at=datetime.now(UTC),
        confidence=0.9,
        evidence={},
    )

    # First intervention
    await supervisor._handle_issue(issue)
    first_count = len(supervisor.intervention_history)

    # Immediate second intervention - should be skipped due to cooldown
    await supervisor._handle_issue(issue)
    second_count = len(supervisor.intervention_history)

    # Count should be the same (cooldown prevented second intervention)
    assert second_count == first_count


@pytest.mark.asyncio
async def test_supervisor_network_health_summary(mock_instance_manager):
    """Test supervisor provides network health summary."""
    supervisor = SupervisorAgent(
        instance_manager=mock_instance_manager,
        config=SupervisionConfig(),
    )

    # Perform an intervention
    issue = DetectedIssue(
        instance_id="instance-1",
        issue_type="stuck",
        severity=IssueSeverity.WARNING,
        description="Test issue",
        detected_at=datetime.now(UTC),
        confidence=0.8,
        evidence={},
    )
    await supervisor._handle_issue(issue)

    # Get health summary
    health = supervisor.get_network_health_summary()

    # Verify summary structure
    assert "total_interventions" in health
    assert "active_issues" in health
    assert "successful_interventions" in health
    assert "failed_interventions" in health
    assert "progress_snapshot" in health
    assert "running" in health

    # Verify counts
    assert health["total_interventions"] >= 1
    assert isinstance(health["running"], bool)


@pytest.mark.asyncio
async def test_spawn_supervised_network(mock_instance_manager):
    """Test spawning a complete supervised network."""
    # Configure mock to return different IDs for each spawn
    spawn_ids = ["participant-1", "participant-2", "participant-3", "supervisor-id"]
    mock_instance_manager.spawn_instance = AsyncMock(side_effect=spawn_ids)

    participants = [
        {"name": "worker-1", "role": "frontend_developer"},
        {"name": "worker-2", "role": "backend_developer"},
        {"name": "worker-3", "role": "testing_specialist"},
    ]

    network = await spawn_supervised_network(
        instance_manager=mock_instance_manager,
        participant_configs=participants,
        supervision_config=SupervisionConfig(),
    )

    # Verify network structure
    assert "supervisor_id" in network
    assert "supervisor_agent" in network
    assert "participant_ids" in network
    assert "network_size" in network

    # Verify participant IDs
    assert len(network["participant_ids"]) == 3
    assert network["participant_ids"] == ["participant-1", "participant-2", "participant-3"]

    # Verify supervisor
    assert network["supervisor_id"] == "supervisor-id"
    assert isinstance(network["supervisor_agent"], SupervisorAgent)

    # Verify network size
    assert network["network_size"] == 4  # 3 participants + 1 supervisor

    # Verify spawn was called 4 times (3 participants + supervisor)
    assert mock_instance_manager.spawn_instance.call_count == 4


@pytest.mark.asyncio
async def test_supervisor_evaluation_loop(mock_instance_manager):
    """Test supervisor evaluation loop runs periodically."""
    config = SupervisionConfig(
        evaluation_interval_seconds=1,  # Fast for testing
    )

    supervisor = SupervisorAgent(
        instance_manager=mock_instance_manager,
        config=config,
    )

    # Start supervisor
    await supervisor.start()
    assert supervisor.running is True

    # Let it run for a few cycles (need >2 seconds for 2 cycles with 1s interval)
    await asyncio.sleep(2.5)

    # Verify get_instance_status was called multiple times
    assert mock_instance_manager.get_instance_status.call_count >= 2

    # Stop supervisor
    await supervisor.stop()
    assert supervisor.running is False


@pytest.mark.asyncio
async def test_supervisor_handles_missing_instance(mock_instance_manager):
    """Test supervisor handles missing instances gracefully."""
    # Configure mock to raise error for missing instance
    mock_instance_manager.get_tmux_pane_content = AsyncMock(
        side_effect=ValueError("Instance not found")
    )

    supervisor = SupervisorAgent(
        instance_manager=mock_instance_manager,
        config=SupervisionConfig(),
    )

    # Should not raise exception, just return empty issues
    issues = await supervisor._detect_instance_issues("nonexistent-instance")
    assert issues == []


@pytest.mark.asyncio
async def test_supervisor_multiple_issue_types(mock_instance_manager):
    """Test supervisor handles different issue types correctly."""
    supervisor = SupervisorAgent(
        instance_manager=mock_instance_manager,
        config=SupervisionConfig(intervention_cooldown_seconds=0),
    )

    # Test stuck issue
    stuck_issue = DetectedIssue(
        instance_id="instance-1",
        issue_type="stuck",
        severity=IssueSeverity.WARNING,
        description="Stuck",
        detected_at=datetime.now(UTC),
        confidence=0.9,
        evidence={},
    )
    await supervisor._handle_issue(stuck_issue)

    # Test waiting issue
    waiting_issue = DetectedIssue(
        instance_id="instance-2",
        issue_type="waiting",
        severity=IssueSeverity.INFO,
        description="Waiting",
        detected_at=datetime.now(UTC),
        confidence=0.8,
        evidence={},
    )
    await supervisor._handle_issue(waiting_issue)

    # Test error loop issue
    error_issue = DetectedIssue(
        instance_id="instance-1",
        issue_type="error_loop",
        severity=IssueSeverity.ERROR,
        description="Error loop",
        detected_at=datetime.now(UTC),
        confidence=0.95,
        evidence={},
    )
    await supervisor._handle_issue(error_issue)

    # Verify different intervention types were selected
    assert len(supervisor.intervention_history) == 3

    # Verify intervention types
    types = {record.intervention_type.value for record in supervisor.intervention_history}
    assert "status_check" in types
    assert "provide_guidance" in types or "reassign_work" in types
