"""Tests for IncrementalLogReader."""

import hashlib
from pathlib import Path

import pytest

from orchestrator.monitoring.log_reader import IncrementalLogReader
from orchestrator.monitoring.models import LogPosition
from orchestrator.monitoring.position_tracker import PositionTracker


class TestIncrementalLogReaderBasic:
    """Tests for basic log reading functionality."""

    def test_read_new_content_first_time(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test first-time reading of a log file."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        new_lines, total_lines = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )

        assert len(new_lines) == 3
        assert new_lines == ["Line 1", "Line 2", "Line 3"]
        assert total_lines == 3

    def test_read_new_content_no_new_lines(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test reading when there are no new lines."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        # First read
        reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )

        # Second read without adding new content
        new_lines, total_lines = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )

        assert len(new_lines) == 0
        assert total_lines == 3

    def test_read_new_content_incremental(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test incremental reading when new lines are appended."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        # First read
        first_lines, first_total = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )
        assert len(first_lines) == 3
        assert first_total == 3

        # Append new lines
        with temp_log_file.open("a") as f:
            f.write("Line 4\nLine 5\n")

        # Second read
        second_lines, second_total = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )
        assert len(second_lines) == 2
        assert second_lines == ["Line 4", "Line 5"]
        assert second_total == 5

    def test_read_empty_file(
        self, empty_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test reading an empty log file."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        new_lines, total_lines = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=empty_log_file,
            log_type="tmux_output",
        )

        assert len(new_lines) == 0
        assert total_lines == 0

    def test_read_nonexistent_file(
        self, tmp_path: Path, position_tracker: PositionTracker
    ) -> None:
        """Test reading a file that doesn't exist."""
        nonexistent = tmp_path / "nonexistent.log"
        reader = IncrementalLogReader(position_tracker=position_tracker)

        new_lines, total_lines = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=nonexistent,
            log_type="tmux_output",
        )

        assert len(new_lines) == 0
        assert total_lines == 0


class TestIncrementalLogReaderMaxLines:
    """Tests for max_lines limiting."""

    def test_max_lines_limit(
        self, tmp_path: Path, position_tracker: PositionTracker
    ) -> None:
        """Test that max_lines limits the number of lines read."""
        log_file = tmp_path / "large.log"
        lines = [f"Line {i}" for i in range(100)]
        log_file.write_text("\n".join(lines) + "\n")

        reader = IncrementalLogReader(position_tracker=position_tracker, max_lines_per_read=10)

        new_lines, total_lines = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=log_file,
            log_type="tmux_output",
        )

        assert len(new_lines) == 10
        assert new_lines[0] == "Line 0"
        assert new_lines[9] == "Line 9"
        assert total_lines == 10

    def test_max_lines_multiple_reads(
        self, tmp_path: Path, position_tracker: PositionTracker
    ) -> None:
        """Test multiple reads with max_lines limit."""
        log_file = tmp_path / "large.log"
        lines = [f"Line {i}" for i in range(30)]
        log_file.write_text("\n".join(lines) + "\n")

        reader = IncrementalLogReader(position_tracker=position_tracker, max_lines_per_read=10)

        # First read: lines 0-9
        lines1, total1 = reader.read_new_content(
            instance_id="test-instance", log_file_path=log_file, log_type="tmux_output"
        )
        assert len(lines1) == 10
        assert total1 == 10

        # Second read: lines 10-19
        lines2, total2 = reader.read_new_content(
            instance_id="test-instance", log_file_path=log_file, log_type="tmux_output"
        )
        assert len(lines2) == 10
        assert total2 == 20

        # Third read: lines 20-29
        lines3, total3 = reader.read_new_content(
            instance_id="test-instance", log_file_path=log_file, log_type="tmux_output"
        )
        assert len(lines3) == 10
        assert total3 == 30

        # Fourth read: no more lines
        lines4, total4 = reader.read_new_content(
            instance_id="test-instance", log_file_path=log_file, log_type="tmux_output"
        )
        assert len(lines4) == 0
        assert total4 == 30


class TestIncrementalLogReaderRotation:
    """Tests for log rotation detection."""

    def test_detect_log_rotation_checksum(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test that log rotation is detected via checksum change."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        # First read
        first_lines, first_total = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )
        assert len(first_lines) == 3
        assert first_total == 3

        # Simulate log rotation by replacing file content
        temp_log_file.write_text("New Line 1\nNew Line 2\n")

        # Second read should detect rotation and read from beginning
        second_lines, second_total = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )
        assert len(second_lines) == 2
        assert second_lines == ["New Line 1", "New Line 2"]
        assert second_total == 2

    def test_detect_file_truncation(
        self, tmp_path: Path, position_tracker: PositionTracker
    ) -> None:
        """Test detection when file is truncated."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")

        reader = IncrementalLogReader(position_tracker=position_tracker)

        # First read
        reader.read_new_content(
            instance_id="test-instance",
            log_file_path=log_file,
            log_type="tmux_output",
        )

        # Truncate file (smaller than previous offset)
        log_file.write_text("Line 1\nLine 2\n")

        # Should detect truncation and read from beginning
        new_lines, total_lines = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=log_file,
            log_type="tmux_output",
        )
        assert len(new_lines) == 2
        assert new_lines == ["Line 1", "Line 2"]


class TestIncrementalLogReaderPositionTracking:
    """Tests for position tracking integration."""

    def test_position_saved_after_read(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test that position is saved after reading."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )

        position = position_tracker.get_position("test-instance", "tmux_output")
        assert position is not None
        assert position.instance_id == "test-instance"
        assert position.log_type == "tmux_output"
        assert position.last_byte_offset > 0
        assert position.last_line_number == 3
        assert position.checksum != ""

    def test_position_updated_on_subsequent_read(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test that position is updated on subsequent reads."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        # First read
        reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )
        first_position = position_tracker.get_position("test-instance", "tmux_output")
        assert first_position is not None
        first_offset = first_position.last_byte_offset

        # Append more lines
        with temp_log_file.open("a") as f:
            f.write("Line 4\n")

        # Second read
        reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )
        second_position = position_tracker.get_position("test-instance", "tmux_output")
        assert second_position is not None
        assert second_position.last_byte_offset > first_offset
        assert second_position.last_line_number == 4

    def test_different_instances_tracked_separately(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test that different instances are tracked separately."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        # Read with instance 1
        reader.read_new_content(
            instance_id="instance-1",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )

        # Read with instance 2 (should start from beginning)
        lines, total = reader.read_new_content(
            instance_id="instance-2",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )

        assert len(lines) == 3
        assert total == 3

        # Verify both positions exist
        pos1 = position_tracker.get_position("instance-1", "tmux_output")
        pos2 = position_tracker.get_position("instance-2", "tmux_output")
        assert pos1 is not None
        assert pos2 is not None


class TestIncrementalLogReaderResetPosition:
    """Tests for reset_position functionality."""

    def test_reset_position(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test that reset_position clears the position."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        # First read
        reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )
        assert position_tracker.get_position("test-instance", "tmux_output") is not None

        # Reset position
        reader.reset_position("test-instance", "tmux_output")
        assert position_tracker.get_position("test-instance", "tmux_output") is None

    def test_read_after_reset(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test reading after resetting position."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        # First read
        reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )

        # Reset
        reader.reset_position("test-instance", "tmux_output")

        # Read again (should read from beginning)
        new_lines, total_lines = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=temp_log_file,
            log_type="tmux_output",
        )
        assert len(new_lines) == 3
        assert total_lines == 3


class TestIncrementalLogReaderLastNLines:
    """Tests for read_last_n_lines utility method."""

    def test_read_last_n_lines(
        self, tmp_path: Path, position_tracker: PositionTracker
    ) -> None:
        """Test reading last N lines from a file."""
        log_file = tmp_path / "test.log"
        lines = [f"Line {i}" for i in range(10)]
        log_file.write_text("\n".join(lines) + "\n")

        reader = IncrementalLogReader(position_tracker=position_tracker)
        last_lines = reader.read_last_n_lines(log_file, n=3)

        assert len(last_lines) == 3
        assert last_lines == ["Line 7", "Line 8", "Line 9"]

    def test_read_last_n_lines_fewer_than_n(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test reading last N lines when file has fewer lines."""
        reader = IncrementalLogReader(position_tracker=position_tracker)
        last_lines = reader.read_last_n_lines(temp_log_file, n=100)

        assert len(last_lines) == 3
        assert last_lines == ["Line 1", "Line 2", "Line 3"]

    def test_read_last_n_lines_empty_file(
        self, empty_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test reading last N lines from empty file."""
        reader = IncrementalLogReader(position_tracker=position_tracker)
        last_lines = reader.read_last_n_lines(empty_log_file, n=10)

        assert len(last_lines) == 0

    def test_read_last_n_lines_nonexistent(
        self, tmp_path: Path, position_tracker: PositionTracker
    ) -> None:
        """Test reading last N lines from nonexistent file."""
        nonexistent = tmp_path / "nonexistent.log"
        reader = IncrementalLogReader(position_tracker=position_tracker)
        last_lines = reader.read_last_n_lines(nonexistent, n=10)

        assert len(last_lines) == 0

    def test_read_last_n_lines_no_position_tracking(
        self, tmp_path: Path, position_tracker: PositionTracker
    ) -> None:
        """Test that read_last_n_lines doesn't affect position tracking."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\n")

        reader = IncrementalLogReader(position_tracker=position_tracker)

        # Use read_last_n_lines
        reader.read_last_n_lines(log_file, n=2)

        # Position should not be set
        position = position_tracker.get_position("test-instance", "tmux_output")
        assert position is None


class TestIncrementalLogReaderEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_long_lines(
        self, tmp_path: Path, position_tracker: PositionTracker
    ) -> None:
        """Test handling of very long lines."""
        log_file = tmp_path / "long.log"
        long_line = "x" * 10000
        log_file.write_text(f"{long_line}\nShort line\n")

        reader = IncrementalLogReader(position_tracker=position_tracker)
        new_lines, total_lines = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=log_file,
            log_type="tmux_output",
        )

        assert len(new_lines) == 2
        assert len(new_lines[0]) == 10000
        assert new_lines[1] == "Short line"

    def test_unicode_content(
        self, tmp_path: Path, position_tracker: PositionTracker
    ) -> None:
        """Test handling of Unicode characters."""
        log_file = tmp_path / "unicode.log"
        log_file.write_text("Hello 世界\nEmoji 🚀\n", encoding="utf-8")

        reader = IncrementalLogReader(position_tracker=position_tracker)
        new_lines, total_lines = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=log_file,
            log_type="tmux_output",
        )

        assert len(new_lines) == 2
        assert "世界" in new_lines[0]
        assert "🚀" in new_lines[1]

    def test_empty_lines(self, tmp_path: Path, position_tracker: PositionTracker) -> None:
        """Test handling of empty lines in file."""
        log_file = tmp_path / "empty_lines.log"
        log_file.write_text("Line 1\n\n\nLine 2\n")

        reader = IncrementalLogReader(position_tracker=position_tracker)
        new_lines, total_lines = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=log_file,
            log_type="tmux_output",
        )

        assert len(new_lines) == 4
        assert new_lines[0] == "Line 1"
        assert new_lines[1] == ""
        assert new_lines[2] == ""
        assert new_lines[3] == "Line 2"

    def test_no_trailing_newline(
        self, tmp_path: Path, position_tracker: PositionTracker
    ) -> None:
        """Test file without trailing newline."""
        log_file = tmp_path / "no_newline.log"
        log_file.write_text("Line 1\nLine 2")  # No trailing newline

        reader = IncrementalLogReader(position_tracker=position_tracker)
        new_lines, total_lines = reader.read_new_content(
            instance_id="test-instance",
            log_file_path=log_file,
            log_type="tmux_output",
        )

        assert len(new_lines) == 2
        assert new_lines[0] == "Line 1"
        assert new_lines[1] == "Line 2"


class TestIncrementalLogReaderChecksumCalculation:
    """Tests for checksum calculation."""

    def test_checksum_consistency(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test that checksum is consistent for same file content."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        # Read twice
        reader.read_new_content("instance1", temp_log_file, "tmux_output")
        reader.read_new_content("instance2", temp_log_file, "tmux_output")

        pos1 = position_tracker.get_position("instance1", "tmux_output")
        pos2 = position_tracker.get_position("instance2", "tmux_output")

        assert pos1 is not None
        assert pos2 is not None
        assert pos1.checksum == pos2.checksum

    def test_checksum_changes_on_content_change(
        self, temp_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test that checksum changes when content changes."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        # First read
        reader.read_new_content("test-instance", temp_log_file, "tmux_output")
        pos1 = position_tracker.get_position("test-instance", "tmux_output")
        assert pos1 is not None
        first_checksum = pos1.checksum

        # Change content
        temp_log_file.write_text("Different content\n")

        # Second read
        reader.read_new_content("test-instance", temp_log_file, "tmux_output")
        pos2 = position_tracker.get_position("test-instance", "tmux_output")
        assert pos2 is not None
        second_checksum = pos2.checksum

        assert first_checksum != second_checksum

    def test_checksum_for_empty_file(
        self, empty_log_file: Path, position_tracker: PositionTracker
    ) -> None:
        """Test checksum handling for empty file."""
        reader = IncrementalLogReader(position_tracker=position_tracker)

        reader.read_new_content("test-instance", empty_log_file, "tmux_output")

        # Position should not be saved for empty file
        position = position_tracker.get_position("test-instance", "tmux_output")
        # Empty file returns early, so no position is saved
        assert position is None
