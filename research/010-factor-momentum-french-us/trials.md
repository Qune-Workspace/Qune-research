# Trial log: Study 010, time-series factor momentum on four US equity factors (1927–2026)

Approval: the owner delegated all decisions on this research programme to the orchestrator on 2026-10-21. This pre-registration is approved by the orchestrator under that delegation on the date of its first commit. An `APPROVED` file is written at implementation time (PREREGISTRATION.md §14 step 4), after this commit, so that `reproduce.sh` keeps its refusal gate.

Every trial is logged here before it is run. **Criterion C3 is decided at N = 3** (a new family, PREREGISTRATION.md §9.4); the programme-wide count is re-counted immediately before the history run, written below, and has no decision weight. Any further rule, parameter or sub-sample choice is appended with a date before it is run. **Rows are never rewritten: every outcome is a new row appended below.** Time labels are read from `git log` or the machine clock, never estimated.

## Registered trials (N = 3)

| ID | Date logged | Description | Window |
|---|---|---|---|
| T1 | 2026-10-26 (this commit) | Time-series factor momentum [EL19]: each factor held +1 if its compounded return over t − 12 to t − 1 is > 0, else −1; equal weight over the factors held (SMB, HML, ST_Rev from 1927-07; LT_Rev from 1932-01); monthly; timing costs 10 bp base, 50 bp stress (§6.3); against its own B3 at h̄ over H | H: 1927-07 to the snapshot's last common month (expected 2026-08, about 1,190 months; exact count at the data step) |
| T1a | 2026-10-26 (this commit) | Fragility companion: SMB and HML only; otherwise T1 | H |
| T1b | 2026-10-26 (this commit) | Fragility companion: the four factors, formation t − 6 to t − 1 (LT_Rev from 1931-07); otherwise T1 | H |

None of the three has been run. No file of the library has been downloaded for this study; no factor return, formation return, position or rule return exists on any window.

## Log

| Step | Date | Outcome |
|---|---|---|
| Question note (step 0) | 2026-10-26, commits `e699ac3` (07:25:24Z by git) and `9cfd47f` | No file read, nothing computed. |
| Design review of the pre-registration (separate session, Opus 5.5, isolated, read-only) | 2026-10-26 08:18:56Z–08:21:05Z (reviewer's clock), before the first commit of PREREGISTRATION.md | Approve with changes: 4 must-fix (stop rule on markers and month gaps over the formation months before H; start-date mismatch in either direction stops, entry dates fixed by the document; forward rows scored whatever the commit time, late rows labelled not dropped; forward trials and frozen h̄ named), 8 should-fix; all addressed before the first commit. [DESIGN_REVIEW.md](DESIGN_REVIEW.md). |
| Pre-registration committed (§14 step 1) | 2026-10-26 (this commit; its own time is the record) | No library file fetched; no factor value read. |
| Data step (§14 step 2), logged before it runs | 2026-10-26 (this commit; logged before `data_step.py` is run) | To run once after this commit is pushed: `data_step.py` reads the library's page for the three links (exact file-name match, else stop), downloads each file once into `data/raw/` (git-ignored; a second download is refused while `results/data_manifest.json` exists), writes the manifest (URL, UTC time, SHA-256 and bytes of zip and CSV, the header lines naming the CRSP release) and `results/data_step.{json,md}`: monthly-section dates, gaps and missing-marker flags only (−99.99, −999, empty), no factor value written or printed; §5.4 stop rules. Parser checked on a synthetic file before this commit. The outcome is appended as a new row. |
| Data step outcome (§14 step 2) | 2026-10-26: library page read 09:17:56Z, three files downloaded 09:17:57Z, step run 09:17:58Z (machine clock, written by the script); after commit `cb8866c` was pushed | **Pass: no §5.4 stop rule met.** File names as expected (no §16 note). All three files name the **202608 CRSP release**. Monthly sections: 3-factor file 1926-07 to 2026-08 (1,202 rows), ST_Rev 1926-02 to 2026-08 (1,207), LT_Rev 1931-01 to 2026-08 (1,148): each start as `QUESTION.md` §1 states; no month gap; no missing-value marker in any column. **H = 1927-07 to 2026-08, 1,190 months**; P1 432, L 630, P2 128, P 560. Holding months in H: T1 and T1a 1,190 per factor except T1's LT_Rev 1,136 (from 1932-01); T1b's LT_Rev 1,142 (from 1931-07). Only dates and marker flags read; no factor value written or printed. Header text recorded verbatim in the manifest; it describes the universe as NYSE, AMEX and NASDAQ stocks (the files' own wording; the pre-1962 NYSE-only point of §10 row 6 is general knowledge, unchanged), and the LT_Rev header calls its series "a momentum factor" while defining LT_Rev (prior return months −60 to −13), an apparent wording slip in the library's header, recorded, not acted on. Raw files in `data/raw/` (git-ignored); [results/data_step.md](results/data_step.md), `data_step.json`, `data_manifest.json` committed. |
