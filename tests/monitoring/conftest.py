"""Shared fixtures for monitoring tests."""

from pathlib import Path

import pytest

from src.orchestrator.monitoring.models import AgentSummary, LogPosition, OnTrackStatus
from src.orchestrator.monitoring.position_tracker import PositionTracker


@pytest.fixture
def temp_state_dir(tmp_path: Path) -> Path:
    """Create temporary state directory for tests."""
    state_dir = tmp_path / "monitoring_state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def temp_log_file(tmp_path: Path) -> Path:
    """Create temporary log file with initial content."""
    log_file = tmp_path / "test.log"
    log_file.write_text("Line 1\nLine 2\nLine 3\n")
    return log_file


@pytest.fixture
def empty_log_file(tmp_path: Path) -> Path:
    """Create empty log file."""
    log_file = tmp_path / "empty.log"
    log_file.write_text("")
    return log_file


@pytest.fixture
def position_tracker(temp_state_dir: Path) -> PositionTracker:
    """Create PositionTracker with temporary directory."""
    return PositionTracker(state_dir=str(temp_state_dir))


@pytest.fixture
def sample_log_position() -> LogPosition:
    """Create sample LogPosition for testing."""
    return LogPosition(
        instance_id="test-instance-123",
        log_type="tmux_output",
        file_path="/tmp/test.log",
        last_byte_offset=1024,
        last_line_number=50,
        last_read_timestamp="2025-01-15T10:30:00",
        checksum="abc123def456789",
    )


@pytest.fixture
def sample_agent_summary() -> AgentSummary:
    """Create sample AgentSummary for testing."""
    return AgentSummary(
        instance_id="test-instance-123",
        instance_name="test-agent-swift-heron",
        timestamp="2025-01-15T10:30:00",
        current_activity="Running tests for monitoring system",
        on_track_status=OnTrackStatus.ON_TRACK,
        confidence_score=0.95,
        assigned_task="Test the monitoring infrastructure",
        parent_instance_id="supervisor-456",
        role="qa_engineer",
        last_tool_used="pytest",
        recent_tools=["pytest", "coverage", "mypy", "ruff"],
        output_preview="All tests passing with 95% coverage",
        idle_duration_seconds=2.5,
        drift_reasons=[],
        alignment_keywords=["test", "monitoring", "coverage"],
        recommended_action="continue",
    )
