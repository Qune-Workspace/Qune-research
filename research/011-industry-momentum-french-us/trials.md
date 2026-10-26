# Trial log: Study 011, industry momentum on US industries outside Moskowitz and Grinblatt's sample

Approval: the owner delegated all decisions on this research programme to the orchestrator on 2026-10-21. This pre-registration is approved by the orchestrator under that delegation on the date of its first commit. An `APPROVED` file is written at implementation time (PREREGISTRATION.md §14 step 4), after this commit, so that `reproduce.sh` keeps its refusal gate.

Every trial is logged here before it is run. **Criterion C3 is decided at N = 3** (a new family, PREREGISTRATION.md §9.4); the programme-wide count is re-counted immediately before the history run, written below, and has no decision weight. Any further rule, parameter or sub-sample choice is appended with a date before it is run. **Rows are never rewritten: every outcome is a new row appended below.** Time labels are read from `git log` or the machine clock, never estimated.

## Registered trials (N = 3)

| ID | Date logged | Description | Window |
|---|---|---|---|
| M1 | 2026-10-26 (this commit) | Industry momentum [MG99], variant on the library: 17 value-weighted industries ranked on their compounded return over t − 6 to t − 1 (no skipped month); long the top 3, short the bottom 3, equal weight within each leg; six overlapping six-month cohorts, 1/6 each; costs 10 bp base, 50 bp stress on Σ\|Δw\| (§6.3); against zero | O: I1 1927-06 to 1963-06 and I2 1995-08 to the snapshot's last common month (expected 2026-08; 806 months expected, exact count at the data step) |
| M1a | 2026-10-26 (this commit) | Fragility companion: 30 industries, top 5 / bottom 5; otherwise M1 | O, as M1 |
| M1b | 2026-10-26 (this commit) | Fragility companion: formation t − 12 to t − 1; otherwise M1 | O: I1 1927-12 to 1963-06 and I2 (800 months expected) |

None of the three has been run. No industry file of the library has been downloaded for this study; no industry return, formation return, rank, position or rule return exists on any window.

## Log

| Step | Date | Outcome |
|---|---|---|
| Question note (step 0) | 2026-10-26, commit `7c0c156` (15:22:57Z by git) | No file read, nothing computed. Separate-session check before commit ([QUESTION_REVIEW.md](QUESTION_REVIEW.md)). |
| Design review of the pre-registration (separate session, Opus 5.5, isolated, read-only) | 2026-10-26, before the first commit of PREREGISTRATION.md | Approve with changes: 3 must-fix (forward lateness measured against month t, not t − 1; the data-step stop on eligible industries at every held ranking month, not on a per-month value count; an over-claim about the paper's horizons reworded), 9 should-fix; all addressed before the first commit. [DESIGN_REVIEW.md](DESIGN_REVIEW.md). |
| Pre-registration committed (§14 step 1) | 2026-10-26 (this commit; its own time is the record) | No library file fetched; no industry value read. |
