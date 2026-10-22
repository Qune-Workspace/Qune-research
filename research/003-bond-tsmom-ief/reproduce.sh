#!/usr/bin/env bash
# Study 003 reproduction script (PREREGISTRATION.md §13, §14; layout as Studies 001 and 002).
#
#   ./reproduce.sh --check      §5.3 data checks D0 and D2, one run -> results/checks/
#   ./reproduce.sh --insample   §8.1 in-sample run                  -> results/insample/
#   ./reproduce.sh --oos        §8.2 out-of-sample, once            -> results/oos/
#
# Every mode refuses to run unless a file named APPROVED exists in this folder
# (§14 step 3; the approval chain is described in it).  --oos refuses if
# results/oos/ already exists (§8.2: executed exactly once).
#
# Data go to data/raw/ (git-ignored) and are recorded in
# results/data_manifest.json.  DTB3 is re-fetched from FRED on every run
# (falling back to the file already present, then to Study 001's file after a
# SHA-256 check).  The vendor IEF series is the file fetched under Study 002,
# reused after a SHA-256 check against Study 002's manifest (§5.1); the vendor
# BIL series is the one fetched under §5.3.2 step 1.  Alpaca bars are fetched
# when APCA_API_KEY_ID and APCA_API_SECRET_KEY are set; otherwise the bars in
# data/raw/ are used, or Study 001's bars are copied after a SHA-256 check.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Interpreter: $PYTHON if set, else the repository's virtual environment, else python3.
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

echo "[1/2] data: FRED DTB3"
if ! "$PYTHON" -m src.fred DTB3; then
  if [ -s data/raw/fred_DTB3.csv ]; then
    echo "[1/2] data: FRED fetch failed; reusing data/raw/fred_DTB3.csv (provenance in results/data_manifest.json)"
  elif "$PYTHON" -m src.reuse_bars --fred DTB3; then
    echo "[1/2] data: FRED fetch failed; Study 001's DTB3 file copied after a SHA-256 check"
  else
    echo "refused: FRED fetch failed, no data/raw/fred_DTB3.csv, and Study 001's file unavailable." >&2
    exit 1
  fi
fi
if [ "$mode" != "--oos" ]; then
  echo "[1/2] data: vendor IEF series (Study 002 fetch, reused after a SHA-256 check)"
  "$PYTHON" -m src.reuse_bars --tiingo IEF
fi
if [ "$mode" = "--check" ]; then
  if [ -s data/raw/tiingo_BIL_daily.csv ]; then
    echo "[1/2] data: vendor BIL series present (§5.3.2 step 1; see results/data_manifest.json)"
  elif [ -n "${TIINGO_API_KEY:-}" ]; then
    echo "[1/2] data: vendor BIL series"
    "$PYTHON" -m src.tiingo_bars BIL
  else
    echo "refused: no vendor BIL series in data/raw/ and no TIINGO_API_KEY; §5.3.2 step 1 must run first." >&2
    exit 1
  fi
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

echo "[2/2] run $mode"
case "$mode" in
  --check)    "$PYTHON" -m src.checks ;;
  --insample) "$PYTHON" -m src.report --insample ;;
  --oos)      "$PYTHON" -m src.report --oos ;;
esac
