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
| Data step (§14 step 2), logged before the run | 2026-10-25 02:2x London | `data_step.py`: hash-check and copy the §5.1 files, read date columns only, apply the §5.3.2 vendor rule to Study 001's execution calendar. Outcome appended below whatever it is. Disclosed: after the pre-registration was pushed (`a67ef8d`) and before this script was written, the header and first row of four input files were printed to confirm their column layout (first IEF, BIL and DGS10 rows of 2002, 2007 and 1962); no other value was looked at. |
| Data step outcome | 2026-10-25 02:21 London (`run_at_utc` 02:21:01Z in `results/data_step.json`) | **Passed: every file matched its source manifest's SHA-256**; dates as in `results/data_step.md`. Overlap: 192 periods (execution 2003-01-02 to period end 2019-01-02); IEF from Tiingo for 156, Alpaca for 36 (first Alpaca period from 2016-01-04), none missing. **First BIL period: signal month 2007-05, execution 2007-06-01 to 2007-07-02 (Tiingo)**; the 53 periods before it use synthetic cash on both sides; BIL from Tiingo for 103 and Alpaca for 36, none missing afterwards. Note on order: the row above was written to this file before the run but committed together with this outcome (one command); the pre-registration (`a67ef8d`) was pushed before either. No price, yield, return or signal value read. |

No return of any rule or benchmark has been computed on any window as of this commit, under this study or Studies 001 and 002. T1, T2 and T3 have never been run.
