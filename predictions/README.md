# Predictions ledger

The desk's market calls, written down before the outcome and scored when due. The point is not the hit rate of five calls; it is that a reader can check that nothing was edited after the fact and that misses are recorded like hits.

Files:

- `ledger.csv`: one row per call, **append-only**. Columns: `id`, `made_on`, `series` (a FRED series id, or a derived id defined in `score.py`), `statement`, `test`, `threshold_low`, `threshold_high`, `due_on`, `confidence` (the desk's own probability), `basis` (why, and the downside case). A row's git history shows when it was added; a row is never changed. If a call turns out to be badly specified, a new row says so and the old one is scored as written.
- `score.py`: scores every due, unscored call against the public series, once, and appends to `outcomes.csv` with the observed value, the observation date and the hash of the data file it used. It never writes to the ledger and refuses to score an id twice. Test kinds are defined in its docstring.
- `outcomes.csv`: created by the first scoring run. A miss is written like a hit.
- `manifest.json`, `raw/`: provenance of each scoring fetch; `raw/` is not committed.

The desk's confidence figures are honest probabilities, not hedges: over many calls, those marked 0.65 should come true about two times in three. With five calls nothing can be said about calibration yet; the ledger is built to be judged once it is long enough.

The calls themselves, and the reading of the data behind them, are in [`../desk-view/DESK_VIEW.md`](../desk-view/DESK_VIEW.md). The view is updated weekly; each update appends new calls here and runs `score.py` for any that are due.

Nothing here is investment advice. The calls are written to be falsified, and some will be.
