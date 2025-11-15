"""Tests for PositionTracker."""

import json
import threading
import time
from pathlib import Path

from src.orchestrator.monitoring.models import LogPosition
from src.orchestrator.monitoring.position_tracker import PositionTracker


class TestPositionTrackerBasicCRUD:
    """Tests for basic CRUD operations."""

    def test_get_position_not_found(self, position_tracker: PositionTracker) -> None:
        """Test that get_position returns None for non-existent position."""
        result = position_tracker.get_position("nonexistent", "tmux_output")
        assert result is None

    def test_update_and_get_position(
        self, position_tracker: PositionTracker, sample_log_position: LogPosition
    ) -> None:
        """Test updating and retrieving a position."""
        position_tracker.update_position(sample_log_position)

        retrieved = position_tracker.get_position(
            sample_log_position.instance_id, sample_log_position.log_type
        )
        assert retrieved is not None
        assert retrieved.instance_id == sample_log_position.instance_id
        assert retrieved.log_type == sample_log_position.log_type
        assert retrieved.last_byte_offset == sample_log_position.last_byte_offset
        assert retrieved.last_line_number == sample_log_position.last_line_number
        assert retrieved.checksum == sample_log_position.checksum

    def test_update_existing_position(
        self, position_tracker: PositionTracker, sample_log_position: LogPosition
    ) -> None:
        """Test updating an existing position."""
        # Add initial position
        position_tracker.update_position(sample_log_position)

        # Update with new values
        updated_position = LogPosition(
            instance_id=sample_log_position.instance_id,
            log_type=sample_log_position.log_type,
            file_path=sample_log_position.file_path,
            last_byte_offset=2048,
            last_line_number=100,
            last_read_timestamp="2025-01-15T11:00:00",
            checksum="newchecksum",
        )
        position_tracker.update_position(updated_position)

        # Verify update
        retrieved = position_tracker.get_position(
            sample_log_position.instance_id, sample_log_position.log_type
        )
        assert retrieved is not None
        assert retrieved.last_byte_offset == 2048
        assert retrieved.last_line_number == 100
        assert retrieved.checksum == "newchecksum"

    def test_remove_position(
        self, position_tracker: PositionTracker, sample_log_position: LogPosition
    ) -> None:
        """Test removing a position."""
        # Add position
        position_tracker.update_position(sample_log_position)
        assert (
            position_tracker.get_position(
                sample_log_position.instance_id, sample_log_position.log_type
            )
            is not None
        )

        # Remove position
        position_tracker.remove_position(
            sample_log_position.instance_id, sample_log_position.log_type
        )

        # Verify removal
        assert (
            position_tracker.get_position(
                sample_log_position.instance_id, sample_log_position.log_type
            )
            is None
        )

    def test_remove_nonexistent_position(self, position_tracker: PositionTracker) -> None:
        """Test removing a position that doesn't exist (should not error)."""
        position_tracker.remove_position("nonexistent", "tmux_output")
        # Should complete without error

    def test_get_all_positions_empty(self, position_tracker: PositionTracker) -> None:
        """Test get_all_positions when empty."""
        positions = position_tracker.get_all_positions()
        assert positions == []

    def test_get_all_positions_multiple(self, position_tracker: PositionTracker) -> None:
        """Test get_all_positions with multiple positions."""
        pos1 = LogPosition(
            instance_id="instance1",
            log_type="tmux_output",
            file_path="/tmp/test1.log",
            last_byte_offset=100,
            last_line_number=10,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="checksum1",
        )
        pos2 = LogPosition(
            instance_id="instance2",
            log_type="tmux_output",
            file_path="/tmp/test2.log",
            last_byte_offset=200,
            last_line_number=20,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="checksum2",
        )
        pos3 = LogPosition(
            instance_id="instance1",
            log_type="instance",
            file_path="/tmp/test3.log",
            last_byte_offset=300,
            last_line_number=30,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="checksum3",
        )

        position_tracker.update_position(pos1)
        position_tracker.update_position(pos2)
        position_tracker.update_position(pos3)

        positions = position_tracker.get_all_positions()
        assert len(positions) == 3

        instance_ids = {p.instance_id for p in positions}
        assert "instance1" in instance_ids
        assert "instance2" in instance_ids

    def test_clear_all_positions(self, position_tracker: PositionTracker) -> None:
        """Test clearing all positions."""
        pos1 = LogPosition(
            instance_id="instance1",
            log_type="tmux_output",
            file_path="/tmp/test1.log",
            last_byte_offset=100,
            last_line_number=10,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="checksum1",
        )
        position_tracker.update_position(pos1)
        assert len(position_tracker.get_all_positions()) == 1

        position_tracker.clear_all_positions()
        assert len(position_tracker.get_all_positions()) == 0


class TestPositionTrackerPersistence:
    """Tests for position persistence to disk."""

    def test_persistence_across_instances(
        self, temp_state_dir: Path, sample_log_position: LogPosition
    ) -> None:
        """Test that positions persist across PositionTracker instances."""
        # Create first tracker and save position
        tracker1 = PositionTracker(state_dir=str(temp_state_dir))
        tracker1.update_position(sample_log_position)

        # Create second tracker (should load from disk)
        tracker2 = PositionTracker(state_dir=str(temp_state_dir))
        retrieved = tracker2.get_position(
            sample_log_position.instance_id, sample_log_position.log_type
        )

        assert retrieved is not None
        assert retrieved.instance_id == sample_log_position.instance_id
        assert retrieved.last_byte_offset == sample_log_position.last_byte_offset
        assert retrieved.checksum == sample_log_position.checksum

    def test_state_file_created(
        self, temp_state_dir: Path, sample_log_position: LogPosition
    ) -> None:
        """Test that state file is created on disk."""
        tracker = PositionTracker(state_dir=str(temp_state_dir))
        state_file = temp_state_dir / "monitor_positions.json"

        # File might not exist initially
        tracker.update_position(sample_log_position)

        # File should exist after update
        assert state_file.exists()

    def test_state_file_json_format(
        self, temp_state_dir: Path, sample_log_position: LogPosition
    ) -> None:
        """Test that state file contains valid JSON."""
        tracker = PositionTracker(state_dir=str(temp_state_dir))
        tracker.update_position(sample_log_position)

        state_file = temp_state_dir / "monitor_positions.json"
        with state_file.open("r") as f:
            data = json.load(f)

        assert isinstance(data, dict)
        key = f"{sample_log_position.instance_id}:{sample_log_position.log_type}"
        assert key in data
        assert data[key]["instance_id"] == sample_log_position.instance_id
        assert data[key]["last_byte_offset"] == sample_log_position.last_byte_offset

    def test_corrupted_state_recovery(self, temp_state_dir: Path) -> None:
        """Test that corrupted state file is handled gracefully."""
        state_file = temp_state_dir / "monitor_positions.json"
        state_file.write_text("invalid json {{{")

        # Should not crash, should start with empty state
        tracker = PositionTracker(state_dir=str(temp_state_dir))
        assert len(tracker.get_all_positions()) == 0

    def test_missing_state_directory_created(self, tmp_path: Path) -> None:
        """Test that missing state directory is created."""
        nonexistent_dir = tmp_path / "does_not_exist"
        assert not nonexistent_dir.exists()

        _tracker = PositionTracker(state_dir=str(nonexistent_dir))
        assert nonexistent_dir.exists()
        assert nonexistent_dir.is_dir()

    def test_empty_state_file(self, temp_state_dir: Path) -> None:
        """Test handling of empty state file."""
        state_file = temp_state_dir / "monitor_positions.json"
        state_file.write_text("{}")

        tracker = PositionTracker(state_dir=str(temp_state_dir))
        assert len(tracker.get_all_positions()) == 0


class TestPositionTrackerConcurrency:
    """Tests for concurrent access safety."""

    def test_concurrent_updates(self, temp_state_dir: Path) -> None:
        """Test concurrent updates from multiple threads."""
        tracker = PositionTracker(state_dir=str(temp_state_dir))
        num_threads = 5
        updates_per_thread = 10

        def update_positions(thread_id: int) -> None:
            for i in range(updates_per_thread):
                pos = LogPosition(
                    instance_id=f"instance-{thread_id}",
                    log_type="tmux_output",
                    file_path=f"/tmp/test{thread_id}.log",
                    last_byte_offset=i * 100,
                    last_line_number=i * 10,
                    last_read_timestamp="2025-01-15T10:00:00",
                    checksum=f"checksum{i}",
                )
                tracker.update_position(pos)
                time.sleep(0.001)  # Small delay to increase contention

        threads = [
            threading.Thread(target=update_positions, args=(i,)) for i in range(num_threads)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify all positions were saved
        positions = tracker.get_all_positions()
        assert len(positions) == num_threads

        # Verify each position has the last update
        for i in range(num_threads):
            pos = tracker.get_position(f"instance-{i}", "tmux_output")
            assert pos is not None
            assert pos.last_byte_offset == (updates_per_thread - 1) * 100

    def test_concurrent_reads(self, temp_state_dir: Path) -> None:
        """Test concurrent reads from multiple threads."""
        tracker = PositionTracker(state_dir=str(temp_state_dir))

        # Add initial position
        pos = LogPosition(
            instance_id="test",
            log_type="tmux_output",
            file_path="/tmp/test.log",
            last_byte_offset=1000,
            last_line_number=100,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="checksum",
        )
        tracker.update_position(pos)

        results = []
        lock = threading.Lock()

        def read_position() -> None:
            for _ in range(20):
                result = tracker.get_position("test", "tmux_output")
                with lock:
                    results.append(result)

        threads = [threading.Thread(target=read_position) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All reads should succeed
        assert len(results) == 100
        assert all(r is not None for r in results)
        assert all(r.last_byte_offset == 1000 for r in results)  # type: ignore

    def test_concurrent_mixed_operations(self, temp_state_dir: Path) -> None:
        """Test concurrent mixed read/write operations."""
        tracker = PositionTracker(state_dir=str(temp_state_dir))

        # Initialize some positions
        for i in range(3):
            pos = LogPosition(
                instance_id=f"instance-{i}",
                log_type="tmux_output",
                file_path=f"/tmp/test{i}.log",
                last_byte_offset=0,
                last_line_number=0,
                last_read_timestamp="2025-01-15T10:00:00",
                checksum="initial",
            )
            tracker.update_position(pos)

        def writer_thread(instance_num: int) -> None:
            for i in range(10):
                pos = LogPosition(
                    instance_id=f"instance-{instance_num}",
                    log_type="tmux_output",
                    file_path=f"/tmp/test{instance_num}.log",
                    last_byte_offset=i * 100,
                    last_line_number=i * 10,
                    last_read_timestamp="2025-01-15T10:00:00",
                    checksum=f"checksum{i}",
                )
                tracker.update_position(pos)
                time.sleep(0.001)

        def reader_thread() -> None:
            for _ in range(10):
                _ = tracker.get_all_positions()
                time.sleep(0.001)

        threads = [
            threading.Thread(target=writer_thread, args=(0,)),
            threading.Thread(target=writer_thread, args=(1,)),
            threading.Thread(target=reader_thread),
            threading.Thread(target=reader_thread),
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify final state
        positions = tracker.get_all_positions()
        assert len(positions) == 3


class TestPositionTrackerKeyFormat:
    """Tests for position key formatting."""

    def test_different_instance_same_log_type(
        self, position_tracker: PositionTracker
    ) -> None:
        """Test that different instances with same log type are stored separately."""
        pos1 = LogPosition(
            instance_id="instance-1",
            log_type="tmux_output",
            file_path="/tmp/test1.log",
            last_byte_offset=100,
            last_line_number=10,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="checksum1",
        )
        pos2 = LogPosition(
            instance_id="instance-2",
            log_type="tmux_output",
            file_path="/tmp/test2.log",
            last_byte_offset=200,
            last_line_number=20,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="checksum2",
        )

        position_tracker.update_position(pos1)
        position_tracker.update_position(pos2)

        retrieved1 = position_tracker.get_position("instance-1", "tmux_output")
        retrieved2 = position_tracker.get_position("instance-2", "tmux_output")

        assert retrieved1 is not None
        assert retrieved2 is not None
        assert retrieved1.last_byte_offset == 100
        assert retrieved2.last_byte_offset == 200

    def test_same_instance_different_log_types(
        self, position_tracker: PositionTracker
    ) -> None:
        """Test that same instance with different log types are stored separately."""
        pos1 = LogPosition(
            instance_id="instance-1",
            log_type="tmux_output",
            file_path="/tmp/test1.log",
            last_byte_offset=100,
            last_line_number=10,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="checksum1",
        )
        pos2 = LogPosition(
            instance_id="instance-1",
            log_type="instance",
            file_path="/tmp/test2.log",
            last_byte_offset=200,
            last_line_number=20,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="checksum2",
        )

        position_tracker.update_position(pos1)
        position_tracker.update_position(pos2)

        retrieved1 = position_tracker.get_position("instance-1", "tmux_output")
        retrieved2 = position_tracker.get_position("instance-1", "instance")

        assert retrieved1 is not None
        assert retrieved2 is not None
        assert retrieved1.last_byte_offset == 100
        assert retrieved2.last_byte_offset == 200


class TestPositionTrackerEdgeCases:
    """Tests for edge cases and error handling."""

    def test_position_with_empty_strings(self, position_tracker: PositionTracker) -> None:
        """Test position with empty string values."""
        pos = LogPosition(
            instance_id="",
            log_type="",
            file_path="",
            last_byte_offset=0,
            last_line_number=0,
            last_read_timestamp="",
            checksum="",
        )
        position_tracker.update_position(pos)

        retrieved = position_tracker.get_position("", "")
        assert retrieved is not None
        assert retrieved.instance_id == ""
        assert retrieved.log_type == ""

    def test_position_with_special_characters(
        self, position_tracker: PositionTracker
    ) -> None:
        """Test position with special characters in IDs."""
        pos = LogPosition(
            instance_id="instance:with:colons",
            log_type="type-with-dashes",
            file_path="/tmp/test.log",
            last_byte_offset=100,
            last_line_number=10,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="checksum",
        )
        position_tracker.update_position(pos)

        retrieved = position_tracker.get_position("instance:with:colons", "type-with-dashes")
        assert retrieved is not None
        assert retrieved.instance_id == "instance:with:colons"

    def test_large_offset_values(self, position_tracker: PositionTracker) -> None:
        """Test with very large offset values."""
        pos = LogPosition(
            instance_id="test",
            log_type="tmux_output",
            file_path="/tmp/test.log",
            last_byte_offset=999_999_999_999,
            last_line_number=100_000_000,
            last_read_timestamp="2025-01-15T10:00:00",
            checksum="checksum",
        )
        position_tracker.update_position(pos)

        retrieved = position_tracker.get_position("test", "tmux_output")
        assert retrieved is not None
        assert retrieved.last_byte_offset == 999_999_999_999
        assert retrieved.last_line_number == 100_000_000
