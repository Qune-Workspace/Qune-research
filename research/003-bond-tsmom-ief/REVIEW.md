# Independent review: Study 003

## 1. Headline

**Confirmed with findings.** The verdict "not supported" for T1 follows from the pre-registered table as written (C1 and C2 failed in-sample; any in-sample failure is "not supported" and no other row of the table can apply), every published number the reviewer could recompute from the committed monthly files and the raw daily files matches to the printed precision, and the commit chain is in the pre-registered order. The findings below are wording and disclosure issues; none changes a number or the verdict.

## 2. Independence statement

The reviewer is Tester, a separate agent session that did not write the code, the pre-registration or the study note. Date of review: 2026-10-22. The reviewer had read access to the repository at commit `6ce61e1` (the finished note), its git history, and the git-ignored raw files in `data/raw/` as present on disk (SHA-256 of all five files matches `results/data_manifest.json`). The reviewer had no network access, no vendor credentials, and did not run `reproduce.sh` in any mode; `results/` was not modified. Every statistic in §4 was re-derived in `review_recompute.py` with numpy, pandas and scipy only, without importing anything from the study's `src/`. The reviewer wrote only this file and `review_recompute.py`.

## 3. Tests

Command, run from the study folder exactly as `.github/workflows/tests.yml` does (`python -m pytest -q`), with the repository's virtual environment:

```
../../.venv/bin/python -m pytest -q
94 passed in 19.69s
```

`python -m pytest -q --co` collects 94 tests. Two of them (`test_real_insample_calendar_counts_match_preregistration`, `test_real_oos_calendar_counts_match_preregistration`) are marked `skipif` when the vendor or Alpaca files are absent, so CI, which has no data, runs 92; with the raw files present all 94 ran and passed. The test files have a single commit (`987b161`) and were not changed after any run.

## 4. Recomputation

`review_recompute.py` prints 174 rows; 171 are numeric comparisons and all 171 match (0 mismatches; 3 rows are informational). The full table is the script's output. Published values are read from `metrics_base.csv` and `summary.json` at full precision; rows marked README compare against the note's rounded text. Selected rows:

| Claim | Published | Recomputed | Match |
|---|---|---|---|
| IS holding periods / OOS holding periods | 185 / 93 | 185 / 93 | yes |
| IS T1 ann. return, vol., Sharpe (excess over B0, mean/sd × √12) | 3.6610%, 5.8170%, 0.4518 | 3.6610%, 5.8170%, 0.4518 | yes |
| IS T2 Sharpe / T3 Sharpe | 0.4056 / 0.3180 | 0.4056 / 0.3180 | yes |
| IS B1 Sharpe / B2 / B3 | 0.5546 / 0.5541 / 0.5543 | 0.5546 / 0.5541 / 0.5543 | yes |
| IS monthly max DD: T1, T2, T3, B1, B3 | −8.60%, −8.60%, −10.14%, −8.07%, −5.64% | same | yes |
| IS switches T1 / T2 / T3 (switch flags inferred from the returns alone) | 18 / 24 / 37 | 18 / 24 / 37 | yes |
| IS fraction in IEF T1 / T2 / T3 | 0.6919 / 0.6703 / 0.6811 | same | yes |
| T1_holding = IEF iff mom_at_signal > 0, every month, both windows | — | true | yes |
| IS mean(T1−B3) ×12; Newey–West t (6 lags, Bartlett, hand-coded) | +0.2272% p.a.; 0.3743 | +0.2272%; 0.3743 | yes |
| IS mean(T1−B1) ×12; NW t | −0.8471% p.a.; −1.4739 | −0.8471%; −1.4739 | yes |
| IS Ledoit–Wolf point estimate (annualised Sharpe difference) vs B3 / B1 | −0.1028 / −0.1031 | −0.1028 / −0.1031 | yes |
| Variance of monthly Sharpe across T1–T3 (ddof = 0); floor not applied | 0.000256 | 0.000256 | yes |
| T1 expected max Sharpe SR* (monthly) N = 3 / N = 10 | 0.01366 / 0.02522 | 0.01366 / 0.02522 | yes |
| T1 DSR at N = 3 / N = 10; PSR | 0.9512 / 0.9322; 0.9679 | 0.9512 / 0.9322; 0.9679 | yes |
| B3 weight = in-sample fraction of months T1 held IEF (128 of 185) | 0.6919 | 0.6919 | yes |
| IS B3 monthly returns reproduce from w, B1, B0 and the rebalancing cost | — | max abs diff 2e-16 | yes |
| OOS T1 ann. return, vol., Sharpe | 3.2059%, 3.8878%, 0.1570 | same | yes |
| OOS B1 / B3 Sharpe | −0.2590 / −0.2593 | −0.2590 / −0.2593 | yes |
| OOS T2 / T3 Sharpe | 0.0024 / −0.2409 | 0.0024 / −0.2409 | yes |
| OOS monthly max DD T1 / B1 | −5.47% / −22.24% | −5.47% / −22.24% | yes |
| OOS switches T1 / T2 / T3; T1 fraction in IEF | 10 / 12 / 16; 0.4086 | 10 / 12 / 16; 0.4086 | yes |
| OOS mean(T1−B3) ×12; NW t | +1.9285% p.a.; 1.3098 | +1.9285%; 1.3098 | yes |
| OOS mean(T1−B1) ×12; NW t | +2.5136% p.a.; 1.2928 | +2.5136%; 1.2928 | yes |
| OOS months with T1−B0 exactly zero | 50 of 93 | 50 of 93 | yes |
| OOS T1 DSR at N = 3 (descriptive) | 0.5192 | 0.5192 | yes |
| mom_at_signal recomputed from month-end bars, all 185 IS months (Tiingo adjClose, own DTB3 accrual) | — | max abs diff 9.7e-17 | yes |
| mom_at_signal recomputed, all 93 OOS months (Alpaca IEF and BIL closes) | — | max abs diff 9.7e-17 | yes |
| B1 and B0 holding-period returns reproduce from the daily indices, both windows | — | max abs diff 1e-16 | yes |
| Daily max DD, IS: T1, T2, T3, B1 | −10.40%, −10.40%, −12.36%, −10.40% | same | yes |
| Daily max DD, OOS: T1, T2, T3, B1 | −6.52%, −11.60%, −15.23%, −23.92% | same | yes |
| README: 57 cash months in 9 episodes; IEF 0.38%/m vs cash 0.16%/m; cash won 42% | 57, 9, 0.38%, 0.16%, 42% | 57, 9, 0.3756%, 0.1591%, 42.1% | yes |
| README episode table: 2005-09..2006-10 −0.12%; 2017 +2.04%; 2018 +2.21% | as printed | −0.12%, +2.04%, +2.21% | yes |
| README sub-periods: T1/B1/B3 Sharpe and switches, three periods, 65/84/36 months | as printed | all match to 3 d.p. | yes |
| README OOS: 55 cash months, 6 episodes; 2021-02..2024-07 42 months, IEF−cash −19.0%, T1 +10.1% | as printed | 55, 6, 42, −18.97%, +10.07% | yes |
| README OOS cumulative T1, cash, B3, B1 | +27.7%, +22.5%, +9.5%, +3.5% | +27.71%, +22.52%, +9.53%, +3.55% | yes |
| README: T1's three worst IS months are IEF's three worst | 2016-10, 2004-03, 2009-11 | same set | yes |
| README: T1 switching cost about 5 bp p.a. | 0.05% | 0.047% | yes |
| Stationary-bootstrap Sharpe CI; Ledoit–Wolf bootstrap p-values and CIs | [0.02, 0.83]; p 0.24 etc. | — | not checked (§9) |

Notes on method. The Newey–West t was hand-coded (Bartlett kernel, 6 lags, no small-sample factor) and reproduces the study's statsmodels value to four decimals. Switch counts were inferred from the strategy returns alone (a month's return is either the IEF or the BIL return, multiplied by (1 − 0.0002)² when a switch is charged) and agree with the T1_holding column in every month. The deflated Sharpe ratio was recomputed from the reviewer's own three monthly Sharpes, skewness and non-excess kurtosis by the §9.4 formula.

## 5. Timestamp chain

Author times from `git log --format=%ci` (all 2026-10-22, London, +0100). Run times are the UTC values the outputs record (`run_at_utc`, `downloaded_at_utc`, `provenance.git_commit`), converted to London.

| Step | Commit | Author time | Governs | Precedes the governed result |
|---|---|---|---|---|
| Pre-registration v1.0 and trial log (§14 step 1) | `b7f7b63` | 06:25:06 | everything below | yes (BIL fetch 06:26:59) |
| Overlap-check code and pre-run row for the fetch (§5.3.2) | `5a83286` | 06:26:57 | BIL fetch | yes (fetch 06:26:59) |
| BIL fetch outcome, manifest | `521e033` | 06:27:17 | overlap run | yes (`run_at_utc` 05:27:20Z = 06:27:20) |
| Overlap outcome, vendor accepted, §16 entry | `e03064d` | 06:28:01 | D2 window | yes (--check 08:30:55) |
| Engine and tests (§14 step 3) | `987b161` | 08:30:10 | --check | yes |
| APPROVED and pre-run row for D0 + D2 | `8076ecc` | 08:30:37 | --check | yes (run 07:30:55Z = 08:30:55; 18 s later) |
| D0 + D2 outputs, §16 entry | `5dfe8cf` | 08:31:43 | in-sample run | yes |
| T1–T3 run dates logged (§14 step 5) | `106696e` | 08:32:03 | --insample | yes (`results/insample/summary.json` provenance commit = `106696e`; DTB3 re-fetch 08:32:10) |
| In-sample outputs, in-sample note, OOS pre-run row (§14 steps 6–7) | `7e44a4c` | 08:36:11 | --oos | yes (`results/oos/summary.json` provenance commit = `7e44a4c`; DTB3 re-fetch 08:36:27) |
| OOS outputs, finished note, §16 entry (§14 steps 8–9) | `6ce61e1` | 08:41:16 | — | after the run, as required |

Every file under `results/` has exactly one commit except `data_manifest.json` (six commits, each appending provenance or updating the DTB3 re-fetch time; the DTB3 SHA-256 is identical in all of them). `results/oos/` appears in exactly one commit (`6ce61e1`). `PREREGISTRATION.md` differs from `b7f7b63` only by the three appended §16 entries. The README diff between `7e44a4c` and `6ce61e1` changes no in-sample number; it merges the in-sample headline into the verdict paragraph, replaces the OOS placeholder and reflows one sentence of the power statement. Limits of this evidence: all git and in-file timestamps come from one machine clock, no commit is signed, and git cannot show whether an uncommitted run happened before a committed one.

## 6. Criteria and verdict

Applied by the reviewer from the recomputed numbers, exactly as Study 001 §9.5 states: C1 fail (0.452 against 0.655 and 0.654), C2 fail (t = 0.374 < 2.0), C3 pass (0.9512 ≥ 0.95), C4 pass (+0.23% → +0.18% p.a., sign unchanged); O1 holds (+1.93% p.a.), O2 holds (0.157 > −0.259); drawdown clause not triggered (−6.5% against −23.9% daily; −5.5% against −22.2% monthly). Table row "Not supported: any of C1–C4 fails" applies. "Supported" and "inconclusive" both require C1–C4 to hold, so no other row applies and the precedence rule (not supported > inconclusive > supported, Study 001 §16, 2026-10-21) is not even needed to break a tie; the note's statement that the precedence rule "decides" is correct but stronger than necessary. The verdict in `results/oos/summary.json` (`verdict_T1`) and the note agree with the reviewer's application. The downgrade rule for T2/T3 does not arise.

## 7. Disclosures

- §2.4 (designer's prior knowledge): present; lists the data seen (IEF and BIL daily returns 2016–2018, the Study 001/002 overlap and validation statistics) and states the prior of 10–20 switches and 20–35% cash. The in-sample outcome (18 switches, 30.8% cash) sits inside that prior; the note reports both next to each other as §9.6 requires.
- §8.3 (the OOS window and 2022): present and plain; the window was fixed on 2026-10-21 under Study 001 before any computation, and §8.3 says in advance that one episode would decide the sign. It did (the single exit 2021-02 to 2024-07 accounts for the whole OOS advantage; recomputed).
- NaN bootstrap intervals: disclosed consistently in §16 (third entry), README (OOS inference paragraph and "What did not work (continued)") and `results/oos/posthoc_bootstrap_nan.md`: 50 of 93 months with excess exactly zero (recomputed: 50), 1 and 4 degenerate resamples of 10,000, post-hoc intervals [−0.698, 0.947] and [−0.460, 1.429] rounded correctly in the README. The published `summary.json` is unchanged (single commit).
- "What did not work": present for in-sample (six items) and out-of-sample (four items); every failed criterion, the C3 margin, the whipsaw episodes and the undefined intervals are listed. The §9.6 power statement is present in the note's first paragraph of the in-sample section and in a dedicated subsection; label "as registered" is correct under the pre-registered rule (18 ≥ 8).

## 8. Findings, ranked

**Blocking:** none.

**Should fix**

1. `trials.md`, last paragraph (line 30): "T1, T2 and T3 have not been run. The out-of-sample window (2019-01 to 2026-09) has never been touched by any study." Both sentences are stale; they contradict the first sentence of the same paragraph and the T1 row ("OOS not yet run", also stale). Append a dated correction rather than editing the sentences.
2. `README.md` lines 13 and 185 and `trials.md` line 22: "92 tests". The suite has 94 tests; 92 is the count CI sees because two real-calendar tests are skipped without raw data, while the author's own run (which, per trials.md, executed those two tests) would have shown 94. State both numbers.
3. `README.md` line 5 and the power statement: "The question was answerable on that sample". Switch count is the pre-registered power proxy, but the detectable effect is what a reader needs: the Newey–West standard error of mean(T1−B3) is 0.051% per month, so C2 at t ≥ 2.0 required a timing contribution of about 1.2% p.a. over 185 months. A one-asset, long-only sign rule with a true edge of 0.5% p.a. would fail C2 on this sample however many times it switched. The verdict is unaffected (the pre-registered bar is the bar), but the sentence overstates what the sample could resolve.

**Note**

4. `README.md` in-sample and OOS tables, "Switches": the engine starts every window holding BIL (§6.6), so the first in-sample month's purchase of IEF is counted as a switch and charged a full round trip (4 bp) while B1 pays nothing after its initial purchase (Study 001 §9.1). Changes of T1_holding alone number 17 in-sample (10 out-of-sample, where the first target was BIL). Effect on T1: about 0.3 bp p.a.; the power label is unchanged either way.
5. C1's second leg (margin over B3) is identical to its first leg: a constant mix of IEF and cash has B1's excess-return Sharpe by construction (0.5543 against 0.5546, the gap being rebalancing cost). The README says so; a reader should know that B3 only bites in C2, C4 and O1, not in C1.
6. `README.md` OOS table, "Hit rate (excess > 0) 0.20" for T1: 50 of 93 months are exactly zero, so the rate on the 43 months with non-zero excess is 0.44. Worth a footnote next to the NaN disclosure, which has the same cause.
7. O1 is tested against B3 at the frozen in-sample weight 0.692 while T1 held IEF in 41% of OOS months. Against a mix at T1's own OOS exposure (0.409, no cost; reviewer's descriptive, not a criterion) the timing contribution is +1.39% p.a. instead of +1.93%. The sign and the reading of the note do not change; the number is reported so that nobody mistakes the frozen-weight comparison for an exposure-matched one out-of-sample.
8. `PREREGISTRATION.md` header, "Status | pre-registered; no data check run, no return ... computed": immutable by the document's own rule, but a reader opening the file at HEAD sees a status that §16 has superseded three times. A one-line pointer to §16 in the header would be an allowed amendment.
9. `results/oos/` contains two post-hoc files written by `posthoc_bootstrap_nan.py` in the same commit as the run outputs. They are correctly labelled descriptive; the folder is nonetheless not "written exactly once" by `reproduce.sh --oos` alone.
10. The vendor decision's `run_at_utc` (06:27:20 London) follows its governing commit `521e033` (06:27:17) by three seconds, and the --check run follows `8076ecc` by eighteen seconds. The order is correct; it rests on one clock and unsigned commits (see §5).

## 9. Not checked (and why)

- Stationary-bootstrap Sharpe intervals and Ledoit–Wolf bootstrap p-values and intervals (§9.3 items 8–9): random resampling; reproducing the seed path would require running the study's own generator code, which the brief excludes. The Ledoit–Wolf point estimates were recomputed and match.
- Whether the in-sample and OOS runs were executed once: git shows each output committed once at the expected HEAD; it cannot show the absence of an uncommitted earlier run.
- The vendor overlap statistics and D2 cash-check statistics (`results/checks/`): the review brief centred on the rule's results; the reviewer's own DTB3 accrual reproduces every B0 holding-period return to 1e-16, which checks the accrual code but not the D2 window statistics themselves.
- The in-sample stress-cost table beyond C4 (`metrics_stress.csv`), the charts, and T2/T3 against C1–C4 individually.
- Literature citations and the NYSE closure list in `src/calendar.py` (the author's own note says "to be re-verified at review"; no offline source was available).

## 10. How to rerun the reviewer's checks

From the study folder:

```
../../.venv/bin/python review_recompute.py && ../../.venv/bin/python -m pytest -q
```

The first command prints the 174-row comparison table and exits non-zero on any mismatch; it requires the raw files in `data/raw/` for the signal and daily-drawdown rows and reports them as not checked if absent.
