"""Tests for summary_generator.py - LLM-powered agent summary generation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.monitoring.models import AgentSummary, OnTrackStatus
from orchestrator.monitoring.summary_generator import SummaryGenerator


@pytest.fixture
def mock_anthropic_client():
    """Create a mock AsyncAnthropic client."""
    with patch("orchestrator.monitoring.summary_generator.AsyncAnthropic") as mock_class:
        mock_client = MagicMock()
        mock_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_agent_context():
    """Sample agent context dictionary."""
    return {
        "instance_name": "test-agent",
        "role": "backend_engineer",
        "assigned_task": "Implement user authentication",
        "parent_instance_id": "supervisor-123",
    }


@pytest.fixture
def sample_log_lines():
    """Sample log lines from agent output."""
    return [
        "⏺ Read(/app/auth/models.py)",
        "⏺ Read(/app/auth/views.py)",
        "⏺ Write(/app/auth/authentication.py)",
        "✓ Created authentication module",
        "⏺ Bash(pytest tests/test_auth.py)",
        "  ⎿ 5 passed in 2.3s",
    ]


@pytest.fixture
def sample_claude_response():
    """Sample JSON response from Claude."""
    return {
        "current_activity": "Implementing user authentication module with tests passing.",
        "on_track_status": "on_track",
        "confidence_score": 0.9,
        "drift_reasons": [],
        "alignment_keywords": ["authentication", "auth", "user", "tests"],
        "last_tool_used": "Bash",
        "recent_tools": ["Read", "Write", "Bash"],
        "idle_duration_seconds": 0.0,
        "recommended_action": None,
    }


@pytest.mark.asyncio
async def test_generate_summary_success(
    mock_anthropic_client, sample_agent_context, sample_log_lines, sample_claude_response
):
    """Test successful summary generation."""
    # Setup mock response
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(sample_claude_response))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

    # Create generator
    generator = SummaryGenerator(api_key="test-key")
    generator.anthropic_client = mock_anthropic_client

    # Generate summary
    summary = await generator.generate_summary(
        instance_id="test-123",
        new_log_lines=sample_log_lines,
        agent_context=sample_agent_context,
    )

    # Assertions
    assert isinstance(summary, AgentSummary)
    assert summary.instance_id == "test-123"
    assert summary.instance_name == "test-agent"
    assert summary.current_activity == "Implementing user authentication module with tests passing."
    assert summary.on_track_status == OnTrackStatus.ON_TRACK
    assert summary.confidence_score == 0.9
    assert summary.assigned_task == "Implement user authentication"
    assert summary.parent_instance_id == "supervisor-123"
    assert summary.role == "backend_engineer"
    assert summary.last_tool_used == "Bash"
    assert summary.recent_tools == ["Read", "Write", "Bash"]
    assert summary.idle_duration_seconds == 0.0
    assert summary.drift_reasons == []
    assert "authentication" in summary.alignment_keywords
    assert summary.recommended_action is None


@pytest.mark.asyncio
async def test_generate_summary_drifting_status(
    mock_anthropic_client, sample_agent_context, sample_log_lines
):
    """Test summary with drifting status."""
    drifting_response = {
        "current_activity": "Refactoring database models instead of implementing auth.",
        "on_track_status": "drifting",
        "confidence_score": 0.7,
        "drift_reasons": ["Working on database refactor, not assigned task"],
        "alignment_keywords": ["database", "models"],
        "last_tool_used": "Edit",
        "recent_tools": ["Read", "Edit"],
        "idle_duration_seconds": 5.0,
        "recommended_action": "Check if agent needs task clarification",
    }

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(drifting_response))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

    generator = SummaryGenerator(api_key="test-key")
    generator.anthropic_client = mock_anthropic_client

    summary = await generator.generate_summary(
        instance_id="test-123",
        new_log_lines=sample_log_lines,
        agent_context=sample_agent_context,
    )

    assert summary.on_track_status == OnTrackStatus.DRIFTING
    assert summary.confidence_score == 0.7
    assert len(summary.drift_reasons) > 0
    assert "database refactor" in summary.drift_reasons[0]
    assert summary.recommended_action is not None


@pytest.mark.asyncio
async def test_generate_summary_blocked_status(mock_anthropic_client, sample_agent_context):
    """Test summary with blocked status."""
    blocked_response = {
        "current_activity": "Stuck waiting for test dependencies to install.",
        "on_track_status": "blocked",
        "confidence_score": 0.85,
        "drift_reasons": ["Dependency installation hanging"],
        "alignment_keywords": ["tests", "dependencies"],
        "last_tool_used": "Bash",
        "recent_tools": ["Bash"],
        "idle_duration_seconds": 120.0,
        "recommended_action": "Investigate dependency installation issue",
    }

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(blocked_response))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

    generator = SummaryGenerator(api_key="test-key")
    generator.anthropic_client = mock_anthropic_client

    summary = await generator.generate_summary(
        instance_id="test-123",
        new_log_lines=["⏺ Bash(pip install pytest)", "  ⎿ (hanging...)"],
        agent_context=sample_agent_context,
    )

    assert summary.on_track_status == OnTrackStatus.BLOCKED
    assert summary.idle_duration_seconds == 120.0
    assert summary.recommended_action is not None
    assert "Investigate" in summary.recommended_action


@pytest.mark.asyncio
async def test_generate_summary_unknown_status(mock_anthropic_client, sample_agent_context):
    """Test summary with unknown status."""
    unknown_response = {
        "current_activity": "Insufficient output to determine current activity.",
        "on_track_status": "unknown",
        "confidence_score": 0.3,
        "drift_reasons": [],
        "alignment_keywords": [],
        "last_tool_used": None,
        "recent_tools": [],
        "idle_duration_seconds": 0.0,
        "recommended_action": None,
    }

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(unknown_response))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

    generator = SummaryGenerator(api_key="test-key")
    generator.anthropic_client = mock_anthropic_client

    summary = await generator.generate_summary(
        instance_id="test-123",
        new_log_lines=[],
        agent_context=sample_agent_context,
    )

    assert summary.on_track_status == OnTrackStatus.UNKNOWN
    assert summary.confidence_score == 0.3


@pytest.mark.asyncio
async def test_prompt_construction(mock_anthropic_client, sample_agent_context, sample_log_lines):
    """Test that prompt is constructed correctly."""
    mock_message = MagicMock()
    mock_message.content = [
        MagicMock(
            text=json.dumps(
                {
                    "current_activity": "Test",
                    "on_track_status": "on_track",
                    "confidence_score": 0.5,
                    "drift_reasons": [],
                    "alignment_keywords": [],
                    "last_tool_used": None,
                    "recent_tools": [],
                    "idle_duration_seconds": 0.0,
                    "recommended_action": None,
                }
            )
        )
    ]
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

    generator = SummaryGenerator(api_key="test-key")
    generator.anthropic_client = mock_anthropic_client

    await generator.generate_summary(
        instance_id="test-123",
        new_log_lines=sample_log_lines,
        agent_context=sample_agent_context,
    )

    # Verify API was called
    assert mock_anthropic_client.messages.create.called
    call_args = mock_anthropic_client.messages.create.call_args

    # Check prompt contains key elements
    messages = call_args.kwargs["messages"]
    prompt = messages[0]["content"]

    assert "test-123" in prompt
    assert "backend_engineer" in prompt
    assert "Implement user authentication" in prompt
    assert "Read(/app/auth/models.py)" in prompt


@pytest.mark.asyncio
async def test_invalid_json_response_retry(
    mock_anthropic_client, sample_agent_context, sample_log_lines
):
    """Test retry logic when Claude returns invalid JSON."""
    # First call returns invalid JSON, second call succeeds
    valid_response = {
        "current_activity": "Working on task",
        "on_track_status": "on_track",
        "confidence_score": 0.8,
        "drift_reasons": [],
        "alignment_keywords": ["test"],
        "last_tool_used": None,
        "recent_tools": [],
        "idle_duration_seconds": 0.0,
        "recommended_action": None,
    }

    mock_message_invalid = MagicMock()
    mock_message_invalid.content = [MagicMock(text="Invalid JSON {")]

    mock_message_valid = MagicMock()
    mock_message_valid.content = [MagicMock(text=json.dumps(valid_response))]

    mock_anthropic_client.messages.create = AsyncMock(
        side_effect=[mock_message_invalid, mock_message_valid]
    )

    generator = SummaryGenerator(api_key="test-key")
    generator.anthropic_client = mock_anthropic_client

    summary = await generator.generate_summary(
        instance_id="test-123",
        new_log_lines=sample_log_lines,
        agent_context=sample_agent_context,
    )

    # Should succeed on retry
    assert summary.on_track_status == OnTrackStatus.ON_TRACK
    assert mock_anthropic_client.messages.create.call_count == 2


@pytest.mark.asyncio
async def test_max_retries_exceeded(mock_anthropic_client, sample_agent_context, sample_log_lines):
    """Test that exception is raised after max retries."""
    mock_message_invalid = MagicMock()
    mock_message_invalid.content = [MagicMock(text="Invalid JSON {")]

    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message_invalid)

    generator = SummaryGenerator(api_key="test-key")
    generator.anthropic_client = mock_anthropic_client

    with pytest.raises(Exception, match="Failed to get valid JSON"):
        await generator.generate_summary(
            instance_id="test-123",
            new_log_lines=sample_log_lines,
            agent_context=sample_agent_context,
        )

    # Should have tried MAX_RETRIES times
    assert mock_anthropic_client.messages.create.call_count == 3


@pytest.mark.asyncio
async def test_rate_limit_handling(mock_anthropic_client, sample_agent_context, sample_log_lines):
    """Test rate limit error handling with backoff."""
    valid_response = {
        "current_activity": "Working",
        "on_track_status": "on_track",
        "confidence_score": 0.8,
        "drift_reasons": [],
        "alignment_keywords": [],
        "last_tool_used": None,
        "recent_tools": [],
        "idle_duration_seconds": 0.0,
        "recommended_action": None,
    }

    # First call rate limited, second succeeds
    rate_limit_error = Exception("rate_limit_error: 429 Too Many Requests")
    mock_message_valid = MagicMock()
    mock_message_valid.content = [MagicMock(text=json.dumps(valid_response))]

    mock_anthropic_client.messages.create = AsyncMock(
        side_effect=[rate_limit_error, mock_message_valid]
    )

    generator = SummaryGenerator(api_key="test-key")
    generator.anthropic_client = mock_anthropic_client

    summary = await generator.generate_summary(
        instance_id="test-123",
        new_log_lines=sample_log_lines,
        agent_context=sample_agent_context,
    )

    # Should succeed after retry
    assert summary.on_track_status == OnTrackStatus.ON_TRACK
    assert mock_anthropic_client.messages.create.call_count == 2


@pytest.mark.asyncio
async def test_empty_log_lines(mock_anthropic_client, sample_agent_context):
    """Test handling of empty log lines."""
    response = {
        "current_activity": "No recent activity detected.",
        "on_track_status": "unknown",
        "confidence_score": 0.2,
        "drift_reasons": [],
        "alignment_keywords": [],
        "last_tool_used": None,
        "recent_tools": [],
        "idle_duration_seconds": 0.0,
        "recommended_action": None,
    }

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(response))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

    generator = SummaryGenerator(api_key="test-key")
    generator.anthropic_client = mock_anthropic_client

    summary = await generator.generate_summary(
        instance_id="test-123",
        new_log_lines=[],
        agent_context=sample_agent_context,
    )

    assert summary.on_track_status == OnTrackStatus.UNKNOWN


@pytest.mark.asyncio
async def test_invalid_on_track_status(
    mock_anthropic_client, sample_agent_context, sample_log_lines
):
    """Test handling of invalid on_track_status value."""
    response = {
        "current_activity": "Working",
        "on_track_status": "invalid_status",  # Invalid
        "confidence_score": 0.5,
        "drift_reasons": [],
        "alignment_keywords": [],
        "last_tool_used": None,
        "recent_tools": [],
        "idle_duration_seconds": 0.0,
        "recommended_action": None,
    }

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(response))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

    generator = SummaryGenerator(api_key="test-key")
    generator.anthropic_client = mock_anthropic_client

    summary = await generator.generate_summary(
        instance_id="test-123",
        new_log_lines=sample_log_lines,
        agent_context=sample_agent_context,
    )

    # Should default to UNKNOWN
    assert summary.on_track_status == OnTrackStatus.UNKNOWN


@pytest.mark.asyncio
async def test_confidence_score_range(
    mock_anthropic_client, sample_agent_context, sample_log_lines
):
    """Test confidence scores across range 0.0-1.0."""
    for score in [0.0, 0.25, 0.5, 0.75, 1.0]:
        response = {
            "current_activity": "Testing",
            "on_track_status": "on_track",
            "confidence_score": score,
            "drift_reasons": [],
            "alignment_keywords": [],
            "last_tool_used": None,
            "recent_tools": [],
            "idle_duration_seconds": 0.0,
            "recommended_action": None,
        }

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(response))]
        mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

        generator = SummaryGenerator(api_key="test-key")
        generator.anthropic_client = mock_anthropic_client

        summary = await generator.generate_summary(
            instance_id="test-123",
            new_log_lines=sample_log_lines,
            agent_context=sample_agent_context,
        )

        assert summary.confidence_score == score


@pytest.mark.asyncio
async def test_model_parameter(mock_anthropic_client, sample_agent_context, sample_log_lines):
    """Test custom model parameter."""
    response = {
        "current_activity": "Testing",
        "on_track_status": "on_track",
        "confidence_score": 0.8,
        "drift_reasons": [],
        "alignment_keywords": [],
        "last_tool_used": None,
        "recent_tools": [],
        "idle_duration_seconds": 0.0,
        "recommended_action": None,
    }

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(response))]
    mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

    # Test custom model
    generator = SummaryGenerator(api_key="test-key", model="claude-opus-4")
    generator.anthropic_client = mock_anthropic_client

    await generator.generate_summary(
        instance_id="test-123",
        new_log_lines=sample_log_lines,
        agent_context=sample_agent_context,
    )

    call_args = mock_anthropic_client.messages.create.call_args
    assert call_args.kwargs["model"] == "claude-opus-4"
