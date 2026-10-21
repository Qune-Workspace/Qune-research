# Trial log: Study 001, term-spread duration switch

Owner approval of the symbol list (IEF, BIL) and of PREREGISTRATION.md v1.0: **given 2026-10-21** (§14 step 1; recorded in `APPROVED`).

Every trial is logged here before it is run (§7). The deflated Sharpe ratio uses the number of rows in this table, N = 3 at registration. Any further rule, parameter or sub-sample choice is appended with a date before it is run and N increases.

| ID | Date logged | Description | Date run | Code commit |
|---|---|---|---|---|
| T1 | 2026-10-21 | Primary: month-end sign of the 10-year minus 3-month spread (bond-equivalent basis); IEF if positive, BIL otherwise (§6.1) | registered 2026-10-21, not run | — |
| T2 | 2026-10-21 | V1: mean of the last 21 valid daily spreads ending on the signal date, same threshold (§7) | registered 2026-10-21, not run | — |
| T3 | 2026-10-21 | V2: carry including roll-down, spread + D_mod(DGS10) × (DGS10 − DGS7)/3, from 1969-07 (§7) | registered 2026-10-21, not run | — |

No return of any rule or benchmark has been computed on real data as of 2026-10-21. The study halted permanently at the §5.3 data validation on 2026-10-21 (second and final run, A4 failed; §16), so T1, T2 and T3 were never run. The table is kept so that the registered trial count N = 3 remains on record.
