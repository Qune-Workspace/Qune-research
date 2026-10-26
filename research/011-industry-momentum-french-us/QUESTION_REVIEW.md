# Study 011: separate-session check of the question note, before commit

*2026-10-26, 15:2xZ by the clock. Reviewer: a separate Opus 5.5 session, isolated, read-only, briefed to check the draft `QUESTION.md` against the text extracted from the source paper ([MG99], the archived published article; SHA-256 confirmed by the reviewer), `tools/power_industry.py`/`.txt`, the agenda's three dated additions of 2026-10-26 and Study 010's note as precedent, and told not to download or read any industry data file. Besides those, the reviewer read the library's 17-industry detail page (text only, no data). Summary below is Qune's; every point was taken in the draft before the first commit of the note, so the committed note is the fixed one.*

## Passed

- Every quotation attributed to the paper was found in the extracted text with the same meaning: the 20 value-weighted two-digit SIC industries, the Table II rule, 0.43 and 0.40 percent, "(which does not skip a month)", Table III's L and H horizons, the sample sentence, "eliminates the profitability". The t-statistic for 0.43 has no text layer: "unread" is right.
- Every number recomputed: 433, 373, 806, 385, 1,191, 427, 800 months; every detectable Sharpe pair and pool multiple; the sd bar 5.77% / 5.21%; 5.20–5.76% a year at an assumed sd of 15%; 0.43 × 12 = 5.16; every share. First full months 1927-06 (M1) and 1927-12 (M1b) confirmed.
- The d_t formula matches the rule and the paper's own example of a January 1992 return built from cohorts ranked July to December 1991.
- British spelling; no private paths or secrets.

## Must-fix (all fixed before commit)

| # | Draft said | Problem | Fix |
|---|---|---|---|
| 1 | the paper copy's SHA-256 ends `e01684` | that is the tail of a different, small file in the same working folder; the archived article's hash ends `8721d9`, as in `tools/power_industry.py` | corrected |
| 2 | the window rule is "Study 010's rule kept" | Study 010 decided on its full history and used the outside months only as a condition; deciding on the outside months is stricter | stated as check (d)'s wording and a departure from 010, with the reason (806 months can see 0.347, 010's 560 could see only 0.416) |
| 3 | I2 = "the post-publication months"; verdict "supported before publication only" | the paper was published in 1999, so I2 (from 1995-08) is after the sample, not after publication | I2 labelled "after the paper's sample"; verdict renamed "inconclusive (one side of the paper's sample only)", now applied to I1 or I2 |

## Should-fix (all taken)

4. "Strong at 3 to 12 months, diminish beyond a year" describes Jegadeesh and Titman's individual-stock results, which the paper calls its results "consistent with": reworded. 5. Check (c) now adds that [MG99] formed its industries monthly from CRSP codes that "allow for time-variation"; the library reassigns once a year. 6. The library's "Other" group is ranked like any industry ([MG99]'s list includes "20. Other"). 7. An eligibility stop line for the 30-industry set (fewer than 20 of 30). 8. W(m) and L(m) defined by ranking month. 9. O is two stretches: Newey–West lags do not bridge the gap; I2's first cohorts are ranked on formation months that include the paper's window. 10. IM(1,1): "remarkably strong" quoted instead of "the paper's strongest horizon".

## Notes

- Check (a) rests on search summaries; the two queries are now listed in the note so the re-run can be repeated.
