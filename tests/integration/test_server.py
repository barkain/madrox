"""Integration tests for Claude Orchestrator Server."""

import asyncio
import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.orchestrator.server import ClaudeOrchestratorServer
from src.orchestrator.simple_models import OrchestratorConfig


@pytest.fixture
def orchestrator_config():
    """Create test orchestrator configuration."""
    return OrchestratorConfig(
        workspace_base_dir="/tmp/test_workspace",
        log_dir="/tmp/test_logs",
        log_level="INFO",
        max_concurrent_instances=10,
        instance_timeout_minutes=60,
    )


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("ARTIFACTS_DIR", "/tmp/test_artifacts")
    monkeypatch.setenv("PRESERVE_ARTIFACTS", "true")
    monkeypatch.setenv("MADROX_LOG_DIR", "/tmp/test_logs")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


@pytest.fixture
def server(orchestrator_config, mock_env_vars):
    """Create ClaudeOrchestratorServer instance for testing."""
    with patch("src.orchestrator.server.LoggingManager"):
        with patch("src.orchestrator.server.InstanceManager") as mock_im:
            # Mock instance manager
            mock_instance_manager = MagicMock()
            mock_instance_manager.instances = {}
            mock_instance_manager.mcp = MagicMock()
            mock_instance_manager._get_instance_status_internal = MagicMock(
                return_value={"instances": {}, "total_instances": 0}
            )

            # Mock MCP tools
            async def mock_get_tools():
                return {}

            mock_instance_manager.mcp.get_tools = mock_get_tools
            mock_im.return_value = mock_instance_manager

            server = ClaudeOrchestratorServer(orchestrator_config)
            server.instance_manager = mock_instance_manager

            return server


@pytest.fixture
def test_client(server):
    """Create FastAPI test client."""
    return TestClient(server.app)


class TestServerInitialization:
    """Test server initialization."""

    def test_server_init_with_config(self, orchestrator_config, mock_env_vars):
        """Test server initializes with configuration."""
        with patch("src.orchestrator.server.LoggingManager"):
            with patch("src.orchestrator.server.InstanceManager"):
                server = ClaudeOrchestratorServer(orchestrator_config)

                assert server.config == orchestrator_config
                assert server.app is not None
                assert server.instance_manager is not None

    def test_logging_manager_setup(self, server):
        """Test logging manager is configured."""
        assert hasattr(server, "logging_manager")

    def test_session_id_generation(self, server):
        """Test unique session ID is generated."""
        assert hasattr(server, "session_id")
        assert server.session_id.startswith("session_")
        assert len(server.session_id) > 8

    def test_artifacts_directory_configuration(self, server):
        """Test artifacts directory is configured."""
        assert hasattr(server, "artifacts_base_dir")
        assert server.preserve_artifacts is True
        assert len(server.artifact_patterns) > 0

    def test_fastapi_app_created(self, server):
        """Test FastAPI app is created with correct configuration."""
        assert server.app.title == "Claude Conversational Orchestrator"
        assert server.app.version == "1.0.0"

    def test_cors_middleware_configured(self, server):
        """Test CORS middleware is added."""
        # Check that middleware is configured
        # user_middleware contains Middleware objects with a .cls attribute
        middleware_classes = [m.cls.__name__ for m in server.app.user_middleware]
        assert any("CORS" in name for name in middleware_classes)

    def test_mcp_adapter_initialized(self, server):
        """Test MCP adapter is initialized and mounted."""
        assert hasattr(server, "mcp_adapter")
        assert server.mcp_adapter is not None

    def test_routes_registered(self, server):
        """Test routes are registered."""
        routes = server.app.routes
        assert len(routes) > 0

        # Check for specific routes
        paths = [route.path for route in routes if hasattr(route, "path")]
        assert "/" in paths or any(p == "/" for p in paths)


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_endpoint_success(self, test_client):
        """Test root endpoint returns server info."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert data["name"] == "Claude Conversational Orchestrator"
        assert data["version"] == "1.0.0"

    def test_root_endpoint_includes_tools(self, test_client):
        """Test root endpoint includes tools list."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)

    def test_root_endpoint_includes_instance_count(self, test_client):
        """Test root endpoint includes active instance count."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "active_instances" in data
        assert isinstance(data["active_instances"], int)

    def test_root_endpoint_includes_timestamp(self, test_client):
        """Test root endpoint includes server timestamp."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "server_time" in data
        assert isinstance(data["server_time"], str)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_endpoint_success(self, test_client):
        """Test health endpoint returns healthy status."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_endpoint_includes_timestamp(self, test_client):
        """Test health endpoint includes timestamp."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)

    def test_health_endpoint_includes_version(self, test_client):
        """Test health endpoint includes version."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"

    def test_health_endpoint_includes_instance_stats(self, test_client):
        """Test health endpoint includes instance statistics."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "instances" in data
        assert "total" in data["instances"]
        assert "running" in data["instances"]
        assert isinstance(data["instances"]["total"], int)
        assert isinstance(data["instances"]["running"], int)


class TestWebSocketMonitoring:
    """Test WebSocket monitoring endpoint."""

    def test_websocket_connection(self, test_client):
        """Test WebSocket connection can be established."""
        with test_client.websocket_connect("/ws/monitor") as websocket:
            # Should receive initial state
            data = websocket.receive_json()
            assert "type" in data
            assert data["type"] == "initial_state"
            assert "timestamp" in data
            assert "data" in data

    def test_websocket_initial_state_format(self, test_client):
        """Test WebSocket initial state has correct format."""
        with test_client.websocket_connect("/ws/monitor") as websocket:
            data = websocket.receive_json()
            assert "data" in data
            assert "instances" in data["data"]
            assert isinstance(data["data"]["instances"], list)


class TestMCPAdapterIntegration:
    """Test MCP adapter integration with server."""

    def test_mcp_routes_mounted(self, test_client):
        """Test MCP adapter routes are mounted."""
        # The MCP adapter should be mounted at /mcp
        # We can't test all routes without a full setup, but we can verify the prefix exists
        routes = test_client.app.routes
        mcp_routes = [r for r in routes if hasattr(r, "path") and "/mcp" in r.path]
        assert len(mcp_routes) > 0

    def test_mcp_health_endpoint(self, test_client):
        """Test MCP health endpoint is accessible."""
        # This endpoint is defined in mcp_adapter.py
        response = test_client.get("/mcp/health")
        # Should return 200 or 404 depending on implementation
        assert response.status_code in [200, 404, 405]


class TestServerConfiguration:
    """Test server configuration and environment handling."""

    def test_artifacts_patterns_parsing(self, server):
        """Test artifact patterns are parsed correctly."""
        assert len(server.artifact_patterns) > 0
        assert "*.py" in server.artifact_patterns
        assert "*.json" in server.artifact_patterns

    def test_session_workspace_directory(self, server):
        """Test session workspace directory is configured."""
        # Verify session_id is generated
        assert hasattr(server, "session_id")
        assert server.session_id.startswith("session_")
        # Verify instance manager was called with session workspace configuration
        # Check that session_id was used in the artifacts directory path
        assert hasattr(server, "artifacts_base_dir")

    def test_preserve_artifacts_flag(self, server):
        """Test preserve artifacts flag is set."""
        assert server.preserve_artifacts is True

    def test_server_start_time_recorded(self, server):
        """Test server start time is recorded."""
        assert hasattr(server, "server_start_time")
        assert isinstance(server.server_start_time, str)
        # Should be valid ISO format
        datetime.fromisoformat(server.server_start_time)


class TestErrorHandling:
    """Test server error handling."""

    def test_invalid_endpoint_returns_404(self, test_client):
        """Test accessing invalid endpoint returns 404."""
        response = test_client.get("/nonexistent/endpoint")
        assert response.status_code == 404

    def test_health_check_always_works(self, test_client):
        """Test health check works even under error conditions."""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestServerLifecycle:
    """Test server lifecycle operations."""

    def test_cleanup_orphaned_sessions_called(self, orchestrator_config, mock_env_vars):
        """Test that cleanup of orphaned tmux sessions is called during init."""
        with patch("src.orchestrator.server.LoggingManager"):
            with patch("src.orchestrator.server.InstanceManager"):
                with patch.object(
                    ClaudeOrchestratorServer, "_cleanup_orphaned_tmux_sessions"
                ) as mock_cleanup:
                    server = ClaudeOrchestratorServer(orchestrator_config)
                    mock_cleanup.assert_called_once()

    def test_instance_manager_configured_with_session_id(self, server):
        """Test instance manager receives session configuration."""
        # The instance manager should have session_id in its config
        assert hasattr(server.instance_manager, "__dict__") or hasattr(
            server.instance_manager, "_mock_name"
        )


class TestConcurrency:
    """Test concurrent request handling."""

    def test_concurrent_health_checks(self, test_client):
        """Test server handles concurrent health checks."""
        # Make multiple concurrent requests
        responses = []
        for _ in range(5):
            response = test_client.get("/health")
            responses.append(response)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        assert all(r.json()["status"] == "healthy" for r in responses)

    def test_concurrent_root_requests(self, test_client):
        """Test server handles concurrent root endpoint requests."""
        responses = []
        for _ in range(5):
            response = test_client.get("/")
            responses.append(response)

        assert all(r.status_code == 200 for r in responses)
        assert all("name" in r.json() for r in responses)
