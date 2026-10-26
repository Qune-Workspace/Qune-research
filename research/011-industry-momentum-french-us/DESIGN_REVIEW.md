# Study 011: separate-session design review of the pre-registration, before commit

*2026-10-26, 15:2xZ by the clock. Reviewer: a separate Opus 5.5 session, isolated and read-only. It was briefed to check the draft `PREREGISTRATION.md` and `trials.md` against `QUESTION.md`, `QUESTION_REVIEW.md`, `tools/power_industry.py`/`.txt`, Study 001 §9.3–§9.5, Study 010's pre-registration and design review, and the source paper's extracted text. It was told not to download or read any industry data file. It read none and edited nothing. The summary below is Qune's. Every must-fix and should-fix point was changed in the draft before the first commit, so the committed pre-registration is the fixed one.*

## Verdict: approve with changes

## Passed

- Consistency with `QUESTION.md`: the rule, d_t, M1/M1a/M1b, I1/I2/O/M/full, the window rule, the fragility clause, N = 3 and the vintage plan match; departures are listed in §0 (after the fixes below).
- Verdict table: C1–C4 suit a zero-investment rule tested against zero; the window row, precedence and companion rows match the note and Study 010; the return-unit label agrees with the note's sd bar (5.77% / 5.21%).
- Arithmetic recomputed: month counts 433, 373, 806, 385, 1,191, 427, 800; first full holding months 1927-06 (M1, M1a) and 1927-12 (M1b); every power pair; forward 2.842/√5 = 1.271 (1.408 at nw 1.108), 3.66–3.67 times O's; Sharpe 0.244 for t = 2 on 806 months; 2/(6n) per replaced member.
- The paper: "approximately 75 basis points per dollar of one-way long or short transactions" and the sample quoted correctly. British spelling; no private paths or secrets.
- Data step: the file names and the value-weighted monthly section are right as far as the reviewer knows the library (confirmed at the data step).

## Must-fix (all fixed before commit)

| # | Draft said | Problem | Fix |
|---|---|---|---|
| 1 | §11: forward rows committed after the first release containing month t − 1 are "late" | the cohort can only be computed from that release, so every row would be late | late = committed after the first release containing month t, as in Study 010; first forward month's cost from the history's last weights |
| 2 | §5.4: stop if fewer than 12 of 17 (20 of 30) industries have a value in a month | the note's stop is on *eligible* industries (all formation months present); a per-month count does not bound that | stop on eligibility at every ranking month whose cohort is held in any row, counted from the marker flags for F = 6 and 12; the per-month count reported |
| 3 | §2(d): a six-month hold is "near the edge" of where the paper reports profits | over-claim: the paper says profits dissipate after 12 months and calls long-run reversals economically small | reworded to what the paper says |

## Should-fix (all taken)

4. Ties: a sort key (−round(R, 10), column index) instead of a non-transitive tolerance; boundary near-ties counted. 5. Two-stretch Newey–West demeaned by O's overall mean; the other rows use the ordinary estimator. 6. EW_t defined as the mean over the set's industries with a value in month t. 7. w_i,t follows the nominal formula whatever is missing; an empty-leg cohort keeps its weights for costs. 8. The formation length renamed F (L is the losers' set). 9. §0 lists the two departures from the note's eligibility sentence. 10. "About 0.24 at nw 1.00 (0.27 at 1.108)". 11. Stops for a duplicated or out-of-order month and a missing or renamed section header. 12. `trials.md` time label from git (15:22:57Z).

## Notes taken

- Marker fields compared as stripped strings, so no value is parsed as a number (§5.3).
- At the data step: confirm the section title, the release line format and that each file's last column is "Other".
