# Study 006 gate (§5.3), run once

**PASS**

| Check | Value | Bound | Pass |
|---|---|---|---|
| G1, \|mean(e)\| × 12 | 0.008% a year | ≤ 0.180% | True |
| G2, sd(g) / sd(x_ETF) | 0.131 | ≤ 0.32 | True |

192 periods; w_o 0.938; switches 6; signed mean(e) × 12 0.008%; level gap mean(g) × 12 0.002% (cancels in e); corr(g, x_ETF) 0.223.

Descriptive, no decision weight (§5.3.4):

| Subset | Periods | w | G1 | G2 |
|---|---|---|---|---|
| split_2003_2007 | 60 | 0.800 | 0.064% | 0.115 |
| split_2008_2018 | 132 | 1.000 | 0.000% | 0.138 |
| T2 | 192 | 0.948 | 0.009% | 0.131 |
| T3 | 192 | 0.948 | 0.014% | 0.131 |

Run 2026-10-25T03:22:29Z, code 392b7e1. No rule or benchmark return computed.
