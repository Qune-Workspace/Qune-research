# Study 006 history run (§8.1, §9), run once

**Verdict for T1: inconclusive (fragile)** (gate redesigned after Study 002's halt (cold read, point 7)).

| Trial | C1 | C2 | C3 | C4 | Sharpe | NW t vs B3 | DSR N=3 |
|---|---|---|---|---|---|---|---|
| T1 | True | True | True | True | 0.463 | 2.06 | 0.999 |
| T2 | True | False | True | True | 0.463 | 1.97 | 0.999 |
| T3 | True | False | True | True | 0.468 | 1.91 | 0.999 |

B1 Sharpe 0.338, B3 Sharpe 0.338 at frozen w 0.8702; 593 periods; T1 switches 27; sigma 7.75% (bar 10.18%).

Observed NW/iid ratio for T1 − B3: 0.963 (assumed 0.972). Programme-level family count 3 (descriptive).

Run 2026-10-25T03:24:57Z, code abb7023.
