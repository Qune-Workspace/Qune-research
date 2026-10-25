# Separate-session recomputation: Study 007

## 1. Headline

**Confirmed with findings.** The verdict "inconclusive (fragile)" for T1 follows from §9.5 as written. At base costs over the 534 periods 1974-07 to 2018-12, T1's Sharpe ratio is 0.4930. It clears B1 (0.3818) by 0.0112 and B3 (0.3814, w̄ 0.60561) by 0.0116 above the 0.10 margin (C1). The Newey–West t of mean(T1 − B3) is 2.1019 (C2). The DSR at the family count 14 is 0.99755 (C3). The sign holds at stress costs, t 2.04 (C4). Companion T1b, on its own 474 periods, passes C1 by 0.0101, C3 and C4, but fails C2 at t 1.9507. So T1b is "not supported", and the companion clause turns T1's own "supported" row into "inconclusive (fragile)". The secondary rows also recompute: T2 is "supported in history; forward record pending" (t 2.1012, C1 margin 0.0110), and T3 is "not supported" (C1 and C2 fail, t 1.6002).

The following recompute from the raw files: the gate (G1 0.019% / 0.019% / 0.019% / 0.021% / 0.061% a year against 0.18%; G2 0.13140878732605116, |diff| below 1e-12) and the volatility check (σ 7.8124% against 10.18%). The carry, the three rank paths, the trend signal, both legs and every monthly return also recompute from the raw files, to 1e-13 or better. All §9.6 descriptives, the episode, about 260 typed numbers in README.md, trials.md and the pre-registration's power figures, and the five chart titles recompute. The commit chain is in the registered order.

There are four findings, none of which changes a number or the verdict: one README episode sentence that the data contradict, one estimated time label that was not corrected, a mislabelled gate split, and a DSR variance taken over this study's trials rather than the family's.

## 2. Independence statement

The reviewer is Tester, a separate agent session that did not write the code, the pre-registration or the note. Date of review: 2026-10-25, from 13:3x to 13:5x GMT. The reviewer had read access to the repository at `a82006a` and its git history, Study 006's committed files and review script, and the git-ignored raw files in `data/raw/` as present on disk (all 7 SHA-256 values match `results/data_manifest.json`). No network access, no credentials, no secret file read. `reproduce.sh` and `charts/make_charts.py` were not run, and nothing under `results/`, `src/`, `tests/`, `charts/`, `paper-log/`, `data/raw/` or the notes was modified.

`review_recompute.py` uses numpy, pandas and scipy only and imports nothing from `src/` or `qune_research/`. The source files were read to learn the conventions the pre-registration leaves to the code: the RNG draw order, the quintile tie rule, ddof 0 for sd(w), and B2/B3 restarted on T1b's window. Those conventions were then reproduced, not chosen. The leg formulas follow Study 002 §5.2 as written in Study 006's review script. The reviewer wrote only this file and `review_recompute.py`.

*Dated note, 2026-10-25, as in Study 005 §2 after the [cold read](../../COLD_READ.md) (point 6):* "independent" in this file means a separate agent session on the same model family as the author, on the same machine. It recomputes the published figures from the committed and raw files and checks the commit order. It is not a replication by an outside party. See [ARCHITECTURE.md](../../ARCHITECTURE.md#how-independence-is-enforced).

## 3. Tests

Both suites were run with the repository's virtual environment and `python -m pytest -q`, at 13:4x GMT on 2026-10-25:

| Suite | Result |
|---|---|
| Study (`tests/`) | 242 passed in 52.7 s (64 warnings, all `RuntimeWarning` in `src/stats.py` lines 111–168: divide/sqrt on degenerate resamples in the Ledoit–Wolf and bootstrap tests) |
| Library (`qune_research/tests/`) | 134 passed in 15.3 s |

`git diff 8a304e4 b43c825 -- src tests reproduce.sh` changes no line of code. It adds one comment line to `src/config007.py` (the family re-count, `4af5b84`). So the code that ran all four steps is the tree tested before `APPROVED`. The README's "242 tests" is correct.

## 4. Recomputation

`review_recompute.py` prints 1,141 rows: 1,128 match, 1 mismatch (finding 1), 12 informational. It runs in about 80 s and exits 1 because of the mismatch. Selected rows:

| Claim | Published | Recomputed | Match |
|---|---|---|---|
| SHA-256 of the 7 raw files = data manifest; the chart manifest's 3 input hashes = committed files | — | equal | yes |
| Signal dates rebuilt from FRED (last date in the month with DGS10, DGS7 and DTB3); carry of §6.1 at each, 534 test months | `carry_at_signal` | max diff ≤ 1e-15 | yes |
| Expanding average-rank weights from 1969-07 for m = 60/36/120, history, gate and episode; first weight 7/59; first months 1974-06 / 1972-06 / 1979-06 | `w_T1`, `w_T1a`, `w_T1b` | ≤ 1e-15 | yes |
| w_T1 ≡ w_T1a on all 534 periods, and ≡ w_T1b on T1b's 474 (the disclosed design miss) | identical | identical | yes |
| Trend h from the rebuilt synthetic indices (12 rows back); T2 = ½ w_T1 + ½ h; actual-side trend from broker closes in the episode | `w_T3`, `w_T2` | exact (closest test-window \|x12\| 1.7e-4) | yes |
| B1, B0 from the rebuilt legs on the committed execution dates; execution dates and B1/B0 = Study 006's committed history | — | ≤ 1e-13; identical | yes |
| T1–T3, B2, B3 at both costs (engine from cash, drift, (1 − c·\|Δw\|)²); T1b, B2 and B3 restarted on 1979-07 | `monthly_*.csv` | ≤ 1e-15 | yes |
| Twelve metrics for each trial and benchmark, both costs; turnover 29.83 / 29.83 / 25.24 / 36.13 / 46.00 | `metrics_*.csv`, `summary.json` | ≤ 1e-10 | yes |
| NW mean/se/t vs B1 and B3; bootstrap CI [0.2174, 0.7375]; Ledoit–Wolf p vs B3 0.1535 (T1), seed order reproduced | as published | same (p exact) | yes |
| DSR at N = 14 / 5 / 10, SR*, floor applied (raw variance 4.85e-5 < 2.08e-4) | 0.99755 / 0.99866 / 0.99795 | same | yes |
| §9.5 criteria for the 5 trials, the reviewer's precedence and companion clause, no turnover label, σ ≤ bar | as published | same | yes |
| Sub-windows and rate eras by execution month (Sharpe of T, B1, B3; mean and t of T − B3; mean weight) for T1–T3 | `summary.json` | same | yes |
| Attribution, corr(w_T1, w_T3) 0.3245, quintiles (qcut on rank "first": 107/107/106/107/107), carry sign 61/473, NW/iid 0.9815, sd(w − w̄) 0.3034 (ddof 0) | as published | same | yes |
| Gate: g from the rebuilt legs and the ETF closes per the vendor columns; G1, w_o, turnover, splits, mean g, corr for all 5 trials; G2 | `periods.csv`, `gate.json` | g ≤ 1e-13; statistics ≤ 1e-12 | yes |
| Volatility check: σ, MDE 1.5348%, 534 periods | `volcheck.json` | same | yes |
| Episode: actual B1/B0 = broker IEF/BIL closes; synthetic legs; weights with the rank still expanding (687 months); all trials and B3 at both costs and both sides; NW t; forward-start weights 0.4111 / 0.2055 / 0, carry 0.0142 | `results/episode/` | ≤ 1e-13 | yes |
| README, trial-log and registered typed numbers (262 rows: verdict table, gate, sub-windows, decades, attribution, mechanism, power after the fact 0.0335% / 0.80% / 1.14%, +0.62%, −3.6% / −16.1%, registered MDEs 1.6 / 0.93 / 0.120 / 4.8 / 0.62 / 2.8 / 0.36) | — | all at printed rounding but one | yes (1 NO) |
| Five chart titles rebuilt from recomputed numbers = SVG text = README alt text; manifest numbers (131, 119, 61, growth 23.64 / 25.57 / 16.50, drawdowns, B1 trough 1980-02, decade and window means and t) | as published | same | yes |

## 5. Commit chain

Committer times are from `git show -s --format=%cI` (all on 2026-10-25, UTC = London), and run times from `run_at_utc` in each output.

| Step | Commit | Time | Run (UTC) | Precedes the governed result |
|---|---|---|---|---|
| Power; question note | `6cc65fb` `7692356` | 09:22:49, 10:21:37 | — | yes |
| Pre-registration and trial log | `e4c21e5` | 11:23:31 | data step 11:25:57 | yes |
| Data step outputs (pre-run row committed with the outcome; disclosed) | `1cb9b28` | 11:26:51 | — | after its run |
| Code parts 1–3, §16 first entry | `b529994` `c9a27f3` `8a304e4` | 11:34:11, 12:22:47, 12:32:04 | — | yes |
| `APPROVED` + gate row; gate outputs, T1a/T1b disclosure, §16 second entry | `96af276` `4b2b7fd` | 12:32:56, 12:34:19 | gate 12:33:18 (code `96af276`) | yes; the disclosure precedes any return |
| Volcheck row; outputs | `ae0cfa7` `04c77e0` | 12:34:44, 12:35:51 | 12:34:52 (code `ae0cfa7`) | yes |
| Family re-count and run rows; history outputs | `4af5b84` `b43c825` | 12:37:56, 12:40:59 | 12:39:33 (provenance `4af5b84`) | yes |
| Note; time precisions | `6cbfa6c` `4c19353` | 13:21:17, 13:21:51 | — | yes, before the episode row |
| Episode row; outputs; README section | `5dc2d38` `5b7632b` `ab0f01a` | 13:22:35, 13:24:05, 13:25:07 | 13:23:27 (provenance `5dc2d38`) | yes |
| Charts; time label; after the chart check | `9d2d317` `91367d8` `a82006a` | 13:28:12, 13:28:37, 13:33:37 | manifest 13:32:47 at `91367d8` | inputs unchanged (hashes) |

The 21 commits are strictly increasing in time. Each `results/` folder has exactly one commit. Since `e4c21e5`, `PREREGISTRATION.md` and `trials.md` have had no line removed: two §16 entries and every outcome row are appended. This fixes Study 006's should-fix 2. Limits as before: one machine clock and unsigned commits, and git cannot show the absence of an uncommitted earlier run.

## 6. Criteria and verdict

The criteria were applied by the reviewer from the recomputed numbers. The gate passes for all five trials, so no trial is dropped and the gate row does not apply. σ 7.812% ≤ 10.18%, so neither the "consistent" row nor the low-power label applies. Every turnover is ≥ 8, so no "low-powered" label applies.

| Trial | C1 | C2 | C3 | C4 | Row on own criteria |
|---|---|---|---|---|---|
| T1 | pass | pass, t 2.1019 | pass | pass | supported in history |
| T1a | pass | pass | pass | pass | supported in history; identical to T1 |
| T1b | pass | **fail, t 1.9507** | pass | pass | **not supported** |
| T2 | pass | pass | pass | pass | supported in history |
| T3 | **fail** | **fail, t 1.6002** | pass | pass | not supported |

Precedence is not supported > inconclusive > consistent > supported. With the clause "T1a or T1b not supported", T1 is **inconclusive (fragile)**. `summary.json`, `verdict.md`, README.md and trials.md agree, and T2 and T3 stay secondary rows.

Two sceptical checks show the miss is a window effect, not a cost or entry artefact. T1 run with its carried-in holdings on T1b's 474 periods against B3_T1b gives t 1.9508, against 1.9507 for T1b. The six periods executed 1979-07 to 1979-12 average +10.3% a year annualised in T1 − B3, and both windows keep them.

## 7. Disclosures

These disclosures are present:

- §2.4 (Study 006 saw the window; the trend's 2003–2026 path is known) is in the first paragraph and in "What did not work".
- The T1a/T1b design miss was found at the gate (`4b2b7fd`), recorded in trials.md and §16 before the volatility check and before any return, and repeated in the note's first paragraph.
- The family count went from 11 to 14 (§0 item 11) and was re-counted before the run. Fidelity before 2003 is an assumption.
- No gain over holding the bond (t −0.54); the mechanism is not monotone (Q4 −2.29%); the trend adds nothing.
- The MDE sentence in trials.md was corrected by an appended, dated row, with a second precision on that correction's own time label. The data step's pre-run row was committed with its outcome.
- The episode has no decision weight and its trend part is a known window; there is no paper order.

Not stated in the note: C1 also passes narrowly (by 0.011 Sharpe for T1, 0.010 for T1b), the same order as C2's margin. See also notes 4 and 5.

## 8. Findings, ranked

**Must fix:** none.

**Should fix**

1. README.md, episode section: "below 0.2 from the July 2022 signal on" is true only up to the 2024-11 signal. From 2024-12 T1's weight is 0.257 and rises to 0.406 (2026-07), and the forward start weight is 0.411. The computed figures (−3.6% against −16.1%, mean weight 0.256, t 0.59) are right. Suggested wording: "below 0.2 from the July 2022 to the November 2024 signal".
2. trials.md, row "Implementation, part 2 of §14 step 3" says "12:4x GMT (this commit; its time is the record)", but `c9a27f3` was committed at 12:22:47. This is an estimate that was not corrected, the same class as Study 006's should-fix 1 and as the two precisions in `4c19353`. Append a dated correction. The order is unaffected.

**Notes**

3. `gate.json`/`gate.md` label the first split "2002-2007". It holds the 60 periods executed 2003–2007 (signal months 2002-12 to 2007-11), as trials.md says. The label mixes signal and execution years.
4. The DSR at N = 14 uses the variance of this study's five monthly Sharpe ratios (raw 4.85e-5, floored to 2.08e-4), not the variance across the 14 family trials, which the code does not have. C3 would fail only if the family's annual Sharpe ratios had an sd above about 0.147 (informational row). This is not decision-relevant here, but the family rule leaves V undefined.
5. README first paragraph: "about 0.36 Sharpe (2.8% a year) at the uniform-rank dispersion, close to the 0.303 the rule showed" compares a dispersion (0.303 = sd(w − w̄)) with a dispersion, but reads as if 0.303 were a Sharpe ratio.
6. sd(w − w̄) is the population sd (ddof 0); the sample sd is 0.3037 (README 0.303 either way at 0.3034). T3's `hit_rate_positive_excess` 0.345 counts exact-cash months as non-hits.
7. The first 60 periods average +0.62% a year, but their decade, 1974–79 (66 periods), averages +1.50%. The difference is the six periods after Volcker's appointment (+10.3% a year), which T1b keeps. So the README's "those months were not the source of the edge" is right for 1974-07 to 1979-06.

## 9. Not checked (and why)

- The NYSE execution calendar: execution dates were taken from the committed files, checked against Study 006's committed history (identical on all 534 months, verified there by its reviewer against a rule-based calendar) and checked to fall 1–7 days after the rebuilt signal date.
- Not run or read: `reproduce.sh`, `make_charts.py`, `forward007.py` (not yet built), the PNG renders (titles read from SVG text), the root README, BUILD_LOG, `CHART_REVIEW.md` beyond the existence of its fourth section, and the citations.
- Episode Ledoit–Wolf p-values and bootstrap intervals: no decision weight and not quoted in the note. 8 are NaN, as disclosed.
- The desk registry count (562 rows) behind the family re-count: outside this repository.
- Whether each run was executed once: git shows one commit per output folder with matching provenance and times inside the logged-to-committed interval, but cannot show an uncommitted earlier run.

## 10. How to rerun the reviewer's checks

From the study folder, with the raw files present in `data/raw/`:

```
../../.venv/bin/python review_recompute.py; ../../.venv/bin/python -m pytest -q
```

The script takes about 80 s, prints the 1,141-row table and exits 1 while finding 1 stands. Without the raw files it checks hashes only and says so.
