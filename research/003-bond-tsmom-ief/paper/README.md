# Paper-trading path for Study 003 (PREREGISTRATION.md §11, §12)

This is the forward record of a rule whose verdict was **not supported** (README.md). It is run anyway because §11 was pre-registered before any result and the forward record is the only test nobody has seen. Every line of it is labelled as the paper record of a not-supported rule. Paper only; there is no real money anywhere in this organisation's trading.

First signal date: **2026-10-30** (last NYSE trading day of October). First execution date: **2026-11-02**. Starting position: BIL. Nothing can be placed before `RISK_CLEARANCE.md` records Independent Risk's clearance and every condition in it is met.

## Pieces and their status

| Piece | What it does | Status (2026-10-22) |
|---|---|---|
| `paper/decide.py` | After the close on the signal date: computes `mom_t` and the target from Alpaca `adjustment='all'` daily bars with the study's own `src.signal.excess_momentum` (the function the backtest called); writes one JSON record per signal date to `paper-log/decisions/`; refuses a date that is not the last NYSE trading day of its month, a missing month-end bar, or a lookback the bars do not cover (`status: signal unavailable`); never overwrites a record | **built, tested** (8 tests on synthetic bars in `tests/test_paper_decide.py`; in CI). Not yet run on real bars: the first signal date is 2026-10-30 |
| Bar fetch | `src.alpaca_bars.fetch_bars` into `paper-log/raw/` (git-ignored) with its own `paper-log/manifest.json` (row counts and SHA-256 only). The study's `data/raw/` and `results/data_manifest.json` are never touched, so the published hashes stay frozen | **built** (parameters of the existing fetcher), not yet run |
| Order leg | On the execution date, 15:45–15:55 ET: reads the decision record, writes the desk journal entry first, then sells the holding, waits for the fill, buys the target with the proceeds in whole shares; appends the fills, the official close and the slippage in basis points to the record. Orders go only through the desk's paper broker client and its risk engine (private workspace, `ops/trading/lib/alpaca.mjs` and `risk.mjs`), which refuse any host but the paper endpoints, any order without a stop, and any breach of the desk limits | **designed**, not built |
| Schedule | Two unattended jobs: the decision after 17:00 ET on the last NYSE trading day of each month; the orders on the next NYSE trading day. A missing bar re-checks each NYSE day at 15:30 ET for up to three days, then holds and alerts the owner (§11.2) | **designed**, not built |
| Monthly summary | `paper-log/summary.csv` (equity, holding, return, cumulative slippage) and the same-dated B0/B1/B3 benchmarks from the same bars (§11.5) | **designed**, not built |
| Clearance | `RISK_CLEARANCE.md`: Independent Risk's decision and its conditions | see that file |

## Rules that do not bend

- **Never backdated.** Every record carries `run_at_utc` and is committed on the day it is written; the commit timestamp is the second clock. A record for a signal date is written after that date's close, never before.
- **Never rewritten.** `write_record` refuses to overwrite. A correction is a new file with a note pointing at the old one.
- **Same code as the backtest.** The decision uses `src/signal.py`, `src/calendar.py` and `src/alpaca_bars.py` unchanged. A change to `src/` after publication is a dated amendment (§11.4) and the record before and after it is kept apart.
- **Desk limits win where tighter.** The sleeve's §12 limits sit under the desk's `RISK_FRAMEWORK.md`; where the two differ, the tighter one applies and the clearance note says which.
- **The engine stop is an overlay.** If the desk's required stop is triggered, the trigger is logged and the no-stop rule's record is computed alongside (§11.4).

## Running the decision (from the study folder)

```
python -m paper.decide --signal-date 2026-10-30 --holding BIL --fetch
```

Credentials come only from the environment variables `src/alpaca_bars.py` reads; nothing is read from a file in this repository. `--dry-run` prints the record without writing it.
