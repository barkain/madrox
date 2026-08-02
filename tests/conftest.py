"""Pytest configuration for supervision tests."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Add src to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from orchestrator.config import resolve_model  # noqa: E402  (needs src on sys.path)


@pytest.fixture
def install_spawn_harness_delegate():
    """Point a mocked manager's ``_spawn_harness_instance`` at ``spawn_instance``.

    The MCP adapter spawns through ``_spawn_harness_instance`` so that the
    HTTP/SSE transport gets the same model resolution and failure reporting as
    the MCP tools. Tests still assert against ``spawn_instance``, so delegate
    back to whatever mock the test has installed there — resolved at call time,
    since tests routinely replace it after the fixture runs.
    """

    def _install(mock):
        async def _spawn(
            instance_type,
            name,
            model,
            initial_prompt,
            wait_for_response=False,
            timeout_seconds=180,
            **kwargs,
        ):
            # Mirror SpawningMixin._spawn_harness_instance closely enough that a
            # regression in the adapter still fails: resolve the model, defer the
            # prompt when the caller waits, and fold the reply (or a bootstrap
            # error) into the status. A delegate that skipped these would let the
            # adapter silently stop honouring wait_for_response.
            resolved_model = resolve_model(instance_type, model)
            spawn_prompt = None if wait_for_response else initial_prompt

            instance_id = await mock.spawn_instance(
                name=name,
                model=resolved_model,
                instance_type=instance_type,
                initial_prompt=spawn_prompt,
                **kwargs,
            )
            result = {
                "instance_id": instance_id,
                "status": "spawned",
                "name": name,
                "instance_type": instance_type,
                "model": resolved_model,
            }

            if wait_for_response and initial_prompt:
                response = await mock.tmux_manager.send_message(
                    instance_id=instance_id,
                    message=initial_prompt,
                    wait_for_response=True,
                    timeout_seconds=timeout_seconds,
                )
                if isinstance(response, dict):
                    result["response"] = response.get("response", "")
                    if error := response.get("error"):
                        result["status"] = "failed"
                        result["error_message"] = error
                    else:
                        result["status"] = "completed"
            else:
                instance = (getattr(mock, "instances", None) or {}).get(instance_id)
                if isinstance(instance, dict) and instance.get("error_message"):
                    result["status"] = "failed"
                    result["error_message"] = instance["error_message"]

            return result

        mock._spawn_harness_instance = AsyncMock(side_effect=_spawn)
        return mock

    return _install
