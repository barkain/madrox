"""Unit tests for event models."""

import unittest
from datetime import datetime

from supervision.events.models import SUPERVISION_EVENT_TYPES, Event, EventHandler


class TestEvent(unittest.TestCase):
    """Test cases for the Event dataclass."""

    def test_event_creation(self) -> None:
        """Test creating a basic event."""
        timestamp = datetime.now()
        event = Event(
            event_type="task.started",
            timestamp=timestamp,
            source="test_source",
            data={"task_id": "123"},
        )

        self.assertEqual(event.event_type, "task.started")
        self.assertEqual(event.timestamp, timestamp)
        self.assertEqual(event.source, "test_source")
        self.assertEqual(event.data, {"task_id": "123"})
        self.assertIsNone(event.correlation_id)

    def test_event_with_correlation_id(self) -> None:
        """Test creating an event with correlation ID."""
        event = Event(
            event_type="task.completed",
            timestamp=datetime.now(),
            source="test_source",
            data={},
            correlation_id="correlation-123",
        )

        self.assertEqual(event.correlation_id, "correlation-123")

    def test_event_immutability(self) -> None:
        """Test that events are immutable (frozen dataclass)."""
        event = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={},
        )

        with self.assertRaises((AttributeError, TypeError)):  # Frozen dataclass raises AttributeError
            event.event_type = "task.completed"  # type: ignore

    def test_event_with_complex_data(self) -> None:
        """Test event with complex nested data."""
        event = Event(
            event_type="analysis.completed",
            timestamp=datetime.now(),
            source="analyzer",
            data={
                "tasks": ["task1", "task2"],
                "metrics": {"count": 5, "duration": 123.45},
                "nested": {"key": "value"},
            },
        )

        self.assertEqual(len(event.data["tasks"]), 2)
        self.assertEqual(event.data["metrics"]["count"], 5)
        self.assertEqual(event.data["nested"]["key"], "value")

    def test_event_equality(self) -> None:
        """Test event equality comparison."""
        timestamp = datetime(2025, 10, 7, 10, 0, 0)
        data = {"task_id": "123"}

        event1 = Event(
            event_type="task.started",
            timestamp=timestamp,
            source="test",
            data=data,
        )

        event2 = Event(
            event_type="task.started",
            timestamp=timestamp,
            source="test",
            data=data,
        )

        # Note: Due to dict mutability, events are equal if all fields match
        self.assertEqual(event1, event2)


class TestEventHandler(unittest.TestCase):
    """Test cases for the EventHandler protocol."""

    def test_handler_protocol_with_function(self) -> None:
        """Test that a function matches the EventHandler protocol."""

        def my_handler(event: Event) -> None:
            pass

        # Type check: this should not raise any issues
        handler: EventHandler = my_handler
        self.assertTrue(callable(handler))

    def test_handler_protocol_with_callable_class(self) -> None:
        """Test that a callable class matches the EventHandler protocol."""

        class MyHandler:
            def __call__(self, event: Event) -> None:
                pass

        handler_instance = MyHandler()
        handler: EventHandler = handler_instance
        self.assertTrue(callable(handler))


class TestSupervisionEventTypes(unittest.TestCase):
    """Test cases for supervision event type constants."""

    def test_event_types_defined(self) -> None:
        """Test that all expected event types are defined."""
        expected_types = {
            "task.started",
            "task.completed",
            "task.failed",
            "milestone.reached",
            "blocker.detected",
            "tool.executed",
            "analysis.completed",
        }

        self.assertEqual(set(SUPERVISION_EVENT_TYPES.keys()), expected_types)

    def test_event_type_descriptions(self) -> None:
        """Test that all event types have descriptions."""
        for event_type, description in SUPERVISION_EVENT_TYPES.items():
            self.assertIsInstance(event_type, str)
            self.assertIsInstance(description, str)
            self.assertGreater(len(description), 0)

    def test_specific_event_type_descriptions(self) -> None:
        """Test specific event type descriptions match specification."""
        self.assertEqual(SUPERVISION_EVENT_TYPES["task.started"], "Task execution began")
        self.assertEqual(SUPERVISION_EVENT_TYPES["task.completed"], "Task execution finished")
        self.assertEqual(SUPERVISION_EVENT_TYPES["milestone.reached"], "Milestone achieved")


if __name__ == "__main__":
    unittest.main()
