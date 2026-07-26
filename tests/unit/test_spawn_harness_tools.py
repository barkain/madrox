"""Tests for the harness spawn tools (spawn_claude / spawn_codex / spawn_grok)."""

import tempfile
from typing import Any
from unittest.mock import AsyncMock

import pytest

from orchestrator.config import _load_model_config
from orchestrator.instance_manager.spawning import SpawningMixin
from orchestrator.tmux_instance_manager import TmuxInstanceManager


class _Spawner(SpawningMixin):
    """Minimal host for the mixin that records what spawn_instance was given."""

    def __init__(self):
        self.instances: dict[str, dict[str, Any]] = {}
        self.tmux_manager = AsyncMock()
        self.calls: list[dict[str, Any]] = []

    async def spawn_instance(self, **kwargs):
        self.calls.append(kwargs)
        instance_id = f"inst-{len(self.calls)}"
        self.instances[instance_id] = {"id": instance_id, **kwargs}
        return instance_id


@pytest.fixture(autouse=True)
def _clean_config(monkeypatch):
    for var in (
        "MADROX_MODELS_CONFIG",
        "MADROX_MODEL_CLAUDE",
        "MADROX_MODEL_CODEX",
        "MADROX_MODEL_GROK",
    ):
        monkeypatch.delenv(var, raising=False)
    _load_model_config.cache_clear()
    yield
    _load_model_config.cache_clear()


@pytest.fixture
def spawner():
    return _Spawner()


class TestDefaultModels:
    """Omitting `model` gives the harness default, and reports it back."""

    @pytest.mark.asyncio
    async def test_spawn_claude_defaults_to_configured_model(self, spawner):
        result = await SpawningMixin.spawn_claude.fn(spawner, name="alpha")

        assert spawner.calls[0]["model"] == "claude-opus-5"
        assert spawner.calls[0]["instance_type"] == "claude"
        assert result["model"] == "claude-opus-5"
        assert result["instance_type"] == "claude"

    @pytest.mark.asyncio
    async def test_spawn_codex_defaults_to_configured_model(self, spawner):
        result = await SpawningMixin.spawn_codex.fn(spawner, name="beta")

        assert spawner.calls[0]["model"] == "gpt-5.6-sol"
        assert spawner.calls[0]["instance_type"] == "codex"
        assert result["model"] == "gpt-5.6-sol"

    @pytest.mark.asyncio
    async def test_spawn_grok_defaults_to_configured_model(self, spawner):
        result = await SpawningMixin.spawn_grok.fn(spawner, name="gamma")

        assert spawner.calls[0]["model"] == "grok-build-0.1"
        assert spawner.calls[0]["instance_type"] == "grok"
        assert result["model"] == "grok-build-0.1"
        assert result["status"] == "spawned"

    @pytest.mark.asyncio
    async def test_explicit_model_is_used_verbatim(self, spawner):
        await SpawningMixin.spawn_grok.fn(spawner, name="delta", model="grok-5-ultra")
        assert spawner.calls[0]["model"] == "grok-5-ultra"

    @pytest.mark.asyncio
    async def test_env_override_changes_default(self, spawner, monkeypatch):
        monkeypatch.setenv("MADROX_MODEL_CODEX", "gpt-6")
        _load_model_config.cache_clear()

        await SpawningMixin.spawn_codex.fn(spawner, name="epsilon")
        assert spawner.calls[0]["model"] == "gpt-6"


class TestSpawnArguments:
    @pytest.mark.asyncio
    async def test_grok_runs_in_yolo_mode_by_default(self, spawner):
        await SpawningMixin.spawn_grok.fn(spawner, name="zeta")
        assert spawner.calls[0]["bypass_isolation"] is True

    @pytest.mark.asyncio
    async def test_initial_prompt_is_deferred_when_waiting_for_response(self, spawner):
        spawner.tmux_manager.send_message.return_value = {"response": "hello back", "error": None}

        result = await SpawningMixin.spawn_grok.fn(
            spawner, name="eta", initial_prompt="hello", wait_for_response=True
        )

        # The prompt is sent as a message so the reply can be captured.
        assert spawner.calls[0]["initial_prompt"] is None
        assert result["status"] == "completed"
        assert result["response"] == "hello back"

    @pytest.mark.asyncio
    async def test_backend_error_surfaces_as_failed(self, spawner):
        spawner.tmux_manager.send_message.return_value = {
            "response": "",
            "error": "unknown model",
        }

        result = await SpawningMixin.spawn_grok.fn(
            spawner, name="theta", initial_prompt="hi", wait_for_response=True
        )

        assert result["status"] == "failed"
        assert result["error_message"] == "unknown model"


class TestUnsupportedHarness:
    @pytest.mark.asyncio
    async def test_spawn_instance_rejects_unknown_type_before_doing_work(self):
        manager = TmuxInstanceManager(
            {"workspace_base_dir": tempfile.mkdtemp(), "max_concurrent_instances": 10}
        )

        with pytest.raises(ValueError, match="Unsupported instance type"):
            await manager.spawn_instance(name="nope", instance_type="gemini")

        assert manager.instances == {}
