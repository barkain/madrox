"""Incremental log reading with rotation detection.

This module provides efficient incremental reading of log files using byte
offsets and detects log rotation via MD5 checksums to handle truncation.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path

from .models import LogPosition
from .position_tracker import PositionTracker

logger = logging.getLogger(__name__)


class IncrementalLogReader:
    """Reads log files incrementally without re-reading entire files.

    This class uses byte offsets to track reading position and MD5 checksums
    to detect when log files have been rotated or truncated. It integrates
    with PositionTracker to persist state across restarts.

    Attributes:
        position_tracker: Position tracker for persistence.
        max_lines: Maximum lines to read per call.
    """

    def __init__(
        self,
        position_tracker: PositionTracker,
        max_lines_per_read: int = 200,
    ):
        """Initialize incremental log reader.

        Args:
            position_tracker: Position tracker for persistence.
            max_lines_per_read: Maximum lines to read per call.
        """
        self.position_tracker = position_tracker
        self.max_lines = max_lines_per_read

    def read_new_content(
        self,
        instance_id: str,
        log_file_path: str | Path,
        log_type: str = "tmux_output",
    ) -> tuple[list[str], int]:
        """Read new content from log file since last read.

        This method reads only new lines appended since the last read,
        using byte offsets for efficiency. It detects log rotation via
        checksum comparison and handles it gracefully by reading from
        the beginning.

        Args:
            instance_id: Instance identifier.
            log_file_path: Path to log file to read.
            log_type: Type of log file for position tracking.

        Returns:
            Tuple of (new_lines, total_lines_read) where new_lines is a list
            of strings containing only the new content since last read, and
            total_lines_read is the cumulative count.
        """
        log_path = Path(log_file_path)

        # Check if file exists
        if not log_path.exists():
            logger.debug(f"Log file does not exist: {log_path}")
            return [], 0

        # Get file stats
        try:
            file_size = log_path.stat().st_size
        except OSError as e:
            logger.error(f"Failed to stat log file {log_path}: {e}")
            return [], 0

        # Handle empty file
        if file_size == 0:
            logger.debug(f"Log file is empty: {log_path}")
            return [], 0

        # Get previous position
        position = self.position_tracker.get_position(instance_id, log_type)

        # Calculate current checksum (always calculate for storage)
        current_checksum = self._calculate_checksum(log_path)

        # Determine if we need to start from beginning
        start_from_beginning = False
        if position is None:
            # First time reading this file
            logger.info(f"First read of log file: {log_path}")
            start_from_beginning = True
        elif position.last_byte_offset > file_size:
            # File was truncated
            logger.warning(
                f"Log file {log_path} was truncated "
                f"(offset {position.last_byte_offset} > size {file_size})"
            )
            start_from_beginning = True
        elif position.checksum != current_checksum:
            # File has been rotated or content at beginning changed
            # Only trigger if file size suggests rotation (decreased or similar size)
            # to avoid false positives when appending to files smaller than checksum size
            if file_size <= position.last_byte_offset + 100:
                # File didn't grow much or shrunk - likely rotation
                logger.info(
                    f"Log rotation detected for {log_path} "
                    f"(checksum changed from {position.checksum} to {current_checksum})"
                )
                start_from_beginning = True
            # else: File grew significantly - likely append, checksum change is expected

        # Read new content
        try:
            with log_path.open("r", encoding="utf-8", errors="replace") as f:
                if start_from_beginning:
                    # Read from beginning
                    offset = 0
                    line_number = 0
                else:
                    # Seek to last position (position is guaranteed non-None here)
                    if position is None:
                        raise ValueError(
                            "position should not be None when not starting from beginning"
                        )
                    offset = position.last_byte_offset
                    line_number = position.last_line_number
                    f.seek(offset)

                # Read new lines up to max_lines
                new_lines: list[str] = []
                lines_read = 0

                while True:
                    line = f.readline()
                    if not line:  # EOF
                        break

                    new_lines.append(line.rstrip("\n"))
                    lines_read += 1
                    line_number += 1

                    if lines_read >= self.max_lines:
                        logger.debug(f"Reached max_lines limit ({self.max_lines}) for {log_path}")
                        break

                # Update offset to current position
                new_offset = f.tell()

                # Update position tracker
                new_position = LogPosition(
                    instance_id=instance_id,
                    log_type=log_type,
                    file_path=str(log_path),
                    last_byte_offset=new_offset,
                    last_line_number=line_number,
                    last_read_timestamp=datetime.now().isoformat(),
                    checksum=current_checksum,
                )
                self.position_tracker.update_position(new_position)

                if new_lines:
                    logger.debug(
                        f"Read {len(new_lines)} new lines from {log_path} "
                        f"(offset {offset} -> {new_offset})"
                    )

                return new_lines, line_number

        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error reading {log_path}: {e}")
            return [], 0
        except OSError as e:
            logger.error(f"OS error reading {log_path}: {e}")
            return [], 0
        except Exception as e:
            logger.error(f"Unexpected error reading {log_path}: {e}")
            return [], 0

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of first 16 bytes of file for rotation detection.

        We only checksum a small fixed portion at the beginning of the file. This is
        sufficient to detect rotation/truncation while minimizing false positives when
        new content is appended to small files. Using only 16 bytes ensures the
        checksum is less likely to change when appending content.

        Args:
            file_path: Path to file.

        Returns:
            MD5 checksum as hex string, or empty string on error.
        """
        try:
            with file_path.open("rb") as f:
                # Read only first 16 bytes for checksum to minimize false rotation
                # detection on small files when new content is appended
                chunk = f.read(16)
                if not chunk:
                    return ""
                return hashlib.md5(chunk).hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return ""

    def read_last_n_lines(
        self,
        log_file_path: str | Path,
        n: int = 100,
    ) -> list[str]:
        """Read last N lines from a log file.

        This is a utility method for getting recent context without using
        position tracking. Useful for initial summaries or debugging.

        Args:
            log_file_path: Path to log file.
            n: Number of lines to read from end.

        Returns:
            List of last N lines from the file.
        """
        log_path = Path(log_file_path)

        if not log_path.exists():
            return []

        try:
            with log_path.open("r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                # Return last N lines, stripped of newlines
                return [line.rstrip("\n") for line in lines[-n:]]
        except Exception as e:
            logger.error(f"Error reading last {n} lines from {log_path}: {e}")
            return []

    def reset_position(self, instance_id: str, log_type: str) -> None:
        """Reset reading position for an instance's log.

        Forces next read to start from beginning of file.

        Args:
            instance_id: Instance identifier.
            log_type: Type of log file.
        """
        self.position_tracker.remove_position(instance_id, log_type)
        logger.info(f"Reset position for {instance_id}:{log_type}")
