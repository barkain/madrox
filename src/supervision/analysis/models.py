"""Data models for transcript analysis and pattern extraction."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AnalysisStatus(Enum):
    """Status of analysis operations."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass(frozen=True)
class Message:
    """
    Represents a single message in a conversation transcript.

    Immutable message structure for safe concurrent analysis.

    Attributes:
        role: Message sender role (e.g., "user", "assistant", "system")
        content: Message text content
        timestamp: When the message was created
        tool_calls: Optional list of tool invocations in this message
        metadata: Additional message metadata (token usage, model info, etc.)
    """

    role: str
    content: str
    timestamp: datetime
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisResult:
    """
    Result of analyzing a conversation transcript.

    Immutable result structure containing extracted patterns and insights.

    Attributes:
        status: Current status of the analysis
        tasks: Extracted task descriptions with context
        blockers: Identified blockers or impediments
        milestones: Detected milestones or achievements
        confidence: Confidence score for the analysis (0.0-1.0)
        metadata: Additional analysis metadata (processing time, patterns matched, etc.)
    """

    status: AnalysisStatus
    tasks: list[str]
    blockers: list[str]
    milestones: list[str]
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence score range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
