"""Small helper for read-modify-write updates of a CLI's TOML config file.

Codex keeps both workspace trust levels and HTTP MCP servers in
``~/.codex/config.toml``.  Loading and dumping that file once per change (as
the spawn path used to do) rewrites it several times per instance; this helper
applies a whole batch of edits in a single load/dump and skips the write
entirely when nothing changed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import toml

logger = logging.getLogger(__name__)


def update_toml_config(path: Path, mutate: Callable[[dict[str, Any]], bool]) -> bool:
    """Apply ``mutate`` to the TOML document at ``path`` and write it back.

    Args:
        path: Config file path (parent directories are created as needed)
        mutate: Callback that edits the document in place and returns True when
            it actually changed something

    Returns:
        True when the file was rewritten.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    config: dict[str, Any] = {}
    if path.exists():
        try:
            config = toml.load(path)
        except (toml.TomlDecodeError, OSError) as e:
            logger.warning(f"Could not parse {path} ({e}) — rewriting it from scratch")
            config = {}

    if not mutate(config):
        return False

    with path.open("w") as f:
        toml.dump(config, f)
    return True
