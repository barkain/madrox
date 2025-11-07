"""Tests for monitoring data models."""

import pytest

from orchestrator.monitoring.models import AgentSummary, LogPosition, OnTrackStatus


class TestOnTrackStatus:
    """Tests for OnTrackStatus enum."""

    def test_enum_values(self) -> None:
        """Test that all expected enum values exist."""
        assert OnTrackStatus.ON_TRACK.value == "on_track"
        assert OnTrackStatus.DRIFTING.value == "drifting"
        assert OnTrackStatus.OFF_TRACK.value == "off_track"
        assert OnTrackStatus.BLOCKED.value == "blocked"
        assert OnTrackStatus.UNKNOWN.value == "unknown"

    def test_enum_count(self) -> None:
        """Test that enum has exactly 5 values."""
        assert len(OnTrackStatus) == 5

    def test_enum_membership(self) -> None:
        """Test enum membership checks."""
        assert OnTrackStatus.ON_TRACK in OnTrackStatus
        assert OnTrackStatus.DRIFTING in OnTrackStatus
        assert OnTrackStatus.OFF_TRACK in OnTrackStatus
        assert OnTrackStatus.BLOCKED in OnTrackStatus
        assert OnTrackStatus.UNKNOWN in OnTrackStatus

    def test_enum_from_value(self) -> None:
        """Test creating enum from string value."""
        assert OnTrackStatus("on_track") == OnTrackStatus.ON_TRACK
        assert OnTrackStatus("drifting") == OnTrackStatus.DRIFTING
        assert OnTrackStatus("off_track") == OnTrackStatus.OFF_TRACK
        assert OnTrackStatus("blocked") == OnTrackStatus.BLOCKED
        assert OnTrackStatus("unknown") == OnTrackStatus.UNKNOWN


class TestLogPosition:
    """Tests for LogPosition dataclass."""

    def test_creation(self, sample_log_position: LogPosition) -> None:
        """Test basic LogPosition creation."""
        assert sample_log_position.instance_id == "test-instance-123"
        assert sample_log_position.log_type == "tmux_output"
        assert sample_log_position.file_path == "/tmp/test.log"
        assert sample_log_position.last_byte_offset == 1024
        assert sample_log_position.last_line_number == 50
        assert sample_log_position.last_read_timestamp == "2025-01-15T10:30:00"
        assert sample_log_position.checksum == "abc123def456789"

    def test_all_fields_required(self) -> None:
        """Test that all fields are required."""
        with pytest.raises(TypeError):
            LogPosition()  # type: ignore

    def test_minimal_creation(self) -> None:
        """Test creating LogPosition with minimal data."""
        pos = LogPosition(
            instance_id="id",
            log_type="type",
            file_path="/path",
            last_byte_offset=0,
            last_line_number=0,
            last_read_timestamp="2025-01-15T00:00:00",
            checksum="checksum",
        )
        assert pos.instance_id == "id"
        assert pos.last_byte_offset == 0
        assert pos.last_line_number == 0

    def test_zero_offset_and_line(self) -> None:
        """Test that zero offset and line number are valid."""
        pos = LogPosition(
            instance_id="test",
            log_type="tmux_output",
            file_path="/test.log",
            last_byte_offset=0,
            last_line_number=0,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="abc",
        )
        assert pos.last_byte_offset == 0
        assert pos.last_line_number == 0

    def test_large_offset_and_line(self) -> None:
        """Test handling large offset and line numbers."""
        pos = LogPosition(
            instance_id="test",
            log_type="tmux_output",
            file_path="/test.log",
            last_byte_offset=1_000_000_000,
            last_line_number=10_000_000,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="abc",
        )
        assert pos.last_byte_offset == 1_000_000_000
        assert pos.last_line_number == 10_000_000

    def test_different_log_types(self) -> None:
        """Test different log type values."""
        for log_type in ["tmux_output", "instance", "communication"]:
            pos = LogPosition(
                instance_id="test",
                log_type=log_type,
                file_path="/test.log",
                last_byte_offset=0,
                last_line_number=0,
                last_read_timestamp="2025-01-15T10:00:00",
                checksum="abc",
            )
            assert pos.log_type == log_type

    def test_equality(self) -> None:
        """Test LogPosition equality."""
        pos1 = LogPosition(
            instance_id="test",
            log_type="tmux_output",
            file_path="/test.log",
            last_byte_offset=100,
            last_line_number=10,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="abc",
        )
        pos2 = LogPosition(
            instance_id="test",
            log_type="tmux_output",
            file_path="/test.log",
            last_byte_offset=100,
            last_line_number=10,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="abc",
        )
        assert pos1 == pos2


class TestAgentSummary:
    """Tests for AgentSummary dataclass."""

    def test_creation(self, sample_agent_summary: AgentSummary) -> None:
        """Test basic AgentSummary creation."""
        assert sample_agent_summary.instance_id == "test-instance-123"
        assert sample_agent_summary.instance_name == "test-agent-swift-heron"
        assert sample_agent_summary.timestamp == "2025-01-15T10:30:00"
        assert sample_agent_summary.current_activity == "Running tests for monitoring system"
        assert sample_agent_summary.on_track_status == OnTrackStatus.ON_TRACK
        assert sample_agent_summary.confidence_score == 0.95
        assert sample_agent_summary.assigned_task == "Test the monitoring infrastructure"
        assert sample_agent_summary.parent_instance_id == "supervisor-456"
        assert sample_agent_summary.role == "qa_engineer"
        assert sample_agent_summary.last_tool_used == "pytest"
        assert len(sample_agent_summary.recent_tools) == 4
        assert sample_agent_summary.idle_duration_seconds == 2.5
        assert len(sample_agent_summary.drift_reasons) == 0
        assert len(sample_agent_summary.alignment_keywords) == 3

    def test_with_none_optional_fields(self) -> None:
        """Test creating AgentSummary with None optional fields."""
        summary = AgentSummary(
            instance_id="test",
            instance_name="test-agent",
            timestamp="2025-01-15T10:00:00",
            current_activity="Working",
            on_track_status=OnTrackStatus.ON_TRACK,
            confidence_score=0.9,
            assigned_task=None,
            parent_instance_id=None,
            role=None,
            last_tool_used=None,
            recent_tools=[],
            output_preview="",
            idle_duration_seconds=0.0,
            drift_reasons=[],
            alignment_keywords=[],
            recommended_action=None,
        )
        assert summary.assigned_task is None
        assert summary.parent_instance_id is None
        assert summary.role is None
        assert summary.last_tool_used is None
        assert summary.recommended_action is None

    def test_confidence_score_boundaries(self) -> None:
        """Test confidence score at boundaries."""
        # Test 0.0
        summary = AgentSummary(
            instance_id="test",
            instance_name="test-agent",
            timestamp="2025-01-15T10:00:00",
            current_activity="Working",
            on_track_status=OnTrackStatus.UNKNOWN,
            confidence_score=0.0,
            assigned_task="Task",
            parent_instance_id=None,
            role=None,
            last_tool_used=None,
            recent_tools=[],
            output_preview="",
            idle_duration_seconds=0.0,
            drift_reasons=[],
            alignment_keywords=[],
            recommended_action=None,
        )
        assert summary.confidence_score == 0.0

        # Test 1.0
        summary2 = AgentSummary(
            instance_id="test",
            instance_name="test-agent",
            timestamp="2025-01-15T10:00:00",
            current_activity="Working",
            on_track_status=OnTrackStatus.ON_TRACK,
            confidence_score=1.0,
            assigned_task="Task",
            parent_instance_id=None,
            role=None,
            last_tool_used=None,
            recent_tools=[],
            output_preview="",
            idle_duration_seconds=0.0,
            drift_reasons=[],
            alignment_keywords=[],
            recommended_action=None,
        )
        assert summary2.confidence_score == 1.0

    def test_different_on_track_statuses(self) -> None:
        """Test different OnTrackStatus values."""
        for status in OnTrackStatus:
            summary = AgentSummary(
                instance_id="test",
                instance_name="test-agent",
                timestamp="2025-01-15T10:00:00",
                current_activity="Working",
                on_track_status=status,
                confidence_score=0.8,
                assigned_task="Task",
                parent_instance_id=None,
                role=None,
                last_tool_used=None,
                recent_tools=[],
                output_preview="",
                idle_duration_seconds=0.0,
                drift_reasons=[],
                alignment_keywords=[],
                recommended_action=None,
            )
            assert summary.on_track_status == status

    def test_recent_tools_list(self) -> None:
        """Test recent_tools list handling."""
        tools = ["Read", "Write", "Grep", "Bash", "Edit"]
        summary = AgentSummary(
            instance_id="test",
            instance_name="test-agent",
            timestamp="2025-01-15T10:00:00",
            current_activity="Working",
            on_track_status=OnTrackStatus.ON_TRACK,
            confidence_score=0.9,
            assigned_task="Task",
            parent_instance_id=None,
            role=None,
            last_tool_used="Edit",
            recent_tools=tools,
            output_preview="",
            idle_duration_seconds=0.0,
            drift_reasons=[],
            alignment_keywords=[],
            recommended_action=None,
        )
        assert summary.recent_tools == tools
        assert len(summary.recent_tools) == 5

    def test_drift_reasons_list(self) -> None:
        """Test drift_reasons list handling."""
        reasons = ["Working on unrelated task", "Using wrong tools"]
        summary = AgentSummary(
            instance_id="test",
            instance_name="test-agent",
            timestamp="2025-01-15T10:00:00",
            current_activity="Working",
            on_track_status=OnTrackStatus.DRIFTING,
            confidence_score=0.6,
            assigned_task="Task A",
            parent_instance_id=None,
            role=None,
            last_tool_used=None,
            recent_tools=[],
            output_preview="",
            idle_duration_seconds=0.0,
            drift_reasons=reasons,
            alignment_keywords=[],
            recommended_action="Check task assignment",
        )
        assert summary.drift_reasons == reasons
        assert len(summary.drift_reasons) == 2

    def test_alignment_keywords_list(self) -> None:
        """Test alignment_keywords list handling."""
        keywords = ["test", "pytest", "coverage", "monitoring"]
        summary = AgentSummary(
            instance_id="test",
            instance_name="test-agent",
            timestamp="2025-01-15T10:00:00",
            current_activity="Working",
            on_track_status=OnTrackStatus.ON_TRACK,
            confidence_score=0.9,
            assigned_task="Task",
            parent_instance_id=None,
            role=None,
            last_tool_used=None,
            recent_tools=[],
            output_preview="",
            idle_duration_seconds=0.0,
            drift_reasons=[],
            alignment_keywords=keywords,
            recommended_action=None,
        )
        assert summary.alignment_keywords == keywords
        assert len(summary.alignment_keywords) == 4

    def test_output_preview_length(self) -> None:
        """Test output_preview with different lengths."""
        # Short preview
        summary1 = AgentSummary(
            instance_id="test",
            instance_name="test-agent",
            timestamp="2025-01-15T10:00:00",
            current_activity="Working",
            on_track_status=OnTrackStatus.ON_TRACK,
            confidence_score=0.9,
            assigned_task="Task",
            parent_instance_id=None,
            role=None,
            last_tool_used=None,
            recent_tools=[],
            output_preview="Short",
            idle_duration_seconds=0.0,
            drift_reasons=[],
            alignment_keywords=[],
            recommended_action=None,
        )
        assert summary1.output_preview == "Short"

        # Long preview (200 chars as per spec)
        long_text = "x" * 200
        summary2 = AgentSummary(
            instance_id="test",
            instance_name="test-agent",
            timestamp="2025-01-15T10:00:00",
            current_activity="Working",
            on_track_status=OnTrackStatus.ON_TRACK,
            confidence_score=0.9,
            assigned_task="Task",
            parent_instance_id=None,
            role=None,
            last_tool_used=None,
            recent_tools=[],
            output_preview=long_text,
            idle_duration_seconds=0.0,
            drift_reasons=[],
            alignment_keywords=[],
            recommended_action=None,
        )
        assert len(summary2.output_preview) == 200

    def test_idle_duration_zero(self) -> None:
        """Test idle_duration_seconds at zero."""
        summary = AgentSummary(
            instance_id="test",
            instance_name="test-agent",
            timestamp="2025-01-15T10:00:00",
            current_activity="Working",
            on_track_status=OnTrackStatus.ON_TRACK,
            confidence_score=0.9,
            assigned_task="Task",
            parent_instance_id=None,
            role=None,
            last_tool_used=None,
            recent_tools=[],
            output_preview="",
            idle_duration_seconds=0.0,
            drift_reasons=[],
            alignment_keywords=[],
            recommended_action=None,
        )
        assert summary.idle_duration_seconds == 0.0

    def test_idle_duration_positive(self) -> None:
        """Test idle_duration_seconds with positive values."""
        summary = AgentSummary(
            instance_id="test",
            instance_name="test-agent",
            timestamp="2025-01-15T10:00:00",
            current_activity="Working",
            on_track_status=OnTrackStatus.ON_TRACK,
            confidence_score=0.9,
            assigned_task="Task",
            parent_instance_id=None,
            role=None,
            last_tool_used=None,
            recent_tools=[],
            output_preview="",
            idle_duration_seconds=123.456,
            drift_reasons=[],
            alignment_keywords=[],
            recommended_action=None,
        )
        assert summary.idle_duration_seconds == 123.456
