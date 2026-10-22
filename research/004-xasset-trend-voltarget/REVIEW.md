# Independent review: Study 004

## 1. Headline

**Confirmed with findings.** The verdict "not supported" for T1 follows from the §9.5 table as written: C1 and C2 failed in-sample (Sharpe 0.886 against a bar of 0.980; Newey–West t 0.65 against 2.0), any in-sample failure is "not supported", and no other row of the table can apply, so the precedence rule is not even needed. Every number in `summary.json` and the metrics CSVs recomputes from the committed monthly, period, daily and signal files; the whole monthly table (signals, volatilities, weights, drift, costs, every strategy and benchmark, both windows, ten and nine assets) and the daily indices rebuild from the raw vendor files with the reviewer's own engine to machine precision; the commit chain is in the pre-registered order. The findings are fourteen README figures that are off by one in their last printed digit (double rounding) and five uncorrected time labels in the trial log. None changes a number that decides anything, or the verdict.

## 2. Independence statement

The reviewer is Tester, a separate agent session that did not write the code, the pre-registration or the study note. Date of review: 2026-10-23. The reviewer had read access to the repository at commit `4bd9187` (the finished note), its git history, and the git-ignored raw files in `data/raw/` as present on disk (SHA-256 of all 26 files matches `results/data_manifest.json`). No network access, no vendor credentials, no secret file read; `reproduce.sh` was not run in any mode; nothing under `results/`, `src/`, `tests/` or the notes was modified. Every statistic in §4 was re-derived in `review_recompute.py` with numpy, pandas and scipy only, importing nothing from `src/` or `qune_research/`. The reviewer wrote only this file and `review_recompute.py`.

## 3. Tests

Run from the study folder and from `qune_research/`, exactly as `.github/workflows/tests.yml` does (`python -m pytest -q`), with the repository's virtual environment:

| Suite | Collected | Result | Skips |
|---|---|---|---|
| Study (`tests/`) | 18 | 18 passed in 23.5 s | none; no test depends on `data/raw/` |
| Library (`qune_research/tests/`) | 71 | 71 passed in 11.6 s | none |

The study's `tests/` and `src/` have three commits (`f57d20b`, `bff736c`, `1697e9d`); the only change after a run is the §16 end-bar amendment in `1697e9d`, whose diff touches `oos_schedule`, `common_last_bar`, the `end_at_last_bar` flag of `qune_research.dates.schedule` (default off) and two tests, and nothing on the in-sample path. No file under `src/`, `tests/`, `qune_research/` or `results/` changed after `784f6ed`.

## 4. Recomputation

`review_recompute.py` prints 1,961 rows: 1,937 match, 14 mismatch, 10 informational. Every one of the 14 mismatches is a README figure one unit off in its last printed digit (finding 1); no value in `summary.json` or any CSV mismatches. The script exits 1 because of those 14 rows, by design. Selected rows (full table: run the script):

| Claim | Published | Recomputed | Match |
|---|---|---|---|
| Holding periods IS / OOS; common last bar | 180 / 93; 2026-09-30 | 180 / 93; 2026-09-30 | yes |
| s12, s6, s3 signals from raw bars, every signal date × asset, both windows, ten and nine assets | — | identical (181 × 10, 94 × 10, 181 × 9, 94 × 9) | yes |
| 63-day volatility from raw bars; T1 weights from signal and vol by §6.2 | — | max abs diff 1e-16; 6e-16 | yes |
| Monthly net returns of B0–B4, T1–T4 rebuilt from raw data with the reviewer's engine, 4 runs | — | max abs diff 3e-16 | yes |
| T1 daily index rebuilt from raw data; daily index at period ends = compounded monthly net | — | 8e-15; 7e-15 | yes |
| k = mean(T1 exposure / B3 exposure), ten / nine; frozen and reused OOS | 0.8018 / 0.7764 | 0.8018 / 0.7764 | yes |
| B4 − [k·B3 + (1−k)·B0], net, max abs (cost residual); k by regression | — / 0.8018 | 7e-7 / 0.8018 | yes |
| IS T1 / B3 / B4 Sharpe (excess over B0, ddof 1, ×√12) | 0.8857 / 0.8804 / 0.8805 | same | yes |
| IS NW t of T1−B4 / T1−B3 (6 Bartlett lags, hand-coded, no small-sample factor) | 0.6474 / −0.4799 | 0.6474 / −0.4799 | yes |
| IS Ledoit–Wolf point estimate T1−B4 (annualised) | +0.0052 | +0.0052 | yes |
| IS variance of the four monthly Sharpes; floor applied ten / nine | 0.00033676; no / yes | same | yes |
| IS T1 DSR N = 4 / N = 10; PSR | 0.9983 / 0.9976; 0.9993 | same | yes |
| IS switches T1 / T2 / T3 / T4 (from the signal CSVs) | 167 / 268 / 390 / 630 | same | yes |
| IS monthly max DD T1 / B3 / B4; daily T1 / B3 / B4 | −5.24% / −8.34% / −6.60%; −6.84% / −9.80% / −7.77% | same | yes |
| IS crisis 2008-09-01..2009-02-28 T1 / B3 / SPY / IEF | +2.4% / −5.3% / −41.4% / +6.4% | same | yes |
| IS correlations T1–SPY / T1–IEF / B3–SPY / B3–IEF | 0.298 / 0.428 / 0.538 / 0.419 | same | yes |
| IS vol forecast ratio T1 / B3; share > 1.5× | 1.581 / 1.606; 0.527 / 0.544 | same | yes |
| IS breakeven curve at 0, 0.5, 1, 2, 3, 5× (T1 and B4 rerun at each multiple); zero crossing | +0.0127 … −0.0248; 1.6995 | same | yes |
| IS sub-period Sharpe, return, max DD for B1, B3, B4, T1–T4, three periods; switches 51 / 70 / 42 | as published | all match | yes |
| IS attribution (contribution, variance share, months on) and per-asset Sharpe, ten assets | as published | all match | yes |
| OOS T1 / B3 / B4 Sharpe; T2 / T3 / T4 | 0.3357 / 0.1995 / 0.1995; 0.2935 / 0.1967 / 0.3223 | same | yes |
| OOS mean(T1−B4), NW t; mean(T1−B3), NW t | +0.000267, 0.3458; +0.000057, 0.0557 | same | yes |
| OOS monthly max DD T1 / B4; daily T1 / B4 | −4.06% / −11.09%; −11.39% / −12.45% | same | yes |
| OOS crisis windows 2020-02-19..03-23, ..08-31, 2022-01-01..10-31, all seven columns | as published | all match | yes |
| OOS switches T1 ten / nine | 122 / 112 | 122 / 112 | yes |
| OOS nine assets: T1 Sharpe, B3, NW t vs B4 / B3 | 0.3402, 0.2734, 0.0282 / −0.3252 | same | yes |
| D1 overlap: mean daily difference × 252 and gate status, all twelve symbols on 753 days | SPY +0.3146% excluded, DBC −0.4648% excluded, HYG +0.1410% pass … | same | yes |
| README tables and text, 10- and 9-asset, both windows (about 560 typed values at README rounding) | — | 14 off by one last digit | NO (finding 1) |
| Stationary-bootstrap CIs, Ledoit–Wolf p-values and CIs | as published | — | not checked (§9) |

## 5. Commit chain

Committer times from `git log --format=%cI` (all 2026-10-22, London, +0100); run times from `run_at_utc`, `downloaded_at_utc` and `provenance.git_commit` in the outputs, and file modification times on disk, converted to London.

| Step | Commit | Time | Governs | Precedes the governed result |
|---|---|---|---|---|
| Pre-registration and trial log (§14 step 1) | `cf5ef34` | 20:23:13 | everything | yes: first vendor fetch 21:25:31 |
| Library pieces 1–3, study code and tests (step 2) | `685ef1d` `b535e68` `f57d20b` | 20:27–21:25:07 | --check | yes |
| APPROVED (step 3) | `08d8019` | 21:25:27 | --check | yes: D0 `run_at` 21:25:31 (4 s later) |
| D0 outputs and manifest | `24a40fe` | 21:26:02 | D1 | yes: D1 `run_at` 21:26:06 |
| D1 outputs; universe fixed at ten | `6f01969` | 21:26:39 | runs | yes |
| §16 data-check entry, trial rows | `a135bf3` | 21:27:41 | runs | yes |
| Run code, run dates logged, seed (step 5) | `bff736c` | 22:25:38 | --insample | yes: DTB3 re-fetch 22:26:01, provenance commit = `bff736c`, summary written 22:30:45 |
| In-sample outputs (step 6) | `02eb987` | 22:31:48 | — | after the run, as required |
| In-sample note, §16 entry (step 7) | `9bde54a` | 22:35:11 | --oos | yes |
| §16 end-bar amendment + code (before step 8) | `1697e9d` | 23:20:12 | --oos | yes: first OOS file 23:20:49, provenance commit = `1697e9d`, summary 23:23:13 |
| OOS outputs, trial row corrected (step 8) | `784f6ed` | 23:24:14 | — | after the run; `results/oos/` has exactly this one commit |
| Finished note, root README (step 9) | `4bd9187` | 23:26:52 | — | — |

`PREREGISTRATION.md` differs from `cf5ef34` only by appended §16 entries (no line removed). The README diff `9bde54a`→`4bd9187` removes only the "not yet run" status and out-of-sample placeholder and the old reproduce paragraph; no in-sample number changes. Limits: one machine clock, unsigned commits; git cannot show whether an uncommitted run happened before a committed one.

## 6. Criteria and verdict

Applied by the reviewer from the recomputed numbers, exactly as §9.5 states: C1 fail (0.886 < 0.980 and 0.980), C2 fail (0.647 < 2.0), C3 pass (0.998 ≥ 0.95), C4 pass (+0.000332 → +0.000305, sign unchanged); O1 pass (+0.000267), O2 pass (0.336 > 0.199); drawdown clause not triggered (−4.1% against −11.1% monthly). Row "Not supported: any of C1–C4 fails" applies; "supported" and "inconclusive" both require C1–C4, so the precedence rule is not needed. T2, T3, T4: C1 and C2 fail each; OOS T2 and T4 pass O1 and O2, T3 fails both. Nine assets without IEF: same four in-sample outcomes, O1 and O2 pass, verdict "not supported"; T2–T4 fail O1 there. `verdict_T1` in both summaries, the README table and the trial log all agree with this application. The downgrade clause for T2–T4 does not arise.

## 7. Disclosures

- §2.4 / §8.3 (IEF seen under Study 003): present in the pre-registration and in the README's "Disclosures that belong in the first paragraph" (its third paragraph, so labelled) with the nine-asset run beside every ten-asset table; the nine-asset verdict is stated in the opening paragraph.
- Bootstrap seed not pre-registered, Study 003's 20261021 inherited: §16 (22:3x entry), README disclosure (4), `provenance.seed` in both summaries.
- Trial-log run times entered as estimates and corrected: stated in the T1–T4 rows and the OOS row of `trials.md`, in §16 and in commits `02eb987` and `784f6ed`.
- B3 and B4 share one Sharpe by construction: §16, README in-sample table note and limitations; recomputed difference 7e-6 (ten) and 4e-6 (OOS).
- End bar 2026-09-30, one day short of §8.2, decided in `1697e9d` before `784f6ed`: §16, `summary.json` (`common_last_bar`, `note`), README out-of-sample section; the one-day difference from Study 003 is stated.
- Universe ten not twelve, SPY failing the gate while B2 keeps the vendor SPY: README disclosures (2) and (3), §16, data-check note.
- Verdict precedence, "what did not work" in both windows (seven and four items), and the power statement ("as registered", 167 and 122 switches ≥ 40): present.

## 8. Findings, ranked

**Must fix:** none.

**Should fix**

1. Fourteen README figures are one unit off in their last printed digit; each is what one gets by rounding the published value twice (first to one extra digit, then half-up). None is a criterion input, and the true values round the other way: OOS B3 and B4 Sharpe "0.200" (0.1995 → 0.199, also in the opening paragraph and the O2 row of the verdict table); OOS T2 Sharpe "0.294" (0.293); nine-asset IS B1 max DD "−30.1%" (−30.0%); nine-asset OOS B1 Sharpe "0.461" (0.460); IS T3 bootstrap CI "0.30 to 1.28" (0.29 to 1.27); "T1's Sharpe advantage over B3 and B4 is 0.006" in "What did not work" (0.005, as the breakeven paragraph itself prints); TLT variance share "12%" (11%); EFA and SHY long/flat Sharpe "0.56" and "0.89" (0.55, 0.88); sub-period 2004–2008 B1 return "6.4%" (6.3%) and T2 max DD "−4.2%" (−4.1%); sub-period 2016–2018 T3 Sharpe "0.54" (0.53). Round once from the stored value.
2. `trials.md` data-check log and one §16 header carry time labels that were entered as estimates and never corrected, unlike the two run rows that were: library piece 1 "20:3x" (commit 20:27), piece 2 "20:4x" (20:29), piece 3 "21:3x" (21:25), run code committed "22:4x" (22:25), end bar fixed "23:3x" (23:20) and the §16 heading "(23:3x London)" for an entry committed at 23:20:12. Append a dated correction; the order of events is unaffected (§5).

**Notes**

3. The README says the verdict is "fixed … under the precedence rule"; it is fixed by the "any of C1–C4 fails" row alone, which is stronger. Same remark as in the Study 003 review.
4. `fraction_asset_months_on` in the metrics CSVs divides asset-months on (over 180 periods) by asset-signal-dates (over 181 dates, the terminal signal included), so it is slightly low (1192/1710 instead of 1192/1700 for IS T1). Not used in the README.
5. The daily index starts the day after each window's first execution date, so a drawdown measured from the initial 1.0 is not in `max_drawdown_daily`; with a 1.0 start prepended every T1 daily drawdown is unchanged to the printed precision (−6.84%, −11.39%).
6. The in-sample T1 is never fully in cash; out-of-sample it holds no asset in 9 of 93 months (ten and nine assets). The README's "mostly in bills" wording for 2022 is consistent with the period file.
7. Order evidence at the data step is tight: D0 ran 4 s after APPROVED and D1 ran 4 s after the D0 commit. Correct, but it rests on one clock.

## 9. Not checked (and why)

- Stationary-bootstrap Sharpe intervals and Ledoit–Wolf p-values and intervals: random resampling; reproducing the seed path would mean running the study's own generator code, which the brief excludes. Point estimates and degenerate-resample counts (0) were checked.
- D0 coverage statistics against the NYSE calendar, and the plots.
- Whether the in-sample and out-of-sample runs were executed once: git shows each output committed once at the expected HEAD, in the right order, with matching provenance commits; it cannot show the absence of an uncommitted earlier run.
- The root README's at-a-glance row and the build log; literature citations; the inherited cash-leg check (§5.3.3).

## 10. How to rerun the reviewer's checks

From the study folder, with the raw files present in `data/raw/`:

```
../../.venv/bin/python review_recompute.py && ../../.venv/bin/python -m pytest -q
```

The script takes about a minute, prints the 1,961-row comparison table, lists the mismatches and exits 1 while finding 1 stands; without the raw files it reports the raw-data rows as not checked and still recomputes everything from the committed files.
