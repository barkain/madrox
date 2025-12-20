"""LLM-powered agent summary generation with on-track inference.

This module provides the SummaryGenerator class that uses Claude Haiku 4.5
to analyze agent log outputs and produce structured AgentSummary objects
with intelligent on-track status inference.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from ..compat import UTC

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None  # Handle gracefully for testing

from .models import AgentSummary, OnTrackStatus

logger = logging.getLogger(__name__)

# Claude Haiku model ID
CLAUDE_HAIKU_MODEL = "claude-haiku-4-5-20250929"

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 16.0


class SummaryGenerator:
    """Generates structured agent summaries using Claude Haiku 4.5.

    This class analyzes agent terminal output (log lines) and generates
    comprehensive AgentSummary objects with on-track status inference,
    confidence scoring, and actionable recommendations.

    Attributes:
        anthropic_client: Async Anthropic client for API calls.
        model: Claude model to use (default: claude-haiku-4-5-20250929).
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """Initialize the SummaryGenerator.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
            model: Claude model to use. Defaults to Haiku 4.5.

        Raises:
            ImportError: If anthropic SDK is not installed.
        """
        if AsyncAnthropic is None:
            raise ImportError("anthropic package is required. Install with: pip install anthropic")

        self.anthropic_client = AsyncAnthropic(api_key=api_key)
        self.model = model or CLAUDE_HAIKU_MODEL

    async def generate_summary(
        self,
        instance_id: str,
        new_log_lines: list[str],
        agent_context: dict[str, Any],
    ) -> AgentSummary:
        """Generate a structured summary from agent logs.

        Analyzes recent log lines and agent context to produce a comprehensive
        AgentSummary with on-track inference, confidence scoring, and recommendations.

        Args:
            instance_id: Unique identifier for the agent instance.
            new_log_lines: Recent log lines from agent terminal output.
            agent_context: Dictionary containing:
                - instance_name: Human-readable agent name
                - role: Agent role/specialization (optional)
                - assigned_task: Task description assigned to agent (optional)
                - parent_instance_id: Parent/supervisor ID (optional)
                - previous_summary: Previous AgentSummary for continuity (optional)

        Returns:
            AgentSummary: Fully populated summary with on-track inference.

        Raises:
            Exception: If all retries fail or API returns invalid response.
        """
        # Build the analysis prompt
        prompt = self._build_prompt(instance_id, new_log_lines, agent_context)

        # Call Claude with retry logic
        response_json = await self._call_claude_with_retry(prompt)

        # Parse and construct AgentSummary
        summary = self._parse_response_to_summary(response_json, instance_id, agent_context)

        return summary

    def _build_prompt(
        self,
        instance_id: str,
        new_log_lines: list[str],
        agent_context: dict[str, Any],
    ) -> str:
        """Construct the analysis prompt for Claude.

        Args:
            instance_id: Agent instance ID.
            new_log_lines: Recent log lines.
            agent_context: Agent context dictionary.

        Returns:
            Formatted prompt string for Claude.
        """
        instance_name = agent_context.get("instance_name", instance_id)
        role = agent_context.get("role", "general agent")
        assigned_task = agent_context.get("assigned_task")
        previous_summary = agent_context.get("previous_summary")

        # Prepare log content
        if not new_log_lines:
            log_content = "(No recent activity)"
        else:
            # Limit to last 100 lines to avoid token limits
            limited_lines = new_log_lines[-100:]
            log_content = "\n".join(limited_lines)

        # Build context section
        context_section = f"""Agent Information:
- Instance ID: {instance_id}
- Instance Name: {instance_name}
- Role: {role}"""

        if assigned_task:
            context_section += f"\n- Assigned Task: {assigned_task}"

        if previous_summary:
            prev_activity = getattr(previous_summary, "current_activity", "Unknown")
            prev_status = getattr(previous_summary, "on_track_status", OnTrackStatus.UNKNOWN)
            context_section += f"\n- Previous Activity: {prev_activity}"
            context_section += f"\n- Previous Status: {prev_status.value}"

        # Construct full prompt
        prompt = f"""{context_section}

Recent Terminal Output:
```
{log_content}
```

Analyze this agent's recent terminal output and provide a structured assessment in JSON format.

Your analysis should determine:
1. **Current Activity**: Concise 1-2 sentence description of what the agent is currently doing
2. **On-Track Status**: One of: on_track, drifting, off_track, blocked, unknown
   - on_track: Agent is working on assigned task as expected
   - drifting: Minor deviation from assigned task
   - off_track: Significant misalignment with assigned task
   - blocked: Agent is stuck, waiting, or encountering errors
   - unknown: Insufficient data to determine status
3. **Confidence Score**: Float 0.0-1.0 indicating confidence in on_track_status assessment
4. **Drift Reasons**: List of specific reasons if status is drifting/off_track/blocked
5. **Alignment Keywords**: Keywords from output indicating task alignment
6. **Last Tool Used**: Name of most recently used tool (if visible)
7. **Recent Tools**: List of last 3-5 tools used
8. **Idle Duration**: Estimated seconds since last activity (0 if active)
9. **Recommended Action**: Suggested action for supervisor (or null if none needed)

Respond with ONLY a JSON object in this exact format:
{{
  "current_activity": "string (1-2 sentences)",
  "on_track_status": "on_track|drifting|off_track|blocked|unknown",
  "confidence_score": 0.0-1.0,
  "drift_reasons": ["reason1", "reason2"],
  "alignment_keywords": ["keyword1", "keyword2"],
  "last_tool_used": "tool_name or null",
  "recent_tools": ["tool1", "tool2", "tool3"],
  "idle_duration_seconds": 0.0,
  "recommended_action": "action description or null"
}}

Do not include any text before or after the JSON object."""

        return prompt

    async def _call_claude_with_retry(self, prompt: str) -> dict[str, Any]:
        """Call Claude API with exponential backoff retry logic.

        Args:
            prompt: The analysis prompt.

        Returns:
            Parsed JSON response from Claude.

        Raises:
            Exception: If all retries fail.
        """
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(MAX_RETRIES):
            try:
                message = await self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )

                # Extract text content
                response_text = message.content[0].text

                # Parse JSON response
                response_json = json.loads(response_text)
                return response_json

            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON from Claude (attempt {attempt + 1}): {e}")
                if attempt == MAX_RETRIES - 1:
                    raise Exception(
                        f"Failed to get valid JSON after {MAX_RETRIES} attempts"
                    ) from None

            except Exception as e:
                error_type = type(e).__name__
                logger.warning(f"API call failed (attempt {attempt + 1}): {error_type} - {e}")

                # Handle rate limits with longer backoff
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                    logger.info(f"Rate limited, backing off {backoff}s")

                if attempt == MAX_RETRIES - 1:
                    raise Exception(f"Failed after {MAX_RETRIES} retries: {e}") from e

            # Exponential backoff
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)

        raise Exception("Unexpected: retry loop exited without return or raise")

    def _parse_response_to_summary(
        self,
        response_json: dict[str, Any],
        instance_id: str,
        agent_context: dict[str, Any],
    ) -> AgentSummary:
        """Parse Claude's JSON response into an AgentSummary object.

        Args:
            response_json: Parsed JSON response from Claude.
            instance_id: Agent instance ID.
            agent_context: Agent context dictionary.

        Returns:
            Fully populated AgentSummary.

        Raises:
            ValueError: If response JSON is missing required fields.
        """
        # Extract required fields
        current_activity = response_json.get("current_activity", "Activity unknown")
        on_track_status_str = response_json.get("on_track_status", "unknown")
        confidence_score = float(response_json.get("confidence_score", 0.5))

        # Parse on_track_status enum
        try:
            on_track_status = OnTrackStatus(on_track_status_str)
        except ValueError:
            logger.warning(f"Invalid on_track_status: {on_track_status_str}, defaulting to UNKNOWN")
            on_track_status = OnTrackStatus.UNKNOWN

        # Extract optional fields
        drift_reasons = response_json.get("drift_reasons", [])
        alignment_keywords = response_json.get("alignment_keywords", [])
        last_tool_used = response_json.get("last_tool_used")
        recent_tools = response_json.get("recent_tools", [])
        idle_duration_seconds = float(response_json.get("idle_duration_seconds", 0.0))
        recommended_action = response_json.get("recommended_action")

        # Get output preview (last 200 chars of log lines)
        output_preview = ""
        if agent_context.get("log_lines_full"):
            all_text = "\n".join(agent_context["log_lines_full"])
            output_preview = all_text[-200:] if len(all_text) > 200 else all_text

        # Build AgentSummary
        summary = AgentSummary(
            instance_id=instance_id,
            instance_name=agent_context.get("instance_name", instance_id),
            timestamp=datetime.now(UTC).isoformat(),
            current_activity=current_activity,
            on_track_status=on_track_status,
            confidence_score=confidence_score,
            assigned_task=agent_context.get("assigned_task"),
            parent_instance_id=agent_context.get("parent_instance_id"),
            role=agent_context.get("role"),
            last_tool_used=last_tool_used,
            recent_tools=recent_tools,
            output_preview=output_preview,
            idle_duration_seconds=idle_duration_seconds,
            drift_reasons=drift_reasons,
            alignment_keywords=alignment_keywords,
            recommended_action=recommended_action,
        )

        return summary
