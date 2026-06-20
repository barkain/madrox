"""End-to-end lifecycle tests for the plugin process supervisor (issue #30).

Unlike ``tests/test_proc_lifecycle.py`` (which unit-tests the bash helpers in
isolation), these spin up the *real* HTTP backend — which starts a
``multiprocessing.Manager`` daemon and a ``resource_tracker`` child — under a
launcher that mirrors ``start_plugin.sh``'s backend + proxy + trap structure,
then assert that the whole process tree is reclaimed when the session ends.

Two failure modes from the issue are covered:

* **SIGTERM** (normal session end): the launcher's cleanup trap must tear the
  backend tree down — including the Manager daemon that previously orphaned.
* **SIGKILL** (hard crash, no trap can run): the backend's parent-death
  watchdog must self-terminate it once it reparents to PID 1.

Marked ``integration`` (slower — a real server boot); deselect with
``-m 'not integration'``.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        sys.platform.startswith("win"), reason="POSIX process supervision (ps/pgrep/kill)"
    ),
]

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "scripts" / "proc_lifecycle.sh"
RUN_ORCHESTRATOR = REPO_ROOT / "run_orchestrator.py"


def _launcher_script() -> str:
    """A minimal stand-in for start_plugin.sh: backend + fake proxy + trap.

    Uses the real ``scripts/proc_lifecycle.sh`` so the actual ``shutdown_trees``
    cleanup path is exercised. The frontend is intentionally omitted (slow, and
    not relevant to the leak).
    """
    return f"""
set -e
. "{HELPER}"

BE_PID=""; PROXY_PID=""; CLEANED=""
cleanup() {{
  [ -n "$CLEANED" ] && return; CLEANED=1
  shutdown_trees "$PROXY_PID" "$BE_PID"
  wait 2>/dev/null || true
}}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

PORT=$(python3 -c "import socket;s=socket.socket();s.bind(('',0));print(s.getsockname()[1]);s.close()")
MADROX_TRANSPORT=http ORCHESTRATOR_PORT=$PORT \
  "{sys.executable}" "{RUN_ORCHESTRATOR}" >/dev/null 2>&1 &
BE_PID=$!
echo "BE_PID=$BE_PID"
echo "PORT=$PORT"

for _ in $(seq 1 120); do
  curl -sf "http://localhost:$PORT/health" >/dev/null 2>&1 && break
  kill -0 "$BE_PID" 2>/dev/null || {{ echo "BACKEND_DIED"; exit 1; }}
  sleep 0.5
done
echo "READY"

# Fake STDIO proxy: inherits stdin like the real one, just blocks.
sleep 600 0<&0 &
PROXY_PID=$!
wait "$PROXY_PID"
"""


def _descendants(pid: int) -> list[int]:
    """Recursively collect all descendant PIDs of ``pid`` via pgrep -P."""
    out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout
    kids = [int(p) for p in out.split()]
    result: list[int] = []
    for kid in kids:
        result.append(kid)
        result.extend(_descendants(kid))
    return result


def _ppid(pid: int) -> int | None:
    out = subprocess.run(
        ["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True
    ).stdout.strip()
    return int(out) if out else None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_until(predicate, timeout: float, interval: float = 0.25) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


class _Launcher:
    """Runs the launcher script in its own session and tracks the backend tree."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            ["bash", "-c", _launcher_script()],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(REPO_ROOT),
            start_new_session=True,  # own process group, for safety-net teardown
        )
        self.be_pid: int | None = None
        self._await_ready()

    def _await_ready(self) -> None:
        deadline = time.monotonic() + 90
        assert self.proc.stdout is not None
        while time.monotonic() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            if line.startswith("BE_PID="):
                self.be_pid = int(line.split("=", 1)[1])
            elif line == "READY":
                return
            elif line in ("BACKEND_DIED",):
                raise AssertionError("backend failed to start")
        raise AssertionError("launcher never reported READY")

    def backend_tree(self) -> list[int]:
        if self.be_pid is None:
            return []
        return [self.be_pid, *_descendants(self.be_pid)]

    def safety_kill(self) -> None:
        # Force-clean the whole launcher session and any survivors.
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        if self.be_pid is not None:
            for pid in self.backend_tree():
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass


@pytest.fixture
def launcher():
    inst = _Launcher()
    try:
        yield inst
    finally:
        inst.safety_kill()


def test_sigterm_reaps_backend_tree(launcher):
    """SIGTERM to the launcher tears down the backend + its multiprocessing tree."""
    # The Manager daemon / resource_tracker children should be present.
    assert _wait_until(lambda: len(_descendants(launcher.be_pid)) >= 1, timeout=15), (
        "backend never spawned its multiprocessing children"
    )
    tree = launcher.backend_tree()
    assert launcher.be_pid in tree

    launcher.proc.terminate()  # SIGTERM -> trap -> shutdown_trees

    assert _wait_until(lambda: not any(_alive(p) for p in tree), timeout=15), (
        f"backend tree survived SIGTERM cleanup: {[p for p in tree if _alive(p)]}"
    )


def test_sigkill_triggers_parent_death_watchdog(launcher):
    """SIGKILL the launcher (no trap can run); the watchdog must self-reap the backend."""
    assert _wait_until(lambda: len(_descendants(launcher.be_pid)) >= 1, timeout=15)
    tree = launcher.backend_tree()
    be_pid = launcher.be_pid

    # Hard-kill the launcher only: the backend reparents to PID 1 (orphaned),
    # and nothing else signals it. Without the watchdog it would leak forever.
    launcher.proc.kill()
    launcher.proc.wait(timeout=5)

    # Confirm the backend actually orphaned (reparented to PID 1) before the watchdog fires.
    assert _wait_until(lambda: _ppid(be_pid) == 1, timeout=3), (
        "backend did not reparent to PID 1 after launcher SIGKILL"
    )

    # Watchdog polls every ~2s, then uvicorn shuts down gracefully.
    assert _wait_until(lambda: not any(_alive(p) for p in tree), timeout=20), (
        f"backend tree survived after parent SIGKILL: {[p for p in tree if _alive(p)]}"
    )
