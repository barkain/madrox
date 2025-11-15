# LLMSummarizer Architecture Design Document

## 1. CLASS INTERFACE SPECIFICATION

### 1.1 Class Definition

```python
class LLMSummarizer:
    """
    Generates natural language summaries of Claude instance activities using OpenRouter API.

    This class provides async summarization of instance output using various LLM models
    through OpenRouter's unified API. Supports configurable models, timeouts, retries,
    and error handling.

    Attributes:
        api_key (str): OpenRouter API key
        base_url (str): OpenRouter API endpoint
        default_model (str): Default model for summarization
        timeout_seconds (float): HTTP request timeout
        max_retries (int): Maximum retry attempts on failure
        session (aiohttp.ClientSession): Persistent HTTP session
    """
```

### 1.2 Core Methods

#### `__init__(api_key: Optional[str] = None, default_model: str = "anthropic/claude-3.5-haiku", timeout_seconds: float = 30.0, max_retries: int = 3)`
**Purpose**: Initialize the LLMSummarizer with configuration
**Parameters**:
- `api_key` (Optional[str]): OpenRouter API key. If None, reads from `OPENROUTER_API_KEY` env var
- `default_model` (str): Default model ID (default: "anthropic/claude-3.5-haiku")
- `timeout_seconds` (float): HTTP request timeout in seconds (default: 30.0)
- `max_retries` (int): Max retry attempts for transient failures (default: 3)

**Raises**:
- `ValueError`: If API key is not provided and `OPENROUTER_API_KEY` env var is not set

**Behavior**:
- Validates API key availability
- Stores configuration parameters
- Does NOT create aiohttp session yet (lazy initialization)

---

#### `async def __aenter__(self) -> "LLMSummarizer"`
**Purpose**: Async context manager entry - creates HTTP session
**Returns**: self
**Behavior**: Creates `aiohttp.ClientSession` for connection pooling

---

#### `async def __aexit__(exc_type, exc_val, exc_tb) -> None`
**Purpose**: Async context manager exit - closes HTTP session
**Behavior**: Closes `aiohttp.ClientSession` gracefully

---

#### `async def summarize_activity(instance_id: str, activity_text: str, max_tokens: int = 200, model: Optional[str] = None) -> str`
**Purpose**: Generate a concise natural language summary of instance activity
**Parameters**:
- `instance_id` (str): Unique identifier of the instance
- `activity_text` (str): Raw activity text to summarize (instance output/logs)
- `max_tokens` (int): Maximum tokens for summary (default: 200)
- `model` (Optional[str]): Model to use (overrides default_model if provided)

**Returns**:
- `str`: Natural language summary (1-2 sentences describing what the instance is doing)

**Raises**:
- `LLMSummarizerError`: Base exception for summarization failures
- `APIKeyMissingError`: If API key is not configured
- `TimeoutError`: If request exceeds timeout_seconds
- `RateLimitError`: If OpenRouter rate limit is hit
- `ModelNotFoundError`: If specified model doesn't exist

**Behavior**:
1. Validates inputs (non-empty activity_text, valid instance_id)
2. Truncates activity_text if too long (last 8000 characters)
3. Builds prompt for summarization
4. Calls OpenRouter API with retry logic
5. Extracts and returns summary text
6. Logs errors and timing metrics

---

#### `async def close() -> None`
**Purpose**: Explicitly close HTTP session (alternative to context manager)
**Behavior**: Closes `aiohttp.ClientSession` if open

---

#### `async def _call_openrouter(messages: List[Dict[str, str]], max_tokens: int, model: str) -> str`
**Purpose**: Internal method to call OpenRouter API with retry logic
**Parameters**:
- `messages` (List[Dict]): Chat messages in OpenAI format
- `max_tokens` (int): Max tokens for response
- `model` (str): Model identifier

**Returns**: Raw response text from LLM
**Raises**: Various API-related exceptions
**Behavior**:
- Implements exponential backoff (1s, 2s, 4s, 8s)
- Retries on transient errors (429, 502, 503, 504)
- Raises on permanent errors (400, 401, 403, 404)
- Ensures HTTP session exists (creates if needed)

---

#### `def _build_prompt(instance_id: str, activity_text: str) -> List[Dict[str, str]]`
**Purpose**: Build chat messages for OpenRouter API
**Parameters**:
- `instance_id` (str): Instance identifier
- `activity_text` (str): Activity text to summarize

**Returns**: List of message dicts in OpenAI chat format
**Behavior**:
- Creates system message with instructions
- Creates user message with activity text
- Prompt optimized for concise 1-2 sentence summaries

---

#### `def _ensure_session() -> None`
**Purpose**: Ensure aiohttp session exists (lazy initialization)
**Behavior**: Creates session if not already created

---

## 2. API INTEGRATION DESIGN

### 2.1 OpenRouter API Specification

**Endpoint**: `https://openrouter.ai/api/v1/chat/completions`
**Method**: POST
**Content-Type**: application/json

**Headers**:
```python
{
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/anthropics/madrox",  # Optional, for attribution
    "X-Title": "Madrox Orchestrator"  # Optional, for attribution
}
```

**Request Body**:
```json
{
    "model": "anthropic/claude-3.5-haiku",
    "messages": [
        {
            "role": "system",
            "content": "You are a concise summarizer..."
        },
        {
            "role": "user",
            "content": "Instance ID: test-123\n\nActivity:\n..."
        }
    ],
    "max_tokens": 200,
    "temperature": 0.3
}
```

**Response Format** (Success - 200):
```json
{
    "id": "gen-xxxxx",
    "model": "anthropic/claude-3.5-haiku",
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "The instance is currently reading configuration files and initializing database connections."
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 150,
        "completion_tokens": 25,
        "total_tokens": 175
    }
}
```

**Response Format** (Error - 4xx/5xx):
```json
{
    "error": {
        "message": "Invalid API key",
        "type": "invalid_request_error",
        "code": 401
    }
}
```

### 2.2 HTTP Client Configuration

**aiohttp ClientSession Configuration**:
```python
timeout = aiohttp.ClientTimeout(total=timeout_seconds)
connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
session = aiohttp.ClientSession(
    timeout=timeout,
    connector=connector,
    headers={
        "HTTP-Referer": "https://github.com/anthropics/madrox",
        "X-Title": "Madrox Orchestrator"
    }
)
```

### 2.3 Model Support

**Supported Models** (via OpenRouter):
- `anthropic/claude-3.5-haiku` (default, fast and cost-effective)
- `anthropic/claude-3.5-sonnet`
- `openai/gpt-4o-mini`
- `openai/gpt-4o`
- `google/gemini-2.0-flash-exp:free` (free option)

**Model Selection Strategy**:
- Default: claude-3.5-haiku (good balance of speed/quality/cost)
- Configurable via constructor parameter
- Overridable per-request via `summarize_activity(model=...)`

---

## 3. ERROR HANDLING STRATEGY

### 3.1 Exception Hierarchy

```python
class LLMSummarizerError(Exception):
    """Base exception for LLMSummarizer errors."""
    pass

class APIKeyMissingError(LLMSummarizerError):
    """Raised when OpenRouter API key is not configured."""
    pass

class APIError(LLMSummarizerError):
    """Base exception for API-related errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

class TimeoutError(APIError):
    """Raised when API request times out."""
    pass

class RateLimitError(APIError):
    """Raised when rate limit is exceeded (429)."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after

class ModelNotFoundError(APIError):
    """Raised when specified model is not found (404)."""
    pass

class AuthenticationError(APIError):
    """Raised when API key is invalid (401/403)."""
    pass

class InvalidRequestError(APIError):
    """Raised when request is malformed (400)."""
    pass
```

### 3.2 Retry Logic

**Retry Strategy**:
- **Transient Errors** (retry with exponential backoff):
  - 429 (Rate Limit)
  - 502 (Bad Gateway)
  - 503 (Service Unavailable)
  - 504 (Gateway Timeout)
  - Network errors (connection reset, DNS failures)

- **Permanent Errors** (fail immediately, no retry):
  - 400 (Bad Request)
  - 401 (Unauthorized)
  - 403 (Forbidden)
  - 404 (Not Found)
  - 422 (Unprocessable Entity)

**Backoff Algorithm**:
```python
backoff_seconds = min(2 ** attempt, 16)  # Cap at 16 seconds
# Attempts: 1s, 2s, 4s, 8s (if max_retries=3)
```

**Rate Limit Handling**:
- Check `Retry-After` header from 429 response
- Use `Retry-After` value if present, otherwise use exponential backoff
- Log warning with backoff duration

### 3.3 Timeout Handling

**Timeout Behavior**:
- Total request timeout: `timeout_seconds` (default 30s)
- Applies to entire request lifecycle (connection + read + write)
- On timeout:
  1. Cancel request
  2. Log warning
  3. Retry if attempts remaining
  4. Raise `TimeoutError` if all retries exhausted

### 3.4 Logging Strategy

**Log Levels**:
- **DEBUG**: Request/response details, timing metrics
- **INFO**: Successful summarizations, retry attempts
- **WARNING**: Rate limits, timeouts, retryable errors
- **ERROR**: Permanent failures, exhausted retries

**Log Messages**:
```python
# Success
logger.info(f"Generated summary for {instance_id} ({duration_ms}ms, {tokens} tokens)")

# Retry
logger.warning(f"API request failed (attempt {attempt}/{max_retries}): {error_type}")

# Rate Limit
logger.warning(f"Rate limited, backing off {backoff}s")

# Timeout
logger.warning(f"Request timed out after {timeout_seconds}s (attempt {attempt})")

# Failure
logger.error(f"Failed to generate summary for {instance_id}: {error}")
```

---

## 4. DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│ MonitoringService (monitoring_service.py:211)                       │
│                                                                       │
│  summary = await llm_summarizer.summarize_activity(                 │
│      instance_id="abc-123",                                          │
│      activity_text="[Recent output from instance...]",              │
│      max_tokens=200                                                  │
│  )                                                                   │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LLMSummarizer.summarize_activity()                                  │
│                                                                       │
│  1. Validate inputs (instance_id, activity_text)                    │
│  2. Truncate activity_text if > 8000 chars (keep last 8000)         │
│  3. Build prompt: _build_prompt(instance_id, activity_text)         │
│  4. Determine model (use provided or default)                       │
│  5. Call API: _call_openrouter(messages, max_tokens, model)         │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LLMSummarizer._build_prompt()                                       │
│                                                                       │
│  Returns:                                                            │
│  [                                                                   │
│    {                                                                 │
│      "role": "system",                                               │
│      "content": "You are a concise summarizer for AI agent          │
│                  activities. Given recent output from a Claude      │
│                  instance, provide a 1-2 sentence summary of what   │
│                  the instance is currently doing. Focus on actions, │
│                  not results. Be specific and technical."           │
│    },                                                                │
│    {                                                                 │
│      "role": "user",                                                 │
│      "content": "Instance ID: abc-123\n\nRecent Activity:\n[...]"   │
│    }                                                                 │
│  ]                                                                   │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ LLMSummarizer._call_openrouter()                                    │
│                                                                       │
│  For attempt in range(max_retries):                                 │
│    1. Ensure aiohttp session exists (_ensure_session)               │
│    2. Build request body                                             │
│    3. POST to https://openrouter.ai/api/v1/chat/completions         │
│    4. Check response status                                          │
│    5. If success (200): extract and return summary                   │
│    6. If transient error: exponential backoff + retry               │
│    7. If permanent error: raise exception                            │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ OpenRouter API                                                       │
│ https://openrouter.ai/api/v1/chat/completions                       │
│                                                                       │
│ Request:                                                             │
│ {                                                                    │
│   "model": "anthropic/claude-3.5-haiku",                            │
│   "messages": [...],                                                 │
│   "max_tokens": 200,                                                 │
│   "temperature": 0.3                                                 │
│ }                                                                    │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ OpenRouter Response Processing                                      │
│                                                                       │
│ Response (200 OK):                                                   │
│ {                                                                    │
│   "choices": [                                                       │
│     {                                                                │
│       "message": {                                                   │
│         "content": "The instance is reading database models and     │
│                     initializing connection pools."                 │
│       }                                                              │
│     }                                                                │
│   ],                                                                 │
│   "usage": {"total_tokens": 175}                                    │
│ }                                                                    │
│                                                                       │
│ Extract: response["choices"][0]["message"]["content"]               │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Return to MonitoringService                                         │
│                                                                       │
│ Returns: "The instance is reading database models and initializing  │
│           connection pools."                                         │
│                                                                       │
│ MonitoringService persists to:                                      │
│ /tmp/madrox_logs/summaries/abc-123/summary_2025-11-06T12:00:00.json│
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. DEPENDENCIES

### 5.1 Required Dependencies

```python
# Core dependencies
aiohttp >= 3.9.0          # Async HTTP client
asyncio                    # Async runtime (stdlib)

# Environment and configuration
os                         # Environment variables (stdlib)
logging                    # Logging (stdlib)
json                       # JSON parsing (stdlib)

# Type hints
typing                     # Type annotations (stdlib)
```

### 5.2 Environment Variables

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx  # OpenRouter API key

# Optional
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1  # Custom endpoint (default shown)
LLM_SUMMARIZER_MODEL=anthropic/claude-3.5-haiku   # Default model
LLM_SUMMARIZER_TIMEOUT=30                          # Request timeout in seconds
LLM_SUMMARIZER_MAX_RETRIES=3                       # Max retry attempts
```

### 5.3 Installation

**requirements.txt addition**:
```
aiohttp>=3.9.0
```

**Installation command**:
```bash
pip install aiohttp
```

---

## 6. USAGE EXAMPLES

### 6.1 Basic Usage (Context Manager - Recommended)

```python
from orchestrator.llm_summarizer import LLMSummarizer

async def main():
    async with LLMSummarizer() as summarizer:
        summary = await summarizer.summarize_activity(
            instance_id="test-instance-123",
            activity_text="⏺ Read(database/models.py)\n⏺ Write(database/schema.py)\n✓ Schema updated",
            max_tokens=200
        )
        print(summary)
        # Output: "The instance is reading database models and writing schema definitions."
```

### 6.2 MonitoringService Integration

```python
from orchestrator.monitoring_service import MonitoringService
from orchestrator.llm_summarizer import LLMSummarizer

async def main():
    async with LLMSummarizer() as llm_summarizer:
        monitoring_service = MonitoringService(
            instance_manager=instance_manager,
            llm_summarizer=llm_summarizer,
            poll_interval=12
        )
        await monitoring_service.start()
```

### 6.3 Custom Model Usage

```python
async with LLMSummarizer(default_model="openai/gpt-4o-mini") as summarizer:
    summary = await summarizer.summarize_activity(
        instance_id="test-123",
        activity_text="...",
        model="anthropic/claude-3.5-sonnet"  # Override per request
    )
```

### 6.4 Error Handling

```python
from orchestrator.llm_summarizer import (
    LLMSummarizer,
    RateLimitError,
    TimeoutError,
    APIKeyMissingError
)

async with LLMSummarizer() as summarizer:
    try:
        summary = await summarizer.summarize_activity(
            instance_id="test-123",
            activity_text="..."
        )
    except APIKeyMissingError:
        print("Please set OPENROUTER_API_KEY environment variable")
    except RateLimitError as e:
        print(f"Rate limited. Retry after {e.retry_after} seconds")
    except TimeoutError:
        print("Request timed out")
    except Exception as e:
        print(f"Unexpected error: {e}")
```

---

## 7. TESTING STRATEGY

### 7.1 Unit Tests (test_llm_summarizer.py)

**Test Categories**:
1. **Initialization Tests**
   - Test with API key provided
   - Test with API key from env var
   - Test missing API key raises error
   - Test custom configuration (model, timeout, retries)

2. **Prompt Building Tests**
   - Test prompt structure
   - Test truncation of long activity text
   - Test instance_id inclusion in prompt

3. **API Call Tests (Mocked)**
   - Test successful API call
   - Test retry on transient errors (429, 503)
   - Test failure on permanent errors (401, 404)
   - Test exponential backoff timing
   - Test timeout behavior
   - Test rate limit header parsing

4. **Integration Tests (Mocked)**
   - Test full summarize_activity flow
   - Test context manager lifecycle
   - Test session reuse
   - Test concurrent requests

5. **Error Handling Tests**
   - Test all exception types
   - Test error message clarity
   - Test logging output

**Mock Strategy**:
- Mock `aiohttp.ClientSession.post()` for API calls
- Use `pytest-aiohttp` for async test support
- Use `unittest.mock.AsyncMock` for async mocks

### 7.2 Integration Tests

**With MonitoringService**:
- Test LLMSummarizer integration with MonitoringService
- Test end-to-end summarization and persistence
- Test error propagation

**With Real API** (optional, requires API key):
- Mark with `@pytest.mark.integration`
- Skip if `OPENROUTER_API_KEY` not set
- Test actual API calls with small payloads

### 7.3 Test Coverage Goals

- **Line Coverage**: > 90%
- **Branch Coverage**: > 85%
- **Critical Paths**: 100% (initialization, API calls, error handling)

---

## 8. PERFORMANCE CONSIDERATIONS

### 8.1 Latency Targets

- **P50 (median)**: < 1 second
- **P95**: < 3 seconds
- **P99**: < 5 seconds (with retries)

**Expected Latency Breakdown**:
- Network RTT: 100-300ms
- API processing: 500-1500ms
- Total: 600-1800ms (typical)

### 8.2 Throughput

- **Connection Pooling**: aiohttp session reuse (10 concurrent connections)
- **Rate Limits**: Respect OpenRouter rate limits (varies by account tier)
- **Concurrent Requests**: Support via asyncio task parallelism

### 8.3 Resource Usage

- **Memory**: ~5-10 MB per LLMSummarizer instance
- **CPU**: Minimal (I/O bound operation)
- **Network**: ~1-3 KB per request, ~0.5-1 KB per response

---

## 9. SECURITY CONSIDERATIONS

### 9.1 API Key Management

- **Storage**: Environment variable only (never hardcoded)
- **Logging**: Never log API key (mask in logs)
- **Validation**: Check key format (basic sanity check)

### 9.2 Input Validation

- **Activity Text**: Sanitize before sending (truncate, validate UTF-8)
- **Instance ID**: Validate format (alphanumeric + hyphens only)
- **Max Tokens**: Enforce reasonable bounds (1-4096)

### 9.3 Rate Limiting

- **Client-Side**: Respect `Retry-After` headers
- **Backoff**: Exponential backoff on 429 responses
- **Monitoring**: Log rate limit events for visibility

---

## 10. FUTURE ENHANCEMENTS (Post-MVP)

1. **Caching**: Cache recent summaries to reduce API calls
2. **Streaming**: Support streaming responses for real-time summaries
3. **Batch Summarization**: Summarize multiple instances in one request
4. **Custom Prompts**: Allow prompt customization per instance type
5. **Metrics**: Expose Prometheus metrics (request duration, error rates)
6. **Fallback Models**: Auto-fallback to alternative models on failure
7. **Token Estimation**: Pre-compute token counts to avoid over-limit errors

---

## ARCHITECTURE COMPLETE

**Summary**:
- **Class**: LLMSummarizer with async OpenRouter integration
- **Core Method**: `summarize_activity(instance_id, activity_text, max_tokens, model)`
- **API**: OpenRouter `/chat/completions` endpoint
- **Error Handling**: Retry with exponential backoff, custom exception hierarchy
- **Dependencies**: aiohttp, asyncio, os, logging, json, typing
- **Data Flow**: MonitoringService → LLMSummarizer → OpenRouter → Summary Text
- **Testing**: Comprehensive unit + integration tests with mocks
- **Performance**: < 2s P95 latency, connection pooling
- **Security**: Env-based API key, input validation, rate limiting

**Estimated Implementation**:
- **llm_summarizer.py**: ~250 lines
- **test_llm_summarizer.py**: ~350 lines
- **Total**: ~600 lines of production-quality code

**Ready for Implementation**: ✅
