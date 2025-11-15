"""
MonitoringService - Background service for monitoring Claude instances and generating summaries.

This service runs an asyncio task that polls InstanceManager at regular intervals,
generates activity summaries using LLMSummarizer, and persists them to disk.

Phase 3: Background Monitoring Service
"""

import asyncio
import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

try:
    import aiofiles
except ImportError:
    # Fallback if aiofiles not available
    aiofiles = None


class MonitoringService:
    """
    Background service for monitoring Claude instances and generating summaries.

    This service runs an asyncio task that polls InstanceManager at regular intervals,
    generates activity summaries using LLMSummarizer, and persists them to disk.
    """

    # Class Attributes (Singleton pattern)
    _instance: Optional['MonitoringService'] = None
    _lock: asyncio.Lock = None  # Will be initialized at runtime

    def __init__(
        self,
        instance_manager: Any,
        llm_summarizer: Any,
        poll_interval: int = 12,
        storage_path: str = "/tmp/madrox_logs/summaries",
        max_tokens: int = 100
    ):
        """
        Initialize the monitoring service.

        Args:
            instance_manager: Reference to the InstanceManager
            llm_summarizer: Reference to the LLMSummarizer
            poll_interval: Polling interval in seconds (default: 12)
            storage_path: Base path for storing summaries (session subdirectory auto-created)
            max_tokens: Maximum tokens for LLM summary generation (default: 100)
        """
        self.instance_manager = instance_manager
        self.llm_summarizer = llm_summarizer
        self.poll_interval = poll_interval
        self.max_tokens = max_tokens

        # Create session-specific subdirectory: /tmp/madrox_logs/summaries/session_YYYYMMDD_HHMMSS/
        from datetime import datetime
        session_id = datetime.now(UTC).strftime("session_%Y%m%d_%H%M%S")
        self.storage_path = Path(storage_path) / session_id
        self.session_id = session_id

        self._task: asyncio.Task | None = None
        self._running = False
        self._logger = logging.getLogger(__name__)

        # Error tracking for backoff
        self._error_counts: dict[str, int] = {}
        self._last_error_time: dict[str, float] = {}

    # ============================================================================
    # Lifecycle Methods
    # ============================================================================

    async def start(self) -> None:
        """
        Start the monitoring service.

        Creates the background asyncio task for monitoring.
        Ensures only one task is running at a time.
        Creates necessary directories.

        Raises:
            RuntimeError: If service is already running
        """
        if self._running:
            raise RuntimeError("MonitoringService is already running")

        self._logger.info(f"Starting MonitoringService (session: {self.session_id})...")

        # Create session storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._logger.info(f"Session summaries path: {self.storage_path}")

        # Start background task
        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())

        self._logger.info(f"MonitoringService started (poll interval: {self.poll_interval}s, session: {self.session_id})")

    async def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the monitoring service gracefully.

        Args:
            timeout: Maximum time to wait for clean shutdown (seconds)

        Cancels the background task and waits for completion.
        Ensures all pending writes are flushed.
        """
        if not self._running:
            return

        self._logger.info("Stopping MonitoringService...")
        self._running = False

        if self._task:
            # Cancel the background task
            self._task.cancel()

            try:
                # Wait for task to complete
                await asyncio.wait_for(self._task, timeout=timeout)
            except TimeoutError:
                self._logger.warning("Monitoring task did not stop within timeout")
            except asyncio.CancelledError:
                self._logger.info("Monitoring task cancelled successfully")

        self._logger.info("MonitoringService stopped")

    def is_running(self) -> bool:
        """Check if the monitoring service is currently running."""
        return self._running and self._task is not None and not self._task.done()

    # ============================================================================
    # Core Monitoring Methods
    # ============================================================================

    async def _monitoring_loop(self) -> None:
        """
        Main monitoring loop (runs in background task).

        Continuously polls InstanceManager, processes instances,
        and persists summaries at the configured interval.

        Handles all exceptions to prevent task crashes.
        Implements graceful shutdown on cancellation.
        """
        self._logger.info("Monitoring loop started")

        while self._running:
            try:
                # Get all instances from InstanceManager
                instances = self.instance_manager.get_all_instances()

                # Filter for active instances (running, idle, busy)
                active_instances = {
                    instance_id: data
                    for instance_id, data in instances.items()
                    if data.get('state') in ['running', 'idle', 'busy']
                }

                self._logger.debug(f"Found {len(active_instances)} active instances")

                # Process each instance in parallel
                tasks = []
                for instance_id, instance_data in active_instances.items():
                    if not self._should_skip_instance(instance_id):
                        tasks.append(self._process_instance(instance_id, instance_data))

                # Process all instances concurrently
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                # Wait for next poll interval
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                self._logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                self._logger.critical(f"Critical error in monitoring loop: {e}")
                # Don't crash, wait and retry
                await asyncio.sleep(self.poll_interval)

        self._logger.info("Monitoring loop exited")

    async def _process_instance(self, instance_id: str, instance_data: dict) -> None:
        """
        Process a single instance and generate summary.

        Args:
            instance_id: ID of the instance to process
            instance_data: Instance metadata and status

        Steps:
            1. Get recent output from instance
            2. Call LLMSummarizer to generate summary
            3. Persist summary to disk
            4. Update error tracking

        Implements error isolation - failures don't crash the loop.
        """
        try:
            start_time = time.time()

            # Get recent activity
            activity = await self._get_instance_activity(instance_id)

            if not activity or len(activity.strip()) == 0:
                self._logger.debug(f"No activity for instance {instance_id}, skipping")
                return

            # Generate summary using LLMSummarizer
            self._logger.debug(f"Generating summary for instance {instance_id}")
            summary = await self.llm_summarizer.summarize_activity(
                instance_id=instance_id,
                activity_text=activity,
                max_tokens=self.max_tokens
            )

            # Calculate generation time
            generation_time_ms = int((time.time() - start_time) * 1000)

            # Persist summary
            await self._persist_summary(
                instance_id=instance_id,
                summary=summary,
                status=instance_data.get('state', 'unknown'),
                metadata={
                    'output_length': len(activity),
                    'error_count': self._error_counts.get(instance_id, 0),
                    'generation_time_ms': generation_time_ms,
                    'poll_interval': self.poll_interval
                }
            )

            # Record success
            self._record_success(instance_id)
            self._logger.info(f"Successfully processed instance {instance_id} ({generation_time_ms}ms)")

        except Exception as e:
            self._logger.error(f"Error processing instance {instance_id}: {e}")
            self._record_error(instance_id)

    async def _get_instance_activity(self, instance_id: str) -> str:
        """
        Retrieve recent activity for an instance.

        Args:
            instance_id: ID of the instance

        Returns:
            Recent output/activity as string

        Calls instance_manager.get_instance_output() with appropriate limits.
        """
        try:
            # Get recent output (last 1000 lines)
            output_data = await self.instance_manager.get_instance_output(
                instance_id=instance_id,
                limit=1000
            )

            # Extract output text
            if isinstance(output_data, dict):
                output = output_data.get('output', '')
            elif isinstance(output_data, list):
                # If it's a list of messages, join them
                output = '\n'.join(str(msg) for msg in output_data)
            else:
                output = str(output_data)

            return output

        except Exception as e:
            self._logger.warning(f"Failed to get activity for instance {instance_id}: {e}")
            return ""

    # ============================================================================
    # Persistence Methods
    # ============================================================================

    async def _persist_summary(
        self,
        instance_id: str,
        summary: str,
        status: str,
        metadata: dict | None = None
    ) -> Path:
        """
        Persist summary to disk using atomic writes.

        Args:
            instance_id: Instance ID
            summary: Generated summary text
            status: Instance status (running, idle, etc.)
            metadata: Additional metadata to include

        Returns:
            Path to the written summary file

        Steps:
            1. Create instance directory if not exists
            2. Generate filename with timestamp
            3. Write to temporary file
            4. Atomically rename to final location
            5. Update 'latest.json' symlink

        Ensures atomic writes to prevent partial reads.
        """
        try:
            # Create instance directory
            instance_dir = self.storage_path / instance_id
            instance_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now(UTC)
            filename = self._get_summary_filename(timestamp)
            summary_file = instance_dir / filename

            # Prepare summary data
            summary_data = {
                'instance_id': instance_id,
                'timestamp': timestamp.isoformat(),
                'status': status,
                'summary': summary,
                'metadata': metadata or {}
            }

            # Atomic write
            await self._atomic_write(summary_file, summary_data)

            # Update latest symlink
            await self._update_latest_symlink(instance_id, summary_file)

            self._logger.debug(f"Persisted summary for {instance_id}: {summary_file}")

            return summary_file

        except PermissionError as e:
            self._logger.error(f"Permission denied writing summary for {instance_id}: {e}")
            raise
        except OSError as e:
            if e.errno == 28:  # ENOSPC - No space left on device
                self._logger.critical("Disk full, cannot write summaries")
            raise

    async def _atomic_write(self, filepath: Path, data: dict) -> None:
        """
        Perform atomic write to file.

        Args:
            filepath: Target file path
            data: Data to write (will be JSON serialized)
        """
        temp_path = filepath.with_suffix('.tmp')

        # Write to temp file
        if aiofiles:
            # Use async file I/O if available
            async with aiofiles.open(temp_path, 'w') as f:
                await f.write(json.dumps(data, indent=2))
                await f.flush()
        else:
            # Fallback to sync I/O
            with open(temp_path, 'w') as f:
                f.write(json.dumps(data, indent=2))
                f.flush()
                os.fsync(f.fileno())

        # Atomic rename
        temp_path.rename(filepath)

    def _get_summary_filename(self, timestamp: datetime) -> str:
        """
        Generate filename for summary.

        Format: summary_YYYY-MM-DDTHH:MM:SS.json
        """
        return f"summary_{timestamp.strftime('%Y-%m-%dT%H:%M:%S')}.json"

    async def _update_latest_symlink(self, instance_id: str, summary_file: Path) -> None:
        """
        Update the 'latest.json' symlink to point to the most recent summary.

        Args:
            instance_id: Instance ID
            summary_file: Path to the latest summary file
        """
        instance_dir = self.storage_path / instance_id
        latest_link = instance_dir / "latest.json"

        try:
            # Remove existing symlink if it exists
            if latest_link.exists() or latest_link.is_symlink():
                latest_link.unlink()

            # Create new symlink (relative path)
            latest_link.symlink_to(summary_file.name)

        except Exception as e:
            self._logger.warning(f"Failed to update latest symlink for {instance_id}: {e}")

    # ============================================================================
    # Error Handling Methods
    # ============================================================================

    def _should_skip_instance(self, instance_id: str) -> bool:
        """
        Determine if an instance should be skipped due to recent errors.

        Args:
            instance_id: Instance ID to check

        Returns:
            True if instance should be skipped (in backoff period)

        Implements exponential backoff based on error count.
        """
        error_count = self._error_counts.get(instance_id, 0)
        if error_count == 0:
            return False

        last_error_time = self._last_error_time.get(instance_id, 0)
        backoff_time = self._get_backoff_seconds(error_count)

        time_since_error = time.time() - last_error_time

        if time_since_error < backoff_time:
            return True  # Still in backoff period

        return False

    def _record_error(self, instance_id: str) -> None:
        """
        Record an error for an instance (for backoff calculation).

        Args:
            instance_id: Instance ID that encountered an error
        """
        self._error_counts[instance_id] = self._error_counts.get(instance_id, 0) + 1
        self._last_error_time[instance_id] = time.time()

        error_count = self._error_counts[instance_id]
        backoff = self._get_backoff_seconds(error_count)

        self._logger.warning(
            f"Error recorded for {instance_id} "
            f"(count: {error_count}, backoff: {backoff}s)"
        )

    def _record_success(self, instance_id: str) -> None:
        """
        Record a successful processing (resets error tracking).

        Args:
            instance_id: Instance ID that was successfully processed
        """
        if instance_id in self._error_counts:
            del self._error_counts[instance_id]
        if instance_id in self._last_error_time:
            del self._last_error_time[instance_id]

    def _get_backoff_seconds(self, error_count: int) -> float:
        """
        Calculate backoff time based on error count.

        Args:
            error_count: Number of consecutive errors

        Returns:
            Backoff time in seconds

        Formula: min(2^error_count, 300) seconds
        Max backoff: 5 minutes
        """
        return min(2 ** error_count, 300)

    # ============================================================================
    # Utility Methods
    # ============================================================================

    @classmethod
    async def get_instance(
        cls,
        instance_manager: Any,
        llm_summarizer: Any,
        **kwargs
    ) -> 'MonitoringService':
        """
        Get or create the singleton MonitoringService instance.

        Thread-safe singleton pattern using asyncio.Lock.

        Args:
            instance_manager: Reference to InstanceManager
            llm_summarizer: Reference to LLMSummarizer
            **kwargs: Additional arguments for initialization

        Returns:
            MonitoringService instance
        """
        # Initialize lock if not already done
        if cls._lock is None:
            cls._lock = asyncio.Lock()

        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(
                    instance_manager=instance_manager,
                    llm_summarizer=llm_summarizer,
                    **kwargs
                )

            return cls._instance

    async def get_summary(
        self,
        instance_id: str,
        latest: bool = True
    ) -> dict | None:
        """
        Retrieve a summary for a specific instance.

        Args:
            instance_id: Instance ID
            latest: If True, return only the latest summary

        Returns:
            Summary data as dict, or None if not found
        """
        instance_dir = self.storage_path / instance_id

        if not instance_dir.exists():
            return None

        try:
            if latest:
                # Read from latest.json symlink
                latest_file = instance_dir / "latest.json"
                if latest_file.exists():
                    if aiofiles:
                        async with aiofiles.open(latest_file, 'r') as f:
                            content = await f.read()
                            return json.loads(content)
                    else:
                        with open(latest_file) as f:
                            return json.load(f)

            return None

        except Exception as e:
            self._logger.error(f"Error reading summary for {instance_id}: {e}")
            return None

    async def get_all_summaries(self) -> dict[str, dict]:
        """
        Retrieve the latest summaries for all monitored instances.

        Returns:
            Dict mapping instance_id to summary data
        """
        summaries = {}

        try:
            # Iterate through all instance directories
            if not self.storage_path.exists():
                return summaries

            for instance_dir in self.storage_path.iterdir():
                if instance_dir.is_dir():
                    instance_id = instance_dir.name
                    summary = await self.get_summary(instance_id, latest=True)
                    if summary:
                        summaries[instance_id] = summary

        except Exception as e:
            self._logger.error(f"Error getting all summaries: {e}")

        return summaries
