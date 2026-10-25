# Trial log: Study 008, bond value tilt by the real yield on the long history (1974–2018)

Approval: the owner approved Study 001's design and the symbols IEF and BIL on 2026-10-21 and, the same day, delegated all further decisions on this research programme to the orchestrator. This pre-registration is approved by the orchestrator under that delegation on the date of its first commit (header of PREREGISTRATION.md). An `APPROVED` file is written at implementation time (§14 step 4), after this commit, so that `reproduce.sh` keeps its refusal gate.

Every trial is logged here before it is run (§7). **Criterion C3 is decided at the programme-level family count (§9.4): 17 at registration** (Study 003 T1–T3, Study 005 T1–T3, Study 006 T1–T3, Study 007's five, this study's three), re-counted immediately before the history run and written below; N = 3 and N = 10 are reported beside it. Any further rule, parameter or sub-sample choice is appended with a date before it is run, and both counts increase. **Rows are never rewritten: every outcome is a new row appended below.** Time labels are read from `git log` or the machine clock, never estimated.

## Registered trials (N = 3)

| ID | Date logged | Description | Window |
|---|---|---|---|
| T1 | 2026-10-25 (this commit) | Primary: weight in the synthetic duration leg = expanding average-rank percentile of the real yield r_m = DGS10 at the signal date − (CPIAUCNSA(m−1)/CPIAUCNSA(m−13) − 1), with the availability and missing-index rules of §6.1; minimum 60 defined real yields; the rest in synthetic cash; costs on the traded fraction with drift (Study 007 §6.4) | 1974-07 to 2018-12, about 534 periods (exact count at the data step) |
| T1a | 2026-10-25 (this commit) | Fragility companion: the same with core CPI (CPILFENS) in π | the test window |
| T1b | 2026-10-25 (this commit) | Fragility companion: the same as T1 with a trailing 120-month rank (the last 120 defined real yields including today, denominator 119) | 1979-07 to 2018-12, about 474 periods; T1 reported beside it on the same periods, descriptive |

None of the three has been run. No CPI file has been fetched or read for this study; no inflation rate, real yield, rank or weight value has been computed on any date; no instrument return or rule return exists under this design.

## Gate and data log (§5, §14; signal paths and instrument returns only, no rule return)

| Step | Date | Outcome |
|---|---|---|
| Question note committed (step 0) | 2026-10-25 16:24:09Z (`1d1daeb`) | No file read, nothing computed. |
| Inflation-forecast check (`QUESTION.md` §4) | 2026-10-25 17:1x GMT (machine clock read at 17:19:42Z, after the check), before this commit | No public monthly inflation-forecast series covers 1969–2018: FRED `MICH` monthly and contiguous from 1978-01 (first and last dates read, 585 rows to 2026-09, no value looked at); Livingston Survey semiannual from 1946; SPF CPI forecasts quarterly from 1981 Q3 (10-year from 1991 Q4), these two from the survey pages and search summaries, not data files. T1's trailing-CPI proxy stands; no trial added (PREREGISTRATION §5.5). |
| Pre-registration committed (§14 step 1) | 2026-10-25 (this commit; its own time is the record) | No CPI file fetched; no inflation rate, real yield, rank, weight, gate statistic, overlap correlation, instrument return or rule return computed. Family count at registration 17. |
