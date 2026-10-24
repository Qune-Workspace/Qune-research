# Independent review: Study 005

## 1. Headline

**Confirmed with findings.** The verdict "refuted in-sample" for T1 follows from the §9.5 table as written: the stationary-bootstrap 95% interval for Δ, recomputed by the reviewer with the pre-registered seed, block and resample count, is [−0.519%, +0.027%] a month, and its upper bound +0.0268% is below the smallest believable edge of 0.0833% a month, which is the first row tested. Twenty-six positive-regime months clear the twelve-month switch-off. Every number in both `summary.json` files, the metrics and monthly CSVs, the episode tables and the data checks recomputes from the committed files; the whole monthly table (schedule, trend signal, three regime variables, B0–B3, T1–T3, d_t, both windows, both cost cases) rebuilds from the raw vendor files with the reviewer's own engine to machine precision; B0, B1 and B2 reproduce Study 003's committed files as claimed; the commit chain is in the pre-registered order. The findings are four README figures off by one in their last printed digit, one sentence that names holding periods by two different conventions, and uncorrected time labels in the trial log and the note. None changes a number that decides anything, or the verdict. The 2019–2026 episode carries no decision weight and the reviewer confirms that no number from it enters a verdict row.

## 2. Independence statement

The reviewer is Tester, a separate agent session that did not write the code, the pre-registration or the study note. Date of review: 2026-10-23. The reviewer had read access to the repository at commit `6826dd3` (the finished note), its git history, Study 003's committed results, and the git-ignored raw files in `data/raw/` as present on disk (SHA-256 of all 8 files matches `results/data_manifest.json`). No network access, no vendor credentials, no secret file read; `reproduce.sh` was not run in any mode; nothing under `results/`, `src/`, `tests/` or the notes was modified. Every statistic in §4 was re-derived in `review_recompute.py` with numpy, pandas and scipy only, importing nothing from `src/` or `qune_research/`; the Newey–West t and the stationary bootstrap are hand-coded there. The reviewer wrote only this file and `review_recompute.py`.

*Dated note, 2026-10-24, after the [cold read](../../COLD_READ.md) (point 6):* "independent" in this file means a separate agent session that did not write the study, on the same underlying model as the author (Fable 5.1) and on the same machine; it recomputes the published figures from the committed files and checks the commit order, and is not a replication by an outside party. New reviews are titled "separate-session recomputation"; this file keeps its title. See [ARCHITECTURE.md](../../ARCHITECTURE.md#how-independence-is-enforced).

## 3. Tests

Run from the study folder and from `qune_research/`, as `.github/workflows/tests.yml` does (`python -m pytest -q`), with the repository's virtual environment:

| Suite | Collected | Result | Skips |
|---|---|---|---|
| Study (`tests/`) | 29 | 29 passed in 8.9 s | none on this machine; test (i) and the overlap-reuse test ran against the raw files and would skip in CI |
| Library (`qune_research/tests/`) | 107 | 107 passed in 12.3 s | none (the brief said 98; the library gained tests on 2026-10-23 before this study's code) |

`src/` and `tests/` have four commits (`0281f89`, `218519b`, `d7c1433`, `17ffd04`); the two after `APPROVED` are the disclosed T3 reading rule (`regime.py`, `checks.py`, one test) and the overlap-reuse idempotency fix (`data.py`, one test), both before the third data-check invocation and before any return. No file under `src/`, `tests/` or `results/` changed after the run it belongs to; `git diff 17ffd04 HEAD -- src tests reproduce.sh` is empty.

## 4. Recomputation

`review_recompute.py` prints 1,349 rows: 1,337 match, 4 mismatch, 8 informational. All four mismatches are README figures one unit off in their last printed digit (finding 1); no value in a `summary.json`, a CSV or a check file mismatches. The script exits 1 because of those rows, by design. Selected rows (full table: run the script):

| Claim | Published | Recomputed | Match |
|---|---|---|---|
| Holding periods IS / EP; first execution; last period end | 185 / 93; 2003-08-01, 2019-01-02; 2019-01-02, 2026-10-01 | same | yes |
| Schedule, `mom_at_signal`, ρ₆₃, ρ₂₅₂ and the T3 CPI change rebuilt from the raw files, every signal date, both windows | — | dates identical; max abs diff 1e-16, 1e-16, 1e-16, 0 | yes |
| T1, T2, T3 regime flags rebuilt from raw daily closes (63 / 252 common return days) and the CPI file (m−2, filled 2025-12 → 2025-09) | — | identical on 185 + 185 + 185 and 93 + 84 + 93 months | yes |
| Monthly net returns of B0–B3, T1–T3 rebuilt from raw data with the reviewer's engine, both windows, both cost cases | — | max abs diff ≤ 1e-16 | yes |
| T1–T3 rebuilt from B1, B0, B2's target and the flag with the (1−c)² switch cost; B3 from B1 and B0 with the drift-rebalancing cost | — | 0 | yes |
| IS B0 / B1 / B2 equal Study 003's committed in-sample B0 / B1 / T1 (monthly) | ≤ 1e-10 | 0, 0, 0 | yes |
| EP B0 / B1 / B2 equal Study 003's out-of-sample B0 / B1 / T1: monthly and all 14 numeric metric columns | exactly | 0 | yes |
| D3: σ_d from Study 003's file; MDE T1 / T2 / T3 a year; rows apply | 0.692%; 4.37% / 6.16% / 3.59%; yes | same | yes |
| IS T1 n_pos / n_neg; mean(d\|pos); mean(d\|neg); Δ | 26 / 159; −0.3247%; −0.0290%; −0.2957% | same (1e-15) | yes |
| IS T1 Newey–West Δ, se, t (one-regressor regression, Bartlett 6 lags, no small-sample factor) | −0.002957, 0.001280, −2.3102 | same (1e-12) | yes |
| IS T1 bootstrap 95% interval for Δ (seed 2005, block 12, 10,000, pairs resampled jointly, one-regime resamples dropped) | [−0.005193, +0.000268]; 0 dropped | same (1e-12) | yes |
| IS T1 half-mean intervals; T2 and T3 intervals; T2 dropped resamples | as published; 480 | same | yes |
| IS §9.5 rows T1 / T2 / T3 (reviewer's application, refuted tested first) | refuted / refuted / sign consistent | same | yes |
| IS Sharpe bootstrap intervals T1–T3 (same seed path); DSR N = 3 / N = 10; PSR; variance floor applied | as published | same (1e-10) | yes |
| IS twelve metrics for every strategy, both cost cases; switches; share in IEF; B3 weight 0.9135 = T1's IEF share | as published | same | yes |
| IS companions (B2 in bills 61.5% / 25.8%; IEF excess +0.218% / +0.302%); sub-period Δ by regime, T1–T3 | as published | same | yes |
| IS positive-episode tables T1 / T2 / T3 (dates, lengths, bill share, IEF excess) | as published | identical | yes |
| EP T1 Δ, NW t, interval; T2 (84 months from 2019-09); T3; dropped 0 / 0 / 1 | −0.2319%, −0.7167, [−0.878%, +0.439%]; … | same | yes |
| EP B3 weight frozen at the in-sample 0.9135; T1 vs B2 / B3 means and t; Sharpe intervals; DSR | as published | same | yes |
| EP terminal ρ₆₃ / ρ₂₅₂ / trend at 2026-09-30 from raw bars | 0.5525 / 0.3150 / −0.0742 | same | yes |
| D0 bar counts (3,966; 3,966; 2,029 × 3); D1 on 691 days: agreement 1.0000, mean 0.006018, max 0.019028 on 2018-01-17 | as published | same | yes |
| README text: 19 negative-regime bill months, d +16.9; five periods executed Jan–May 2022 +9.7; Feb–Mar 2022 signal months +9.9; calendar 2022 by execution month −13.7 / +1.4 / −7.6; 19 IEF-against-B2 months as listed; 16 of 26 positive months in 2004–2006; episode details | as published | same | yes (see finding 2 on naming) |
| README tables and text, both windows (about 330 typed values at README rounding) | — | 4 off by one last digit | NO (finding 1) |

## 5. Commit chain

Committer times from `git log --format=%cI` (all 2026-10-23, London, +0100); run times from file modification times under `results/` and `downloaded_at_utc` / `reused_at_utc` in the manifest, converted to London; `provenance.git_commit` in both summaries.

| Step | Commit | Time | Governs | Precedes the governed result |
|---|---|---|---|---|
| Question note (step 0) | `b9ad02e` | 08:21:56 | everything | yes |
| Pre-registration, trial log (step 1); citations file | `60f211e` `5809bc9` | 09:26:07, 09:26:50 | everything | yes: first fetch 11:21:40 |
| Code and tests, first part (step 2) | `0281f89` | 10:25:44 | --check | yes |
| Code complete, `reproduce.sh`, `APPROVED` (step 2) | `218519b` | 11:20:57 | every run | yes |
| Fetch 1 logged → fetched → outcome; fetch 2 logged → fetched → outcome (step 3) | `80a2a2f` `1fc0178` `3f20db5` | 11:21:29 → 11:21:40 → 11:21:54 → 11:21:59 → 11:22:17 | --check | yes, each row before its fetch |
| §16 T3 reading rule after the first --check stop | `d7c1433` | 11:24:17 | second invocation | yes: reuse stamps 11:22:24–31 belong to the first invocation |
| `data.py` idempotency fix after the second stop | `17ffd04` | 11:25:33 | third invocation | yes: d0 11:25:41, d1 11:25:44, d3 11:25:48 |
| Data checks committed, §16 D3 entry (step 4) | `85381f2` | 11:26:45 | --insample | yes |
| Run rows T1–T3 and the in-sample run logged (step 5) | `840cdbd` | 11:27:18 | --insample | yes: results written 11:27:26–27; provenance commit = `840cdbd` |
| In-sample outputs (step 6) | `e60ab05` | 11:27:47 | — | after the run; `results/insample/` has exactly this one commit |
| In-sample note (step 7) | `24086b3` | 11:29:54 | --episode | yes |
| Episode logged (step 8) | `7f01c30` | 12:15:48 | --episode | yes: results written 12:16:02–03; provenance commit = `7f01c30` |
| Episode outputs (step 8) | `94c93a3` | 12:16:16 | — | after the run; `results/episode/` has exactly this one commit |
| Finished note, root README (step 9) | `6826dd3` | 12:21:30 | — | — |

`PREREGISTRATION.md` differs from `60f211e` only by 27 appended §16 lines (no line removed). The README diff `24086b3`→`6826dd3` removes only the "when done", "not yet run" and "not yet started" placeholders and the old reproduce comment; no in-sample number changes. Limits: one machine clock, unsigned commits; git cannot show whether an uncommitted run happened before a committed one.

## 6. Criteria and verdict

Applied by the reviewer from the recomputed numbers, exactly as §9.5 states. Gate: n_pos = 26 ≥ 12, rows apply. T1: U = +0.000268 < 0.000833 → **refuted in-sample**; the other rows are not reached (precedence refuted > inconclusive > sign consistent, and the refuted condition is tested first in the reviewer's code as in the study's). Both half-means are negative, so the sign-consistent row could not have applied either. T2 (descriptive): U = −0.001082 → refuted. T3 (descriptive): U = +0.003017 ≥ 0.000833; Δ = +0.001011 > 0, mean(d|pos) = +0.000070 > 0, mean(d|neg) = −0.000941 < 0 → sign consistent, forward record decides. Stress costs change no row. `row_9_5_T1`, `rows_9_5`, the README table and the trial log all agree. The episode summary carries `decision_weight: false` and the note "no row applies"; the README gives it no row. The clause of §9.5 for T1 sign consistent with T2 refuted does not arise.

## 7. Disclosures

- The 2019–2026 window generated the hypothesis and carries no decision weight: §2.4, §8.2, the README's second paragraph and the episode section heading; the hypothesis family's claim on the window is stated in §8.2 and the README.
- No "supported" row from history; MDE 4.37% a year at the actual counts written in §16 before any return: §9.5, §9.6, README first paragraph and power statement.
- The two data-check stops (missing October 2025 CPI → T3 reading rule; the overlap-reuse fault), D0 and D1 identical across the three invocations: §16 (two entries), `trials.md` (four rows), README step 4.
- B3's weight frozen at T1's in-sample IEF share 0.914 in the episode: §9.1, §5.3.5 (vi), both summaries, README.
- T2's 480 dropped resamples, T3's one in the episode: README, `summary.json`.
- First-draft corrections: stated in the commit messages of `24086b3` and `6826dd3` only; the README and trial log do not mention them (note 6).
- "What did not work", the precedence reasoning ("refuted rather than inconclusive"), the one-vendor-per-window limitation with D1's answer: present.

## 8. Findings, ranked

**Must fix:** none.

**Should fix**

1. Four README figures are one unit off in their last printed digit; none is a criterion input. "Stress costs move Δ by at most 0.007% a month (T2)": the largest shift is 0.0065% (0.006). T1's negative-regime half-mean interval "[−0.12%, +0.07%]": the lower bound is −0.1147% (−0.11). Episode "d summed to +2.8 points over them": over the 38 positive months d sums to +2.75 (2.7); +2.79 is the sum over the 36 positive months in which B2 held bills, so either change the figure or name the 36 months. Episode cumulative "B1 +3.6%": +3.55% (3.5). Round once from the stored value.
2. One episode sentence names holding periods by two conventions. "+9.7 points fell in the five holding periods January to May 2022" is the sum over the periods *executed* in January to May 2022 (signal months 2021-12 to 2022-04; +9.67), the same convention as the calendar-2022 figures (−13.7 / +1.4 / −7.6, periods executed in 2022). "February and March 2022 alone +9.9" is the sum over the *signal* months 2022-02 and 2022-03 (periods executed in March and April; +9.94). By signal months, January to May 2022 sum to +7.7; by execution months, February and March sum to +4.8. Say which months are meant (the file's `month` column is the signal month).
3. Time labels entered as estimates and not corrected: `trials.md` "Code, first part … 10:5x London" (commit 10:25:44); "`reproduce.sh --episode` logged … 12:2x London" (commit 12:15:48); README step 7 "2026-10-23, 12:xx" left as a placeholder in the published note (commit 12:21:30). Append a dated correction; the order of events is unaffected (§5).

**Notes**

4. The episode `summary.json` carries `rows_9_5` with the string "inconclusive, forward record decides" for T1–T3 beside the `rows_9_5_note` that no row applies. The README does not quote them; a reader of the file alone could. Writing `null` there, or omitting the key in the episode, would remove the ambiguity.
5. The episode summary's `subperiods_d_by_regime` block is all zeros and NaN because the three sub-periods are in-sample dates; harmless, but noise in the file.
6. The first-draft corrections (three in-sample claims, two episode claims) live only in commit messages; the programme's "zero corrections" rule in §2.5 would be better served by one line in `trials.md`.
7. The T3 "sign consistent" row rests on a positive-regime mean of +0.007% a month (+0.00007), which is positive by 7e-5 on 43 months; the row is applied as written and the README says the edge is a third of the detectable size. The forward table (§11.4) has no such sensitivity for T1 because it requires t ≥ 2.0.
8. `trials.md` run rows give "85381f2 (code as of the data-check commit)" as the code commit; the code last changed in `17ffd04` and HEAD at the run was `840cdbd`, which the summaries record. Consistent, but three identifiers for one tree.
9. The in-sample first period (2003-07 signal) charges T1 and B2 the BIL→IEF purchase cost while B1 starts in IEF for free, so d and T1−B1 are −0.04% there by construction (Study 003's convention, inherited).

## 9. Not checked (and why)

- D0 coverage against the rule-based NYSE calendar: bar counts in the windows were matched (3,966 and 2,029), the day-by-day comparison with the calendar was not re-derived.
- The library's own correctness beyond what this study's outputs exercise; the `--forward` mode (refuses until step 11); the root README's at-a-glance rows and the build log; literature citations; the inherited cash-leg check.
- Whether the in-sample and episode runs were executed once: git shows each output committed once, in order, with matching provenance commits and file times inside the logged-to-committed interval; it cannot show the absence of an uncommitted earlier run.
- Charts: none exist yet (§9.7 says they follow from the committed files).

## 10. How to rerun the reviewer's checks

From the study folder, with the raw files present in `data/raw/`:

```
../../.venv/bin/python review_recompute.py && ../../.venv/bin/python -m pytest -q
```

The script takes under ten seconds, prints the 1,349-row comparison table, lists the mismatches and exits 1 while finding 1 stands; without the raw files it reports the raw rows as not checked and still recomputes everything from the committed files.
