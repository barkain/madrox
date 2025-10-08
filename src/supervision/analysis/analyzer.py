"""Transcript analyzer for extracting tasks, blockers, and milestones."""

import logging
import re
from datetime import UTC, datetime

from supervision.analysis.models import AnalysisResult, AnalysisStatus, Message

logger = logging.getLogger(__name__)


class TranscriptAnalyzer:
    """
    Analyzes conversation transcripts to extract actionable insights.

    Pattern-based analyzer that identifies:
    - Tasks and action items
    - Blockers and impediments
    - Milestones and achievements

    Confidence scoring accounts for ambiguity and pattern strength.
    """

    # Task patterns - action-oriented language
    TASK_PATTERNS = [
        r"(?:will|going to|need to|must|should|plan to)\s+(.{10,100})",
        r"(?:implement|create|build|develop|write|add|fix|update)\s+(.{10,100})",
        r"(?:^|\n)(?:TODO|FIXME|TASK):\s*(.{10,200})",
        r"next steps?:\s*(.{10,200})",
        r"(?:i'll|i will|let me)\s+(.{10,100})",
    ]

    # Blocker patterns - problems and impediments
    BLOCKER_PATTERNS = [
        r"(?:blocked by|waiting (?:on|for)|cannot proceed|stuck on)\s+(.{10,100})",
        r"(?:error|exception|failed|failure):\s*(.{10,150})",
        r"(?:issue|problem) with\s+(.{10,100})",
        r"(?:missing|lack of|need)\s+(.{10,100})\s+(?:to proceed|to continue|before)",
        r"(?:dependency on|depends on|requires)\s+(.{10,100})\s+(?:to be|which)",
    ]

    # Milestone patterns - achievements and completions
    MILESTONE_PATTERNS = [
        r"(?:completed|finished|done with|implemented|delivered)\s+(.{10,100})",
        r"(?:successfully|successfully created|successfully implemented)\s+(.{10,100})",
        r"✅\s*(.{10,100})",
        r"(?:milestone reached|achieved|accomplished):\s*(.{10,100})",
        r"(?:all tests pass|tests passing|build successful)",
        r"(?:deployed|released|shipped)\s+(.{10,100})",
    ]

    def __init__(self) -> None:
        """Initialize the transcript analyzer."""
        self._compiled_task_patterns = [re.compile(p, re.IGNORECASE) for p in self.TASK_PATTERNS]
        self._compiled_blocker_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.BLOCKER_PATTERNS
        ]
        self._compiled_milestone_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.MILESTONE_PATTERNS
        ]

        logger.info(
            "TranscriptAnalyzer initialized",
            extra={
                "pattern_count": len(self.TASK_PATTERNS)
                + len(self.BLOCKER_PATTERNS)
                + len(self.MILESTONE_PATTERNS)
            },
        )

    def analyze(self, messages: list[Message]) -> AnalysisResult:
        """
        Analyze a conversation transcript to extract patterns.

        Args:
            messages: List of conversation messages to analyze

        Returns:
            AnalysisResult containing extracted tasks, blockers, and milestones

        Raises:
            ValueError: If messages list is empty
        """
        if not messages:
            logger.warning("Empty message list provided to analyzer")
            raise ValueError("Cannot analyze empty message list")

        logger.info("Starting transcript analysis", extra={"message_count": len(messages)})

        try:
            # Extract patterns from messages
            tasks = self._extract_tasks(messages)
            blockers = self._extract_blockers(messages)
            milestones = self._extract_milestones(messages)

            # Calculate confidence based on pattern matches
            confidence = self._calculate_confidence(len(tasks), len(blockers), len(milestones))

            # Determine status
            status = self._determine_status(blockers, milestones)

            logger.info(
                "Analysis completed",
                extra={
                    "tasks": len(tasks),
                    "blockers": len(blockers),
                    "milestones": len(milestones),
                    "confidence": confidence,
                    "status": status.value,
                },
            )

            return AnalysisResult(
                status=status,
                tasks=tasks,
                blockers=blockers,
                milestones=milestones,
                confidence=confidence,
                metadata={
                    "message_count": len(messages),
                    "analyzed_at": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.error("Analysis failed", extra={"error": str(e)})
            return AnalysisResult(
                status=AnalysisStatus.ERROR,
                tasks=[],
                blockers=[f"Analysis error: {str(e)}"],
                milestones=[],
                confidence=0.0,
                metadata={"error": str(e), "analyzed_at": datetime.now(UTC).isoformat()},
            )

    def _extract_tasks(self, messages: list[Message]) -> list[str]:
        """Extract task descriptions from messages."""
        tasks = []
        for message in messages:
            for pattern in self._compiled_task_patterns:
                matches = pattern.finditer(message.content)
                for match in matches:
                    task = self._clean_extracted_text(
                        match.group(1) if match.lastindex else match.group(0)
                    )
                    if task and len(task) >= 10:  # Minimum meaningful task length
                        tasks.append(task)

        # Deduplicate while preserving order
        return list(dict.fromkeys(tasks))

    def _extract_blockers(self, messages: list[Message]) -> list[str]:
        """Extract blocker descriptions from messages."""
        blockers = []
        for message in messages:
            for pattern in self._compiled_blocker_patterns:
                matches = pattern.finditer(message.content)
                for match in matches:
                    blocker = self._clean_extracted_text(
                        match.group(1) if match.lastindex else match.group(0)
                    )
                    if blocker and len(blocker) >= 10:
                        blockers.append(blocker)

        return list(dict.fromkeys(blockers))

    def _extract_milestones(self, messages: list[Message]) -> list[str]:
        """Extract milestone descriptions from messages."""
        milestones = []
        for message in messages:
            for pattern in self._compiled_milestone_patterns:
                matches = pattern.finditer(message.content)
                for match in matches:
                    if match.lastindex:
                        milestone = self._clean_extracted_text(match.group(1))
                    else:
                        milestone = self._clean_extracted_text(match.group(0))

                    if milestone and len(milestone) >= 10:
                        milestones.append(milestone)

        return list(dict.fromkeys(milestones))

    def _clean_extracted_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        # Remove excessive whitespace
        text = " ".join(text.split())

        # Remove trailing punctuation that might be sentence delimiters
        text = text.rstrip(".,;:")

        # Truncate at sentence boundaries if too long
        if len(text) > 150:
            # Try to find last complete sentence
            for delimiter in [".", "!", "?"]:
                last_delim = text[:150].rfind(delimiter)
                if last_delim > 50:
                    text = text[: last_delim + 1]
                    break
            else:
                text = text[:150].rstrip() + "..."

        return text.strip()

    def _calculate_confidence(
        self, task_count: int, blocker_count: int, milestone_count: int
    ) -> float:
        """
        Calculate confidence score based on pattern matches.

        Higher confidence when:
        - Multiple patterns detected
        - Balanced distribution of patterns
        - Clear signal-to-noise ratio

        Args:
            task_count: Number of tasks extracted
            blocker_count: Number of blockers extracted
            milestone_count: Number of milestones extracted

        Returns:
            Confidence score between 0.0 and 1.0
        """
        total_patterns = task_count + blocker_count + milestone_count

        # Base confidence on total patterns found
        if total_patterns == 0:
            return 0.0
        elif total_patterns == 1:
            return 0.4
        elif total_patterns <= 3:
            return 0.6
        elif total_patterns <= 6:
            return 0.8
        else:
            return 0.95

    def _determine_status(self, blockers: list[str], milestones: list[str]) -> AnalysisStatus:
        """
        Determine analysis status based on extracted patterns.

        Args:
            blockers: List of extracted blockers
            milestones: List of extracted milestones

        Returns:
            Appropriate AnalysisStatus
        """
        if blockers and not milestones:
            return AnalysisStatus.BLOCKED
        elif milestones:
            return AnalysisStatus.COMPLETED
        else:
            return AnalysisStatus.IN_PROGRESS
