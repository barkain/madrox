"""Unit tests for config.py - Model configuration validation."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from orchestrator.config import _load_model_config, get_harness_config, resolve_model


class TestLoadModelConfig:
    """Test _load_model_config function."""

    @pytest.fixture
    def mock_config_data(self):
        """Sample configuration data matching actual models.yaml structure."""
        return {
            "codex": {
                "default": "gpt-5-codex",
                "allowed_models": ["gpt-5-codex"],
            },
            "claude": {
                "default": "claude-sonnet-4-5",
                "allowed_models": [
                    "claude-sonnet-4-5",
                    "claude-opus-4-1",
                    "claude-haiku-4-5",
                ],
            },
        }

    def test_load_model_config_success(self, mock_config_data):
        """Test successful loading of model configuration."""
        # Clear the LRU cache before test
        _load_model_config.cache_clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_file = config_dir / "models.yaml"

            # Write test config
            with open(config_file, "w") as f:
                yaml.dump(mock_config_data, f)

            # Mock the config path resolution
            with patch("orchestrator.config.Path") as mock_path:
                mock_path_instance = MagicMock()
                mock_path_instance.parent.parent.parent = Path(tmpdir)
                mock_path.return_value = mock_path_instance

                config = _load_model_config()

                assert "codex" in config
                assert "claude" in config
                assert config["codex"]["default"] == "gpt-5-codex"
                assert config["claude"]["default"] == "claude-sonnet-4-5"
                assert "claude-opus-4-1" in config["claude"]["allowed_models"]

    def test_load_model_config_file_not_found(self):
        """Test loading config when file doesn't exist."""
        # Clear the LRU cache before test
        _load_model_config.cache_clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Point to non-existent config
            with patch("orchestrator.config.Path") as mock_path:
                mock_path_instance = MagicMock()
                mock_path_instance.parent.parent.parent = Path(tmpdir)
                mock_path.return_value = mock_path_instance

                with pytest.raises(FileNotFoundError) as exc_info:
                    _load_model_config()

                assert "Model configuration file not found" in str(exc_info.value)
                assert "models.yaml" in str(exc_info.value)

    def test_load_model_config_invalid_yaml(self):
        """Test loading config with invalid YAML syntax."""
        # Clear the LRU cache before test
        _load_model_config.cache_clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_file = config_dir / "models.yaml"

            # Write invalid YAML
            with open(config_file, "w") as f:
                f.write("invalid: yaml: syntax:\n  - broken\n    - more broken")

            with patch("orchestrator.config.Path") as mock_path:
                mock_path_instance = MagicMock()
                mock_path_instance.parent.parent.parent = Path(tmpdir)
                mock_path.return_value = mock_path_instance

                with pytest.raises(ValueError) as exc_info:
                    _load_model_config()

                assert "Failed to parse model configuration YAML" in str(exc_info.value)

    def test_load_model_config_caching(self, mock_config_data):
        """Test that configuration is cached using lru_cache."""
        # Clear the LRU cache before test
        _load_model_config.cache_clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_file = config_dir / "models.yaml"

            with open(config_file, "w") as f:
                yaml.dump(mock_config_data, f)

            with patch("orchestrator.config.Path") as mock_path:
                mock_path_instance = MagicMock()
                mock_path_instance.parent.parent.parent = Path(tmpdir)
                mock_path.return_value = mock_path_instance

                # First call
                config1 = _load_model_config()
                # Second call should return cached result
                config2 = _load_model_config()

                # Should be the same object due to caching
                assert config1 is config2

    def test_load_model_config_empty_file(self):
        """Test loading an empty YAML file."""
        # Clear the LRU cache before test
        _load_model_config.cache_clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_file = config_dir / "models.yaml"

            # Write empty file
            with open(config_file, "w") as f:
                f.write("")

            with patch("orchestrator.config.Path") as mock_path:
                mock_path_instance = MagicMock()
                mock_path_instance.parent.parent.parent = Path(tmpdir)
                mock_path.return_value = mock_path_instance

                config = _load_model_config()
                # Empty YAML file returns None, which is acceptable
                assert config is None or config == {}


class TestResolveModel:
    """Test resolve_model — the single model-resolution entry point.

    Model names are NOT validated against an allowlist (see issue #28): any
    non-empty model string is passed through as-is, and only the harness
    default is sourced from config when no model is given.
    """

    @pytest.fixture(autouse=True)
    def _no_env_overrides(self, monkeypatch):
        for var in (
            "MADROX_MODELS_CONFIG",
            "MADROX_MODEL_CLAUDE",
            "MADROX_MODEL_CODEX",
            "MADROX_MODEL_GROK",
        ):
            monkeypatch.delenv(var, raising=False)

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        return {
            "codex": {"default": "gpt-5.6-sol", "known_models": ["gpt-5.6-sol"]},
            "claude": {
                "default": "claude-opus-5",
                "known_models": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
            },
            "grok": {"default": "grok-build-0.1", "known_models": ["grok-build-0.1"]},
        }

    def test_defaults_per_harness(self, mock_config):
        """No model given -> that harness's configured default."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            assert resolve_model("claude", None) == "claude-opus-5"
            assert resolve_model("codex", None) == "gpt-5.6-sol"
            assert resolve_model("grok", None) == "grok-build-0.1"

    def test_explicit_model_passes_through(self, mock_config):
        """Known or unknown, an explicit model is forwarded verbatim."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            assert resolve_model("claude", "claude-sonnet-5") == "claude-sonnet-5"
            assert resolve_model("claude", "some-future-model") == "some-future-model"
            assert resolve_model("codex", "openai.gpt-5.3-codex") == "openai.gpt-5.3-codex"
            assert resolve_model("claude", "CLAUDE-SONNET-5") == "CLAUDE-SONNET-5"

    def test_explicit_model_is_stripped(self, mock_config):
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            assert resolve_model("claude", "  claude-opus-5  ") == "claude-opus-5"

    def test_blank_model_uses_default(self, mock_config):
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            assert resolve_model("claude", "") == "claude-opus-5"
            assert resolve_model("claude", "   ") == "claude-opus-5"

    def test_env_override_beats_config(self, mock_config, monkeypatch):
        monkeypatch.setenv("MADROX_MODEL_CLAUDE", "claude-from-env")
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            assert resolve_model("claude", None) == "claude-from-env"
            # An explicit request still wins over the env default.
            assert resolve_model("claude", "claude-explicit") == "claude-explicit"

    def test_unknown_harness_has_no_default(self, mock_config):
        """Unknown harness -> None, letting the CLI choose (never an exception)."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            assert resolve_model("gemini", None) is None
            assert resolve_model("gemini", "some-model") == "some-model"

    def test_missing_default_key(self):
        broken_config = {"claude": {"known_models": ["claude-opus-5"]}}
        with patch("orchestrator.config._load_model_config", return_value=broken_config):
            assert resolve_model("claude", None) is None

    def test_config_errors_degrade_to_cli_default(self):
        """A missing or broken config must not break spawning."""
        with patch(
            "orchestrator.config._load_model_config",
            side_effect=FileNotFoundError("Config not found"),
        ):
            assert resolve_model("claude", None) is None
            assert resolve_model("claude", "claude-opus-5") == "claude-opus-5"

        with patch(
            "orchestrator.config._load_model_config",
            side_effect=ValueError("Failed to parse YAML"),
        ):
            assert resolve_model("claude", None) is None

    def test_explicit_model_skips_config_load(self):
        """An explicit model never touches the config loader."""
        with patch(
            "orchestrator.config._load_model_config",
            side_effect=AssertionError("config should not be loaded for explicit model"),
        ):
            assert resolve_model("claude", "claude-opus-5") == "claude-opus-5"


class TestGetHarnessConfig:
    """Test get_harness_config — used for per-harness command/extra_args."""

    def test_returns_section(self):
        config = {"grok": {"default": "grok-build-0.1", "command": "/opt/grok"}}
        with patch("orchestrator.config._load_model_config", return_value=config):
            assert get_harness_config("grok")["command"] == "/opt/grok"

    def test_missing_or_malformed_section_is_empty(self):
        with patch("orchestrator.config._load_model_config", return_value={"grok": "nonsense"}):
            assert get_harness_config("grok") == {}
            assert get_harness_config("absent") == {}

    def test_unreadable_config_is_empty(self):
        with patch("orchestrator.config._load_model_config", side_effect=FileNotFoundError("gone")):
            assert get_harness_config("claude") == {}
