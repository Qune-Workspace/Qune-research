# Paper dashboard: the forward records, as committed

Generated 2026-10-26T22:22:32Z from the files at commit `930db95` by `tools/make_paper_dashboard.py`. Each study's forward code writes its own record once a month and never rewrites it; this page only counts and draws what is on disk at generation time, so an empty row means no record exists yet, not that one was missed. Nothing here is a backtest: every value is a forward observation after the study's publication. No study has a supported verdict; no order has been placed. Not advice.

| Study | Kind | Records | Shadow lines | Next record due |
|---|---|---|---|---|
| Study 003 | paper sleeve, not supported; paper record of a not-supported rule; orders only once Independent Risk clears the sleeve | 0 | 0 | 30 Oct 2026 |
| Study 004 | shadow record, not supported; no paper order | 0 | 0 | 30 Oct 2026 |
| Study 005 | shadow record, refuted in-sample; no paper order | 0 | 0 | 30 Oct 2026 |
| Study 006 | shadow record, inconclusive (fragile) on 1969–2018; forward record, scored once after 60 periods; no paper order | 0 | 0 | 30 Oct 2026 |
| Study 007 | shadow record, inconclusive (fragile) on 1974–2018; forward record, scored once after 60 periods; no paper order | 0 | 0 | 30 Oct 2026 |
| Study 008 | shadow record, not supported on 1974–2018; forward record, scored once after 60 periods; no paper order | 0 | 0 | 30 Oct 2026 |
| Study 010 | monthly position record, not supported on 1927–2026; shadow-only, every month scored once after 60 holding months; no paper order | 1 | none (scored once at the end) | 2026-10, from release 202609 once published |
| Study 011 | monthly cohort record, not supported on 806 months outside [MG99]'s 1963–1995 sample; shadow-only, scored once after 60 holding months; no paper order | 1 | none (scored once at the end) | 2026-10, from release 202609 once published |

## Study 003 (paper sleeve)

**Label: not supported; paper record of a not-supported rule; orders only once Independent Risk clears the sleeve.** Folder `research/003-bond-tsmom-ief/paper-log/`.

| | |
|---|---|
| Decision records | 0 |
| Last record | none yet |
| Shadow lines (holding periods ended) | 0 |
| Next record due (signal date) | 30 Oct 2026 |
| Execution records (orders) | 0 |
| Runner lines in runs.jsonl | 1 |
| Daily stop-check lines | 0 |

No chart yet: the first shadow line follows the record after 30 Oct 2026.

## Study 004 (shadow record)

**Label: not supported; no paper order.** Folder `research/004-xasset-trend-voltarget/paper-log/`.

| | |
|---|---|
| Decision records | 0 |
| Last record | none yet |
| Shadow lines (holding periods ended) | 0 |
| Next record due (signal date) | 30 Oct 2026 |

No chart yet: the first shadow line follows the record after 30 Oct 2026.

## Study 005 (shadow record)

**Label: refuted in-sample; no paper order.** Folder `research/005-duration-trend-regime/paper-log/`.

| | |
|---|---|
| Decision records | 0 |
| Last record | none yet |
| Shadow lines (holding periods ended) | 0 |
| Next record due (signal date) | 30 Oct 2026 |

No chart yet: the first shadow line follows the record after 30 Oct 2026.

## Study 006 (shadow record)

**Label: inconclusive (fragile) on 1969–2018; forward record, scored once after 60 periods; no paper order.** Folder `research/006-term-spread-switch-long-history/paper-log/`.

| | |
|---|---|
| Decision records | 0 |
| Last record | none yet |
| Shadow lines (holding periods ended) | 0 |
| Next record due (signal date) | 30 Oct 2026 |

No chart yet: the first shadow line follows the record after 30 Oct 2026.

## Study 007 (shadow record)

**Label: inconclusive (fragile) on 1974–2018; forward record, scored once after 60 periods; no paper order.** Folder `research/007-bond-carry-tilt-long-history/paper-log/`.

| | |
|---|---|
| Decision records | 0 |
| Last record | none yet |
| Shadow lines (holding periods ended) | 0 |
| Next record due (signal date) | 30 Oct 2026 |

No chart yet: the first shadow line follows the record after 30 Oct 2026.

## Study 008 (shadow record)

**Label: not supported on 1974–2018; forward record, scored once after 60 periods; no paper order.** Folder `research/008-bond-value-tilt-long-history/paper-log/`.

| | |
|---|---|
| Decision records | 0 |
| Last record | none yet |
| Shadow lines (holding periods ended) | 0 |
| Next record due (signal date) | 30 Oct 2026 |

No chart yet: the first shadow line follows the record after 30 Oct 2026.

## Study 010 (monthly position record)

**Label: not supported on 1927–2026; shadow-only, every month scored once after 60 holding months; no paper order.** Folder `research/010-factor-momentum-french-us/paper-log/`.

| | |
|---|---|
| Monthly records | 1 |
| Last record | 2026-09 from release 202608 (recorded) |
| Last release check | 26 Oct 2026 22:16Z: release 202608, not kept (not newer than the history snapshot's release 202608) |
| Next record due | 2026-10, from release 202609 once published |
| Scoring | once, by `python -m src.forward010 score --release YYYYMM`, after 60 holding months (2026-09 to 2031-08), from the first archived release that contains 2031-08; a low-power check (detects a Sharpe of d of about 1.27 at 80% power); `interim` gives months recorded, months with a return, cumulative T and B3 and the mean of d, without a t-statistic or verdict |

| Month | Release | Status | Positions by trial |
|---|---|---|---|
| 2026-09 | 202608 | recorded | T1: SMB +1, HML +1, ST_Rev -1, LT_Rev +1<br>T1a: SMB +1, HML +1<br>T1b: SMB +1, HML +1, ST_Rev -1, LT_Rev +1 |

No equity line: positions are +1 (long) or −1 (short) per factor; the factor returns of each month come from a later library release and are scored only at the end.

## Study 011 (monthly cohort record)

**Label: not supported on 806 months outside [MG99]'s 1963–1995 sample; shadow-only, scored once after 60 holding months; no paper order.** Folder `research/011-industry-momentum-french-us/paper-log/`.

| | |
|---|---|
| Monthly records | 1 |
| Last record | 2026-09 from release 202608 (recorded) |
| Last release check | 26 Oct 2026 22:17Z: release 202608, not kept (not newer than the history snapshot's release 202608) |
| Next record due | 2026-10, from release 202609 once published |
| Scoring | once, by `python -m src.forward011 score --release YYYYMM`, after 60 holding months (2026-09 to 2031-08), from the first archived release that contains 2031-08; a low-power check (detects a Sharpe of d of about 1.27 at 80% power); `interim` gives counts and the mean and sum of d without a t-statistic or verdict |

| Month | Release | Status | Positions by trial |
|---|---|---|---|
| 2026-09 | 202608 | recorded | M1: long Machn, Oil, Finan / short Steel, Cnstr, Clths<br>M1a: long BusEq, Coal, Oil, Servs, Fin / short Steel, Hshld, Games, Beer, Clths<br>M1b: long Mines, Machn, Oil / short Durbl, Cnstr, Clths |

No equity line: each month starts a six-month cohort (winners long, losers short, French Data Library industry names); its returns are scored only at the end.

## How this page is made

`make dashboard` runs `tools/make_paper_dashboard.py`, which reads each study's `paper-log/decisions/*.json`, `shadow.csv` (Study 003: its §11.5 `summary.csv`), `executions/*.json`, `runs.jsonl` and `stops.jsonl` as committed (Studies 010 and 011: their monthly `positions.csv` or `cohorts.csv` and the last line of `releases/fetch_log.csv`), compounds the shadow lines' net returns (or reads the book values Study 004 writes) into one path per series, and draws it with `qune_research/style.py`. The SHA-256 of every input file and the generation time are in `manifest.json`. The page is regenerated by the work loop after each record; a run that finds nothing new changes only the time stamp. The forward records' own rules (no record before the close, never overwritten, misses logged as misses) are in each study's `paper-log/README.md`.
