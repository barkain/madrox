"""Unit tests for config.py - Model configuration validation."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from orchestrator.config import _load_model_config, validate_model


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


class TestValidateModel:
    """Test validate_model function.

    Model names are NOT validated against an allowlist (see issue #28): any
    non-empty model string is passed through as-is, and only the provider
    default is sourced from config when no model is given.
    """

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        return {
            "codex": {
                "default": "gpt-5.5",
                "known_models": ["gpt-5.5"],
            },
            "claude": {
                "default": "claude-sonnet-4-5",
                "known_models": [
                    "claude-sonnet-4-5",
                    "claude-opus-4-1",
                    "claude-haiku-4-5",
                ],
            },
        }

    def test_validate_model_claude_default(self, mock_config):
        """Test resolving Claude provider with None model (should return default)."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            result = validate_model("claude", None)
            assert result == "claude-sonnet-4-5"

    def test_validate_model_codex_default(self, mock_config):
        """Test resolving Codex provider with None model (should return default)."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            result = validate_model("codex", None)
            assert result == "gpt-5.5"

    def test_validate_model_passthrough_known(self, mock_config):
        """A known model is passed through unchanged."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            assert validate_model("claude", "claude-opus-4-1") == "claude-opus-4-1"
            assert validate_model("codex", "gpt-5.5") == "gpt-5.5"

    def test_validate_model_passthrough_unknown(self, mock_config):
        """An unknown model is passed through as-is (no allowlist rejection)."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            # Previously these raised ValueError — now they pass through.
            assert validate_model("claude", "some-future-model") == "some-future-model"
            assert validate_model("codex", "openai.gpt-5.3-codex") == "openai.gpt-5.3-codex"
            assert validate_model("claude", "CLAUDE-SONNET-4-5") == "CLAUDE-SONNET-4-5"
            assert validate_model("claude", "claude@sonnet#4.5") == "claude@sonnet#4.5"

    def test_validate_model_unknown_provider_passthrough(self, mock_config):
        """An explicit model is returned even for an unknown provider."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            assert validate_model("unknown-provider", "some-model") == "some-model"

    def test_validate_model_empty_string_uses_default(self, mock_config):
        """Empty string falls back to the provider default."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            assert validate_model("claude", "") == "claude-sonnet-4-5"

    def test_validate_model_whitespace_uses_default(self, mock_config):
        """Whitespace-only model falls back to the provider default."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            assert validate_model("claude", "   ") == "claude-sonnet-4-5"

    def test_validate_model_no_default_for_provider(self, mock_config):
        """Requesting a default for an unknown provider raises."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            with pytest.raises(ValueError) as exc_info:
                validate_model("unknown-provider", None)
            assert "No default model configured" in str(exc_info.value)

    def test_validate_model_file_not_found_propagates(self):
        """FileNotFoundError from config loading propagates when a default is needed."""
        with patch(
            "orchestrator.config._load_model_config",
            side_effect=FileNotFoundError("Config not found"),
        ):
            with pytest.raises(FileNotFoundError):
                validate_model("claude", None)

    def test_validate_model_explicit_model_skips_config(self):
        """An explicit model never touches the config loader."""
        with patch(
            "orchestrator.config._load_model_config",
            side_effect=AssertionError("config should not be loaded for explicit model"),
        ):
            assert validate_model("claude", "claude-opus-4-6") == "claude-opus-4-6"

    def test_validate_model_yaml_error_propagates(self):
        """YAML parsing errors propagate when resolving a default."""
        with patch(
            "orchestrator.config._load_model_config",
            side_effect=ValueError("Failed to parse YAML"),
        ):
            with pytest.raises(ValueError) as exc_info:
                validate_model("claude", None)
            assert "Failed to parse YAML" in str(exc_info.value)

    def test_validate_model_returns_string(self, mock_config):
        """Test that validate_model always returns a string."""
        with patch("orchestrator.config._load_model_config", return_value=mock_config):
            assert isinstance(validate_model("claude", None), str)
            assert isinstance(validate_model("claude", "claude-opus-4-1"), str)

    def test_validate_model_config_missing_default(self):
        """A provider config missing its default raises when a default is needed."""
        broken_config = {
            "claude": {
                "known_models": ["claude-sonnet-4-5"],
                # Missing "default" key
            }
        }

        with patch("orchestrator.config._load_model_config", return_value=broken_config):
            with pytest.raises(ValueError) as exc_info:
                validate_model("claude", None)
            assert "No default model configured" in str(exc_info.value)
