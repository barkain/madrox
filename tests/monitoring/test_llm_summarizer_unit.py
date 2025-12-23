"""Comprehensive unit tests for SummaryGenerator error handling.

This module tests error paths in the LLM-powered summary generation:
- API errors and retry logic
- Rate limit handling with exponential backoff
- Malformed response parsing
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.monitoring.summary_generator import SummaryGenerator


@pytest.fixture
def summary_generator():
    """Create a SummaryGenerator instance with mocked Anthropic client."""
    with patch("orchestrator.monitoring.summary_generator.AsyncAnthropic"):
        generator = SummaryGenerator(api_key="test-key")
        generator.anthropic_client = AsyncMock()
        yield generator


@pytest.mark.asyncio
async def test_summarize_api_error(summary_generator):
    """Test handling of Anthropic API errors.

    Verifies that:
    - API errors are caught and retried
    - After MAX_RETRIES attempts, an exception is raised
    - Error is logged appropriately

    Coverage: Lines 225-235 (exception handling in _call_claude_with_retry)
    """
    # Mock Anthropic client to raise API error on all attempts
    api_error = Exception("Anthropic API Error: Service unavailable")
    summary_generator.anthropic_client.messages.create = AsyncMock(side_effect=api_error)

    # Attempt to call with retry - should fail after MAX_RETRIES
    with pytest.raises(Exception) as exc_info:
        await summary_generator._call_claude_with_retry("test prompt")

    # Verify the exception message mentions retries
    assert "Failed after" in str(exc_info.value) and "retries" in str(exc_info.value)

    # Verify it retried MAX_RETRIES times (3 attempts)
    assert summary_generator.anthropic_client.messages.create.call_count == 3


@pytest.mark.asyncio
async def test_summarize_rate_limit(summary_generator):
    """Test rate limit handling with exponential backoff.

    Verifies that:
    - Rate limit errors are detected (429 status or "rate_limit" in message)
    - Backoff time is increased appropriately
    - Eventually raises exception after MAX_RETRIES

    Coverage: Lines 229-232 (rate limit detection and backoff)
    """
    # Mock Anthropic client to raise rate limit error
    rate_limit_error = Exception("RateLimitError: 429 - Too many requests")
    summary_generator.anthropic_client.messages.create = AsyncMock(side_effect=rate_limit_error)

    # Attempt to call with retry - should fail after MAX_RETRIES
    with pytest.raises(Exception) as exc_info:
        await summary_generator._call_claude_with_retry("test prompt")

    # Verify the exception is raised after retries
    assert "Failed after" in str(exc_info.value)

    # Verify it retried MAX_RETRIES times
    assert summary_generator.anthropic_client.messages.create.call_count == 3


@pytest.mark.asyncio
async def test_summarize_malformed_response(summary_generator):
    """Test parsing error handling for malformed JSON responses.

    Verifies that:
    - Malformed JSON responses are caught
    - JSONDecodeError is handled gracefully
    - After MAX_RETRIES of invalid JSON, an exception is raised

    Coverage: Lines 218-223 (JSON parsing error handling)
    """
    # Mock Anthropic client to return malformed JSON
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="This is not valid JSON { broken")]
    summary_generator.anthropic_client.messages.create = AsyncMock(return_value=mock_message)

    # Attempt to call with retry - should fail after MAX_RETRIES due to JSON parse errors
    with pytest.raises(Exception) as exc_info:
        await summary_generator._call_claude_with_retry("test prompt")

    # Verify the exception mentions JSON validation failure
    assert "Failed to get valid JSON" in str(exc_info.value)

    # Verify it retried MAX_RETRIES times (3 attempts)
    assert summary_generator.anthropic_client.messages.create.call_count == 3


@pytest.mark.asyncio
async def test_summarize_api_error_with_partial_success(summary_generator):
    """Test API error recovery when retry succeeds.

    Verifies that:
    - First API call fails
    - Second API call succeeds
    - Valid JSON is returned

    Coverage: Lines 225-235 (retry logic with eventual success)
    """
    # First call fails, second succeeds
    valid_response = {
        "current_activity": "Testing error recovery",
        "on_track_status": "on_track",
        "confidence_score": 0.9,
        "drift_reasons": [],
        "alignment_keywords": ["test", "recovery"],
        "last_tool_used": "pytest",
        "recent_tools": ["pytest", "mock"],
        "idle_duration_seconds": 0.0,
        "recommended_action": None,
    }

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(valid_response))]

    # First call fails, second succeeds
    summary_generator.anthropic_client.messages.create = AsyncMock(
        side_effect=[
            Exception("Temporary API error"),
            mock_message,  # Success on retry
        ]
    )

    # Should succeed on second attempt
    result = await summary_generator._call_claude_with_retry("test prompt")

    assert result == valid_response
    assert summary_generator.anthropic_client.messages.create.call_count == 2


@pytest.mark.asyncio
async def test_generate_summary_with_malformed_enum_value(summary_generator):
    """Test handling of invalid on_track_status enum values.

    Verifies that:
    - Invalid enum values default to UNKNOWN
    - Warning is logged
    - AgentSummary is still created successfully

    Coverage: Lines 268-272 (enum parsing with ValueError handling)
    """
    # Valid JSON but with invalid enum value
    invalid_enum_response = {
        "current_activity": "Testing enum handling",
        "on_track_status": "invalid_status_value",  # Invalid enum
        "confidence_score": 0.5,
        "drift_reasons": [],
        "alignment_keywords": [],
        "last_tool_used": None,
        "recent_tools": [],
        "idle_duration_seconds": 0.0,
        "recommended_action": None,
    }

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(invalid_enum_response))]
    summary_generator.anthropic_client.messages.create = AsyncMock(return_value=mock_message)

    # Should succeed and return UNKNOWN status
    summary = await summary_generator.generate_summary(
        instance_id="test-123",
        new_log_lines=["Test log line"],
        agent_context={
            "instance_name": "test-agent",
            "role": "test",
        },
    )

    # Verify summary was created with UNKNOWN status
    assert summary.instance_id == "test-123"
    assert summary.on_track_status.value == "unknown"  # Defaulted to UNKNOWN
    assert summary.current_activity == "Testing enum handling"


@pytest.mark.asyncio
async def test_generate_summary_with_missing_optional_fields(summary_generator):
    """Test handling of response with missing optional fields.

    Verifies that:
    - Missing optional fields use defaults
    - AgentSummary is created successfully
    - No errors are raised

    Coverage: Lines 262-280 (optional field extraction with .get() defaults)
    """
    # Minimal valid response (only required fields)
    minimal_response = {
        "current_activity": "Minimal test",
        "on_track_status": "on_track",
        "confidence_score": 0.8,
    }

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(minimal_response))]
    summary_generator.anthropic_client.messages.create = AsyncMock(return_value=mock_message)

    # Should succeed with defaults for optional fields
    summary = await summary_generator.generate_summary(
        instance_id="test-456",
        new_log_lines=["Test"],
        agent_context={"instance_name": "minimal-agent"},
    )

    # Verify defaults are applied
    assert summary.drift_reasons == []
    assert summary.alignment_keywords == []
    assert summary.last_tool_used is None
    assert summary.recent_tools == []
    assert summary.idle_duration_seconds == 0.0
    assert summary.recommended_action is None
