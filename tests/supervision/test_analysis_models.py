"""Tests for analysis data models."""

from datetime import UTC, datetime

import pytest

from src.supervision.analysis.models import AnalysisResult, AnalysisStatus, Message


class TestAnalysisStatus:
    """Tests for AnalysisStatus enum."""

    def test_enum_values(self) -> None:
        """Test that all expected enum values exist."""
        assert AnalysisStatus.IN_PROGRESS.value == "in_progress"
        assert AnalysisStatus.COMPLETED.value == "completed"
        assert AnalysisStatus.BLOCKED.value == "blocked"
        assert AnalysisStatus.ERROR.value == "error"

    def test_enum_count(self) -> None:
        """Test that enum has exactly 4 values."""
        assert len(AnalysisStatus) == 4


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation(self) -> None:
        """Test creating a basic message."""
        timestamp = datetime.now(UTC)
        msg = Message(role="user", content="Hello, world!", timestamp=timestamp)

        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert msg.timestamp == timestamp
        assert msg.tool_calls == []
        assert msg.metadata == {}

    def test_message_with_tool_calls(self) -> None:
        """Test message with tool invocations."""
        tool_calls = [
            {"tool": "read_file", "args": {"path": "/tmp/test.txt"}},
            {"tool": "write_file", "args": {"path": "/tmp/output.txt", "content": "data"}},
        ]

        msg = Message(
            role="assistant",
            content="I'll read and write files",
            timestamp=datetime.now(UTC),
            tool_calls=tool_calls,
        )

        assert len(msg.tool_calls) == 2
        assert msg.tool_calls[0]["tool"] == "read_file"

    def test_message_with_metadata(self) -> None:
        """Test message with additional metadata."""
        metadata = {"model": "claude-3", "tokens": 150, "temperature": 0.7}

        msg = Message(
            role="assistant",
            content="Response with metadata",
            timestamp=datetime.now(UTC),
            metadata=metadata,
        )

        assert msg.metadata["model"] == "claude-3"
        assert msg.metadata["tokens"] == 150

    def test_message_immutability(self) -> None:
        """Test that messages are immutable."""
        msg = Message(role="user", content="Test", timestamp=datetime.now(UTC))

        with pytest.raises(AttributeError):
            msg.role = "assistant"  # type: ignore

        with pytest.raises(AttributeError):
            msg.content = "Modified"  # type: ignore


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_basic_result(self) -> None:
        """Test creating a basic analysis result."""
        result = AnalysisResult(
            status=AnalysisStatus.COMPLETED,
            tasks=["Implement feature X", "Write tests"],
            blockers=[],
            milestones=["MVP completed"],
            confidence=0.9,
        )

        assert result.status == AnalysisStatus.COMPLETED
        assert len(result.tasks) == 2
        assert len(result.blockers) == 0
        assert len(result.milestones) == 1
        assert result.confidence == 0.9
        assert result.metadata == {}

    def test_result_with_blockers(self) -> None:
        """Test result with identified blockers."""
        result = AnalysisResult(
            status=AnalysisStatus.BLOCKED,
            tasks=["Complete authentication"],
            blockers=["Missing API credentials", "Database connection failed"],
            milestones=[],
            confidence=0.85,
        )

        assert result.status == AnalysisStatus.BLOCKED
        assert len(result.blockers) == 2
        assert "Missing API credentials" in result.blockers

    def test_result_with_metadata(self) -> None:
        """Test result with analysis metadata."""
        metadata = {
            "analyzed_at": "2025-10-07T12:00:00Z",
            "message_count": 50,
            "processing_time_ms": 125,
        }

        result = AnalysisResult(
            status=AnalysisStatus.IN_PROGRESS,
            tasks=["Refactor module"],
            blockers=[],
            milestones=[],
            confidence=0.75,
            metadata=metadata,
        )

        assert result.metadata["message_count"] == 50
        assert result.metadata["processing_time_ms"] == 125

    def test_confidence_validation_valid(self) -> None:
        """Test that valid confidence values are accepted."""
        # Boundary values
        result_min = AnalysisResult(
            status=AnalysisStatus.COMPLETED,
            tasks=[],
            blockers=[],
            milestones=[],
            confidence=0.0,
        )
        assert result_min.confidence == 0.0

        result_max = AnalysisResult(
            status=AnalysisStatus.COMPLETED,
            tasks=[],
            blockers=[],
            milestones=[],
            confidence=1.0,
        )
        assert result_max.confidence == 1.0

        # Mid-range value
        result_mid = AnalysisResult(
            status=AnalysisStatus.COMPLETED,
            tasks=[],
            blockers=[],
            milestones=[],
            confidence=0.5,
        )
        assert result_mid.confidence == 0.5

    def test_confidence_validation_invalid(self) -> None:
        """Test that invalid confidence values raise ValueError."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            AnalysisResult(
                status=AnalysisStatus.COMPLETED,
                tasks=[],
                blockers=[],
                milestones=[],
                confidence=1.5,
            )

        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            AnalysisResult(
                status=AnalysisStatus.COMPLETED,
                tasks=[],
                blockers=[],
                milestones=[],
                confidence=-0.1,
            )

    def test_default_confidence(self) -> None:
        """Test that default confidence is 1.0."""
        result = AnalysisResult(
            status=AnalysisStatus.COMPLETED, tasks=[], blockers=[], milestones=[]
        )

        assert result.confidence == 1.0

    def test_result_immutability(self) -> None:
        """Test that analysis results are immutable."""
        result = AnalysisResult(
            status=AnalysisStatus.COMPLETED, tasks=["Task 1"], blockers=[], milestones=[]
        )

        with pytest.raises(AttributeError):
            result.status = AnalysisStatus.BLOCKED  # type: ignore

        with pytest.raises(AttributeError):
            result.confidence = 0.5  # type: ignore

    def test_empty_lists(self) -> None:
        """Test result with all empty lists."""
        result = AnalysisResult(
            status=AnalysisStatus.IN_PROGRESS, tasks=[], blockers=[], milestones=[], confidence=0.0
        )

        assert result.tasks == []
        assert result.blockers == []
        assert result.milestones == []
        assert result.confidence == 0.0

    def test_result_equality(self) -> None:
        """Test that two identical results are equal."""
        result1 = AnalysisResult(
            status=AnalysisStatus.COMPLETED,
            tasks=["Task A"],
            blockers=[],
            milestones=["Milestone 1"],
            confidence=0.8,
        )

        result2 = AnalysisResult(
            status=AnalysisStatus.COMPLETED,
            tasks=["Task A"],
            blockers=[],
            milestones=["Milestone 1"],
            confidence=0.8,
        )

        # Metadata doesn't affect equality by default since it uses default_factory
        assert result1 == result2
