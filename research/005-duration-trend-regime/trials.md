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
| Code, first part (§14 step 2) | 2026-10-23 10:5x London | `src/` (five frozen Study 003 modules + `config`, `regime`, `conditional`, `edge`, `forward`, `pipeline`, `checks`, `data`) and `tests/` (20 tests incl. §5.3.5 (i)–(viii); (i) passed against Study 003's committed file to 1e−10 on this machine); CI matrix entry; §16 layout entry. Not yet: `report.py`, `reproduce.sh`, `APPROVED`. No fetch, no check, no correlation of real data beyond test (i)'s reproduction of Study 003's own public column, no return of this study. |

| Code, second part (§14 step 2 complete) | 2026-10-23 11:2x London | `src/report.py` (`--insample`, `--episode`; T1–T3 on their regimes, B0–B3, both cost cases, the edge statistics, the §9.5 row, the §9.7 tables), `src/data.py` fetch commands, `reproduce.sh` (`--check`, `--insample`, `--episode`; `--forward` refuses until §14 step 11), 7 report tests (27 in the suite, all passing), `APPROVED` written in the same commit after `reproduce.sh --check` had refused without it (exit 1, observed). §16 layout entry. No fetch, no check, no correlation of real data beyond test (i), no return of this study. |

| Fetch 1 logged (§5.3.3 step 1, §14 step 3) | 2026-10-23 11:2x London | Alpaca SPY daily bars 2018-09-01 to 2026-09-30, `adjustment='all'`, through `python -m src.data fetch-alpaca-spy` with the desk's existing paper credential read from its file into the environment for the one process (never printed). Attempt 1 of 2; branch S after a second failure on a separate run. Logged before the fetch runs; outcome in the next row. |

In-sample returns of this study have not been computed. The 2019–2026 window is the hypothesis-generating episode (§8.2), to be run once under that label after the in-sample results are committed, with no decision weight. The forward record starts at the first month-end after the note's publication (§11). N = 3.
