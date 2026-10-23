# Forward record of Study 005 (PREREGISTRATION.md §11; no paper order)

**Label: refuted in-sample.** This folder is the forward record of a conditional rule whose in-sample check found the opposite sign (README.md). It is kept because §11 was pre-registered before any result and the forward record is the only clean test still to come. **No paper order is placed under this study** (§11, §12): the organisation's paper record belongs to Study 003's pre-registered rule, and SPY, the regime input, is never held. Promotion to any order would need an explicit owner decision and Independent Risk clearance; none is asked for.

First signal date: **2026-10-30** (the last NYSE trading day of the first month after the note's publication on 2026-10-23). First execution date: **2026-11-02**. Starting holdings (the episode's terminal targets at the 2026-09-30 signal, `results/episode/summary.json`): B2 BIL, T1 BIL, T2 BIL, T3 BIL. The holding period 2026-10-01 to 2026-11-02 belongs to the episode's last signal and is counted nowhere (§16, step 11 entry).

## What is written, by whom, when

| Piece | Command (from the study folder) | When | Status (2026-10-23) |
|---|---|---|---|
| Decision record `decisions/<signal_date>.json` (§11.1) | `./reproduce.sh --forward decide --signal-date t --fetch` | after 21:15 UTC on the last NYSE trading day of each month | **built, tested** (14 tests in `tests/test_forward.py`; in CI). Check run once against the committed episode: the 2026-09-30 record from the frozen files reproduces the episode's terminal values exactly (nothing written). Not yet run on a forward month |
| Shadow line in `shadow.csv` (§11.2) | `./reproduce.sh --forward shadow --signal-date t --fetch` | after the close of `t`'s execution date; the first line (period 2026-11-02 to 2026-12-01) follows the 2026-11-30 record | **built, tested** against the frozen engine (`switching.run_switching` on the same period returns), not yet run |
| Interim figures `interim.json` (§11.2) | `./reproduce.sh --forward interim` (also rewritten by `shadow`) | every month | **built, tested**; heading "Not yet scored", no verdict sentence |
| Scoring (§11.3–11.4) | `forward.score` | once, at the first month-end with 24 positive-regime months (T1) or 60 holding periods | **built, tested** on constructed data; refuses until the rule fires |
| Bar and CPI fetch | `--fetch`: Alpaca `adjustment='all'` daily bars of IEF, BIL, SPY from 2024-01-02 and FRED CPIAUCNS into `raw/` (git-ignored), hashes in `manifest.json` | with each record | **built** (the library's fetchers with other paths), not yet run |

## Rules the code enforces (each has a test)

- No record before 2026-10-30; none before 21:15 UTC on the signal date (after the 16:00 New York close under EDT or EST: a daily bar fetched during the session would be the partial day); none on a date that is not the last NYSE trading day of its month; none without the IEF, BIL and SPY bars for the signal date. A refused run writes nothing and exits 1.
- Only observations on or before the signal date enter a record (tested: the record is identical with and without later bars).
- A record is never overwritten; a correction is a later record with a note. A shadow line is appended once per period and only for the period that follows the last recorded one; a missed month is logged here as missed, never filled.
- The engine conventions are Study 003's: the period runs between the first common IEF/BIL bars on or after the two execution dates (slippage recorded), a switch pays 0.02% on the sale and on the purchase of the whole position (base case), hold-IEF pays nothing. `d_t = r(B2) − r(B1)`.
- The study's `data/raw/` and `results/data_manifest.json` are never touched by the forward record.

## Record

| Signal date | Execution date | Record | Shadow line | Note |
|---|---|---|---|---|
| 2026-10-30 | 2026-11-02 | not yet (written after 21:15 UTC on 2026-10-30) | n/a (first period starts here) | |

Interim figures: `interim.json` (none yet: no holding period has ended).
