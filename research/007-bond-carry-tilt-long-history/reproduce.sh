#!/usr/bin/env bash
# Study 007 reproduction script (PREREGISTRATION.md §13, §14).
#
#   ./reproduce.sh --gate       §5.3 gate per weight path, once      -> results/gate/
#   ./reproduce.sh --volcheck   §5.4 volatility check, once          -> results/volcheck/
#   ./reproduce.sh --history    §8.1 test window 1974-2018, once     -> results/history/
#   ./reproduce.sh --episode    §8.2 2019-2026 episode, once         -> results/episode/
#
# Every mode refuses without a file named APPROVED in this folder (§14 step 4)
# and refuses when its output folder already exists (each runs once).
# No data are fetched: the inputs are Study 006's files, copied after a
# SHA-256 check against results/data_manifest.json (§5.1).
#
# State of the build (§14 step 3): --gate and --volcheck are built (src/gate007.py,
# src/volcheck007.py); --history and --episode stop after the two gates with
# "not built yet". Nothing has run on data.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -z "${PYTHON:-}" ]; then
  if [ -x ../../.venv/bin/python ]; then PYTHON=../../.venv/bin/python; else PYTHON=python3; fi
fi

usage() { echo "usage: $0 --gate | --volcheck | --history | --episode" >&2; exit 2; }
[ $# -eq 1 ] || usage
mode="$1"
case "$mode" in --gate|--volcheck|--history|--episode) ;; *) usage ;; esac

if [ ! -s APPROVED ]; then
  echo "refused: no APPROVED file in $(pwd | xargs basename)." >&2
  echo "PREREGISTRATION.md §14 step 4: the approval record must exist in a file named APPROVED before any run." >&2
  exit 1
fi
echo "approval on record: $(head -n 1 APPROVED)"

out="results/${mode#--}"
if [ -e "$out" ]; then
  echo "refused: $out already exists. Each step runs once (§5.3.3, §5.4, §8);" >&2
  echo "a re-run requires a dated amendment in §16 and must keep the existing output." >&2
  exit 1
fi

echo "[1/2] data: inputs present and matching the manifest (§5.1; no fetch)"
"$PYTHON" -I - <<'PY'
import hashlib, json, pathlib, shutil, sys
here = pathlib.Path.cwd()
manifest = json.loads((here / "results" / "data_manifest.json").read_text())
for name, entry in manifest.items():
    dst = here / "data" / "raw" / name
    if not dst.exists():
        study = entry["reused_from"].split()[1]
        src = next(here.parent.glob(f"{study}-*")) / "data" / "raw" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    if hashlib.sha256(dst.read_bytes()).hexdigest() != entry["sha256"]:
        sys.exit(f"refused: data/raw/{name} does not match its SHA-256 in results/data_manifest.json")
print(f"  {len(manifest)} files verified")
PY

echo "[2/2] run $mode"
case "$mode" in
  --gate)     exec "$PYTHON" -m src.gate007 ;;
  --volcheck) exec "$PYTHON" -m src.volcheck007 ;;
  *)
    echo "refused: $mode is not built yet (PREREGISTRATION.md §14 step 3 in progress); nothing was run." >&2
    exit 1 ;;
esac
