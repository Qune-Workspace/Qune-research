# Study 011: separate-session recomputation of the note (review of `research/011-industry-momentum-french-us/README.md` at 9e2bfab)

**Verdict: confirmed with findings.** Every number in the note and in the root README's Study 011 text was recomputed independently from `results/history/` and matches to the printed precision. The verdict (not supported: M1 fails C3, DSR 0.935 at N = 3) is right. Findings are about wording: one gap in the §2.4 disclosure, a few overclaims and unlabelled windows, and the return-unit label missing from the root README's companion sentences. No wrong number.

Method: `recompute011.py` (scratch, run with `python -I recompute011.py <repo root>`) rebuilds the rule from `industries_17.csv` and `industries_30.csv` only, without importing the study's `src/`. It follows PREREGISTRATION §6: compounded F-month return ending at m with no skip; sort key (−round(R, 10), column index); top and bottom n; six cohorts at 1/6; netted weights; cost c × Σ|Δw| with entry from zero at the first holding month; c = 0.10 and 0.50. The Newey–West estimators (two-stretch and ordinary), the Sharpe ratios, skewness and kurtosis, the DSR formula with the floor, and every descriptive row are written out in the script. The DSR was also checked against `qune_research.stats.deflated_sharpe` (agrees to 1e-12). The bootstrap uses `qune_research.stats.sharpe_ci_stationary_bootstrap`, with the code's seed and its order of RNG draws.

## Rows checked

| Block | Figures checked | Match |
|---|---|---|
| Rule rebuild vs `monthly.csv`: d_gross, turnover, d_base, d_stress, winners leg, losers leg, EW, per month, M1/M1a/M1b (1,191 / 1,191 / 1,185 months) | 21 series | all; max abs difference 7.1e-15 (d), 1.1e-16 (turnover) |
| W(m), L(m) vs `cohorts.json` | 1,197 + 1,197 + 1,191 ranking months | all (0 mismatches); boundary near-ties 0, empty legs 0 (as `monthly.csv`) |
| O table: months, mean d, two-stretch NW t, Sharpe, DSR N = 3, C1–C4, row label (3 trials) | 33 | 33 |
| DSR at N = 11, 34, 598 (3 trials) | 9 | 9 (floor applied: raw across-trial variance 1.19e-4 < floor 2.08e-4) |
| Window row (I1/I2 mean and t, pass) | 5 | 5 |
| Stress: mean and t (3 trials) | 6 | 6 |
| Turnover per year (6.1 / 6.1 / 4.3), base cost 0.6 / 0.4, stress cost 3.0 / 2.1 | 7 | 7 (turnover is over the full history; see note N3) |
| Bootstrap CI 0.006–0.502, 58.1% positive months | 3 | 3 |
| Sub-window table: I1, I2, M, full × 3 trials (mean, t), months | 24 + 6 | all |
| Decades: 11 rows (mean, t), months 31 and 80 | 24 | 24 |
| Legs on O: +1.97 (2.10), −2.09 (−2.22), EW +11.84 | 5 | 5 |
| Paper comparison 0.29 vs 0.43 % a month; 5.2% a year (0.43 × 12) | 3 | 3 |
| Episodes: 40 months −5.68%, 16 months −26.12% | 4 | 4 |
| Twelve worst months (dates and values) | 24 | 24 (full history, base costs; see S3) |
| Skewness −1.28, kurtosis 12.7, worst month −34.1% | 3 | 3 (skew/kurt on O; the full history gives −1.14 / 12.3) |
| "Other": W 6.1%, L 7.6%, lowest of 17 (on both W and L) | 3 | 3 (denominator 1,196 held ranking months 1926-12..2026-07) |
| Power: sd 14.56%, NW/iid 0.95, MDE 3.38 / 4.80% a year, Sharpe 0.232 / 0.330, planned 0.347–0.384 | 7 | 7 |
| Return-unit label (MDE80 4.799 > 2) on M1a, M1b rows | 2 | 2 |
| Month counts 433 / 373 / 806 / 800 / 427 / 385 / 1,191 / 1,185 | 8 | 8 |
| Commit hashes and times in the timeline (`7c0c156` 15:22, `f534c99` 15:29, `c7753a5`/`d0b18cd` 15:31, `fc2e1cc`/`0ab2ab2` 15:34–15:48, `8ccf310`, `5c40e1b` 16:16, `468c5bd`, run 16:17:35Z) | 11 | 11 (all UTC from `git log`; 2026-10-26 is after the UK clock change, so "London is UTC" holds) |
| Review counts (question review 3 must-fix; design review 3 must-fix, 9 should-fix; code review 1 must-fix) | 4 | 4 |
| Programme count 34 / 598, keyword search no hits, release 202608 | 4 | 4 (from `summary.json` and the manifest; the desk registry itself not checked, as it is private) |
| Root README: point 1, "Latest result", table row | all figures | all |

Not checked: "pushed before the run" (no remote access by instruction); the desk registry count of 598 (private file, not in the clone); results of the other studies in point 1 of the root README (only the 2+5+1+2+1 = 11 tally and 011's place in it were checked).

## Must-fix

**M1. The first-paragraph disclosure is incomplete against PREREGISTRATION §2.4.** §2.4 lists "later uses of the library's pre-1963 industry months for related rules (check (a), search summaries only, **including a ranking study on 10 industries from 1926**)". The note says: "that later work has used the library's pre-1963 industry months for related rules (known from abstracts and search summaries only)". It leaves out the one item closest to this study: a *ranking* rule on the library's industries from 1926 (Faber 2010, by summary; QUESTION.md §3.1). §9.5 requires the first paragraph to carry the §2.4 disclosure. Fix: "...for related rules, including a ranking study on the library's 10 industries from 1926 (known from search summaries only)...". The other items (MG99 1963–1995, crashes 1932 and 2009, the 1929–32 fall, post-publication decay, nothing seen, no episode used) are all present.

## Should-fix

**S1. Root README, companions without the return-unit label.** §9.5 says "any row that is not 'not supported' adds '(Sharpe units; the 2%-a-year bar not met)'". The root README's "Both registered companions meet all four criteria on their own (30 industries: +5.03% a year, t 2.78; twelve-month formation: +4.63%, t 2.23)" and the table row's "both companions meet the criteria (t 2.78, 2.23)" leave the label out. The note itself carries it.

**S2. Overclaim in the paper comparison.** "so the library's 17 industries are a weaker version of the paper's 20, not a stronger one." M1's gross mean over M is 0.289% a month with an NW standard error of 0.179. The paper's 0.43 is 0.79 standard errors away, from a different classification and with the paper's own sampling error on top. That supports "earned less on this window", not a general claim that one set is weaker. Suggest: "...earned less than the paper on its own window (0.29% against 0.43% a month before costs, a gap under one standard error), so this variant gives no sign of being stronger than the paper's rule."

**S3. The twelve worst months are over the full history, not O, and the note does not say so.** "**The twelve worst months of d:** 1932-07 −34.06%, ... 1986-09 −10.99%, 1987-10 −10.47%, 1980-03 −10.36%." The last three fall in M, outside the decision row. The paragraph sits beside O-only figures (skewness −1.28 and kurtosis 12.7 are on O; the full history gives −1.14 and 12.3). Label it "(full history, base costs)". On O alone, the 10th to 12th worst are 2002-11 −10.14%, 2023-01 −10.03% and 2012-01 −9.60%. The "What did not work" bullet ("three of the twelve worst in 2008–09") stays true either way.

**S4. "Before 1962 the library's universe is NYSE firms only."** PREREGISTRATION §2(c) and §10 row 6 call this general knowledge, not read from the library, and pitfall 6 says "the note says so (general knowledge)". The note states it as fact. Add "(general knowledge, not read from the library)".

**S5. Root README disclosure is broader than §2.4 allows, and partial.** "had not seen any industry's past returns outside the paper's window" claims more than §2.4 ("any industry's six- or twelve-month return over 1926–1963 or 1995–2026, nor any ranking on them"). It also drops the 1929–32 fall, post-publication decay and the 10-industry ranking study. As a summary it need not be complete, but it should not claim more than §2.4 does: use "six- or twelve-month returns".

**S6. Root README table row does not say "variant".** §9.5: "every verdict says the rule is a variant of [MG99]'s". The table row's rule cell ("Top three minus bottom three of 17 US industries ... months outside [MG99]'s 1963–1995 sample") gives a verdict without the word. Add "(a variant of [MG99]'s)".

**S7. Root README "The test can only see an edge of about 4.8% a year in return units".** 4.8% is the 80%-power MDE; at t = 2 the MDE is 3.38% a year, and the observed 3.45% was in fact seen at t 2.04. Say "can see reliably (80% power) only an edge of about 4.8% a year".

## Notes (no change required)

- N1. **The variance floor does not decide the verdict.** Without the floor, M1's DSR at N = 3 is 0.945, still below 0.95. M1a and M1b: 0.986 and 0.969. The floor (Study 001 §9.4) was applied because the three trials' annualised Sharpe spread, 0.038, is below 0.05. The note says "applied" but not that it is not decisive; a dated addition could say so.
- N2. The DSR at N = 11, 34 and 598 uses the variance across this study's three trials (floored), not across the 11, 34 or 598 trials. That is the code's convention and §9.4 does not say otherwise. These rows carry no weight, but a reader may assume otherwise.
- N3. "Turnover is about 6.1 units ... for M1 and M1a and 4.3 for M1b" is over the full history (`turnover_per_year`); on O it is 6.06 / 6.04 / 4.23 (M1a rounds to 6.0). The cost figures beside it (0.6 / 0.4 / 3.0 / 2.1) are on O. The window is not stated.
- N4. The two-stretch NW t (2.0424) and the naive t on the concatenated series (2.0417) differ only in the fourth decimal; C2 does not hinge on the §9.3 adaptation. The stationary bootstrap CI treats O as one series, so its blocks can span the 1963/1995 join; this is negligible but not stated.
- N5. "code and 21 tests on synthetic series (`fc2e1cc`, `0ab2ab2`)": the 21 are 5 data-step tests (`c7753a5`), 9 rule tests and 7 history tests. The 7th history test (the crash test) was added in `8ccf310`. At `0ab2ab2` there were 20. Accurate as a total, loose as attribution.
- N6. "which flatters every figure on this page": the unpriced drift and rebalancing flatter the net d figures, not the gross paper comparison or EW. The note also omits the unpriced reset to equal weights within each leg (§6.3), though "drift within a month" largely covers it.
- N7. "No decade from the 1970s on has t above 1.30" (root): the 2020s t is 1.2994, so this is true. The note's "t between 0.24 and 1.30" and "every decade from the 1970s to the 2010s has t below 1.1" (max 1.03) are also right.
- N8. "supported" never appears in the note except as "not supported"; the note says the rule is a variant of [MG99]'s in the verdict paragraph; "ten earlier studies" and "only N = 3 decides" come before any result (§9.4). All compliant.
- N9. The decades, worst months and episodes use base-cost d (CODE_REVIEW notes this choice). The episode sums before costs would be −3.74% and −25.22%.
