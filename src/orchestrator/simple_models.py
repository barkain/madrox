"""Simple models for Claude Orchestrator without SQLAlchemy dependency."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any


class MessageStatus(str, Enum):
    """Status of a message in the bidirectional communication protocol."""

    SENT = "sent"
    DELIVERED = "delivered"
    REPLIED = "replied"
    TIMEOUT = "timeout"
    ERROR = "error"


class MessageEnvelope:
    """Lightweight wrapper for tracking message lifecycle in bidirectional communication.

    This is an in-memory only structure (no database persistence) used to correlate
    requests with responses in the asyncio.Queue-based messaging system.
    """

    def __init__(
        self,
        message_id: str,
        sender_id: str,
        recipient_id: str,
        content: str,
        sent_at: datetime,
    ):
        self.message_id = message_id  # UUID for correlation
        self.sender_id = sender_id  # Instance ID or "coordinator"
        self.recipient_id = recipient_id  # Instance ID
        self.content = content  # Original message content
        self.sent_at = sent_at
        self.replied_at: datetime | None = None
        self.reply_content: str | None = None
        self.status: MessageStatus = MessageStatus.SENT

    def mark_delivered(self) -> None:
        """Mark message as delivered to recipient."""
        self.status = MessageStatus.DELIVERED

    def mark_replied(self, reply_content: str, replied_at: datetime | None = None) -> None:
        """Mark message as replied with response content."""
        self.status = MessageStatus.REPLIED
        self.reply_content = reply_content
        self.replied_at = replied_at or datetime.now()

    def mark_timeout(self) -> None:
        """Mark message as timed out (no response received)."""
        self.status = MessageStatus.TIMEOUT

    def mark_error(self) -> None:
        """Mark message as errored during delivery."""
        self.status = MessageStatus.ERROR

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "content": self.content,
            "sent_at": self.sent_at.isoformat(),
            "replied_at": self.replied_at.isoformat() if self.replied_at else None,
            "reply_content": self.reply_content,
            "status": self.status.value,
        }


class InstanceState(str, Enum):
    """State of a Claude instance."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    TERMINATED = "terminated"


class InstanceRole(str, Enum):
    """Predefined roles for Claude instances."""

    GENERAL = "general"
    FRONTEND_DEVELOPER = "frontend_developer"
    BACKEND_DEVELOPER = "backend_developer"
    TESTING_SPECIALIST = "testing_specialist"
    DOCUMENTATION_WRITER = "documentation_writer"
    CODE_REVIEWER = "code_reviewer"
    ARCHITECT = "architect"
    DEBUGGER = "debugger"
    SECURITY_ANALYST = "security_analyst"
    DATA_ANALYST = "data_analyst"


class SpawnInstanceRequest:
    """Request to spawn a new Claude instance."""

    def __init__(
        self,
        name: str,
        role: InstanceRole = InstanceRole.GENERAL,
        system_prompt: str | None = None,
        model: str = "claude-4-sonnet-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        workspace_dir: str | None = None,
        environment_vars: dict[str, str] | None = None,
        max_total_tokens: int | None = None,
        max_cost: float | None = None,
        timeout_minutes: int | None = None,
        parent_instance_id: str | None = None,
    ):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.workspace_dir = workspace_dir
        self.environment_vars = environment_vars or {}
        self.max_total_tokens = max_total_tokens
        self.max_cost = max_cost
        self.timeout_minutes = timeout_minutes
        self.parent_instance_id = parent_instance_id


class SendMessageRequest:
    """Request to send message to an instance."""

    def __init__(
        self,
        instance_id: str,
        message: str,
        wait_for_response: bool = True,
        timeout_seconds: int = 30,
        priority: int = 0,
    ):
        self.instance_id = instance_id
        self.message = message
        self.wait_for_response = wait_for_response
        self.timeout_seconds = timeout_seconds
        self.priority = priority


class InstanceOutput:
    """Output from a Claude instance."""

    def __init__(
        self,
        instance_id: str,
        response: str,
        timestamp: datetime,
        tokens_used: int,
        cost: float,
        processing_time_ms: int,
        conversation_id: str | None = None,
        message_id: str | None = None,
    ):
        self.instance_id = instance_id
        self.response = response
        self.timestamp = timestamp
        self.tokens_used = tokens_used
        self.cost = cost
        self.processing_time_ms = processing_time_ms
        self.conversation_id = conversation_id
        self.message_id = message_id


class CoordinationTask:
    """Task for instance coordination."""

    def __init__(
        self,
        description: str,
        coordinator_id: str,
        participant_ids: list[str],
        coordination_type: str = "sequential",
    ):
        self.task_id = str(uuid.uuid4())
        self.description = description
        self.coordinator_id = coordinator_id
        self.participant_ids = participant_ids
        self.coordination_type = coordination_type
        self.steps: list[dict[str, Any]] = []
        self.current_step = 0
        self.results: dict[str, Any] = {}
        self.status = "pending"
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None


class InstanceMetrics:
    """Metrics for an instance."""

    def __init__(
        self,
        instance_id: str,
        state: InstanceState,
        total_requests: int,
        total_tokens: int,
        total_cost: float,
        avg_response_time_ms: float,
        success_rate: float,
        uptime_seconds: int,
        last_activity: datetime | None,
        health_score: float,
        error_count: int,
        retry_count: int,
    ):
        self.instance_id = instance_id
        self.state = state
        self.total_requests = total_requests
        self.total_tokens = total_tokens
        self.total_cost = total_cost
        self.avg_response_time_ms = avg_response_time_ms
        self.success_rate = success_rate
        self.uptime_seconds = uptime_seconds
        self.last_activity = last_activity
        self.health_score = health_score
        self.error_count = error_count
        self.retry_count = retry_count


class OrchestratorConfig:
    """Configuration for the Claude Orchestrator."""

    def __init__(
        self,
        server_host: str = "localhost",
        server_port: int = 8001,
        anthropic_api_key: str = "",
        default_model: str = "claude-4-sonnet-20250514",
        max_concurrent_instances: int = 10,
        max_tokens_per_instance: int = 100000,
        max_total_cost: float = 100.0,
        instance_timeout_minutes: int = 60,
        workspace_base_dir: str = "/tmp/claude_orchestrator",
        enable_isolation: bool = True,
        database_url: str = "sqlite:///claude_orchestrator.db",
        log_dir: str = "/tmp/madrox_logs",
        log_level: str = "INFO",
        enable_metrics: bool = True,
        metrics_port: int = 9090,
        artifacts_dir: str = "/tmp/madrox_logs/artifacts",
        preserve_artifacts: bool = True,
    ):
        self.server_host = server_host
        self.server_port = server_port
        self.anthropic_api_key = anthropic_api_key
        self.default_model = default_model
        self.max_concurrent_instances = max_concurrent_instances
        self.max_tokens_per_instance = max_tokens_per_instance
        self.max_total_cost = max_total_cost
        self.instance_timeout_minutes = instance_timeout_minutes
        self.workspace_base_dir = workspace_base_dir
        self.enable_isolation = enable_isolation
        self.database_url = database_url
        self.log_dir = log_dir
        self.log_level = log_level
        self.enable_metrics = enable_metrics
        self.metrics_port = metrics_port
        self.artifacts_dir = artifacts_dir
        self.preserve_artifacts = preserve_artifacts

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict representation suitable for consumers.

        This mirrors pydantic's model_dump used elsewhere but avoids the dependency.
        """
        return {
            "server_host": self.server_host,
            "server_port": self.server_port,
            "anthropic_api_key": self.anthropic_api_key,
            "default_model": self.default_model,
            "max_concurrent_instances": self.max_concurrent_instances,
            "max_tokens_per_instance": self.max_tokens_per_instance,
            "max_total_cost": self.max_total_cost,
            "instance_timeout_minutes": self.instance_timeout_minutes,
            "workspace_base_dir": self.workspace_base_dir,
            "enable_isolation": self.enable_isolation,
            "database_url": self.database_url,
            "log_level": self.log_level,
            "enable_metrics": self.enable_metrics,
            "metrics_port": self.metrics_port,
            "artifacts_dir": self.artifacts_dir,
            "preserve_artifacts": self.preserve_artifacts,
        }
