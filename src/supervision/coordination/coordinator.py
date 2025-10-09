"""Supervision coordinator for unified transcript analysis and progress tracking."""

import logging
from dataclasses import dataclass
from uuid import UUID

from supervision.analysis.analyzer import TranscriptAnalyzer
from supervision.analysis.models import AnalysisResult, Message
from supervision.events.bus import EventBus
from supervision.events.models import Event
from supervision.tracking.models import ProgressSnapshot, TaskStatus
from supervision.tracking.tracker import ProgressTracker

logger = logging.getLogger(__name__)


@dataclass
class CoordinationResult:
    """
    Result of coordinated analysis and tracking operation.

    Combines analysis insights with task tracking state for
    comprehensive supervision feedback.

    Attributes:
        analysis: Raw analysis results from transcript
        task_ids: UUIDs of tasks created from analysis
        snapshot: Current progress snapshot after task creation
        events_published: Number of events published during coordination
    """

    analysis: AnalysisResult
    task_ids: list[UUID]
    snapshot: ProgressSnapshot
    events_published: int


class SupervisionCoordinator:
    """
    Central coordinator for the supervision system.

    The SupervisionCoordinator integrates transcript analysis, task tracking,
    and event-driven coordination into a unified supervision workflow.

    It orchestrates:
    - End-to-end transcript analysis
    - Automatic task creation from analysis results
    - Progress tracking and milestone recording
    - Event publication for system-wide notifications

    All components are injected via constructor for testability and flexibility.

    Example:
        coordinator = SupervisionCoordinator(
            event_bus=EventBus(),
            analyzer=TranscriptAnalyzer(),
            tracker=ProgressTracker(event_bus)
        )

        result = coordinator.analyze_and_track(messages)
        health = coordinator.get_network_health()
    """

    def __init__(
        self,
        event_bus: EventBus,
        analyzer: TranscriptAnalyzer,
        tracker: ProgressTracker,
    ) -> None:
        """
        Initialize the supervision coordinator.

        Args:
            event_bus: EventBus for pub/sub messaging
            analyzer: TranscriptAnalyzer for pattern extraction
            tracker: ProgressTracker for task and milestone management
        """
        self._event_bus = event_bus
        self._analyzer = analyzer
        self._tracker = tracker
        self._events_published = 0

        # Subscribe to analysis completion events
        self._event_bus.subscribe("analysis.completed", self._on_analysis_completed)

        logger.info(
            "SupervisionCoordinator initialized",
            extra={
                "has_event_bus": True,
                "has_analyzer": True,
                "has_tracker": True,
            },
        )

    def analyze_and_track(self, messages: list[Message]) -> CoordinationResult:
        """
        Analyze transcript and automatically create tasks and milestones.

        This is the primary end-to-end workflow that:
        1. Analyzes the conversation transcript
        2. Creates tasks from extracted action items
        3. Records milestones from achievements
        4. Updates task status based on detected blockers
        5. Publishes coordination events

        Args:
            messages: List of conversation messages to analyze

        Returns:
            CoordinationResult with analysis, created tasks, and current state

        Raises:
            ValueError: If messages list is empty

        Example:
            messages = [
                Message(role="user", content="Build the auth system", ...),
                Message(role="assistant", content="I'll implement JWT auth", ...),
            ]
            result = coordinator.analyze_and_track(messages)
            print(f"Created {len(result.task_ids)} tasks")
        """
        logger.info(
            "Starting coordinated analysis and tracking",
            extra={"message_count": len(messages)},
        )

        # Step 1: Analyze the transcript
        analysis = self._analyzer.analyze(messages)

        logger.info(
            "Analysis completed",
            extra={
                "status": analysis.status.value,
                "tasks": len(analysis.tasks),
                "blockers": len(analysis.blockers),
                "milestones": len(analysis.milestones),
                "confidence": analysis.confidence,
            },
        )

        # Step 2: Create tasks from extracted patterns
        task_ids = []
        for task_description in analysis.tasks:
            task_id = self._tracker.add_task(
                description=task_description,
                assigned_to="supervision_system",
            )
            task_ids.append(task_id)

            logger.debug(
                "Task created from analysis",
                extra={"task_id": str(task_id), "description": task_description},
            )

        # Step 3: Handle blockers by updating task status
        if analysis.blockers:
            logger.warning(
                "Blockers detected in analysis",
                extra={"blocker_count": len(analysis.blockers)},
            )

            # Mark the first task as blocked if tasks exist
            if task_ids:
                first_task_id = task_ids[0]
                blocker_summary = "; ".join(analysis.blockers[:3])  # Summarize first 3
                self._tracker.update_status(
                    first_task_id,
                    TaskStatus.BLOCKED,
                    blocker=blocker_summary,
                )

                logger.info(
                    "Task marked as blocked",
                    extra={
                        "task_id": str(first_task_id),
                        "blocker": blocker_summary,
                    },
                )

        # Step 4: Record milestones
        for milestone in analysis.milestones:
            self._tracker.add_milestone(milestone)
            logger.info("Milestone recorded", extra={"description": milestone})

        # Step 5: Publish analysis.completed event
        self._publish_analysis_event(analysis, task_ids)

        # Step 6: Get current snapshot
        snapshot = self._tracker.get_snapshot()

        result = CoordinationResult(
            analysis=analysis,
            task_ids=task_ids,
            snapshot=snapshot,
            events_published=self._events_published,
        )

        logger.info(
            "Coordination completed",
            extra={
                "tasks_created": len(task_ids),
                "milestones_recorded": len(analysis.milestones),
                "completion_percentage": snapshot.completion_percentage,
            },
        )

        return result

    def get_network_health(self) -> ProgressSnapshot:
        """
        Get current supervision system health and progress.

        Returns:
            Immutable snapshot of current task tracking state

        Example:
            health = coordinator.get_network_health()
            print(f"System health: {health.completion_percentage:.1f}% complete")
            print(f"Active tasks: {health.in_progress}")
            print(f"Blockers: {health.blocked}")
        """
        snapshot = self._tracker.get_snapshot()

        logger.debug(
            "Network health snapshot",
            extra={
                "total_tasks": snapshot.total_tasks,
                "completed": snapshot.completed,
                "in_progress": snapshot.in_progress,
                "blocked": snapshot.blocked,
                "completion_percentage": snapshot.completion_percentage,
            },
        )

        return snapshot

    def _publish_analysis_event(self, analysis: AnalysisResult, task_ids: list[UUID]) -> None:
        """
        Publish analysis.completed event with coordination results.

        Args:
            analysis: Analysis results
            task_ids: IDs of tasks created from analysis
        """
        event = Event(
            event_type="analysis.completed",
            timestamp=analysis.metadata.get("analyzed_at"),
            source="supervision_coordinator",
            data={
                "status": analysis.status.value,
                "task_count": len(task_ids),
                "blocker_count": len(analysis.blockers),
                "milestone_count": len(analysis.milestones),
                "confidence": analysis.confidence,
                "task_ids": [str(tid) for tid in task_ids],
            },
        )

        self._event_bus.publish(event)
        self._events_published += 1

        logger.debug(
            "Analysis event published",
            extra={
                "event_type": "analysis.completed",
                "task_count": len(task_ids),
            },
        )

    def _on_analysis_completed(self, event: Event) -> None:
        """
        Handle analysis.completed events.

        This handler demonstrates event subscription and could be extended
        to trigger additional coordination logic.

        Args:
            event: Analysis completion event
        """
        logger.debug(
            "Analysis completed event received",
            extra={
                "source": event.source,
                "task_count": event.data.get("task_count"),
            },
        )
