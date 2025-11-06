"""Agent monitoring system for Madrox orchestrator.

This package provides incremental log reading and position tracking for
monitoring agent activity in real-time. It forms the foundation for the
Phase 1 core infrastructure.

Key Components:
    - models: Data structures for agent summaries and position tracking
    - config: Configuration dataclass for monitoring service
    - position_tracker: Persistent position tracking with file locking
    - log_reader: Incremental log reading with rotation detection

Example:
    >>> from orchestrator.monitoring import (
    ...     MonitoringConfig,
    ...     PositionTracker,
    ...     IncrementalLogReader,
    ... )
    >>> config = MonitoringConfig()
    >>> tracker = PositionTracker(config.state_dir)
    >>> reader = IncrementalLogReader(tracker, config.max_log_lines_per_read)
    >>> lines, total = reader.read_new_content("instance-123", "/path/to/log")
"""

from __future__ import annotations

from .config import MonitoringConfig
from .log_reader import IncrementalLogReader
from .models import AgentSummary, LogPosition, OnTrackStatus
from .position_tracker import PositionTracker

__all__ = [
    "MonitoringConfig",
    "PositionTracker",
    "IncrementalLogReader",
    "LogPosition",
    "AgentSummary",
    "OnTrackStatus",
]

__version__ = "0.1.0"
