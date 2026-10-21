# Trial log: Study 002, term-spread duration switch re-tested with a roll-down-aware synthetic series

Approval: the owner approved the design of Study 001 and the symbols IEF and BIL on 2026-10-21 and, the same day, delegated all further decisions on this research programme to the orchestrator. This pre-registration is approved by the orchestrator under that delegation on the date of its first commit (§ header of PREREGISTRATION.md). An `APPROVED` file is written at implementation time (§14 step 3), after this commit, so that `reproduce.sh` keeps its refusal gate.

Every trial is logged here before it is run (§7). The deflated Sharpe ratio uses the number of rows in this table, N = 3 at registration (carried over from Study 001, where the same three trials were registered on 2026-10-21 and never run; see §7 for why N is not 6). Any further rule, parameter or sub-sample choice is appended with a date before it is run and N increases.

| ID | Date logged | Description | Date run | Code commit |
|---|---|---|---|---|
| T1 | 2026-10-21 (Study 001); carried over 2026-10-21 | Primary: month-end sign of the 10-year minus 3-month spread (bond-equivalent basis); IEF if positive, BIL otherwise (Study 001 §6.1) | registered, not run | — |
| T2 | 2026-10-21 (Study 001); carried over 2026-10-21 | V1: mean of the last 21 valid daily spreads ending on the signal date, same threshold (Study 001 §7) | registered, not run | — |
| T3 | 2026-10-21 (Study 001); carried over 2026-10-21 | V2: carry including roll-down, spread + D_mod(DGS10) × (DGS10 − DGS7)/3, from 1969-07 (Study 001 §7) | registered, not run | — |

## Validation log (§5.3; instrument returns only, no rule)

| Step | Date | Outcome |
|---|---|---|
| Pre-registration committed (§14 step 1) | 2026-10-21 | this commit; no validation run, no return computed |
| Window-2 vendor fetch (§5.3.4 step 1) | 2026-10-22 00:18 London (2026-10-21T23:18Z) | Tiingo IEF daily prices fetched with the desk's existing credential (token read from the environment, sent as a header, never logged; no credential created): 6,099 rows, 2002-07-26 to 2026-10-21, SHA-256 in `results/data_manifest.json`. Starts before 2003-01-02, so window 2 is **not** excluded for unavailability. Tiingo's first row is 2002-07-26, four days after the fund's 2002-07-22 inception; irrelevant to window 2. No return computed. |
| Window-2 overlap check (§5.3.4 step 2) | — | `src/overlap_check.py` written and committed with this entry, before running; not yet run |
| `reproduce.sh --validate`, single run (§14 step 4) | — | not yet run |

No return of any rule or benchmark has been computed on real data as of 2026-10-21, under this study or Study 001.
