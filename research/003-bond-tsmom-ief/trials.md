# Trial log: Study 003, time-series momentum in intermediate Treasuries (IEF vs BIL)

Approval: the owner approved Study 001's design and the symbols IEF and BIL on 2026-10-21 and, the same day, delegated all further decisions on this research programme to the orchestrator. This pre-registration is approved by the orchestrator under that delegation on the date of its first commit (header of PREREGISTRATION.md). An `APPROVED` file is written at implementation time (§14 step 3), after this commit, so that `reproduce.sh` keeps its refusal gate.

Every trial is logged here before it is run (§7). The deflated Sharpe ratio uses the number of rows in this table, N = 3 at registration. Studies 001 and 002 registered three trials of a different hypothesis and never ran them; they do not count here (§7). Any further rule, parameter or sub-sample choice is appended with a date before it is run and N increases.

| ID | Date logged | Description | Date run | Code commit |
|---|---|---|---|---|
| T1 | 2026-10-22 | Primary: sign of IEF's 12-month excess return over cash at the month-end close; IEF if positive, BIL otherwise (§6.1) | registered, not run | — |
| T2 | 2026-10-22 | V1: 12-1, the same excess return measured to the end of the previous month (§7) | registered, not run | — |
| T3 | 2026-10-22 | V2: IEF month-end adjusted close above its 10-month moving average (Faber, 2007); price only (§7) | registered, not run | — |

## Data-check log (§5.3; instrument returns only, no rule)

| Step | Date | Outcome |
|---|---|---|
| Pre-registration committed (§14 step 1) | 2026-10-22 | this commit; no fetch, no check, no return computed |
| BIL vendor fetch (§5.3.2 step 1) | logged 2026-10-22 06:3x London before the run; outcome appended below | **About to run once**: Tiingo daily BIL prices from 2007-05-01 with the desk's existing credential (token read from the environment, sent as a header, never logged; no credential created). The overlap-check code (`src/bil_overlap_check.py`, acceptance = mean difference within ±0.05% p.a. only, as §5.3.2 fixes) is committed in the same commit as this row, before either runs. |

No return of any rule or benchmark has been computed on real data as of 2026-10-22 under this study. T1, T2 and T3 have not been run. The out-of-sample window (2019-01 to 2026-09) has never been touched by any study.
