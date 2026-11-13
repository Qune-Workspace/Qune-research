#!/usr/bin/env bash
# tools/lint.sh: the runner behind `make lint`. It runs every check of the
# repository in order, stops at the first failure naming the check, and ends
# with one summary line of its own:
#
#   lint: 15 checks run, 0 skipped
#   lint: pass
#
# A check that cannot run where it is started says so with a line of the form
# `<name> self-test: skipped (<reason>)` and exits 0 (tools/detach.sh where no
# user service manager is reachable, tools/scan.sh where gitleaks is not
# installed; both true on the CI runner, neither on the host that runs the
# learning loop). Until 2026-11-13 the lint's exit code could not tell a check
# that passed from one that skipped, so the first `make lint` run through the
# detached launcher (2026-11-12 06:26Z) was cited as passed while its leak-scan
# self-test had skipped, and the rule written that day asked each run to count
# the `skipped (` lines in the log by hand (research/POST_MORTEMS.md, "A lint
# that passed by skipping"). The runner counts them itself: a skip is a failure
# unless LINT_ALLOW_SKIP names the check (space-separated names, e.g.
# `LINT_ALLOW_SKIP="detach scan"` where those tools are absent by design), and
# the summary line names every check that skipped, allowed or not.
#
#   PYTHON=.venv/bin/python bash tools/lint.sh      (what `make lint` runs)
#   bash tools/lint.sh --self-test                  (in `make lint` itself: a
#       stub check that prints a skip line fails the run, is admitted when named
#       in LINT_ALLOW_SKIP and is counted in the summary either way; a stub that
#       exits 1 stops the run with its name and exit code; a clean list passes
#       with "0 skipped")
set -u

PYTHON=${PYTHON:-$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)}
SKIP_PATTERN='self-test: skipped ('

# Name and command of every check, in the order `make lint` has always run
# them. The name is what the summary line and LINT_ALLOW_SKIP use.
checks() {
  cat <<EOF
ruff|$PYTHON -m ruff check .
mypy|$PYTHON -m mypy
links|$PYTHON tools/check_links.py
glance|$PYTHON tools/check_glance.py
dashboard|$PYTHON tools/check_dashboard.py
question-gate|$PYTHON tools/check_question_gate.py
due|$PYTHON tools/check_due.py
bound-defaults|$PYTHON tools/check_bound_defaults.py
stamp-compares|$PYTHON tools/check_stamp_compares.py
data-terms|$PYTHON tools/check_data_terms.py
view-brier|$PYTHON tools/check_view_brier.py
skill-pages|$PYTHON tools/check_skill_pages.py
lint-runner|bash tools/lint.sh --self-test
detach|bash tools/detach.sh --self-test
scan|bash tools/scan.sh --self-test
EOF
}

allowed_to_skip() {  # $1 = check name
  local n
  for n in ${LINT_ALLOW_SKIP:-}; do [ "$n" = "$1" ] && return 0; done
  return 1
}

# run_checks reads "name|command" lines on stdin, prints each command and its
# output as make did, and returns 0 only when every check ran and no check
# skipped without being named in LINT_ALLOW_SKIP.
run_checks() {
  local name cmd out rc n_run=0 skipped="" refused="" line
  out=$(mktemp)
  trap 'rm -f "$out"' RETURN
  while IFS='|' read -r name cmd; do
    [ -n "$name" ] || continue
    echo "$cmd"
    # stdin closed: the check must not read the rest of this list.
    bash -c "$cmd" </dev/null 2>&1 | tee "$out"
    rc=${PIPESTATUS[0]}
    n_run=$((n_run + 1))
    if [ "$rc" -ne 0 ]; then
      echo "lint: FAIL at check '$name' (rc=$rc) after $n_run check(s)"
      return "$rc"
    fi
    if grep -q -F "$SKIP_PATTERN" "$out"; then
      skipped="$skipped $name"
      allowed_to_skip "$name" || refused="$refused $name"
    fi
  done
  line="lint: $n_run checks run, $(echo $skipped | wc -w) skipped"
  [ -n "$skipped" ] && line="$line (${skipped# })"
  echo "$line"
  if [ -n "$refused" ]; then
    echo "lint: FAIL: skipped and not named in LINT_ALLOW_SKIP (${LINT_ALLOW_SKIP:-unset}):${refused}; a skip on the host that runs the loop is a defect, not a pass"
    return 1
  fi
  echo "lint: pass"
  return 0
}

self_test() {
  local fails=0 out rc
  # 1. a check that prints a skip line and exits 0 fails the run by default,
  #    and the summary names it.
  out=$(printf 'alpha|echo ok\nbeta|echo "beta self-test: skipped (stub reason)"\n' | LINT_ALLOW_SKIP= run_checks 2>&1); rc=$?
  if [ "$rc" -ne 1 ] || ! grep -q '^lint: 2 checks run, 1 skipped (beta)$' <<<"$out" || ! grep -q 'not named in LINT_ALLOW_SKIP' <<<"$out"; then
    echo "FAIL: an unnamed skip did not fail the run (rc=$rc)"; echo "$out" | sed 's/^/    /'; fails=$((fails + 1))
  fi
  # 2. the same check is admitted when LINT_ALLOW_SKIP names it, and is still
  #    counted and named in the summary line.
  out=$(printf 'alpha|echo ok\nbeta|echo "beta self-test: skipped (stub reason)"\n' | LINT_ALLOW_SKIP="other beta" run_checks 2>&1); rc=$?
  if [ "$rc" -ne 0 ] || ! grep -q '^lint: 2 checks run, 1 skipped (beta)$' <<<"$out" || ! grep -q '^lint: pass$' <<<"$out"; then
    echo "FAIL: a named skip was not admitted and counted (rc=$rc)"; echo "$out" | sed 's/^/    /'; fails=$((fails + 1))
  fi
  # 3. naming another check does not admit this one.
  out=$(printf 'beta|echo "beta self-test: skipped (stub reason)"\n' | LINT_ALLOW_SKIP="alpha" run_checks 2>&1); rc=$?
  [ "$rc" -eq 1 ] || { echo "FAIL: a skip was admitted by another check's name (rc=$rc)"; fails=$((fails + 1)); }
  # 4. a failing check stops the run with its name and exit code; later checks
  #    do not run.
  out=$(printf 'alpha|echo ok\ngamma|sh -c "echo broken; exit 3"\ndelta|echo "delta self-test: skipped (never reached)"\n' | run_checks 2>&1); rc=$?
  if [ "$rc" -ne 3 ] || ! grep -q "^lint: FAIL at check 'gamma' (rc=3) after 2 check(s)$" <<<"$out" || grep -q 'never reached' <<<"$out"; then
    echo "FAIL: a failing check did not stop the run with its name (rc=$rc)"; echo "$out" | sed 's/^/    /'; fails=$((fails + 1))
  fi
  # 5. a clean list passes with a zero count and no names.
  out=$(printf 'alpha|echo ok\nbeta|echo "beta self-test: pass"\n' | LINT_ALLOW_SKIP= run_checks 2>&1); rc=$?
  if [ "$rc" -ne 0 ] || ! grep -q '^lint: 2 checks run, 0 skipped$' <<<"$out" || ! grep -q '^lint: pass$' <<<"$out"; then
    echo "FAIL: a clean list did not pass with 0 skipped (rc=$rc)"; echo "$out" | sed 's/^/    /'; fails=$((fails + 1))
  fi
  # 6. the live list names every self-test that can skip, so a skip line from
  #    either is attributed to a name LINT_ALLOW_SKIP can carry.
  for n in detach scan; do
    checks | grep -q "^$n|" || { echo "FAIL: live check list has no '$n' entry"; fails=$((fails + 1)); }
  done
  if [ "$fails" -eq 0 ]; then
    echo "lint-runner self-test: pass (unnamed skip fails, named skip admitted and counted, other name does not admit, failing check stops with its name and rc, clean list 0 skipped, live list names detach and scan)"
    return 0
  fi
  echo "lint-runner self-test: $fails failure(s)"
  return 1
}

case "${1:-}" in
  "") checks | run_checks ;;
  --self-test) self_test ;;
  --list) checks ;;
  *) sed -n '2,30p' "$0"; exit 1 ;;
esac
