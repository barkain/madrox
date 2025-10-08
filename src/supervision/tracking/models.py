"""Task tracking data models for the supervision system."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class TaskStatus(Enum):
    """
    Task execution status.

    Attributes:
        PENDING: Task has been created but not started
        IN_PROGRESS: Task is currently being executed
        COMPLETED: Task has been successfully completed
        FAILED: Task execution failed
        BLOCKED: Task is blocked and cannot proceed
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """
    Mutable task representation for tracking work items.

    Tasks can be updated throughout their lifecycle as status changes,
    blockers are identified, or other metadata is modified.

    Attributes:
        id: Unique task identifier
        description: Human-readable task description
        status: Current execution status
        created_at: Timestamp when task was created
        updated_at: Timestamp of last status change
        assigned_to: Optional assignee identifier
        blocker: Optional description of what's blocking the task
        metadata: Optional additional task-specific data
    """

    id: UUID
    description: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    assigned_to: str | None = None
    blocker: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProgressSnapshot:
    """
    Immutable snapshot of current progress state.

    Provides a point-in-time view of task tracking metrics
    that can be safely shared across threads or stored for
    historical analysis.

    Attributes:
        timestamp: When this snapshot was taken
        total_tasks: Total number of tasks
        completed: Number of completed tasks
        in_progress: Number of tasks currently in progress
        blocked: Number of blocked tasks
        failed: Number of failed tasks
        completion_percentage: Percentage of tasks completed (0.0 to 100.0)
        milestones: List of achieved milestones
    """

    timestamp: datetime
    total_tasks: int
    completed: int
    in_progress: int
    blocked: int
    failed: int
    completion_percentage: float
    milestones: list[str]
