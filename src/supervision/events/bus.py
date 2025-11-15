"""Thread-safe event bus implementation for pub/sub messaging."""

import logging
import threading
import uuid

from supervision.events.models import Event, EventHandler

logger = logging.getLogger(__name__)


class EventBus:
    """
    Thread-safe event bus with pub/sub pattern.

    The EventBus allows components to communicate via events without
    tight coupling. Subscribers register interest in specific event
    types and receive notifications when those events are published.

    Thread Safety:
        - All public methods are thread-safe
        - Subscribers can be added/removed during event publishing
        - Events are delivered in subscription order (per type)

    Example:
        bus = EventBus()

        def handler(event: Event) -> None:
            print(f"Received: {event.event_type}")

        sub_id = bus.subscribe("task.started", handler)
        bus.publish(Event(
            event_type="task.started",
            timestamp=datetime.now(UTC),
            source="test",
            data={"task_id": "123"}
        ))
        bus.unsubscribe(sub_id)
    """

    def __init__(self) -> None:
        """Initialize the event bus with empty subscriber registry."""
        # Map of event_type -> list of (subscription_id, handler) tuples
        self._subscribers: dict[str, list[tuple[str, EventHandler]]] = {}
        # Lock for thread-safe access to _subscribers
        self._lock = threading.Lock()
        logger.debug("EventBus initialized")

    def subscribe(self, event_type: str, handler: EventHandler) -> str:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: Type of events to receive (e.g., "task.started")
            handler: Callable that processes events

        Returns:
            Subscription ID for unsubscribing

        Example:
            sub_id = bus.subscribe("task.completed", my_handler)
        """
        subscription_id = str(uuid.uuid4())

        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append((subscription_id, handler))

        logger.debug(
            "Subscribed to event type",
            extra={
                "event_type": event_type,
                "subscription_id": subscription_id,
                "total_subscribers": len(self._subscribers[event_type]),
            },
        )

        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Remove a subscription.

        Args:
            subscription_id: ID returned from subscribe()

        Returns:
            True if unsubscribed, False if ID not found

        Example:
            if bus.unsubscribe(sub_id):
                print("Successfully unsubscribed")
        """
        with self._lock:
            for event_type, subscribers in self._subscribers.items():
                # Find and remove the subscription
                for i, (sub_id, _) in enumerate(subscribers):
                    if sub_id == subscription_id:
                        subscribers.pop(i)
                        logger.debug(
                            "Unsubscribed from event type",
                            extra={
                                "event_type": event_type,
                                "subscription_id": subscription_id,
                            },
                        )
                        return True

        logger.warning(
            "Subscription ID not found",
            extra={"subscription_id": subscription_id},
        )
        return False

    def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers synchronously.

        Handlers are called in subscription order. If a handler raises
        an exception, it is logged but does not prevent other handlers
        from executing.

        Args:
            event: Event to publish

        Example:
            bus.publish(Event(
                event_type="task.started",
                timestamp=datetime.now(UTC),
                source="tracker",
                data={"task_id": "abc-123"}
            ))
        """
        # Get a snapshot of current subscribers for this event type
        with self._lock:
            subscribers = self._subscribers.get(event.event_type, []).copy()

        if not subscribers:
            logger.debug(
                "No subscribers for event type",
                extra={"event_type": event.event_type},
            )
            return

        logger.debug(
            "Publishing event",
            extra={
                "event_type": event.event_type,
                "source": event.source,
                "subscriber_count": len(subscribers),
            },
        )

        # Call handlers synchronously
        for subscription_id, handler in subscribers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "Handler raised exception",
                    extra={
                        "event_type": event.event_type,
                        "subscription_id": subscription_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )

    def publish_async(self, event: Event) -> None:
        """
        Publish event asynchronously without waiting for handlers.

        Handlers execute in a background thread, allowing the caller
        to continue immediately. Useful for fire-and-forget notifications.

        Args:
            event: Event to publish

        Example:
            bus.publish_async(Event(
                event_type="milestone.reached",
                timestamp=datetime.now(UTC),
                source="tracker",
                data={"milestone": "Phase 1 complete"}
            ))
        """
        logger.debug(
            "Publishing event asynchronously",
            extra={
                "event_type": event.event_type,
                "source": event.source,
            },
        )

        # Create and start a background thread to handle the event
        thread = threading.Thread(
            target=self.publish,
            args=(event,),
            daemon=True,
            name=f"EventBus-{event.event_type}",
        )
        thread.start()

    def get_subscriber_count(self, event_type: str | None = None) -> int:
        """
        Get the number of subscribers.

        Args:
            event_type: Optional event type to count. If None, returns
                       total count across all event types.

        Returns:
            Number of subscribers

        Note:
            This method is provided for debugging and monitoring.
            It is not part of the public API specification.
        """
        with self._lock:
            if event_type is not None:
                return len(self._subscribers.get(event_type, []))
            return sum(len(subs) for subs in self._subscribers.values())
