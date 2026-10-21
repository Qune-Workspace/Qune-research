#!/usr/bin/env bash
# Pre-commit / pre-push leak scan for this repository.
#  1. gitleaks over the working tree and the full git history (secrets, keys, tokens).
#  2. Generic patterns that should never appear in a public research repo:
#     IPv4 addresses, e-mail addresses, private-key headers, broker key prefixes.
#  3. An optional private denylist (one regex per line) passed via SCAN_DENYLIST.
#     It lives outside the repo so the sensitive terms themselves are never published.
# Exit code 0 = clean; anything else = stop and investigate before pushing.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
fail=0

echo "[scan] gitleaks: working tree"
gitleaks dir . --no-banner --redact -v --exit-code 3 || fail=1
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "[scan] gitleaks: git history"
  gitleaks git . --no-banner --redact -v --exit-code 3 || fail=1
fi

# Files that are tracked or about to be committed (ignores .venv, data caches, etc.).
mapfile -t files < <(git ls-files --cached --others --exclude-standard)
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
