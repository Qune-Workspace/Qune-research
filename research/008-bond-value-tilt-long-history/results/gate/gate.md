# Study 008 gate (§5.3) and overlap check (§5.6), run once

**PASS**

| Trial | Role | Periods | mean w | Turnover | G1, \|mean(e)\| × 12 | Bound | G1 pass |
|---|---|---|---|---|---|---|---|
| T1 | primary | 192 | 0.257 | 8.99 | 0.021% a year | ≤ 0.180% | True |
| T1a | companion | 192 | 0.228 | 6.44 | 0.024% a year | ≤ 0.180% | True |
| T1b | companion | 192 | 0.326 | 14.69 | 0.062% a year | ≤ 0.180% | True |

G2, sd(g) / sd(x_ETF): inherited as observed from Study 006 (0.131); reproduced here 0.131409 (|diff| 0.0e+00 ≤ 1e-12); bound ≤ 0.32; pass True.

Dropped before any return: none. Proceeding: T1, T1a, T1b.

Overlap with Studies 006 and 007 (§5.6), signal paths over T1's test-window periods:

| Trial | Periods | corr(w, 007 T1 weight) | corr(w, 006 T1 in IEF) |
|---|---|---|---|
| T1 | 534 | 0.115 | 0.161 |
| T1a | 534 | -0.014 | 0.115 |
| T1b | 474 | 0.085 | 0.088 |

Flag (> 0.8 for T1): none; the note's headline states non-independence: False.

Descriptive, no decision weight, by the execution year of the period:

| Trial | Split | Periods | mean w | Turnover | G1 |
|---|---|---|---|---|---|
| T1 | 2002-2007 | 60 | 0.270 | 3.22 | 0.028% |
| T1 | 2008-2018 | 132 | 0.251 | 5.74 | 0.046% |
| T1a | 2002-2007 | 60 | 0.356 | 2.72 | 0.026% |
| T1a | 2008-2018 | 132 | 0.169 | 3.71 | 0.006% |
| T1b | 2002-2007 | 60 | 0.179 | 4.57 | 0.062% |
| T1b | 2008-2018 | 132 | 0.393 | 10.10 | 0.099% |

Level gap mean(g) × 12 0.002% (cancels in e); corr(g, x_ETF) 0.223. Real yields from 1969-07; first weight month {'T1': '1974-06', 'T1a': '1974-06', 'T1b': '1979-06'}; undefined real-yield months to 2018-12: {'CPIAUCNS': [], 'CPILFENS': []}.

Run 2026-10-25T20:43:56Z, code e9169dd. No rule or benchmark return computed.
