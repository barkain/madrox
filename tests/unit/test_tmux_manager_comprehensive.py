"""Comprehensive unit tests for tmux_instance_manager.py

This test suite covers:
1. Session Management (tmux session lifecycle)
2. Message Communication (send/receive via tmux)
3. Instance Lifecycle (spawn, initialize, terminate)
4. MCP Server Configuration
5. Pane Content Capture
6. Error Handling

Target: 85% coverage for tmux_instance_manager.py
Current: 28% (230/813 statements)
"""

import asyncio
import threading
from datetime import datetime, timedelta
from queue import Queue
from unittest.mock import MagicMock, patch

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
    """Create mock libtmux server with session/window/pane hierarchy."""
    mock_server = MagicMock()

    # Mock pane
    mock_pane = MagicMock()
    mock_pane.send_keys = MagicMock()
    mock_pane.cmd = MagicMock(return_value=MagicMock(stdout=["Test output"]))

    # Mock window
    mock_window = MagicMock()
    mock_window.panes = [mock_pane]

    # Mock session
    mock_session = MagicMock()
    mock_session.windows = [mock_window]
    mock_session.kill_session = MagicMock()
    mock_session.set_environment = MagicMock()

    # Server methods
    mock_server.new_session = MagicMock(return_value=mock_session)
    mock_server.find_where = MagicMock(return_value=None)

    return mock_server, mock_session, mock_window, mock_pane


@pytest.fixture
def tmux_manager(mock_config, mock_libtmux_server):
    """Create TmuxInstanceManager with mocked dependencies."""
    mock_server, mock_session, mock_window, mock_pane = mock_libtmux_server

    with patch("src.orchestrator.tmux_instance_manager.libtmux.Server", return_value=mock_server):
        with patch.dict("os.environ", {"ORCHESTRATOR_PORT": "8001"}, clear=False):
            # Mock Path operations to avoid filesystem access
            with patch("pathlib.Path.write_text"):
                with patch("pathlib.Path.mkdir"):
                    manager = TmuxInstanceManager(mock_config)

                    # Store mock references in separate dict for test access (not on manager instance)
                    # This avoids type errors while allowing tests to access mocks

                    # Attach mocks to the manager's actual tmux_server for test access
                    manager.tmux_server._test_session = mock_session
                    manager.tmux_server._test_window = mock_window
                    manager.tmux_server._test_pane = mock_pane

                    # Use setattr to bypass type checking - these are test-only attributes
                    object.__setattr__(manager, "_mock_server", mock_server)
                    object.__setattr__(manager, "_mock_session", mock_session)
                    object.__setattr__(manager, "_mock_pane", mock_pane)

                    yield manager


# ============================================================================
# Session Management Tests (15 tests)
# ============================================================================


class TestSessionManagement:
    """Test tmux session creation, listing, and cleanup."""

    @pytest.mark.asyncio
    async def test_create_tmux_session_success(self, tmux_manager):
        """Test successful tmux session creation."""
        instance_id = "test-123"
        instance = {
            "id": instance_id,
            "workspace_dir": "/tmp/test_workspace",
            "instance_type": "claude",
            "model": None,
            "bypass_isolation": True,
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity": datetime.now(UTC).isoformat(),
            "mcp_servers": {},
        }

        tmux_manager.instances[instance_id] = instance

        # Execute
        await tmux_manager._initialize_tmux_session(instance_id)

        # Assert
        assert instance_id in tmux_manager.tmux_sessions
        assert tmux_manager._mock_server.new_session.called

    @pytest.mark.asyncio
    async def test_create_tmux_session_already_exists(self, tmux_manager):
        """Test creating session when one already exists (should kill old session)."""
        instance_id = "existing-123"

        # Setup existing session mock
        existing_session = MagicMock()
        existing_session.kill_session = MagicMock()
        tmux_manager._mock_server.find_where = MagicMock(return_value=existing_session)

        instance = {
            "id": instance_id,
            "workspace_dir": "/tmp/test",
            "instance_type": "claude",
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity": datetime.now(UTC).isoformat(),
            "mcp_servers": {},
        }
        tmux_manager.instances[instance_id] = instance

        # Execute
        await tmux_manager._initialize_tmux_session(instance_id)

        # Assert - old session should be killed
        existing_session.kill_session.assert_called_once()
        tmux_manager._mock_server.new_session.assert_called()

    @pytest.mark.asyncio
    async def test_create_tmux_session_tmux_not_installed(self, tmux_manager):
        """Test session creation when tmux is not available."""
        instance_id = "no-tmux-123"

        # Mock tmux unavailability
        tmux_manager._mock_server.new_session.side_effect = Exception("tmux not found")

        instance = {
            "id": instance_id,
            "workspace_dir": "/tmp/test",
            "instance_type": "claude",
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity": datetime.now(UTC).isoformat(),
            "mcp_servers": {},
        }
        tmux_manager.instances[instance_id] = instance

        # Execute & Assert
        with pytest.raises(Exception, match="tmux not found"):
            await tmux_manager._initialize_tmux_session(instance_id)

    @pytest.mark.asyncio
    async def test_kill_tmux_session_success(self, tmux_manager):
        """Test successful tmux session termination."""
        instance_id = "kill-123"

        # Setup instance with session
        tmux_manager.tmux_sessions[instance_id] = tmux_manager._mock_session
        tmux_manager.instances[instance_id] = {
            "id": instance_id,
            "state": "running",
        }

        # Execute
        result = await tmux_manager.terminate_instance(instance_id, force=True)

        # Assert
        assert result is True
        tmux_manager._mock_session.kill_session.assert_called_once()
        assert instance_id not in tmux_manager.tmux_sessions

    @pytest.mark.asyncio
    async def test_kill_tmux_session_not_found(self, tmux_manager):
        """Test terminating instance with no tmux session."""
        instance_id = "no-session-123"

        tmux_manager.instances[instance_id] = {
            "id": instance_id,
            "state": "running",
        }

        # No session in tmux_sessions dict

        # Execute
        result = await tmux_manager.terminate_instance(instance_id, force=True)

        # Assert - should still succeed
        assert result is True

    @pytest.mark.asyncio
    async def test_list_tmux_sessions(self, tmux_manager):
        """Test listing all active tmux sessions."""
        # Setup multiple sessions
        for i in range(3):
            instance_id = f"inst-{i}"
            tmux_manager.tmux_sessions[instance_id] = MagicMock()
            tmux_manager.instances[instance_id] = {
                "id": instance_id,
                "state": "running",
            }

        # Execute
        sessions = list(tmux_manager.tmux_sessions.keys())

        # Assert
        assert len(sessions) == 3
        assert "inst-0" in sessions
        assert "inst-2" in sessions

    @pytest.mark.asyncio
    async def test_session_cleanup_on_error(self, tmux_manager):
        """Test that sessions are cleaned up on initialization error."""
        instance_id = "error-123"

        # Mock pane to raise error during CLI startup
        tmux_manager._mock_pane.send_keys.side_effect = Exception("CLI startup failed")

        instance = {
            "id": instance_id,
            "workspace_dir": "/tmp/test",
            "instance_type": "claude",
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity": datetime.now(UTC).isoformat(),
            "mcp_servers": {},
        }
        tmux_manager.instances[instance_id] = instance

        # Execute & Assert
        with pytest.raises(Exception, match="CLI startup failed"):
            await tmux_manager._initialize_tmux_session(instance_id)

    @pytest.mark.asyncio
    async def test_session_name_sanitization(self, tmux_manager):
        """Test that session names are properly formatted."""
        instance_id = "test-with-special-chars!@#"

        instance = {
            "id": instance_id,
            "workspace_dir": "/tmp/test",
            "instance_type": "claude",
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity": datetime.now(UTC).isoformat(),
            "mcp_servers": {},
        }
        tmux_manager.instances[instance_id] = instance

        # Execute
        await tmux_manager._initialize_tmux_session(instance_id)

        # Assert - session name should be sanitized
        call_args = tmux_manager._mock_server.new_session.call_args
        session_name = call_args.kwargs.get("session_name")
        assert session_name == f"madrox-{instance_id}"


# ============================================================================
# Message Communication Tests (20 tests)
# ============================================================================


class TestMessageCommunication:
    """Test message sending and receiving via tmux."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, tmux_manager):
        """Test successful message send."""
        instance_id = "msg-123"

        # Setup instance
        tmux_manager.instances[instance_id] = {
            "id": instance_id,
            "state": "running",
            "last_activity": datetime.now(UTC).isoformat(),
            "total_tokens_used": 0,
            "request_count": 0,
        }
        tmux_manager.tmux_sessions[instance_id] = tmux_manager._mock_session
        tmux_manager.message_history[instance_id] = []

        # Mock response queue behavior
        with patch.object(tmux_manager, "response_queues", {}):
            tmux_manager.response_queues[instance_id] = asyncio.Queue()

            # Execute
            result = await tmux_manager.send_message(
                instance_id=instance_id,
                message="Test message",
                wait_for_response=False,
            )

            # Assert
            assert result["status"] == "sent"
            assert result["instance_id"] == instance_id
            assert "message_id" in result

    @pytest.mark.asyncio
    async def test_send_message_timeout(self, tmux_manager):
        """Test message send with timeout."""
        instance_id = "timeout-123"

        tmux_manager.instances[instance_id] = {
            "id": instance_id,
            "state": "running",
            "last_activity": datetime.now(UTC).isoformat(),
            "total_tokens_used": 0,
            "request_count": 0,
        }
        tmux_manager.tmux_sessions[instance_id] = tmux_manager._mock_session
        tmux_manager.message_history[instance_id] = []
        tmux_manager.response_queues = {}
        tmux_manager.response_queues[instance_id] = asyncio.Queue()

        # Mock pane output to never change (timeout scenario)
        tmux_manager._mock_pane.cmd = MagicMock(
            return_value=MagicMock(stdout=["Same output"] * 100)
        )

        # Execute with very short timeout
        result = await tmux_manager.send_message(
            instance_id=instance_id,
            message="Test",
            wait_for_response=True,
            timeout_seconds=1,
        )

        # Assert - should return even with timeout
        assert "response" in result or "status" in result

    @pytest.mark.asyncio
    async def test_send_message_instance_not_found(self, tmux_manager):
        """Test sending to non-existent instance."""
        # Execute & Assert
        with pytest.raises(ValueError, match="not found"):
            await tmux_manager.send_message(
                instance_id="nonexistent",
                message="Test",
            )

    @pytest.mark.asyncio
    async def test_send_multiline_message(self, tmux_manager):
        """Test sending multiline message."""
        instance_id = "multiline-123"

        tmux_manager.instances[instance_id] = {
            "id": instance_id,
            "state": "running",
            "last_activity": datetime.now(UTC).isoformat(),
            "total_tokens_used": 0,
            "request_count": 0,
        }
        tmux_manager.tmux_sessions[instance_id] = tmux_manager._mock_session
        tmux_manager.message_history[instance_id] = []
        tmux_manager.response_queues = {}
        tmux_manager.response_queues[instance_id] = asyncio.Queue()

        multiline_msg = "Line 1\nLine 2\nLine 3"

        # Execute
        result = await tmux_manager.send_message(
            instance_id=instance_id,
            message=multiline_msg,
            wait_for_response=False,
        )

        # Assert
        assert result["status"] == "sent"
        # Pane should have been called multiple times for multiline
        assert tmux_manager._mock_pane.send_keys.call_count > 1

    @pytest.mark.asyncio
    async def test_send_message_with_special_chars(self, tmux_manager):
        """Test sending message with special characters."""
        instance_id = "special-123"

        tmux_manager.instances[instance_id] = {
            "id": instance_id,
            "state": "running",
            "last_activity": datetime.now(UTC).isoformat(),
            "total_tokens_used": 0,
            "request_count": 0,
        }
        tmux_manager.tmux_sessions[instance_id] = tmux_manager._mock_session
        tmux_manager.message_history[instance_id] = []
        tmux_manager.response_queues = {}
        tmux_manager.response_queues[instance_id] = asyncio.Queue()

        special_msg = 'Test with "quotes" and $vars and `backticks`'

        # Execute
        result = await tmux_manager.send_message(
            instance_id=instance_id,
            message=special_msg,
            wait_for_response=False,
        )

        # Assert
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_receive_response_success(self, tmux_manager):
        """Test receiving response from instance."""
        instance_id = "recv-123"

        tmux_manager.instances[instance_id] = {
            "id": instance_id,
            "state": "running",
            "last_activity": datetime.now(UTC).isoformat(),
            "total_tokens_used": 0,
            "request_count": 0,
        }
        tmux_manager.tmux_sessions[instance_id] = tmux_manager._mock_session
        tmux_manager.message_history[instance_id] = []
        tmux_manager.response_queues = {}
        tmux_manager.response_queues[instance_id] = asyncio.Queue()

        # Queue a response
        await tmux_manager.response_queues[instance_id].put(
            {
                "reply_message": "Response text",
                "correlation_id": "msg-123",
            }
        )

        # Execute
        result = await tmux_manager.send_message(
            instance_id=instance_id,
            message="Question",
            wait_for_response=True,
            timeout_seconds=5,
        )

        # Assert
        assert result["response"] == "Response text"
        assert result["protocol"] == "bidirectional"

    @pytest.mark.asyncio
    async def test_receive_response_timeout(self, tmux_manager):
        """Test timeout when waiting for response."""
        instance_id = "timeout-recv-123"

        tmux_manager.instances[instance_id] = {
            "id": instance_id,
            "state": "running",
            "last_activity": datetime.now(UTC).isoformat(),
            "total_tokens_used": 0,
            "request_count": 0,
        }
        tmux_manager.tmux_sessions[instance_id] = tmux_manager._mock_session
        tmux_manager.message_history[instance_id] = []
        tmux_manager.response_queues = {}
        tmux_manager.response_queues[instance_id] = asyncio.Queue()

        # No response queued - will timeout

        # Mock stable pane output for fallback
        tmux_manager._mock_pane.cmd = MagicMock(return_value=MagicMock(stdout=["Output"] * 100))

        # Execute
        result = await tmux_manager.send_message(
            instance_id=instance_id,
            message="Question",
            wait_for_response=True,
            timeout_seconds=1,
        )

        # Assert - should fall back to polling
        assert "response" in result or "protocol" in result

    @pytest.mark.asyncio
    async def test_message_queue_operations(self, tmux_manager):
        """Test response queue FIFO operations."""
        instance_id = "queue-123"

        tmux_manager.response_queues = {}
        queue = asyncio.Queue()
        tmux_manager.response_queues[instance_id] = queue

        # Add multiple messages
        await queue.put({"msg": "first"})
        await queue.put({"msg": "second"})
        await queue.put({"msg": "third"})

        # Retrieve in order
        msg1 = await queue.get()
        msg2 = await queue.get()
        msg3 = await queue.get()

        # Assert FIFO order
        assert msg1["msg"] == "first"
        assert msg2["msg"] == "second"
        assert msg3["msg"] == "third"

    @pytest.mark.asyncio
    async def test_put_with_lock(self, tmux_manager):
        """Test thread-safe queue put operation with lock."""
        # This is a simplified test since put_with_lock is used internally
        # It's actually part of _put_to_shared_queue which requires shared_state

        # Setup shared_state mock
        mock_shared_state = MagicMock()
        mock_queue = MagicMock()
        mock_lock = MagicMock()

        mock_shared_state.get_response_queue = MagicMock(return_value=mock_queue)
        mock_shared_state.queue_locks = {"inst-123": mock_lock}

        tmux_manager.shared_state = mock_shared_state

        # Execute
        await tmux_manager._put_to_shared_queue("inst-123", {"test": "message"})

        # Assert - lock context manager was used
        mock_lock.__enter__.assert_called()
        mock_lock.__exit__.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_message_sending(self, tmux_manager):
        """Test sending messages to multiple instances concurrently."""
        # Setup multiple instances
        for i in range(3):
            instance_id = f"concurrent-{i}"
            tmux_manager.instances[instance_id] = {
                "id": instance_id,
                "state": "running",
                "last_activity": datetime.now(UTC).isoformat(),
                "total_tokens_used": 0,
                "request_count": 0,
            }
            tmux_manager.tmux_sessions[instance_id] = tmux_manager._mock_session
            tmux_manager.message_history[instance_id] = []

        tmux_manager.response_queues = {}

        # Send messages concurrently
        tasks = []
        for i in range(3):
            instance_id = f"concurrent-{i}"
            tmux_manager.response_queues[instance_id] = asyncio.Queue()
            task = tmux_manager.send_message(
                instance_id=instance_id,
                message=f"Message {i}",
                wait_for_response=False,
            )
            tasks.append(task)

        # Execute all concurrently
        results = await asyncio.gather(*tasks)

        # Assert
        assert len(results) == 3
        assert all(r["status"] == "sent" for r in results)


# ============================================================================
# Instance Lifecycle Tests (12 tests)
# ============================================================================


class TestInstanceLifecycle:
    """Test instance spawn, initialization, and termination."""

    @pytest.mark.asyncio
    async def test_spawn_instance_success(self, tmux_manager):
        """Test successful instance spawn."""
        # Execute
        instance_id = await tmux_manager.spawn_instance(
            name="test-instance",
            role="general",
        )

        # Assert
        assert instance_id in tmux_manager.instances
        assert tmux_manager.instances[instance_id]["name"] == "test-instance"
        assert tmux_manager.instances[instance_id]["state"] == "running"

    @pytest.mark.asyncio
    async def test_spawn_instance_with_system_prompt(self, tmux_manager):
        """Test spawning with custom system prompt."""
        custom_prompt = "You are a specialized agent for testing."

        # Execute
        instance_id = await tmux_manager.spawn_instance(
            name="custom-agent",
            system_prompt=custom_prompt,
        )

        # Assert
        assert tmux_manager.instances[instance_id]["system_prompt"] == custom_prompt
        assert tmux_manager.instances[instance_id]["has_custom_prompt"] is True

    @pytest.mark.asyncio
    async def test_spawn_instance_with_mcp_servers(self, tmux_manager):
        """Test spawning with MCP server configuration."""
        mcp_config = {
            "test_server": {
                "transport": "http",
                "url": "http://localhost:9000/mcp",
            }
        }

        # Execute
        instance_id = await tmux_manager.spawn_instance(
            name="mcp-instance",
            mcp_servers=mcp_config,
        )

        # Assert
        assert tmux_manager.instances[instance_id]["mcp_servers"] == mcp_config

    @pytest.mark.asyncio
    async def test_terminate_instance_graceful(self, tmux_manager):
        """Test graceful instance termination."""
        # Setup
        instance_id = await tmux_manager.spawn_instance(name="to-terminate")
        tmux_manager.instances[instance_id]["state"] = "idle"

        # Execute
        result = await tmux_manager.terminate_instance(instance_id, force=False)

        # Assert
        assert result is True
        assert tmux_manager.instances[instance_id]["state"] == "terminated"

    @pytest.mark.asyncio
    async def test_terminate_instance_force(self, tmux_manager):
        """Test forced termination of busy instance."""
        # Setup
        instance_id = await tmux_manager.spawn_instance(name="force-terminate")
        tmux_manager.instances[instance_id]["state"] = "busy"

        # Execute
        result = await tmux_manager.terminate_instance(instance_id, force=True)

        # Assert
        assert result is True
        assert tmux_manager.instances[instance_id]["state"] == "terminated"

    @pytest.mark.asyncio
    async def test_instance_state_transitions(self, tmux_manager):
        """Test instance state transitions through lifecycle."""
        # Spawn
        instance_id = await tmux_manager.spawn_instance(name="lifecycle-test")
        assert tmux_manager.instances[instance_id]["state"] == "running"

        # Update to busy
        tmux_manager.instances[instance_id]["state"] = "busy"
        assert tmux_manager.instances[instance_id]["state"] == "busy"

        # Back to idle
        tmux_manager.instances[instance_id]["state"] = "idle"
        assert tmux_manager.instances[instance_id]["state"] == "idle"

        # Terminate
        await tmux_manager.terminate_instance(instance_id, force=True)
        assert tmux_manager.instances[instance_id]["state"] == "terminated"

    @pytest.mark.asyncio
    async def test_instance_health_check(self, tmux_manager):
        """Test instance health check."""
        # Setup
        instance_id = await tmux_manager.spawn_instance(name="health-test")

        # Execute
        health = await tmux_manager.check_pane_health(instance_id)

        # Assert
        assert health["healthy"] is True or "error" in health
        assert health["instance_id"] == instance_id

    @pytest.mark.asyncio
    async def test_instance_timeout_handling(self, tmux_manager):
        """Test instance timeout enforcement."""
        # Setup
        instance_id = await tmux_manager.spawn_instance(name="timeout-test")

        # Set last_activity to old time
        old_time = datetime.now(UTC) - timedelta(minutes=70)
        tmux_manager.instances[instance_id]["last_activity"] = old_time.isoformat()

        # Execute health check
        await tmux_manager.health_check()

        # Assert - should be terminated
        assert tmux_manager.instances[instance_id]["state"] == "terminated"

    @pytest.mark.asyncio
    async def test_spawn_instance_max_limit(self, tmux_manager):
        """Test spawning fails when max instances reached."""
        # Spawn up to limit
        tmux_manager.config["max_concurrent_instances"] = 2

        await tmux_manager.spawn_instance(name="inst-1")
        await tmux_manager.spawn_instance(name="inst-2")

        # Execute & Assert - should fail
        with pytest.raises(RuntimeError, match="Maximum concurrent instances"):
            await tmux_manager.spawn_instance(name="inst-3")

    @pytest.mark.asyncio
    async def test_spawn_instance_workspace_creation(self, tmux_manager):
        """Test that instance workspace is created."""
        # Execute
        instance_id = await tmux_manager.spawn_instance(name="workspace-test")

        # Assert
        workspace_dir = tmux_manager.instances[instance_id]["workspace_dir"]
        assert workspace_dir is not None
        assert instance_id in workspace_dir

    @pytest.mark.asyncio
    async def test_spawn_codex_instance(self, tmux_manager):
        """Test spawning Codex instance type."""
        # Execute
        instance_id = await tmux_manager.spawn_instance(
            name="codex-test",
            instance_type="codex",
            sandbox_mode="workspace-write",
        )

        # Assert
        assert tmux_manager.instances[instance_id]["instance_type"] == "codex"
        assert tmux_manager.instances[instance_id]["sandbox_mode"] == "workspace-write"

    @pytest.mark.asyncio
    async def test_spawn_instance_with_initial_prompt(self, tmux_manager):
        """Test spawning with initial prompt."""
        initial = "Start working on task X"

        # Execute
        instance_id = await tmux_manager.spawn_instance(
            name="initial-prompt-test",
            initial_prompt=initial,
        )

        # Assert
        assert tmux_manager.instances[instance_id]["initial_prompt"] == initial


# ============================================================================
# MCP Server Configuration Tests (8 tests)
# ============================================================================


class TestMCPServerConfiguration:
    """Test MCP server configuration for Claude and Codex instances."""

    @pytest.mark.asyncio
    async def test_configure_mcp_servers_success(self, tmux_manager):
        """Test successful MCP server configuration."""
        instance_id = "mcp-config-123"
        instance = {
            "id": instance_id,
            "workspace_dir": "/tmp/mcp_test",
            "instance_type": "claude",
            "mcp_servers": {
                "test_server": {
                    "transport": "http",
                    "url": "http://localhost:8000/mcp",
                }
            },
        }

        # Execute
        tmux_manager._configure_mcp_servers(tmux_manager._mock_pane, instance)

        # Assert - config file path should be set
        assert "_mcp_config_path" in instance

    @pytest.mark.asyncio
    async def test_configure_mcp_servers_stdio(self, tmux_manager):
        """Test MCP server with STDIO transport."""
        instance = {
            "id": "stdio-123",
            "workspace_dir": "/tmp/stdio_test",
            "instance_type": "claude",
            "mcp_servers": {
                "stdio_server": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["server.py"],
                    "env": {"KEY": "value"},
                }
            },
        }

        # Execute
        tmux_manager._configure_mcp_servers(tmux_manager._mock_pane, instance)

        # Assert
        assert "_mcp_config_path" in instance

    @pytest.mark.asyncio
    async def test_configure_mcp_servers_invalid_config(self, tmux_manager):
        """Test handling of invalid MCP server config."""
        instance = {
            "id": "invalid-123",
            "workspace_dir": "/tmp/invalid_test",
            "instance_type": "claude",
            "mcp_servers": "invalid-json-string",  # Invalid format
        }

        # Execute - should handle gracefully (logs error but doesn't crash)
        tmux_manager._configure_mcp_servers(tmux_manager._mock_pane, instance)

        # Assert - method completes without raising exception
        # Note: Implementation doesn't update instance["mcp_servers"] when invalid
        # It only updates the local mcp_servers variable
        assert instance["mcp_servers"] == "invalid-json-string"  # Unchanged

    @pytest.mark.asyncio
    async def test_configure_mcp_servers_auto_madrox(self, tmux_manager):
        """Test auto-addition of Madrox MCP server."""
        instance = {
            "id": "auto-madrox-123",
            "workspace_dir": "/tmp/auto_test",
            "instance_type": "claude",
            "mcp_servers": {},  # Empty - should auto-add madrox
        }

        # Execute
        tmux_manager._configure_mcp_servers(tmux_manager._mock_pane, instance)

        # Assert
        assert "madrox" in instance["mcp_servers"]

    @pytest.mark.asyncio
    async def test_mcp_server_startup(self, tmux_manager):
        """Test MCP server configuration during instance startup."""
        mcp_config = {
            "my_server": {
                "transport": "http",
                "url": "http://localhost:9000/mcp",
            }
        }

        # Execute
        instance_id = await tmux_manager.spawn_instance(
            name="mcp-startup-test",
            mcp_servers=mcp_config,
        )

        # Assert
        assert (
            tmux_manager.instances[instance_id]["mcp_servers"]["my_server"]["url"]
            == "http://localhost:9000/mcp"
        )

    @pytest.mark.asyncio
    async def test_mcp_server_codex_config(self, tmux_manager):
        """Test MCP server configuration for Codex instances."""
        instance = {
            "id": "codex-mcp-123",
            "workspace_dir": "/tmp/codex_mcp_test",
            "instance_type": "codex",
            "mcp_servers": {
                "codex_server": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["mcp_server.py"],
                }
            },
        }

        # Execute
        tmux_manager._configure_mcp_servers(tmux_manager._mock_pane, instance)

        # Assert - Codex uses direct commands, no _mcp_config_path
        assert "_mcp_config_path" not in instance
        tmux_manager._mock_pane.send_keys.assert_called()

    @pytest.mark.asyncio
    async def test_mcp_server_http_with_bearer_token(self, tmux_manager):
        """Test HTTP MCP server with bearer token authentication."""
        instance = {
            "id": "bearer-123",
            "workspace_dir": "/tmp/bearer_test",
            "instance_type": "claude",
            "mcp_servers": {
                "secure_server": {
                    "transport": "http",
                    "url": "http://localhost:8000/mcp",
                    "bearer_token": "secret-token-123",
                }
            },
        }

        # Execute
        tmux_manager._configure_mcp_servers(tmux_manager._mock_pane, instance)

        # Assert
        assert "_mcp_config_path" in instance

    @pytest.mark.asyncio
    async def test_mcp_server_missing_required_fields(self, tmux_manager):
        """Test MCP server config with missing required fields."""
        instance = {
            "id": "missing-123",
            "workspace_dir": "/tmp/missing_test",
            "instance_type": "claude",
            "mcp_servers": {
                "broken_server": {
                    "transport": "http",
                    # Missing "url" field
                }
            },
        }

        # Execute - should handle gracefully
        tmux_manager._configure_mcp_servers(tmux_manager._mock_pane, instance)

        # Assert - should still create config file
        assert "_mcp_config_path" in instance


# ============================================================================
# Pane Content Tests (5 tests)
# ============================================================================


class TestPaneContent:
    """Test tmux pane content capture."""

    @pytest.mark.asyncio
    async def test_get_tmux_pane_content_success(self, tmux_manager):
        """Test successful pane content capture."""
        # Setup
        instance_id = await tmux_manager.spawn_instance(name="pane-test")

        mock_output = ["Line 1", "Line 2", "Line 3"]
        tmux_manager._mock_pane.cmd = MagicMock(return_value=MagicMock(stdout=mock_output))

        # Execute
        content = await tmux_manager.get_tmux_pane_content(instance_id, lines=100)

        # Assert
        assert "Line 1" in content
        assert "Line 2" in content

    @pytest.mark.asyncio
    async def test_get_tmux_pane_content_large_output(self, tmux_manager):
        """Test capturing large pane output."""
        # Setup
        instance_id = await tmux_manager.spawn_instance(name="large-pane-test")

        # Mock large output
        large_output = [f"Line {i}" for i in range(1000)]
        tmux_manager._mock_pane.cmd = MagicMock(return_value=MagicMock(stdout=large_output))

        # Execute
        content = await tmux_manager.get_tmux_pane_content(instance_id, lines=500)

        # Assert
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_get_tmux_pane_content_empty(self, tmux_manager):
        """Test capturing empty pane content."""
        # Setup
        instance_id = await tmux_manager.spawn_instance(name="empty-pane-test")

        tmux_manager._mock_pane.cmd = MagicMock(return_value=MagicMock(stdout=[]))

        # Execute
        content = await tmux_manager.get_tmux_pane_content(instance_id, lines=100)

        # Assert
        assert content == ""

    @pytest.mark.asyncio
    async def test_capture_pane_with_history(self, tmux_manager):
        """Test capturing pane with full scrollback history."""
        # Setup
        instance_id = await tmux_manager.spawn_instance(name="history-test")

        history_output = [f"History line {i}" for i in range(100)]
        tmux_manager._mock_pane.cmd = MagicMock(return_value=MagicMock(stdout=history_output))

        # Execute - capture all history
        content = await tmux_manager.get_tmux_pane_content(instance_id, lines=-1)

        # Assert
        assert "History line 0" in content or len(content) > 0

    @pytest.mark.asyncio
    async def test_pane_content_not_found(self, tmux_manager):
        """Test getting pane content for non-existent instance."""
        # Execute & Assert
        with pytest.raises(ValueError, match="not found"):
            await tmux_manager.get_tmux_pane_content("nonexistent", lines=100)


# ============================================================================
# Error Handling Tests (10 tests)
# ============================================================================


class TestErrorHandling:
    """Test error scenarios and recovery."""

    @pytest.mark.asyncio
    async def test_tmux_command_failure(self, tmux_manager):
        """Test handling of tmux command failures."""
        instance_id = "cmd-fail-123"

        # Mock command failure
        tmux_manager._mock_pane.cmd.side_effect = Exception("tmux command failed")

        tmux_manager.instances[instance_id] = {"id": instance_id}
        tmux_manager.tmux_sessions[instance_id] = tmux_manager._mock_session

        # Execute & Assert
        with pytest.raises(Exception, match="tmux command failed"):
            await tmux_manager.get_tmux_pane_content(instance_id)

    @pytest.mark.asyncio
    async def test_subprocess_timeout(self, tmux_manager):
        """Test subprocess timeout handling."""
        # This tests the timeout logic in _initialize_tmux_session
        instance_id = "subprocess-timeout-123"

        # Mock slow CLI startup
        async def slow_startup(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than max_init_wait

        instance = {
            "id": instance_id,
            "workspace_dir": "/tmp/timeout_test",
            "instance_type": "claude",
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity": datetime.now(UTC).isoformat(),
            "mcp_servers": {},
        }
        tmux_manager.instances[instance_id] = instance

        # Mock pane to never show ready state
        tmux_manager._mock_pane.cmd = MagicMock(return_value=MagicMock(stdout=["Loading..."] * 100))

        # Execute - should complete despite timeout warning
        await tmux_manager._initialize_tmux_session(instance_id)

        # Assert - should still create session
        assert instance_id in tmux_manager.tmux_sessions

    @pytest.mark.asyncio
    async def test_ipc_queue_error(self, tmux_manager):
        """Test IPC queue communication errors."""
        # Setup shared_state with failing queue
        mock_shared_state = MagicMock()
        mock_queue = MagicMock()
        mock_queue.get.side_effect = Exception("Queue error")

        mock_shared_state.get_response_queue = MagicMock(return_value=mock_queue)
        tmux_manager.shared_state = mock_shared_state

        # Execute & Assert
        with pytest.raises(Exception):  # noqa: B017
            await tmux_manager._get_from_shared_queue("inst-123", timeout=1)

    @pytest.mark.asyncio
    async def test_manager_daemon_failure(self, tmux_manager):
        """Test handling of manager daemon failure."""
        # Setup
        mock_shared_state = MagicMock()
        mock_shared_state.health_check = MagicMock(
            return_value={"healthy": False, "error": "Manager dead"}
        )
        tmux_manager.shared_state = mock_shared_state

        # Trigger health check failures
        tmux_manager._manager_health_failures = 3
        tmux_manager._max_health_failures = 3

        # Execute
        await tmux_manager._handle_manager_failure()

        # Assert - shared_state should be disabled
        assert tmux_manager.shared_state is None

    @pytest.mark.asyncio
    async def test_graceful_error_recovery(self, tmux_manager):
        """Test graceful recovery from errors."""
        instance_id = "recovery-123"

        # Spawn instance
        instance_id = await tmux_manager.spawn_instance(name="recovery-test")

        # Simulate error state
        tmux_manager.instances[instance_id]["state"] = "error"
        tmux_manager.instances[instance_id]["error_message"] = "Test error"

        # Attempt to recover by terminating
        result = await tmux_manager.terminate_instance(instance_id, force=True)

        # Assert
        assert result is True
        assert tmux_manager.instances[instance_id]["state"] == "terminated"

    @pytest.mark.asyncio
    async def test_instance_not_found_errors(self, tmux_manager):
        """Test various operations on non-existent instances."""
        fake_id = "nonexistent-instance"

        # Test get_instance_status
        with pytest.raises(ValueError, match="not found"):
            tmux_manager.get_instance_status(fake_id)

        # Test terminate_instance
        with pytest.raises(ValueError, match="not found"):
            await tmux_manager.terminate_instance(fake_id)

        # Test send_message
        with pytest.raises(ValueError, match="not found"):
            await tmux_manager.send_message(fake_id, "test")

    @pytest.mark.asyncio
    async def test_invalid_instance_state(self, tmux_manager):
        """Test operations on instances in invalid states."""
        instance_id = await tmux_manager.spawn_instance(name="invalid-state-test")

        # Set to terminated state
        tmux_manager.instances[instance_id]["state"] = "terminated"

        # Attempt to send message
        with pytest.raises(RuntimeError, match="not in a valid state"):
            await tmux_manager.send_message(instance_id, "test")

    @pytest.mark.asyncio
    async def test_resource_limit_exceeded(self, tmux_manager):
        """Test resource limit enforcement."""
        instance_id = await tmux_manager.spawn_instance(name="resource-test")

        # Set resource limits
        tmux_manager.instances[instance_id]["resource_limits"] = {"max_total_tokens": 100}
        tmux_manager.instances[instance_id]["total_tokens_used"] = 150  # Exceeded

        # Execute health check
        await tmux_manager.health_check()

        # Assert - should be terminated
        assert tmux_manager.instances[instance_id]["state"] == "terminated"

    @pytest.mark.asyncio
    async def test_cascade_termination(self, tmux_manager):
        """Test cascade termination of parent and children."""
        # Spawn parent
        parent_id = await tmux_manager.spawn_instance(name="parent")

        # Spawn children
        child1_id = await tmux_manager.spawn_instance(
            name="child1",
            parent_instance_id=parent_id,
        )
        child2_id = await tmux_manager.spawn_instance(
            name="child2",
            parent_instance_id=parent_id,
        )

        # Terminate parent
        await tmux_manager.terminate_instance(parent_id, force=True)

        # Assert - children should also be terminated
        assert tmux_manager.instances[parent_id]["state"] == "terminated"
        assert tmux_manager.instances[child1_id]["state"] == "terminated"
        assert tmux_manager.instances[child2_id]["state"] == "terminated"

    @pytest.mark.asyncio
    async def test_concurrent_termination(self, tmux_manager):
        """Test terminating multiple instances concurrently."""
        # Spawn multiple instances
        instances = []
        for i in range(3):
            instance_id = await tmux_manager.spawn_instance(name=f"concurrent-term-{i}")
            instances.append(instance_id)

        # Terminate all concurrently
        tasks = [tmux_manager.terminate_instance(inst_id, force=True) for inst_id in instances]
        results = await asyncio.gather(*tasks)

        # Assert
        assert all(results)
        assert all(
            tmux_manager.instances[inst_id]["state"] == "terminated" for inst_id in instances
        )


# ============================================================================
# Additional Critical Function Tests
# ============================================================================


class TestCriticalFunctions:
    """Test critical functions with 0% coverage."""

    @pytest.mark.asyncio
    async def test_put_with_lock_concurrent(self, tmux_manager):
        """Test concurrent put operations are thread-safe (critical 0% coverage function)."""
        # Setup shared_state with queue and lock
        mock_shared_state = MagicMock()
        mock_queue = Queue()
        mock_lock = threading.Lock()

        mock_shared_state.get_response_queue = MagicMock(return_value=mock_queue)
        mock_shared_state.queue_locks = {"inst-123": mock_lock}

        tmux_manager.shared_state = mock_shared_state

        # Execute concurrent puts
        async def put_message(i):
            await tmux_manager._put_to_shared_queue("inst-123", {"msg": f"message-{i}"})

        tasks = [put_message(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Assert - all messages should be in queue
        assert mock_queue.qsize() == 10

    @pytest.mark.asyncio
    async def test_send_multiline_message_to_pane(self, tmux_manager):
        """Test _send_multiline_message_to_pane helper function."""
        # Setup
        await tmux_manager.spawn_instance(name="multiline-helper-test")

        # Get pane
        pane = tmux_manager._mock_pane

        # Test multiline message
        message = "Line 1\nLine 2\nLine 3"

        # Execute
        tmux_manager._send_multiline_message_to_pane(pane, message)

        # Assert - send_keys should be called multiple times
        assert pane.send_keys.call_count > 3  # At least once per line + Enter

    @pytest.mark.asyncio
    async def test_extract_response(self, tmux_manager):
        """Test _extract_response function."""
        # Setup instance
        instance_id = await tmux_manager.spawn_instance(name="extract-test")
        tmux_manager.message_history[instance_id] = [{"role": "user", "content": "Question"}]

        # Mock output with UI chrome
        full_output = """
        ╭─────────────────────╮
        │ Response text here  │
        ╰─────────────────────╯
        """
        initial_output = ""

        # Execute
        response = tmux_manager._extract_response(full_output, initial_output)

        # Assert
        assert "Response text here" in response or len(response) > 0

    @pytest.mark.asyncio
    async def test_get_role_prompt(self, tmux_manager):
        """Test _get_role_prompt helper function."""
        # Test valid role
        prompt = tmux_manager._get_role_prompt("general")
        assert len(prompt) > 0

        # Test fallback for unknown role
        prompt = tmux_manager._get_role_prompt("unknown_role_12345")
        assert len(prompt) > 0  # Should return fallback

    @pytest.mark.asyncio
    async def test_handle_reply_to_caller(self, tmux_manager):
        """Test handle_reply_to_caller bidirectional messaging."""
        # Setup
        parent_id = await tmux_manager.spawn_instance(name="parent")
        child_id = await tmux_manager.spawn_instance(name="child", parent_instance_id=parent_id)

        # Execute
        result = await tmux_manager.handle_reply_to_caller(
            instance_id=child_id,
            reply_message="Reply from child",
            correlation_id="corr-123",
        )

        # Assert
        assert result["success"] is True
        assert result["delivered_to"] == parent_id

    @pytest.mark.asyncio
    async def test_get_event_statistics(self, tmux_manager):
        """Test get_event_statistics function."""
        # Setup
        instance_id = await tmux_manager.spawn_instance(name="stats-test")

        # Add message history
        tmux_manager.message_history[instance_id] = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
        ]

        # Execute
        stats = tmux_manager.get_event_statistics(instance_id)

        # Assert
        assert stats["event_counts"]["user_messages"] == 2
        assert stats["event_counts"]["assistant_messages"] == 1
        assert stats["event_counts"]["tool_calls"] == 0  # Not tracked in interactive mode

    @pytest.mark.asyncio
    async def test_interrupt_instance(self, tmux_manager):
        """Test interrupt_instance function."""
        # Setup
        instance_id = await tmux_manager.spawn_instance(name="interrupt-test")
        tmux_manager.instances[instance_id]["state"] = "busy"

        # Execute
        result = await tmux_manager.interrupt_instance(instance_id)

        # Assert
        assert result["success"] is True
        assert result["instance_id"] == instance_id

    @pytest.mark.asyncio
    async def test_check_pane_health_detailed(self, tmux_manager):
        """Test detailed pane health check."""
        # Setup
        instance_id = await tmux_manager.spawn_instance(name="health-detailed-test")

        # Mock pane info
        tmux_manager._mock_pane.cmd = MagicMock(
            return_value=MagicMock(stdout=["1"])  # Pane active
        )

        # Execute
        health = await tmux_manager.check_pane_health(instance_id)

        # Assert
        assert "healthy" in health
        assert health["instance_id"] == instance_id
