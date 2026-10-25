# Study 006 — Term-spread duration switch on the long history (1969–2018)

**Verdict: inconclusive (fragile)** (pre-registered row, §9.5; history run once on 2026-10-25). *Gate redesigned after Study 002's halt ([cold read](../../COLD_READ.md), point 7).* The rule holds an intermediate Treasury position (a synthetic 8.5-year bond) when the 10-year minus 3-month spread is positive at month end and synthetic bills otherwise. **Over 593 months, August 1969 to December 2018, the primary rule T1 met all four pre-registered criteria**: Sharpe 0.463 against 0.338 for holding the bond (B1) and 0.338 for the same average exposure held throughout (B3, w = 0.870); Newey–West t of the monthly difference to B3 **2.06** (+0.075% a month, about 0.9% a year); deflated Sharpe ratio 0.999 at N = 3; the sign unchanged at double costs (t 2.01). **The two registered variants did not**: the 21-day average of the spread (T2) and the carry-with-roll-down signal (T3) reached t 1.97 and 1.91 against the 2.0 bar, so by the fragility rule written before the run the result is not called supported. The volatility check passed (σ 7.75% a year against a 10.18% bar), so this is not a "low-power" label: the test could see an edge of about 1.5% a year; it could not see one of 1% or less.

**Read this before the numbers.** The verdict is a near miss in both directions: T1 cleared t = 2.0 by 0.06 and its variants missed it by 0.03 and 0.09. Most of the advantage comes from one regime, the rising-rate years 1969–1981 (T1 Sharpe 0.105 against −0.271 for holding the bond); from 1982 to 2008 the rule lagged holding the bond (0.599 against 0.629), and from 2009 to 2018 the curve never inverted at a month end, so the rule simply held the bond. The author knew before the run that the curve inverted in the late 1970s and early 1980s and that rates were most volatile then (§2.4 of the pre-registration). No paper order; the only clean test is the forward record, which starts at the 2026-10-30 month end and is scored once after 60 months, when it can see an edge of about 3% a year (§11.4). Published 2026-10-25; the 2019–2026 episode (no decision weight) and a separate-session recomputation follow.

Everything on this page is a backtest on synthetic constant-maturity series built from FRED yields, after costs. Nothing here is a track record, a forecast or investment advice. The question, the trials, the benchmarks, the criteria, the gate, the volatility bar and the order of operations were fixed in [`PREREGISTRATION.md`](PREREGISTRATION.md) before any file was read (`a67ef8d`); the trial log is [`trials.md`](trials.md).

What happened, in order (every step is a dated commit; times are London, which left BST at 02:00 on this date, so London equals UTC):

1. 2026-10-25, 00:1x: the power bar committed first ([`tools/power_candidate6.txt`](../../tools/power_candidate6.txt), `21f850b`): the test counts only if the duration leg's excess-return volatility is at most 10.18% a year. 01:1x–01:4x: question note (`07962f7`, `1f20f16`).
2. 02:1x–02:20: pre-registration and trial log pushed before any file was read (`a67ef8d`). 02:21: data step, seven files copied from Studies 002 and 004 after a SHA-256 match, dates only (`edec076`).
3. 02:2x–03:2x: code and tests (`e505e28`, `a693069`, `2f1884f`): Study 002's construction, signal, calendar, engine and statistics copied unchanged (14 of 16 modules syntax-identical to `a2b713b`; checked by [`src_provenance.py`](src_provenance.py)); the gate, the volatility check, the history and episode wrappers new; 163 tests. Two §16 clarifications before any run, the second on a sub-period month convention in the copied code (below).
4. 03:22: `APPROVED` and the gate's trial-log row, pushed (`392b7e1`); then **the gate, run once: PASS** (`8286e25`).
5. 03:23: the volatility check's row (`ff50d9f`), then **the volatility check, run once: σ 7.75%, criteria stand** (`9e9d9b5`).
6. 03:23–03:24: T1–T3 run dates and the programme-family re-count logged and pushed (`abb7023`); then **the history run, once** (03:24:57Z), committed as written (`662630c`).
7. This note: the publication (the commit carrying this line).

## The gate (§5.3; instrument returns and the signal path only, no rule return)

The gate asks how much error the synthetic series puts into the quantity the verdict rests on, the monthly differential T1 − B3, over the 192 months in which an ETF exists to compare with (2003–2018): e_t = (h_t − w)·g_t, where h_t is T1's holding and g_t the synthetic-minus-ETF gap in the duration-over-cash return. A gap that is constant cancels in e; only a gap that coincides with the rule's positions moves the decision.

| Check | Observed | Bound | Result |
|---|---|---|---|
| G1, bias: \|mean(e)\| × 12 | 0.008% a year | ≤ 0.18% | pass |
| G2, noise: sd(g) / sd(x_ETF) | 0.131 | ≤ 0.32 | pass |

Beside it, no decision weight: level gap mean(g) × 12 0.002% a year; corr(g, x_ETF) 0.223; 2003–2007 G1 0.064%, G2 0.115; 2008–2018 G1 0.000%, G2 0.138. Full output: [`results/gate/gate.md`](results/gate/gate.md). **What the pass does not show:** T1 held the bond in every period from 2008 to 2018, so the bias check rests on the 12 cash months of 2003–2007, one inversion episode; G2's bound assumed g uncorrelated with the differential and the observed correlation with x_ETF is 0.22, so that bound is approximate; G2 was expected to pass (§5.3.5); and before 2003 there is no ETF, so fidelity in 1969–2002 is an assumption, not a measurement.

## Results: the test window, 1969-08 to 2018-12 (593 months, synthetic legs, base costs 2 bp a side)

| | T1 (spread sign) | T2 (21-day mean) | T3 (carry) | B1 (hold the bond) | B3 (same exposure, w 0.870) | B2 (50/50) |
|---|---|---|---|---|---|---|
| Annual return (geometric) | 7.98% | 7.94% | 7.99% | 7.31% | 7.03% | 6.15% |
| Sharpe ratio | 0.463 | 0.463 | 0.468 | 0.338 | 0.338 | 0.338 |
| Deepest monthly drawdown | −9.8% | −9.8% | −9.8% | −15.2% | −12.4% | −4.3% |
| Mean difference to B3, a month | +0.075% | +0.072% | +0.076% | | | |
| Newey–West t to B3 (C2 ≥ 2.0) | **2.06** | **1.97** | **1.91** | | | |
| Newey–West t to B1 | 1.16 | 1.09 | 1.09 | | | |
| DSR at N = 3 (C3 ≥ 0.95) | 0.999 | 0.999 | 0.999 | | | |
| t to B3 at stress costs (4 bp) | 2.01 | 1.94 | 1.86 | | | |
| C1 / C2 / C3 / C4 | pass / pass / pass / pass | pass / **fail** / pass / pass | pass / **fail** / pass / pass | | | |

T1 switched 27 times (0.55 a year; the low-powered label applies below 8) and held the bond in 87.0% of months. Its stationary-bootstrap 95% interval for the Sharpe ratio is [0.21, 0.71]; the Ledoit–Wolf test of its Sharpe ratio against B3's gives p = 0.097 (descriptive, §9.3). The deflated Sharpe ratio at N = 10 is 0.997; the programme-level family count (§9.4: every trial of a term-spread or curve-slope duration rule whose return had been seen, in the desk's registry and the public trial logs) is this study's three trials, so the family figure equals the N = 3 figure; the three trials' Sharpe ratios are so close that the variance floor was applied. The observed ratio of the Newey–West to the i.i.d. standard error of T1 − B3 is **0.963**, against the 0.972 the power file assumed; the power statement stands. Full output: [`results/history/verdict.md`](results/history/verdict.md), [`summary.json`](results/history/summary.json), monthly returns in [`monthly_base.csv`](results/history/monthly_base.csv) and [`monthly_stress.csv`](results/history/monthly_stress.csv).

### Sub-windows and sub-periods (descriptive, no decision weight; by the month in which each holding period starts)

| Window | Months | T1 Sharpe | B1 Sharpe | B3 Sharpe | T1 in the bond |
|---|---|---|---|---|---|
| 1969-08 to 2002-12 (before any ETF) | 401 | 0.444 | 0.279 | 0.278 | 83.8% |
| 2003-01 to 2018-12 (the gate's overlap) | 192 | 0.508 | 0.499 | 0.499 | 93.8% |
| 1969-08 to 1981-12 (rising rates) | 149 | 0.105 | −0.271 | −0.271 | 63.8% |
| 1982-01 to 2008-12 (disinflation) | 324 | 0.599 | 0.629 | 0.629 | 92.9% |
| 2009-01 to 2018-12 (zero lower bound and QE) | 120 | 0.452 | 0.452 | 0.452 | 100% |

Study 002's copied engine also writes Study 001's three sub-periods by signal month, one month earlier than the registered definition (key `subperiods` in `summary.json`; §16 clarification of 2026-10-25 03:3x); the table above uses the registered definition (`subperiods_by_execution_month`). The two differ by one month at each boundary and give the same picture (rising-rate T1 0.076 against −0.274).

**Mechanism check (§9.6).** The spread was at or below zero at 77 month ends in 14 episodes (mean 5.5 months). In those months the synthetic bond returned 0.38% a month on average and synthetic bills 0.76%; bills beat the bond in 55% of them. That is the hypothesis's mechanism (an inverted curve precedes poor bond excess returns), and it is what the late-1970s and early-1980s episodes supply.

## 2019–2026 episode (no decision weight)

*Added 2026-10-25 03:3x London, after the episode was run once at 03:29 (`results/episode/`, logged and pushed first, `d1ffbbd`); nothing above was changed.* This window is the programme's shared held-back window, but it is not a test here: the 2022–24 inversion is common knowledge and the author's general knowledge covers it (§8.2). With actual IEF and BIL over 93 months (January 2019 to October 2026) and B3 at the frozen w 0.870, **T1 lost to its benchmarks**: Sharpe −0.494 against −0.259 for holding IEF and for B3; mean T1 − B3 −0.065% a month (Newey–West t −0.61); deepest daily drawdown −22.6% against −23.9% for IEF. The curve was inverted at 37 month ends in 5 episodes; in those months IEF returned 0.46% a month and bills 0.36%, the opposite of the mechanism in the long history. T2 (t +0.20) and T3 (t +0.97) were closer to flat. The synthetic series gives the same picture (T1 − B3 −0.074% a month, t −0.69), as the gate implied. The episode carries no decision weight and changes no verdict; it is reported because a reader would ask, and it is the most recent evidence against the rule.

## What did not work

- **The fragility rule bit.** The registered variants, which change only how the spread is read (a 21-day average; adding roll-down), missed C2 at t 1.97 and 1.91. A timing edge that depends on the exact definition of the signal is the case the rule was written for; the note does not re-weight it after seeing how close they came.
- **One regime carries the result.** Against B3 the rule gained in 1969–1981 and lost in 1982–2008; since 2009 it made no decision at all. Read as a test of "inversions precede poor bond returns", the evidence is a handful of inversions in a single rising-rate era that the author knew about beforehand.
- **Against simply holding the bond the gain is not distinguishable from zero** (t 1.16). C2 is defined against the exposure-matched B3 on purpose, but a reader comparing with B1 should know this.
- **The effect is below the design size.** The observed +0.9% a year sits under the 1.5% a year the test could detect with 80% power; an estimate that clears t = 2 at below-design size is likely to overstate the true effect (inferred, not measured).
- **The gate is thinner than its pass suggests** (12 cash months behind G1; fidelity before 2003 assumed).
- **Charts:** the engine's diagnostic chart ([`results/history/main_chart.png`](results/history/main_chart.png)) is Study 002's unchanged code and not to the house standard; the §9.6 charts in house style are not drawn yet. *(2026-10-25 04:2x London: drawn, see the Charts section below; Tester chart check not yet run.)*

## Next

1. ~~The 2019–2026 episode~~ run once on 2026-10-25 (section above).
2. Separate-session recomputation (`review_recompute.py`, `REVIEW.md`), as Studies 001–005; house-style charts with a chart check. *(2026-10-25 04:2x London: charts drawn; chart check and recomputation still to come.)*
3. The forward record (§11): decision records from the 2026-10-30 month end, shadow lines after each execution, scored once after 60 periods. Its code is not built yet; it must be before 2026-10-30. *(2026-10-25 04:2x London: built and tested, `src/forward.py`, 16 tests; see `paper-log/README.md` and the §16 entry of the same time. Not yet run on a forward month.)*

## Charts (§9.6, added 2026-10-25 04:2x London; descriptive, no decision weight)

Drawn by [`charts/make_charts.py`](charts/make_charts.py) from the committed history files only (`results/history/monthly_base.csv`, `metrics_base.csv`); every title is computed from the numbers, which are listed with the input hashes in [`charts/manifest.json`](charts/manifest.json). Nothing was re-run. Tester chart check not yet run. *(2026-10-25 05:2x GMT: Tester chart check run, no chart passed (three must-fix, one should-fix: "beat" in the growth title, a drawdown cut quoted against holding the bond only, "came from 1969–79" where 1969–89 carries the edge, "never left the bond"); all fixed and re-rendered from the same files, see the third section of [CHART_REVIEW.md](../../CHART_REVIEW.md). The titles below are the corrected ones.)*

![The curve inverted at 77 of 593 month ends](charts/history_spread_and_holdings.png)

![Growth of the spread switch against holding the bond and the same-exposure mix](charts/history_growth.png)

![Drawdown of the spread switch against the same-exposure mix and holding the bond](charts/history_drawdown.png)

![The switch's edge over the same-exposure mix by decade](charts/history_differential_by_decade.png)

The decade chart separates timing from exposure: in the 1990s and 2010–2018 the rule never held bills, so those two bars are only the gap between holding the bond and the 87% mix, (1 − w)(bond − bill). The timing advantage sits in 1969–1989 (+1.9% and +1.7% a year against the same-exposure mix); in the 2000s, the only later decade with bill months, it was −0.1%.

