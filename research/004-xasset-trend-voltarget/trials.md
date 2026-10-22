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
