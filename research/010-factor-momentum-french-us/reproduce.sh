#!/usr/bin/env bash
# Study 010 reproduction script (PREREGISTRATION.md §13, §14).
#
#   ./reproduce.sh --history    §8 decision row H and its sub-windows, once -> results/history/
#   ./reproduce.sh --forward    §11 shadow forward record (not built yet; refused)
#
# --history refuses without a non-empty file named APPROVED in this folder
# (§14 step 4), when results/history/ already exists (it runs once), and when
# the programme-wide re-count (results/programme_count.json, §9.4, §14 step 5)
# has not been written. No data are fetched: the three zips of the data step
# must be in data/raw/ with the SHA-256 recorded in results/data_manifest.json
# (§5.2: one snapshot, no second download). The checks are repeated in
# src/history.py.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -z "${PYTHON:-}" ]; then
  if [ -x ../../.venv/bin/python ]; then PYTHON=../../.venv/bin/python; else PYTHON=python3; fi
fi

usage() { echo "usage: $0 --history | --forward" >&2; exit 2; }
[ $# -eq 1 ] || usage
case "$1" in
  --forward)
    echo "refused: the forward record code (forward010.py) is not built yet (§11, §14 step 10)." >&2
    exit 1 ;;
  --history) ;;
  *) usage ;;
esac

if [ ! -s APPROVED ]; then
  echo "refused: no APPROVED file in $(basename "$(pwd)")." >&2
  echo "PREREGISTRATION.md §14 step 4: the approval record must exist before the history run." >&2
  exit 1
fi
echo "approval on record: $(head -n 1 APPROVED)"
if [ -e results/history ]; then
  echo "refused: results/history already exists; the history run is executed once (§14 step 6)." >&2
  exit 1
fi
if [ ! -s results/programme_count.json ]; then
  echo "refused: results/programme_count.json missing; the programme-wide re-count comes first (§9.4, §14 step 5)." >&2
  exit 1
fi

echo "[1/2] data: snapshot present and matching the manifest (§5.2; no fetch)"
"$PYTHON" -I - <<'PY'
import hashlib, json, pathlib, sys
here = pathlib.Path.cwd()
m = json.loads((here / "results" / "data_manifest.json").read_text())["files"]
for name, e in m.items():
    p = here / "data" / "raw" / name
    if not p.is_file():
        sys.exit(f"refused: {p.relative_to(here)} missing; the snapshot cannot be downloaded again (§5.2)")
    if hashlib.sha256(p.read_bytes()).hexdigest() != e["sha256"]:
        sys.exit(f"refused: {name} does not match its recorded SHA-256")
    print(f"  {name}: ok")
PY

echo "[2/2] history run (§8, §9)"
exec "$PYTHON" -m src.history
