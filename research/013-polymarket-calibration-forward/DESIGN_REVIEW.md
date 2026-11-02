# Study 013: separate-session design review of the pre-registration, before commit

*2026-11-02, 12:2x–12:3xZ by the clock. Reviewer: a separate Opus 5.5 session, isolated and read-only, no network. It was briefed to check the draft `PREREGISTRATION.md` and `trials.md` against `QUESTION.md`, `collector.py` (the fields a snapshot row holds), `tools/power_pm013.txt`, `tools/pm_data_terms.md`, METHODS §1–§2 and Study 011's pre-registration and design review; to open nothing under `data/raw/` or `tools/data/`; and to change nothing. It read no snapshot row and edited nothing (its own report lists the git state before and after: the two drafts untracked throughout). The summary below is Qune's; the reviewer's report was written to a file outside the repository and read from there. Every must-fix and should-fix point was changed in the draft before the first commit, so the committed pre-registration is the fixed one. Qune recomputed the arithmetic behind must-fix 1 and 3 before taking them.*

## Verdict: approve with changes

## Passed

- Question, H1/H0, test object, the three trials, the fragility clause and N = 3 match `QUESTION.md` §1.
- The first-token switch leaves b unchanged (y → 1 − y and x → −x flip only a's sign).
- S0 is excluded by "dated on or after S"; the trials.md S0 figures match `snapshots.csv`; the question note's commit hash and time match git.
- The C1a tag and the cluster come from the snapshot-of-record row, not from post-resolution metadata.
- Every field of §6.2–§6.4 is in the collector's whitelist or added by its `strip()`; t_s comes from `started_utc`.
- C1–C4 and the verdict rows are decidable from b̂, SE_cl and the W1/W2 fits; the precedence is complete.
- No raw response or per-market row is committed; the outputs are aggregates, as the `derived` verdict's conditions require.
- British spelling; no private path, secret or personal information.

## Must-fix (all fixed before commit)

| # | Draft said | Problem | Fix |
|---|---|---|---|
| 1 | §5.4 "42 of the 57 snapshot days from S to 2026-12-29"; §14 "2026-12-29, the last that can serve C1" | a market closing before 2026-12-30 00:00Z needs t_s ≤ T − 24 h, before 2026-12-29 00:00Z, and that day's snapshot starts at 04:40Z, so it can never serve C1; the last is 12-28 (56 days; 42 = 0.75 × 56); C1b's last is 12-22 | 56 days S to 2026-12-28; C1b to 12-22; §14 step 2 |
| 2 | a snapshot "whose rows lack a field of §6.3" is excluded whole | the collector writes every whitelisted key, null when absent, so a dropped field is indistinguishable from an ordinary null; the trigger was undecidable | trigger: a §6.3 field null on every row of the snapshot; counted as a gap day |
| 3 | low-power label if "the recomputed ratio exceeds 0.50"; §5.4 "below 5,000 markets or 2,000 events the ratio exceeds 1 under every E" | the ratio's unit (markets or clusters), E and K were unstated; the claim holds for 2,000 events (1.22 / 1.13 / 1.05) but not for 5,000 markets (0.77 / 0.71 / 0.66) | ratio = 2.842 / √(G · Ê) / 0.112, G the C1 clusters, Ê measured over the data-step sample (§9.6); the 5,000-market floor keeps its own reason (500 markets a bin) |
| 4 | horizon measured back from `closedTime`; post-event prices guarded by t_s ≤ `endDate` and no UMA status | `closedTime` depends on the outcome for markets that can resolve early; a proposal lagging the event by more than h puts a decided price into the snapshot of record while §6.3 passes the row; prices of 0.95–0.99 on decided markets push b̂ towards H1; size unknown | §10 row 15 and a §9.6 early-close split (flag fixed at the data step with no outcome read; descriptive, not a trial; early closes kept, since removing them would select on the outcome) |
| 5 | §0 listed ten points | unlisted departures from the note: the gap cap; the §6.3 rules beyond floor and spread; y redefined from "YES won" to the first token; the window starting the day after S; the multi-event cluster rule | each listed in §0 with its reason (now fifteen points) |
| 6 | cluster = "the smallest `eventIds` entry" | the collector sorts ids as strings ("1000" < "999"), an implementer's choice | numerically smallest, ids parsed as integers; the fallback stated |
| 7 | resolution-fetch responses "hashed into a manifest, kept git-ignored" | kept bodies would be a third file holding `outcomePrices` and `winner`, defeating the two-file separation | bodies hashed, not kept; the fetch prints no outcome field |
| 8 | the §5.4 amendment "may only change how gaps or a changed field are handled" | nothing said what follows a §6.2-check failure or a sample-size stop, and no amendment could remedy them | a permanent halt with the verdict "inconclusive (halted at the data step)", as METHODS §1.3 provides; a verdict row added |

## Should-fix (all taken)

1. The terms re-read of 2026-11-02 12:24Z recorded as a dated row in `tools/pm_data_terms.md`, committed with the pre-registration and cited in the header. 2. The snapshot-of-record rule rewritten without the circular "if missing" clause. 3. A push after 2026-11-03 04:40Z excludes that day's snapshot like S0 (§14 step 1). 4. A snapshot with `distinct_markets` below half the window's median is a gap day (a cut page cap looks complete to the collector). 5. The consecutive-gap rule given as dates for C1 and C1b. 6. The data-step sample keeps every windowed, eligible market whatever its UMA status; the §6.2 check runs over the C1 data-step sample; UMA status read from `status.jsonl`. 7. The JSON-encoded list fields decoded first; the outcome match on decimal values exactly 1 and 0. 8. The sandwich formula, the convergence rule, the bootstrap level, generator and failed-resample rule written out (§9.3). 9. Tag-family precedence and source stated. 10. "may be higher" (an Ê above 0.2159 lowers the ratio). 11. Sports share corrected: 38.8 percent of clean parent events, 55.2 percent of clean markets (August–October rows). 12. C1b's first eligible close as t_s(S) + 168 h. 13. `results/sample.jsonl` added to `.gitignore`; the resolution files placed under `data/raw/`; no raw venue field name as a key of `data_step.json`. 14. The trials.md review row written after the fixes.

## Arithmetic recomputed by the reviewer

z at 0.05/3 = 2.128 and at 0.05/12 = 2.638; N = 12 (001–011 and 013; 012 closed unopened); window 56 days, halves 28 and 28; n 44,694 → MDE 0.0289 → ratio 0.26, C1a 0.0370 → 0.33; K 2.842 / 2.486; b = 1.02 at p = 0.35 → 0.3472 (0.28 points lower); ratio above 1 below 2,000 clusters (1.22 / 1.13 / 1.05): all matched. Two did not: the 57-day count (must-fix 1) and the 5,000-market claim (must-fix 3); both fixed.

## Notes taken

- The kept outcome labels can name a team or a candidate, so "no wording" in §2.4 means no question text; stated there.
- The review itself recorded that the git state changed during its run by another process (the terms-file row at 12:24Z and the wait-line commit `4a4ac55` at 12:28Z); both were this learning run's own commits, not the reviewer's.
