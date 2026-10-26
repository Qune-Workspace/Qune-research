# Separate-session recomputation of tools/power_seasonality.py

Run 2026-10-26 23:2xZ by the clock (about two minutes): a separate Opus 5.5 session, isolated, read-only, given the uncommitted tool and output, the NBER working paper PDF (SHA-256 a273963eeaf32b3acdd15bb0ddfd9d74cc91c7138f8f81956a7d9072d518fc65) and the committed anchors; it extracted the paper's text itself. Its report, condensed, then how each point was taken before the first commit.

**Verdict: ALL MATCH.** Every number in `power_seasonality.txt` recomputed exactly; every quote found in the paper (ignoring ligature noise); the PDF hash matched.

- Quotes: "17 portfolios for Fama-French industries"; "…by their average return in the same calendar month over the prior 20 years"; "…that based on the industry portfolios trade the top two and bottom two portfolios"; "We use monthly data from January 1963 through December 2011"; "the industry strategy earns 0.70% (t-value = 3.79)"; "[However, for] right-hand-side returns we use monthly returns going back to January 1943". The Table 1 industry row's first cell, 0.70 (3.79), is "All months / Same-month return". The paper never says its t-values are adjusted ("Newey", "HAC", "serial", "clustered" do not occur).
- Numbers checked (reviewer's own arithmetic): S_MDE(806) 0.3468 / 0.3842; 588 and 240 months; implied Sharpe 0.5414, sd 4.479% a month / 15.51% a year, mean 8.4% a year; S1 198 months 0.6997 / 0.7752; S2 176 months 0.7421 / 0.8222; S1+S2 374 months 0.5091 / 0.5641; every ratio and return-unit MDE; months needed 940.6 / 1154.8, 1725.6 / 2118.4, 330.6 / 405.9. Anchors present in the named files.
- Start date: 1946-07 is the first month with 20 prior same-calendar-month returns (brute-force search; 1946-06 has only 19 Junes because June 1926 is not in the library). No scorable month precedes everything the paper read.

| # | Class | Finding | Taken |
|---|---|---|---|
| 1 | must-fix | The Reading line said a rule below the "x paper" share "would likely be missed"; at the MDE power is 80%, so it is missed more often than not only below about 0.70 of the MDE (2.0 / 2.842). | Reading line rewritten with the reviewer's wording. |
| 2 | should-fix | S1's label "inputs seen 1943-62" points at the wrong months: S1's scored months themselves were read by the paper as ranking inputs; most of their own ranking inputs (1926-07..1942-12) were not. | Relabelled "scored months read by paper"; docstring says so. |
| 3 | should-fix | S1+S2 mixes seen and fresh months and carries the only ratio below 1. | Relabelled "(S1 seen)"; line added: only S2 (176 months) has outcomes the paper never read. |
| 4 | should-fix | Docstring "for every calendar month first exists" misworded. | Reworded as suggested. |
| 5 | note | "share" though most values exceed 1. | Called a multiple; "above 1 means even the full published edge is below the MDE". |
| 6 | note | Return-unit MDE assumes the paper's plain-t volatility. | Label in the column header and a line under the table. |
| 7 | note | S1c printed −42 months. | Prints 0 with "first scorable 1946-07 is after 1943-01". |
| 8 | note | Table 1's portfolios are value-weighted. | Noted in the docstring. |
