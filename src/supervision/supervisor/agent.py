"""Supervisor Agent - Autonomous network monitor and coordinator.

This module implements the core Supervisor Agent that monitors Madrox networks,
detects issues, makes autonomous decisions, and executes remediation actions.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from orchestrator.compat import UTC
from supervision.analysis.analyzer import TranscriptAnalyzer
from supervision.analysis.models import AnalysisStatus
from supervision.events.bus import EventBus
from supervision.tracking.tracker import ProgressTracker

logger = logging.getLogger(__name__)


class InterventionType(Enum):
    """Types of supervisor interventions."""

    STATUS_CHECK = "status_check"
    PROVIDE_GUIDANCE = "provide_guidance"
    REASSIGN_WORK = "reassign_work"
    SPAWN_HELPER = "spawn_helper"
    BREAK_DEADLOCK = "break_deadlock"
    ESCALATE = "escalate"


class IssueSeverity(Enum):
    """Severity levels for detected issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DetectedIssue:
    """Represents a detected issue in the network."""

    instance_id: str
    issue_type: str
    severity: IssueSeverity
    description: str
    detected_at: datetime
    confidence: float  # 0.0-1.0
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class SupervisionConfig:
    """Configuration for supervisor agent behavior."""

    # Detection thresholds
    stuck_threshold_seconds: int = 300  # 5 minutes
    waiting_threshold_seconds: int = 120  # 2 minutes
    error_loop_threshold: int = 3  # consecutive errors

    # Intervention limits
    max_interventions_per_instance: int = 3
    intervention_cooldown_seconds: int = 60

    # Evaluation cycle
    evaluation_interval_seconds: int = 30

    # Performance targets
    network_efficiency_target: float = 0.70  # 70% productive time

    # Escalation
    escalate_after_failed_interventions: int = 3


@dataclass
class InterventionRecord:
    """Record of a supervisor intervention."""

    intervention_id: str
    intervention_type: InterventionType
    target_instance_id: str
    timestamp: datetime
    reason: str
    action_taken: str
    success: bool | None = None  # None = pending
    details: dict[str, Any] = field(default_factory=dict)


class SupervisorAgent:
    """Autonomous supervisor for Madrox networks.

    The Supervisor Agent continuously monitors network health, detects issues,
    makes autonomous decisions about interventions, and executes remediation
    actions without user intervention.

    Responsibilities:
    - Monitor all instances via event bus and transcript analysis
    - Detect stuck, waiting, idle, and troubled instances
    - Make autonomous intervention decisions
    - Execute remediation actions (messages, spawning, termination)
    - Escalate unresolvable issues to user
    - Maintain network health metrics

    Integration:
    - Uses Phase 1 components: EventBus, TranscriptAnalyzer, ProgressTracker
    - Leverages existing InstanceManager API for actions
    - Operates as special Madrox instance with elevated privileges
    """

    def __init__(
        self,
        instance_manager: Any,  # TmuxInstanceManager
        config: SupervisionConfig | None = None,
    ):
        """Initialize supervisor agent.

        Args:
            instance_manager: Instance manager for network operations
            config: Supervision configuration (uses defaults if None)
        """
        self.manager = instance_manager
        self.config = config or SupervisionConfig()

        # Phase 1 components
        self.event_bus = EventBus()
        self.analyzer = TranscriptAnalyzer()
        self.tracker = ProgressTracker(self.event_bus)

        # Supervision state
        self.running = False
        self.supervision_task: asyncio.Task | None = None
        self.intervention_history: list[InterventionRecord] = []
        self.intervention_counts: dict[str, int] = {}  # instance_id -> count
        self.last_intervention: dict[str, datetime] = {}  # instance_id -> timestamp

        logger.info(
            "Supervisor agent initialized",
            extra={
                "stuck_threshold": self.config.stuck_threshold_seconds,
                "waiting_threshold": self.config.waiting_threshold_seconds,
                "evaluation_interval": self.config.evaluation_interval_seconds,
            },
        )

    async def start(self):
        """Start autonomous supervision loop."""
        if self.running:
            logger.warning("Supervisor already running")
            return

        self.running = True
        self.supervision_task = asyncio.create_task(self._supervision_loop())
        logger.info("Supervisor agent started - autonomous monitoring active")

    async def stop(self):
        """Stop supervision loop."""
        if not self.running:
            return

        self.running = False
        if self.supervision_task:
            self.supervision_task.cancel()
            try:
                await self.supervision_task
            except asyncio.CancelledError:
                pass

        logger.info("Supervisor agent stopped")

    async def _supervision_loop(self):
        """Main supervision loop - evaluates network periodically."""
        logger.info(
            "Supervision loop started", extra={"interval": self.config.evaluation_interval_seconds}
        )

        while self.running:
            try:
                await self._evaluate_network()
                await asyncio.sleep(self.config.evaluation_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in supervision loop", extra={"error": str(e)}, exc_info=True)
                await asyncio.sleep(self.config.evaluation_interval_seconds)

    async def _evaluate_network(self):
        """Evaluate network health and make intervention decisions."""
        # Get all active instances
        instances = await self._get_active_instances()

        logger.debug("Evaluating network health", extra={"instance_count": len(instances)})

        # Detect issues across all instances
        issues: list[DetectedIssue] = []
        for instance_id in instances:
            instance_issues = await self._detect_instance_issues(instance_id)
            issues.extend(instance_issues)

        if not issues:
            logger.debug("No issues detected - network healthy")
            return

        logger.info(
            "Issues detected in network",
            extra={
                "issue_count": len(issues),
                "affected_instances": len({i.instance_id for i in issues}),
            },
        )

        # Make intervention decisions for each issue
        for issue in issues:
            await self._handle_issue(issue)

    async def _get_active_instances(self) -> list[str]:
        """Get list of active instance IDs from InstanceManager."""
        status = self.manager.get_instance_status()
        instances = status.get("instances", {})

        # Return IDs of instances that are running/busy/idle (not terminated/error)
        active_ids = [
            iid
            for iid, inst in instances.items()
            if inst.get("state") in ["running", "busy", "idle"]
        ]

        return active_ids

    async def _detect_instance_issues(self, instance_id: str) -> list[DetectedIssue]:
        """Detect issues for a specific instance.

        Uses transcript analysis and progress tracking to identify:
        - Stuck instances (busy but no progress)
        - Waiting instances (completed work, awaiting input)
        - Error loops (repeated failures)
        - Degraded performance

        Args:
            instance_id: Instance to analyze

        Returns:
            List of detected issues
        """
        issues: list[DetectedIssue] = []

        # Fetch transcript from tmux pane
        try:
            transcript = await self.manager.get_tmux_pane_content(instance_id, lines=200)
        except Exception as e:
            logger.error(
                "Failed to get transcript for instance",
                extra={"instance_id": instance_id, "error": str(e)},
            )
            return issues

        # Parse transcript into messages (simple line-based parsing)
        from datetime import datetime

        from orchestrator.compat import UTC
        from supervision.analysis.models import Message

        messages = [
            Message(role="assistant", content=line, timestamp=datetime.now(UTC))
            for line in transcript.split("\n")
            if line.strip()
        ]

        # Analyze transcript for progress signals
        analysis = self.analyzer.analyze(messages)

        # Get progress snapshot from tracker
        snapshot = self.tracker.get_snapshot()

        # Detect stuck state
        if analysis.status == AnalysisStatus.BLOCKED:
            issues.append(
                DetectedIssue(
                    instance_id=instance_id,
                    issue_type="stuck",
                    severity=IssueSeverity.WARNING,
                    description="Instance appears blocked with no progress",
                    detected_at=datetime.now(UTC),
                    confidence=analysis.confidence,
                    evidence={"analysis": analysis, "blockers": analysis.blockers},
                )
            )

        # Detect waiting for work
        if snapshot.in_progress == 0 and snapshot.completed > 0:
            issues.append(
                DetectedIssue(
                    instance_id=instance_id,
                    issue_type="waiting",
                    severity=IssueSeverity.INFO,
                    description="Instance idle after completing work",
                    detected_at=datetime.now(UTC),
                    confidence=0.9,
                    evidence={"snapshot": snapshot},
                )
            )

        # Detect error loop
        if snapshot.failed >= self.config.error_loop_threshold:
            issues.append(
                DetectedIssue(
                    instance_id=instance_id,
                    issue_type="error_loop",
                    severity=IssueSeverity.ERROR,
                    description=f"Instance has {snapshot.failed} failed tasks",
                    detected_at=datetime.now(UTC),
                    confidence=0.95,
                    evidence={"snapshot": snapshot, "failed_count": snapshot.failed},
                )
            )

        return issues

    async def _handle_issue(self, issue: DetectedIssue):
        """Handle a detected issue with appropriate intervention.

        Decision logic:
        1. Check intervention limits
        2. Check cooldown period
        3. Select intervention type
        4. Execute intervention
        5. Record result

        Args:
            issue: Detected issue to handle
        """
        instance_id = issue.instance_id

        # Check intervention limits
        intervention_count = self.intervention_counts.get(instance_id, 0)
        if intervention_count >= self.config.max_interventions_per_instance:
            logger.warning(
                "Max interventions reached, escalating",
                extra={"instance_id": instance_id, "count": intervention_count},
            )
            await self._escalate_issue(issue)
            return

        # Check cooldown
        last_intervention = self.last_intervention.get(instance_id)
        if last_intervention:
            seconds_since = (datetime.now(UTC) - last_intervention).total_seconds()
            if seconds_since < self.config.intervention_cooldown_seconds:
                logger.debug(
                    "Intervention cooldown active, skipping",
                    extra={
                        "instance_id": instance_id,
                        "seconds_remaining": self.config.intervention_cooldown_seconds
                        - seconds_since,
                    },
                )
                return

        # Select intervention based on issue type
        intervention = self._select_intervention(issue)

        # Execute intervention
        success = await self._execute_intervention(intervention)

        # Record intervention
        intervention.success = success
        self.intervention_history.append(intervention)
        self.intervention_counts[instance_id] = intervention_count + 1
        self.last_intervention[instance_id] = datetime.now(UTC)

        logger.info(
            "Intervention executed",
            extra={
                "instance_id": instance_id,
                "intervention_type": intervention.intervention_type.value,
                "success": success,
            },
        )

    def _select_intervention(self, issue: DetectedIssue) -> InterventionRecord:
        """Select appropriate intervention for issue.

        Args:
            issue: Detected issue

        Returns:
            Intervention to execute
        """
        import uuid

        intervention_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC)

        # Stuck instance -> status check
        if issue.issue_type == "stuck":
            return InterventionRecord(
                intervention_id=intervention_id,
                intervention_type=InterventionType.STATUS_CHECK,
                target_instance_id=issue.instance_id,
                timestamp=timestamp,
                reason=issue.description,
                action_taken="Sending status check message",
            )

        # Waiting instance -> check for available work
        elif issue.issue_type == "waiting":
            return InterventionRecord(
                intervention_id=intervention_id,
                intervention_type=InterventionType.REASSIGN_WORK,
                target_instance_id=issue.instance_id,
                timestamp=timestamp,
                reason=issue.description,
                action_taken="Checking for work to assign",
            )

        # Error loop -> provide guidance or spawn helper
        elif issue.issue_type == "error_loop":
            return InterventionRecord(
                intervention_id=intervention_id,
                intervention_type=InterventionType.PROVIDE_GUIDANCE,
                target_instance_id=issue.instance_id,
                timestamp=timestamp,
                reason=issue.description,
                action_taken="Providing error recovery guidance",
            )

        # Default: status check
        return InterventionRecord(
            intervention_id=intervention_id,
            intervention_type=InterventionType.STATUS_CHECK,
            target_instance_id=issue.instance_id,
            timestamp=timestamp,
            reason=issue.description,
            action_taken="Default status check",
        )

    async def _execute_intervention(self, intervention: InterventionRecord) -> bool:
        """Execute an intervention action.

        Args:
            intervention: Intervention to execute

        Returns:
            True if intervention succeeded, False otherwise
        """
        try:
            if intervention.intervention_type == InterventionType.STATUS_CHECK:
                # Send status check message
                message = (
                    "Status check: You appear to be making no progress. "
                    "Can you provide an update on your current task and any blockers?"
                )
                await self.manager.send_to_instance(
                    instance_id=intervention.target_instance_id,
                    message=message,
                    wait_for_response=False,
                    timeout_seconds=30,
                )
                logger.info(f"Sent status check to {intervention.target_instance_id}")
                return True

            elif intervention.intervention_type == InterventionType.PROVIDE_GUIDANCE:
                # Send guidance message
                message = (
                    "I notice you've encountered multiple errors. "
                    "Consider: 1) Review error messages carefully, "
                    "2) Check for common issues, 3) Request help if needed."
                )
                await self.manager.send_to_instance(
                    instance_id=intervention.target_instance_id,
                    message=message,
                    wait_for_response=False,
                    timeout_seconds=30,
                )
                logger.info(f"Sent guidance to {intervention.target_instance_id}")
                return True

            elif intervention.intervention_type == InterventionType.REASSIGN_WORK:
                # Check for work to assign (placeholder - would query work queue)
                logger.info(f"Would check for work to assign to {intervention.target_instance_id}")
                # Future: Implement work queue and assignment logic
                return True

            else:
                logger.warning(f"Unhandled intervention type: {intervention.intervention_type}")
                return False

        except Exception as e:
            logger.error(
                "Intervention execution failed",
                extra={"intervention_id": intervention.intervention_id, "error": str(e)},
                exc_info=True,
            )
            return False

    async def _escalate_issue(self, issue: DetectedIssue):
        """Escalate unresolvable issue to user.

        Args:
            issue: Issue to escalate
        """
        logger.warning(
            "Escalating issue to user",
            extra={
                "instance_id": issue.instance_id,
                "issue_type": issue.issue_type,
                "severity": issue.severity.value,
                "description": issue.description,
            },
        )

        # Would integrate with user notification system
        # For now, just log

    def get_network_health_summary(self) -> dict[str, Any]:
        """Get current network health summary.

        Returns:
            Dictionary with network health metrics
        """
        snapshot = self.tracker.get_snapshot()

        return {
            "total_interventions": len(self.intervention_history),
            "active_issues": len([i for i in self.intervention_history if i.success is None]),
            "successful_interventions": len(
                [i for i in self.intervention_history if i.success is True]
            ),
            "failed_interventions": len(
                [i for i in self.intervention_history if i.success is False]
            ),
            "progress_snapshot": {
                "total_tasks": snapshot.total_tasks,
                "completed": snapshot.completed,
                "in_progress": snapshot.in_progress,
                "blocked": snapshot.blocked,
                "failed": snapshot.failed,
                "completion_percentage": snapshot.completion_percentage,
            },
            "instances_intervened": list(self.intervention_counts.keys()),
            "running": self.running,
        }
