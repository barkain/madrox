"""Configuration for agent monitoring system.

This module defines the configuration dataclass that controls monitoring
service behavior, including polling intervals, storage paths, and LLM settings.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MonitoringConfig:
    """Configuration for the monitoring service.

    This class centralizes all configuration parameters for the monitoring
    system, providing sensible defaults while allowing customization.

    Attributes:
        poll_interval_seconds: Seconds between monitoring polls (default: 12).
        summary_dir: Directory for storing agent summaries (default: /tmp/madrox_logs/summaries).
        state_dir: Directory for position tracking state (default: /tmp/madrox_logs/monitoring_state).
        model: Claude model to use for summary generation (default: claude-haiku-4-5).
        max_log_lines_per_read: Maximum lines to read per poll (default: 200).
        error_backoff_seconds: Seconds to wait after error before retry (default: 10).
        enable_streaming: Whether to enable WebSocket streaming (default: True).
    """

    poll_interval_seconds: int = 12
    summary_dir: str = "/tmp/madrox_logs/summaries"
    state_dir: str = "/tmp/madrox_logs/monitoring_state"
    model: str = "claude-haiku-4-5"
    max_log_lines_per_read: int = 200
    error_backoff_seconds: int = 10
    enable_streaming: bool = True
