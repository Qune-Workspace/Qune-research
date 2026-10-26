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
| Data step (§14 step 2), logged before it runs | 2026-10-26 (this commit; logged before `data_step.py` is run) | To run once after this commit is pushed: `data_step.py` reads the library's page for the two links (exact file-name match, else stop), downloads each file once into `data/raw/` (git-ignored; a second download is refused while `results/data_manifest.json` exists), writes the manifest (URL, UTC time, SHA-256 and bytes of zip and CSV, the header lines naming the CRSP release) and `results/data_step.{json,md}`: the value-weighted monthly section's dates, column names, gaps, duplicates, per-month counts of industries with a value and the eligible count at every held ranking month, all from marker flags (stripped-string comparison with "-99.99", "-999" and empty; no field parsed as a number, no return written or printed, no other section read); §5.4 stop rules. Parser checked on synthetic text before this commit (`tests/test_data_step.py`, 5 tests). The outcome is appended as a new row. |
| Data step outcome | 2026-10-26, run 15:31:24Z (machine clock; downloads 15:31:23Z) | **Pass: no §5.4 stop rule met.** Both files from the 202608 CRSP release; value-weighted monthly sections 1926-07 to 2026-08, 1,202 rows each, no gap, duplicate or out-of-order month; 17 and 30 industry columns, the last named "Other" in both; no missing-value marker anywhere in either section, so every industry is eligible at every held ranking month (minimum 17 of 17 and 30 of 30). Exact month counts: M1 and M1a I1 433, I2 373, **O 806**, M 385, full 1,191; M1b I1 427, I2 373, **O 800**, full 1,185, as pre-registered. Manifest and outputs: `results/data_manifest.json`, `results/data_step.{json,md}`. No return value read. |
| Code and tests (§14 step 3); separate-session code review | 2026-10-26, commits `fc2e1cc`, `0ab2ab2`, `8ccf310` | Pass with fixes: 1 must-fix (run-once marker before any value is read) and 4 should-fix, all taken; 21 tests on synthetic data ([CODE_REVIEW.md](CODE_REVIEW.md)). No industry return read. `APPROVED` not yet written. |
