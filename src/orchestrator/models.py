"""Models for Claude Orchestrator."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

try:
    from pydantic import BaseModel, Field
except ImportError:
    # Fallback if pydantic not available
    class BaseModel:
        pass

    def Field(*args, **kwargs):
        return None


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


class ClaudeInstance(Base):
    """Database model for Claude instances."""

    __tablename__ = "claude_instances"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    model = Column(String, nullable=False, default="claude-4-sonnet-20250514")
    state = Column(String, nullable=False, default=InstanceState.INITIALIZING.value)

    # Instance configuration
    system_prompt = Column(Text, nullable=True)
    max_tokens = Column(Integer, default=4096)
    temperature = Column(Integer, default=0)  # Store as int (0-100), convert to float

    # Environment and isolation
    workspace_dir = Column(String, nullable=True)
    environment_vars = Column(JSON, nullable=True)
    resource_limits = Column(JSON, nullable=True)

    # Lifecycle tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    last_activity = Column(DateTime, nullable=True)
    terminated_at = Column(DateTime, nullable=True)

    # Communication
    session_id = Column(String, nullable=True)
    message_queue = Column(JSON, nullable=True)  # Pending messages

    # Resource usage tracking
    total_tokens_used = Column(Integer, default=0)
    total_cost = Column(String, default="0.00")  # Store as string for precision
    request_count = Column(Integer, default=0)

    # Parent/child relationships
    parent_instance_id = Column(String, nullable=True)
    spawned_by_instance_id = Column(String, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    health_check_failures = Column(Integer, default=0)

    # Termination
    auto_terminate = Column(Boolean, default=True)
    keep_alive_until = Column(DateTime, nullable=True)


class OrchestratorConfig(BaseModel):
    """Configuration for the Claude Orchestrator."""

    # MCP Server settings
    server_host: str = "localhost"
    server_port: int = 8001

    # Claude API settings
    anthropic_api_key: str
    default_model: str = "claude-4-sonnet-20250514"
    max_concurrent_instances: int = 10

    # Resource limits
    max_tokens_per_instance: int = 100000
    max_total_cost: float = 100.0  # USD
    instance_timeout_minutes: int = 60

    # Environment settings
    workspace_base_dir: str = "/tmp/claude_orchestrator"
    enable_isolation: bool = True

    # Database settings
    database_url: str = "sqlite:///claude_orchestrator.db"

    # Logging and monitoring
    log_level: str = "INFO"
    enable_metrics: bool = True
    metrics_port: int = 9090


class SpawnInstanceRequest(BaseModel):
    """Request to spawn a new Claude instance."""

    name: str = Field(..., description="Human-readable name for the instance")
    role: InstanceRole = Field(InstanceRole.GENERAL, description="Predefined role")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")
    model: str = Field("claude-4-sonnet-20250514", description="Claude model to use")

    # Configuration
    max_tokens: int = Field(4096, description="Max tokens per request")
    temperature: float = Field(0.0, ge=0.0, le=1.0, description="Temperature setting")

    # Environment
    workspace_dir: Optional[str] = Field(None, description="Working directory")
    environment_vars: Dict[str, str] = Field(default_factory=dict)

    # Resource limits
    max_total_tokens: Optional[int] = Field(None, description="Total token limit")
    max_cost: Optional[float] = Field(None, description="Cost limit in USD")
    timeout_minutes: Optional[int] = Field(None, description="Instance timeout")

    # Parent relationship
    parent_instance_id: Optional[str] = Field(None, description="Parent instance ID")


class SendMessageRequest(BaseModel):
    """Request to send message to an instance."""

    instance_id: str = Field(..., description="Target instance ID")
    message: str = Field(..., description="Message to send")

    # Message options
    wait_for_response: bool = Field(True, description="Wait for response")
    timeout_seconds: int = Field(30, description="Response timeout")
    priority: int = Field(0, description="Message priority (higher = urgent)")


class InstanceOutput(BaseModel):
    """Output from a Claude instance."""

    instance_id: str
    response: str
    timestamp: datetime

    # Metadata
    tokens_used: int
    cost: float
    processing_time_ms: int

    # Context
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None


class CoordinationTask(BaseModel):
    """Task for instance coordination."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = Field(..., description="Task description")

    # Participants
    coordinator_id: str = Field(..., description="Coordinating instance ID")
    participant_ids: List[str] = Field(..., description="Participating instance IDs")

    # Execution
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    current_step: int = Field(0)

    # Results
    results: Dict[str, Any] = Field(default_factory=dict)
    status: str = Field("pending")  # pending, running, completed, failed

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class InstanceMetrics(BaseModel):
    """Metrics for an instance."""

    instance_id: str
    state: InstanceState

    # Usage metrics
    total_requests: int
    total_tokens: int
    total_cost: float

    # Performance metrics
    avg_response_time_ms: float
    success_rate: float

    # Resource metrics
    uptime_seconds: int
    last_activity: Optional[datetime]

    # Health metrics
    health_score: float  # 0.0 to 1.0
    error_count: int
    retry_count: int