# Study 011: separate-session code review, before `APPROVED`

*2026-10-26, 15:3x–15:4xZ by the clock. Reviewer: a separate Opus 5.5 session, isolated, read-only in the repository (scratch scripts outside it), briefed to check `src/rule.py`, `src/stats011.py`, `src/data.py`, `src/history.py`, `programme_count.py`, `reproduce.sh`, `data_step.py` and the tests against PREREGISTRATION.md §5–§9 and §14, and told not to open the real industry files or run the history. It read no real industry value and changed nothing. Summary below is Qune's; every must-fix and should-fix was taken in the commit that adds this file. `APPROVED` is not yet written.*

## Verdict: pass with fixes

## Passed (reviewer's own code on synthetic data)

- §6.1 formation (no skipped month; a missing value makes an industry ineligible for exactly the next F rankings), the sort key (−round(R, 10), column index), W/L, n.
- §6.2 cohorts and timing: a brute-force version matched `run` to 1e-12 on d_gross, turnover, d_base and d_stress for M1, M1a and M1b, with planted missing values and ties; a shock in month m first moves d in m + 1; first holding months 1927-06 and 1927-12; no off-by-one.
- §6.3 costs: netted weights, Σ|Δw| from zero weights at entry, straight through the 1963–1995 gap (no re-entry in 1995-08), 0.10 / 0.50 in percent units, empty-leg cohorts keep their weights.
- §6.5 and the loader: only the value-weighted monthly section is read; markers become NaN; a synthetic zip round-tripped exactly.
- §9.3: a hand loop of the two-stretch Newey–West matched `newey_west_stretches` to 2e-16; on one stretch it equals statsmodels; other rows use the ordinary estimator.
- §9.4–§9.5: an independent DSR at N = 3 matched exactly; C1–C4, window slices (433, 373, 385; full 1,191 / 1,185), the window row, precedence and the return-unit label checked.
- Gates: with the loader stubbed, every refusal (APPROVED, existing `results/history`, `.history_tmp`, programme count, `trials.md` row) fired with zero load calls; outputs are written to a temporary folder and renamed.

## Must-fix (fixed)

1. `src/history.py`: the `.history_tmp` marker was created only after the data were read and computed, so a crash in between left no marker and a re-run would have been allowed, against the run-once rule (Study 010's code has the same gap; it ran once without a crash, so no re-run happened there). Fix: the folder and a `STARTED` file are written before the first value is read; a test makes `load_industries` raise and checks that the marker stays and the next run refuses.

## Should-fix (taken)

2. The legs table (§9.6) gains an O row, with the two-stretch Newey–West.
3. Boundary near-ties are counted over every held ranking month (the first five cohorts of each trial were missed); `cohorts.json` carries the tie count per ranking month.
4. Tests: d = Σ wᵢ rᵢ now checked month by month on 17 industries; an empty-leg month keeps turnover at zero; a misleading test comment corrected.
5. The data step's eligibility summary is copied into `summary.json`.

## Notes (recorded, no change)

- Choices the pre-registration leaves open, fixed here before any run: the twelve worst months are taken from base-cost d over the full history; `turnover_per_year` is over the full history; the episodes report sum and mean (monthly values are in `monthly.csv`); DSR at N = 11 and at the programme counts uses the three-trial variance, as in Study 010.
- The code does not check that the programme count is fresh; the re-count is run and committed immediately before the history run (§14 step 5), as a process step.

# Second part: `forward011.py` part 1 (§11 cohort records), 2026-10-26

Reviewer: a separate Opus 5.5 session, isolated, read-only in the repository (scratch copies under /tmp), 317 s by the harness, on commit `17940d2`; 25 mutations of the module run against the tests; the first record run on the real snapshot into a scratch path only. Brief: §11, Study 010's `forward010.py` part 1 and its review fixes as the template.

## Verdict: FAIL (1 must-fix), then fixed before any record was written

**Must-fix 1 (fixed).** The release pattern `created using the (\d{6}) CRSP database` did not match the 30-industry file's own header, "This file was created **by CMPT_IND_RETS** using the 202608 CRSP database." (recorded by the data step, `results/data_step.md`), so `record` would have stopped before writing the first forward month. The synthetic tests gave both files the 17-industry wording, so they missed it. Fixed: `created (?:by \S+ )?using the (\d{6}) CRSP database`; the test fixture now writes each file's real wording.

**Should-fix 2 (taken).** 11 of the 25 mutants survived (files ending after t − 1, tie order, non-atomic write, fsync, lock, rounded formation returns, NaN industries kept, missing download time, wrong manifest hash, wrong `release_last_month`, ties forced to 0). Added tests: a crash inside the write leaves the file byte-identical with no temp file; a 17-industry file reaching 2026-09 under release 202608 is refused; every formation return equals the engine's exactly and a NaN industry is left out; a boundary tie at the n-th place is broken by column order and counted; the metadata columns (release month, manifest hash, download and record times); a manifest without a download time is refused; agreement with `cohort_table` over 3 seeds × 3 months, with t − 13 changing no trial and t − 7 changing only M1b. The lock and fsync mutants remain uncaught by unit tests; the reviewer ran six concurrent writers by hand (one write, five refusals).

**Should-fix 3 (taken).** `.gitignore` now ignores Study 011's `paper-log/*.lock`.

**Note 5 (taken).** A month after the first is now refused until t − 1 is recorded for every trial, because §11 takes the five earlier cohorts held in t from the earlier records; tested.

**Notes 4 and 6 (recorded for part 2).** Each row carries everything scoring needs (ordered W and L, every eligible industry's formation return at full precision in file order, release, both hashes, both download times); the first five forward months' earlier cohorts come from the committed `results/history/cohorts.json`. Part 2 should check that a later release's industry names equal the snapshot's. The §16 code decisions are added with this part (below).

**Real-snapshot check.** With the fix, the reviewer's scratch run and the committed record agree: the 2026-09 cohorts from release 202608 equal the history run's 2026-08 cohorts in `results/history/cohorts.json` for all three trials (M1: winners Machn, Oil, Finan; losers Steel, Cnstr, Clths; no boundary tie). Suite: 27 forward tests, all passing.

# Third part: `forward011.py` part 2 (fetch, lateness, interim, scoring), 2026-10-26

Reviewer: a separate Opus 5.5 session, isolated, read-only in the repository (own clone and scratch files under /tmp), 20:17:23Z–20:52:00Z by its `date -u`, on commit `90d3b30` (HEAD `fbce344`), synthetic data only, no network. Brief: §11, Study 010's part 2 and its review as the template, at least 10 mutations. Brief and report summary also in the workspace's review briefs. The report is summarised below; nothing is left out that changes a finding.

## Verdict: PASS WITH FIXES (no must-fix)

Checked and correct by the reviewer's own runs: the 63-test study suite passes; the real 202608 zips pass the release-header check (including the 30-industry "created by CMPT_IND_RETS using …") and the industry-name check; the committed 2026-09 rows have one commit (17:35:18Z), are not late and equal the history's 2026-08 cohorts; forward weights built from `cohorts.json` reproduce the history's turnover for 2026-07 and 2026-08 in all three trials; ordinary Newey–West with six lags for the single forward stretch; costs 0.10 / 0.50 in percent units; the first month's trade from the history's 2026-08 weights; C2 and C4 decide, C1 and C3 reported, the low-power label on every row; the scoring release is the first archived one containing 2031-08; late rows counted and listed. End to end in a scratch git repository: a synthetic snapshot 202608, 59 releases fetched through a stubbed `fetch`, 60 months recorded with one commit each (two committed late on purpose), release 203108 fetched, then `row_commit_times` and `score` with the default own-release loader: all 180 rows re-checked; d at base and stress equal to `rule.run` on the scoring release (largest difference 0.0); late months exactly the two planted; the vintage row found the one revised cell; strict JSON. Probes: an uncommitted edit and a committed rewrite stop scoring; missing raw files are listed as not re-checked; a committed then deleted `score.json` stops a rescore; a git failure stops scoring; a simulated crash between moving the files and writing the json is recovered by the next fetch; a shallow clone is refused. Every Study 010 part-2 fix is carried over.

| # | Level | Finding | Response |
|---|---|---|---|
| 1 | should-fix | `results/history/cohorts.json` was read from the working tree with no check, although it sets the first five forward months' earlier cohorts and the 2026-09 starting weights; swapping W and L of M1's 2026-07 cohort moved M1's mean d and scoring still ran. | Taken: `check_history_cohorts` recomputes the six ranking months used (2026-02 to 2026-07) for each trial from the snapshot; `score` stops on any difference. Tests: unit test, and the swapped cohort now stops `score`. |
| 2 | should-fix | Tests too weak: no verdict "meets"/"does not meet" test, DSR at N = 3 unasserted, `late_months` unasserted, vintage test without a revision, `row_commit_times`/shallow clone/`_ever_committed`/`own_release_loader` never run, fetch crash recovery untested, `check_rows` release/SHA, formation-return and tie mismatches untested. 12 of 17 run mutations survived. | Taken: `tests/test_forward011_review.py` (11 tests: verdict rows, scoring release, release/SHA, formation-return and tie mismatches, duplicate industries, history cohorts, own-release loader incl. missing raw files, git-backed first commit and rewrite, shallow clone, `_ever_committed` incl. git failure, crash between moving the files and writing the json plus leftover files); the end-to-end test now plants one late month, one revised history cell and asserts DSR at N = 3 against the library. |
| 3 | should-fix | §16 said nothing on part 2; `paper-log/README.md` still said part 2 was not written. | Taken: §16 dated addition items 5–11; README updated. |
| 4 | note | The vintage row recomputed only forward rows, not the history cohorts that are scored too. | Taken: the vintage row recomputes the 18 history cohorts from the scoring release. |
| 5 | note | `interim`: `months_to_scoring` negative after 60 months; interim.json written without `allow_nan=False`. | Taken: floored at 0; `_clean` + `allow_nan=False`. |
| 6 | note | `weights` did not refuse duplicates within a leg or overlap between W and L. | Taken, with a test. |

## Mutations after the fixes (Qune, scratch copies under /tmp, the new fast tests only)

Re-run the reviewer's surviving mutations that the new tests target, plus three on the new code: release/SHA check removed (M03), formation-return comparison removed (M04), last archived release instead of the first (M05), git failure let through (M06), latest commit instead of earliest (M07), verdict on C2 or C4 (M08), own release t instead of t − 1 (M12), json renamed before the files are moved (M13), leftover files not cleared (M14), shallow-clone check removed (M16), tie comparison removed (M18), history-cohorts comparison disabled (M24), distinct-industry check removed (M25): **13 of 13 killed**. A baseline copy with no change passed. The reviewer's M09 (DSR at N = 11), M10 (late months inverted) and M11 (vintage against itself), run against the strengthened end-to-end test: **3 of 3 killed** (DSR, late-month and vintage-cell assertions respectively). Not re-run by a separate session; the fixes add checks and tests and change no computed figure.
