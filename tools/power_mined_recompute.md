# Separate-session recomputation of `tools/power_mined.py` (2026-10-26)

Reviewer: Opus 5.5 sub-agent, isolated, read-only on the repository, no factor return read; it downloaded the two NBER working papers itself and extracted their text with its own standard-library script. Run on the first draft, before commit. Report as returned (local temporary paths replaced by placeholders):

> I found no number mismatches and every quote checked out. There is one must-fix: the output labels MM17's appraisal ratio 0.33 as "Sharpe(d) 0.330". I downloaded the PDFs to `<tmp>` and ran my own stdlib extractor from `<tmp>` with `python3 -I`. Nothing in the repo was edited and no return data was read.
>
> **(1) Numbers (all match)**
> - 2016-01..2026-08 is 128 months, giving 0.870 / 0.964, the same as Study 010's P2 row. Ratios to the pool: 2.71x / 3.00x. Ratios to 0.33: 2.64x / 2.92x.
> - 2013-04..2026-08 is 161 months, giving 0.776 / 0.860, 2.42x / 2.68x and 2.35x / 2.61x.
> - Library spans: 1926-07..2026-08 is 1,202 months and 1927-01..2026-08 is 1,196, matching rows F3/F2.
> - Months needed: 0.33 needs 890 / 1,093 and 0.321 needs 941 / 1,155.
> - K = 2.0 + 0.8416, which is 2.842.
>
> **(2) Quotes and sample windows (all verbatim)**
> - "the sample is 1926-2015 for Mkt, SMB, HML, and Mom": in the Table 1 notes.
> - "an alpha of 4.9%, an Appraisal ratio of 0.33": in the introduction. Table 2's Mkt column also shows 0.33, but a footnote says "The scaled markets' annualized appraisal ratio is 0.34". 4.86/51.39·√12 gives 0.328.
> - "full sample period 1927:01 to 2013:03": in the Figure 1 caption. The paper also says the window has 1,035 months, which checks.
> - Israel and Moskowitz "from 1927 to 1965 and from 1990 to 2012": verbatim.
> - WP dates: April 2016 (MM) and August 2014 (DM), as the docstring says.
>
> **(3) Is the 0.33 anchor fair?**
> Only as a unit comparison. The appraisal ratio is alpha over residual sd against the unmanaged market, with beta 0.61 (Table 1). d is managed minus unmanaged, which also carries −0.39 of the market premium. So the Sharpe of d is likely well below 0.33, and the anchor flatters detectability.
>
> **(4) Fixes**
> - **Must-fix:** the output line `Sharpe(d) 0.330: 890 / 1093 months` presents the appraisal ratio as Sharpe(d). Relabel it `MM17 market appraisal ratio 0.33 (alpha/residual sd vs unmanaged, beta 0.61; not Sharpe of d)`. Rename the column header the same way.
> - **Should-fix:** add to the docstring "paper's footnote gives 0.34 for the same ratio".
> - **Should-fix:** "1926-2015" is a year-only window. MM17's Table 1 has N = 1,065 (Mkt/SMB/HML) and 1,060 (Mom), against 1,074 / 1,068 calendar months. Note "regression months fewer than the calendar span; 2016-01 boundary assumed".
> - **Should-fix:** DM16 builds its own CRSP winner-minus-loser deciles, not French Mom. Note that V3a counts calendar months, not the same series.
>
> **(5) The "no pre-sample window" claim**
> It is right in substance. MM17's N shortfall leaves at most about 9 months (Mkt) or 8 (Mom) possibly unused. The paper doesn't say whether they fall at the start or the end, and early months would be needed as volatility burn-in anyway. DM16 states 1927:01 for the full sample. Some of its regressions start at 1927:06 or 1927:07, and the dynamic-strategy regression runs 1927:07–2013:03, so 1927:01–06 is unused there. That is 6 months that are only burn-in. Saying "no usable pre-sample window (at most ~9 months)" would be exact.

## Response (before commit)

All four points taken: the must-fix label and column header changed (the anchor is now printed as MM17's appraisal ratio, "not Sharpe of d", and the pool's 0.321 is listed first); the docstring gives the 0.34 footnote, the regression counts against the calendar span with the 2016-01 boundary marked as assumed, DM16's own CRSP deciles and its 1927:07 regression start; the pre-sample line now reads "no usable window ... at most ~9 unused months". The agenda's dated addition states that the 0.33 comparison flatters detectability. No figure changed.
