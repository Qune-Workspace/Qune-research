# Desk view

A dated rates-and-macro view from public data, updated weekly, ending in falsifiable calls that are logged in [`../predictions/`](../predictions/) before the outcome and scored there when due.

- [`DESK_VIEW.md`](DESK_VIEW.md): the current view. Earlier views are kept under `archive/` once superseded, unchanged.
- `build_view.py`: fetches the FRED series, writes `data/snapshot_<date>.csv` and `data/numbers_<date>.json` (every number the note quotes) and the four charts in `charts/`. `view_lib.py` holds the definitions (curve snapshot, 10-year decomposition, stock-bond correlation proxy, market-implied path) as pure functions, and the wording rules that choose each chart's title from the numbers; `tests/` checks them and the prediction scorer on constructed series.
- `charts/`: the four charts to the house chart standard (`qune_research/style.py`), SVG and 2x PNG, with `charts/manifest.json` recording the hash of every raw file read and every number that appears in a title. The title of each chart is chosen by a pure function from the numbers, never typed.
- `data/manifest.json`: provenance of every fetch (url, time, rows, hash); `data/raw/` is not committed.

Run from this folder with the repository's virtualenv: `python build_view.py --asof YYYY-MM-DD` (or `--offline` to reuse the raw files), `python -m pytest -q`. To redraw a published view's charts without touching its numbers: `--charts-only`, which hash-checks the raw files against the manifest, recomputes the numbers and refuses to draw if any differs from the committed json.
