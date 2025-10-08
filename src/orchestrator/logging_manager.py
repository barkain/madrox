"""Structured logging manager for Claude Orchestrator.

Provides per-instance logging, audit trails, and log aggregation capabilities.
"""

import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Any


class InstanceLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds instance context to all log messages."""

    def process(self, msg, kwargs):
        """Add instance_id to log messages."""
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


class LoggingManager:
    """Manages structured logging for orchestrator and instances."""

    def __init__(self, log_dir: str | Path = "/tmp/madrox_logs", log_level: str = "INFO"):
        """Initialize logging manager.

        Args:
            log_dir: Base directory for all logs
            log_level: Default log level
        """
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper())

        # Create directory structure
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.instances_dir = self.log_dir / "instances"
        self.instances_dir.mkdir(exist_ok=True)
        self.audit_dir = self.log_dir / "audit"
        self.audit_dir.mkdir(exist_ok=True)

        # Instance loggers cache
        self._instance_loggers: dict[str, InstanceLoggerAdapter] = {}

        # Setup orchestrator logger
        self._setup_orchestrator_logger()

        # Setup audit logger
        self._setup_audit_logger()

    def _setup_orchestrator_logger(self):
        """Setup main orchestrator logger with file and console handlers."""
        logger = logging.getLogger("orchestrator")
        logger.setLevel(self.log_level)
        logger.propagate = False  # Don't propagate to root

        # Remove existing handlers
        logger.handlers.clear()

        # Console handler - human readable
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # File handler - structured JSON
        log_file = self.log_dir / "orchestrator.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(logging.DEBUG)  # Capture everything to file
        file_formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", '
            '"message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s", '
            '"line": %(lineno)d%(extras)s}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

        # Custom filter to add extra fields as JSON
        class JsonExtraFilter(logging.Filter):
            def filter(self, record):
                extras = {}
                # Collect all extra attributes
                for key, value in record.__dict__.items():
                    if key not in [
                        "name",
                        "msg",
                        "args",
                        "created",
                        "filename",
                        "funcName",
                        "levelname",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "message",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "exc_info",
                        "exc_text",
                        "stack_info",
                        "asctime",
                        "taskName",
                    ]:
                        try:
                            json.dumps(value)  # Ensure serializable
                            extras[key] = value
                        except (TypeError, ValueError):
                            extras[key] = str(value)

                if extras:
                    record.extras = ", " + ", ".join(
                        f'"{k}": {json.dumps(v)}' for k, v in extras.items()
                    )
                else:
                    record.extras = ""
                return True

        file_handler.addFilter(JsonExtraFilter())
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        self.orchestrator_logger = logger

    def _setup_audit_logger(self):
        """Setup audit trail logger (JSON Lines format)."""
        logger = logging.getLogger("orchestrator.audit")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        # Remove existing handlers
        logger.handlers.clear()

        # Audit file - JSONL format, daily rotation
        audit_file = self.audit_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        file_handler = logging.handlers.TimedRotatingFileHandler(
            audit_file,
            when="midnight",
            interval=1,
            backupCount=30,  # Keep 30 days
        )
        file_handler.setLevel(logging.INFO)

        # JSONL formatter - one JSON object per line
        class JsonLineFormatter(logging.Formatter):
            def format(self, record):
                log_obj = {
                    "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                    "level": record.levelname,
                    "event": record.getMessage(),
                    "logger": record.name,
                }

                # Add all extra fields
                for key, value in record.__dict__.items():
                    if key not in [
                        "name",
                        "msg",
                        "args",
                        "created",
                        "filename",
                        "funcName",
                        "levelname",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "message",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "exc_info",
                        "exc_text",
                        "stack_info",
                        "asctime",
                        "taskName",
                    ]:
                        try:
                            json.dumps(value)  # Ensure serializable
                            log_obj[key] = value
                        except (TypeError, ValueError):
                            log_obj[key] = str(value)

                return json.dumps(log_obj)

        file_handler.setFormatter(JsonLineFormatter())
        logger.addHandler(file_handler)

        self.audit_logger = logger

    def get_instance_logger(
        self, instance_id: str, instance_name: str = None
    ) -> InstanceLoggerAdapter:
        """Get or create a logger for a specific instance.

        Args:
            instance_id: Unique instance identifier
            instance_name: Human-readable instance name

        Returns:
            Logger adapter with instance context
        """
        if instance_id in self._instance_loggers:
            return self._instance_loggers[instance_id]

        # Create instance-specific directory
        instance_dir = self.instances_dir / instance_id
        instance_dir.mkdir(exist_ok=True)

        # Create instance logger
        logger = logging.getLogger(f"instance.{instance_id}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # Remove existing handlers
        logger.handlers.clear()

        # Instance lifecycle log
        lifecycle_file = instance_dir / "instance.log"
        lifecycle_handler = logging.handlers.RotatingFileHandler(
            lifecycle_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
        )
        lifecycle_handler.setLevel(logging.DEBUG)
        lifecycle_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        lifecycle_handler.setFormatter(lifecycle_formatter)
        logger.addHandler(lifecycle_handler)

        # Communication log (structured JSONL)
        comm_file = instance_dir / "communication.jsonl"
        comm_handler = logging.FileHandler(comm_file)
        comm_handler.setLevel(logging.DEBUG)

        class CommJsonLineFormatter(logging.Formatter):
            def format(self, record):
                log_obj = {
                    "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                    "event_type": getattr(record, "event_type", "unknown"),
                    "message": record.getMessage(),
                }

                # Add communication-specific fields
                for key in [
                    "message_id",
                    "direction",
                    "content",
                    "tokens",
                    "cost",
                    "response_time",
                ]:
                    if hasattr(record, key):
                        log_obj[key] = getattr(record, key)

                return json.dumps(log_obj)

        comm_handler.setFormatter(CommJsonLineFormatter())
        logger.addHandler(comm_handler)

        # Create metadata file
        metadata_file = instance_dir / "metadata.json"
        metadata = {
            "instance_id": instance_id,
            "instance_name": instance_name,
            "created_at": datetime.now().isoformat(),
            "log_directory": str(instance_dir),
        }
        metadata_file.write_text(json.dumps(metadata, indent=2))

        # Create adapter with context
        adapter = InstanceLoggerAdapter(
            logger, {"instance_id": instance_id, "instance_name": instance_name}
        )

        self._instance_loggers[instance_id] = adapter
        return adapter

    def log_audit_event(
        self,
        event_type: str,
        instance_id: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        """Log an audit event.

        Args:
            event_type: Type of event (spawn, terminate, message, etc.)
            instance_id: Related instance ID if applicable
            details: Additional event details
            **kwargs: Additional fields to include
        """
        extra = {
            "event_type": event_type,
            "instance_id": instance_id,
            "details": details or {},
        }
        extra.update(kwargs)

        self.audit_logger.info(event_type, extra=extra)

    def log_tmux_output(self, instance_id: str, output: str):
        """Log raw tmux pane output for debugging.

        Args:
            instance_id: Instance ID
            output: Raw tmux output
        """
        instance_dir = self.instances_dir / instance_id
        if not instance_dir.exists():
            instance_dir.mkdir(parents=True, exist_ok=True)

        tmux_log = instance_dir / "tmux_output.log"

        # Append with timestamp
        with tmux_log.open("a") as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"[{datetime.now().isoformat()}]\n")
            f.write(f"{'=' * 80}\n")
            f.write(output)
            f.write("\n")

    def get_instance_logs(
        self, instance_id: str, log_type: str = "instance", tail: int = 100
    ) -> list[str]:
        """Retrieve logs for an instance.

        Args:
            instance_id: Instance ID
            log_type: Type of log (instance, communication, tmux_output)
            tail: Number of recent lines to return

        Returns:
            List of log lines
        """
        instance_dir = self.instances_dir / instance_id
        if not instance_dir.exists():
            return []

        log_files = {
            "instance": "instance.log",
            "communication": "communication.jsonl",
            "tmux_output": "tmux_output.log",
        }

        log_file = instance_dir / log_files.get(log_type, "instance.log")
        if not log_file.exists():
            return []

        try:
            with log_file.open("r") as f:
                lines = f.readlines()
                return lines[-tail:] if tail else lines
        except Exception as e:
            self.orchestrator_logger.error(f"Failed to read logs for {instance_id}: {e}")
            return []

    def get_all_instance_ids(self) -> list[str]:
        """Get all instance IDs that have logs.

        Returns:
            List of instance IDs
        """
        return [d.name for d in self.instances_dir.iterdir() if d.is_dir()]

    def cleanup_instance_logs(self, instance_id: str):
        """Remove logs for a terminated instance.

        Args:
            instance_id: Instance ID to cleanup
        """
        instance_dir = self.instances_dir / instance_id
        if instance_dir.exists():
            import shutil

            try:
                shutil.rmtree(instance_dir)
                self.orchestrator_logger.info(f"Cleaned up logs for instance {instance_id}")
            except Exception as e:
                self.orchestrator_logger.error(f"Failed to cleanup logs for {instance_id}: {e}")

        # Remove from cache
        if instance_id in self._instance_loggers:
            del self._instance_loggers[instance_id]
