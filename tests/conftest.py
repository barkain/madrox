"""Pytest configuration for supervision tests."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Add src to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


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
            instance_id = await mock.spawn_instance(
                name=name,
                model=model,
                instance_type=instance_type,
                initial_prompt=initial_prompt,
                **kwargs,
            )
            return {
                "instance_id": instance_id,
                "status": "spawned",
                "name": name,
                "instance_type": instance_type,
                "model": model,
            }

        mock._spawn_harness_instance = AsyncMock(side_effect=_spawn)
        return mock

    return _install
