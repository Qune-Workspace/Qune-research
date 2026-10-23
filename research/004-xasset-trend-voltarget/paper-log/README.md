# Forward shadow record of Study 004 (PREREGISTRATION.md §11; no paper order)

**Label: not supported.** This folder is the forward shadow record of a rule whose pre-registered verdict is "not supported" (README.md: C1 and C2 failed in-sample; the out-of-sample sign conditions held). It is kept because §11 was pre-registered before any result and a forward record is the only test still to come. **No paper order is placed under this study** (§11, §12): the universe is beyond the symbols approved for paper trading, and a not-supported rule earns no approval request. Promotion would need everything in §11.3; none of it is asked for.

First signal date: **2026-10-30** (the last NYSE trading day of the first month after the note's publication on 2026-10-22; *corrected 2026-10-24: this file had written 2026-10-23, but the note was published at 23:26 London on 2026-10-22, commit `4bd9187`, as the note's own first line says; the first signal date does not change*). First execution date: **2026-11-02**. The three books (T1, B3, B4; 10,000 USD each, notional) start all cash at that close, the initial purchase charged like any trade. The held-back window's terminal position (the 2026-09-30 signal: IWM, EFA, EEM and GLD on, gross exposure 76.6%, from `results/oos/signal_s12_10assets.csv` and `signal_vol_10assets.csv`) is reported in the first record as `holding_before` for information; the holding period 2026-10-01 to 2026-11-02 is counted nowhere (§16, step 11 entry).

## What is written, by whom, when

| Piece | Command (from the study folder) | When | Status (2026-10-23) |
|---|---|---|---|
| Decision record `decisions/<signal_date>.json` (§11.1): the ten instruments' 12-month excess momentum, signal, 63-day volatility, T1/B3/B4 weights, gross exposure, cash weight, turnover against the previous targets, input hashes, UTC time | `./reproduce.sh --forward decide --signal-date t --fetch` | after 21:15 UTC on the last NYSE trading day of each month | **built, tested** (11 tests in `tests/test_forward.py`; in CI). Check run once against the committed files: the 2026-08-31 and 2026-09-30 records from the frozen vendor files reproduce the committed signal, volatility and T1 weight files to 1e-16 (nothing written). Not yet run on a forward month |
| Shadow line in `shadow.csv` (§11.2): net return, cost, turnover and gross exposure of T1, B3 and B4 for the period, the three book values, the period returns of SPY, IEF and the cash ETF | `./reproduce.sh --forward shadow --signal-date t --fetch` | after the close of `t`'s execution date; the first line (period 2026-11-02 to 2026-12-01) follows the 2026-11-30 record | **built, tested** against the frozen engine (`period_step` against `qune_research.engine.run`, eight consecutive periods, 1e-14), not yet run |
| Books `books/<period_end>.json`: each book's value, target and drifted weights after the period | written by `shadow` | with each line | **built, tested**; the next line charges its trade from these drifted weights |
| Bar fetch | `--fetch`: Alpaca `adjustment='all'` daily bars of the ten instruments, BIL and SPY from 2025-06-02 into `raw/` (git-ignored), hashes in `manifest.json` | with each record | **built** (the library's fetcher with other paths), not yet run |

## Rules the code enforces (each has a test)

- No record before 2026-10-30; none before 21:15 UTC on the signal date (after the 16:00 New York close under EDT or EST: a daily bar fetched during the session would be the partial day); none on a date that is not the last NYSE trading day of its month; none without the cash ETF's bar for the signal date. A refused run writes nothing and exits 1.
- Only observations on or before the signal date enter a record (tested: the record is identical with and without later bars).
- An instrument without a bar at the signal date is logged "signal unavailable" and its previous weight is carried (§11.1); the record's status names it.
- A record is never overwritten; a correction is a later record with a note. A shadow line is appended once per period and only for the period that follows the last recorded one; the books of a period are written once; a missed month is logged here as missed, never filled.
- The engine conventions are the study's own (§6.3–6.4): a period runs between the first bars on or after the two execution dates that every instrument and the cash ETF have (slippage recorded); the trade from the drifted weights to the targets costs Σ|Δw|·c at base costs (2.0–3.5 bp per side by instrument); the remainder of each book earns the cash ETF's return.
- The study's `data/raw/` and `results/data_manifest.json` are never touched by the forward record.

## Record

| Signal date | Execution date | Record | Shadow line | Note |
|---|---|---|---|---|
| 2026-10-30 | 2026-11-02 | not yet (written after 21:15 UTC on 2026-10-30) | n/a (first period starts here) | |
