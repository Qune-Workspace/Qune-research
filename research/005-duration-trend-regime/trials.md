# Trial log: Study 005, trend exits from duration conditional on the stock-bond correlation regime

Approval: the owner approved Study 001's design and the symbols IEF and BIL on 2026-10-21 and, the same day, delegated all further decisions on this research programme to the orchestrator. This pre-registration is approved by the orchestrator under that delegation on the date of its first commit (header of `PREREGISTRATION.md`). An `APPROVED` file is written at implementation time (§14 step 2), after this commit, so that `reproduce.sh` keeps its refusal gate. No paper order is placed under this study (§11), so no Independent Risk clearance is sought.

Every trial is logged here before it is run (§7). The deflated Sharpe ratio, reported without decision weight in this study, uses the number of rows in this table, N = 3 at registration. Study 003's three trials tested the unconditional rule and are not trials of this hypothesis; Study 003's T1 enters here as benchmark B2 with its path already known to the author (§2.4). Any further regime variable, window, threshold or sub-sample choice is appended with a date before it is run and N increases.

| ID | Date logged | Description | Date run | Code commit |
|---|---|---|---|---|
| T1 | 2026-10-23 | Primary: regime = sign of the Pearson correlation of daily SPY and IEF total returns over the 63 most recent common return days ending at the month-end signal date; in the positive regime apply Study 003's T1 (IEF if its 12-month excess return over cash is positive, else BIL), in the negative regime hold IEF (§6) | 2026-10-23 11:2x London, in-sample (§14 step 6), logged before the run | 85381f2 (code as of the data-check commit; the run's own commit hash is written into results/insample/summary.json) |
| T2 | 2026-10-23 | Descriptive alternative: the same with a 252-day window (§7) | 2026-10-23 11:2x London, in-sample (§14 step 6), logged before the run | 85381f2 (code as of the data-check commit; the run's own commit hash is written into results/insample/summary.json) |
| T3 | 2026-10-23 | Descriptive alternative: regime = FRED CPIAUCNS twelve-month change for month m−2 above 3.0% at the signal date of month m (§7) | 2026-10-23 11:2x London, in-sample (§14 step 6), logged before the run | 85381f2 (code as of the data-check commit; the run's own commit hash is written into results/insample/summary.json) |

## Data-check log (§5.3; instrument returns, correlations and a committed file only; no rule)

| Step | Date | Outcome |
|---|---|---|
| Question note (step 0) | 2026-10-23 08:2x London | `QUESTION.md` committed (b9ad02e) before this document; no fetch, no regime share, no return. |
| Pre-registration committed (§14 step 1) | 2026-10-23 | this commit; no fetch, no check, no correlation, no return computed |
| Code, first part (§14 step 2) | 2026-10-23 10:5x London | `src/` (five frozen Study 003 modules + `config`, `regime`, `conditional`, `edge`, `forward`, `pipeline`, `checks`, `data`) and `tests/` (20 tests incl. §5.3.5 (i)–(viii); (i) passed against Study 003's committed file to 1e−10 on this machine); CI matrix entry; §16 layout entry. Not yet: `report.py`, `reproduce.sh`, `APPROVED`. No fetch, no check, no correlation of real data beyond test (i)'s reproduction of Study 003's own public column, no return of this study. |

| Code, second part (§14 step 2 complete) | 2026-10-23 11:2x London | `src/report.py` (`--insample`, `--episode`; T1–T3 on their regimes, B0–B3, both cost cases, the edge statistics, the §9.5 row, the §9.7 tables), `src/data.py` fetch commands, `reproduce.sh` (`--check`, `--insample`, `--episode`; `--forward` refuses until §14 step 11), 7 report tests (27 in the suite, all passing), `APPROVED` written in the same commit after `reproduce.sh --check` had refused without it (exit 1, observed). §16 layout entry. No fetch, no check, no correlation of real data beyond test (i), no return of this study. |

| Fetch 1 logged (§5.3.3 step 1, §14 step 3) | 2026-10-23 11:2x London | Alpaca SPY daily bars 2018-09-01 to 2026-09-30, `adjustment='all'`, through `python -m src.data fetch-alpaca-spy` with the desk's existing paper credential read from its file into the environment for the one process (never printed). Attempt 1 of 2; branch S after a second failure on a separate run. Logged before the fetch runs; outcome in the next row. |

| Fetch 1 outcome | 2026-10-23 11:21 London | **Succeeded on attempt 1**: `data/raw/alpaca_SPY_1Day_all.csv`, 2,029 bars, 2018-09-04 to 2026-09-30, SHA-256 `1f1d6425…` in `results/data_manifest.json` (downloaded 2026-10-23T10:21:40Z). Branch S not taken. Dates and row count read; no return, no correlation computed. |
| Fetch 2 logged (§5.3.3 step 2) | 2026-10-23 11:2x London | FRED CPIAUCNS, full history, through `python -m src.data fetch-cpi`. Attempt 1 of 2; after a second failure on a separate run T3 is logged "not run: series unavailable" and N stays 3. Logged before the fetch runs; outcome in the next row. |

| Fetch 2 outcome | 2026-10-23 11:22 London | **Succeeded on attempt 1**: `data/raw/fred_CPIAUCNS.csv`, 1,365 monthly rows, 1913-01 to 2026-09, SHA-256 `cfab9b9b…` in the manifest (downloaded 2026-10-23T10:21:59Z). T3 runs. No correlation, no return computed. |
| `reproduce.sh --check` (§14 step 4) | 2026-10-23 11:2x London | logged before the run: D0, D1, D3 once; outcome in the §16 entry and the next row. |

| `--check`, first invocation | 2026-10-23 11:22 London | D0 **pass** (every file; halt flags false); D1 sign agreement **1.0000** on 691 days (mean abs. difference 0.0060, largest 0.0190); **D3 stopped** before writing: the T3 flag at the 2025-12 signal date had no value because CPIAUCNS has no 2025-10 print. §16 amendment (reading rule for a missing CPI month, T3 only) committed before the second invocation; no regime share, no MDE, no return seen. |
| `--check`, second invocation logged | 2026-10-23 11:2x London | the full script again under the amended code; D0 and D1 are compared with the first invocation's kept outputs; outcome in the next row. |

| `--check`, second invocation | 2026-10-23 11:24 London | D0 written again, **identical** to the first invocation apart from the write time (diff observed); **D1 stopped before writing** on a code fault of this study's `data.py` (the overlap file's scratch manifest is not written when the file is already present, so the second reuse raised FileNotFoundError); `d1.json` on disk is still the first invocation's. D3 not reached. Fixed with a test (29 in the suite); no number of this study seen beyond the first invocation's D0 and D1. |
| `--check`, third invocation logged | 2026-10-23 11:2x London | the full script again under the fixed code; D0 and D1 compared with the first invocation's kept outputs; outcome in the next row and in §16. |

| `--check`, third invocation | 2026-10-23 11:25 London | **Completed.** D0 and D1 identical to the first invocation (diff observed). **D3**: in-sample T1 26 positive-regime months of 185 (14.1%), T2 12, T3 43; σ_d = 0.692%/month from Study 003's committed file; **actual MDE for T1 4.37% a year**; §9.5's in-sample rows **apply**. Episode (no decision weight): T1 38 of 93 positive (40.9%); T2 starts 2019-09 (84 dates); T3 44 of 93; one filled T3 month (2025-12 read 2025-09). Full figures in §16 and `results/checks/`. No return of this study computed. |

| `reproduce.sh --insample` (§14 step 6) logged | 2026-10-23 11:2x London | the single in-sample run, T1–T3 at base and stress costs, logged before it runs; outcome in the next row and the note. |

| `--insample` outcome | 2026-10-23 11:27 London | **Run once, committed as written (e60ab05).** §9.5 rows at base costs: **T1 refuted in-sample** (Δ −0.296%/month, NW t −2.31, 95% interval [−0.519%, +0.027%], upper bound below 0.083%); T2 refuted in-sample (descriptive; Δ −0.593%, t −3.11; 480 of 10,000 resamples dropped for want of a positive month); T3 sign consistent, forward record decides (descriptive; Δ +0.101%, t 0.81, interval [−0.125%, +0.302%]). Note's in-sample section in the next commit. |

In-sample returns of this study were computed once on 2026-10-23 (row above). The 2019–2026 window is the hypothesis-generating episode (§8.2), to be run once under that label now that the in-sample results are committed, with no decision weight. The forward record starts at the first month-end after the note's publication (§11). N = 3.
