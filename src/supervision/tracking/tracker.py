"""Progress tracking implementation for task and milestone management."""

import logging
import threading
import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from supervision.events.bus import EventBus
from supervision.events.models import Event
from supervision.tracking.models import ProgressSnapshot, Task, TaskStatus

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Thread-safe tracker for task progress and system state.

    The ProgressTracker maintains the current state of all tasks,
    milestones, and provides metrics through immutable snapshots.
    Optionally integrates with EventBus to publish task lifecycle events.

    Thread Safety:
        - All public methods are thread-safe
        - Uses RLock to support reentrant operations
        - Snapshots are immutable for safe sharing

    Example:
        tracker = ProgressTracker()
        task_id = tracker.add_task("Implement feature X")
        tracker.update_status(task_id, TaskStatus.IN_PROGRESS)
        snapshot = tracker.get_snapshot()
        print(f"Progress: {snapshot.completion_percentage}%")
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """
        Initialize progress tracker.

        Args:
            event_bus: Optional event bus for publishing task lifecycle events.
                      If provided, tracker will publish events for task state
                      changes and milestone achievements.
        """
        self._tasks: dict[UUID, Task] = {}
        self._milestones: list[str] = []
        self._lock = threading.RLock()
        self._event_bus = event_bus
        logger.debug(
            "ProgressTracker initialized",
            extra={"has_event_bus": event_bus is not None},
        )

    def add_task(self, description: str, assigned_to: str | None = None) -> UUID:
        """
        Add a new task with PENDING status.

        Args:
            description: Human-readable task description
            assigned_to: Optional assignee identifier

        Returns:
            UUID of the created task

        Example:
            task_id = tracker.add_task("Write unit tests", assigned_to="dev-123")
        """
        task_id = uuid.uuid4()
        now = datetime.now()

        task = Task(
            id=task_id,
            description=description,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            assigned_to=assigned_to,
        )

        with self._lock:
            self._tasks[task_id] = task

        logger.info(
            "Task added",
            extra={
                "task_id": str(task_id),
                "description": description,
                "assigned_to": assigned_to,
            },
        )

        # Publish task.started event
        self._publish_event(
            event_type="task.started",
            data={"task_id": str(task_id), "description": description},
        )

        return task_id

    def update_status(self, task_id: UUID, status: TaskStatus, blocker: str | None = None) -> None:
        """
        Update task status and optional blocker information.

        Args:
            task_id: UUID of the task to update
            status: New status to set
            blocker: Optional blocker description (recommended when status is BLOCKED)

        Raises:
            ValueError: If task_id is not found

        Example:
            tracker.update_status(
                task_id,
                TaskStatus.BLOCKED,
                blocker="Waiting for API credentials"
            )
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise ValueError(f"Task {task_id} not found")

            old_status = task.status
            task.status = status
            task.updated_at = datetime.now()
            task.blocker = blocker

        logger.info(
            "Task status updated",
            extra={
                "task_id": str(task_id),
                "old_status": old_status.value,
                "new_status": status.value,
                "blocker": blocker,
            },
        )

        # Publish appropriate event based on new status
        if status == TaskStatus.COMPLETED:
            self._publish_event(
                event_type="task.completed",
                data={"task_id": str(task_id)},
            )
        elif status == TaskStatus.BLOCKED:
            self._publish_event(
                event_type="blocker.detected",
                data={"task_id": str(task_id), "blocker": blocker or "Unknown blocker"},
            )
        elif status == TaskStatus.FAILED:
            self._publish_event(
                event_type="task.failed",
                data={"task_id": str(task_id)},
            )

    def get_task(self, task_id: UUID) -> Task | None:
        """
        Retrieve task by ID.

        Args:
            task_id: UUID of the task to retrieve

        Returns:
            Task if found, None otherwise

        Example:
            task = tracker.get_task(task_id)
            if task:
                print(f"Task status: {task.status}")
        """
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[Task]:
        """
        Get all tasks.

        Returns:
            List of all tasks (copy to prevent external modification)

        Example:
            for task in tracker.get_all_tasks():
                print(f"{task.description}: {task.status.value}")
        """
        with self._lock:
            return list(self._tasks.values())

    def get_snapshot(self) -> ProgressSnapshot:
        """
        Get current progress snapshot with metrics.

        Calculates real-time metrics including task counts by status,
        completion percentage, and current milestones.

        Returns:
            Immutable ProgressSnapshot with current state

        Example:
            snapshot = tracker.get_snapshot()
            print(f"Completed: {snapshot.completed}/{snapshot.total_tasks}")
            print(f"Progress: {snapshot.completion_percentage:.1f}%")
        """
        with self._lock:
            tasks = list(self._tasks.values())
            milestones = self._milestones.copy()

        # Count tasks by status
        total_tasks = len(tasks)
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        in_progress = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
        blocked = sum(1 for t in tasks if t.status == TaskStatus.BLOCKED)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)

        # Calculate completion percentage
        completion_percentage = (completed / total_tasks * 100.0) if total_tasks > 0 else 0.0

        snapshot = ProgressSnapshot(
            timestamp=datetime.now(),
            total_tasks=total_tasks,
            completed=completed,
            in_progress=in_progress,
            blocked=blocked,
            failed=failed,
            completion_percentage=completion_percentage,
            milestones=milestones,
        )

        logger.debug(
            "Snapshot generated",
            extra={
                "total_tasks": total_tasks,
                "completed": completed,
                "completion_percentage": f"{completion_percentage:.1f}%",
            },
        )

        return snapshot

    def add_milestone(self, description: str) -> None:
        """
        Record a milestone achievement.

        Args:
            description: Milestone description

        Example:
            tracker.add_milestone("Phase 1 implementation complete")
        """
        with self._lock:
            self._milestones.append(description)

        logger.info("Milestone added", extra={"description": description})

        # Publish milestone.reached event
        self._publish_event(
            event_type="milestone.reached",
            data={"description": description},
        )

    def get_milestones(self) -> list[str]:
        """
        Get all recorded milestones.

        Returns:
            List of milestone descriptions in chronological order

        Example:
            for milestone in tracker.get_milestones():
                print(f"✓ {milestone}")
        """
        with self._lock:
            return self._milestones.copy()

    def _publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Internal helper to publish events if EventBus is configured.

        Args:
            event_type: Type of event to publish
            data: Event-specific data payload
        """
        if self._event_bus is None:
            return

        event = Event(
            event_type=event_type,
            timestamp=datetime.now(),
            source="progress_tracker",
            data=data,
        )

        try:
            self._event_bus.publish(event)
            logger.debug(
                "Event published",
                extra={"event_type": event_type, "data": data},
            )
        except Exception as e:
            logger.error(
                "Failed to publish event",
                extra={
                    "event_type": event_type,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
