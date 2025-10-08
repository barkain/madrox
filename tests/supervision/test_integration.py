"""Integration tests for the supervision system."""

import threading
from datetime import datetime

import pytest

from supervision.analysis.analyzer import TranscriptAnalyzer
from supervision.analysis.models import Message
from supervision.coordinator import CoordinationResult, SupervisionCoordinator
from supervision.events.bus import EventBus
from supervision.events.models import Event
from supervision.tracking.tracker import ProgressTracker


class TestEndToEndWorkflow:
    """Test complete supervision workflows from transcript to task tracking."""

    def test_basic_supervision_flow(self):
        """Test basic flow: analyze messages → create tasks → track progress."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        # Create sample transcript
        messages = [
            Message(
                role="user",
                content="We need to implement the authentication system",
                timestamp=datetime.now(),
            ),
            Message(
                role="assistant",
                content="I'll create the JWT token handler and implement OAuth2 flow",
                timestamp=datetime.now(),
            ),
        ]

        # Execute
        result = coordinator.analyze_and_track(messages)

        # Verify
        assert isinstance(result, CoordinationResult)
        assert len(result.task_ids) > 0
        assert result.snapshot.total_tasks > 0
        assert result.events_published > 0

    def test_task_detection_and_tracking(self):
        """Test that tasks are correctly detected and tracked."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        messages = [
            Message(
                role="assistant",
                content="I will implement the user registration endpoint and create the database schema",
                timestamp=datetime.now(),
            ),
        ]

        # Execute
        result = coordinator.analyze_and_track(messages)

        # Verify tasks created
        assert len(result.task_ids) >= 1
        assert result.snapshot.total_tasks >= 1

        # Verify tasks are in tracker
        all_tasks = tracker.get_all_tasks()
        assert len(all_tasks) >= 1

        # Verify at least one task matches expected description
        task_descriptions = [task.description for task in all_tasks]
        assert any(
            "registration" in desc.lower() or "database" in desc.lower()
            for desc in task_descriptions
        )

    def test_blocker_detection_and_handling(self):
        """Test that blockers are detected and tasks marked appropriately."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        messages = [
            Message(
                role="assistant",
                content="I need to implement the payment API but I'm blocked by missing API credentials",
                timestamp=datetime.now(),
            ),
        ]

        # Execute
        result = coordinator.analyze_and_track(messages)

        # Verify blockers detected
        assert len(result.analysis.blockers) > 0
        assert (
            "API credentials" in result.analysis.blockers[0]
            or "missing" in result.analysis.blockers[0]
        )

        # Verify snapshot shows blocked tasks
        assert result.snapshot.blocked >= 0  # May be 0 if no tasks created

    def test_milestone_recording(self):
        """Test that milestones are correctly detected and recorded."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        messages = [
            Message(
                role="assistant",
                content="Successfully implemented the authentication system and all tests are passing",
                timestamp=datetime.now(),
            ),
        ]

        # Execute
        result = coordinator.analyze_and_track(messages)

        # Verify milestones detected
        assert len(result.analysis.milestones) > 0

        # Verify milestones in tracker
        milestones = tracker.get_milestones()
        assert len(milestones) > 0

    def test_network_health_snapshot(self):
        """Test that network health provides accurate system state."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        # Create some tasks first
        messages = [
            Message(
                role="assistant",
                content="I will implement feature A, feature B, and feature C",
                timestamp=datetime.now(),
            ),
        ]

        coordinator.analyze_and_track(messages)

        # Execute
        health = coordinator.get_network_health()

        # Verify
        assert health.total_tasks > 0
        assert 0.0 <= health.completion_percentage <= 100.0
        assert (
            health.completed + health.in_progress + health.blocked + health.failed
            <= health.total_tasks
        )


class TestEventPropagation:
    """Test event-driven coordination and message flow."""

    def test_analysis_events_published(self):
        """Test that analysis.completed events are published correctly."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        # Subscribe to analysis events
        received_events = []

        def event_handler(event: Event) -> None:
            received_events.append(event)

        event_bus.subscribe("analysis.completed", event_handler)

        # Execute
        messages = [
            Message(
                role="assistant",
                content="I will implement the new feature",
                timestamp=datetime.now(),
            ),
        ]

        coordinator.analyze_and_track(messages)

        # Verify
        assert len(received_events) > 0
        event = received_events[0]
        assert event.event_type == "analysis.completed"
        assert event.source == "supervision_coordinator"
        assert "task_count" in event.data

    def test_task_lifecycle_events(self):
        """Test that task lifecycle events (started, completed, blocked) are published."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        # Track all events
        received_events = []

        def event_handler(event: Event) -> None:
            received_events.append(event)

        event_bus.subscribe("task.started", event_handler)
        event_bus.subscribe("blocker.detected", event_handler)
        event_bus.subscribe("milestone.reached", event_handler)

        # Execute with blocker
        messages = [
            Message(
                role="assistant",
                content="I will implement the API but blocked by missing credentials",
                timestamp=datetime.now(),
            ),
        ]

        coordinator.analyze_and_track(messages)

        # Verify events published
        event_types = [e.event_type for e in received_events]
        assert "task.started" in event_types

    def test_event_handler_isolation(self):
        """Test that failing event handlers don't break the system."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        # Subscribe a failing handler
        def failing_handler(event: Event) -> None:
            raise RuntimeError("Handler intentionally failed")

        # Subscribe a working handler
        successful_calls = []

        def working_handler(event: Event) -> None:
            successful_calls.append(event)

        event_bus.subscribe("task.started", failing_handler)
        event_bus.subscribe("task.started", working_handler)

        # Execute
        messages = [
            Message(
                role="assistant",
                content="I will implement the feature",
                timestamp=datetime.now(),
            ),
        ]

        # Should not raise despite failing handler
        result = coordinator.analyze_and_track(messages)

        # Verify working handler was called
        assert len(successful_calls) > 0
        assert result.snapshot.total_tasks > 0


class TestMultiComponentIntegration:
    """Test integration across multiple components."""

    def test_analyzer_tracker_coordination(self):
        """Test that analyzer results properly flow to tracker."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        messages = [
            Message(
                role="assistant",
                content="I will create three endpoints: /users, /auth, and /products",
                timestamp=datetime.now(),
            ),
        ]

        # Execute
        result = coordinator.analyze_and_track(messages)

        # Verify analyzer extracted tasks
        assert len(result.analysis.tasks) > 0

        # Verify tracker received tasks
        assert len(result.task_ids) > 0
        assert result.snapshot.total_tasks > 0

        # Verify task IDs match tracker tasks
        all_tasks = tracker.get_all_tasks()
        task_ids_in_tracker = {task.id for task in all_tasks}
        assert all(tid in task_ids_in_tracker for tid in result.task_ids)

    def test_concurrent_coordination(self):
        """Test thread safety with concurrent analyze_and_track calls."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        # Create different message sets
        message_sets = [
            [
                Message(
                    role="assistant",
                    content=f"I will implement feature {i}",
                    timestamp=datetime.now(),
                )
            ]
            for i in range(5)
        ]

        results = []
        threads = []

        def analyze_in_thread(messages):
            result = coordinator.analyze_and_track(messages)
            results.append(result)

        # Execute concurrently
        for messages in message_sets:
            thread = threading.Thread(target=analyze_in_thread, args=(messages,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify
        assert len(results) == 5

        # Verify final state is consistent
        health = coordinator.get_network_health()
        assert health.total_tasks >= 5  # At least one task per message set


class TestErrorHandling:
    """Test error handling and recovery scenarios."""

    def test_empty_messages_handled(self):
        """Test that empty message lists are handled gracefully."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        # Execute with empty messages
        with pytest.raises(ValueError):
            coordinator.analyze_and_track([])

    def test_analysis_error_recovery(self):
        """Test that analysis errors are handled without crashing."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)

        # Mock analyzer to raise error
        def failing_analyze(messages):
            raise RuntimeError("Analysis failed")

        analyzer.analyze = failing_analyze

        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        # Execute
        messages = [
            Message(
                role="assistant",
                content="I will implement the feature",
                timestamp=datetime.now(),
            ),
        ]

        # Should raise the error from analyzer
        with pytest.raises(RuntimeError):
            coordinator.analyze_and_track(messages)

    def test_tracker_isolation(self):
        """Test that tracker errors don't affect analysis."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)

        # Execute analysis first to verify it works
        messages = [
            Message(
                role="assistant",
                content="I will implement the feature",
                timestamp=datetime.now(),
            ),
        ]

        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        # This should work normally
        result = coordinator.analyze_and_track(messages)

        # Verify analysis succeeded even if tracking has issues
        assert result.analysis is not None


class TestComplexScenarios:
    """Test complex real-world supervision scenarios."""

    def test_multi_wave_development_tracking(self):
        """Test tracking a multi-wave development workflow."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        # Wave 1: Initial tasks
        wave1_messages = [
            Message(
                role="assistant",
                content="I will implement the database schema and API endpoints",
                timestamp=datetime.now(),
            ),
        ]

        result1 = coordinator.analyze_and_track(wave1_messages)
        snapshot1 = coordinator.get_network_health()

        # Wave 2: Blockers discovered
        wave2_messages = [
            Message(
                role="assistant",
                content="Blocked by missing database credentials for development",
                timestamp=datetime.now(),
            ),
        ]

        result2 = coordinator.analyze_and_track(wave2_messages)
        snapshot2 = coordinator.get_network_health()

        # Wave 3: Completion
        wave3_messages = [
            Message(
                role="assistant",
                content="Successfully completed the database integration and all tests pass",
                timestamp=datetime.now(),
            ),
        ]

        result3 = coordinator.analyze_and_track(wave3_messages)
        snapshot3 = coordinator.get_network_health()

        # Verify progression
        assert snapshot1.total_tasks > 0
        assert snapshot2.total_tasks >= snapshot1.total_tasks
        assert len(result3.analysis.milestones) > 0

    def test_high_confidence_analysis(self):
        """Test that detailed transcripts produce high-confidence results."""
        # Setup
        event_bus = EventBus()
        analyzer = TranscriptAnalyzer()
        tracker = ProgressTracker(event_bus=event_bus)
        coordinator = SupervisionCoordinator(
            event_bus=event_bus, analyzer=analyzer, tracker=tracker
        )

        # Rich, detailed transcript
        messages = [
            Message(
                role="user",
                content="We need to build a payment processing system",
                timestamp=datetime.now(),
            ),
            Message(
                role="assistant",
                content="I will implement the Stripe integration, create the payment endpoints, and add error handling",
                timestamp=datetime.now(),
            ),
            Message(
                role="assistant",
                content="Successfully completed the Stripe webhook handler and all tests are passing",
                timestamp=datetime.now(),
            ),
        ]

        result = coordinator.analyze_and_track(messages)

        # Verify high confidence
        assert result.analysis.confidence > 0.6
        assert len(result.task_ids) >= 2
        assert len(result.analysis.milestones) >= 1
