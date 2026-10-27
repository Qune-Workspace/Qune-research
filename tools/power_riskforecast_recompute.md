# Separate-session recomputation of tools/power_riskforecast.py

Run 2026-10-27 from 00:2xZ by the clock (about two minutes): a separate Opus 5.5 session, isolated, read-only, given the uncommitted tool and output, Study 004's two committed forecast files and the reading the author intended to publish; it wrote its own script outside the repository and looked up the one citation on Crossref. Its report, condensed, then how each point was taken before the first commit.

**Verdict: MATCH WITH FINDINGS.** Every number in `power_riskforecast.txt` recomputed and matching at the printed precision (all twelve rows: n, s, t iid, t NW, nw, d > 0 count, months to see; both S_MDE lines; means, sds, row counts, date ranges, realised-vol medians, the largest QLIKE nw 1.345). Ratios to the in-sample 0.218: 1.68 / 2.26 at N = 60, 1.19 / 1.60 at N = 120. Citation: doi:10.1016/j.jeconom.2010.03.034 resolves to A. J. Patton, "Volatility forecast comparison using imperfect volatility proxies", Journal of Econometrics 160(1), 246–256 (2011).

| # | Class | Finding | Taken |
|---|---|---|---|
| 1 | must-fix | "R2 (shrinkage) shows no effect in either window" claims absence; the numbers show only that none was detected (NW t 0.05 to 1.28, mean d positive in all four rows). Median Ledoit–Wolf intensity is 0.04 in-sample and 0.10 in 2019–2026, so the shrunk forecast is nearly the plain EWMA by construction. | Agenda and README say "no detectable effect (NW t at most 1.28)" and give the intensity medians (0.042 / 0.097, recomputed by Qune). |
| 2 | must-fix | "No risk-property question on the ETF era is fixed at monthly evaluation" is broader than the tool: only three volatility-forecast comparisons were powered; VaR coverage (`var99_exceedances`) was not assessed; "fixed" undefined. | Decision limited to volatility-forecast accuracy (R1–R3), "fixed" defined as "chosen as a forward test"; VaR coverage named as not assessed. |
| 3 | should-fix | Name the loss: the quoted R1 figures are QLIKE; under MSE on variance R1 in-sample has NW t 1.66 and 2019–2026 s 0.173 (529 / 494 months to see). | Both losses stated. |
| 4 | should-fix | "Seeing 0.218 takes about 307 months" uses nw 1.345; at nw 1.00 about 170. | Given as 170–307 months. |
| 5 | should-fix | The upper S_MDE end uses the largest QLIKE nw; the largest nw in the table is 1.875 (R1 in-sample MSE), which would give 0.688 / 0.487. | Stated as a bracket, not a bound, with the MSE figure. |
| 6 | should-fix | R3 is powered within 60 months only for its in-sample size; its 2019–2026 sizes need 61 and 87 months. | Worded that way. |
| 7 | should-fix | "Already answered … no stake" is a judgement next to the tool's own "only forward months are a clean sample". | Worded as a judgement: "answered as far as seen data can answer it". |
| 8 | note | The daily-scoring sentence is a proposal; the archived daily files were not inspected by the reviewer. | Kept as a proposal; Qune checked that `data/raw/` holds the vendor daily files (git-ignored, in the raw-file backup); their power is not computed. |
| 9 | note | Nine flat months dropped from the 2019–2026 file (2018-12-31; 2022-07 to 2023-03 except 2023-01-31), so the 84 months are not contiguous and the HAC treats them as if they were. | Stated in the docstring. |
| 10 | note | Patton's condition is a conditionally unbiased variance proxy (r²), not an unbiased volatility proxy; MSE on variance is also robust, not merely a bracket. | Docstring corrected; the printed output is unchanged. |
