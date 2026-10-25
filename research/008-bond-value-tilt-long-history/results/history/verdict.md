# Study 008 history run (§8.1, §9), run once

**Verdict for T1 (the headline): not supported**.

| Trial | Role | Own row | C1 | C2 | C3 (N=17) | C4 | Sharpe | B1 | B3 | NW t vs B3 | DSR N=17 | N=3 | N=10 | w̄ | Turnover |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | primary | not supported | False | False | True | True | 0.415 | 0.382 | 0.381 | 1.38 | 0.988 | 0.996 | 0.991 | 0.4662 | 23.83 |
| T1a | companion | not supported | False | False | True | True | 0.448 | 0.382 | 0.381 | 1.78 | 0.994 | 0.998 | 0.996 | 0.4483 | 21.89 |
| T1b | companion | not supported | False | False | True | True | 0.388 | 0.406 | 0.405 | 0.91 | 0.976 | 0.989 | 0.980 | 0.4008 | 32.70 |

Era row (T1, execution months 1986-01 to 2018-12, 396 periods): mean(T1 − B3) -0.06% a year, pass False (sign only; NW t -0.18, reported, not tested).

Periods: {'T1': 534, 'T1a': 534, 'T1b': 474}. sigma 7.81% (bar 10.18%). Family count 17 decides C3 (§9.4). Hold periods: {'T1': [], 'T1a': [], 'T1b': []}.

T1 on T1b's periods (descriptive): mean(T1 − B3) 0.61% a year, NW t 1.33.

Mechanism, leg excess return a year by quintile of T1's weight: Q1 0.84% (n 107); Q2 1.27% (n 107); Q3 2.08% (n 106); Q4 3.83% (n 107); Q5 6.88% (n 107); by the sign of the real yield: r_le_0 1.30% (n 76); r_gt_0 3.26% (n 458).

Power, realised (T1): NW/iid ratio 1.095 (assumed 0.972); sd(w − w̄) 0.270 (design 0.5, uniform rank 0.289); MDE 0.82% a year at t = 2, 1.16% at 80% power (K 2.842).

Overlap after the fact: corr(d T1, d Study 007 T1) 0.193 over 534 periods.

Run 2026-10-25T21:19:39Z, code 031c134.
