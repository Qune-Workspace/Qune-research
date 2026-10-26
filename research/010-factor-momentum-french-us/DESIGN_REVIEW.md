# Study 010: separate-session design review of the pre-registration, before commit

*2026-10-26, reviewer's clock 08:18:56Z to 08:21:05Z. Reviewer: a separate Opus 5.5 session, isolated and read-only. It was briefed to check the draft `PREREGISTRATION.md` and `trials.md` against `QUESTION.md`, `QUESTION_REVIEW.md`, `tools/power_study010.py`/`.txt`, Study 001 §9.3–§9.5 and the Study 008 and 009 templates. It was told not to download or read any factor data file. It read none and edited nothing. The summary below is Qune's. Every must-fix and should-fix point was changed in the draft before the first commit, so the committed pre-registration is the fixed one.*

## Verdict: approve with changes

## Passed

- Arithmetic, recomputed by the reviewer:
  - Month counts 1,190, 432, 630, 128 and 560; 618 strategy months.
  - The 54 months from 1927-07 to 1931-12.
  - Every power figure against `power_study010.txt`.
  - Entry dates: SMB, HML and ST_Rev from 1927-07; LT_Rev from 1932-01 with 12-month formation and from 1931-07 with 6-month formation.
  - Cost formula: 2|Δh| gives 4c per flip and 2c on entry.
- Consistency with `QUESTION.md`: factor set, trials, windows, window rule, and B1 with a varying K_t.
- Criteria C1–C4 match Study 001 §9.5, with B1 and B3 taken per trial. The precedence of the verdict table is coherent.

## Must-fix (all fixed before commit)

| # | Draft said | Problem | Fix |
|---|---|---|---|
| 1 | Missing data "Outside H: not used"; the stop rule covered missing-value markers inside H only | The formation months before H (from 1926-07) are used. A marker or a missing row there would quietly move a factor's entry. Month gaps were recorded but did not trigger a stop. | §5.4 now stops on any marker **or month gap** from 1926-07 (SMB, HML, ST_Rev) or from 1931-01 (LT_Rev) to H's end. §6.5 reworded to match. |
| 2 | The stop rule fired only if a file started *later* than stated; entry dates were "confirmed at the data step" | An earlier start left the code free to choose between fixed and data-derived entry dates. | Stop if any start month differs in either direction. Entry dates are fixed by the document, not derived from the files. |
| 3 | Forward rows committed after the release containing month t were to be "excluded from scoring" | This is a gaming channel. Positions are committed weeks into month t, so delaying a commit would drop a month whose market the operator can already see. | Every forward month is scored. Late rows are labelled and counted, not dropped. The committed h is scored. The h recomputed from the scoring release is shown in the vintage row. |
| 4 | The forward record did not say which trials it records or how B3's h̄ is set | This was a free choice at scoring. | T1, T1a and T1b are recorded. B3 uses h̄ frozen from H and is never re-estimated. |

## Should-fix (all taken)

1. The forward record's power is now stated: 60 months can detect a Sharpe of d of 1.27 (1.41 at nw 1.108).
2. Ties: an exact zero is not reliable in floating point. The rule now uses |R| ≤ 10⁻¹² → −1, and ties are counted.
3. Cost units are stated: c enters as 0.10 and 0.50 because T is in percent. The reweighting when K_t changes is stated as not charged.
4. The ±1 versus {0, 1} identity is stated "gross of costs".
5. If every h̄ is zero, C1's B3 leg reads Sharpe(T) ≥ 0.10.
6. The return-unit label's MDE formula is written out: 2.842 × NW s.e. of mean monthly d × 12, at base costs.
7. Reading the private desk registry for the programme-wide count is a departure from `QUESTION.md` §2.2. It is now listed in §0 item 9, with a public-logs-only count beside it.
8. The data step's marker check parses values. The rule now says the parser compares each value with the marker codes and writes nothing else.

## Notes taken

- C3 is computed on T, not on d, by the programme's convention. It can pass partly on the static premium. This is disclosed in §9.4.
- h̄ is unweighted while the factor weights are 1/K_t, which leaves a small residual static exposure in d. It is disclosed in §9.1 and reported per factor.
- The raw files sit on disk between the data step and the history run. This is now §10 row 12.
- In the hit rate, a month with f = 0 counts as a miss.
- The 0.29 edge is the 80%-power detectable size, not a hard floor. This is now worded in §8.
