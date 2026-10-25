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
