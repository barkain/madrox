"""Unit tests for config.py - Model configuration validation."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.orchestrator.config import _load_model_config, validate_model


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
            with patch("src.orchestrator.config.Path") as mock_path:
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
            with patch("src.orchestrator.config.Path") as mock_path:
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

            with patch("src.orchestrator.config.Path") as mock_path:
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

            with patch("src.orchestrator.config.Path") as mock_path:
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

            with patch("src.orchestrator.config.Path") as mock_path:
                mock_path_instance = MagicMock()
                mock_path_instance.parent.parent.parent = Path(tmpdir)
                mock_path.return_value = mock_path_instance

                config = _load_model_config()
                # Empty YAML file returns None, which is acceptable
                assert config is None or config == {}


class TestValidateModel:
    """Test validate_model function."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
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

    def test_validate_model_claude_default(self, mock_config):
        """Test validating Claude provider with None model (should return default)."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            result = validate_model("claude", None)
            assert result == "claude-sonnet-4-5"

    def test_validate_model_codex_default(self, mock_config):
        """Test validating Codex provider with None model (should return default)."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            result = validate_model("codex", None)
            assert result == "gpt-5-codex"

    def test_validate_model_claude_valid_sonnet(self, mock_config):
        """Test validating a valid Claude Sonnet model."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            result = validate_model("claude", "claude-sonnet-4-5")
            assert result == "claude-sonnet-4-5"

    def test_validate_model_claude_valid_opus(self, mock_config):
        """Test validating a valid Claude Opus model."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            result = validate_model("claude", "claude-opus-4-1")
            assert result == "claude-opus-4-1"

    def test_validate_model_claude_valid_haiku(self, mock_config):
        """Test validating a valid Claude Haiku model."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            result = validate_model("claude", "claude-haiku-4-5")
            assert result == "claude-haiku-4-5"

    def test_validate_model_codex_valid(self, mock_config):
        """Test validating a valid Codex model."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            result = validate_model("codex", "gpt-5-codex")
            assert result == "gpt-5-codex"

    def test_validate_model_invalid_provider(self, mock_config):
        """Test validating with unknown provider."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            with pytest.raises(ValueError) as exc_info:
                validate_model("unknown-provider", "some-model")

            assert "Unknown provider: unknown-provider" in str(exc_info.value)

    def test_validate_model_invalid_claude_model(self, mock_config):
        """Test validating an invalid Claude model."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            with pytest.raises(ValueError) as exc_info:
                validate_model("claude", "invalid-model")

            error_msg = str(exc_info.value)
            assert "Invalid model 'invalid-model' for claude provider" in error_msg
            assert "Allowed models:" in error_msg
            assert "claude-sonnet-4-5" in error_msg

    def test_validate_model_invalid_codex_model(self, mock_config):
        """Test validating an invalid Codex model."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            with pytest.raises(ValueError) as exc_info:
                validate_model("codex", "gpt-4-turbo")

            error_msg = str(exc_info.value)
            assert "Invalid model 'gpt-4-turbo' for codex provider" in error_msg
            assert "Allowed models:" in error_msg
            assert "gpt-5-codex" in error_msg

    def test_validate_model_case_sensitive(self, mock_config):
        """Test that model validation is case-sensitive."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            # Uppercase should fail
            with pytest.raises(ValueError):
                validate_model("claude", "CLAUDE-SONNET-4-5")

    def test_validate_model_empty_string(self, mock_config):
        """Test validating with empty string model (should fail)."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            with pytest.raises(ValueError) as exc_info:
                validate_model("claude", "")

            assert "Invalid model '' for claude provider" in str(exc_info.value)

    def test_validate_model_whitespace_model(self, mock_config):
        """Test validating with whitespace-only model name."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            with pytest.raises(ValueError):
                validate_model("claude", "   ")

    def test_validate_model_file_not_found_propagates(self):
        """Test that FileNotFoundError from config loading propagates."""
        with patch(
            "src.orchestrator.config._load_model_config",
            side_effect=FileNotFoundError("Config not found"),
        ):
            with pytest.raises(FileNotFoundError):
                validate_model("claude", None)

    def test_validate_model_yaml_error_propagates(self):
        """Test that YAML parsing errors propagate."""
        with patch(
            "src.orchestrator.config._load_model_config",
            side_effect=ValueError("Failed to parse YAML"),
        ):
            with pytest.raises(ValueError) as exc_info:
                validate_model("claude", None)
            assert "Failed to parse YAML" in str(exc_info.value)

    def test_validate_model_all_claude_models(self, mock_config):
        """Test validating all allowed Claude models."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            allowed_models = mock_config["claude"]["allowed_models"]

            for model in allowed_models:
                result = validate_model("claude", model)
                assert result == model

    def test_validate_model_provider_case_sensitive(self, mock_config):
        """Test that provider name is case-sensitive."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            # Uppercase provider should fail
            with pytest.raises(ValueError) as exc_info:
                validate_model("CLAUDE", "claude-sonnet-4-5")

            assert "Unknown provider: CLAUDE" in str(exc_info.value)

    def test_validate_model_with_special_characters(self, mock_config):
        """Test model names with special characters."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            with pytest.raises(ValueError):
                validate_model("claude", "claude@sonnet#4.5")

    def test_validate_model_returns_string(self, mock_config):
        """Test that validate_model always returns a string."""
        with patch("src.orchestrator.config._load_model_config", return_value=mock_config):
            result = validate_model("claude", None)
            assert isinstance(result, str)

            result = validate_model("claude", "claude-opus-4-1")
            assert isinstance(result, str)

    def test_validate_model_config_missing_default(self):
        """Test behavior when provider config is missing default key."""
        broken_config = {
            "claude": {
                "allowed_models": ["claude-sonnet-4-5"],
                # Missing "default" key
            }
        }

        with patch("src.orchestrator.config._load_model_config", return_value=broken_config):
            with pytest.raises(KeyError):
                validate_model("claude", None)

    def test_validate_model_config_missing_allowed_models(self):
        """Test behavior when provider config is missing allowed_models key."""
        broken_config = {
            "claude": {
                "default": "claude-sonnet-4-5",
                # Missing "allowed_models" key
            }
        }

        with patch("src.orchestrator.config._load_model_config", return_value=broken_config):
            with pytest.raises(KeyError):
                validate_model("claude", "claude-sonnet-4-5")

    def test_validate_model_empty_allowed_models(self):
        """Test behavior when allowed_models list is empty."""
        config_with_empty_list = {
            "claude": {
                "default": "claude-sonnet-4-5",
                "allowed_models": [],
            }
        }

        with patch(
            "src.orchestrator.config._load_model_config", return_value=config_with_empty_list
        ):
            # Default should still work
            result = validate_model("claude", None)
            assert result == "claude-sonnet-4-5"

            # But explicit model should fail since allowed list is empty
            with pytest.raises(ValueError):
                validate_model("claude", "claude-sonnet-4-5")
