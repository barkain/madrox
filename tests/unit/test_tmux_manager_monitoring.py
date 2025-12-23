"""Test TmuxInstanceManager monitoring service and health checks."""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch, Mock
import pytest

from src.orchestrator.compat import UTC
from src.orchestrator.tmux_instance_manager import TmuxInstanceManager


@pytest.fixture
def mock_config():
    """Create mock configuration for TmuxInstanceManager."""
    return {
        "workspace_base_dir": "/tmp/test_tmux_workspace",
        "max_concurrent_instances": 10,
        "instance_timeout_minutes": 60,
    }


@pytest.fixture
def mock_libtmux_server():
    """Create mock libtmux server."""
    mock_server = MagicMock()
    mock_session = MagicMock()
    mock_window = MagicMock()
    mock_pane = MagicMock()

    mock_pane.send_keys = MagicMock()
    mock_pane.cmd = MagicMock(return_value=MagicMock(stdout=["Test output"]))
    mock_window.panes = [mock_pane]
    mock_session.windows = [mock_window]
    mock_session.kill_session = MagicMock()
    mock_session.set_environment = MagicMock()
    mock_server.new_session = MagicMock(return_value=mock_session)
    mock_server.find_where = MagicMock(return_value=None)

    return mock_server, mock_session, mock_window, mock_pane


class TestMonitoringServiceInitialization:
    """Test MonitoringService initialization."""

    def test_monitoring_service_disabled_without_api_key(self, mock_config):
        """Test that monitoring service is disabled when OPENROUTER_API_KEY not set."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove OPENROUTER_API_KEY if it exists
            if "OPENROUTER_API_KEY" in os.environ:
                del os.environ["OPENROUTER_API_KEY"]

            with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
                manager = TmuxInstanceManager(mock_config)

                assert manager.monitoring_service is None

    def test_monitoring_service_enabled_with_api_key(self, mock_config):
        """Test that monitoring service is enabled when OPENROUTER_API_KEY is set."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
                with patch("src.orchestrator.tmux_instance_manager.LLMSummarizer") as mock_llm:
                    with patch(
                        "src.orchestrator.tmux_instance_manager.MonitoringService"
                    ) as mock_mon:
                        manager = TmuxInstanceManager(mock_config)

                        # Should have created LLMSummarizer
                        mock_llm.assert_called_once()

                        # Should have created MonitoringService
                        mock_mon.assert_called_once()

    def test_monitoring_service_initialization_failure(self, mock_config):
        """Test graceful handling of monitoring service initialization failure."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
                with patch(
                    "src.orchestrator.tmux_instance_manager.LLMSummarizer",
                    side_effect=Exception("Failed to init"),
                ):
                    # Should not raise, just log warning
                    manager = TmuxInstanceManager(mock_config)

                    assert manager.monitoring_service is None

    def test_monitoring_service_logger_configuration(self, mock_config):
        """Test that monitoring service and LLM summarizer loggers are configured."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
                with patch("src.orchestrator.tmux_instance_manager.LLMSummarizer"):
                    with patch("src.orchestrator.tmux_instance_manager.MonitoringService"):
                        with patch(
                            "src.orchestrator.tmux_instance_manager.logging.getLogger"
                        ) as mock_get_logger:
                            # Create mock loggers
                            mock_logger = MagicMock()
                            mock_get_logger.return_value = mock_logger

                            manager = TmuxInstanceManager(mock_config)

                            # Should have configured loggers
                            # (called multiple times for different logger names)
                            assert mock_get_logger.call_count >= 1


class TestHealthMonitoring:
    """Test manager health monitoring functionality."""

    def test_health_monitoring_defaults(self, mock_config):
        """Test default health monitoring configuration."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager._manager_health_check_interval == 30
            assert manager._max_health_failures == 3
            assert manager._health_monitoring_enabled is False
            assert manager._manager_health_task is None
            assert manager._manager_health_failures == 0

    def test_monitoring_service_started_flag(self, mock_config):
        """Test monitoring service started flag initialization."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager._monitoring_service_started is False


class TestSharedStateQueueOperations:
    """Test shared state queue operations."""

    @pytest.mark.asyncio
    async def test_get_from_shared_queue_no_shared_state(self, mock_config):
        """Test _get_from_shared_queue raises error when shared state not available."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)
            manager.shared_state = None

            with pytest.raises(RuntimeError, match="Shared state not available"):
                await manager._get_from_shared_queue("inst-123", timeout=1)

    @pytest.mark.asyncio
    async def test_get_from_shared_queue_timeout(self, mock_config):
        """Test _get_from_shared_queue handles timeout."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            # Mock shared state with queue that times out
            mock_shared_state = MagicMock()
            mock_queue = MagicMock()

            # Simulate queue.Empty exception
            import queue

            mock_queue.get.side_effect = queue.Empty()
            mock_shared_state.get_response_queue.return_value = mock_queue
            manager.shared_state = mock_shared_state

            with pytest.raises(TimeoutError, match="No message received"):
                await manager._get_from_shared_queue("inst-123", timeout=1)

    @pytest.mark.asyncio
    async def test_get_from_shared_queue_success(self, mock_config):
        """Test _get_from_shared_queue successfully retrieves message."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            # Mock shared state with queue that returns message
            mock_shared_state = MagicMock()
            mock_queue = MagicMock()
            test_message = {"content": "test message"}
            mock_queue.get.return_value = test_message
            mock_shared_state.get_response_queue.return_value = mock_queue
            manager.shared_state = mock_shared_state

            result = await manager._get_from_shared_queue("inst-123", timeout=1)

            assert result == test_message


class TestServerPortConfiguration:
    """Test server port configuration."""

    def test_default_server_port(self, mock_config):
        """Test default server port when ORCHESTRATOR_PORT not set."""
        with patch.dict(os.environ, {}, clear=False):
            if "ORCHESTRATOR_PORT" in os.environ:
                del os.environ["ORCHESTRATOR_PORT"]

            with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
                manager = TmuxInstanceManager(mock_config)

                assert manager.server_port == 8001

    def test_custom_server_port_from_env(self, mock_config):
        """Test custom server port from environment variable."""
        with patch.dict(os.environ, {"ORCHESTRATOR_PORT": "9000"}):
            with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
                manager = TmuxInstanceManager(mock_config)

                assert manager.server_port == 9000


class TestWorkspaceConfiguration:
    """Test workspace directory configuration."""

    def test_default_workspace_directory(self):
        """Test default workspace directory."""
        config = {}
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(config)

            assert str(manager.workspace_base) == "/tmp/claude_orchestrator"

    def test_custom_workspace_directory(self):
        """Test custom workspace directory from config."""
        config = {"workspace_base_dir": "/custom/workspace"}
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            with patch("pathlib.Path.mkdir"):
                manager = TmuxInstanceManager(config)

                assert str(manager.workspace_base) == "/custom/workspace"

    def test_workspace_directory_created(self, mock_config):
        """Test that workspace directory is created."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            with patch("pathlib.Path.mkdir") as mock_mkdir:
                manager = TmuxInstanceManager(mock_config)

                # Should have called mkdir with parents=True, exist_ok=True
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestResourceTracking:
    """Test resource tracking initialization."""

    def test_total_tokens_initialized(self, mock_config):
        """Test total tokens counter is initialized."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager.total_tokens_used == 0


class TestLegacyBackwardCompatibility:
    """Test backward compatibility with HTTP transport."""

    def test_response_queues_initialized(self, mock_config):
        """Test response_queues dict is initialized for HTTP transport."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager.response_queues == {}

    def test_message_registry_initialized(self, mock_config):
        """Test message_registry dict is initialized."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager.message_registry == {}

    def test_main_message_inbox_initialized(self, mock_config):
        """Test main_message_inbox list is initialized."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager.main_message_inbox == []

    def test_main_instance_id_initialized(self, mock_config):
        """Test main_instance_id is initialized to None."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager.main_instance_id is None


class TestLoggingManagerIntegration:
    """Test logging manager integration."""

    def test_logging_manager_stored(self, mock_config):
        """Test that logging_manager is stored if provided."""
        mock_logging_manager = MagicMock()

        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config, logging_manager=mock_logging_manager)

            assert manager.logging_manager is mock_logging_manager

    def test_logging_manager_optional(self, mock_config):
        """Test that logging_manager is optional."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager.logging_manager is None


class TestSharedStateManagerIntegration:
    """Test shared state manager integration."""

    def test_shared_state_manager_stored(self, mock_config):
        """Test that shared_state_manager is stored if provided."""
        mock_shared_state = MagicMock()

        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config, shared_state_manager=mock_shared_state)

            assert manager.shared_state is mock_shared_state

    def test_shared_state_manager_optional(self, mock_config):
        """Test that shared_state_manager is optional."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager.shared_state is None


class TestDataStructureInitialization:
    """Test that all data structures are properly initialized."""

    def test_instances_dict_initialized(self, mock_config):
        """Test instances dict is initialized."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager.instances == {}

    def test_tmux_sessions_dict_initialized(self, mock_config):
        """Test tmux_sessions dict is initialized."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager.tmux_sessions == {}

    def test_message_history_dict_initialized(self, mock_config):
        """Test message_history dict is initialized."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server"):
            manager = TmuxInstanceManager(mock_config)

            assert manager.message_history == {}


class TestTmuxServerConnection:
    """Test tmux server connection."""

    def test_tmux_server_connection(self, mock_config):
        """Test that tmux server is connected."""
        with patch("src.orchestrator.tmux_instance_manager.libtmux.Server") as mock_server_class:
            mock_server = MagicMock()
            mock_server_class.return_value = mock_server

            manager = TmuxInstanceManager(mock_config)

            # Should have created server
            mock_server_class.assert_called_once()
            assert manager.tmux_server is mock_server
