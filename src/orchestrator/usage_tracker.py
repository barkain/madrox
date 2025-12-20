"""Usage tracker for reading actual token usage from Claude Code JSONL files."""

import json
import logging
import re
import threading
import time
from pathlib import Path

from .simple_models import TokenUsage

logger = logging.getLogger(__name__)

# UUID pattern for validation
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


class UsageTracker:
    """Tracks actual token usage by parsing Claude Code's local JSONL files."""

    def __init__(self, config_dir: str = "~/.config/claude"):
        """Initialize the usage tracker.

        Args:
            config_dir: Path to Claude Code's config directory (default: ~/.config/claude)
        """
        self.config_dir = Path(config_dir).expanduser()
        self.instance_sessions: dict[str, Path] = {}
        self.instance_workspaces: dict[str, str] = {}
        self._lock = threading.Lock()
        logger.info(f"UsageTracker initialized with config_dir: {self.config_dir}")

    def register_instance(self, instance_id: str, workspace_dir: str) -> None:
        """Register an instance and discover its session file.

        Args:
            instance_id: Unique instance identifier
            workspace_dir: Path to the instance's workspace directory
        """
        with self._lock:
            # Store workspace for potential retry discovery
            self.instance_workspaces[instance_id] = workspace_dir

            session_file = self._find_session_file(workspace_dir)
            if session_file:
                self.instance_sessions[instance_id] = session_file
                logger.info(f"Registered instance {instance_id} with session file: {session_file}")
            else:
                logger.warning(
                    f"Could not discover session file for instance {instance_id} "
                    f"in workspace {workspace_dir}. JSONL may not exist yet - use retry_session_discovery() after first message."
                )

    def get_session_usage(self, instance_id: str) -> TokenUsage:
        """Get total token usage for an instance's session.

        Args:
            instance_id: Instance identifier

        Returns:
            TokenUsage with aggregated usage across all messages
        """
        with self._lock:
            session_file = self.instance_sessions.get(instance_id)
            if not session_file:
                logger.debug(f"No session file for instance {instance_id}, returning zero usage")
                return TokenUsage()

            try:
                usage_list = self._parse_jsonl(session_file)
                if not usage_list:
                    return TokenUsage()

                # Aggregate all usage
                total_usage = TokenUsage()
                for usage in usage_list:
                    total_usage = total_usage + usage

                return total_usage

            except Exception as e:
                logger.error(f"Error reading session usage for {instance_id}: {e}", exc_info=True)
                return TokenUsage()

    def get_message_usage(self, instance_id: str, message_index: int = -1) -> TokenUsage:
        """Get token usage for a specific message in the session.

        Args:
            instance_id: Instance identifier
            message_index: Index of the message (default: -1 for last message)

        Returns:
            TokenUsage for the specified message
        """
        with self._lock:
            session_file = self.instance_sessions.get(instance_id)
            if not session_file:
                logger.debug(f"No session file for instance {instance_id}, returning zero usage")
                return TokenUsage()

            try:
                usage_list = self._parse_jsonl(session_file)
                if not usage_list:
                    return TokenUsage()

                # Handle negative indices
                if message_index < 0:
                    message_index = len(usage_list) + message_index

                if 0 <= message_index < len(usage_list):
                    return usage_list[message_index]
                else:
                    logger.warning(
                        f"Message index {message_index} out of range for instance {instance_id}"
                    )
                    return TokenUsage()

            except Exception as e:
                logger.error(f"Error reading message usage for {instance_id}: {e}", exc_info=True)
                return TokenUsage()

    def retry_session_discovery(
        self, instance_id: str, max_retries: int = 5, delay: float = 1.0
    ) -> bool:
        """
        Retry session file discovery for instances where JSONL may not exist yet.

        Claude creates the JSONL file after the first message, not at startup.
        This method retries discovery with exponential backoff.

        Args:
            instance_id: The instance ID to retry discovery for
            max_retries: Maximum number of retry attempts
            delay: Seconds to wait between retries

        Returns:
            True if session file was found, False otherwise
        """
        workspace_dir = self.instance_workspaces.get(instance_id)
        if not workspace_dir:
            logger.warning(f"No workspace registered for instance {instance_id}")
            return False

        for attempt in range(max_retries):
            session_file = self._find_session_file(workspace_dir)
            if session_file:
                with self._lock:
                    self.instance_sessions[instance_id] = session_file
                logger.info(
                    f"Session file discovered on attempt {attempt + 1}/{max_retries}: {session_file}"
                )
                return True

            if attempt < max_retries - 1:
                logger.debug(
                    f"Session file not found (attempt {attempt + 1}/{max_retries}), retrying in {delay}s..."
                )
                time.sleep(delay)

        logger.warning(
            f"Session file not found after {max_retries} attempts for instance {instance_id}"
        )
        return False

    def _find_session_file(self, workspace_dir: str) -> Path | None:
        """Find the session JSONL file for a workspace.

        Looks for .madrox_session_id file in workspace, then finds the corresponding
        JSONL file in Claude Code's config directory.

        Args:
            workspace_dir: Path to instance workspace directory

        Returns:
            Path to session JSONL file if found, None otherwise
        """
        try:
            workspace_path = Path(workspace_dir)
            session_id_file = workspace_path / ".madrox_session_id"

            if not session_id_file.exists():
                logger.debug(f"Session ID file not found: {session_id_file}")
                return None

            session_id = session_id_file.read_text().strip()
            if not session_id:
                logger.warning(f"Empty session ID in {session_id_file}")
                return None

            # Validate UUID format
            if not UUID_PATTERN.match(session_id):
                logger.error(f"Invalid UUID format in {session_id_file}: {session_id}")
                return None

            logger.info(f"Read session ID from {session_id_file}: {session_id}")

            # Find the session file in Claude's config directory
            # Pattern: ~/.config/claude/projects/<project>/<session-id>.jsonl
            projects_dir = self.config_dir / "projects"
            if not projects_dir.exists():
                logger.warning(f"Projects directory not found: {projects_dir}")
                return None

            logger.debug(f"Searching for session file in {projects_dir}")

            # Search all project directories for the session file
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    session_file = project_dir / f"{session_id}.jsonl"
                    logger.debug(f"Checking: {session_file}")
                    if session_file.exists():
                        logger.info(f"Found session file: {session_file}")
                        return session_file

            logger.debug(
                f"Session file not found for session ID {session_id} in {projects_dir} "
                f"(JSONL may not exist yet - created after first message)"
            )
            return None

        except PermissionError as e:
            logger.error(
                f"Permission denied reading session file for {workspace_dir}: {e}", exc_info=True
            )
            return None
        except Exception as e:
            logger.error(f"Error finding session file for {workspace_dir}: {e}", exc_info=True)
            return None

    def _parse_jsonl(self, session_file: Path) -> list[TokenUsage]:
        """Parse JSONL file and extract token usage from each entry.

        Args:
            session_file: Path to session JSONL file

        Returns:
            List of TokenUsage objects, one per message
        """
        usage_list = []

        try:
            with open(session_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        usage = self._extract_usage(data)
                        if usage:
                            usage_list.append(usage)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse line {line_num} in {session_file}: {e}")
                        continue

        except FileNotFoundError:
            logger.warning(f"Session file not found: {session_file}")
        except Exception as e:
            logger.error(f"Error parsing JSONL file {session_file}: {e}", exc_info=True)

        return usage_list

    def _extract_usage(self, json_data: dict) -> TokenUsage | None:
        """Extract token usage from a JSONL entry.

        Args:
            json_data: Parsed JSON object from JSONL line

        Returns:
            TokenUsage if usage data found, None otherwise
        """
        try:
            # Navigate to message.usage in the JSON structure
            message = json_data.get("message", {})
            usage = message.get("usage", {})

            if not usage:
                return None

            # Helper to safely convert to int
            def safe_int(value, default=0):
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default

            return TokenUsage(
                input_tokens=safe_int(usage.get("input_tokens", 0)),
                output_tokens=safe_int(usage.get("output_tokens", 0)),
                cache_creation_input_tokens=safe_int(usage.get("cache_creation_input_tokens", 0)),
                cache_read_input_tokens=safe_int(usage.get("cache_read_input_tokens", 0)),
            )

        except Exception as e:
            logger.debug(f"Could not extract usage from JSON data: {e}")
            return None
