#!/usr/bin/env bash
# Study 004 reproduction script (PREREGISTRATION.md §13, §14; layout as Studies 001–003).
#
#   ./reproduce.sh --check      §5.3 data checks D0 then D1, one run -> results/checks/
#   ./reproduce.sh --insample   §8.1 in-sample run                   -> results/insample/   (not built yet)
#   ./reproduce.sh --oos        §8.2 out-of-sample, once             -> results/oos/        (not built yet)
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

usage() { echo "usage: $0 --check | --insample | --oos" >&2; exit 2; }
[ $# -eq 1 ] || usage
mode="$1"
case "$mode" in --check|--insample|--oos) ;; *) usage ;; esac

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
  --insample|--oos)
    echo "refused: $mode is not built yet (§14 step 2 remainder: the study's run.py)." >&2
    exit 1 ;;
esac
