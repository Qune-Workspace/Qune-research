#!/usr/bin/env bash
# Study 014 reproduction script (PREREGISTRATION.md §13, §14).
#
#   ./reproduce.sh --test     the synthetic-row tests of §6.5 (no network, no data)
#   ./reproduce.sh --run      §14 step 6, once: the analysis run -> results/run/ (aggregates only)
#
# --run repeats the first two refusals of src/run.py's docstring (no non-empty APPROVED, §14
# step 4; results/run/ exists, the run executes once) and stops there; src/run.py holds the
# full order (Study 013's report and manifest, the stop flag, the trials.md analysis-run row,
# the sample file's SHA-256, every snapshot's logged hash before any row is read). Nothing
# here fetches anything.
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
  if [ -e results/run/started.txt ]; then echo "  $(cat results/run/started.txt)" >&2; fi
  exit 1
fi

echo "analysis run (§9, §14 step 6): Study 013's sample rows and snapshot-of-record quotes, eight fields, hash-checked"
exec "$PYTHON" -m src.run
