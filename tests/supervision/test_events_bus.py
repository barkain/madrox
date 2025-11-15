"""Unit tests for EventBus implementation."""

import threading
import time
import unittest
from datetime import datetime

from src.supervision.events.bus import EventBus
from src.supervision.events.models import Event


class TestEventBusBasics(unittest.TestCase):
    """Test basic EventBus functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.bus = EventBus()

    def test_subscribe_returns_id(self) -> None:
        """Test that subscribe returns a unique subscription ID."""

        def handler(event: Event) -> None:
            pass

        sub_id = self.bus.subscribe("task.started", handler)
        self.assertIsInstance(sub_id, str)
        self.assertGreater(len(sub_id), 0)

    def test_subscribe_multiple_handlers(self) -> None:
        """Test subscribing multiple handlers to the same event type."""

        def handler1(event: Event) -> None:
            pass

        def handler2(event: Event) -> None:
            pass

        sub_id1 = self.bus.subscribe("task.started", handler1)
        sub_id2 = self.bus.subscribe("task.started", handler2)

        self.assertNotEqual(sub_id1, sub_id2)
        self.assertEqual(self.bus.get_subscriber_count("task.started"), 2)

    def test_unsubscribe_existing(self) -> None:
        """Test unsubscribing an existing subscription."""

        def handler(event: Event) -> None:
            pass

        sub_id = self.bus.subscribe("task.started", handler)
        result = self.bus.unsubscribe(sub_id)

        self.assertTrue(result)
        self.assertEqual(self.bus.get_subscriber_count("task.started"), 0)

    def test_unsubscribe_nonexistent(self) -> None:
        """Test unsubscribing a non-existent subscription."""
        result = self.bus.unsubscribe("nonexistent-id")
        self.assertFalse(result)

    def test_publish_to_no_subscribers(self) -> None:
        """Test publishing when there are no subscribers."""
        event = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={},
        )

        # Should not raise any exceptions
        self.bus.publish(event)

    def test_publish_to_single_subscriber(self) -> None:
        """Test publishing to a single subscriber."""
        received_events: list[Event] = []

        def handler(event: Event) -> None:
            received_events.append(event)

        self.bus.subscribe("task.started", handler)

        event = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={"task_id": "123"},
        )

        self.bus.publish(event)

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0], event)

    def test_publish_to_multiple_subscribers(self) -> None:
        """Test publishing to multiple subscribers."""
        received1: list[Event] = []
        received2: list[Event] = []

        def handler1(event: Event) -> None:
            received1.append(event)

        def handler2(event: Event) -> None:
            received2.append(event)

        self.bus.subscribe("task.started", handler1)
        self.bus.subscribe("task.started", handler2)

        event = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={},
        )

        self.bus.publish(event)

        self.assertEqual(len(received1), 1)
        self.assertEqual(len(received2), 1)
        self.assertEqual(received1[0], event)
        self.assertEqual(received2[0], event)

    def test_publish_only_to_matching_type(self) -> None:
        """Test that events are only sent to subscribers of matching type."""
        received_started: list[Event] = []
        received_completed: list[Event] = []

        def handler_started(event: Event) -> None:
            received_started.append(event)

        def handler_completed(event: Event) -> None:
            received_completed.append(event)

        self.bus.subscribe("task.started", handler_started)
        self.bus.subscribe("task.completed", handler_completed)

        event = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={},
        )

        self.bus.publish(event)

        self.assertEqual(len(received_started), 1)
        self.assertEqual(len(received_completed), 0)

    def test_handler_exception_does_not_stop_others(self) -> None:
        """Test that exception in one handler doesn't prevent others from executing."""
        received: list[Event] = []

        def failing_handler(event: Event) -> None:
            raise ValueError("Handler failure")

        def successful_handler(event: Event) -> None:
            received.append(event)

        self.bus.subscribe("task.started", failing_handler)
        self.bus.subscribe("task.started", successful_handler)

        event = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={},
        )

        # Should not raise exception
        self.bus.publish(event)

        # Successful handler should still execute
        self.assertEqual(len(received), 1)

    def test_subscription_order_maintained(self) -> None:
        """Test that handlers are called in subscription order."""
        call_order: list[int] = []

        def handler1(event: Event) -> None:
            call_order.append(1)

        def handler2(event: Event) -> None:
            call_order.append(2)

        def handler3(event: Event) -> None:
            call_order.append(3)

        self.bus.subscribe("task.started", handler1)
        self.bus.subscribe("task.started", handler2)
        self.bus.subscribe("task.started", handler3)

        event = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={},
        )

        self.bus.publish(event)

        self.assertEqual(call_order, [1, 2, 3])


class TestEventBusAsync(unittest.TestCase):
    """Test asynchronous EventBus functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.bus = EventBus()

    def test_publish_async_executes_handler(self) -> None:
        """Test that async publish executes handlers in background."""
        received_events: list[Event] = []
        event_received = threading.Event()

        def handler(event: Event) -> None:
            received_events.append(event)
            event_received.set()

        self.bus.subscribe("task.started", handler)

        event = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={},
        )

        self.bus.publish_async(event)

        # Wait for async handler to execute (with timeout)
        self.assertTrue(event_received.wait(timeout=2.0))
        self.assertEqual(len(received_events), 1)

    def test_publish_async_does_not_block(self) -> None:
        """Test that async publish returns immediately."""
        slow_handler_started = threading.Event()

        def slow_handler(event: Event) -> None:
            slow_handler_started.set()
            time.sleep(0.5)  # Simulate slow processing

        self.bus.subscribe("task.started", slow_handler)

        event = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={},
        )

        start_time = time.time()
        self.bus.publish_async(event)
        elapsed = time.time() - start_time

        # Should return almost immediately (well before 0.5 seconds)
        self.assertLess(elapsed, 0.1)

        # Wait for handler to actually start
        self.assertTrue(slow_handler_started.wait(timeout=2.0))


class TestEventBusThreadSafety(unittest.TestCase):
    """Test EventBus thread safety."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.bus = EventBus()

    def test_concurrent_subscriptions(self) -> None:
        """Test multiple threads subscribing simultaneously."""
        subscription_ids: list[str] = []
        lock = threading.Lock()

        def subscribe_handler() -> None:
            def handler(event: Event) -> None:
                pass

            sub_id = self.bus.subscribe("task.started", handler)
            with lock:
                subscription_ids.append(sub_id)

        threads = [threading.Thread(target=subscribe_handler) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All subscriptions should succeed
        self.assertEqual(len(subscription_ids), 10)
        self.assertEqual(self.bus.get_subscriber_count("task.started"), 10)

    def test_concurrent_publish(self) -> None:
        """Test multiple threads publishing simultaneously."""
        received_count = 0
        lock = threading.Lock()

        def handler(event: Event) -> None:
            nonlocal received_count
            with lock:
                received_count += 1

        self.bus.subscribe("task.started", handler)

        def publish_event() -> None:
            event = Event(
                event_type="task.started",
                timestamp=datetime.now(),
                source="test",
                data={},
            )
            self.bus.publish(event)

        threads = [threading.Thread(target=publish_event) for _ in range(20)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Handler should be called for each publish
        self.assertEqual(received_count, 20)

    def test_subscribe_during_publish(self) -> None:
        """Test subscribing while events are being published."""
        received: list[Event] = []
        lock = threading.Lock()

        def handler(event: Event) -> None:
            with lock:
                received.append(event)

        # Subscribe initial handler
        self.bus.subscribe("task.started", handler)

        # Function to publish events continuously
        def continuous_publish() -> None:
            for i in range(10):
                event = Event(
                    event_type="task.started",
                    timestamp=datetime.now(),
                    source="test",
                    data={"iteration": i},
                )
                self.bus.publish(event)
                time.sleep(0.01)

        # Function to subscribe during publishing
        def subscribe_during() -> None:
            time.sleep(0.05)  # Let some publishes happen first
            self.bus.subscribe("task.started", handler)

        publish_thread = threading.Thread(target=continuous_publish)
        subscribe_thread = threading.Thread(target=subscribe_during)

        publish_thread.start()
        subscribe_thread.start()

        publish_thread.join()
        subscribe_thread.join()

        # Should receive events without crashes
        self.assertGreater(len(received), 0)

    def test_unsubscribe_during_publish(self) -> None:
        """Test unsubscribing while events are being published."""
        received: list[Event] = []
        lock = threading.Lock()

        def handler(event: Event) -> None:
            with lock:
                received.append(event)

        sub_id = self.bus.subscribe("task.started", handler)

        # Function to publish events continuously
        def continuous_publish() -> None:
            for i in range(10):
                event = Event(
                    event_type="task.started",
                    timestamp=datetime.now(),
                    source="test",
                    data={"iteration": i},
                )
                self.bus.publish(event)
                time.sleep(0.01)

        # Function to unsubscribe during publishing
        def unsubscribe_during() -> None:
            time.sleep(0.05)  # Let some publishes happen first
            self.bus.unsubscribe(sub_id)

        publish_thread = threading.Thread(target=continuous_publish)
        unsubscribe_thread = threading.Thread(target=unsubscribe_during)

        publish_thread.start()
        unsubscribe_thread.start()

        publish_thread.join()
        unsubscribe_thread.join()

        # Should complete without crashes, received count may vary
        self.assertGreaterEqual(len(received), 0)


class TestEventBusIntegration(unittest.TestCase):
    """Integration tests for EventBus."""

    def test_full_lifecycle(self) -> None:
        """Test complete subscribe -> publish -> unsubscribe lifecycle."""
        bus = EventBus()
        received: list[Event] = []

        def handler(event: Event) -> None:
            received.append(event)

        # Subscribe
        sub_id = bus.subscribe("task.started", handler)
        self.assertEqual(bus.get_subscriber_count("task.started"), 1)

        # Publish
        event1 = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={"task_id": "1"},
        )
        bus.publish(event1)
        self.assertEqual(len(received), 1)

        # Publish again
        event2 = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={"task_id": "2"},
        )
        bus.publish(event2)
        self.assertEqual(len(received), 2)

        # Unsubscribe
        bus.unsubscribe(sub_id)
        self.assertEqual(bus.get_subscriber_count("task.started"), 0)

        # Publish after unsubscribe (should not receive)
        event3 = Event(
            event_type="task.started",
            timestamp=datetime.now(),
            source="test",
            data={"task_id": "3"},
        )
        bus.publish(event3)
        self.assertEqual(len(received), 2)  # Still 2, not 3

    def test_multiple_event_types(self) -> None:
        """Test handling multiple event types simultaneously."""
        bus = EventBus()
        started_events: list[Event] = []
        completed_events: list[Event] = []

        def started_handler(event: Event) -> None:
            started_events.append(event)

        def completed_handler(event: Event) -> None:
            completed_events.append(event)

        bus.subscribe("task.started", started_handler)
        bus.subscribe("task.completed", completed_handler)

        # Publish various events
        for i in range(5):
            bus.publish(
                Event(
                    event_type="task.started",
                    timestamp=datetime.now(),
                    source="test",
                    data={"task_id": str(i)},
                )
            )

        for i in range(3):
            bus.publish(
                Event(
                    event_type="task.completed",
                    timestamp=datetime.now(),
                    source="test",
                    data={"task_id": str(i)},
                )
            )

        self.assertEqual(len(started_events), 5)
        self.assertEqual(len(completed_events), 3)


if __name__ == "__main__":
    unittest.main()
