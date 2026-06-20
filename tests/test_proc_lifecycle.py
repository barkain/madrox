"""Regression tests for the plugin process-lifecycle helpers (issue #30).

These exercise the bash helpers in ``scripts/proc_lifecycle.sh`` that prevent the
subprocess leak: ``kill_tree`` (tear down a whole process tree) and
``reap_orphans`` (reclaim processes orphaned to PID 1 by a previous session that
died uncleanly, e.g. via SIGKILL).

The tests build real process trees with a unique marker in their command line,
orphan them to PID 1, and assert the helpers reclaim them. POSIX-only.
"""

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform.startswith("win"), reason="POSIX process-tree helpers (ps/pgrep/kill)"
)

HELPER = Path(__file__).resolve().parents[1] / "scripts" / "proc_lifecycle.sh"


def _marker() -> str:
    """A unique directory-like token that won't collide with real processes.

    Mirrors a plugin root: every process in a spawned tree carries this token in
    its command line, and it is what ``reap_orphans`` matches against.
    """
    return f"/tmp/madrox_proctest_{uuid.uuid4().hex}"


def _ppid(pid: int) -> int | None:
    """Return the parent PID of ``pid``, or None if it no longer exists."""
    out = subprocess.run(
        ["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True
    ).stdout.strip()
    return int(out) if out else None


def _pids_matching(marker: str) -> list[int]:
    """Return PIDs whose command line contains the marker (excluding the grep)."""
    # `-ww` disables ps column-width truncation (Linux truncates to COLUMNS by
    # default), which would otherwise drop the marker from the end of long lines.
    out = subprocess.run(
        ["ps", "-ww", "-axo", "pid=,command="], capture_output=True, text=True
    ).stdout
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_str, _, cmd = line.partition(" ")
        if marker in cmd and "ps -axo" not in cmd:
            try:
                pids.append(int(pid_str))
            except ValueError:
                pass
    return pids


def _run_helper(snippet: str, plugin_root: str = "") -> subprocess.CompletedProcess:
    """Source the helper file and run a snippet against it under bash."""
    script = f'. "{HELPER}"\n{snippet}\n'
    env = dict(os.environ)
    if plugin_root:
        env["PLUGIN_ROOT"] = plugin_root
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)


def _spawn_orphan_tree(marker: str) -> None:
    """Spawn a 2-level python process tree, orphaned to PID 1.

    A short-lived bash launcher backgrounds a python "parent" (whose argv carries
    the marker) that in turn spawns a python "child"; the launcher then exits,
    reparenting the tree to PID 1 — exactly the post-SIGKILL leak shape.
    """
    parent_arg = f"{marker}/run_orchestrator.py"
    child_arg = f"{marker}/manager_daemon"
    py = sys.executable
    launcher = (
        f'{py} -c "import subprocess,sys,time;'
        f"subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)','{child_arg}']);"
        f'time.sleep(120)" "{parent_arg}" &'
    )
    # The launcher bash exits immediately, orphaning the python tree.
    subprocess.run(["bash", "-c", launcher], check=True)


def _wait_for(predicate, timeout: float = 10.0, interval: float = 0.2) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


@pytest.fixture
def cleanup_marker():
    """Ensure any test processes are reaped even if an assertion fails."""
    markers: list[str] = []
    yield markers
    for marker in markers:
        for pid in _pids_matching(marker):
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass


def test_reap_orphans_reclaims_orphaned_tree(cleanup_marker):
    """reap_orphans kills a previous session's orphaned (ppid==1) process tree."""
    marker = _marker()
    cleanup_marker.append(marker)
    plugin_root = marker  # the marker dir stands in for the plugin root

    _spawn_orphan_tree(marker)

    # Both parent and child should be alive and carrying the marker.
    assert _wait_for(lambda: len(_pids_matching(marker)) >= 2), "orphan tree did not start"
    # At least one process in the tree should have reparented to PID 1 (true orphan).
    assert _wait_for(lambda: any(_ppid(pid) == 1 for pid in _pids_matching(marker))), (
        "tree did not orphan to PID 1"
    )

    result = _run_helper("reap_orphans", plugin_root=plugin_root)
    assert result.returncode == 0, result.stderr

    assert _wait_for(lambda: _pids_matching(marker) == []), (
        f"orphans survived reaping: {_pids_matching(marker)}"
    )


def test_reap_orphans_ignores_unrelated_plugin_root(cleanup_marker):
    """reap_orphans must not touch processes outside its own PLUGIN_ROOT."""
    marker = _marker()
    cleanup_marker.append(marker)

    _spawn_orphan_tree(marker)
    assert _wait_for(lambda: len(_pids_matching(marker)) >= 2)

    # A different plugin root must leave our tree untouched.
    other_root = f"/tmp/some_other_plugin_{uuid.uuid4().hex}"
    result = _run_helper("reap_orphans", plugin_root=other_root)
    assert result.returncode == 0, result.stderr

    time.sleep(1.0)
    assert len(_pids_matching(marker)) >= 2, "unrelated processes were wrongly reaped"


def test_reap_orphans_reaps_across_plugin_versions(cleanup_marker):
    """An updated install reaps orphans left by the version it replaced.

    For a plugins/cache install path, reap scope is the version-agnostic
    ".../madrox" dir, so launching a new version reclaims old-version orphans.
    """
    base = f"/tmp/plugins/cache/barkain-plugins/madrox_{uuid.uuid4().hex}"
    old_version_root = f"{base}/madrox/1.8.1"
    new_version_root = f"{base}/madrox/1.8.2"
    cleanup_marker.append(old_version_root)

    # Orphan tree from the OLD version.
    _spawn_orphan_tree(old_version_root)
    assert _wait_for(lambda: len(_pids_matching(old_version_root)) >= 2)

    # The NEW version's launch must reap the old version's orphans.
    result = _run_helper("reap_orphans", plugin_root=new_version_root)
    assert result.returncode == 0, result.stderr

    assert _wait_for(lambda: _pids_matching(old_version_root) == []), (
        f"old-version orphans survived: {_pids_matching(old_version_root)}"
    )


def test_kill_tree_kills_descendants(cleanup_marker):
    """kill_tree terminates a process and all of its descendants."""
    marker = _marker()
    cleanup_marker.append(marker)

    # A parent we keep a handle on, with a grandchild, so we can target the root.
    child_arg = f"{marker}/manager_daemon"
    py = sys.executable
    proc = subprocess.Popen(
        [
            py,
            "-c",
            "import subprocess,sys,time;"
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)',sys.argv[1]]);"
            "time.sleep(120)",
            child_arg,
        ]
    )
    try:
        assert _wait_for(lambda: len(_pids_matching(marker)) >= 2)
        result = _run_helper(f"kill_tree {proc.pid} TERM")
        assert result.returncode == 0, result.stderr
        assert _wait_for(lambda: _pids_matching(marker) == []), (
            f"descendants survived kill_tree: {_pids_matching(marker)}"
        )
    finally:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
