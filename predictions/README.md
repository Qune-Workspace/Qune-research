# Predictions ledger

The desk's market calls, written down before the outcome and scored when due. The point is not the hit rate of five calls; it is that a reader can check that nothing was edited after the fact and that misses are recorded like hits.

Files:

- `ledger.csv`: one row per call, **append-only**. Columns: `id`, `made_on`, `series` (a FRED series id, or a derived id defined in `score.py`), `statement`, `test`, `threshold_low`, `threshold_high`, `due_on`, `confidence` (the desk's own probability), `basis` (why, and the downside case). A row's git history shows when it was added; a row is never changed. If a call turns out to be badly specified, a new row says so and the old one is scored as written.
- `score.py`: scores every due, unscored call against the public series, once, and appends to `outcomes.csv` with the observed value, the observation date and the hash of the data file it used. It never writes to the ledger and refuses to score an id twice. Test kinds are defined in its docstring.
- `outcomes.csv`: created by the first scoring run. A miss is written like a hit.
- `manifest.json`, `raw/`: provenance of each scoring fetch; `raw/` is not committed.
- `baseline.py`, `baselines.csv` (added 2026-10-25): a second, market-anchored probability for every call, computed by the frozen method in `baseline.py` from public data as of the last observation the view used, written before the outcome; **append-only**, one row per id, a second attempt is refused. `baseline.py --summary` writes `SKILL.md`: the desk's Brier score beside the baseline's, so the ledger is judged on skill over the market, not on a bare hit rate.

The desk's confidence figures are honest probabilities, not hedges: over many calls, those marked 0.65 should come true about two times in three. With five calls nothing can be said about calibration yet; the ledger is built to be judged once it is long enough.

The calls themselves, and the reading of the data behind them, are in [`../desk-view/DESK_VIEW.md`](../desk-view/DESK_VIEW.md). The view is updated weekly; each update appends new calls here, writes their baseline rows with `baseline.py --asof <view's market-data date> --ids <new ids>` in the same commit, and runs `score.py` for any that are due, then `baseline.py --summary`.

Nothing here is investment advice. The calls are written to be falsified, and some will be.

## Market-anchored baseline (dated addition, 2026-10-25)

The [cold read](../COLD_READ.md) (point 3) said a hit rate on range calls means little when the market already prices them. Agreed. From 2026-10-25 every call carries a second probability in `baselines.csv`, computed by `baseline.py` by a method fixed in that file before any later call was written:

- policy-rate calls: the 4-week bill minus the effective funds rate, scaled to the meeting day and divided by the hike step (FRED has no futures; the bill-funds basis is ignored, which is the method's main weakness);
- yield and slope levels on a date: a normal distribution centred on the forward level read off the par curve, with the trailing-year realised daily volatility as the scale (realised, not option-implied: FRED carries no implied-volatility series, so the width is a proxy);
- "stays inside a band every day": seeded random-walk paths with the same scale;
- the stock-bond correlation proxy, which has no market price: the historical persistence of its sign, labelled a base rate.

Every input, the observation dates and the hash of each file used are in the row. `SKILL.md` lists desk and baseline probabilities side by side and, once calls are scored, both Brier scores and their difference; with fewer than about thirty scored calls the difference is descriptive.

**Disclosure.** The method was designed on 2026-10-25, two days after the first five calls were logged, so their baselines are retrospective: computed from observations to 2026-10-21 only (the view's market-data date), but by a method chosen after the calls existed. A reader may discount them for that. For calls from the 2026-10-30 view onward the baseline row is written in the same commit as the call. What the retrospective rows say: the 4-week bill on 2026-10-21 (3.92% against funds at 3.88%) priced about a one-in-five chance of the 28 October hike the desk put at 0.70, so V1 is a call against the market, scored on 2026-10-29; the forward curve put V2 and V3 close to the desk's figures (0.66 and 0.59 against 0.65 and 0.60); the breakeven band of V4 is wide against realised volatility (baseline 0.95 against the desk's 0.75, so a hit there earns little); the correlation call V5 has a base rate of 0.70 against the desk's 0.65.

## Scoring waits for the due date's print (dated addition, 2026-10-28)

Found before any call was scored: `score.py` treated a call as due on its due date and, when the fetched series had no value for that date, used the last earlier observation. Run on 2026-10-29 before FRED posts that day's row, it would have scored V1 on the 2026-10-28 value (upper limit 4.00%, the day of the decision) and written a permanent miss, since a call is scored once. A dry run on a throwaway copy with the live FRED file at about 17:25Z on 2026-10-28 (`--today 2026-10-29`, series ending 2026-10-28) did exactly that. The scorer now requires the series to hold a row dated on or after the due date (FRED writes an empty row on holidays; the derived correlation series drops empty days, so a later row counts); until then it prints `NOT SCORED ... retry on a later day` and writes nothing. The same dry run with the fix refused V1. When the due date's own value is empty, the last valid value before it is still used and named. No ledger row, threshold or due date changed; `outcomes.csv` does not exist yet.
