# Trial log: Study 004, cross-asset time-series momentum with volatility targeting (twelve ETFs, long-only or flat)

Approval: the owner delegated all decisions on this research programme to the orchestrator on 2026-10-21, including the use of liquid ETFs beyond the approved paper symbols for research. This pre-registration is approved by the orchestrator under that delegation on the date of its first commit (header of PREREGISTRATION.md). An `APPROVED` file is written at implementation time (§14 step 3), after this commit, so that `reproduce.sh` keeps its refusal gate. No paper order is part of this study (§11).

Every trial is logged here before it is run (§7). The deflated Sharpe ratio uses the number of rows in this table, N = 4 at registration. Study 003's three trials tested a different hypothesis on one instrument and do not count here (§7); what was seen of them is disclosed in §2.4. Any further rule, parameter, universe or sub-sample choice is appended with a date before it is run and N increases.

| ID | Date logged | Description | Date run | Code commit |
|---|---|---|---|---|
| T1 | 2026-10-22 | Primary: per asset, long if its 12-month excess return over cash at the month-end close is positive, else flat; each position sized to σ_a/(N_t·σ_i) with σ_a = 10%, 63-day σ, 25% cap, no leverage (§6) | not run | — |
| T2 | 2026-10-22 | 6-month lookback, everything else as T1 (§7) | not run | — |
| T3 | 2026-10-22 | 3-month lookback, everything else as T1 (§7) | not run | — |
| T4 | 2026-10-22 | Blend: each asset on at the average of its 12-, 6- and 3-month signals (0, ⅓, ⅔, 1), everything else as T1 (§7) | not run | — |

## Data-check log (§5.3; instrument data only, no rule)

| Step | Date | Outcome |
|---|---|---|
| Pre-registration committed (§14 step 1) | 2026-10-22 | this commit; no fetch, no check, no return computed; ten of the twelve instruments have never been fetched from any source |
| Shared library piece 1 (§14 step 2, in progress) | 2026-10-22 20:3x London | `qune_research/` dates, sizing, engine with tests for §5.3.4 (i), (ii), (iii), (v), (vi), (viii): 9 pass on constructed data; in CI. Check (ii) reworded (§16). No data fetched, no check run, no return computed. Remaining for step 2: data adapters, statistics (incl. check vii), report, the study's `src/` and `reproduce.sh`. |
| Shared library piece 2 (§14 step 2, in progress) | 2026-10-22 20:4x London | `qune_research/stats.py` ported from Study 003 by attribution with the degenerate-resample rule; Study 003's statistics tests rerun against it plus the §5.3.4 (vii) test: 21 pass. Still no data fetched, no check run, no return computed. Remaining for step 2: data adapters with hashing, report, the study's `src/` and `reproduce.sh`. |
| Shared library piece 3 + the study's code (§14 step 2, completed) | 2026-10-22 21:3x London | `qune_research/nyse` (calendar ported from Study 003), `data` (Tiingo, Alpaca, FRED adapters and hash-checked reuse, every path a parameter), `datacheck` (coverage, overlap statistics, no thresholds): library tests 70 pass. Study `src/config.py` (every §4–§9 constant), `src/data.py` (reuse-or-fetch per §5.1), `src/checks.py` (§5.3.1 D0 with the single retry and branch X, §5.3.2 D1 with the ±0.20% gate, the single-vendor skip and branch X, §5.3.5 halt rule, §8.1 entry dates from dates only), `reproduce.sh --check` (D0 then D1; --insample/--oos refuse as not built), 11 study tests covering every branch on constructed series; study added to CI. Still no data fetched, no check run, no return computed. |
| APPROVED (§14 step 3) | 2026-10-22 21:2x London | commit 08d8019, after the code and tests; no data check run, no return computed. |
| D0 fetch and coverage (§5.3.1, §14 step 4, single run) | 2026-10-22 21:25 London | commit 24a40fe: eleven files fetched, IEF and BIL reused by hash; all thirteen pass coverage from their first bar with no missing NYSE trading day; every entry signal date as expected in §4; no retry, no exclusion. Manifest committed before D1. Dates only. |
| D1 overlap per symbol (§5.3.2, §14 step 4, single run) | 2026-10-22 21:26 London | commit 6f01969: 753 common return days 2016-01-04..2018-12-31; ten within ±0.20% p.a.; **SPY +0.3146% and DBC −0.4648% excluded under branch X**; HYG +0.1410% inside the gate but outside the ex-ante 0.10%; broker bars available for all twelve (none single-vendor). §5.3.5: two exclusions, every class ≥ 2, **proceed with ten instruments**. Recorded in §16; N = 4 unchanged. No return of any rule computed. |
