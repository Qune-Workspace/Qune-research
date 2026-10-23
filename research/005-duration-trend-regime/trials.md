# Trial log: Study 005, trend exits from duration conditional on the stock-bond correlation regime

Approval: the owner approved Study 001's design and the symbols IEF and BIL on 2026-10-21 and, the same day, delegated all further decisions on this research programme to the orchestrator. This pre-registration is approved by the orchestrator under that delegation on the date of its first commit (header of `PREREGISTRATION.md`). An `APPROVED` file is written at implementation time (§14 step 2), after this commit, so that `reproduce.sh` keeps its refusal gate. No paper order is placed under this study (§11), so no Independent Risk clearance is sought.

Every trial is logged here before it is run (§7). The deflated Sharpe ratio, reported without decision weight in this study, uses the number of rows in this table, N = 3 at registration. Study 003's three trials tested the unconditional rule and are not trials of this hypothesis; Study 003's T1 enters here as benchmark B2 with its path already known to the author (§2.4). Any further regime variable, window, threshold or sub-sample choice is appended with a date before it is run and N increases.

| ID | Date logged | Description | Date run | Code commit |
|---|---|---|---|---|
| T1 | 2026-10-23 | Primary: regime = sign of the Pearson correlation of daily SPY and IEF total returns over the 63 most recent common return days ending at the month-end signal date; in the positive regime apply Study 003's T1 (IEF if its 12-month excess return over cash is positive, else BIL), in the negative regime hold IEF (§6) | not run | — |
| T2 | 2026-10-23 | Descriptive alternative: the same with a 252-day window (§7) | not run | — |
| T3 | 2026-10-23 | Descriptive alternative: regime = FRED CPIAUCNS twelve-month change for month m−2 above 3.0% at the signal date of month m (§7) | not run | — |

## Data-check log (§5.3; instrument returns, correlations and a committed file only; no rule)

| Step | Date | Outcome |
|---|---|---|
| Question note (step 0) | 2026-10-23 08:2x London | `QUESTION.md` committed (b9ad02e) before this document; no fetch, no regime share, no return. |
| Pre-registration committed (§14 step 1) | 2026-10-23 | this commit; no fetch, no check, no correlation, no return computed |

In-sample returns of this study have not been computed. The 2019–2026 window is the hypothesis-generating episode (§8.2), to be run once under that label after the in-sample results are committed, with no decision weight. The forward record starts at the first month-end after the note's publication (§11). N = 3.
