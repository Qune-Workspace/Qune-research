#!/usr/bin/env bash
# Study 014 reproduction script (PREREGISTRATION.md §13, §14).
#
#   ./reproduce.sh --test     the synthetic-row tests of §6.5 (no network, no data)
#   ./reproduce.sh --run      §14 step 6, once: the analysis run -> results/run/ (aggregates only)
#
# --run refuses without a non-empty file named APPROVED in this folder (§14 step 4), when
# results/run/ already exists (it runs once) and when trials.md has no analysis-run row
# (§14 step 5). The checks are repeated in src/run.py, which also refuses when Study 013's
# data step has not written its manifest, when its sample file is off its recorded SHA-256,
# and when a snapshot is off the hash logged on its day. Nothing here fetches anything.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -z "${PYTHON:-}" ]; then
  if [ -x ../../.venv/bin/python ]; then PYTHON=../../.venv/bin/python; else PYTHON=python3; fi
fi

usage() { echo "usage: $0 --test | --run" >&2; exit 2; }
[ $# -eq 1 ] || usage
case "$1" in
  --test) exec "$PYTHON" -m pytest -q ;;
  --run) ;;
  *) usage ;;
esac

if [ ! -s APPROVED ]; then
  echo "refused: no APPROVED file in $(basename "$(pwd)")." >&2
  echo "PREREGISTRATION.md §14 step 4: the approval record must exist before the analysis run." >&2
  exit 1
fi
echo "approval on record: $(head -n 1 APPROVED)"
if [ -e results/run ]; then
  echo "refused: results/run already exists; the analysis run is executed once (§14 step 6)." >&2
  exit 1
fi
if ! grep -q "^| Analysis run logged (§14 step 5)" trials.md; then
  echo "refused: trials.md has no analysis-run row; it is logged before the run (§14 step 5)." >&2
  exit 1
fi

echo "analysis run (§9, §14 step 6): Study 013's sample rows and snapshot-of-record quotes, eight fields, hash-checked"
exec "$PYTHON" -m src.run
