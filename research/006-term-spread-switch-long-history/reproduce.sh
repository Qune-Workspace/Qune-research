#!/usr/bin/env bash
# Study 006 reproduction script (PREREGISTRATION.md §13, §14).
#
#   ./reproduce.sh --gate       §5.3 gate, once                    -> results/gate/
#   ./reproduce.sh --volcheck   §5.4 volatility check, once        -> results/volcheck/
#   ./reproduce.sh --history    §8.1 test window 1969-2018, once   -> results/history/
#   ./reproduce.sh --episode    §8.2 2019-2026 episode, once       -> results/episode/
#   ./reproduce.sh --forward decide|shadow|interim --signal-month YYYY-MM [--fetch] [--dry-run]
#                               §11 forward record, monthly        -> paper-log/ (no paper order)
#
# Every mode refuses without a file named APPROVED in this folder (§14 step 4)
# and refuses when its output folder already exists (each runs once).
# No data are fetched: the inputs are copied from the studies that fetched
# them, after a SHA-256 check against results/data_manifest.json (§5.1).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -z "${PYTHON:-}" ]; then
  if [ -x ../../.venv/bin/python ]; then PYTHON=../../.venv/bin/python; else PYTHON=python3; fi
fi

usage() { echo "usage: $0 --gate | --volcheck | --history | --episode | --forward <step> [args]" >&2; exit 2; }
[ $# -ge 1 ] || usage
mode="$1"
if [ "$mode" = "--forward" ]; then
  shift
  # §11: monthly and append-only; the module refuses every run its gates do not allow.
  exec "$PYTHON" -m src.forward "$@"
fi
[ $# -eq 1 ] || usage
case "$mode" in --gate|--volcheck|--history|--episode) ;; *) usage ;; esac

if [ ! -s APPROVED ]; then
  echo "refused: no APPROVED file in $(pwd | xargs basename)." >&2
  echo "PREREGISTRATION.md §14 step 4: the approval record must exist in a file named APPROVED before any run." >&2
  exit 1
fi
echo "approval on record: $(head -n 1 APPROVED)"

out="results/${mode#--}"
if [ -e "$out" ]; then
  echo "refused: $out already exists. Each step runs once (§5.3.6, §5.4, §8);" >&2
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
  --gate)     "$PYTHON" -m src.gate ;;
  --volcheck) "$PYTHON" -m src.volcheck ;;
  --history)  "$PYTHON" -m src.history ;;
  --episode)  "$PYTHON" -m src.episode ;;
esac
