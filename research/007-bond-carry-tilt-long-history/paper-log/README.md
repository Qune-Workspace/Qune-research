# Forward record of Study 007 (PREREGISTRATION.md §11; no paper order)

**Label: forward record; the history verdict is inconclusive (fragile)** (README.md). **No paper order is placed under this study** (§11, §12): the programme's paper sleeve belongs to Study 003's rule. This folder is the only clean test of T1: the rule was fixed before these data existed. It is scored **once, after 60 holding periods** (§11.3–11.4); until then every figure here is under **"Not yet scored"**. Power, stated before any forward data (§11.4): over 60 periods the detectable edge is about 4.8% a year at the design dispersion and 2.8% a year at the uniform-rank dispersion, so the forward record is weak.

First signal month: **2026-10** (signal date 2026-10-30 if FRED holds all three yields that day; the note was committed on 2026-10-25, before 21:15 UTC on 2026-10-30, §11.1). First execution date: the first NYSE trading day after it, normally **2026-11-02**. Starting weights in the duration leg (the 2026-09-30 signal, from `results/episode/summary.json`): **T1, T1a, T1b 0.4111; T2 0.2055; T3 0** (carry rank 41st percentile of 687 month-ends; 12-month trend not positive). The period from 2026-10-01 to the first execution date is counted nowhere.

## What is written, by whom, when

| Piece | Command (from the study folder) | When | Status (2026-10-25) |
|---|---|---|---|
| Decision record `decisions/<signal_date>.json` (§11.2): DGS10, DGS7, DTB3, c_t, n_t, w_t for T1, T1a, T1b, h_t, T2's weight, input hashes, UTC time | `./reproduce.sh --forward decide --signal-month YYYY-MM --fetch` | after 21:15 UTC on the month's last weekday, before the close of the execution date | **built, tested** (17 tests in `tests/test_forward007.py`; separate code review 2026-10-25, one must-fix found and fixed, `CODE_REVIEW.md`); refused on the real clock on 2026-10-25 for 2026-10 (too early) and 2026-09 (before the first month) (observed); not yet run on a forward month |
| Wait log `waits.csv` | written by `decide` when FRED or the ETF bars do not yet make t final | each re-check | **built, tested** |
| Shadow line in `shadow.csv` (§11.3): IEF and BIL period returns, T1, T1a, T1b, T2, T3, B1, B2, each trial's B3, d = T1 − B3^T1, weights held and traded fractions | `./reproduce.sh --forward shadow --signal-month YYYY-MM --fetch` | after the close of that month's execution date; the first line (the period from the 2026-10 record's execution date) follows the 2026-11 record | **built, tested** against `tilt.run_tilt` and `backtest.benchmarks`; not yet run |
| Interim figures `interim.json` | `./reproduce.sh --forward interim` (also rewritten by `shadow`) | every month | **built, tested**; heading "Not yet scored", no statistic |
| Scoring (§11.4) | `forward007.score` | once per 60-period block; the scoring date is in the record that ends the block | **built, tested** on constructed data; refuses until then |
| Inputs | `--fetch`: FRED DGS10, DTB3, DGS7 and Alpaca `adjustment='all'` daily bars of IEF and BIL from 2025-01-02 into `raw/` (git-ignored), hashes in `manifest.json` | with each step | **built** (the study's own fetchers with other paths); not yet run |

## Rules the code enforces (each has a test)

- No record for a month before 2026-10; none before 21:15 UTC on the month's last weekday. A refused run writes nothing and exits 1.
- t (Study 001 §6.3) is final only when DGS10, DTB3 and DGS7 each have a row on t and on every later weekday of the month that is an NYSE day, and both ETFs have a bar on or after t; until then a wait line, no record.
- Only observations dated on or before t enter a record (tested: identical with later FRED rows and later bars added).
- The rank history is the frozen one to 2026-09 (687 carries, the episode's; tested on the study's files) plus one carry per forward month; a later fetch that disagrees before 2026-10 changes nothing (tested).
- The trend reads the ETF closes at the last bar on or before each of the thirteen signal dates t−12 … t.
- A trial whose weight is undefined on t holds its position: no trade, its weight drifts. A forward month without a carry is left out of the rank history and does not hold later months.
- The execution date is the first NYSE day after t whose close follows the record; at most the third. Past that, a `signal unavailable` record: weights held, the period runs on, never filled later.
- A record is never rewritten; a shadow line is appended once per period and only for the period that follows the last one.

By construction, not by a test: the module writes only under `paper-log/`; the study's `data/raw/` and `results/` are read, never written.

The code decisions behind these rules are in PREREGISTRATION.md §16 (two entries of 2026-10-25, before any forward input was fetched; the second follows the code review).

## Record

| Signal month | Signal date | Execution date | Record | Shadow line |
|---|---|---|---|---|
| 2026-10 | 2026-10-30 (expected) | 2026-11-02 (expected) | not yet: wait line 2026-10-31 06:18Z in `waits.csv` (FRED's DGS10 had no row for 2026-10-30; the first check came about nine hours after the gate, see [`../../../MONTH_END.md`](../../../MONTH_END.md)); re-checked each run, deadline 2026-11-04 21:00Z | n/a (first period starts here) |

Not yet scored: no holding period has ended.
