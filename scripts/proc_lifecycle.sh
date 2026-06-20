#!/usr/bin/env bash
#
# Madrox process-lifecycle helpers (issue #30 — subprocess leak).
#
# Sourced by start_plugin.sh. Kept in a standalone, side-effect-free file so the
# logic can be unit-tested without launching the full plugin stack.
#
# Portable across macOS and Linux (uses only ps/pgrep/kill).
#

# Recursively send a signal to a pid and all of its descendants, children first
# so they are signalled before they can reparent to launchd/init.
kill_tree() {
  local pid="$1" sig="${2:-TERM}" child
  [ -n "$pid" ] || return 0
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    kill_tree "$child" "$sig"
  done
  kill "-$sig" "$pid" 2>/dev/null || true
}

# True while any of the given pids (or their descendants) are still alive.
tree_alive() {
  local pid
  for pid in "$@"; do
    [ -n "$pid" ] || continue
    if kill -0 "$pid" 2>/dev/null || [ -n "$(pgrep -P "$pid" 2>/dev/null)" ]; then
      return 0
    fi
  done
  return 1
}

# TERM a set of process trees, wait out a grace period, then KILL survivors.
#   shutdown_trees <pid> [pid...]
shutdown_trees() {
  local pids="$*" p
  [ -n "${pids// /}" ] || return 0
  for p in $pids; do kill_tree "$p" TERM; done
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    tree_alive $pids || break
    sleep 0.5
  done
  for p in $pids; do kill_tree "$p" KILL; done
}

# Reclaim orphans left by previous sessions that died uncleanly.
#
# Targets only processes that (a) reference the reap scope in their command line
# and (b) have reparented to PID 1 (truly orphaned). Live concurrent sessions keep
# a live shell parent, so their ppid is never 1 and they are never touched.
#
# Scope: for an installed plugin the path is
#   .../plugins/cache/<marketplace>/madrox/<version>
# We reap across ALL versions (the parent ".../madrox" dir) so a freshly-updated
# plugin also reclaims orphans left by the version it replaced. For a dev/source
# checkout (no plugins/cache marker) the scope stays strictly $PLUGIN_ROOT.
#
# Requires PLUGIN_ROOT to be set by the caller.
reap_orphans() {
  : "${PLUGIN_ROOT:?reap_orphans requires PLUGIN_ROOT}"

  local scope="$PLUGIN_ROOT"
  case "$PLUGIN_ROOT" in
    */plugins/cache/*/madrox/*) scope="$(dirname "$PLUGIN_ROOT")" ;;
  esac

  local pid ppid roots=""
  while read -r pid ppid; do
    [ "$ppid" = "1" ] || continue
    # Match the trailing slash so "$scope" only matches paths *under* the scope
    # dir (never a sibling like "${scope}-other"). `-ww` disables ps's
    # column-width truncation (Linux truncates to COLUMNS by default), which would
    # otherwise drop the long venv path from the command line and miss matches.
    case "$(ps -ww -o command= -p "$pid" 2>/dev/null)" in
      *"$scope"/*) roots="$roots $pid" ;;
    esac
  done < <(ps -axo pid=,ppid=)

  [ -n "${roots// /}" ] || return 0
  echo "Reaping orphaned madrox processes from previous sessions:$roots" >&2
  shutdown_trees $roots
}
