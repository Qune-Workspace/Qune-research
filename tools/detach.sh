#!/usr/bin/env bash
# tools/detach.sh: run a long fetch so that it outlives the shell that launched it.
#
#   bash tools/detach.sh start <name> <logfile> -- <command> [args...]
#   bash tools/detach.sh status <name>
#   bash tools/detach.sh wait <name> [seconds]      (default 3600; exit 2 on timeout)
#   bash tools/detach.sh --self-test                (in `make lint`; skipped where no
#                                                   user service manager is reachable)
#
# Why this exists (research/POST_MORTEMS.md, "A detach rule the loop's own shell
# could not honour", 2026-11-04): the learning loop's shell kills every process
# it started when the call that started it returns, including processes that
# `setsid` put in a new session and processes `nohup ... & disown` had let go,
# so the "setsid nohup ... &" recipe of 2026-11-02 left empty logs and no
# process. A transient systemd user unit lives in its own control group and
# runs to completion. The command's output goes to the log file with a dated
# start line and an end line that carries the exit code, so a later run reads
# completion from the file alone.
#
# The unit name is qr-<name>; a second start under a name that is still active
# is refused by systemd (exit 1, nothing launched), so one fetch cannot be
# started twice by mistake. Finished units are collected and disappear; the log
# file is the record. The unit runs with the launcher's PATH (2026-11-12): a
# user unit otherwise starts from the service manager's environment, and a
# check inside it that skips when a tool is "not installed" then skips on the
# one host where the tool is installed.
set -u

usage() { sed -n '2,8p' "$0"; exit "${1:-1}"; }

have_user_manager() {
  command -v systemd-run >/dev/null 2>&1 || return 1
  systemctl --user list-units --no-pager --no-legend >/dev/null 2>&1
}

unit_name() { printf 'qr-%s' "$1"; }

do_start() {
  [ $# -ge 4 ] || usage
  local name=$1 log=$2
  shift 2
  [ "$1" = "--" ] || usage
  shift
  [ $# -ge 1 ] || usage
  log=$(realpath -m "$log")
  mkdir -p "$(dirname "$log")"
  have_user_manager || { echo "detach: no user service manager reachable; nothing launched" >&2; return 1; }
  local unit
  unit=$(unit_name "$name")
  # The wrapper writes the dated start and end lines into the same log; the
  # command itself runs with the launcher's working directory and the
  # launcher's PATH. A user unit starts from the service manager's own
  # environment, not the launcher's, and that PATH has no ~/.local/bin, so the
  # first `make lint` run through this launcher (2026-11-12 06:26Z) found no
  # gitleaks and its scan self-test skipped with exit 0 (research/POST_MORTEMS.md,
  # "A lint that passed by skipping", 2026-11-12).
  if systemd-run --user --quiet --collect --unit="$unit" --working-directory="$PWD" \
      --setenv=PATH="$PATH" \
      -p StandardOutput=append:"$log" -p StandardError=append:"$log" -- \
      bash -c 'echo "detach start $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; "$@"; rc=$?; echo "detach end $(date -u +%Y-%m-%dT%H:%M:%SZ) rc=$rc"; exit $rc' \
      detach "$@"; then
    echo "detach: started $unit (log $log)"
  else
    echo "detach: refused; $unit may still be active (bash tools/detach.sh status $name)" >&2
    return 1
  fi
}

do_status() {
  [ $# -eq 1 ] || usage
  local unit
  unit=$(unit_name "$1")
  have_user_manager || { echo "detach: no user service manager reachable" >&2; return 1; }
  local state
  state=$(systemctl --user is-active "$unit" 2>/dev/null || true)
  echo "$unit: ${state:-unknown} (a finished unit is collected; read the log's end line)"
  [ "$state" = "active" ]
}

do_wait() {
  [ $# -ge 1 ] || usage
  local unit limit=${2:-3600} waited=0
  unit=$(unit_name "$1")
  have_user_manager || { echo "detach: no user service manager reachable" >&2; return 1; }
  while [ "$(systemctl --user is-active "$unit" 2>/dev/null || true)" = "active" ]; do
    [ "$waited" -ge "$limit" ] && { echo "detach: $unit still active after ${limit}s" >&2; return 2; }
    sleep 1
    waited=$((waited + 1))
  done
  echo "detach: $unit finished (waited ${waited}s)"
}

self_test() {
  if ! have_user_manager; then
    echo "detach self-test: skipped (no user service manager reachable; the launcher is used only on the host that runs the loop)"
    return 0
  fi
  local dir name log fails=0 unit own_cg unit_cg self
  self=$(realpath "$0")
  dir=$(mktemp -d)
  name="selftest-$$"
  log="$dir/run.log"
  unit=$(unit_name "$name")
  trap 'systemctl --user stop "$unit" >/dev/null 2>&1 || true; rm -rf "$dir"' RETURN

  # 1. a unit starts, lives in a control group other than the launcher's, and
  #    runs to completion with the log's start line, output and end line.
  ( cd "$dir" && bash "$self" start "$name" "$log" -- sh -c 'echo one; pwd; sleep 2; echo two' ) >/dev/null \
    || { echo "FAIL: start refused"; fails=$((fails + 1)); }
  own_cg=$(sed -n 's/^0::\(.*\)$/\1/p' /proc/self/cgroup)
  unit_cg=$(systemctl --user show -p ControlGroup --value "$unit" 2>/dev/null)
  if [ -z "$unit_cg" ] || [ "$unit_cg" = "$own_cg" ]; then
    echo "FAIL: unit control group '$unit_cg' is not separate from the launcher's '$own_cg'"
    fails=$((fails + 1))
  fi
  bash "$self" wait "$name" 30 >/dev/null || { echo "FAIL: wait"; fails=$((fails + 1)); }
  grep -q '^detach start 20' "$log" || { echo "FAIL: no start line"; fails=$((fails + 1)); }
  grep -qx 'one' "$log" && grep -qx 'two' "$log" || { echo "FAIL: output missing"; fails=$((fails + 1)); }
  grep -qx "$dir" "$log" || { echo "FAIL: working directory not kept"; fails=$((fails + 1)); }
  grep -q '^detach end 20.* rc=0$' "$log" || { echo "FAIL: no end line with rc=0"; fails=$((fails + 1)); }

  # 2. a failing command's exit code reaches the end line.
  : > "$log"
  bash "$self" start "$name" "$log" -- sh -c 'exit 3' >/dev/null || { echo "FAIL: second start"; fails=$((fails + 1)); }
  bash "$self" wait "$name" 30 >/dev/null
  grep -q 'rc=3$' "$log" || { echo "FAIL: exit code 3 not recorded"; fails=$((fails + 1)); }

  # 3. a second start under an active name is refused and launches nothing.
  : > "$log"
  bash "$self" start "$name" "$log" -- sleep 20 >/dev/null || { echo "FAIL: third start"; fails=$((fails + 1)); }
  if bash "$self" start "$name" "$log" -- sh -c 'echo DUPLICATE' >/dev/null 2>&1; then
    echo "FAIL: duplicate name accepted"; fails=$((fails + 1))
  fi
  bash "$self" status "$name" >/dev/null || { echo "FAIL: status not active"; fails=$((fails + 1)); }
  systemctl --user stop "$unit" >/dev/null 2>&1
  sleep 1
  grep -q DUPLICATE "$log" && { echo "FAIL: duplicate ran"; fails=$((fails + 1)); }

  # 4. the launcher's PATH reaches the command: a stub that exists only in a
  #    folder the launcher prepends to PATH is found inside the unit, and the
  #    unit's PATH is the launcher's (2026-11-12; before the fix the unit saw
  #    the service manager's PATH, without ~/.local/bin).
  : > "$log"
  mkdir -p "$dir/bin"
  printf '#!/bin/sh\necho stub-ran\n' > "$dir/bin/qr-stub-$$"
  chmod +x "$dir/bin/qr-stub-$$"
  PATH="$dir/bin:$PATH" bash "$self" start "$name" "$log" -- sh -c "command -v qr-stub-$$ && qr-stub-$$ && echo \"unit PATH=\$PATH\"" >/dev/null \
    || { echo "FAIL: fourth start"; fails=$((fails + 1)); }
  bash "$self" wait "$name" 30 >/dev/null
  grep -qx 'stub-ran' "$log" || { echo "FAIL: a command on the launcher's PATH was not found inside the unit"; fails=$((fails + 1)); }
  grep -qxF "unit PATH=$dir/bin:$PATH" "$log" || { echo "FAIL: the unit's PATH is not the launcher's"; fails=$((fails + 1)); }

  if [ "$fails" -eq 0 ]; then
    echo "detach self-test: pass (own control group, dated start and end lines, exit code kept, duplicate name refused, launcher's PATH carried)"
    return 0
  fi
  echo "detach self-test: $fails failure(s)"
  return 1
}

case "${1:-}" in
  start) shift; do_start "$@" ;;
  status) shift; do_status "$@" ;;
  wait) shift; do_wait "$@" ;;
  --self-test) self_test ;;
  -h|--help) usage 0 ;;
  *) usage ;;
esac
