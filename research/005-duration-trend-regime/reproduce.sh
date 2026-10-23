#!/usr/bin/env bash
# Study 005 reproduction script (PREREGISTRATION.md §13, §14; layout as Studies 003 and 004).
#
#   ./reproduce.sh --check      §5.3 data checks D0, D1, D3, one run              -> results/checks/
#   ./reproduce.sh --insample   §8.1 in-sample run, once (refuses if the folder exists)  -> results/insample/
#   ./reproduce.sh --episode    §8.2 the 2019–2026 hypothesis-generating episode, once,
#                               no decision weight, B3 weight read from results/insample/ -> results/episode/
#   ./reproduce.sh --forward    §11 forward decision record (added at §14 step 11, before the
#                               first forward month-end; refuses until then)
#
# Every mode refuses to run unless a file named APPROVED exists in this folder
# (§14 step 2).  --insample and --episode refuse if their results folder
# exists.  No mode fetches: the two fetches of §5.3.3 run through
# `python -m src.data fetch-alpaca-spy` and `python -m src.data fetch-cpi`,
# each logged in trials.md before it runs (§14 step 3).
#
# Data go to data/raw/ (git-ignored) and are recorded in results/data_manifest.json.
# Tiingo IEF and SPY are reused from Study 004 after a SHA-256 check against its
# manifest; DTB3 and the Alpaca IEF and BIL bars from Study 003 the same way;
# Study 004's 2016–2018 broker SPY file is reused into data/raw/overlap/ for D1.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
export PYTHONPATH="$(cd ../.. && pwd)${PYTHONPATH:+:$PYTHONPATH}"

if [ -z "${PYTHON:-}" ]; then
  if [ -x ../../.venv/bin/python ]; then PYTHON=../../.venv/bin/python; else PYTHON=python3; fi
fi

usage() { echo "usage: $0 --check | --insample | --episode | --forward <decide|shadow|interim> [--signal-date YYYY-MM-DD] [--fetch] [--dry-run]" >&2; exit 2; }
[ $# -ge 1 ] || usage
mode="$1"
shift
case "$mode" in --check|--insample|--episode) [ $# -eq 0 ] || usage ;; --forward) ;; *) usage ;; esac

if [ ! -s APPROVED ]; then
  echo "refused: no APPROVED file in $(pwd | xargs basename)." >&2
  echo "PREREGISTRATION.md §14 step 2: the approval record must exist in a file named APPROVED" >&2
  echo "before any computation that touches returns." >&2
  exit 1
fi
echo "approval on record: $(head -n 1 APPROVED)"

if [ "$mode" = "--insample" ] && [ -e results/insample ]; then
  echo "refused: results/insample already exists. The in-sample run is executed once (§14 step 6);" >&2
  echo "a re-run requires a dated amendment in §16 and must keep the existing output." >&2
  exit 1
fi
if [ "$mode" = "--episode" ] && [ -e results/episode ]; then
  echo "refused: results/episode already exists. The episode is run exactly once (§8.2, §14 step 8)." >&2
  exit 1
fi
if [ "$mode" = "--episode" ] && [ ! -s results/insample/summary.json ]; then
  echo "refused: results/insample/summary.json missing. The episode runs after the in-sample results" >&2
  echo "are committed (§8.2, §14 step 8)." >&2
  exit 1
fi

case "$mode" in
  --check)
    echo "[1/3] D0: coverage of the reused and fetched files (dates only)"
    "$PYTHON" -m src.checks d0
    echo "[2/3] D1: regime sign agreement across vendors, 2016–2018 (descriptive, no gate)"
    "$PYTHON" -m src.checks d1
    echo "[3/3] D3: regime shares, σ_d from Study 003's committed file, the MDE at the actual counts"
    "$PYTHON" -m src.checks d3 ;;
  --insample)
    echo "[1/1] in-sample run (§8.1, §9): T1–T3 on their regimes, B0–B3, base and stress costs"
    "$PYTHON" -m src.report --insample ;;
  --episode)
    echo "[1/1] the 2019–2026 episode (§8.2), executed exactly once, no decision weight"
    "$PYTHON" -m src.report --episode ;;
  --forward)
    # §11, §14 step 11 (added 2026-10-23, before the first forward month-end 2026-10-30). No paper order.
    #   decide  --signal-date t [--fetch]   after 21:15 UTC on the last NYSE trading day of a month:
    #                                        paper-log/decisions/<t>.json (refuses before 2026-10-30,
    #                                        before the close, on a non-month-end date, without the bars)
    #   shadow  --signal-date t [--fetch]   after t's execution date's close: appends the period that
    #                                        ended there to paper-log/shadow.csv; interim.json
    #   interim                              rewrites paper-log/interim.json ("Not yet scored") only
    # The study's data/raw/ and results/data_manifest.json are never touched: forward fetches go to
    # paper-log/raw/ (git-ignored) with their own paper-log/manifest.json.
    echo "[1/1] forward record (§11): src.forward $*"
    "$PYTHON" -m src.forward "$@" ;;
esac
