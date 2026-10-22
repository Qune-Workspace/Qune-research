# Study 003 — Time-series momentum in intermediate Treasuries (IEF vs BIL)

**In-sample result (2003-08 to 2018-12, 185 monthly holding periods): the rule did not beat its benchmarks.** Holding IEF only when its trailing 12-month return exceeded bills (T1) earned an annualised Sharpe ratio of 0.45 after costs, against 0.55 for buy-and-hold IEF (B1) and 0.55 for the constant mix with the same average IEF exposure (B3). Of the four pre-registered in-sample criteria (Study 001 §9.5, inherited), **C1 and C2 fail**, C3 passes by 0.001 and C4 passes. Under the pre-registered verdict table, a failure of any in-sample criterion makes the final verdict for T1 **not supported**, whatever the out-of-sample window shows. The out-of-sample run (§8.2) still goes ahead exactly once, as §14 requires, and its results are reported below once it has run.

The in-sample test was **not** low-powered by the pre-registered standard (§9.6): T1 switched 18 times (the author's prior was 10–20) and was in cash in 31% of months (prior 20–35%). The question was answerable on this sample, and the answer on this sample is no.

Everything on this page is a backtest on historical ETF prices and bill yields. Nothing here is a track record, a forecast or investment advice. The question, hypothesis, benchmarks, costs, criteria and order of operations are fixed in [PREREGISTRATION.md](PREREGISTRATION.md) (and, for the sections it inherits, in [Study 001's](../001-slope-duration-switch/PREREGISTRATION.md)); they are not repeated here. The trial log is [trials.md](trials.md).

What happened, in order (every step is a dated commit; times are London):

1. 2026-10-22, 06:2x: pre-registration committed (`b7f7b63`): question, hypothesis, the three trials, the ex-ante estimate for the one modelled series (the cash accrual), every data-check branch. No fetch, no check, no return.
2. 2026-10-22, 06:27: BIL vendor decision (§5.3.2): second-vendor BIL fetched (`521e033`), overlap against Alpaca 2016–2018 passed on the single pre-registered threshold (mean difference −0.0001% p.a. against ±0.05%), vendor accepted (`e03064d`).
3. 2026-10-22, 08:30: engine and 92 tests committed (`987b161`), including the six engine checks of §5.3.4; `APPROVED` and the pre-run trial-log row (`8076ecc`).
4. 2026-10-22, 08:31: data checks D0 and D2, the single run: **both passed** (`5dfe8cf`). D0: the vendor IEF file covers all 4,134 NYSE trading days of the in-sample period. D2: BIL minus the cash accrual over 2007-06 to 2018-12 is +0.037% p.a. against a ±0.30% gate and an ex-ante estimate of 0.00 ± 0.20.
5. 2026-10-22, 08:32: T1–T3 run dates logged (`106696e`), then `reproduce.sh --insample`, the single in-sample run. Results below.
6. Out-of-sample: not yet run at the time of this section's commit. §14 step 8 follows the commit of this section.

## Data checks (§5.3; backtest data check, not a performance test)

| Check | Statistic | Threshold | Observed | Result |
|---|---|---|---|---|
| D0 | Vendor IEF bars on NYSE trading days 2002-07-31 to 2018-12-31; first bar | all days, ≤ 3 consecutive missing; first bar ≤ 2002-07-31 | 4,134 of 4,134; longest gap 0; first bar 2002-07-26 | pass |
| D2 / B1 | Annualised mean difference, BIL − cash accrual, 2007-06-04 to 2018-12-31 (2,916 days) | within ±0.30% p.a. (ex-ante **0.00 ± 0.20**) | **+0.037%** | pass |
| D2 / B2 | Annualised tracking error of the same difference | descriptive; reference 0.50%, 2016–2018 reading 0.288% | 0.586% | descriptive |

B2 is above its historical reference, and the by-year table in `results/checks/data_checks.md` shows why: 0.90% in 2007, 1.56% in 2008, 0.68% in 2009, then 0.21–0.31% in every year from 2010. The level by year moved the other way to what the daily noise might suggest: +0.26 to +0.32% p.a. in 2007–2009 while bill rates fell fast (the fund's portfolio yield lagged the spot rate) and −0.07 to −0.12% in 2016–2018 while they rose, both signs inside the ex-ante band and the pattern the largest component of the §5.3.3 table described in advance. This is the regime effect that made B2 descriptive rather than a gate in this study (§2.5), decided before the number was seen. Source: `results/checks/data_checks.json`; chart `results/checks/cash_check.png`.

## In-sample results (§8.1; 2003-08-01 to 2019-01-02; base costs 2 bp per side)

Instruments: IEF from the vendor's adjusted close throughout (one vendor, no splice), cash from the §5.2 accrual. Every execution date fell on a bar (no slippage logged). The B3 weight, frozen here for the out-of-sample run, is **w = 0.692** (T1 held IEF in 128 of 185 months).

| | Ann. return | Ann. vol. | Sharpe | Max DD (monthly) | Max DD (daily) | Hit rate (excess > 0) | Switches | Share in IEF |
|---|---|---|---|---|---|---|---|---|
| **T1** 12-month excess return sign | 3.66% | 5.82% | **0.452** | −8.6% | −10.4% | 0.39 | 18 | 0.69 |
| T2 12-1 | 3.34% | 5.72% | 0.406 | −8.6% | −10.4% | 0.37 | 24 | 0.67 |
| T3 10-month moving average | 2.76% | 5.47% | 0.318 | −10.1% | −12.4% | 0.37 | 37 | 0.68 |
| B0 cash | 1.14% | 0.47% | — | −0.4% | | | | 0 |
| B1 buy-and-hold IEF | 4.51% | 6.27% | **0.555** | −8.1% | −10.4% | 0.57 | 0 | 1 |
| B2 50/50 rebalanced | 2.86% | 3.15% | 0.554 | −4.1% | | 0.57 | | 0.5 |
| B3 constant mix, w = 0.692 | 3.50% | 4.34% | **0.554** | −5.6% | | 0.57 | | 0.69 |

Source: `results/insample/metrics_base.csv`, `summary.json`. Sharpe ratios are of monthly returns in excess of B0, annualised by √12. The daily maximum drawdown is from daily indices inside the holding periods (§9.3 item 4).

### Inference (§9.3 items 7–9) and criteria (§9.5), T1

| | vs B1 (buy-and-hold) | vs B3 (same exposure, no timing) |
|---|---|---|
| Mean monthly return difference, annualised | −0.85% p.a. | **+0.23% p.a.** |
| Newey–West t (6 lags) | −1.47 | **0.37** |
| Ledoit–Wolf Sharpe difference (annualised), bootstrap p | −0.103, p = 0.24 | −0.103, p = 0.24 |

T1's annualised Sharpe ratio has a stationary-bootstrap 95% interval of [0.02, 0.83]. The Sharpe difference against B1 and against B3 is the same number because B3 is a constant mix of B1 and cash, which leaves the Sharpe ratio of excess returns unchanged; that is the point of B3, and it is why C1 asks for a margin above both.

| Criterion | Requirement | Observed | Result |
|---|---|---|---|
| C1 | Sharpe(T1) ≥ Sharpe(B1) + 0.10 and ≥ Sharpe(B3) + 0.10 | 0.452 vs 0.655 and 0.654 | **FAIL** |
| C2 | Newey–West t of T1 − B3 ≥ 2.0 | 0.37 | **FAIL** |
| C3 | Deflated Sharpe ratio at N = 3 ≥ 0.95 | 0.951 (PSR 0.968; at N = 10: 0.932) | pass (by 0.001) |
| C4 | Sign of mean(T1 − B3) unchanged at 4 bp per side | +0.23% → +0.18% p.a. | pass |

Deflation inputs: variance of monthly Sharpe ratios across the three trials 0.000256 (floor not applied); expected maximum Sharpe (monthly) 0.0137 at N = 3, 0.0252 at N = 10. C3 is a statement that T1's Sharpe is distinguishable from zero after the three-trial search, not that it beats anything; with C1 and C2 failed it carries no weight in the verdict.

T2 and T3 against the same criteria: T2 fails C1, C2 and C3 (DSR 0.929), passes C4; T3 fails C1, C2 and C3 (DSR 0.866), passes C4. T3 is the only trial whose return is lower than B1's at conventional significance (Newey–West t −2.23 against B1; Ledoit–Wolf p = 0.058). Under the stress cost case (4 bp per side) every number moves by a few hundredths and no conclusion changes (`metrics_stress.csv`); the switching cost of T1 was about 5 bp p.a. in the base case.

![In-sample: 12-month excess return of IEF over cash at each month-end, shaded where T1 holds IEF; drawdown of T1 versus B1](results/insample/main_chart.png)

### Mechanism (§9.6, descriptive)

The rule can add value only in the months it is out of IEF. There were 57 such months in 9 episodes (mean length 6.3 months). In those months IEF returned 0.38% per month on average and cash 0.16%: **the months the rule stepped aside were, on average, months in which IEF beat cash by 0.22% per month**, and cash beat IEF in only 42% of them. Episode by episode (IEF total return minus cash over the episode, from the holding-period returns):

| Cash episode (signal months) | Length | IEF − cash over the episode |
|---|---|---|
| 2004-04 to 2004-06 | 3 | +1.20% |
| 2005-02 to 2005-03 | 2 | +1.75% |
| 2005-09 to 2006-10 | 14 | **−0.12%** |
| 2006-12 to 2007-01 | 2 | +0.70% |
| 2009-12 to 2010-01 | 2 | +2.57% |
| 2010-03 | 1 | +1.60% |
| 2013-05 to 2014-04 | 12 | +0.11% |
| 2017-01 to 2017-10 | 10 | +2.04% |
| 2018-01 to 2018-11 | 11 | +2.21% |

Only the 2005–2006 episode, the long hiking cycle the hypothesis is built on, saw cash hold its own against IEF, and only by 0.12%. The two long episodes of 2017 and 2018 (the normalisation) each forwent about 2% as IEF's coupon outran its price decline. The whipsaw episodes of 2004, 2005, 2006–07 and 2009–10 each cost a rally. T1's three worst months (2016-10, 2004-03, 2009-11; −4.6%, −4.2%, −3.6%) are IEF's three worst months: the rule was long in every one of them. The supervisory-stop descriptive of §11.4 (IEF closing 5% below its entry close inside a holding period) was touched in 0 of 185 periods.

### Sub-periods (§9.6, descriptive; by execution month)

| Period | T1 Sharpe | B1 Sharpe | B3 Sharpe | T1 share in IEF | T1 switches |
|---|---|---|---|---|---|
| 2003-08 to 2008-12 (hiking cycle and crisis), 65 months | 0.575 | 0.653 | 0.652 | 0.68 | 9 |
| 2009-01 to 2015-12 (zero lower bound and QE), 84 months | 0.553 | 0.621 | 0.621 | 0.82 | 6 |
| 2016-01 to 2018-12 (normalisation), 36 months | −0.208 | 0.122 | 0.122 | 0.42 | 3 |

T1 trailed B1 and B3 in all three sub-periods. The normalisation, the regime in which a momentum rule on Treasuries is supposed to earn its keep, is where it did worst: in cash for 58% of the months while IEF still returned 1.44% p.a. against 0.95% for cash. T3 was the only trial with a positive Sharpe there (0.284), on 8 switches in 36 months; it was the worst of the three overall.

### Power statement (§9.6, pre-registered)

18 switches (prior 10–20); 30.8% of months in cash (prior 20–35%); 9 cash episodes. The in-sample test is labelled **as registered**, not low-powered: the signal changed sign often enough for C2 to have been reachable, and the prior in §2.4 was accurate. The failure of C1 and C2 is therefore a result, not an artefact of too few switches.

## What did not work

- **The hypothesis, on this sample.** The sign of IEF's past 12-month excess return did not predict the sign of its next month's excess return well enough to beat holding the average exposure without timing: +0.23% p.a. against B3 with a t-statistic of 0.37, and −0.85% p.a. against buy-and-hold. Huang, Li, Wang and Zhou's (2020) objection in §2.3, that time-series momentum on a single asset is mostly the asset's drift, is what the exposure-matched benchmark was built to test, and on 2003–2018 it is what the data say.
- **The cash months were the wrong months.** The mechanism check is the clearest statement of the failure: IEF beat cash in 58% of the months the rule held cash, by 0.22% per month on average. The rule exited after sell-offs that had already happened (2013, 2017, 2018) and re-entered after rallies that had already happened (2004, 2005, 2010).
- **The canonical variants did worse, not better.** Skipping the most recent month (T2) and the 10-month moving average (T3) each switched more often and earned less; T3 is below buy-and-hold at conventional significance. The conclusion does not depend on the exact trend definition.
- **Tails were not reduced.** The rule's excess returns have higher kurtosis than IEF's (7.3 against 5.5) and the same three worst months, because it was long in each of them. The drawdown protection a trend rule is supposed to offer did not show up in fifteen years of monthly data; whether it shows up in the one episode the out-of-sample window holds (2022) is what §8.2 will report, once, without changing the in-sample verdict.
- **C3 passed by 0.001.** Had it failed the note would say the same thing; it is recorded because a reader checking the criteria against `summary.json` should not take it as support.
- **Nothing in the engineering failed.** No execution date slipped, D0 and D2 passed with the level inside the ex-ante band, the switching cost was 5 bp p.a. Two test tolerances were fixed before the code was committed (a test compared an unresolved with a resolved schedule; a sub-period count included the schedule row that starts no holding period); both were errors in the tests, found by the tests, before any data were touched. Noted so that they are not mistaken for tuning.

## Limitations of what can be concluded (in-sample)

- One asset, fifteen years, three or four rate cycles, a secular bull market in Treasuries. The result is about a long-only, unlevered, single-asset sign rule on IEF; it says nothing about the published multi-asset, volatility-scaled strategies, and it should not be cited as a refutation of time-series momentum in general.
- The in-sample cash leg is modelled (the §5.2 accrual), with a level within 0.04% p.a. of actual BIL over 2007–2018; a level error of that size moves T1's annualised return by about a basis point. The out-of-sample window uses actual BIL.
- The vendor's adjusted close carries a known +0.05% p.a. offset against Alpaca's convention (Study 002 §5.3.4); it is immaterial to a sign rule and applies equally to T1 and B1.
- The author knew the broad history of US rates before designing the study (§2.4). The rule has no parameter, so that knowledge could not be used to tune it; it could have been used to choose the question, and the pre-registered power statement exists so that the reader can judge whether the sample was adequate (it was).

## Out-of-sample (§8.2; 2019-01 to 2026-09)

Not yet run at the time of this section's commit. It runs exactly once, after this section is committed, by `reproduce.sh --oos`, with the B3 weight frozen at 0.692; the results, O1 and O2, and the final verdict are appended below when it has run. Per the pre-registered verdict table the final verdict for T1 cannot be better than **not supported**, because C1 and C2 failed in-sample; the out-of-sample run is reported for the record and because it is the one window that holds the episode (2022) a trend rule exists for.
