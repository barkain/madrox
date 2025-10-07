"""Tests for Claude CLI event parsing in TmuxInstanceManager."""

import json
from datetime import UTC, datetime

import pytest

from src.orchestrator.tmux_instance_manager import TmuxInstanceManager


class TestCLIEventParsing:
    """Test suite for CLI event parsing functionality."""

    @pytest.fixture
    def manager(self):
        """Create a TmuxInstanceManager for testing."""
        config = {
            "workspace_base_dir": "/tmp/test_madrox",
            "max_concurrent_instances": 5,
        }
        return TmuxInstanceManager(config)

    def test_parse_tool_use_event(self, manager):
        """Test parsing a tool_use event."""
        event_json = json.dumps(
            {
                "type": "tool_use",
                "name": "Bash",
                "tool_use_id": "toolu_123abc",
                "input": {"command": "ls -la"},
            }
        )

        result = manager._parse_cli_output(event_json)

        assert result is not None
        assert result["type"] == "tool_use"
        assert result["name"] == "Bash"
        assert result["tool_use_id"] == "toolu_123abc"
        assert result["input"]["command"] == "ls -la"
        assert "timestamp" in result

    def test_parse_tool_result_event(self, manager):
        """Test parsing a tool_result event."""
        event_json = json.dumps(
            {
                "type": "tool_result",
                "tool_use_id": "toolu_123abc",
                "content": "file1.txt\nfile2.txt",
                "is_error": False,
            }
        )

        result = manager._parse_cli_output(event_json)

        assert result is not None
        assert result["type"] == "tool_result"
        assert result["tool_use_id"] == "toolu_123abc"
        assert result["content"] == "file1.txt\nfile2.txt"
        assert result["is_error"] is False
        assert "timestamp" in result

    def test_parse_text_event(self, manager):
        """Test parsing a text event."""
        event_json = json.dumps({"type": "text", "text": "I'm thinking about this..."})

        result = manager._parse_cli_output(event_json)

        assert result is not None
        assert result["type"] == "text"
        assert result["text"] == "I'm thinking about this..."
        assert "timestamp" in result

    def test_parse_invalid_json(self, manager):
        """Test parsing invalid JSON returns None."""
        invalid_json = "This is not JSON"

        result = manager._parse_cli_output(invalid_json)

        assert result is None

    def test_parse_non_event_json(self, manager):
        """Test parsing JSON without 'type' field returns None."""
        non_event_json = json.dumps({"some": "data", "but": "no type"})

        result = manager._parse_cli_output(non_event_json)

        assert result is None

    def test_parse_empty_line(self, manager):
        """Test parsing empty line returns None."""
        result = manager._parse_cli_output("")

        assert result is None

    def test_get_event_statistics_empty_history(self, manager):
        """Test getting event statistics for instance with no history."""
        stats = manager.get_event_statistics("nonexistent-instance")

        assert stats["instance_id"] == "nonexistent-instance"
        assert "error" in stats
        assert stats["total_events"] == 0

    def test_get_event_statistics_with_events(self, manager):
        """Test getting event statistics with various event types."""
        instance_id = "test-instance-123"
        manager.message_history[instance_id] = [
            {"role": "user", "content": "Hello", "timestamp": datetime.now(UTC).isoformat()},
            {"role": "tool_call", "tool": "Bash", "timestamp": datetime.now(UTC).isoformat()},
            {
                "role": "tool_result",
                "content": "output",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            {"role": "tool_call", "tool": "Read", "timestamp": datetime.now(UTC).isoformat()},
            {
                "role": "tool_result",
                "content": "file contents",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            {
                "role": "assistant",
                "content": "Here you go",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            {"role": "tool_call", "tool": "Bash", "timestamp": datetime.now(UTC).isoformat()},
        ]

        stats = manager.get_event_statistics(instance_id)

        assert stats["instance_id"] == instance_id
        assert stats["total_events"] == 7
        assert stats["event_counts"]["user_messages"] == 1
        assert stats["event_counts"]["assistant_messages"] == 1
        assert stats["event_counts"]["tool_calls"] == 3
        assert stats["event_counts"]["tool_results"] == 2
        assert stats["tools_used"]["Bash"] == 2
        assert stats["tools_used"]["Read"] == 1

    def test_timestamp_added_to_parsed_events(self, manager):
        """Test that timestamps are automatically added to parsed events."""
        event_json = json.dumps({"type": "tool_use", "name": "Grep", "tool_use_id": "toolu_xyz"})

        before = datetime.now(UTC)
        result = manager._parse_cli_output(event_json)
        after = datetime.now(UTC)

        assert result is not None
        assert "timestamp" in result

        # Verify timestamp is in ISO format and within expected range
        timestamp = datetime.fromisoformat(result["timestamp"])
        assert before <= timestamp <= after
