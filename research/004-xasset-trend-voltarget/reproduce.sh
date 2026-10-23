#!/usr/bin/env bash
# Study 004 reproduction script (PREREGISTRATION.md §13, §14; layout as Studies 001–003).
#
#   ./reproduce.sh --check      §5.3 data checks D0 then D1, one run -> results/checks/
#   ./reproduce.sh --insample   §8.1 in-sample run (ten assets and nine without IEF, k frozen) -> results/insample/
#   ./reproduce.sh --oos        §8.2 out-of-sample, once, k read from results/insample/        -> results/oos/
#   ./reproduce.sh --forward    §11 forward shadow record (added at §14 step 11, before the first
#                               forward month-end 2026-10-30; refuses until then); no paper order
#
# Every mode refuses to run unless a file named APPROVED exists in this folder
# (§14 step 3).  --oos refuses if results/oos/ already exists (§8.2: executed
# exactly once).
#
# Data go to data/raw/ (git-ignored) and are recorded in results/data_manifest.json.
# Vendor files: IEF reused from Study 002 and BIL from Study 003 after a SHA-256
# check; the other eleven fetched from Tiingo when TIINGO_API_KEY is set, else the
# files already in data/raw/ are used.  Broker bars for the overlap check: IEF and
# BIL reused from Study 001; the others fetched when APCA_API_KEY_ID and
# APCA_API_SECRET_KEY are set, else the check is skipped for that symbol (§5.3.2).
# DTB3 is re-fetched from FRED if reachable, else Study 003's file after a hash check.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
export PYTHONPATH="$(cd ../.. && pwd)${PYTHONPATH:+:$PYTHONPATH}"

if [ -z "${PYTHON:-}" ]; then
  if [ -x ../../.venv/bin/python ]; then PYTHON=../../.venv/bin/python; else PYTHON=python3; fi
fi

usage() { echo "usage: $0 --check | --insample | --oos | --forward <decide|shadow> --signal-date YYYY-MM-DD [--fetch] [--dry-run]" >&2; exit 2; }
[ $# -ge 1 ] || usage
mode="$1"
shift
case "$mode" in --check|--insample|--oos) [ $# -eq 0 ] || usage ;; --forward) ;; *) usage ;; esac

if [ ! -s APPROVED ]; then
  echo "refused: no APPROVED file in $(pwd | xargs basename)." >&2
  echo "PREREGISTRATION.md §14 step 3: the approval record must exist in a file named APPROVED" >&2
  echo "before any computation that touches returns." >&2
  exit 1
fi
echo "approval on record: $(head -n 1 APPROVED)"

if [ "$mode" = "--oos" ] && [ -e results/oos ]; then
  echo "refused: results/oos already exists. The out-of-sample run is executed exactly once (§8.2);" >&2
  echo "a re-run requires a dated amendment in §16 and must keep the existing output." >&2
  exit 1
fi

case "$mode" in
  --check)
    echo "[1/2] D0: vendor files (reuse by hash or fetch) and coverage"
    "$PYTHON" -m src.checks d0
    echo "[2/2] D1: per-symbol overlap against the broker's bars, then the §5.3.5 evaluation"
    "$PYTHON" -m src.checks d1 ;;
  --insample)
    echo "[1/1] in-sample run (§8.1, §9): T1-T4, B0-B4, base and stress costs, every §9.6 item"
    "$PYTHON" -m src.run --insample ;;
  --oos)
    echo "[1/1] out-of-sample run (§8.2), executed exactly once"
    "$PYTHON" -m src.run --oos ;;
  --forward)
    # §11, §14 step 11 (added 2026-10-23, before the first forward month-end 2026-10-30). No paper order.
    #   decide  --signal-date t [--fetch]   after 21:15 UTC on the last NYSE trading day of a month:
    #                                        paper-log/decisions/<t>.json (refuses before 2026-10-30, before
    #                                        the close, on a non-month-end date, without the cash ETF's bar)
    #   shadow  --signal-date t [--fetch]   after t's execution date's close: appends the period that ended
    #                                        there to paper-log/shadow.csv and writes paper-log/books/<end>.json
    # The study's data/raw/ and results/data_manifest.json are never touched: forward fetches go to
    # paper-log/raw/ (git-ignored) with their own paper-log/manifest.json.
    echo "[1/1] forward shadow record (§11): src.forward $*"
    "$PYTHON" -m src.forward "$@" ;;
esac
