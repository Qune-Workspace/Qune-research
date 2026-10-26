# Trial log: Study 009, pooled forward check of Studies 006–008 (low-power check)

Every trial is logged here before it is run. Rows are never rewritten: every outcome is a new row appended below. Time labels are read from `git log` or the machine clock, never estimated.

## Registered trials (N = 1)

| ID | Date logged | Description | Window |
|---|---|---|---|
| P1 | 2026-10-26 (this commit) | Equal-weight average of the forward d = T1 − B3 of Studies 006, 007 and 008 on their common holding periods, members dropped only under PREREGISTRATION.md §2; Newey–West t (6 lags), rows of §3 | common holding periods (same signal date, execution date and period end in every member) inside every remaining member's first 60-period block, from the 2026-10 signal month (first execution date expected 2026-11-02); n ≤ 60, reported |

Not run. No forward record of any member exists; no forward return has been fetched or computed.

## Log

| Step | Date | Outcome |
|---|---|---|
| Power (`tools/power_pooled.py`) | 2026-10-26, commit `36eae76` | From committed history files only; members' published t reproduced first. Figures in PREREGISTRATION.md §4. |
| Design review (separate session, Fable, isolated, read-only) | 2026-10-26 01:19:40Z–01:22:59Z (reviewer's clock) | Approve with changes: 2 must-fix (period keying under missed or slipped months; scoring rule), 3 should-fix, 3 notes; all addressed in PREREGISTRATION.md before its first commit. [DESIGN_REVIEW.md](DESIGN_REVIEW.md). |
