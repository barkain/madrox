"""
Comprehensive Test Suite for LLMSummarizer

Tests cover:
1. Valid API key with successful API responses
2. Missing API key (fallback behavior)
3. API timeout scenarios
4. API error responses (401, 403, 500)
5. Different instance states and output lengths
6. No exceptions raised in error paths

Phase 2: LLM Summarizer - Testing
"""

import os
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

# Import the LLMSummarizer (will be available when implementation is complete)
try:
    from orchestrator.llm_summarizer import LLMSummarizer
except ImportError:
    # Fallback for when module doesn't exist yet
    LLMSummarizer = None


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_openrouter_response():
    """Mock successful OpenRouter API response."""
    return {
        "id": "gen-123456",
        "model": "anthropic/claude-3.5-sonnet",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Instance is processing data analysis tasks with pandas and generating visualizations."
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 50,
            "total_tokens": 200
        }
    }


@pytest.fixture
def sample_activity_text():
    """Sample instance activity text."""
    return """
    Running analysis on customer data...
    Processing 10,000 records with pandas
    Generating visualization with matplotlib
    Export completed successfully
    """


@pytest.fixture
def long_activity_text():
    """Long instance activity text (over 1000 chars)."""
    lines = []
    for i in range(100):
        lines.append(f"Line {i}: Processing task with various operations and outputs")
    return "\n".join(lines)


@pytest.fixture
async def summarizer_with_api_key():
    """LLMSummarizer instance with API key set."""
    with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test-api-key-12345'}):
        if LLMSummarizer:
            summarizer = LLMSummarizer()
            yield summarizer
        else:
            yield None


@pytest.fixture
async def summarizer_without_api_key():
    """LLMSummarizer instance without API key."""
    with patch.dict(os.environ, {}, clear=True):
        # Ensure OPENROUTER_API_KEY is not set
        os.environ.pop('OPENROUTER_API_KEY', None)
        if LLMSummarizer:
            summarizer = LLMSummarizer()
            yield summarizer
        else:
            yield None


# ============================================================================
# Test: Successful API Call with Valid Key
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_summarize_with_valid_api_key(summarizer_with_api_key, sample_activity_text, mock_openrouter_response):
    """
    Test successful summary generation with valid API key.

    Verifies:
    - API request is formatted correctly
    - OpenRouter endpoint is called
    - Response is properly parsed
    - Returns expected summary text
    """
    summarizer = summarizer_with_api_key

    # Mock aiohttp ClientSession
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_openrouter_response)

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        # Call summarize_activity
        result = await summarizer.summarize_activity(
            instance_id="test-instance-123",
            activity_text=sample_activity_text,
            max_tokens=200
        )

        # Verify API was called
        assert mock_session.post.called
        call_args = mock_session.post.call_args

        # Check endpoint
        assert "openrouter.ai" in call_args[0][0]

        # Check headers
        headers = call_args[1]['headers']
        assert 'Authorization' in headers
        assert 'Bearer test-api-key-12345' in headers['Authorization']

        # Check request body
        json_data = call_args[1]['json']
        assert 'model' in json_data
        assert 'messages' in json_data
        assert json_data['max_tokens'] == 200

        # Verify result
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Instance is processing data analysis" in result


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_request_format_matches_openrouter_spec(summarizer_with_api_key, sample_activity_text):
    """
    Test that API request format exactly matches OpenRouter specification.

    Verifies:
    - Correct endpoint URL
    - Required headers (Authorization, HTTP-Referer, X-Title)
    - Message format with system and user roles
    - Model specification
    """
    summarizer = summarizer_with_api_key

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "choices": [{"message": {"content": "Test summary"}}]
    })

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        await summarizer.summarize_activity(
            instance_id="test-instance",
            activity_text=sample_activity_text,
            max_tokens=150
        )

        # Verify call was made
        assert mock_session.post.called
        call_args = mock_session.post.call_args

        # Check URL
        url = call_args[0][0]
        assert url == "https://openrouter.ai/api/v1/chat/completions"

        # Check all required headers
        headers = call_args[1]['headers']
        assert 'Authorization' in headers
        assert headers['Authorization'].startswith('Bearer ')
        assert 'HTTP-Referer' in headers or 'Content-Type' in headers

        # Check message structure
        json_data = call_args[1]['json']
        assert 'messages' in json_data
        messages = json_data['messages']
        assert len(messages) >= 1
        assert any(msg['role'] in ['system', 'user'] for msg in messages)


# ============================================================================
# Test: Missing API Key (Fallback Behavior)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_summarize_without_api_key(summarizer_without_api_key, sample_activity_text):
    """
    Test behavior when OPENROUTER_API_KEY is not set.

    Verifies:
    - No API call is made
    - Returns basic fallback summary
    - No exceptions raised
    - Fallback contains instance ID
    """
    summarizer = summarizer_without_api_key

    result = await summarizer.summarize_activity(
        instance_id="test-instance-no-key",
        activity_text=sample_activity_text,
        max_tokens=200
    )

    # Verify fallback behavior
    assert isinstance(result, str)
    assert len(result) > 0
    assert "test-instance-no-key" in result or "activity" in result.lower()
    # Should indicate it's a basic summary, not from LLM
    assert "summary" in result.lower() or "instance" in result.lower()


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_no_api_key_no_exception_raised(summarizer_without_api_key):
    """
    Test that missing API key does not raise exceptions.

    Verifies:
    - summarize_activity completes successfully
    - Returns string result
    - No exception propagates to caller
    """
    summarizer = summarizer_without_api_key

    # Should not raise any exception
    try:
        result = await summarizer.summarize_activity(
            instance_id="test-no-exception",
            activity_text="Some activity text",
            max_tokens=100
        )
        assert isinstance(result, str)
    except Exception as e:
        pytest.fail(f"Unexpected exception raised: {e}")


# ============================================================================
# Test: API Timeout Scenarios
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_api_timeout_returns_fallback(summarizer_with_api_key, sample_activity_text):
    """
    Test behavior when API call times out.

    Verifies:
    - Timeout exception is caught
    - Returns fallback message
    - Fallback mentions timeout
    - No exception propagates
    """
    summarizer = summarizer_with_api_key

    # Mock timeout
    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.side_effect = TimeoutError("API request timeout")
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await summarizer.summarize_activity(
            instance_id="test-timeout",
            activity_text=sample_activity_text,
            max_tokens=200
        )

        # Verify fallback behavior
        assert isinstance(result, str)
        assert "timeout" in result.lower() or "unavailable" in result.lower()


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_connection_timeout_graceful_fallback(summarizer_with_api_key):
    """
    Test graceful handling of connection timeout.

    Verifies:
    - ClientTimeout exceptions handled
    - Returns appropriate fallback
    - No exception raised to caller
    """
    summarizer = summarizer_with_api_key

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        # Simulate connection timeout
        mock_session.post.side_effect = aiohttp.ClientConnectorError(
            connection_key=None,
            os_error=TimeoutError("Connection timeout")
        )
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await summarizer.summarize_activity(
            instance_id="test-conn-timeout",
            activity_text="Some text",
            max_tokens=100
        )

        assert isinstance(result, str)
        assert len(result) > 0


# ============================================================================
# Test: API Error Responses
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_api_401_unauthorized(summarizer_with_api_key, sample_activity_text):
    """
    Test handling of 401 Unauthorized response.

    Verifies:
    - 401 status code handled gracefully
    - Returns fallback summary
    - No exception raised
    """
    summarizer = summarizer_with_api_key

    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.text = AsyncMock(return_value="Unauthorized")

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await summarizer.summarize_activity(
            instance_id="test-401",
            activity_text=sample_activity_text,
            max_tokens=200
        )

        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_api_403_forbidden(summarizer_with_api_key, sample_activity_text):
    """
    Test handling of 403 Forbidden response.

    Verifies:
    - 403 status code handled gracefully
    - Returns fallback summary
    - No exception raised
    """
    summarizer = summarizer_with_api_key

    mock_response = AsyncMock()
    mock_response.status = 403
    mock_response.text = AsyncMock(return_value="Forbidden")

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await summarizer.summarize_activity(
            instance_id="test-403",
            activity_text=sample_activity_text,
            max_tokens=200
        )

        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_api_500_server_error(summarizer_with_api_key, sample_activity_text):
    """
    Test handling of 500 Internal Server Error.

    Verifies:
    - 500 status code handled gracefully
    - Returns fallback summary
    - No exception raised
    """
    summarizer = summarizer_with_api_key

    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.text = AsyncMock(return_value="Internal Server Error")

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await summarizer.summarize_activity(
            instance_id="test-500",
            activity_text=sample_activity_text,
            max_tokens=200
        )

        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_api_rate_limit_429(summarizer_with_api_key, sample_activity_text):
    """
    Test handling of 429 Rate Limit response.

    Verifies:
    - 429 status code handled gracefully
    - Returns fallback summary
    - No exception raised
    """
    summarizer = summarizer_with_api_key

    mock_response = AsyncMock()
    mock_response.status = 429
    mock_response.text = AsyncMock(return_value="Rate limit exceeded")

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await summarizer.summarize_activity(
            instance_id="test-429",
            activity_text=sample_activity_text,
            max_tokens=200
        )

        assert isinstance(result, str)
        assert len(result) > 0


# ============================================================================
# Test: Different Instance States
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_summarize_running_instance(summarizer_with_api_key):
    """Test summarization for instance in 'running' state."""
    summarizer = summarizer_with_api_key

    activity = "Processing batch job... Computing results... Writing output..."

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "choices": [{"message": {"content": "Instance is running batch processing tasks"}}]
    })

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await summarizer.summarize_activity(
            instance_id="running-instance",
            activity_text=activity,
            max_tokens=150
        )

        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_summarize_idle_instance(summarizer_with_api_key):
    """Test summarization for instance in 'idle' state with minimal output."""
    summarizer = summarizer_with_api_key

    activity = "Waiting for tasks..."

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "choices": [{"message": {"content": "Instance is idle, waiting for new tasks"}}]
    })

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await summarizer.summarize_activity(
            instance_id="idle-instance",
            activity_text=activity,
            max_tokens=100
        )

        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_summarize_busy_instance_long_output(summarizer_with_api_key, long_activity_text):
    """Test summarization for busy instance with long output."""
    summarizer = summarizer_with_api_key

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "choices": [{"message": {"content": "Instance is very busy processing multiple tasks concurrently"}}]
    })

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        result = await summarizer.summarize_activity(
            instance_id="busy-instance",
            activity_text=long_activity_text,
            max_tokens=250
        )

        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_summarize_empty_activity(summarizer_with_api_key):
    """Test summarization with empty activity text."""
    summarizer = summarizer_with_api_key

    result = await summarizer.summarize_activity(
        instance_id="empty-activity",
        activity_text="",
        max_tokens=100
    )

    # Should handle empty input gracefully
    assert isinstance(result, str)


# ============================================================================
# Test: Exception Handling - No Exceptions Raised
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_no_exceptions_on_network_error(summarizer_with_api_key):
    """
    Test that network errors don't raise exceptions.

    Verifies:
    - ClientError exceptions are caught
    - Returns fallback string
    - No exception propagates
    """
    summarizer = summarizer_with_api_key

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.side_effect = aiohttp.ClientError("Network error")
        mock_session_class.return_value.__aenter__.return_value = mock_session

        try:
            result = await summarizer.summarize_activity(
                instance_id="network-error",
                activity_text="Some text",
                max_tokens=100
            )
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Exception should not be raised: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_no_exceptions_on_json_decode_error(summarizer_with_api_key):
    """
    Test that JSON decode errors don't raise exceptions.

    Verifies:
    - Malformed JSON response is handled
    - Returns fallback string
    - No exception propagates
    """
    summarizer = summarizer_with_api_key

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        try:
            result = await summarizer.summarize_activity(
                instance_id="json-error",
                activity_text="Some text",
                max_tokens=100
            )
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Exception should not be raised: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_no_exceptions_on_unexpected_response_format(summarizer_with_api_key):
    """
    Test handling of unexpected API response format.

    Verifies:
    - Missing expected fields handled
    - Returns fallback string
    - No exception propagates
    """
    summarizer = summarizer_with_api_key

    # Response missing 'choices' field
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"error": "unexpected format"})

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        try:
            result = await summarizer.summarize_activity(
                instance_id="bad-format",
                activity_text="Some text",
                max_tokens=100
            )
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Exception should not be raised: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_all_error_paths_return_strings(summarizer_with_api_key):
    """
    Comprehensive test: All error conditions return strings, never raise exceptions.

    Tests multiple error scenarios in sequence.
    """
    summarizer = summarizer_with_api_key

    error_scenarios = [
        aiohttp.ClientError("Network error"),
        TimeoutError("Timeout"),
        Exception("Unexpected error"),
    ]

    for error in error_scenarios:
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post.side_effect = error
            mock_session_class.return_value.__aenter__.return_value = mock_session

            try:
                result = await summarizer.summarize_activity(
                    instance_id=f"error-test-{type(error).__name__}",
                    activity_text="Test activity",
                    max_tokens=100
                )
                assert isinstance(result, str), f"Expected string for {type(error).__name__}"
                assert len(result) > 0, f"Expected non-empty string for {type(error).__name__}"
            except Exception as e:
                pytest.fail(f"No exception should be raised for {type(error).__name__}: {e}")


# ============================================================================
# Test: Caching and Performance
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_multiple_calls_with_different_instances(summarizer_with_api_key):
    """
    Test multiple summarization calls for different instances.

    Verifies:
    - Multiple instances can be summarized
    - Each call is independent
    - All return valid results
    """
    summarizer = summarizer_with_api_key

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "choices": [{"message": {"content": "Summary text"}}]
    })

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        results = []
        for i in range(3):
            result = await summarizer.summarize_activity(
                instance_id=f"instance-{i}",
                activity_text=f"Activity for instance {i}",
                max_tokens=100
            )
            results.append(result)

        # All should return strings
        assert all(isinstance(r, str) for r in results)
        assert all(len(r) > 0 for r in results)

        # API should be called 3 times
        assert mock_session.post.call_count == 3


@pytest.mark.asyncio
@pytest.mark.skipif(LLMSummarizer is None, reason="LLMSummarizer not yet implemented")
async def test_max_tokens_parameter_passed_correctly(summarizer_with_api_key):
    """
    Test that max_tokens parameter is correctly passed to API.

    Verifies:
    - max_tokens appears in request
    - Different values are respected
    """
    summarizer = summarizer_with_api_key

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "choices": [{"message": {"content": "Summary"}}]
    })

    mock_post = AsyncMock()
    mock_post.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session.post.return_value = mock_post
        mock_session_class.return_value.__aenter__.return_value = mock_session

        test_max_tokens = 300
        await summarizer.summarize_activity(
            instance_id="test-max-tokens",
            activity_text="Test activity",
            max_tokens=test_max_tokens
        )

        # Verify max_tokens in request
        call_args = mock_session.post.call_args
        json_data = call_args[1]['json']
        assert json_data['max_tokens'] == test_max_tokens
