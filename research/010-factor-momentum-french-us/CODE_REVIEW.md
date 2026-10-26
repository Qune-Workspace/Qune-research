# Study 010: separate-session code review (PREREGISTRATION.md §14 step 3)

The reviewer was a separate Opus 5.5 session. It ran isolated and read-only, in a fresh clone that held no raw data, on synthetic data only. It opened no library file and wrote nothing to the repository. Its report is below, shortened only by dropping the paths of its scratch files. My response to each item follows the report, and the re-check of the fixes comes after that.

## Report (first review, HEAD `1839e5a`, 2026-10-26 09:29:06Z–09:33:35Z by the reviewer's `date -u`)

**Verdict: FAIL (must-fix present).** One must-fix, and it is small. Once it is fixed, with a test added, the code is fit for `APPROVED`.

**Must-fix**

1. `src/history.py` `verdict`: the return-unit label on a companion row depended on T1's verdict. §9.5 says: "any row that is not 'not supported' adds '(Sharpe units; the 2%-a-year bar not met)'". The reviewer reproduced the error: with T1 "not supported" and T1a meeting C1–C4 at an MDE of 2.5% a year, T1a's row came out without the label. Fix: apply the suffix to each row on that row's own reading, and add a test.

**Should-fix**

1. No test ran a full successful `main()`, and outputs were written straight into the final folder. Any error while writing would leave a half-written `results/history/` and use up the one-time run. Fix: write to a temp folder, then rename it, and add the test.
2. The program only checked that `programme_count.json` existed, and it read the file after the factor values had been loaded. A bad count would stop the run after the data had been read. Fix: validate the count before loading any data, and require the history-run row in `trials.md`.
3. The per-factor contribution was gross of costs, but its key did not say so. Fix: add `_gross` to the key, and add a net version that sums to mean d.
4. There was no trial-level (pooled) hit rate, which §9.3 (a) defines. Fix: add one.
5. The `kurtosis` key held non-excess kurtosis, while Study 001 §9.3 item 11 names excess kurtosis. Fix: add `_non_excess` to the key and report excess kurtosis beside it.
6. The engine did not check that f_k,t exists in a held month (§6.5). This is defensive only, since the snapshot has no gaps. Fix: raise when it is missing.
7. The paper-comparison t was Newey–West, and the paper's t (7.04, 7.60) may not be. Fix: report the iid t beside the NW t.

**Checked and found correct (reviewer's own checks)**

- 21 tests pass, and no test can use up a one-time step on the real repository.
- An independent engine of the reviewer's own was run against a full synthetic `--history` run. For all three trials at both cost levels the largest difference was 1.8e-15, and the h̄ values matched.
- Costs checked by hand, including LT_Rev's entry in 1932-01: c·2/4, and 0.15 with one other flip in the same month.
- The Newey–West t of d checked by hand (Bartlett kernel, 6 lags) for all three trials: matches to 1e-14.
- DSR at N = 3 checked by hand: 0.511580408721912 on the reviewer's synthetic series, equal to the code's value.
- The window row's mean of d over P, with h̄ frozen from H.
- The path where B3 is identically zero.
- C1–C4, including the direction of each inequality and the thresholds; the verdict precedence; the bar of the return-unit label.
- Every §9.6 row is in `summary.json`; the CSVs round-trip exactly; the seed convention.
- The loader's hash check and its handling of missing-value markers.
- The refusals in `reproduce.sh`.
- The checks `data_step.py` makes and the counts it recorded.

## Response (fixes in `55aa9e3`, before `APPROVED`)

| Item | Done |
|---|---|
| M1 | `verdict()` labels each row on its own reading and reports `return_unit_bar_not_met`. The reviewer's failing case is now a test. |
| S1 | Outputs are written to `results/.history_tmp/`, which is then renamed to `results/history/`. A leftover temp folder is refused and needs a dated §16 amendment. A test runs `main()` in full on synthetic zips, then checks that a second call is refused. |
| S2 | `check_programme_count` requires integers ≥ 2 and a method, and runs before any value is read. `trials.md` must contain the row "History run (§14 step 6), logged before it runs". There are tests for each refusal. |
| S3 | The per-factor rows now carry `contribution_to_mean_d_gross_…` and `…_net_…`, each with its NW t. A test checks that the net contributions sum to mean d. |
| S4 | `hit_rate_pooled` is reported per trial and per cost case. |
| S5 | `kurtosis_non_excess` and `excess_kurtosis` are both reported. |
| S6 | `rule.run` raises on a missing factor return in a held month. A test sets f to NaN in H's last month, where the formation is still defined. |
| S7 | `diff_row` reports `iid_t` beside `nw_t`, so the note can compare like with like or say it cannot. |

Tests: 27, all passing.

## Re-check of the fixes (HEAD `55aa9e3`, 2026-10-26 09:37:43Z–09:38:39Z by the reviewer's `date -u`; same reviewer session, fresh clone, synthetic data only)

**Re-check verdict: PASS.** 27 tests pass. All eight items are confirmed (M1, S1–S7), and no new must-fix was found.

The reviewer also re-ran its own checks:

- **Independent engine:** re-run on the new monthly CSVs. Every column is within 1.8e-15 for all three trials at both cost levels.
- **Hand-checks:** the hand-computed NW t and the DSR at N = 3 still match.
- **Net contributions:** they sum to mean d within 4.4e-16.
- **One-time run:** a full synthetic `reproduce.sh --history` returned rc 0 with the four output files and no leftover `.history_tmp`, and a second call returned rc 1.

Two notes, neither needing action:

1. The history-run row in `trials.md` must begin exactly `| History run (§14 step 6), logged before it runs`. If the wording differs, the run is refused, so the mistake is safe.
2. `reproduce.sh` itself does not check for a leftover temp folder or for the `trials.md` row. `src/history.py` does both, before any value is read.

---

# Forward record, part 1: separate-session code review (PREREGISTRATION.md §11, §14 step 10)

Code under review: `src/forward010.py` (monthly position records for T1, T1a and T1b; shadow only) and `tests/test_forward010.py`, uncommitted at review time on top of `2196a1f`. Scoring after 60 months, the fetch of later releases and the vintage row are part 2 and were out of scope. The reviewer was a separate Opus 5.5 session, isolated and read-only, on synthetic data only (scratch in /tmp/review010fw/); it did not run `record` against the snapshot and created no `paper-log/`. Its two reports are below unedited; my response sits between them.

## Report (first review, 2026-10-26, about 11:29–11:33Z; 213 s by the harness)

**FAIL**: 1 must-fix, 4 should-fix, 5 notes

The signal itself is correct. Positions match `rule.run` and nothing at or after month t can affect h_t. The failure is that `record` accepts any release containing t − 1, while §11 requires the *first* such release. An operator holding a later release can work out both candidate positions after seeing month t's return, then record whichever did better. The fix is small (row 1). A first record for 2026-09 from the default snapshot (release 202608, ending 2026-08) would be correct, but the code should be fixed and re-reviewed before any record is written.

| # | Severity | Finding | Exact fix |
|---|---|---|---|
| 1 | must-fix | §11 says h_k,t is computed "from the first release that contains month t − 1". `record()` accepts any release whose files reach t − 1, including one that already contains month t, and only labels it `late=True`. The library revises history between releases, so h_t can differ by release. `positions_for` is a pure function, so an operator holding release A (ends t − 1) and release B (contains t) can work out both candidate positions without writing anything, see month t's return in B, and record the better one. Reproduced on synthetic data: a revised t − 1 value flipped SMB's h in T1, T1a and T1b from +1 to −1, SMB's month-t return (3.19) was visible in B, and `record` accepted B. A record from the first release, made after B appeared, gets `late=False`, so the choice also leaves no trace in the file. | In `record()`, after loading: `want = (t - 1).strftime("%Y%m")`; `lasts = {k: f[k].last_valid_index() for k in ("SMB", "HML", "ST_Rev", "LT_Rev")}`; refuse with `SystemExit` unless `release_of(manifest_path) == want` and every value in `lasts` equals `t - 1`. The message should say that §11 requires the first release containing t − 1, and that if it was not archived a dated §16 amendment is needed. Keep the `late` column but always write False, with a comment that lateness comes from commit time at scoring. In `test_record_writes_once_and_labels_late`, replace the 202610 case with one that asserts refusal (202610 for month 2026-10) and one that asserts acceptance (202609 ending 2026-09). |
| 2 | should-fix | `late` and `release_last_month` use the *minimum* last month across the four factors. A release whose 3-factor file already contains month t but whose reversal files end at t − 1 is written with `late=False`, even though SMB and HML for month t are visible. Reproduced: late labels `{False}`, `release_last_month` 2026-08. | Fixed by row 1, which requires every file to end exactly at t − 1. If row 1 is not adopted, use `max(...) >= t` for `late`. |
| 3 | should-fix | The append reads the old file as text and writes new rows straight after it, with no checks. If the existing file has been hand-edited and lacks a final newline, the first new row merges into the last old row. Reproduced: 19 rows instead of 20, with a field reading `False2026-10`. The header is never checked against `COLUMNS` either. | Before writing: if `body` is not empty, require `body.endswith("\n")` and require its first line to equal `",".join(COLUMNS)`; otherwise refuse with `SystemExit("STOP: positions.csv is malformed; restore it from git")`. |
| 4 | should-fix | The temp-file rename is atomic against a Python crash (reproduced: the old file was byte-identical afterwards). But the temp file is not flushed to disk with `os.fsync` before the rename, so a power loss could leave an empty `positions.csv`. There is also no lock. Two runs at the same time both pass the duplicate check, and the second rename drops the first run's rows. | Inside the `with` block, after `writerows`, call `fh.flush(); os.fsync(fh.fileno())`. After `tmp.replace(out)`, fsync the parent directory. Wrap everything from the `existing()` check to the rename in `fcntl.flock(open(out.with_suffix(".lock"), "w"), fcntl.LOCK_EX)`. |
| 5 | should-fix | The tests do not cover several of the required paths. Refusal when one factor's file lacks t − 1 is tested only through `positions_for`, not `record`. Mismatched release lines are tested only through `release_of`. There is no crash or atomicity test, no partial-release test, no malformed-file test, no test of a duplicate from a different release, and no test that a T1b position ignores t − 7. Equivalence with `rule.run` is checked for one month and one seed. | Add tests for each of these: `record` refusing when LT_Rev ends at t − 2; `record` refusing mismatched release lines and writing no file; a duplicate from a different release refused; a simulated crash in `writerows` leaving the file byte-identical; the row 1 refusals; the row 3 refusal; T1b's h unchanged when t − 7 is perturbed; equivalence with `rule.run` over several seeds and months. |
| 6 | note | The rule against replacing a record is enforced only by `positions.csv` being present. If an uncommitted file is deleted, the month can be recorded again. Once row 1 is in place, a second record is identical apart from `recorded_at_utc`, so nothing can be chosen this way. | Commit and push `paper-log/` straight after each `record`. The commit time is the evidence §11 relies on. |
| 7 | note | A crash leaves `positions.tmp` behind (reproduced). It is harmless, because the next run overwrites it. | Optionally delete it in a `finally` block. |
| 8 | note | Each row carries the zips' SHA-256 values but not the manifest's `downloaded_at_utc` or the manifest's own hash. Part 2 will need both to show which release was the first and when it appeared. | Add `manifest_sha256` and `downloaded_at_utc` columns now, before the first row, so the CSV format never has to change. |
| 9 | note | `FIRST_FORWARD_MONTH = "2026-09"` is hard-coded. It agrees with `trials.md` (H = 1927-07 to 2026-08) and with the snapshot's last month. | None. |
| 10 | note | `freeze_hbar` compares only the h̄ values on later runs, not `source_sha256`. That is enough for §11. | None. |

**Check by check, with evidence**

1. **Same positions as `rule.run`.** Matched in 144 of 144 trial-months: six seeds, months from 2026-09 to 2030-12, all three trials. The timing is t − L to t − 1 with no skipped month. A tie takes −1 (the existing test covers this). T1b's 6-month window is confirmed: perturbing t − 7 left T1b unchanged, and perturbing t − 13 left every trial unchanged. Every entry month falls before 2026-09, so all ten trial-factor rows are written; the code that skips factors not yet entered can never run.
2. **No look-ahead.** I replaced every value from 2026-09 to 2027-06 with random noise, and h for 2026-09 did not change. The frame is cut at t − 1 before the signal is computed.
3. **Refusals, all reproduced:** month inside H: refused; LT_Rev alone ending at t − 2: refused through `record`, no file written; duplicate from a different release: refused; month given as "2026-9": normalised and refused as a duplicate; mismatched release line: refused, no file written; missing release line: refused; a zip that does not match the manifest hash: refused; h̄ factor set not matching the trial: refused; h̄ value changed: refused (existing test). The gap is the release choice in row 1.
4. **Atomic append and CSV format.** A Python crash left the file intact and a retry gave 20 rows with the correct header. The remaining gaps are rows 3 and 4.
5. **Tests.** The 8 tests in `test_forward010.py` pass, and the full suite passes (39). For the gaps, see row 5.
6. **Choosing a record after seeing the return.** Row 1. Once it is fixed, the record is fully determined by month t, so neither the timing of the record nor its re-creation can choose anything.

**What I ran and observed:** `pytest -q tests/test_forward010.py` gave 8 passed; the whole `tests/` folder 39 passed. Scratch scripts in /tmp/review010fw/ covered checks 1 to 4 on synthetic zips built with the tests' own `write_release` and reproduced row 1. h̄ frozen from the real `results/history/summary.json` into a scratch file matches the history run (T1: SMB 0.0588, HML 0.2235, ST_Rev 0.5109, LT_Rev 0.1197). The real manifest's header lines (not the zips) all name the 202608 CRSP release and the regex parses each of them. `record` was not run against `data/raw/`; no `paper-log/` was created; `git status` showed only the two untracked files under review before and after every run.

## Response (Qune, before any record was written)

Bad news first: my first version treated a later release as merely "late", which left an operator free to compute h_t from two releases after seeing month t's return and record the better one. That contradicts §11's own words ("the first release that contains month t − 1"). Fixed as the reviewer specified, and every should-fix and note 6–8 taken:
1. `record()` refuses unless the release is named t − 1 (YYYYMM) and all four factors end exactly at t − 1; the check on the release name runs before any factor value is loaded. `late` is always written False and is set at scoring from the commit time.
2. Fixed by 1.
3. `existing_body()` refuses a file without a final newline or with a header other than `COLUMNS`.
4. fsync of the temp file and of the folder; `fcntl.flock` on `paper-log/positions.lock` (git-ignored) around the duplicate check and the rename; the temp file is removed in `finally`.
5. Tests added for each listed path.
6. Practice: `paper-log/` is committed and pushed straight after each record.
8. Columns `manifest_sha256` and `downloaded_at_utc` added before the first row.

Out of the review's scope, in the same commit: `reproduce.sh --forward` now names the record command and still refuses scoring.

## Re-check (same reviewer session, 2026-10-26 about 11:34–11:35Z; 76 s by the harness)

**PASS**: the must-fix and all four should-fixes are fixed, and the notes I raised have been taken up. Two new notes, neither blocking.

With this, the code can write Study 010's first real record, the 2026-09 positions from release 202608. All 12 tests in `test_forward010.py` pass, and the full suite passes (43).

| # | Status | Evidence |
|---|---|---|
| 1 (must-fix, release choice) | Fixed | My earlier reproduction was a later release (202609) offered for month 2026-09. It is now refused with "release 202609 is not 202608; §11 requires the first release that contains 2026-08". A release labelled 202608 whose files reach 2026-09 is refused because every file must end at 2026-08. The correct first release is accepted: 10 rows, all with `late` False. The release name is checked before any factor value is loaded. |
| 2 (should-fix, partial release) | Fixed by 1 | A release where only LT_Rev ends at t − 2 is refused. A release where the 3-factor file already contains month t is refused, both in my script and in the new test. |
| 3 (should-fix, malformed file) | Fixed | A file without a final newline is refused with "malformed; restore it from git", and so is a file with a wrong header. A duplicate month is still refused. The file was byte-identical after all three refusals. |
| 4 (should-fix, fsync and lock) | Fixed | A crash part-way through writing (one row written, then an exception) left the file byte-identical and no `.tmp` behind. In 4 runs of the same month at once, exactly one wrote and three were refused; the file ended with 20 rows and the earlier rows were intact. The temp file and the folder are fsynced before and after the rename. `paper-log/*.lock` is git-ignored (`.gitignore` line 19). |
| 5 (should-fix, tests) | Fixed | The new tests cover every case listed: later release refused, partial release refused both ways, malformed file refused, crash leaves the file byte-identical with no `.tmp`, T1b ignores t − 7, the next month appends with earlier rows byte-identical, and equivalence with `rule.run` over 3 seeds × 2 months. |
| 6, 7 (notes) | Taken | Temp file removed in a `finally` block, confirmed above. Committing and pushing `paper-log/` after each record is a working practice, so I cannot check it in code. |
| 8 (note, new columns) | Done | `manifest_sha256` and `downloaded_at_utc` are present and the header equals `COLUMNS`. |

**New findings (notes, not blocking)**

| # | Severity | Finding | Exact fix |
|---|---|---|---|
| N1 | note | `release_of` takes the release from the manifest's copied header lines, not from the zips themselves. Reproduced: zips whose own header says 202610 were accepted against a manifest that says 202608. A real later release would still be refused, because its files end after t − 1. Getting past that would mean editing the zips as well, which changes the SHA-256 values recorded in the row. So the risk is deliberate forgery only. | In `record()`, also read each zip's text with `data.read_zip` and require its own `created using the YYYYMM CRSP database` line to equal `want`. |
| N2 | note | If a manifest has no `downloaded_at_utc`, `downloaded_at()` silently writes an empty value (seen with the tests' synthetic manifests). The real manifest has the field. | Refuse when any file's `downloaded_at_utc` is missing, or accept that it is empty only in tests. |

**Outside this review:** `git status` also shows changes to `.gitignore`, `reproduce.sh` and `tests/test_programme_count.py`. Apart from the `.lock` ignore line, I did not review them.

**What I ran:** the two pytest commands above, plus a re-check script on synthetic zips in /tmp/review010fw/. I did not run `record` against `data/raw/`, no `paper-log/` was created in the repo, and nothing in the repo was modified.

## After the re-check (Qune)

Both notes taken before the first record: `record()` also reads each zip's own header line and refuses unless all three name t − 1 (N1); `downloaded_at()` refuses a manifest without a download time, and the tests' synthetic manifests now carry one (N2). One test added for both; 13 tests in `test_forward010.py`, 44 in the study, `ruff` and `mypy` clean. Not re-reviewed: both changes only add refusals. The change to `tests/test_programme_count.py` is an import-order fix that `ruff check .` flagged on the committed file; it is committed separately.

---

# Forward record, part 2 (fetch, lateness, interim, scoring): separate-session code review

The reviewer was a separate Opus 5.5 session, isolated, read-only, in its own clone at `2c5ccb9`, on synthetic data only and with no network. It ran nothing against the real `paper-log/` or `results/`. Its report is below, shortened only by dropping its scratch-file paths and by light formatting. My response follows, then the re-check.

## Report (first review, HEAD `2c5ccb9`, 2026-10-26 12:23:59Z–12:29:27Z by the reviewer's `date -u`)

**Verdict: FAIL (must-fix present).**

**Must-fix**

1. `score` / `row_commit_times` / `read_positions`: the h that gets scored is whatever is in the working tree, not the h that was committed. `row_commit_times` kept only the time of each key's first commit and threw away that commit's contents; `score` took h from the current file; nothing compared the two. Reproduced: a row committed on 2026-11-01 with h = +1 and rewritten to h = −1 in a commit dated 2031-10-01 kept the 2026-11-01 time, was scored at h = −1 and was not labelled late; an uncommitted edit behaved the same way. End to end, flipping every T1 h was accepted with `rows_late == 0` and showed only as `vintage.h_rows_differing == 85`. So a position picked after month t's return was known could be scored and labelled on time, which §11 rules out. Fix: keep the first-committed contents and refuse any difference; add a test.

**Should-fix**

1. "Scored once" rested only on `score.json` existing, and the release was a free choice: score with 203108, delete the output, score again with 203109, and mean d differs. Fix: the code picks the release itself (the first archived release named 203108 or later) and refuses a run if git has ever committed `score.json`.
2. `score` did not check rows against their own release (release = month − 1, `files_sha256` against the release's json or the snapshot's manifest, h recomputed with `positions_for`). Fix: recompute and STOP on any mismatch.
3. `fetch`: a crash between moving the files and writing `releases/<rel>.json` locked that release out for good. Fix: write the json to a temp file first, or treat files without their json as incomplete.
4. `fetch`: two runs at once shared `_incoming`, each removing it at the start. Fix: `tempfile.mkdtemp` plus an flock.
5. `score`: late rows were only counted, not listed. Fix: list them.
6. Tests weak in places: the C2/C4 test would probably pass if `score` recomputed h; no test reached a "does not meet" row; DSR at N = 3 untested beyond the field; no rewrite or uncommitted-edit test.

**Notes**

1. `%cI` is the committer's clock; push or remote time is stronger evidence. A shallow clone would date rows at the shallow boundary (refuse it); no `--follow` if the file is renamed; use the minimum time rather than the first in topological order.
2. Design (a), lateness against the desk's own first download, is acceptable: `record(t + 1)` needs release t archived, so release t is always downloaded before month t + 1 is recorded. Two gaps to disclose: refused fetches are never logged, and a desk that delays fetching can never be late.
3. `results/forward/score.lock` and `score.tmp` are not git-ignored.
4. Design (b), the first month's cost from h at H's end, matches the engine running straight through; (c) the wording is fine with the label attached; (d) the refusal rules are correct. All four need a §16 entry.
5. `json.dumps(default=float)` would write NaN into `score.json`.

**Checked and found correct (reviewer's own runs):** 54 tests pass; `forward_frame` against `rule.run` over 2026-09 to 2031-08, all three trials, base and stress, largest difference 0.0; `h_at_h_end()` on the committed monthly file; `forward_verdict` against `history.criteria` on a grid around every threshold; DSR call at N = 3; the B3-zero leg; second `score`, 59-month record, unarchived release, release ending 2031-07 and a missing LT_Rev month all stop and write nothing; UTC conversion of a `+01:00` commit; fetch refusals leave no staging; vintage row finds one changed HML month and none for SMB; interim has no t and no verdict; no part-2 test touches the real repository; part 1's `record` unchanged.

## Response (fixes in `0cac41d`)

| Item | Done |
|---|---|
| Must-fix 1 | `row_commit_times` returns, per row, the earliest commit time and the row as first committed; `score` refuses any row that differs from it or was never committed. Tests: rewrite in a later commit keeps the first contents; a rewritten or uncommitted row stops the scoring. |
| Should-fix 1 | `scoring_release()` fixes the release as the first archived one containing 2031-08 and refuses any other; `score` refuses if `score.json` exists or git has ever committed it (`git log --all`). Test added. |
| Should-fix 2 | `check_rows` reproduces every row (release name, files' SHA-256, h, formation return) from its own release (the snapshot for 2026-09, `releases/<t − 1>.json` after). Test added. |
| Should-fix 3 | The json is written to a temp file, the files moved, then the json renamed; files left without their json are cleared and fetched again (no record existed, so no download is repeated on the record). Test added. |
| Should-fix 4 | Own `mkdtemp` staging under an flock on `raw/.fetch.lock`. |
| Should-fix 5 | `late_rows` listed per trial. |
| Should-fix 6 | Tests added: T's mean rebuilt by hand from the committed h; a rule always wrong in sign gives "does not meet C2 and C4"; DSR equal to the library's at N = 3 to 1e-12. |
| Note 1 | Shallow clone refused; earliest time taken; the committer-clock caveat is in §16 with the push events as stronger evidence. |
| Note 2 | Every fetch attempt appended to `paper-log/releases/fetch_log.csv`; both gaps disclosed in §16. |
| Note 3 | Lock and temp files git-ignored. |
| Note 4 | PREREGISTRATION.md §16 dated addition (2026-10-26), items 1–6. |
| Note 5 | NaN and infinities written as null, `allow_nan=False`. |

## Re-check (same reviewer session, 2026-10-26 12:36:51Z–12:41:50Z by its `date -u`)

**Verdict: PASS.** Every fix in `0cac41d` held against the earlier probes; nothing new at must-fix. The reviewer ran the real path end to end on synthetic data: snapshot 202608 and archived releases 202609 to 203108, 60 months written by `record`, committed in a temporary git repo, then `row_commit_times` and `score` with the default own-release loader: all 600 rows (240 T1, 120 T1a, 240 T1b) reproduced from their own releases, 2026-09 from the snapshot. M1 (rewrite and uncommitted edit stop, no output), S1 (203109 refused; a committed-then-deleted `score.json` stops), S3 (forced crash between the move and the json rename: next fetch clears the leftover and keeps the release), S4, S5 and the notes confirmed. Suite 59 passed.

New should-fix: (1) the formation return was compared as an exact string, so a NumPy or pandas upgrade by 2031 could block every row: compare with a tolerance; (2) `_ever_committed` let scoring through when git failed: stop instead; (3) no repo test used the default own-release loader; (4) scoring needs all 60 sets of raw files, git-ignored and no longer served by the library: state a backup requirement. Note: a fetch that raises is not logged, and a re-fetch after a crash gets a later download time; disclose both.

## After the re-check (Qune)

All four should-fix items and the note taken: tolerance 1e-12 relative on the formation return, h exact; `_ever_committed` stops when git fails (test); a test of the default loader (snapshot for 2026-09, archive for 2026-10, `FileNotFoundError` when the raw files are gone); a missing release's raw files no longer stop the scoring for good: the month is listed in `score.json` under `months_not_rechecked_raw_files_missing` (rows still held to their first commit), and the five-year backup requirement and the two lateness gaps are in PREREGISTRATION.md §16 item 7. Study suite 61 passed; ruff clean.
