"""
LLMSummarizer - Generates natural language summaries of Claude instance activities.

Uses OpenRouter API to generate concise, readable summaries of instance activity logs.
Implements robust error handling and never raises exceptions.

Phase 2: LLM Integration for Activity Summarization
"""

import logging
import os

try:
    import aiohttp
except ImportError:
    aiohttp = None


class LLMSummarizer:
    """
    Generates natural language summaries of Claude instance activities using OpenRouter API.

    Features:
    - Async API calls using aiohttp
    - Robust error handling (never raises exceptions)
    - Configurable model and timeout
    - Automatic fallback summaries on errors
    - Comprehensive logging

    Example:
        >>> summarizer = LLMSummarizer(api_key="sk-...")
        >>> summary = await summarizer.summarize_activity(
        ...     instance_id="abc123",
        ...     activity_text="User: Hello\nAssistant: Hi there!",
        ...     max_tokens=200
        ... )
    """

    # OpenRouter API endpoint
    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

    # Default configuration
    DEFAULT_MODEL = "google/gemini-2.0-flash-exp:free"
    DEFAULT_TIMEOUT = 30  # seconds
    DEFAULT_MAX_TOKENS = 100  # Reduced for more concise summaries

    # Recommended models for different use cases (2025)
    RECOMMENDED_MODELS = {
        # FREE OPTIONS (no cost)
        "free_fast": "google/gemini-2.0-flash-exp:free",  # Best free option, faster than Gemini 1.5
        "free_balanced": "deepseek/deepseek-r1:free",  # MIT licensed, good reasoning
        "free_concurrent": "minimax/minimax-m2:free",  # High concurrency, cost efficient
        # CHEAP OPTIONS (ultra-low cost)
        "ultra_fast": "google/gemini-2.5-flash-lite",  # Ultra-low latency, minimal cost
        "fast": "google/gemini-2.5-flash",  # Fast, advanced reasoning
        # QUALITY OPTIONS (balanced cost/quality)
        "balanced": "anthropic/claude-haiku-4.5",  # Default, 200K context, good quality
        "reasoning": "anthropic/claude-sonnet-4.5",  # Advanced reasoning, higher cost
    }

    def __init__(
        self, api_key: str | None = None, model: str = DEFAULT_MODEL, timeout: int = DEFAULT_TIMEOUT
    ):
        """
        Initialize the LLMSummarizer.

        Args:
            api_key: OpenRouter API key. If None, reads from OPENROUTER_API_KEY env var.
            model: Model identifier for OpenRouter. Options:

                FREE MODELS (Recommended for high-volume monitoring):
                - "google/gemini-2.0-flash-exp:free" - Best free option, faster than Gemini 1.5
                - "deepseek/deepseek-r1:free" - MIT licensed, good reasoning capabilities
                - "minimax/minimax-m2:free" - High concurrency, cost efficient

                CHEAP MODELS (Ultra-low cost):
                - "google/gemini-2.5-flash-lite" - Ultra-low latency, minimal cost
                - "google/gemini-2.5-flash" - Fast with advanced reasoning

                QUALITY MODELS (Balanced cost/quality):
                - "anthropic/claude-haiku-4.5" - Default, 200K context, high quality
                - "anthropic/claude-sonnet-4.5" - Advanced reasoning, higher cost

                See RECOMMENDED_MODELS class attribute for full list.

            timeout: Request timeout in seconds (default: 30)

        Example:
            >>> # Use free Gemini model
            >>> summarizer = LLMSummarizer(
            ...     api_key="sk-or-v1-...",
            ...     model="google/gemini-2.0-flash-exp:free"
            ... )

            >>> # Use class constant
            >>> summarizer = LLMSummarizer(
            ...     api_key="sk-or-v1-...",
            ...     model=LLMSummarizer.RECOMMENDED_MODELS["free_fast"]
            ... )

        Note:
            If api_key is not provided and OPENROUTER_API_KEY env var is not set,
            all summarize_activity calls will return fallback summaries.
        """
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.model = model
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)

        # Validate aiohttp is available
        if aiohttp is None:
            self.logger.warning(
                "aiohttp not available - LLMSummarizer will return fallback summaries"
            )

        # Log initialization
        if self.api_key:
            self.logger.info(
                f"LLMSummarizer initialized with model={self.model}, timeout={self.timeout}s"
            )
        else:
            self.logger.warning(
                "LLMSummarizer initialized without API key - will return fallback summaries"
            )

    async def summarize_activity(
        self, instance_id: str, activity_text: str, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str:
        """
        Generate a natural language summary of instance activity.

        Args:
            instance_id: ID of the Claude instance
            activity_text: Recent activity/output text to summarize
            max_tokens: Maximum tokens for the summary (default: 200)

        Returns:
            Natural language summary (2-3 sentences). Never raises exceptions.
            Returns meaningful fallback string on any error.

        Error Handling:
            - No API key: Returns "No API key configured" fallback
            - Empty activity: Returns "No activity to summarize" message
            - API errors: Returns error description with instance_id
            - Network errors: Returns "Network error" fallback
            - Timeouts: Returns "Request timed out" fallback
            - All exceptions logged as warnings, never propagated

        Example:
            >>> summary = await summarizer.summarize_activity(
            ...     instance_id="test-123",
            ...     activity_text="Running tests... All passed!",
            ...     max_tokens=150
            ... )
        """
        # Validate inputs
        if not activity_text or len(activity_text.strip()) == 0:
            self.logger.debug(f"Empty activity text for instance {instance_id}")
            return f"Instance {instance_id}: No activity to summarize"

        # Check prerequisites
        if not self.api_key:
            self.logger.warning(f"No API key available for instance {instance_id}")
            return f"Instance {instance_id}: Summary unavailable (no API key configured)"

        if aiohttp is None:
            self.logger.warning(f"aiohttp not available for instance {instance_id}")
            return f"Instance {instance_id}: Summary unavailable (aiohttp not installed)"

        # Generate summary via OpenRouter API
        try:
            summary = await self._call_openrouter_api(
                instance_id=instance_id, activity_text=activity_text, max_tokens=max_tokens
            )
            return summary

        except TimeoutError:
            self.logger.warning(f"Timeout generating summary for instance {instance_id}")
            return f"Instance {instance_id}: Summary generation timed out"

        except aiohttp.ClientError as e:
            self.logger.warning(f"Network error generating summary for instance {instance_id}: {e}")
            return f"Instance {instance_id}: Summary unavailable (network error)"

        except Exception as e:
            self.logger.warning(
                f"Unexpected error generating summary for instance {instance_id}: {e}"
            )
            return f"Instance {instance_id}: Summary unavailable (error: {type(e).__name__})"

    async def _call_openrouter_api(
        self, instance_id: str, activity_text: str, max_tokens: int
    ) -> str:
        """
        Call OpenRouter API to generate summary.

        Args:
            instance_id: ID of the instance
            activity_text: Activity text to summarize
            max_tokens: Maximum tokens for response

        Returns:
            Generated summary text

        Raises:
            aiohttp.ClientError: On network errors
            asyncio.TimeoutError: On timeout
            Exception: On other errors
        """
        # Truncate activity text if too long (keep last 4000 chars)
        if len(activity_text) > 4000:
            activity_text = "..." + activity_text[-4000:]

        # Build prompt
        prompt = self._build_prompt(instance_id, activity_text)

        # Prepare request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/anthropics/madrox",
            "X-Title": "Madrox Instance Monitor",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        # Make request with timeout
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self.OPENROUTER_API_URL, headers=headers, json=payload
            ) as response:
                # Check HTTP status
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.warning(
                        f"OpenRouter API returned status {response.status}: {error_text[:200]}"
                    )
                    return (
                        f"Instance {instance_id}: Summary unavailable (API error {response.status})"
                    )

                # Parse response
                data = await response.json()

                # Extract summary from response
                if "choices" in data and len(data["choices"]) > 0:
                    summary = data["choices"][0]["message"]["content"].strip()
                    self.logger.debug(
                        f"Generated summary for instance {instance_id}: {len(summary)} chars"
                    )
                    return summary
                else:
                    self.logger.warning(
                        f"Unexpected API response format for instance {instance_id}"
                    )
                    return f"Instance {instance_id}: Summary unavailable (unexpected API response)"

    def _build_prompt(self, instance_id: str, activity_text: str) -> str:
        """
        Build the prompt for summary generation.

        Args:
            instance_id: ID of the instance
            activity_text: Activity text to summarize

        Returns:
            Formatted prompt string
        """
        return f"""Summarize this Claude instance's activity in 1-2 very brief sentences. Focus only on key actions and current status. Be extremely concise.

Activity:
{activity_text}

Brief summary:"""

    def __repr__(self) -> str:
        """String representation of the summarizer."""
        return f"LLMSummarizer(model={self.model}, timeout={self.timeout}s, api_key={'set' if self.api_key else 'not set'})"
