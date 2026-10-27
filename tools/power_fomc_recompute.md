# Separate-session recomputation of tools/power_fomc.py

Run 2026-10-27 21:1xZ–21:2xZ by the clock (about two minutes): a separate Opus 5.5 session, isolated, read-only, given the uncommitted tool and output, the staff-report PDF and the Fed's calendar pages; it extracted the paper's text itself and counted the meetings from the Fed's yearly pages. Its report, condensed, then how each point was taken before the first commit.

**Verdict: MATCH WITH FINDINGS.** All 33 printed numbers recomputed exactly; the PDF hash matched; every quote and Table 1 number found; Crossref metadata for both DOIs matched. The meeting count was one too high.

- Quotes: the Table 1 note (sample 1994:09-2011:03; SPX-2pm and SPX definitions); post-1994 pre-FOMC column SPX-2pm .488 / 1.215 / 131 and SPX .338 / 1.144 / 132; "for the 131 FOMC observations ... 49 basis points, with a t-statistic of more than 4.5 based on Huber-White standard errors"; "about 33 basis points"; "...Sharpe Ratio of 0.84" (the ellipsis drops "still remains highly significant and"). The paper annualises Sharpe at sqrt(8) per meeting, so the tool's convention matches its 0.84.
- Numbers checked (reviewer's own arithmetic): plain t 4.60 / 3.39, Sharpe 1.136 / 0.836; every minimum detectable mean and multiple at N = 124 and N = 40; Sharpe MDE 0.722 / 0.800 and 1.271 / 1.408; meetings needed 51 and 93. K = 2 + z(0.80) = 2.8416. 1.108 present in `tools/power_offduration.txt`.
- Meetings held, 2011-04..2026-09: 2011 six (Aug 1 and Nov 28 conference calls); 2012–2019 eight each (unscheduled Oct 2013, Mar 2014, Oct 2019 excluded); **2020 seven** (Mar 17-18 cancelled; Mar 2 and Mar 15 unscheduled); 2021–2025 eight each (Aug 22 2025 notation vote excluded); 2026 six. Total 123.

| # | Class | Finding | Taken |
|---|---|---|---|
| 1 | must-fix | N = 124 assumed eight meetings in 2020; the scheduled Mar 17-18 2020 meeting was cancelled. | Qune read the 2020 page ("March 17-18 (cancelled)"); N = 123 with the count by year in the docstring; output rerun (0.310 → 0.311, 0.292 → 0.293, Sharpe MDE 0.722 → 0.725). |
| 2 | should-fix | The later paper's title signals a result (a decline), not only that the window was read; that it covers the window is inferred. | Docstring says so: direction of the prior known before any question is fixed; its sample not checked. |
| 3 | should-fix | Sharpe table compared only with the close-to-close 0.84, not the 2pm 1.136. | 2pm comparison added (0.64x after the sample, 1.12x forward). |
| 4 | note | 11.625 years printed as 11.6 (round-half-even). | Printed to three decimals. |
| 5 | note | Normal K slightly understates the need at N = 40. | Stated in the docstring: forward figures, if anything, optimistic. |
| 6 | note | The 1.108 sensitivity is in the Sharpe table only. | Said so in the docstring. |
| 7 | note | Statement times after 2011 may fall inside a 2pm-to-2pm window on some days (reviewer's memory, not checked). | Flagged in the docstring as not checked, for any later data step; power figures unaffected. |

The fixed output was not re-reviewed.
