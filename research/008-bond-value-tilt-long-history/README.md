# Study 008 — Bond value tilt by the real yield on the long history (1974–2018)

**Verdict: not supported** (pre-registered row, §9.5; history run once on 2026-10-25 at 21:19:39Z). **Read the disclosure first:** the test window had been seen twice on this leg, by Studies 006 and 007, and the drift of real yields (low in the 1970s, highest in the early 1980s, falling for most of the decades after) is general knowledge the author had before choosing this form (§2.4 of the pre-registration). The rule holds a weight between 0 and 1 in a synthetic 8.5-year Treasury position and the rest in synthetic bills; the weight is the expanding percentile rank of the real yield at each month end, where the real yield is the 10-year yield less the trailing 12-month CPI inflation that had been published by that date. **Over 534 months, July 1974 to December 2018, the primary rule T1 had a Sharpe ratio of 0.415 against 0.382 for holding the bond and 0.381 for the same average exposure (w̄ 0.466) held throughout. Its mean gain over that exposure-matched mix was +0.56% a year with a Newey–West t of 1.38, so C1 (a Sharpe margin of 0.10) and C2 (t ≥ 2.0) fail.** Both registered companions also fail C1 and C2 on their own criteria: core CPI in place of headline (T1a, t 1.78) and a trailing 120-month rank in place of the expanding one (T1b, 1979–2018, t 0.91). The registered era row fails as well: from 1986 to 2018 T1 earned −0.06% a year against the exposure-matched mix.

**What it does and does not show.** Whatever gain the full window shows sits in the years before any ETF existed, and mostly before 1986: +1.36% a year over 1974–2002 (t 2.47, descriptive) and −0.85% a year over 2003–2018 (t −1.81); +2.34% a year over 1974–1985 (t 1.92). That is the pattern §2.4 said was partly foreseeable from the history of real yields, and the reason the era row was registered. The bond's excess return over bills does rise across the fifths of T1's weight (from 0.84% a year in the lowest fifth to 6.88% in the highest), but the monthly gain over the same average exposure is too noisy to tell from zero. The signal is close to independent of the two earlier studies on this leg (the gate's weight correlations 0.115 with Study 007's carry tilt and 0.161 with Study 006's switch; the monthly gains correlate 0.193 with Study 007's), so it is a third, largely separate question with a negative answer, not a restatement. No paper order; the forward record starts at the 2026-10-30 month end and is scored once after 60 months. The 2019–2026 episode (no decision weight), the charts and a separate-session recomputation follow this note.

Everything on this page is a backtest on synthetic constant-maturity series built from FRED yields and CPI, after costs. Nothing here is a track record, a forecast or investment advice. The question, the trials, the benchmarks, the criteria, the gate, the volatility bar, the era row and the order of operations were fixed in [`PREREGISTRATION.md`](PREREGISTRATION.md) before any CPI file was read (`ca2432a`); the trial log is [`trials.md`](trials.md).

What happened, in order (every step is a dated commit; times are commit times read back from git, UTC, which equals London on this date):

1. 2026-10-25 16:24: question note (`1d1daeb`), after the agenda refresh gave four candidates their detectable edges first ([`tools/power_refresh.txt`](../../tools/power_refresh.txt)).
2. 17:20: pre-registration and trial log pushed before any CPI file was read (`ca2432a`). 17:25: data step, dates part (`be162c1`), after a §16 correction of a wrong series ID (`CPIAUCNSA` for `CPIAUCNS`) found by an HTTP 404 before any CPI data were received.
3. 18:18–18:27: the CPI vintage and release-date check, logged before it ran (`ac42f2d`, outcome `245613c`): 1,045 ALFRED vintages read; the previous month's CPI was not yet public at the signal date in one test-window month (signal month 1996-01, which therefore uses November 1995) and in the episode's 2025-11; December vintages 1995–2018 equal today's files. Two §6.1 clarifications before any real yield was computed (`dcf5cd1`).
4. 18:34–20:36: code and tests (`0dec256` to `7d7dc03`); a separate code review (Opus Tester, isolated, constructed data only) failed it on one must-fix (a trial dropped at the gate would still have run in the history), fixed with tests and re-checked (pass); 319 tests pass, 2 skipped by name.
5. 20:43: `APPROVED` and the gate's trial-log row (`e9169dd`); then **the gate and overlap check, run once: PASS, no trial dropped** (`172c456`).
6. 20:44: the volatility check's row (`fe94ff7`), then **the volatility check, run once: σ 7.81%, Study 007's figure reproduced exactly; the criteria stand** (`2902e22`).
7. 21:18: family re-counted at 17 and the history-run row logged and pushed (`031c134`); then **the history run, once** (21:19:39Z), committed as written (`ef7f4bd`); outcome row (`b111b0e`).
8. This note: the publication (the commit carrying this line).

## The gate (§5.3, §5.6; signal paths and instrument returns only, no rule return)

Study 007's gate for a fractional weight path: the error the synthetic series puts into the monthly differential T_k − B3 over the 192 months in which an ETF exists to compare with (2003–2018), e_t = (w_t − w̄)·g_t, with g_t the synthetic-minus-ETF gap in the duration-over-cash return.

| Check | T1 | T1a | T1b | Bound | Result |
|---|---|---|---|---|---|
| G1, bias: \|mean(e)\| × 12 | 0.021% | 0.024% | 0.062% | ≤ 0.18% a year | pass |
| G2, noise: sd(g) / sd(x_ETF) | 0.131 (inherited from Study 006, reproduced exactly) | | | ≤ 0.32 | pass |
| Overlap: corr(w, Study 007 T1 weight) | 0.115 | −0.014 | 0.085 | flag above 0.8 for T1 | no flag |
| Overlap: corr(w, Study 006 T1 holding) | 0.161 | 0.115 | 0.088 | | |

Full output: [`results/gate/gate.md`](results/gate/gate.md). **What the pass does not show:** before 2003 there is no ETF, so the series' fidelity over 1974–2002 (342 of the 534 months, the months that carry this rule's gain) is an assumption carried from Studies 002 and 006, not a measurement.

## Results: the test window, 1974-07 to 2018-12 (534 months, synthetic legs, base costs 2 bp a side on the traded fraction)

| | T1 (headline CPI, expanding rank) | T1a (core CPI) | T1b (trailing 120-month rank, 1979–2018) | B1 (hold the bond) | B3 for T1 (same exposure, w̄ 0.466) | B2 (50/50) |
|---|---|---|---|---|---|---|
| Months | 534 | 534 | 474 | 534 | 534 | 534 |
| Annual return (geometric) | 6.66% | 6.77% | 6.21% | 7.56% | 6.11% | 6.21% |
| Volatility | 4.85% | 4.72% | 4.67% | 7.82% | 3.73% | 3.99% |
| Sharpe ratio | **0.415** | 0.448 | 0.388 | 0.382 | 0.381 | 0.381 |
| Same-window B1 / B3 Sharpe | 0.382 / 0.381 | 0.382 / 0.381 | 0.406 / 0.405 | | | |
| Deepest monthly drawdown | −6.3% | −6.4% | −6.2% | −15.2% | −3.8% | −4.3% |
| Mean difference to own B3, a year | +0.56% | +0.72% | +0.44% | | | |
| Newey–West t to own B3 (C2 ≥ 2.0) | **1.38** | **1.78** | **0.91** | | | |
| Mean difference to B1, a year; Newey–West t | −1.03%; −1.53 | −0.93%; −1.38 | −1.53%; −1.82 | | | |
| DSR at the family count 17 (C3 ≥ 0.95); at N = 3 / 10 | 0.988; 0.996 / 0.991 | 0.994; 0.998 / 0.996 | 0.976; 0.989 / 0.980 | | | |
| t to own B3 at stress costs, 4 bp (C4: sign) | 1.33 | 1.73 | 0.85 | | | |
| C1 / C2 / C3 / C4 | **fail** / **fail** / pass / pass | **fail** / **fail** / pass / pass | **fail** / **fail** / pass / pass | | | |
| Verdict on own criteria | **not supported** | not supported | not supported | | | |

Each trial's B3 holds that trial's own mean weight throughout (T1 0.466, T1a 0.448, T1b 0.401; T1b's B1 and B3 are on its own 474 months). One-way turnover over the window: T1 23.8 units, T1a 21.9, T1b 32.7; the low-powered label applies below 8, so none carries it. No trial had a hold month (a month whose CPI was never published) on its window. T1's stationary-bootstrap 95% interval for the Sharpe ratio is [0.14, 0.68]; the Ledoit–Wolf test of its Sharpe ratio against B3 gives p = 0.70 (T1a 0.43, T1b 0.87; descriptive, §9.3). The family count (§9.4) was re-counted before the run at 17: Studies 003, 005 and 006 three each, Study 007 five, this study three; the trials' Sharpe ratios are so close that the variance floor was applied, so at these counts the DSR mainly tests whether the leg carries a premium (METHODS §2.1), which is why C3 passes while C1 and C2 fail. Full output: [`results/history/verdict.md`](results/history/verdict.md), [`summary.json`](results/history/summary.json), monthly returns and weights in [`monthly_base.csv`](results/history/monthly_base.csv) and [`monthly_stress.csv`](results/history/monthly_stress.csv).

**Era row (§9.5):** T1 over execution months 1986-01 to 2018-12 (396 months): mean(T1 − B3) **−0.06% a year**, so the sign condition fails (Newey–West t −0.18, reported, not tested). Under the precedence T1's verdict is already fixed by its C1 and C2 failures; the era row would have withheld "supported" even if they had passed.

### Sub-windows and rate eras (descriptive, no decision weight; by the month in which each holding period starts)

| Window | Months | T1 Sharpe | B1 / B3 Sharpe | T1 − B3, a year | Newey–West t | T1 mean weight |
|---|---|---|---|---|---|---|
| 1974-07 to 2002-12 (before any ETF) | 342 | 0.468 | 0.333 / 0.332 | +1.36% | 2.47 | 0.584 |
| 2003-01 to 2018-12 (the gate's overlap) | 192 | 0.346 | 0.499 / 0.499 | −0.85% | −1.81 | 0.257 |
| 1974-07 to 1985-12 (complement of the era window) | 138 | 0.401 | 0.113 / 0.112 | +2.34% | 1.92 | 0.581 |
| Rate era 1974-07 to 1981-12 | 90 | −0.099 | −0.364 / −0.365 | +1.14% | 1.16 | 0.385 |
| Rate era 1982-01 to 2008-12 | 324 | 0.600 | 0.629 / 0.629 | +0.87% | 1.54 | 0.563 |
| Rate era 2009-01 to 2018-12 | 120 | 0.289 | 0.452 / 0.452 | −0.68% | −1.20 | 0.267 |

The B3 column in each row is T1's full-window B3 (w̄ 0.466), not a per-window mean weight. After 2002 the expanding rank put the rule mostly in bills (mean weight 0.26) while the bond kept earning, so the rule lagged both benchmarks; in 1982–2008 it had a positive mean gain over B3 (+0.87% a year) but a lower Sharpe ratio than holding the bond (0.600 against 0.629).

### Mechanism (§9.6): does a higher rank precede a higher bond excess return?

| Fifth of T1's weight (equal counts) | Months | Weight range | Leg excess return over bills, a year | Months the leg beat bills |
|---|---|---|---|---|
| Q1 (lowest) | 107 | 0.000–0.190 | 0.84% | 50.5% |
| Q2 | 107 | 0.190–0.349 | 1.27% | 54.2% |
| Q3 | 106 | 0.353–0.556 | 2.08% | 53.8% |
| Q4 | 107 | 0.558–0.702 | 3.83% | 58.9% |
| Q5 (highest) | 107 | 0.702–1.000 | 6.88% | 53.3% |

By the sign of the real yield: 1.30% a year in the 76 months with r ≤ 0, 3.26% in the 458 months with r > 0. The ordering is monotone, unlike Study 007's carry quintiles, but the fifths are not independent samples: an expanding rank of a slowly moving series sorts months largely by date, so the sort and the sub-window table above describe the same early-years concentration (inferred from the two tables, not separately tested). The decision statistic is the Newey–West t of the monthly gain, 1.38.

### Power, after the fact (§9.6)

The realised dispersion of T1's weight was sd(w − w̄) = 0.270, against 0.5 in the design and 0.289 for a uniform rank; the observed Newey–West/iid ratio of the standard error was 1.095 (0.972 assumed). With the observed standard error the test could detect a mean gain of 0.82% a year at t = 2 and 1.16% a year at 80% power; the observed +0.56% is below both. Before the run the bar was stated as about 1.5% a year at w = 0.5 (volatility check). So the study could not have told an edge of half a percent a year from zero, and it did not.

## What did not work

- **The rule itself:** T1 fails C1 and C2; both companions fail the same two criteria; the era row fails. No form of the value signal registered here beat the same average exposure by a margin the test could see.
- **The years that matter now:** over 2003–2018, the only part of the window that an ETF can check, T1 − B3 was −0.85% a year (t −1.81), and −0.68% a year over 2009–2018. The rule's gain comes from 1974–1985, the years whose real-yield path the author knew before choosing the form (§2.4).
- **The trailing rank (T1b), meant to remove the secular drift, did worse,** not better (t 0.91 on 1979–2018), so the drift was not hiding a cleaner signal in this form.
- **Process slips in this study, all caught and disclosed before the result they could affect:** a wrong FRED series ID in the pre-registration (found by a 404 before any CPI data were received, corrected by a §16 amendment); a data-step script that labelled its ALFRED probe as a finished check (disclosed; the real check followed as its own logged step); a history module that ignored the gate's dropped trials (caught by the separate code review before any run; no trial was dropped in the event); several time labels written ahead of the clock (each corrected by a dated precision, including the two pre-run rows of this history run, labelled 21:2x and committed at 21:18:23Z, before the run).

## Next

- §14 step 9: the 2019–2026 episode with actual IEF and BIL, logged first and run once, no decision weight (one hold month, signal month 2025-11, because the October 2025 CPI was never published).
- Charts to the house standard and the Tester chart check; then step 10, a separate-session recomputation (`REVIEW.md`).
- `forward008.py` before the first forward signal at the 2026-10-30 month end (§11.1), separating "not yet in the fetched file" from "never published" (code-review note 8); signal month 2026-11 will hold, because its k − 12 month is the unpublished October 2025 index.
- Not done and not planned: any further trial on this question. The verdict is fixed by the pre-registered table.
