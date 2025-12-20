"""Data models for agent monitoring system.

This module defines the core data structures used throughout the monitoring
system, including agent summaries, position tracking, and status enums.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OnTrackStatus(Enum):
    """Enum representing agent alignment with assigned task.

    Attributes:
        ON_TRACK: Agent is working on assigned task as expected.
        DRIFTING: Agent shows minor deviation from assigned task.
        OFF_TRACK: Agent has significant misalignment with assigned task.
        BLOCKED: Agent is stuck, waiting, or encountering errors.
        UNKNOWN: Insufficient data to determine alignment status.
    """

    ON_TRACK = "on_track"
    DRIFTING = "drifting"
    OFF_TRACK = "off_track"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass
class LogPosition:
    """Tracks reading position for incremental log consumption.

    This class stores the state needed to resume reading from where we left off,
    including byte offsets, line numbers, and checksums for rotation detection.

    Attributes:
        instance_id: Unique identifier for the agent instance.
        log_type: Type of log file (e.g., "tmux_output", "instance", "communication").
        file_path: Absolute path to the log file.
        last_byte_offset: File position in bytes for seeking.
        last_line_number: Line number of last read line.
        last_read_timestamp: ISO 8601 timestamp of last read operation.
        checksum: MD5 checksum for detecting log rotation.
    """

    instance_id: str
    log_type: str
    file_path: str
    last_byte_offset: int
    last_line_number: int
    last_read_timestamp: str
    checksum: str


@dataclass
class AgentSummary:
    """Real-time agent activity summary with on-track inference.

    This class represents the complete state of an agent at a point in time,
    including activity description, alignment status, and contextual metadata.

    Attributes:
        instance_id: Unique identifier for the agent instance.
        instance_name: Human-readable name for the agent.
        timestamp: ISO 8601 timestamp when summary was generated.
        current_activity: Concise statement (1-2 sentences) of current activity.
        on_track_status: Agent alignment status enum.
        confidence_score: Confidence in on_track_status assessment (0.0-1.0).
        assigned_task: Task description assigned to agent.
        parent_instance_id: ID of parent/supervisor instance if any.
        role: Agent role/specialization if applicable.
        last_tool_used: Most recently used tool name.
        recent_tools: List of last 5 tools used.
        output_preview: Last 200 characters of agent output.
        idle_duration_seconds: Time since last activity in seconds.
        drift_reasons: List of reasons for drift if not on track.
        alignment_keywords: Keywords indicating task alignment.
        recommended_action: Suggested action for supervisor if needed.
    """

    instance_id: str
    instance_name: str
    timestamp: str
    current_activity: str
    on_track_status: OnTrackStatus
    confidence_score: float
    assigned_task: str | None
    parent_instance_id: str | None
    role: str | None
    last_tool_used: str | None
    recent_tools: list[str]
    output_preview: str
    idle_duration_seconds: float
    drift_reasons: list[str]
    alignment_keywords: list[str]
    recommended_action: str | None
