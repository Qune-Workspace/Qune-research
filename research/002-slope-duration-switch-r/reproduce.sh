#!/usr/bin/env bash
# Study 002 reproduction script (PREREGISTRATION.md §13, §14; layout as Study 001).
#
#   ./reproduce.sh --validate   §5.3 data check, both windows -> results/validation/
#   ./reproduce.sh --insample   §8.1 in-sample run            -> results/insample/
#   ./reproduce.sh --oos        §8.2 out-of-sample, once      -> results/oos/
#
# Every mode refuses to run unless a file named APPROVED exists in this folder
# (§14 step 3; the approval chain is described in it).  --oos refuses if
# results/oos/ already exists (§8.2: executed exactly once).
#
# Data go to data/raw/ (git-ignored) and are recorded in
# results/data_manifest.json.  FRED is re-fetched on every run.  Alpaca bars
# are fetched when APCA_API_KEY_ID and APCA_API_SECRET_KEY are set; otherwise
# the bars already in data/raw/ are used, or Study 001's bars are copied after
# a SHA-256 check against its manifest.  The second-vendor IEF series for
# validation window 2 is fetched when TIINGO_API_KEY is set and the file is
# missing; otherwise the file fetched under §5.3.4 step 1 is used.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Interpreter: $PYTHON if set, else the repository's virtual environment, else python3.
if [ -z "${PYTHON:-}" ]; then
  if [ -x ../../.venv/bin/python ]; then PYTHON=../../.venv/bin/python; else PYTHON=python3; fi
fi

usage() { echo "usage: $0 --validate | --insample | --oos" >&2; exit 2; }
[ $# -eq 1 ] || usage
mode="$1"
case "$mode" in --validate|--insample|--oos) ;; *) usage ;; esac

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

echo "[1/2] data: FRED"
if ! "$PYTHON" -m src.fred DGS10 DTB3 DGS7; then
  # A failed fetch never overwrites data/raw/ (parsing precedes writing), so
  # files already there are reused, with their manifest entry as provenance.
  for s in DGS10 DTB3 DGS7; do
    [ -s "data/raw/fred_$s.csv" ] || { echo "refused: FRED fetch failed and no data/raw/fred_$s.csv" >&2; exit 1; }
  done
  echo "[1/2] data: FRED fetch failed; reusing data/raw/fred_*.csv (provenance in results/data_manifest.json)"
fi
if [ "$mode" != "--insample" ]; then
  if [ -n "${APCA_API_KEY_ID:-}" ] && [ -n "${APCA_API_SECRET_KEY:-}" ]; then
    echo "[1/2] data: Alpaca bars (adjustment=all)"
    "$PYTHON" -m src.alpaca_bars IEF BIL
  elif [ -s data/raw/alpaca_IEF_1Day_all.csv ] && [ -s data/raw/alpaca_BIL_1Day_all.csv ]; then
    echo "[1/2] data: Alpaca credentials not set; reusing bars in data/raw/ (see results/data_manifest.json)"
  elif "$PYTHON" -m src.reuse_bars IEF BIL; then
    echo "[1/2] data: Alpaca credentials not set; Study 001's bars copied after a SHA-256 check"
  else
    echo "refused: no Alpaca credentials, no bars in data/raw/, and Study 001's bars unavailable." >&2
    exit 1
  fi
fi
if [ "$mode" = "--validate" ]; then
  if [ -s data/raw/tiingo_IEF_daily.csv ]; then
    echo "[1/2] data: second-vendor IEF series present in data/raw/ (§5.3.4 step 1; see results/data_manifest.json)"
  elif [ -n "${TIINGO_API_KEY:-}" ]; then
    echo "[1/2] data: second-vendor IEF series"
    "$PYTHON" -m src.tiingo_bars IEF
  else
    echo "[1/2] data: no second-vendor IEF series and no TIINGO_API_KEY; window 2 cannot run" >&2
  fi
fi

echo "[2/2] run $mode"
case "$mode" in
  --validate) "$PYTHON" -m src.validate ;;
  --insample) "$PYTHON" -m src.report --insample ;;
  --oos)      "$PYTHON" -m src.report --oos ;;
esac
