"""Event data models and types for the supervision system."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class Event:
    """
    Immutable event class for the supervision system.

    All events in the system are immutable to ensure thread safety
    and prevent accidental modification during event processing.

    Attributes:
        event_type: Type of the event (e.g., "task.started", "task.completed")
        timestamp: When the event occurred
        source: Origin of the event (e.g., "supervision_system", "progress_tracker")
        data: Event-specific data payload
        correlation_id: Optional ID for correlating related events
    """

    event_type: str
    timestamp: datetime
    source: str
    data: dict[str, Any]
    correlation_id: str | None = None


class EventHandler(Protocol):
    """
    Protocol defining the interface for event handlers.

    Event handlers must be callable objects that accept an Event
    and return None. This protocol ensures type safety when
    subscribing handlers to the event bus.

    Example:
        def my_handler(event: Event) -> None:
            print(f"Received event: {event.event_type}")

        bus.subscribe("task.started", my_handler)
    """

    def __call__(self, event: Event) -> None:
        """
        Process an event.

        Args:
            event: The event to process
        """
        ...


# Event type constants for supervision system
SUPERVISION_EVENT_TYPES: dict[str, str] = {
    "task.started": "Task execution began",
    "task.completed": "Task execution finished",
    "task.failed": "Task execution failed",
    "milestone.reached": "Milestone achieved",
    "blocker.detected": "Progress blocked",
    "tool.executed": "Tool call completed",
    "analysis.completed": "Transcript analysis done",
}
