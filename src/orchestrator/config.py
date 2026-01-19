"""Model configuration for Madrox orchestrator."""

import logging
from functools import lru_cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model_config() -> dict:
    """Load model configuration from YAML file.

    Returns:
        Model configuration dict

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "models.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Model configuration file not found: {config_path}\n"
            "Please ensure config/models.yaml exists in the project root."
        )

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        logger.debug(f"Loaded model configuration from {config_path}")
        return config

    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse model configuration YAML: {e}") from e


def validate_model(provider: str, model: str | None) -> str:
    """Validate and return a model for the given provider.

    Args:
        provider: Provider name ("codex" or "claude")
        model: Model name to validate (None to use default)

    Returns:
        Validated model name

    Raises:
        ValueError: If model is invalid for the provider
        FileNotFoundError: If config file doesn't exist
    """
    model_config = _load_model_config()

    if provider not in model_config:
        raise ValueError(f"Unknown provider: {provider}")

    provider_config = model_config[provider]
    allowed_models = provider_config.get("allowed_models", [])

    # Use default if no model specified
    if model is None:
        default_model = provider_config.get("default")
        # If default is None/null, return None to let CLI use its default
        return default_model if default_model else None

    # Validate model is in allowed list (if list is non-empty)
    if allowed_models and model not in allowed_models:
        allowed = ", ".join(allowed_models)
        raise ValueError(
            f"Invalid model '{model}' for {provider} provider. Allowed models: {allowed}"
        )

    return model
