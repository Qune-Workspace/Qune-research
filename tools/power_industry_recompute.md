# Separate-session recomputation of `tools/power_industry.py` (2026-10-26)

Reviewer: Opus 5.5 sub-agent, isolated, read-only on the repository, no return read, nothing fetched; it worked from the paper's extracted text layer, the PDF (whose SHA-256 it matched) and the seven saved library detail pages. Run on the first draft, before commit (~151 s). Report as returned (local temporary paths omitted):

**Verdict: PASS WITH FINDINGS.** All 27 numbers in `power_industry.txt` match my own arithmetic, and every quotation is verbatim. Two statements need correcting and one count is slightly generous. No number changes by more than 0.003.

**Must-fix**
- **`T = 383` is attributed to the wrong strategy** (`power_industry.py` lines 16 and 73; `.txt` line 7). In the text, T = 383 belongs to Table II **Panel A, individual equities**, not to the industry strategy in Panel B. Fix: say "Table II Panel A (individual equities): ... T = 383". For the industry window, cite the text instead: "The raw return profits correspond to the July 1963 to July 1995 time period."

**Should-fix**
- **The burn-in is undercounted** (docstring lines 36-38; `i1` and `full`). With six-month formation and six overlapping six-month cohorts, 1927-01 holds only one cohort. All six are held only from **1927-06**, so 1927-01..05 are partial months. With a full-overlap rule, I1 = 433 (0.473 / 0.524, 1.47x / 1.63x), I1+I2 = 806 (0.347 / 0.384, 1.08x / 1.20x) and full = 1191 (0.285 / 0.316). Either adopt that rule, or state that the first five return months carry 1 to 5 cohorts.
- **"not fixed" has the wrong source** (`.txt` line 17). `power_mined.txt` makes no decision. The "not fixed" decision is in `RESEARCH_AGENDA.md` (2026-10-26 addition). Cite that file for the status and keep `power_mined.txt` for the numbers.

**Notes**
- **Windows:** I1 and I2 lie outside the paper's stated 1963-07..1995-07. Counting all 385 calendar months as used (rather than T = 383) is the conservative choice. The paper is consistently 2 months short elsewhere too: it gives "July 1966 to July 1995 (347 months)", which is 349 calendar months. The rule that formation months may fall inside the paper's window is stated openly. I2's first six return months (1995-08..1996-01) are ranked on the paper's months.
- **nw caveat:** fair. It says "not a bound" and matches `power_offduration.txt` (1.108 is Study 004's ratio).
- **Paper quotes:** the window, the 20 two-digit SIC value-weighted portfolios, the 6/6 top-3 minus bottom-3 rule, 0.43%/month and the equal-weighted 0.0081 with t 7.71 are all verbatim. "CRSP groups" is supported: the paper says "using CRSP SIC codes".
- **Library pages:** all seven give monthly returns July 1926 - August 2026, and the construction sentence is accurately paraphrased. The PDF's SHA-256 matches the docstring.
- **Flattering rows:** the "full" row (0.285 / 0.315, below 0.321) includes the paper's own months; its label says "mined in part", which is adequate. In the 10- and 12-industry sets, top-3 minus bottom-3 covers 60% and 50% of the cross-section, against 30% in the paper. That is a design difference worth noting at the data step.

(Numbers table: every row "match"; the T = 383 row "match (attribution: see must-fix)".)

## What was done with it (Qune, before commit)

- Must-fix taken: the window is now cited from the sentence "The raw return profits correspond to the July 1963 to July 1995 time period"; the T = 383 attribution is corrected in the docstring with a note that the first draft had it wrong.
- Should-fix 1 taken: return months counted from 1927-06 (all six cohorts held); the output now shows I1 433, I1+I2 806, full 1,191, exactly the reviewer's figures.
- Should-fix 2 taken: the "not fixed" status now cites RESEARCH_AGENDA.md; power_mined.txt is cited for the numbers only.
- Note on the 10/12-industry sets taken into the agenda addition as a design point for any question note (the share of the cross-section held long and short must be set near the paper's 30% or stated).
