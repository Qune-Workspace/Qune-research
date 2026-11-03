#!/usr/bin/env bash
# Study 013 reproduction script (PREREGISTRATION.md §13, §14).
#
#   ./reproduce.sh --test                  the synthetic-data tests of §6.6 (no network, no data)
#   ./reproduce.sh --fetch                 §14 step 4: the resolution fetch, on or after 2027-01-20 00:00Z (two files, bodies hashed, not kept)
#   ./reproduce.sh --data-step [--amendment "<dated §16 gap amendment>"]
#                                          §14 step 6: sample, exclusions, power; never opens outcome.jsonl;
#                                          the re-run of §14 step 8 names its amendment
#   ./reproduce.sh --count <registry.jsonl> §14 step 7: the programme-wide re-count -> results/programme_count.json
#   ./reproduce.sh --score                 §14 step 9, once: the scoring run -> results/score/
#   ./reproduce.sh --charts                §14 step 12: charts from results/score/ only
#
# --score refuses without a non-empty file named APPROVED in this folder (§14 step 5),
# when results/score/ already exists (it runs once), when results/programme_count.json
# is missing (§9.4, §14 step 7) and when trials.md has no scoring-run row. The checks
# are repeated in src/score.py, which also checks every input's SHA-256 against the
# record written when it was produced. Nothing here fetches a price: the snapshots are
# the daily job's (§5.1) and the resolution fetch runs once (§5.3).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -z "${PYTHON:-}" ]; then
  if [ -x ../../.venv/bin/python ]; then PYTHON=../../.venv/bin/python; else PYTHON=python3; fi
fi

usage() { echo "usage: $0 --test | --fetch | --data-step [--amendment <text>] | --count <desk-registry.jsonl> | --score | --charts" >&2; exit 2; }
[ $# -ge 1 ] || usage
case "$1" in
  --test)      exec "$PYTHON" -m pytest -q ;;
  --fetch)     exec "$PYTHON" -m src.resolution ;;
  --data-step) shift
               if [ $# -eq 0 ]; then exec "$PYTHON" -m src.data_step; fi
               { [ $# -eq 2 ] && [ "$1" = "--amendment" ]; } || usage
               exec "$PYTHON" -m src.data_step --amendment "$2" ;;
  --count)     [ $# -eq 2 ] || usage; exec "$PYTHON" programme_count.py --desk-registry "$2" ;;
  --charts)    exec "$PYTHON" charts/make_charts.py ;;
  --score)     [ $# -eq 1 ] || usage ;;
  *) usage ;;
esac

if [ ! -s APPROVED ]; then
  echo "refused: no APPROVED file in $(basename "$(pwd)")." >&2
  echo "PREREGISTRATION.md §14 step 5: the approval record must exist before the scoring run." >&2
  exit 1
fi
echo "approval on record: $(head -n 1 APPROVED)"
if [ -e results/score ]; then
  echo "refused: results/score already exists; the scoring run is executed once (§14 step 9)." >&2
  exit 1
fi
if [ ! -s results/programme_count.json ]; then
  echo "refused: results/programme_count.json missing; the programme-wide re-count comes first (§9.4, §14 step 7)." >&2
  exit 1
fi
if ! grep -q "^| Scoring run logged (§14 step 7)" trials.md; then
  echo "refused: trials.md has no scoring-run row; it is logged before the run (§14 step 7)." >&2
  exit 1
fi

echo "scoring run (§9, §14 step 9): the only step that opens outcome.jsonl"
exec "$PYTHON" -m src.score
