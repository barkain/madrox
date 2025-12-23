"""Test server artifact management and logging configuration."""

import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from src.orchestrator.server import ClaudeOrchestratorServer
from src.orchestrator.simple_models import OrchestratorConfig


@pytest.fixture
def mock_config():
    """Create mock orchestrator configuration."""
    return OrchestratorConfig(
        anthropic_api_key="test-key",
        server_host="localhost",
        server_port=8001,
        max_concurrent_instances=10,
        workspace_base_dir="/tmp/test_madrox",
        log_dir="/tmp/test_madrox_logs",
        log_level="INFO",
    )


class TestServerArtifactConfiguration:
    """Test artifact directory and pattern configuration."""

    def test_default_artifacts_directory(self, mock_config):
        """Test default artifacts directory configuration."""
        with patch("src.orchestrator.server.InstanceManager"):
            with patch("src.orchestrator.server.LoggingManager"):
                with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                    server = ClaudeOrchestratorServer(mock_config)

                    assert server.artifacts_base_dir == "/tmp/madrox_logs/artifacts"
                    assert server.preserve_artifacts is True

    def test_custom_artifacts_directory_from_env(self, mock_config):
        """Test custom artifacts directory from environment variable."""
        with patch.dict(os.environ, {"ARTIFACTS_DIR": "/custom/artifacts"}):
            with patch("src.orchestrator.server.InstanceManager"):
                with patch("src.orchestrator.server.LoggingManager"):
                    with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                        server = ClaudeOrchestratorServer(mock_config)

                        assert server.artifacts_base_dir == "/custom/artifacts"

    def test_preserve_artifacts_false(self, mock_config):
        """Test preserve_artifacts set to false."""
        with patch.dict(os.environ, {"PRESERVE_ARTIFACTS": "false"}):
            with patch("src.orchestrator.server.InstanceManager"):
                with patch("src.orchestrator.server.LoggingManager"):
                    with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                        server = ClaudeOrchestratorServer(mock_config)

                        assert server.preserve_artifacts is False

    def test_preserve_artifacts_case_insensitive(self, mock_config):
        """Test preserve_artifacts is case insensitive."""
        with patch.dict(os.environ, {"PRESERVE_ARTIFACTS": "TRUE"}):
            with patch("src.orchestrator.server.InstanceManager"):
                with patch("src.orchestrator.server.LoggingManager"):
                    with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                        server = ClaudeOrchestratorServer(mock_config)

                        assert server.preserve_artifacts is True

    def test_default_artifact_patterns(self, mock_config):
        """Test default artifact patterns include common file types."""
        with patch("src.orchestrator.server.InstanceManager"):
            with patch("src.orchestrator.server.LoggingManager"):
                with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                    server = ClaudeOrchestratorServer(mock_config)

                    # Check for common patterns
                    assert "*.py" in server.artifact_patterns
                    assert "*.js" in server.artifact_patterns
                    assert "*.md" in server.artifact_patterns
                    assert "*.json" in server.artifact_patterns
                    assert "*.yaml" in server.artifact_patterns
                    assert "*.yml" in server.artifact_patterns
                    assert "requirements.txt" in server.artifact_patterns
                    assert "Dockerfile" in server.artifact_patterns
                    assert "package.json" in server.artifact_patterns

    def test_custom_artifact_patterns(self, mock_config):
        """Test custom artifact patterns from environment."""
        custom_patterns = "*.txt,*.log,*.csv"
        with patch.dict(os.environ, {"ARTIFACT_PATTERNS": custom_patterns}):
            with patch("src.orchestrator.server.InstanceManager"):
                with patch("src.orchestrator.server.LoggingManager"):
                    with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                        server = ClaudeOrchestratorServer(mock_config)

                        assert server.artifact_patterns == ["*.txt", "*.log", "*.csv"]

    def test_session_id_generation(self, mock_config):
        """Test session ID generation with timestamp."""
        with patch("src.orchestrator.server.InstanceManager"):
            with patch("src.orchestrator.server.LoggingManager"):
                with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                    server = ClaudeOrchestratorServer(mock_config)

                    # Session ID should start with "session_"
                    assert server.session_id.startswith("session_")
                    # Should contain timestamp
                    assert len(server.session_id) > len("session_")

    def test_instance_manager_workspace_uses_session_artifacts(self, mock_config):
        """Test that instance manager workspace is set to session artifacts directory."""
        with patch("src.orchestrator.server.InstanceManager") as mock_im:
            with patch("src.orchestrator.server.LoggingManager"):
                with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                    server = ClaudeOrchestratorServer(mock_config)

                    # Check that InstanceManager was initialized with correct config
                    call_args = mock_im.call_args[0][0]
                    assert "workspace_base_dir" in call_args
                    assert server.session_id in call_args["workspace_base_dir"]
                    assert "artifacts_dir" in call_args
                    assert call_args["artifacts_dir"] == call_args["workspace_base_dir"]


class TestServerLoggingConfiguration:
    """Test logging configuration and setup."""

    def test_logging_manager_initialization(self, mock_config):
        """Test LoggingManager is initialized with correct parameters."""
        with patch("src.orchestrator.server.InstanceManager"):
            with patch("src.orchestrator.server.LoggingManager") as mock_logging:
                mock_logging.return_value.orchestrator_logger = MagicMock()
                with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                    server = ClaudeOrchestratorServer(mock_config)

                    # Check LoggingManager was called
                    mock_logging.assert_called_once()
                    call_kwargs = mock_logging.call_args[1]
                    assert "log_dir" in call_kwargs
                    assert "log_level" in call_kwargs

    def test_logging_manager_with_custom_log_dir(self, mock_config):
        """Test LoggingManager uses custom log directory from environment."""
        with patch.dict(os.environ, {"MADROX_LOG_DIR": "/custom/logs"}):
            with patch("src.orchestrator.server.InstanceManager"):
                with patch("src.orchestrator.server.LoggingManager") as mock_logging:
                    mock_logging.return_value.orchestrator_logger = MagicMock()
                    with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                        server = ClaudeOrchestratorServer(mock_config)

                        call_kwargs = mock_logging.call_args[1]
                        assert call_kwargs["log_dir"] == "/custom/logs"

    def test_logging_manager_with_custom_log_level(self, mock_config):
        """Test LoggingManager uses custom log level from environment."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            with patch("src.orchestrator.server.InstanceManager"):
                with patch("src.orchestrator.server.LoggingManager") as mock_logging:
                    mock_logging.return_value.orchestrator_logger = MagicMock()
                    with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                        server = ClaudeOrchestratorServer(mock_config)

                        call_kwargs = mock_logging.call_args[1]
                        assert call_kwargs["log_level"] == "DEBUG"

    def test_server_start_time_recorded(self, mock_config):
        """Test that server start time is recorded."""
        with patch("src.orchestrator.server.InstanceManager"):
            with patch("src.orchestrator.server.LoggingManager"):
                with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                    server = ClaudeOrchestratorServer(mock_config)

                    # Should have start time in ISO format
                    assert server.server_start_time is not None
                    # Should be parseable as datetime
                    datetime.fromisoformat(server.server_start_time)


class TestServerCORSConfiguration:
    """Test CORS middleware configuration."""

    def test_cors_middleware_configured(self, mock_config):
        """Test that CORS middleware is added to the app."""
        with patch("src.orchestrator.server.InstanceManager"):
            with patch("src.orchestrator.server.LoggingManager"):
                with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                    server = ClaudeOrchestratorServer(mock_config)

                    # Check that middleware was added
                    # FastAPI stores middleware in app.user_middleware
                    assert len(server.app.user_middleware) > 0

                    # Find CORS middleware
                    cors_middleware_found = False
                    for middleware in server.app.user_middleware:
                        if "CORSMiddleware" in str(middleware.cls):
                            cors_middleware_found = True
                            break

                    assert cors_middleware_found, "CORS middleware not found"


class TestMCPAdapterIntegration:
    """Test MCP adapter integration with server."""

    def test_mcp_adapter_initialized(self, mock_config):
        """Test that MCP adapter is created and mounted."""
        with patch("src.orchestrator.server.InstanceManager"):
            with patch("src.orchestrator.server.LoggingManager"):
                with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                    server = ClaudeOrchestratorServer(mock_config)

                    assert server.mcp_adapter is not None
                    assert hasattr(server.mcp_adapter, "router")

    def test_mcp_router_included_in_app(self, mock_config):
        """Test that MCP router is included in FastAPI app."""
        with patch("src.orchestrator.server.InstanceManager"):
            with patch("src.orchestrator.server.LoggingManager"):
                with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                    server = ClaudeOrchestratorServer(mock_config)

                    # Check that router was included
                    # FastAPI stores routers in app.routes
                    routes = [str(route.path) for route in server.app.routes]

                    # MCP adapter has /mcp prefix
                    mcp_routes = [r for r in routes if "/mcp" in r]
                    assert len(mcp_routes) > 0, "No MCP routes found"


class TestServerInitializationOrder:
    """Test initialization order of server components."""

    def test_logging_before_instance_manager(self, mock_config):
        """Test that logging is set up before instance manager."""
        init_order = []

        class MockLoggingManager:
            def __init__(self, **kwargs):
                init_order.append("logging")
                self.orchestrator_logger = MagicMock()

        class MockInstanceManager:
            def __init__(self, config):
                init_order.append("instance_manager")
                self.instances = {}
                self.mcp = MagicMock()
                self.mcp.get_tools = AsyncMock(return_value={})

        with patch("src.orchestrator.server.LoggingManager", MockLoggingManager):
            with patch("src.orchestrator.server.InstanceManager", MockInstanceManager):
                with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                    server = ClaudeOrchestratorServer(mock_config)

                    # Logging should be initialized before instance manager
                    assert init_order.index("logging") < init_order.index("instance_manager")

    def test_session_id_before_instance_manager(self, mock_config):
        """Test that session ID is generated before instance manager initialization."""
        with patch("src.orchestrator.server.InstanceManager") as mock_im:
            with patch("src.orchestrator.server.LoggingManager"):
                with patch.object(ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"):
                    server = ClaudeOrchestratorServer(mock_config)

                    # Instance manager config should have session_id
                    call_args = mock_im.call_args[0][0]
                    assert "session_id" in call_args
                    assert call_args["session_id"] == server.session_id
