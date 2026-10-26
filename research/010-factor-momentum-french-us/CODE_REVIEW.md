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
