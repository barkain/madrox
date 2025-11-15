"""Comprehensive tests for ProgressTracker."""

import threading
import time
import uuid
from datetime import datetime

import pytest

from src.supervision.events.bus import EventBus
from src.supervision.events.models import Event
from src.supervision.tracking.models import ProgressSnapshot, TaskStatus
from src.supervision.tracking.tracker import ProgressTracker


class TestProgressTrackerBasicCRUD:
    """Tests for basic task CRUD operations."""

    def test_add_task_creates_with_pending_status(self) -> None:
        """Test that add_task creates a task with PENDING status."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("Test task")

        task = tracker.get_task(task_id)
        assert task is not None
        assert task.description == "Test task"
        assert task.status == TaskStatus.PENDING
        assert task.assigned_to is None

    def test_add_task_returns_uuid(self) -> None:
        """Test that add_task returns a valid UUID."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("Test task")

        assert isinstance(task_id, uuid.UUID)

    def test_add_task_with_assignee(self) -> None:
        """Test adding a task with an assignee."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("Test task", assigned_to="dev-123")

        task = tracker.get_task(task_id)
        assert task is not None
        assert task.assigned_to == "dev-123"

    def test_get_task_returns_task(self) -> None:
        """Test retrieving an existing task."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("Test task")

        task = tracker.get_task(task_id)
        assert task is not None
        assert task.id == task_id

    def test_get_task_returns_none_for_invalid_id(self) -> None:
        """Test that get_task returns None for non-existent task."""
        tracker = ProgressTracker()
        task = tracker.get_task(uuid.uuid4())
        assert task is None

    def test_get_all_tasks_returns_all(self) -> None:
        """Test retrieving all tasks."""
        tracker = ProgressTracker()
        task_id_1 = tracker.add_task("Task 1")
        task_id_2 = tracker.add_task("Task 2")
        task_id_3 = tracker.add_task("Task 3")

        tasks = tracker.get_all_tasks()
        assert len(tasks) == 3

        task_ids = {task.id for task in tasks}
        assert task_id_1 in task_ids
        assert task_id_2 in task_ids
        assert task_id_3 in task_ids

    def test_get_all_tasks_returns_empty_list_initially(self) -> None:
        """Test that get_all_tasks returns empty list initially."""
        tracker = ProgressTracker()
        tasks = tracker.get_all_tasks()
        assert tasks == []


class TestProgressTrackerStatusTransitions:
    """Tests for task status transitions."""

    def test_update_status_changes_status(self) -> None:
        """Test that update_status changes the task status."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("Test task")

        tracker.update_status(task_id, TaskStatus.IN_PROGRESS)
        task = tracker.get_task(task_id)
        assert task is not None
        assert task.status == TaskStatus.IN_PROGRESS

    def test_update_status_updates_timestamp(self) -> None:
        """Test that update_status updates the updated_at timestamp."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("Test task")

        task = tracker.get_task(task_id)
        assert task is not None
        original_time = task.updated_at

        # Small delay to ensure timestamp changes
        time.sleep(0.01)

        tracker.update_status(task_id, TaskStatus.IN_PROGRESS)
        task = tracker.get_task(task_id)
        assert task is not None
        assert task.updated_at > original_time

    def test_update_status_raises_on_invalid_id(self) -> None:
        """Test that update_status raises ValueError for invalid task ID."""
        tracker = ProgressTracker()

        with pytest.raises(ValueError, match="Task .* not found"):
            tracker.update_status(uuid.uuid4(), TaskStatus.COMPLETED)

    def test_update_status_sets_blocker_when_blocked(self) -> None:
        """Test that blocker is set when status is BLOCKED."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("Test task")

        tracker.update_status(task_id, TaskStatus.BLOCKED, blocker="Waiting for API")
        task = tracker.get_task(task_id)
        assert task is not None
        assert task.status == TaskStatus.BLOCKED
        assert task.blocker == "Waiting for API"

    def test_update_status_clears_blocker_when_unblocked(self) -> None:
        """Test that blocker can be cleared."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("Test task")

        tracker.update_status(task_id, TaskStatus.BLOCKED, blocker="Blocked")
        tracker.update_status(task_id, TaskStatus.IN_PROGRESS, blocker=None)

        task = tracker.get_task(task_id)
        assert task is not None
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.blocker is None

    def test_status_transition_pending_to_completed(self) -> None:
        """Test transitioning from PENDING to COMPLETED."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("Test task")

        tracker.update_status(task_id, TaskStatus.COMPLETED)
        task = tracker.get_task(task_id)
        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_status_transition_in_progress_to_failed(self) -> None:
        """Test transitioning from IN_PROGRESS to FAILED."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("Test task")

        tracker.update_status(task_id, TaskStatus.IN_PROGRESS)
        tracker.update_status(task_id, TaskStatus.FAILED)

        task = tracker.get_task(task_id)
        assert task is not None
        assert task.status == TaskStatus.FAILED


class TestProgressTrackerSnapshot:
    """Tests for progress snapshot generation."""

    def test_get_snapshot_calculates_correct_counts(self) -> None:
        """Test that snapshot calculates task counts correctly."""
        tracker = ProgressTracker()

        task_1 = tracker.add_task("Task 1")
        task_2 = tracker.add_task("Task 2")
        task_3 = tracker.add_task("Task 3")
        task_4 = tracker.add_task("Task 4")
        _ = tracker.add_task("Task 5")  # PENDING status

        tracker.update_status(task_1, TaskStatus.COMPLETED)
        tracker.update_status(task_2, TaskStatus.COMPLETED)
        tracker.update_status(task_3, TaskStatus.IN_PROGRESS)
        tracker.update_status(task_4, TaskStatus.BLOCKED)

        snapshot = tracker.get_snapshot()
        assert snapshot.total_tasks == 5
        assert snapshot.completed == 2
        assert snapshot.in_progress == 1
        assert snapshot.blocked == 1
        assert snapshot.failed == 0

    def test_get_snapshot_calculates_percentage(self) -> None:
        """Test that snapshot calculates completion percentage correctly."""
        tracker = ProgressTracker()

        task_1 = tracker.add_task("Task 1")
        task_2 = tracker.add_task("Task 2")
        _ = tracker.add_task("Task 3")  # PENDING status
        _ = tracker.add_task("Task 4")  # PENDING status

        tracker.update_status(task_1, TaskStatus.COMPLETED)
        tracker.update_status(task_2, TaskStatus.COMPLETED)

        snapshot = tracker.get_snapshot()
        assert snapshot.completion_percentage == 50.0

    def test_get_snapshot_includes_milestones(self) -> None:
        """Test that snapshot includes recorded milestones."""
        tracker = ProgressTracker()
        tracker.add_milestone("Milestone 1")
        tracker.add_milestone("Milestone 2")

        snapshot = tracker.get_snapshot()
        assert len(snapshot.milestones) == 2
        assert "Milestone 1" in snapshot.milestones
        assert "Milestone 2" in snapshot.milestones

    def test_get_snapshot_with_no_tasks(self) -> None:
        """Test snapshot with zero tasks."""
        tracker = ProgressTracker()
        snapshot = tracker.get_snapshot()

        assert snapshot.total_tasks == 0
        assert snapshot.completed == 0
        assert snapshot.completion_percentage == 0.0

    def test_get_snapshot_100_percent(self) -> None:
        """Test snapshot with all tasks completed."""
        tracker = ProgressTracker()

        task_1 = tracker.add_task("Task 1")
        task_2 = tracker.add_task("Task 2")

        tracker.update_status(task_1, TaskStatus.COMPLETED)
        tracker.update_status(task_2, TaskStatus.COMPLETED)

        snapshot = tracker.get_snapshot()
        assert snapshot.completion_percentage == 100.0

    def test_get_snapshot_is_immutable(self) -> None:
        """Test that snapshot is immutable."""
        tracker = ProgressTracker()
        tracker.add_task("Task 1")

        snapshot = tracker.get_snapshot()

        with pytest.raises(AttributeError):
            snapshot.total_tasks = 10  # type: ignore


class TestProgressTrackerMilestones:
    """Tests for milestone tracking."""

    def test_add_milestone_stores_milestone(self) -> None:
        """Test that add_milestone stores the milestone."""
        tracker = ProgressTracker()
        tracker.add_milestone("Test milestone")

        milestones = tracker.get_milestones()
        assert len(milestones) == 1
        assert "Test milestone" in milestones

    def test_get_milestones_returns_all(self) -> None:
        """Test that get_milestones returns all milestones."""
        tracker = ProgressTracker()
        tracker.add_milestone("Milestone 1")
        tracker.add_milestone("Milestone 2")
        tracker.add_milestone("Milestone 3")

        milestones = tracker.get_milestones()
        assert len(milestones) == 3
        assert "Milestone 1" in milestones
        assert "Milestone 2" in milestones
        assert "Milestone 3" in milestones

    def test_get_milestones_returns_empty_list_initially(self) -> None:
        """Test that get_milestones returns empty list initially."""
        tracker = ProgressTracker()
        milestones = tracker.get_milestones()
        assert milestones == []

    def test_get_milestones_returns_copy(self) -> None:
        """Test that get_milestones returns a copy to prevent external modification."""
        tracker = ProgressTracker()
        tracker.add_milestone("Milestone 1")

        milestones = tracker.get_milestones()
        milestones.append("External milestone")

        # Original should not be modified
        milestones_again = tracker.get_milestones()
        assert len(milestones_again) == 1
        assert "External milestone" not in milestones_again


class TestProgressTrackerEventIntegration:
    """Tests for EventBus integration."""

    def test_add_task_publishes_event_when_bus_provided(self) -> None:
        """Test that add_task publishes task.started event."""
        bus = EventBus()
        tracker = ProgressTracker(event_bus=bus)

        received_events: list[Event] = []

        def handler(event: Event) -> None:
            received_events.append(event)

        bus.subscribe("task.started", handler)

        task_id = tracker.add_task("Test task")

        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == "task.started"
        assert event.source == "progress_tracker"
        assert event.data["task_id"] == str(task_id)
        assert event.data["description"] == "Test task"

    def test_update_status_to_completed_publishes_event(self) -> None:
        """Test that updating status to COMPLETED publishes task.completed event."""
        bus = EventBus()
        tracker = ProgressTracker(event_bus=bus)

        received_events: list[Event] = []

        def handler(event: Event) -> None:
            received_events.append(event)

        bus.subscribe("task.completed", handler)

        task_id = tracker.add_task("Test task")
        tracker.update_status(task_id, TaskStatus.COMPLETED)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == "task.completed"
        assert event.data["task_id"] == str(task_id)

    def test_update_status_to_blocked_publishes_event(self) -> None:
        """Test that updating status to BLOCKED publishes blocker.detected event."""
        bus = EventBus()
        tracker = ProgressTracker(event_bus=bus)

        received_events: list[Event] = []

        def handler(event: Event) -> None:
            received_events.append(event)

        bus.subscribe("blocker.detected", handler)

        task_id = tracker.add_task("Test task")
        tracker.update_status(task_id, TaskStatus.BLOCKED, blocker="Waiting for API")

        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == "blocker.detected"
        assert event.data["task_id"] == str(task_id)
        assert event.data["blocker"] == "Waiting for API"

    def test_update_status_to_failed_publishes_event(self) -> None:
        """Test that updating status to FAILED publishes task.failed event."""
        bus = EventBus()
        tracker = ProgressTracker(event_bus=bus)

        received_events: list[Event] = []

        def handler(event: Event) -> None:
            received_events.append(event)

        bus.subscribe("task.failed", handler)

        task_id = tracker.add_task("Test task")
        tracker.update_status(task_id, TaskStatus.FAILED)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == "task.failed"
        assert event.data["task_id"] == str(task_id)

    def test_add_milestone_publishes_event(self) -> None:
        """Test that add_milestone publishes milestone.reached event."""
        bus = EventBus()
        tracker = ProgressTracker(event_bus=bus)

        received_events: list[Event] = []

        def handler(event: Event) -> None:
            received_events.append(event)

        bus.subscribe("milestone.reached", handler)

        tracker.add_milestone("Test milestone")

        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == "milestone.reached"
        assert event.data["description"] == "Test milestone"

    def test_no_events_when_bus_not_provided(self) -> None:
        """Test that no events are published when EventBus is not provided."""
        tracker = ProgressTracker()  # No event bus

        # Should not raise any errors
        task_id = tracker.add_task("Test task")
        tracker.update_status(task_id, TaskStatus.COMPLETED)
        tracker.add_milestone("Test milestone")

    def test_update_status_to_in_progress_does_not_publish_event(self) -> None:
        """Test that updating to IN_PROGRESS doesn't publish a specific event."""
        bus = EventBus()
        tracker = ProgressTracker(event_bus=bus)

        received_events: list[Event] = []

        def handler(event: Event) -> None:
            received_events.append(event)

        # Subscribe to all relevant event types
        bus.subscribe("task.completed", handler)
        bus.subscribe("blocker.detected", handler)
        bus.subscribe("task.failed", handler)

        task_id = tracker.add_task("Test task")
        tracker.update_status(task_id, TaskStatus.IN_PROGRESS)

        # Only task.started should have been published, not captured by our handler
        assert len(received_events) == 0


class TestProgressTrackerThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_task_additions(self) -> None:
        """Test that concurrent task additions are thread-safe."""
        tracker = ProgressTracker()
        task_ids: list[uuid.UUID] = []
        lock = threading.Lock()

        def add_tasks() -> None:
            for i in range(50):
                task_id = tracker.add_task(f"Task {i}")
                with lock:
                    task_ids.append(task_id)

        threads = [threading.Thread(target=add_tasks) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have 200 tasks (4 threads × 50 tasks)
        all_tasks = tracker.get_all_tasks()
        assert len(all_tasks) == 200
        assert len(task_ids) == 200

        # All task IDs should be unique
        assert len(set(task_ids)) == 200

    def test_concurrent_status_updates(self) -> None:
        """Test that concurrent status updates are thread-safe."""
        tracker = ProgressTracker()

        # Create 100 tasks
        task_ids = [tracker.add_task(f"Task {i}") for i in range(100)]

        def update_tasks(ids: list[uuid.UUID]) -> None:
            for task_id in ids:
                tracker.update_status(task_id, TaskStatus.COMPLETED)

        # Split tasks across 4 threads
        chunk_size = 25
        chunks = [task_ids[i : i + chunk_size] for i in range(0, 100, chunk_size)]

        threads = [threading.Thread(target=update_tasks, args=(chunk,)) for chunk in chunks]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All tasks should be completed
        snapshot = tracker.get_snapshot()
        assert snapshot.completed == 100

    def test_concurrent_snapshot_reads(self) -> None:
        """Test that concurrent snapshot reads are thread-safe."""
        tracker = ProgressTracker()

        # Add some tasks
        for i in range(10):
            tracker.add_task(f"Task {i}")

        snapshots: list[ProgressSnapshot] = []
        lock = threading.Lock()

        def read_snapshot() -> None:
            for _ in range(20):
                snapshot = tracker.get_snapshot()
                with lock:
                    snapshots.append(snapshot)

        threads = [threading.Thread(target=read_snapshot) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have 100 snapshots (5 threads × 20 reads)
        assert len(snapshots) == 100

        # All snapshots should show 10 tasks
        for snapshot in snapshots:
            assert snapshot.total_tasks == 10

    def test_concurrent_mixed_operations(self) -> None:
        """Test thread safety with mixed read/write operations."""
        tracker = ProgressTracker()

        def add_and_complete() -> None:
            for i in range(10):
                task_id = tracker.add_task(f"Task {i}")
                tracker.update_status(task_id, TaskStatus.COMPLETED)

        def read_all() -> None:
            for _ in range(10):
                _ = tracker.get_all_tasks()
                _ = tracker.get_snapshot()

        def add_milestones() -> None:
            for i in range(5):
                tracker.add_milestone(f"Milestone {i}")

        threads = [
            threading.Thread(target=add_and_complete),
            threading.Thread(target=add_and_complete),
            threading.Thread(target=read_all),
            threading.Thread(target=add_milestones),
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have 20 tasks (2 threads × 10 tasks)
        snapshot = tracker.get_snapshot()
        assert snapshot.total_tasks == 20
        assert snapshot.completed == 20

        # Should have 5 milestones
        assert len(tracker.get_milestones()) == 5


class TestProgressTrackerEdgeCases:
    """Tests for edge cases and error handling."""

    def test_blocker_with_none_value(self) -> None:
        """Test that blocker can be set to None."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("Test task")

        tracker.update_status(task_id, TaskStatus.BLOCKED, blocker=None)
        task = tracker.get_task(task_id)
        assert task is not None
        assert task.blocker is None

    def test_empty_description(self) -> None:
        """Test adding a task with empty description."""
        tracker = ProgressTracker()
        task_id = tracker.add_task("")

        task = tracker.get_task(task_id)
        assert task is not None
        assert task.description == ""

    def test_get_all_tasks_returns_copy(self) -> None:
        """Test that get_all_tasks returns a copy to prevent external modification."""
        tracker = ProgressTracker()
        _ = tracker.add_task("Test task")

        tasks = tracker.get_all_tasks()
        # Modify the returned list
        tasks.clear()

        # Original should not be affected
        tasks_again = tracker.get_all_tasks()
        assert len(tasks_again) == 1

    def test_task_created_at_and_updated_at_set(self) -> None:
        """Test that created_at and updated_at are properly set."""
        tracker = ProgressTracker()
        before = datetime.now()
        task_id = tracker.add_task("Test task")
        after = datetime.now()

        task = tracker.get_task(task_id)
        assert task is not None
        assert before <= task.created_at <= after
        assert before <= task.updated_at <= after
        assert task.created_at == task.updated_at  # Should be same initially
