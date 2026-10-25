# Trial log: Study 006, term-spread duration switch on the long history (1969–2018), gate tied to the decision

Approval: the owner approved Study 001's design and the symbols IEF and BIL on 2026-10-21 and, the same day, delegated all further decisions on this research programme to the orchestrator. This pre-registration is approved by the orchestrator under that delegation on the date of its first commit (header of PREREGISTRATION.md). An `APPROVED` file is written at implementation time (§14 step 4), after this commit, so that `reproduce.sh` keeps its refusal gate.

Every trial is logged here before it is run (§7). The deflated Sharpe ratio's decision count is the number of rows in this table, N = 3 at registration, carried over from Studies 001 and 002, where the same three trials were registered on 2026-10-21 and never run; N = 10 is reported beside it, and the programme-level family count descriptively (§9.4). Any further rule, parameter or sub-sample choice is appended with a date before it is run, and N increases.

| ID | Date logged | Description | Date run | Code commit |
|---|---|---|---|---|
| T1 | 2026-10-21 (Study 001); carried over 2026-10-25 | Primary: month-end sign of the 10-year minus 3-month spread (bond-equivalent basis); synthetic 8.5-year leg if positive, synthetic cash otherwise (Study 001 §6.1; legs Study 002 §5.2 and Study 001 §5.2) | registered, not run | — |
| T2 | 2026-10-21 (Study 001); carried over 2026-10-25 | 21-observation mean of the spread, same threshold (Study 001 §7) | registered, not run | — |
| T3 | 2026-10-21 (Study 001); carried over 2026-10-25 | Carry including roll-down, spread + D_mod(DGS10) × (DGS10 − DGS7)/3 (Study 001 §7) | registered, not run | — |

## Gate and data log (§5.3–§5.4; instrument returns and signal paths only, no rule)

| Step | Date | Outcome |
|---|---|---|
| Question note committed | 2026-10-25 01:1x–01:4x London | `07962f7`, `1f20f16`; no file read, nothing computed |
| Pre-registration committed (§14 step 1) | 2026-10-25 (this commit; its own time is the record) | No file read for this study; no gate statistic, signal path, instrument return or rule return computed |

No return of any rule or benchmark has been computed on any window as of this commit, under this study or Studies 001 and 002. T1, T2 and T3 have never been run.
