"""Persistent state store for instance and server state.

Follows the PositionTracker pattern: JSON file with atomic writes
(temp file + os.replace) and fcntl locking.
"""

from __future__ import annotations

import fcntl
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TRANSIENT_PREFIXES = ("_",)
PRUNE_AFTER_HOURS = 24


class StateStore:
    """Persists instance and server state to JSON files.

    Files:
        {state_dir}/instances.json  — all instance records
        {state_dir}/server.json     — server-level state (session_id, etc.)
    """

    def __init__(self, state_dir: str | Path = "/tmp/madrox_logs/state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.instances_file = self.state_dir / "instances.json"
        self.server_file = self.state_dir / "server.json"
        self._lock_file = self.state_dir / ".lock"

    def _acquire_lock(self):
        """Acquire exclusive lock file for read-modify-write operations."""
        f = self._lock_file.open("w")
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        return f

    def _release_lock(self, f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()

    def _write_json(self, path: Path, data: Any) -> None:
        try:
            temp = path.with_suffix(".tmp")
            with temp.open("w") as f:
                json.dump(data, f, indent=2, default=str)
                f.flush()
            temp.replace(path)
        except Exception as e:
            logger.error(f"Failed to write {path}: {e}")

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            return None
        try:
            with path.open("r") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to read {path}: {e}")
            return None

    @staticmethod
    def _strip_transient(instance: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in instance.items() if not any(k.startswith(p) for p in TRANSIENT_PREFIXES)}

    def save_instance(self, instance: dict[str, Any]) -> None:
        lock = self._acquire_lock()
        try:
            all_instances = self.load_all()
            all_instances[instance["id"]] = self._strip_transient(instance)
            self._write_json(self.instances_file, all_instances)
        finally:
            self._release_lock(lock)

    def save_all(self, instances: dict[str, dict[str, Any]]) -> None:
        lock = self._acquire_lock()
        try:
            data = {iid: self._strip_transient(inst) for iid, inst in instances.items()}
            self._write_json(self.instances_file, data)
        finally:
            self._release_lock(lock)

    def load_all(self) -> dict[str, dict[str, Any]]:
        data = self._read_json(self.instances_file)
        if not isinstance(data, dict):
            return {}
        return data

    def remove_instance(self, instance_id: str) -> None:
        lock = self._acquire_lock()
        try:
            all_instances = self.load_all()
            if instance_id in all_instances:
                del all_instances[instance_id]
                self._write_json(self.instances_file, all_instances)
        finally:
            self._release_lock(lock)

    def save_server_state(self, state: dict[str, Any]) -> None:
        self._write_json(self.server_file, state)

    def load_server_state(self) -> dict[str, Any] | None:
        data = self._read_json(self.server_file)
        if not isinstance(data, dict):
            return None
        return data

    def prune_terminated(self, max_age_hours: float = PRUNE_AFTER_HOURS) -> int:
        """Remove terminated/error instances older than max_age_hours. Returns count removed."""
        lock = self._acquire_lock()
        try:
            all_instances = self.load_all()
            now = datetime.now().timestamp()
            to_remove = []
            for iid, inst in all_instances.items():
                if inst.get("state") not in ("terminated", "error"):
                    continue
                terminated_at = inst.get("terminated_at") or inst.get("created_at")
                if not terminated_at:
                    to_remove.append(iid)
                    continue
                try:
                    ts = datetime.fromisoformat(terminated_at).timestamp()
                    if now - ts > max_age_hours * 3600:
                        to_remove.append(iid)
                except (ValueError, TypeError):
                    to_remove.append(iid)

            for iid in to_remove:
                del all_instances[iid]

            if to_remove:
                self._write_json(self.instances_file, all_instances)
                logger.info(f"Pruned {len(to_remove)} stale instances from state store")

            return len(to_remove)
        finally:
            self._release_lock(lock)
