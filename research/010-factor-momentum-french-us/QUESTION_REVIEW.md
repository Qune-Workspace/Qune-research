# Study 010: separate-session check of the question note, before commit

*2026-10-26, 07:2xZ by the clock. Reviewer: a separate Opus 5.5 session, isolated, read-only, briefed to check the draft `QUESTION.md` against the text extracted from the source paper (NBER WP 25551; PDF SHA-256 `00af3d63…fdd3`, confirmed by the reviewer), `tools/power_study010.py`/`.txt` and `tools/power_offduration.txt`, and told not to download or read any factor data file. Besides those, the reviewer read one library detail page (earnings-to-price portfolios; text only, no data). Summary below is Qune's; every point was fixed in the draft before the first commit of the note, so the committed note is the fixed one.*

## Passed

- Every quotation attributed to the paper was found in the extracted text with the same meaning (line references in the reviewer's report: the 15 US factors, "20 non-momentum factors", the rule, monthly rebalancing, the 1963 start, T = 618, 4.2% with t 7.04, the "inconsequential" sentence, the decile construction, 2.8% with t 5.74, Table 1's 6.7%–17.6%). The paper's text also says directly: "We exclude the two stock momentum factors, U.S. and global UMD".
- Month counts 1,190 / 432 / 630 / 128 / 560 and every detectable Sharpe, ratio and sd(d) bar recomputed (e.g. 2.842/√(1190/12) = 0.2854; × 1.108 = 0.3162; 2/0.2854 = 7.01%).
- The claim that d for a ±1 rule is exactly twice d for a {0, 1} rule, each against its own mean position: proved (g = (h + 1)/2 gives g − ḡ = (h − h̄)/2); t and Sharpe ratio are scale-invariant.
- First holding months: 1927-07 (SMB, HML), 1932-01 (LT_Rev).

## Must-fix (all fixed before commit)

| # | Draft said | Problem | Fix |
|---|---|---|---|
| 1 | d_t = (1/3) Σ … | the factor count is 3 to 1931-12, 4 from 1932-01, 2 in T1a | 1/K_t over the factors available |
| 2 | "the paper's other eleven US factors: the library does not publish them before 1963, or at all" | ten, not eleven; earnings to price can be built from deciles from July 1951 | true count and the real reason (none reaches the 1920s; mid-history entry on a chosen construction; value measures close to HML, inferred); disclosed as a departure |
| 3 | the 4.2% "against an equal-weighted portfolio" | the equal-weighted portfolio itself earns 4.21%; the 4.2% is reported beside it, not as an excess | "beside", with the 4.21% quoted |
| 4 | the files are "of the same length within 6 months" | false for LT_Rev, 54 months later | start dates per file; LT_Rev joins in 1932-01 |

## Should-fix (all taken)

5. "No skipped month" is inferred from an example in the paper's equation (1), not stated for the rule: labelled inferred. 6. The paper's "inconsequential" remark concerns long versus short after a losing year, not flat versus short: reworded. 7. Table A2's caption says "annualized" while the magnitudes read as per month: units labelled inferred. 8. A duplicated clause: removed. 9. The list of edges below the detectable size omitted 006's 0.282: added. 10. 630 months is the paper's data window; its strategy months are 618: stated.
