# Forward record of Study 006 (PREREGISTRATION.md §11; no paper order)

**Label: forward record; the history verdict is inconclusive (fragile)** (README.md). **No paper order is placed under this study** (§11): the programme's paper sleeve belongs to Study 003's rule. This folder is the only clean test of T1: the rule was fixed before these data existed. It is scored **once, after 60 holding periods** (§11.3–11.4), when it can see an edge of about 3% a year; until then every figure here is under **"Not yet scored"**.

First signal month: **2026-10** (signal date 2026-10-30 if FRED holds both yields that day). First execution date: the first NYSE trading day after it, normally **2026-11-02**. Starting holdings (the 2026-09-30 signal from the study's frozen FRED files): **T1 IEF, T2 IEF, T3 IEF**. The holding period from 2026-10-01 to the first execution date is counted nowhere.

## What is written, by whom, when

| Piece | Command (from the study folder) | When | Status (2026-10-25) |
|---|---|---|---|
| Decision record `decisions/<signal_date>.json` (§11.2) | `./reproduce.sh --forward decide --signal-month YYYY-MM --fetch` | after 21:15 UTC on the month's last weekday, before the close of the execution date | **built, tested** (16 tests in `tests/test_forward.py`); refused on the real clock on 2026-10-25 (observed); not yet run on a forward month |
| Wait log `waits.csv` | written by `decide` when FRED does not yet hold the final signal date | each re-check | **built, tested** |
| Shadow line in `shadow.csv` (§11.3) | `./reproduce.sh --forward shadow --signal-month YYYY-MM --fetch` | after the close of that month's execution date; the first line (period from the 2026-10 record's execution date) follows the 2026-11 record | **built, tested** against the frozen engine; not yet run |
| Interim figures `interim.json` | `./reproduce.sh --forward interim` (also rewritten by `shadow`) | every month | **built, tested**; heading "Not yet scored", no statistic |
| Scoring (§11.4) | `forward.score` | once per 60-period block; the scoring date is in the record that ends the block | **built, tested** on constructed data; refuses until then |
| Inputs | `--fetch`: FRED DGS10, DTB3, DGS7 (decide) and Alpaca `adjustment='all'` daily bars of IEF and BIL from 2026-01-02 (shadow) into `raw/` (git-ignored), hashes in `manifest.json` | with each step | **built** (the study's own fetchers with other paths); not yet run |

## Rules the code enforces (each has a test)

- No record for a month before 2026-10; none before 21:15 UTC on the month's last weekday. A refused run writes nothing and exits 1.
- t (Study 001 §6.3) is final only when every later weekday of the month has a FRED row or is an NYSE holiday; until then a wait line, no record.
- Only observations dated on or before t enter a record (tested: identical with and without later data).
- The execution date is the first NYSE day after t whose close follows the record; at most the third. Past that, a `signal unavailable` record: positions held, the period runs on, never filled later.
- A record is never rewritten; a shadow line is appended once per period and only for the period that follows the last one.
- Engine conventions are the study's own (`backtest.run_switching`, `backtest.benchmarks`): base cost 0.02% a side on a switch of the whole position, B1 free, B2 and B3 rebalanced at each execution date, B3 at w = 0.8702 frozen by the history run. `d = T1 − B3`.
- The study's `data/raw/` and `results/data_manifest.json` are never touched.

## Record

| Signal month | Signal date | Execution date | Record | Shadow line |
|---|---|---|---|---|
| 2026-10 | 2026-10-30 (expected) | 2026-11-02 (expected) | not yet | n/a (first period starts here) |

Not yet scored: no holding period has ended.
