"""Tests for tracking data models."""

import uuid
from datetime import datetime

import pytest

from supervision.tracking.models import ProgressSnapshot, Task, TaskStatus


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_task_status_values(self) -> None:
        """Test that TaskStatus has all required values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.BLOCKED.value == "blocked"

    def test_task_status_count(self) -> None:
        """Test that TaskStatus has exactly 5 states."""
        assert len(TaskStatus) == 5


class TestTask:
    """Tests for Task dataclass."""

    def test_task_creation_with_required_fields(self) -> None:
        """Test creating a task with only required fields."""
        task_id = uuid.uuid4()
        now = datetime.now()

        task = Task(
            id=task_id,
            description="Test task",
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        assert task.id == task_id
        assert task.description == "Test task"
        assert task.status == TaskStatus.PENDING
        assert task.created_at == now
        assert task.updated_at == now
        assert task.assigned_to is None
        assert task.blocker is None
        assert task.metadata is None

    def test_task_creation_with_all_fields(self) -> None:
        """Test creating a task with all optional fields."""
        task_id = uuid.uuid4()
        now = datetime.now()
        metadata = {"priority": "high", "tags": ["backend"]}

        task = Task(
            id=task_id,
            description="Complex task",
            status=TaskStatus.IN_PROGRESS,
            created_at=now,
            updated_at=now,
            assigned_to="dev-123",
            blocker="Waiting for API access",
            metadata=metadata,
        )

        assert task.id == task_id
        assert task.description == "Complex task"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.assigned_to == "dev-123"
        assert task.blocker == "Waiting for API access"
        assert task.metadata == metadata

    def test_task_is_mutable(self) -> None:
        """Test that Task instances can be modified."""
        task_id = uuid.uuid4()
        now = datetime.now()

        task = Task(
            id=task_id,
            description="Test task",
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        # Modify status
        task.status = TaskStatus.IN_PROGRESS
        assert task.status == TaskStatus.IN_PROGRESS

        # Modify updated_at
        new_time = datetime.now()
        task.updated_at = new_time
        assert task.updated_at == new_time

        # Add blocker
        task.blocker = "Blocked by dependency"
        assert task.blocker == "Blocked by dependency"

    def test_task_status_transitions(self) -> None:
        """Test various task status transitions."""
        task_id = uuid.uuid4()
        now = datetime.now()

        task = Task(
            id=task_id,
            description="Test task",
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        # PENDING -> IN_PROGRESS
        task.status = TaskStatus.IN_PROGRESS
        assert task.status == TaskStatus.IN_PROGRESS

        # IN_PROGRESS -> COMPLETED
        task.status = TaskStatus.COMPLETED
        assert task.status == TaskStatus.COMPLETED

        # Can also fail
        task.status = TaskStatus.FAILED
        assert task.status == TaskStatus.FAILED


class TestProgressSnapshot:
    """Tests for ProgressSnapshot dataclass."""

    def test_progress_snapshot_creation(self) -> None:
        """Test creating a progress snapshot."""
        now = datetime.now()
        milestones = ["Milestone 1", "Milestone 2"]

        snapshot = ProgressSnapshot(
            timestamp=now,
            total_tasks=10,
            completed=5,
            in_progress=3,
            blocked=1,
            failed=1,
            completion_percentage=50.0,
            milestones=milestones,
        )

        assert snapshot.timestamp == now
        assert snapshot.total_tasks == 10
        assert snapshot.completed == 5
        assert snapshot.in_progress == 3
        assert snapshot.blocked == 1
        assert snapshot.failed == 1
        assert snapshot.completion_percentage == 50.0
        assert snapshot.milestones == milestones

    def test_progress_snapshot_is_immutable(self) -> None:
        """Test that ProgressSnapshot instances are immutable."""
        now = datetime.now()

        snapshot = ProgressSnapshot(
            timestamp=now,
            total_tasks=10,
            completed=5,
            in_progress=3,
            blocked=1,
            failed=1,
            completion_percentage=50.0,
            milestones=["Milestone 1"],
        )

        # Attempting to modify should raise AttributeError
        with pytest.raises(AttributeError):
            snapshot.completed = 6  # type: ignore

        with pytest.raises(AttributeError):
            snapshot.completion_percentage = 60.0  # type: ignore

    def test_progress_snapshot_zero_tasks(self) -> None:
        """Test snapshot with no tasks."""
        now = datetime.now()

        snapshot = ProgressSnapshot(
            timestamp=now,
            total_tasks=0,
            completed=0,
            in_progress=0,
            blocked=0,
            failed=0,
            completion_percentage=0.0,
            milestones=[],
        )

        assert snapshot.total_tasks == 0
        assert snapshot.completion_percentage == 0.0
        assert snapshot.milestones == []

    def test_progress_snapshot_100_percent(self) -> None:
        """Test snapshot with all tasks completed."""
        now = datetime.now()

        snapshot = ProgressSnapshot(
            timestamp=now,
            total_tasks=20,
            completed=20,
            in_progress=0,
            blocked=0,
            failed=0,
            completion_percentage=100.0,
            milestones=["All tasks complete"],
        )

        assert snapshot.total_tasks == 20
        assert snapshot.completed == 20
        assert snapshot.completion_percentage == 100.0

    def test_progress_snapshot_partial_completion(self) -> None:
        """Test snapshot with partial task completion."""
        now = datetime.now()

        snapshot = ProgressSnapshot(
            timestamp=now,
            total_tasks=100,
            completed=73,
            in_progress=15,
            blocked=8,
            failed=4,
            completion_percentage=73.0,
            milestones=["Phase 1 complete", "Phase 2 in progress"],
        )

        # Verify counts add up
        assert snapshot.completed + snapshot.in_progress + snapshot.blocked + snapshot.failed == 100
        assert snapshot.completion_percentage == 73.0
