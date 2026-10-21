#!/usr/bin/env bash
# Study 001 reproduction script (PREREGISTRATION.md §13, §14).
#
#   ./reproduce.sh --validate   §5.3 data check            -> results/validation/
#   ./reproduce.sh --insample   §8.1 in-sample run         -> results/insample/
#   ./reproduce.sh --oos        §8.2 out-of-sample, once   -> results/oos/
#
# Every mode refuses to run unless a file named APPROVED (containing the
# owner's approval date, §14 step 1) exists in this folder.  --oos refuses if
# results/oos/ already exists (§8.2: executed exactly once).
#
# Data are re-fetched into data/raw/ (git-ignored) on every run and recorded
# in results/data_manifest.json.  Alpaca credentials are read from the
# environment variables APCA_API_KEY_ID and APCA_API_SECRET_KEY only.
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
  echo "PREREGISTRATION.md §14 step 1: the owner's approval date must be recorded in a file named APPROVED" >&2
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
"$PYTHON" -m src.fred DGS10 DTB3 DGS7
if [ "$mode" != "--insample" ]; then
  echo "[1/2] data: Alpaca bars (adjustment=all)"
  "$PYTHON" -m src.alpaca_bars IEF BIL
fi

echo "[2/2] run $mode"
case "$mode" in
  --validate) "$PYTHON" -m src.validate ;;
  --insample) "$PYTHON" -m src.report --insample ;;
  --oos)      "$PYTHON" -m src.report --oos ;;
esac
