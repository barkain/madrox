"""Unit tests for simple_models.py - Simple data models without SQLAlchemy dependency."""

import uuid
from datetime import datetime

import pytest

from src.orchestrator.simple_models import (
    CoordinationTask,
    InstanceMetrics,
    InstanceOutput,
    InstanceRole,
    InstanceState,
    MessageEnvelope,
    MessageStatus,
    OrchestratorConfig,
    SendMessageRequest,
    SpawnInstanceRequest,
)


class TestMessageStatus:
    """Test MessageStatus enum."""

    def test_all_status_values_exist(self):
        """Verify all expected status values are defined."""
        assert MessageStatus.SENT == "sent"
        assert MessageStatus.DELIVERED == "delivered"
        assert MessageStatus.REPLIED == "replied"
        assert MessageStatus.TIMEOUT == "timeout"
        assert MessageStatus.ERROR == "error"

    def test_status_is_string_enum(self):
        """Verify MessageStatus inherits from str and Enum."""
        assert isinstance(MessageStatus.SENT, str)
        assert MessageStatus.SENT.value == "sent"

    def test_all_members_count(self):
        """Verify the enum has exactly 5 members."""
        assert len(MessageStatus) == 5


class TestMessageEnvelope:
    """Test MessageEnvelope class."""

    @pytest.fixture
    def sample_envelope(self) -> MessageEnvelope:
        """Create a sample MessageEnvelope for testing."""
        return MessageEnvelope(
            message_id="msg-123",
            sender_id="instance-sender",
            recipient_id="instance-recipient",
            content="Test message content",
            sent_at=datetime(2025, 1, 15, 10, 30, 0),
        )

    def test_initialization(self, sample_envelope):
        """Test MessageEnvelope initialization."""
        assert sample_envelope.message_id == "msg-123"
        assert sample_envelope.sender_id == "instance-sender"
        assert sample_envelope.recipient_id == "instance-recipient"
        assert sample_envelope.content == "Test message content"
        assert sample_envelope.sent_at == datetime(2025, 1, 15, 10, 30, 0)
        assert sample_envelope.replied_at is None
        assert sample_envelope.reply_content is None
        assert sample_envelope.status == MessageStatus.SENT

    def test_mark_delivered(self, sample_envelope):
        """Test marking message as delivered."""
        sample_envelope.mark_delivered()
        assert sample_envelope.status == MessageStatus.DELIVERED

    def test_mark_replied_with_custom_timestamp(self, sample_envelope):
        """Test marking message as replied with custom timestamp."""
        reply_time = datetime(2025, 1, 15, 10, 31, 0)
        sample_envelope.mark_replied("Reply content here", replied_at=reply_time)

        assert sample_envelope.status == MessageStatus.REPLIED
        assert sample_envelope.reply_content == "Reply content here"
        assert sample_envelope.replied_at == reply_time

    def test_mark_replied_with_auto_timestamp(self, sample_envelope):
        """Test marking message as replied with auto-generated timestamp."""
        before = datetime.now()
        sample_envelope.mark_replied("Auto timestamp reply")
        after = datetime.now()

        assert sample_envelope.status == MessageStatus.REPLIED
        assert sample_envelope.reply_content == "Auto timestamp reply"
        assert sample_envelope.replied_at is not None
        assert before <= sample_envelope.replied_at <= after

    def test_mark_timeout(self, sample_envelope):
        """Test marking message as timed out."""
        sample_envelope.mark_timeout()
        assert sample_envelope.status == MessageStatus.TIMEOUT

    def test_mark_error(self, sample_envelope):
        """Test marking message as errored."""
        sample_envelope.mark_error()
        assert sample_envelope.status == MessageStatus.ERROR

    def test_to_dict_without_reply(self, sample_envelope):
        """Test to_dict conversion without reply."""
        result = sample_envelope.to_dict()

        assert result["message_id"] == "msg-123"
        assert result["sender_id"] == "instance-sender"
        assert result["recipient_id"] == "instance-recipient"
        assert result["content"] == "Test message content"
        assert result["sent_at"] == "2025-01-15T10:30:00"
        assert result["replied_at"] is None
        assert result["reply_content"] is None
        assert result["status"] == "sent"

    def test_to_dict_with_reply(self, sample_envelope):
        """Test to_dict conversion with reply."""
        reply_time = datetime(2025, 1, 15, 10, 31, 30)
        sample_envelope.mark_replied("Test reply", replied_at=reply_time)
        result = sample_envelope.to_dict()

        assert result["replied_at"] == "2025-01-15T10:31:30"
        assert result["reply_content"] == "Test reply"
        assert result["status"] == "replied"

    def test_state_transitions(self, sample_envelope):
        """Test various state transitions."""
        # SENT -> DELIVERED -> REPLIED
        assert sample_envelope.status == MessageStatus.SENT
        sample_envelope.mark_delivered()
        assert sample_envelope.status == MessageStatus.DELIVERED
        sample_envelope.mark_replied("Final reply")
        assert sample_envelope.status == MessageStatus.REPLIED

    def test_error_state_transition(self):
        """Test transitioning to error state."""
        envelope = MessageEnvelope(
            message_id="err-msg",
            sender_id="sender",
            recipient_id="recipient",
            content="Error test",
            sent_at=datetime.now(),
        )
        envelope.mark_error()
        assert envelope.status == MessageStatus.ERROR

    def test_empty_content(self):
        """Test envelope with empty content."""
        envelope = MessageEnvelope(
            message_id="empty",
            sender_id="sender",
            recipient_id="recipient",
            content="",
            sent_at=datetime.now(),
        )
        assert envelope.content == ""
        assert envelope.status == MessageStatus.SENT


class TestInstanceState:
    """Test InstanceState enum."""

    def test_all_state_values_exist(self):
        """Verify all expected state values are defined."""
        assert InstanceState.INITIALIZING == "initializing"
        assert InstanceState.RUNNING == "running"
        assert InstanceState.IDLE == "idle"
        assert InstanceState.BUSY == "busy"
        assert InstanceState.ERROR == "error"
        assert InstanceState.TERMINATED == "terminated"

    def test_state_is_string_enum(self):
        """Verify InstanceState inherits from str."""
        assert isinstance(InstanceState.RUNNING, str)

    def test_all_members_count(self):
        """Verify the enum has exactly 6 members."""
        assert len(InstanceState) == 6


class TestInstanceRole:
    """Test InstanceRole enum."""

    def test_all_role_values_exist(self):
        """Verify all expected role values are defined."""
        expected_roles = {
            "GENERAL": "general",
            "FRONTEND_DEVELOPER": "frontend_developer",
            "BACKEND_DEVELOPER": "backend_developer",
            "TESTING_SPECIALIST": "testing_specialist",
            "DOCUMENTATION_WRITER": "documentation_writer",
            "CODE_REVIEWER": "code_reviewer",
            "ARCHITECT": "architect",
            "DEBUGGER": "debugger",
            "SECURITY_ANALYST": "security_analyst",
            "DATA_ANALYST": "data_analyst",
        }

        for role_name, role_value in expected_roles.items():
            assert getattr(InstanceRole, role_name).value == role_value

    def test_role_is_string_enum(self):
        """Verify InstanceRole inherits from str."""
        assert isinstance(InstanceRole.GENERAL, str)

    def test_all_members_count(self):
        """Verify the enum has exactly 10 members."""
        assert len(InstanceRole) == 10


class TestSpawnInstanceRequest:
    """Test SpawnInstanceRequest class."""

    def test_initialization_with_defaults(self):
        """Test initialization with only required parameters."""
        request = SpawnInstanceRequest(name="test-instance")

        assert request.name == "test-instance"
        assert request.role == InstanceRole.GENERAL
        assert request.system_prompt is None
        assert request.model == "claude-4-sonnet-20250514"
        assert request.max_tokens == 4096
        assert request.temperature == 0.0
        assert request.workspace_dir is None
        assert request.environment_vars == {}
        assert request.max_total_tokens is None
        assert request.timeout_minutes is None
        assert request.parent_instance_id is None

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters provided."""
        env_vars = {"API_KEY": "test-key", "ENV": "production"}
        request = SpawnInstanceRequest(
            name="full-instance",
            role=InstanceRole.BACKEND_DEVELOPER,
            system_prompt="Custom system prompt",
            model="claude-opus-4",
            max_tokens=8192,
            temperature=0.5,
            workspace_dir="/tmp/workspace",
            environment_vars=env_vars,
            max_total_tokens=200000,
            timeout_minutes=120,
            parent_instance_id="parent-123",
        )

        assert request.name == "full-instance"
        assert request.role == InstanceRole.BACKEND_DEVELOPER
        assert request.system_prompt == "Custom system prompt"
        assert request.model == "claude-opus-4"
        assert request.max_tokens == 8192
        assert request.temperature == 0.5
        assert request.workspace_dir == "/tmp/workspace"
        assert request.environment_vars == env_vars
        assert request.max_total_tokens == 200000
        assert request.timeout_minutes == 120
        assert request.parent_instance_id == "parent-123"

    def test_environment_vars_default_to_empty_dict(self):
        """Test that environment_vars defaults to empty dict, not None."""
        request = SpawnInstanceRequest(name="test")
        assert request.environment_vars == {}
        assert isinstance(request.environment_vars, dict)

    def test_various_roles(self):
        """Test instantiation with different roles."""
        roles = [
            InstanceRole.FRONTEND_DEVELOPER,
            InstanceRole.TESTING_SPECIALIST,
            InstanceRole.SECURITY_ANALYST,
        ]

        for role in roles:
            request = SpawnInstanceRequest(name=f"test-{role.value}", role=role)
            assert request.role == role


class TestSendMessageRequest:
    """Test SendMessageRequest class."""

    def test_initialization_with_defaults(self):
        """Test initialization with default parameters."""
        request = SendMessageRequest(
            instance_id="instance-123",
            message="Test message",
        )

        assert request.instance_id == "instance-123"
        assert request.message == "Test message"
        assert request.wait_for_response is True
        assert request.timeout_seconds == 30
        assert request.priority == 0

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters provided."""
        request = SendMessageRequest(
            instance_id="instance-456",
            message="Urgent message",
            wait_for_response=False,
            timeout_seconds=60,
            priority=10,
        )

        assert request.instance_id == "instance-456"
        assert request.message == "Urgent message"
        assert request.wait_for_response is False
        assert request.timeout_seconds == 60
        assert request.priority == 10

    def test_empty_message(self):
        """Test with empty message string."""
        request = SendMessageRequest(instance_id="test", message="")
        assert request.message == ""

    def test_negative_priority(self):
        """Test with negative priority value."""
        request = SendMessageRequest(instance_id="test", message="Low priority", priority=-5)
        assert request.priority == -5


class TestInstanceOutput:
    """Test InstanceOutput class."""

    def test_initialization_with_required_parameters(self):
        """Test initialization with required parameters only."""
        timestamp = datetime(2025, 1, 15, 14, 30, 0)
        output = InstanceOutput(
            instance_id="instance-789",
            response="Test response",
            timestamp=timestamp,
            tokens_used=150,
            processing_time_ms=1200,
        )

        assert output.instance_id == "instance-789"
        assert output.response == "Test response"
        assert output.timestamp == timestamp
        assert output.tokens_used == 150
        assert output.processing_time_ms == 1200
        assert output.conversation_id is None
        assert output.message_id is None

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters."""
        timestamp = datetime(2025, 1, 15, 14, 30, 0)
        output = InstanceOutput(
            instance_id="instance-789",
            response="Complete response",
            timestamp=timestamp,
            tokens_used=250,
            processing_time_ms=2500,
            conversation_id="conv-abc",
            message_id="msg-xyz",
        )

        assert output.conversation_id == "conv-abc"
        assert output.message_id == "msg-xyz"

    def test_zero_tokens_and_time(self):
        """Test with zero tokens and processing time."""
        output = InstanceOutput(
            instance_id="test",
            response="Quick response",
            timestamp=datetime.now(),
            tokens_used=0,
            processing_time_ms=0,
        )
        assert output.tokens_used == 0
        assert output.processing_time_ms == 0

    def test_large_values(self):
        """Test with large token counts and processing times."""
        output = InstanceOutput(
            instance_id="test",
            response="Long response",
            timestamp=datetime.now(),
            tokens_used=100000,
            processing_time_ms=300000,  # 5 minutes
        )
        assert output.tokens_used == 100000
        assert output.processing_time_ms == 300000


class TestCoordinationTask:
    """Test CoordinationTask class."""

    def test_initialization_with_defaults(self):
        """Test initialization with default coordination type."""
        task = CoordinationTask(
            description="Test coordination task",
            coordinator_id="coord-123",
            participant_ids=["instance-1", "instance-2"],
        )

        assert task.description == "Test coordination task"
        assert task.coordinator_id == "coord-123"
        assert task.participant_ids == ["instance-1", "instance-2"]
        assert task.coordination_type == "sequential"
        assert task.steps == []
        assert task.current_step == 0
        assert task.results == {}
        assert task.status == "pending"
        assert task.started_at is None
        assert task.completed_at is None
        # Verify task_id is a valid UUID
        assert uuid.UUID(task.task_id)

    def test_initialization_with_custom_coordination_type(self):
        """Test initialization with custom coordination type."""
        task = CoordinationTask(
            description="Parallel task",
            coordinator_id="coord-456",
            participant_ids=["instance-3", "instance-4", "instance-5"],
            coordination_type="parallel",
        )

        assert task.coordination_type == "parallel"
        assert len(task.participant_ids) == 3

    def test_task_id_is_unique(self):
        """Test that each task gets a unique task_id."""
        task1 = CoordinationTask(
            description="Task 1",
            coordinator_id="coord",
            participant_ids=["p1"],
        )
        task2 = CoordinationTask(
            description="Task 2",
            coordinator_id="coord",
            participant_ids=["p1"],
        )

        assert task1.task_id != task2.task_id
        # Both should be valid UUIDs
        uuid.UUID(task1.task_id)
        uuid.UUID(task2.task_id)

    def test_empty_participant_list(self):
        """Test with empty participant list."""
        task = CoordinationTask(
            description="Solo task",
            coordinator_id="coord",
            participant_ids=[],
        )
        assert task.participant_ids == []

    def test_single_participant(self):
        """Test with single participant."""
        task = CoordinationTask(
            description="Single task",
            coordinator_id="coord",
            participant_ids=["instance-1"],
        )
        assert len(task.participant_ids) == 1


class TestInstanceMetrics:
    """Test InstanceMetrics class."""

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters."""
        last_activity = datetime(2025, 1, 15, 15, 0, 0)
        metrics = InstanceMetrics(
            instance_id="metrics-instance",
            state=InstanceState.RUNNING,
            total_requests=100,
            total_tokens=50000,
            avg_response_time_ms=1500.5,
            success_rate=0.95,
            uptime_seconds=3600,
            last_activity=last_activity,
            health_score=0.92,
            error_count=5,
            retry_count=2,
        )

        assert metrics.instance_id == "metrics-instance"
        assert metrics.state == InstanceState.RUNNING
        assert metrics.total_requests == 100
        assert metrics.total_tokens == 50000
        assert metrics.avg_response_time_ms == 1500.5
        assert metrics.success_rate == 0.95
        assert metrics.uptime_seconds == 3600
        assert metrics.last_activity == last_activity
        assert metrics.health_score == 0.92
        assert metrics.error_count == 5
        assert metrics.retry_count == 2

    def test_metrics_with_none_last_activity(self):
        """Test metrics with None last_activity."""
        metrics = InstanceMetrics(
            instance_id="new-instance",
            state=InstanceState.INITIALIZING,
            total_requests=0,
            total_tokens=0,
            avg_response_time_ms=0.0,
            success_rate=0.0,
            uptime_seconds=0,
            last_activity=None,
            health_score=1.0,
            error_count=0,
            retry_count=0,
        )

        assert metrics.last_activity is None
        assert metrics.total_requests == 0
        assert metrics.health_score == 1.0

    def test_metrics_with_different_states(self):
        """Test metrics with various instance states."""
        states = [
            InstanceState.IDLE,
            InstanceState.BUSY,
            InstanceState.ERROR,
            InstanceState.TERMINATED,
        ]

        for state in states:
            metrics = InstanceMetrics(
                instance_id=f"instance-{state.value}",
                state=state,
                total_requests=10,
                total_tokens=1000,
                avg_response_time_ms=100.0,
                success_rate=0.8,
                uptime_seconds=600,
                last_activity=datetime.now(),
                health_score=0.5,
                error_count=2,
                retry_count=1,
            )
            assert metrics.state == state

    def test_metrics_with_high_error_count(self):
        """Test metrics with high error count."""
        metrics = InstanceMetrics(
            instance_id="error-prone",
            state=InstanceState.ERROR,
            total_requests=1000,
            total_tokens=10000,
            avg_response_time_ms=2000.0,
            success_rate=0.50,
            uptime_seconds=7200,
            last_activity=datetime.now(),
            health_score=0.3,
            error_count=500,
            retry_count=250,
        )

        assert metrics.error_count == 500
        assert metrics.retry_count == 250
        assert metrics.success_rate == 0.50
        assert metrics.health_score == 0.3

    def test_metrics_perfect_performance(self):
        """Test metrics with perfect performance."""
        metrics = InstanceMetrics(
            instance_id="perfect-instance",
            state=InstanceState.RUNNING,
            total_requests=1000,
            total_tokens=50000,
            avg_response_time_ms=50.0,
            success_rate=1.0,
            uptime_seconds=86400,  # 24 hours
            last_activity=datetime.now(),
            health_score=1.0,
            error_count=0,
            retry_count=0,
        )

        assert metrics.success_rate == 1.0
        assert metrics.health_score == 1.0
        assert metrics.error_count == 0
        assert metrics.retry_count == 0


class TestOrchestratorConfig:
    """Test OrchestratorConfig class."""

    def test_initialization_with_defaults(self):
        """Test initialization with default parameters."""
        config = OrchestratorConfig()

        assert config.server_host == "localhost"
        assert config.server_port == 8001
        assert config.anthropic_api_key == ""
        assert config.default_model == "claude-4-sonnet-20250514"
        assert config.max_concurrent_instances == 10
        assert config.max_tokens_per_instance == 100000
        assert config.instance_timeout_minutes == 60
        assert config.workspace_base_dir == "/tmp/claude_orchestrator"
        assert config.enable_isolation is True
        assert config.database_url == "sqlite:///claude_orchestrator.db"
        assert config.log_dir == "/tmp/madrox_logs"
        assert config.log_level == "INFO"
        assert config.enable_metrics is True
        assert config.metrics_port == 9090
        assert config.artifacts_dir == "/tmp/madrox_logs/artifacts"
        assert config.preserve_artifacts is True

    def test_initialization_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        config = OrchestratorConfig(
            server_host="0.0.0.0",
            server_port=9000,
            anthropic_api_key="sk-test-key-123",
            default_model="claude-opus-4",
            max_concurrent_instances=50,
            max_tokens_per_instance=200000,
            instance_timeout_minutes=120,
            workspace_base_dir="/custom/workspace",
            enable_isolation=False,
            database_url="postgresql://localhost/madrox",
            log_dir="/var/log/madrox",
            log_level="DEBUG",
            enable_metrics=False,
            metrics_port=8080,
            artifacts_dir="/var/artifacts",
            preserve_artifacts=False,
        )

        assert config.server_host == "0.0.0.0"
        assert config.server_port == 9000
        assert config.anthropic_api_key == "sk-test-key-123"
        assert config.default_model == "claude-opus-4"
        assert config.max_concurrent_instances == 50
        assert config.max_tokens_per_instance == 200000
        assert config.instance_timeout_minutes == 120
        assert config.workspace_base_dir == "/custom/workspace"
        assert config.enable_isolation is False
        assert config.database_url == "postgresql://localhost/madrox"
        assert config.log_dir == "/var/log/madrox"
        assert config.log_level == "DEBUG"
        assert config.enable_metrics is False
        assert config.metrics_port == 8080
        assert config.artifacts_dir == "/var/artifacts"
        assert config.preserve_artifacts is False

    def test_to_dict_with_defaults(self):
        """Test to_dict method with default configuration."""
        config = OrchestratorConfig()
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["server_host"] == "localhost"
        assert config_dict["server_port"] == 8001
        assert config_dict["anthropic_api_key"] == ""
        assert config_dict["default_model"] == "claude-4-sonnet-20250514"
        assert config_dict["max_concurrent_instances"] == 10
        assert config_dict["max_tokens_per_instance"] == 100000
        assert config_dict["instance_timeout_minutes"] == 60
        assert config_dict["workspace_base_dir"] == "/tmp/claude_orchestrator"
        assert config_dict["enable_isolation"] is True
        assert config_dict["database_url"] == "sqlite:///claude_orchestrator.db"
        assert config_dict["log_level"] == "INFO"
        assert config_dict["enable_metrics"] is True
        assert config_dict["metrics_port"] == 9090
        assert config_dict["artifacts_dir"] == "/tmp/madrox_logs/artifacts"
        assert config_dict["preserve_artifacts"] is True
        # Note: log_dir is not in to_dict output based on the source code

    def test_to_dict_with_custom_values(self):
        """Test to_dict method with custom configuration."""
        config = OrchestratorConfig(
            server_host="custom-host",
            server_port=7777,
            anthropic_api_key="custom-key",
            log_level="WARNING",
        )
        config_dict = config.to_dict()

        assert config_dict["server_host"] == "custom-host"
        assert config_dict["server_port"] == 7777
        assert config_dict["anthropic_api_key"] == "custom-key"
        assert config_dict["log_level"] == "WARNING"

    def test_to_dict_excludes_log_dir(self):
        """Test that to_dict does not include log_dir."""
        config = OrchestratorConfig(log_dir="/custom/logs")
        config_dict = config.to_dict()

        # log_dir is not in the to_dict output based on source
        assert "log_dir" not in config_dict
        # But the attribute exists on the object
        assert config.log_dir == "/custom/logs"

    def test_config_with_various_log_levels(self):
        """Test configuration with different log levels."""
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in log_levels:
            config = OrchestratorConfig(log_level=level)
            assert config.log_level == level

    def test_config_with_zero_instances(self):
        """Test configuration with zero max concurrent instances."""
        config = OrchestratorConfig(max_concurrent_instances=0)
        assert config.max_concurrent_instances == 0

    def test_config_boolean_flags(self):
        """Test all boolean configuration flags."""
        # Test enable_isolation
        config_isolated = OrchestratorConfig(enable_isolation=True)
        assert config_isolated.enable_isolation is True

        config_not_isolated = OrchestratorConfig(enable_isolation=False)
        assert config_not_isolated.enable_isolation is False

        # Test enable_metrics
        config_metrics = OrchestratorConfig(enable_metrics=True)
        assert config_metrics.enable_metrics is True

        config_no_metrics = OrchestratorConfig(enable_metrics=False)
        assert config_no_metrics.enable_metrics is False

        # Test preserve_artifacts
        config_preserve = OrchestratorConfig(preserve_artifacts=True)
        assert config_preserve.preserve_artifacts is True

        config_no_preserve = OrchestratorConfig(preserve_artifacts=False)
        assert config_no_preserve.preserve_artifacts is False
