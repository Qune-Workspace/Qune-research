# Trial log: Study 007, bond carry tilt by level on the long history (1974–2018)

Approval: the owner approved Study 001's design and the symbols IEF and BIL on 2026-10-21 and, the same day, delegated all further decisions on this research programme to the orchestrator. This pre-registration is approved by the orchestrator under that delegation on the date of its first commit (header of PREREGISTRATION.md). An `APPROVED` file is written at implementation time (§14 step 4), after this commit, so that `reproduce.sh` keeps its refusal gate.

Every trial is logged here before it is run (§7). **Criterion C3 is decided at the programme-level family count (§9.4): 14 at registration** (Study 003 T1–T3, Study 005 T1–T3, Study 006 T1–T3, this study's five), re-counted immediately before the history run and written below; N = 5 and N = 10 are reported beside it. Any further rule, parameter or sub-sample choice is appended with a date before it is run, and both counts increase. **Rows are never rewritten: every outcome is a new row appended below** (Study 006 `REVIEW.md`, should-fix 2).

## Registered trials (N = 5)

| ID | Date logged | Description | Window |
|---|---|---|---|
| T1 | 2026-10-25 (this commit) | Primary: weight in the synthetic duration leg = expanding percentile rank of the leg's carry (Study 001 §7's carry including roll-down), minimum 60 month-end carries, tie rule and denominator of §6.2; the rest in synthetic cash; costs on the traded fraction with drift (§6.4) | 1974-07 to 2018-12, about 534 periods (exact count at the data step) |
| T1a | 2026-10-25 (this commit) | Fragility companion: the same with a minimum of 36 months | the test window (its earlier weights are not used) |
| T1b | 2026-10-25 (this commit) | Fragility companion: the same with a minimum of 120 months | 1979-07 to 2018-12, about 474 periods; T1 reported beside it on the same periods, descriptive |
| T2 | 2026-10-25 (this commit) | Secondary: ½ × T1's weight + ½ × 1[12-month excess return of the leg over cash > 0] (§6.3) | the test window |
| T3 | 2026-10-25 (this commit) | Secondary: 1[12-month excess return of the leg over cash > 0], Study 003's rule unchanged on the synthetic indices (§6.3) | the test window |

None of the five has been run. No carry, rank, trend or weight value has been computed on any date; no instrument return or rule return exists under this design.

## Gate and data log (§5.3–§5.5, §14; signal paths and instrument returns only, no rule return)

| Step | Date | Outcome |
|---|---|---|
| Question note committed (step 0) | 2026-10-25 10:21:37Z (`7692356`) | No file read, nothing computed. |
| Pre-registration committed (§14 step 1) | 2026-10-25 (this commit; its own time is the record) | No file read for this study; no carry, rank, trend, weight, gate statistic, instrument return or rule return computed. Family count at registration 14 (the question note said 11; §0 item 11 says why). |
| Data step (§14 step 2), logged before the run | 2026-10-25 11:2x GMT (after `e4c21e5` was pushed) | `data_step.py`: hash-check and copy Study 006's seven files against Study 006's manifest, read date columns only, count the §8.1 and T1b windows and the first signal month of each trial on Study 001's committed execution calendar, and reproduce Study 006's vendor plan field for field as a check on the copy. Outcome appended below whatever it is. Disclosed: this row and the outcome row are committed together (one command), as in Study 006; the pre-registration (`e4c21e5`) was pushed before either. |
| Data step outcome | 2026-10-25 11:25 GMT (`run_at_utc` 11:25:57Z in `results/data_step.json`) | **Passed: every file matched Study 006's SHA-256.** Dates as in `results/data_step.md`. **Test window 534 holding periods** (signal months 1974-06 to 2018-11; first execution date 1974-07-01; last period end 2019-01-02), so "about 534" in the pre-registration is exact. **T1b's window 474 periods** (first signal month 1979-06, first execution 1979-07-02). First signal month by minimum history: T1 1974-06, T1a 1972-06, T1b 1979-06; trend signal from 1970-07. Vendor plan reproduced Study 006's committed `data_step.json` field for field (192 overlap periods, first BIL period 2007-05, 53 periods with synthetic cash on both sides). One calendar note: Study 001's calendar lists signal month 2018-12 twice (its in-sample/out-of-sample boundary rows, both executed 2019-01-02); both fall outside the test window and after every first-signal row, so no count here depends on it; the code step uses `calendar.build_schedule`, not the CSV. No price, yield, return, carry, rank or signal value read. |
