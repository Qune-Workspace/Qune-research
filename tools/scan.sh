#!/usr/bin/env bash
# Pre-commit / pre-push leak scan for this repository.
#  1. gitleaks over the files git could publish (tracked, plus untracked files
#     that .gitignore does not exclude) and over the full git history
#     (secrets, keys, tokens). Git-ignored paths are never read: the virtual
#     environment, caches and the studies' raw data (Study 013's daily
#     snapshots alone grow by about a quarter of a gigabyte a day) can never
#     reach the public repository, and scanning them made every commit and
#     every push wait on them (research/POST_MORTEMS.md, "A leak scan that
#     read what it could never publish", 2026-11-05).
#  2. Generic patterns that should never appear in a public research repo:
#     IPv4 addresses, e-mail addresses, private-key headers, broker key prefixes.
#  3. An optional private denylist (one regex per line) passed via SCAN_DENYLIST.
#     It lives outside the repo so the sensitive terms themselves are never published.
#  4. `bash tools/scan.sh --self-test` (in `make lint`; skipped with a line where
#     gitleaks is not installed): in a throwaway repository, a secret in a
#     git-ignored file is neither read nor reported, the same secret in an
#     untracked file that git would publish blocks, and a clean tree passes.
# Exit code 0 = clean; anything else = stop and investigate before pushing.
set -euo pipefail

SELF=$(realpath "$0")

# Hard-link every publishable file into a staging folder under .git/ (same
# filesystem, so no bytes are copied; cp -p is the fallback) and point gitleaks
# at that folder. gitleaks 8.30's `dir` command has no option to honour
# .gitignore, so the list comes from git itself, the same list the pattern
# pass below has always used.
stage_publishable() {  # $1 = stage dir; sets n_files and n_bytes
  local f
  n_files=0
  while IFS= read -r -d '' f; do
    [ -f "$f" ] || continue        # deleted-but-tracked, submodules, sockets
    mkdir -p "$1/$(dirname "$f")"
    ln "$f" "$1/$f" 2>/dev/null || cp -p "$f" "$1/$f"
    n_files=$((n_files + 1))
  done < <(git ls-files -z --cached --others --exclude-standard)
  n_bytes=$(du -sb "$1" | cut -f1)
}

run_scan() {
  cd "$(git rev-parse --show-toplevel)"
  local fail=0
  # Not `local`: the EXIT trap runs after this function has returned.
  stage=$(mktemp -d "$(git rev-parse --git-dir)/scan-stage.XXXXXX")
  trap 'rm -rf "$stage"' EXIT

  stage_publishable "$stage"
  echo "[scan] gitleaks: files git could publish ($n_files files, $n_bytes bytes; git-ignored paths not read)"
  (cd "$stage" && gitleaks dir . --no-banner --redact -v --exit-code 3) || fail=1
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    echo "[scan] gitleaks: git history"
    gitleaks git . --no-banner --redact -v --exit-code 3 || fail=1
  fi

  # The same files, for the generic patterns (ignores .venv, data caches, etc.).
  mapfile -d '' files < <(git ls-files -z --cached --others --exclude-standard)
  scan_regex () {  # $1 = label, $2 = extended regex (case-insensitive)
    local hits
    hits=$(printf '%s\0' "${files[@]}" | xargs -0 -r grep -nIiE -- "$2" 2>/dev/null || true)
    if [ -n "$hits" ]; then echo "[scan] FAIL $1:"; echo "$hits" | sed 's/^/    /'; fail=1; fi
  }
  # IPv4 (version strings like 1.2.3 have only three parts; a dotted quad is flagged).
  scan_regex "IPv4 address" '(^|[^0-9.])([0-9]{1,3}\.){3}[0-9]{1,3}([^0-9.]|$)'
  scan_regex "e-mail address" '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(com|net|org|io|co|uk|dev|ai)\b'
  scan_regex "private key" 'BEGIN [A-Z ]*PRIVATE KEY'
  scan_regex "broker key id" '\b(PK|AK)[A-Z0-9]{16,}\b'

  if [ -n "${SCAN_DENYLIST:-}" ] && [ -f "$SCAN_DENYLIST" ]; then
    while IFS= read -r pat; do
      [[ -z "$pat" || "$pat" == \#* ]] && continue
      scan_regex "private denylist term" "$pat"
    done < "$SCAN_DENYLIST"
  fi

  if [ "$fail" -ne 0 ]; then echo "[scan] BLOCKED: findings above"; exit 1; fi
  echo "[scan] clean"
}

# The self-test builds its secret at run time so that this file never holds one.
self_test() {
  if ! command -v gitleaks >/dev/null 2>&1; then
    echo "scan self-test: skipped (gitleaks not installed)"
    exit 0
  fi
  local fails=0 out rc secret
  tmp=$(mktemp -d)   # not `local`: the EXIT trap runs after this function has returned
  trap 'rm -rf "$tmp"' EXIT
  # gitleaks' private-key rule wants a body of at least 64 characters; built from
  # /dev/urandom so the body is never the same twice and never in this file.
  secret=$(printf -- '-----BEGIN %s PRIVATE KEY-----\n%s\n-----END %s PRIVATE KEY-----\n' RSA \
    "$(head -c 96 /dev/urandom | base64 | tr -d '\n' | head -c 96)" RSA)
  (
    cd "$tmp" && git init -q
    printf 'data/raw/\n' > .gitignore
    printf 'nothing here\n' > clean.md
    git add .gitignore clean.md
    git -c user.name=t -c user.email=t@example.invalid commit -q -m files
    mkdir -p data/raw
    { head -c 1048576 /dev/zero | tr '\0' 'x'; printf '\n%s\n' "$secret"; } > data/raw/big.jsonl
  )
  check() {  # $1 = label, $2 = 0 for pass; the scan's output is shown on a failure
    if [ "$2" -eq 0 ]; then echo "scan self-test: pass  $1"; else
      echo "scan self-test: FAIL  $1"; printf '%s\n' "$out" | sed 's/^/    | /'; fails=$((fails + 1))
    fi
  }

  # 1. Secret in a git-ignored file: not read, not reported, scan passes.
  out=$(cd "$tmp" && bash "$SELF" 2>&1) && rc=0 || rc=$?
  check "ignored secret does not block (rc $rc)" "$rc"
  check "ignored file not counted (2 files staged)" "$(printf '%s' "$out" | grep -q '(2 files, ' && echo 0 || echo 1)"
  check "ignored bytes not read (under 1 MB staged)" "$(printf '%s' "$out" | grep -qE '\(2 files, [0-9]{1,6} bytes' && echo 0 || echo 1)"
  check "no staging folder left behind" "$(ls -d "$tmp"/.git/scan-stage.* >/dev/null 2>&1 && echo 1 || echo 0)"

  # 2. The same secret in an untracked file git would publish: blocked by both passes.
  printf '%s\n' "$secret" > "$tmp/notes.txt"
  out=$(cd "$tmp" && bash "$SELF" 2>&1) && rc=0 || rc=$?
  check "publishable secret blocks (rc $rc)" "$([ "$rc" -ne 0 ] && echo 0 || echo 1)"
  check "pattern pass names the file" "$(printf '%s' "$out" | grep -q 'notes.txt' && echo 0 || echo 1)"
  check "gitleaks found it too" "$(printf '%s' "$out" | grep -qi 'leaks found: [1-9]' && echo 0 || echo 1)"
  rm -f "$tmp/notes.txt"

  # 3. Clean tree with the ignored secret still present: passes again.
  out=$(cd "$tmp" && bash "$SELF" 2>&1) && rc=0 || rc=$?
  check "clean tree passes (rc $rc)" "$rc"

  if [ "$fails" -ne 0 ]; then echo "scan self-test: $fails failure(s)"; exit 1; fi
  echo "scan self-test: pass"
}

case "${1:-}" in
  --self-test) self_test ;;
  "") run_scan ;;
  *) echo "usage: bash tools/scan.sh [--self-test]" >&2; exit 2 ;;
esac
