"""Position tracking for incremental log reading.

This module provides persistent storage of log reading positions using JSON
with file locking to support concurrent access from multiple processes.
"""

from __future__ import annotations

import fcntl
import json
import logging
from pathlib import Path
from typing import Any

from .models import LogPosition

logger = logging.getLogger(__name__)


class PositionTracker:
    """Manages persistent storage of log reading positions.

    This class handles saving and loading LogPosition objects to/from JSON
    storage with file locking to prevent concurrent access conflicts. Each
    instance's position is tracked separately, enabling efficient incremental
    log reading across restarts.

    Attributes:
        state_file: Path to the JSON file storing all positions.
        _positions: In-memory cache of positions keyed by (instance_id, log_type).
    """

    def __init__(self, state_dir: str | Path = "/tmp/madrox_logs/monitoring_state"):
        """Initialize position tracker.

        Args:
            state_dir: Directory for storing position state file.
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "monitor_positions.json"
        self._positions: dict[tuple[str, str], LogPosition] = {}

        # Load existing positions
        self._load_positions()

    def _load_positions(self) -> None:
        """Load positions from disk into memory with file locking.

        Uses fcntl shared lock to safely read the position file. If the file
        doesn't exist or is corrupted, starts with an empty position cache.
        """
        if not self.state_file.exists():
            logger.info("Position state file does not exist, starting fresh")
            return

        try:
            with self.state_file.open("r") as f:
                # Acquire shared lock for reading
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                    for key_str, pos_dict in data.items():
                        instance_id, log_type = key_str.split(":", 1)
                        position = LogPosition(
                            instance_id=pos_dict["instance_id"],
                            log_type=pos_dict["log_type"],
                            file_path=pos_dict["file_path"],
                            last_byte_offset=pos_dict["last_byte_offset"],
                            last_line_number=pos_dict["last_line_number"],
                            last_read_timestamp=pos_dict["last_read_timestamp"],
                            checksum=pos_dict["checksum"],
                        )
                        self._positions[(instance_id, log_type)] = position
                    logger.info(f"Loaded {len(self._positions)} positions from disk")
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse position file: {e}, starting fresh")
            self._positions = {}
        except Exception as e:
            logger.error(f"Error loading positions: {e}, starting fresh")
            self._positions = {}

    def _save_positions(self) -> None:
        """Save positions to disk with file locking.

        Uses fcntl exclusive lock to safely write the position file. Writes
        to a temporary file first and then atomically renames it to prevent
        corruption if the process is interrupted.
        """
        try:
            # Prepare data for serialization
            data: dict[str, Any] = {}
            for (instance_id, log_type), position in self._positions.items():
                key = f"{instance_id}:{log_type}"
                data[key] = {
                    "instance_id": position.instance_id,
                    "log_type": position.log_type,
                    "file_path": position.file_path,
                    "last_byte_offset": position.last_byte_offset,
                    "last_line_number": position.last_line_number,
                    "last_read_timestamp": position.last_read_timestamp,
                    "checksum": position.checksum,
                }

            # Write to temporary file with exclusive lock
            temp_file = self.state_file.with_suffix(".tmp")
            with temp_file.open("w") as f:
                # Acquire exclusive lock for writing
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2)
                    f.flush()
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Atomic rename to replace old file
            temp_file.replace(self.state_file)
            logger.debug(f"Saved {len(self._positions)} positions to disk")

        except Exception as e:
            logger.error(f"Failed to save positions: {e}")

    def get_position(self, instance_id: str, log_type: str) -> LogPosition | None:
        """Get the current position for an instance's log file.

        Args:
            instance_id: Instance identifier.
            log_type: Type of log file (e.g., "tmux_output", "instance").

        Returns:
            LogPosition if found, None if no position exists yet.
        """
        return self._positions.get((instance_id, log_type))

    def update_position(self, position: LogPosition) -> None:
        """Update the position for an instance's log file.

        Updates both the in-memory cache and persists to disk.

        Args:
            position: New position to store.
        """
        key = (position.instance_id, position.log_type)
        self._positions[key] = position
        self._save_positions()
        logger.debug(
            f"Updated position for {position.instance_id}:{position.log_type} "
            f"to offset {position.last_byte_offset}, line {position.last_line_number}"
        )

    def remove_position(self, instance_id: str, log_type: str) -> None:
        """Remove position tracking for an instance's log file.

        Useful when an instance is terminated and logs are no longer needed.

        Args:
            instance_id: Instance identifier.
            log_type: Type of log file.
        """
        key = (instance_id, log_type)
        if key in self._positions:
            del self._positions[key]
            self._save_positions()
            logger.info(f"Removed position for {instance_id}:{log_type}")

    def get_all_positions(self) -> list[LogPosition]:
        """Get all tracked positions.

        Returns:
            List of all LogPosition objects currently tracked.
        """
        return list(self._positions.values())

    def clear_all_positions(self) -> None:
        """Clear all tracked positions.

        Removes all position data from memory and disk. Use with caution.
        """
        self._positions = {}
        self._save_positions()
        logger.warning("Cleared all position tracking data")
