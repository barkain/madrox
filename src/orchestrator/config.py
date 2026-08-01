"""Model configuration for Madrox harnesses.

Model ids are intentionally *not* validated against an allowlist: vendors ship
new models continuously and the backends serving them change independently of
Madrox, so an allowlist only produces false rejections.  Any non-empty model
string is forwarded to the CLI as-is.

When no model is requested, the harness default is resolved in this order:

1. ``MADROX_MODEL_<HARNESS>`` environment variable (e.g. ``MADROX_MODEL_CLAUDE``)
2. ``<harness>.default`` in ``config/models.yaml``
3. nothing — the CLI picks its own default
"""

import logging
import os
from functools import lru_cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model_config() -> dict:
    """Load model configuration from YAML.

    The path can be overridden with ``MADROX_MODELS_CONFIG`` so operators can
    keep their own defaults outside the repository.

    Returns:
        Model configuration dict

    Raises:
        FileNotFoundError: If the config file doesn't exist
        ValueError: If YAML parsing fails
    """
    config_override = os.getenv("MADROX_MODELS_CONFIG")
    config_path = (
        Path(config_override)
        if config_override
        else Path(__file__).parent.parent.parent / "config" / "models.yaml"
    )

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


def get_harness_config(harness: str) -> dict:
    """Return the YAML section for a harness ({} when missing or unreadable).

    Never raises: harness lookups happen on the spawn path, where a missing or
    malformed config should degrade to CLI defaults rather than kill the spawn.
    """
    try:
        config = _load_model_config() or {}
    except (FileNotFoundError, ValueError, OSError) as e:
        logger.warning(f"Could not load model configuration: {e}")
        return {}

    # A syntactically valid YAML document whose top level is not a mapping (a
    # list, a bare string, …) is truthy, so it survives the `or {}` above and
    # would raise AttributeError on .get() — outside the handler.
    if not isinstance(config, dict):
        logger.warning(
            f"Model configuration must be a mapping, got {type(config).__name__}; ignoring it"
        )
        return {}

    section = config.get(harness)
    return section if isinstance(section, dict) else {}


def _configured_default(harness: str) -> str | None:
    """Default model for a harness from env or YAML, if any."""
    env_override = os.getenv(f"MADROX_MODEL_{harness.upper()}")
    if env_override and env_override.strip():
        return env_override.strip()

    default = get_harness_config(harness).get("default")
    return str(default) if default else None


def resolve_model(harness: str, model: str | None) -> str | None:
    """Resolve the model to launch a harness with.

    Args:
        harness: Harness name ("claude", "codex", "grok", ...)
        model: Explicitly requested model, or None/empty for the default

    Returns:
        The model id, or None when the harness has no configured default (the
        CLI then picks its own — never a hard failure).
    """
    # An explicitly requested model is passed through untouched — no allowlist.
    if model is not None and model.strip():
        return model.strip()

    default = _configured_default(harness)
    if not default:
        logger.debug(f"No default model configured for harness '{harness}' — using CLI default")
    return default
