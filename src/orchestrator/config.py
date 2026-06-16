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
    """Resolve a model name for the given provider.

    Model names are intentionally NOT validated against a static allowlist.
    The backends that actually serve these models (e.g. the Codex Bedrock
    proxy) change their available model ids independently of Madrox, so a
    hard-coded allowlist only produces false rejections — or worse, silently
    accepts names the backend then 404s on. Any non-empty model string is
    passed through as-is; when no model is given, the provider's configured
    default from ``config/models.yaml`` is used.

    Args:
        provider: Provider name ("codex" or "claude")
        model: Model name to use (None/empty to use the provider default)

    Returns:
        The model name to use

    Raises:
        ValueError: If no model is given and the provider has no default
        FileNotFoundError: If the config file doesn't exist
    """
    # Pass an explicitly requested model straight through — no allowlist check.
    if model is not None and model.strip():
        return model

    # Fall back to the provider's configured default.
    model_config = _load_model_config()
    provider_config = model_config.get(provider) if model_config else None
    default = provider_config.get("default") if provider_config else None

    if not default:
        raise ValueError(f"No default model configured for provider: {provider}")

    return default
