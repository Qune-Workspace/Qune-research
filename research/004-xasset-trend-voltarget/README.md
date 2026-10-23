# Study 004 — Cross-asset time-series momentum with volatility targeting, ten liquid ETFs, long-only or flat

**Verdict: not supported** (pre-registered table, §9.5; published 2026-10-22; independently reviewed 2026-10-23, confirmed with findings: [REVIEW.md](REVIEW.md)). **Status: finished (§14 step 9); out-of-sample run once on 2026-10-22, never to be re-run.** *Addition 2026-10-24: the one piece still to come is the forward shadow record of §11, no paper order, kept in [`paper-log/`](paper-log/README.md) from the 2026-10-30 month-end; its code was built and tested on 2026-10-23 (§14 step 11).* Pre-registration: [PREREGISTRATION.md](PREREGISTRATION.md) (committed before any data were fetched); trial log: [trials.md](trials.md); data checks: [results/checks/data_checks.md](results/checks/data_checks.md); in-sample outputs: `results/insample/`; out-of-sample outputs: `results/oos/`.

**Out-of-sample headline (2019-01-02 to 2026-09-30, 93 monthly holding periods, run once, base costs): both pre-registered sign conditions held, and the verdict is still "not supported".** T1 earned a Sharpe ratio of 0.336 against 0.199 for the always-long volatility-scaled portfolio (B3) and for the exposure-matched one (B4), so **O2 passes**; the mean monthly difference T1 − B4 was +0.00027 with a Newey–West t of 0.35, so **O1 passes** (a sign condition, as registered: 93 months cannot establish a difference of this size); T1's monthly maximum drawdown was −4.1% against −11.1% for B4, so the drawdown clause is not triggered. **The verdict is fixed by the in-sample failures of C1 and C2 under the precedence rule written before any result** (not supported > inconclusive > supported), and this note does not re-weight the criteria after seeing the window go the rule's way. What the window shows, descriptively: the trend signal kept the book out of most of the 2022 sell-off (−3.1% from January to October 2022 against −13.4% for B3, −19.3% for equal weight and −18.2% for SPY), and that one episode is where its whole out-of-sample advantage sits; the 2020 crash it only softened (−8.5% against −11.8% for B3 over 2020-02-19 to 2020-03-23) and it then missed the recovery (−3.8% to 2020-08-31 against +3.3% for equal weight). T2 and T4 pass both sign conditions; T3 fails both. The nine-asset run without IEF passes both (Sharpe 0.340 against 0.273, t of the difference 0.03). Over the same window, plain equal weight (Sharpe 0.43) and 60/40 (0.74, vendor SPY) beat every volatility-scaled variant: the window rewarded equity beta, and 10%-per-asset volatility targeting with no leverage gave it up.

**In-sample headline (2004-01 to 2018-12, 180 monthly holding periods, base costs): the trend signal added nothing measurable on top of volatility scaling.** T1 (hold each asset only when its 12-month excess return over cash is positive, each position sized to a 10% volatility target with a 25% cap) earned a Sharpe ratio of 0.886 against 0.880 for the always-long volatility-scaled portfolio (B3) and 0.880 for the same portfolio at T1's own average exposure (B4). **C1 fails** (the pre-registered margin is 0.10) and **C2 fails** (Newey–West t of the monthly difference T1 − B4 is 0.65 against the 2.0 required). C3 (deflated Sharpe 0.998 at N = 4) and C4 (the sign of T1 − B4 holds under doubled costs) pass. T2, T3 and T4 fail C1 and C2 on the same criteria. Because C1 and C2 fail, **the §9.5 table already fixes the verdict as "not supported" whatever the out-of-sample window shows**; the out-of-sample run still happens, once, as pre-registered, because the window's result is informative and the programme runs every step it registered. The test is not low-powered: T1 switched 167 times across the ten assets (the pre-registered floor was 40).

**Disclosures that belong in the first paragraph (§2.4, §8.3, §16).** (1) The author had seen IEF's out-of-sample path under Study 003 before this study was designed; no parameter was set after that, and the nine-asset run without IEF is reported next to every ten-asset table below: it reaches the same four in-sample outcomes. (2) The pre-registered universe was twelve ETFs; SPY and DBC were excluded before any return was computed because their vendor series differed from the broker's by more than the ±0.20% p.a. gate fixed in advance (§5.3.2; details in the data-check note). The study therefore tests ten instruments, and the equity class lacks its largest member and the real-asset class its only broad commodity index. (3) B2 (60/40) and the SPY rows below use the pre-registered vendor SPY series, which failed that gate by +0.31% p.a. on 2016–2018; B2 is descriptive only. (4) The pre-registration fixed no bootstrap seed; Study 003's seed (20261021) is inherited and recorded in §16 so that every resample is reproducible.

## What was run (§6, §7, §9)

Monthly, at the last NYSE trading day's close, for each of the ten assets present (an asset enters at the first month-end with a 12-month lookback bar and 63 days of returns; entry dates below): the 12-month excess return over cash sets the signal (long if positive, otherwise flat); the position is `σ_a / (N_t · σ_i)` with σ_a = 10%, σ_i the 63-day close-to-close volatility, capped at 25%, scaled down proportionally if the weights sum to more than one. Trades fill at the next day's close; costs are per-ETF (2.0–3.0 bp one way, Table §9.2) on the change from the drifted weight; stress = twice that. Cash in-sample is the DTB3 bill accrual inherited from Study 003 (§5.2). T2 and T3 use 6- and 3-month lookbacks; T4 blends the three signals (0, ⅓, ⅔, 1). Benchmarks: B0 cash, B1 equal weight, B2 60/40 SPY/IEF, B3 always-long volatility-scaled (exactly T1's sizing with every signal on), B4 = B3 × k with k = the in-sample mean of T1's gross exposure over B3's, frozen now: **k = 0.8018** (ten assets), **0.7764** (nine without IEF).

Entry signal dates (from the vendor files' first bars, §8.1): IWM, EFA, SHY, IEF, TLT, LQD 2003-12-31; EEM 2004-04-30; VNQ 2005-09-30; GLD 2005-11-30; HYG 2008-04-30. All as expected in §4. Holding periods: 2004-01-02 to 2019-01-02, 180.

## In-sample results, ten assets (§8.1; base costs)

| | Ann. return | Ann. vol | Sharpe | Max DD (monthly) | Max DD (daily) | Hit rate (excess > 0) | One-way turnover p.a. | Mean gross exposure | Skew / kurtosis |
|---|---|---|---|---|---|---|---|---|---|
| B0 cash | 1.15% | 0.47% | — | −0.4% | −0.4% | — | 0 | 0 | — |
| B1 equal weight | 6.65% | 9.74% | 0.594 | −26.5% | −30.2% | 0.628 | 0.44 | 1.00 | 0.12 / 11.4 |
| B2 60/40 (vendor SPY) | 6.82% | 8.90% | 0.657 | −30.3% | −32.2% | 0.650 | 0.29 | 1.00 | −0.48 / 6.9 |
| B3 vol-scaled, always long | 4.96% | 4.32% | 0.880 | −8.3% | −9.8% | 0.628 | 0.87 | 0.95 | −0.54 / 3.4 |
| B4 = B3 × 0.8018 | 4.21% | 3.47% | 0.880 | −6.6% | −7.8% | 0.628 | 0.70 | 0.76 | −0.54 / 3.4 |
| **T1 12-month, long/flat** | **4.60%** | **3.90%** | **0.886** | **−5.2%** | **−6.8%** | **0.644** | **2.07** | **0.76** | **−0.44 / 3.9** |
| T2 6-month | 3.71% | 3.57% | 0.723 | −6.1% | −6.5% | 0.628 | 2.68 | 0.70 | −0.49 / 4.5 |
| T3 3-month | 3.87% | 3.57% | 0.767 | −6.3% | −7.1% | 0.633 | 3.61 | 0.67 | −0.54 / 4.2 |
| T4 blend | 4.14% | 3.55% | 0.843 | −5.1% | −6.0% | 0.639 | 2.45 | 0.73 | −0.55 / 4.2 |

Stress costs (2× base): Sharpe T1 0.873, B3 0.876, B4 0.876, T2 0.705, T3 0.744, T4 0.827. B3 and B4 have the same Sharpe ratio by construction (B4 is B3 scaled with the remainder in cash; costs scale too), so C1's two conditions are one bar here; B4's job is C2 and O1, the mean difference.

Reading: volatility scaling, not trend, did the work. B3 lifts the Sharpe ratio from 0.59 (equal weight) to 0.88 with a maximum drawdown a third of B1's; T1 then matches B3's Sharpe ratio at three times the turnover, with a smaller drawdown (−5.2% against −8.3% monthly) and a lower return (4.60% against 4.96%). The drawdown reduction is real and is the one thing the signal bought; it was not a criterion.

### Inference (§9.3 items 7–9) and criteria (§9.5)

| Trial | Sharpe 95% CI (stationary bootstrap, 10,000) | vs B3: NW mean (monthly) / t | vs B3: LW Sharpe diff (ann.) / p | vs B4: NW mean / t | vs B4: LW diff / p | Stress vs B4: mean / t |
|---|---|---|---|---|---|---|
| T1 | 0.44 to 1.37 | −0.00030 / −0.48 | +0.005 / 0.98 | **+0.00033 / 0.65** | +0.005 / 0.98 | +0.00031 / 0.59 |
| T2 | 0.24 to 1.25 | −0.00102 / −1.68 | −0.158 / 0.49 | −0.00040 / −0.78 | −0.158 / 0.48 | −0.00043 / −0.85 |
| T3 | 0.29 to 1.27 | −0.00090 / −1.53 | −0.114 / 0.54 | −0.00027 / −0.56 | −0.114 / 0.54 | −0.00032 / −0.68 |
| T4 | 0.37 to 1.37 | −0.00068 / −1.27 | −0.038 / 0.85 | −0.00005 / −0.12 | −0.038 / 0.84 | −0.00009 / −0.20 |

No bootstrap resample was degenerate (0 dropped in every interval). Deflated Sharpe ratio (§9.4; variance of the four trials' monthly Sharpe ratios 0.000337, floor not applied): T1 PSR 0.999, **DSR 0.998 at N = 4**, 0.998 at N = 10; T2 0.991 / 0.988; T3 0.994 / 0.992; T4 0.997 / 0.996. These say the portfolios' Sharpe ratios are far from zero, which is the volatility-scaled long-only portfolio's merit, not the signal's.

| Criterion (T1, base costs) | Required | Observed | Result |
|---|---|---|---|
| C1 | Sharpe(T1) ≥ Sharpe(B4) + 0.10 and ≥ Sharpe(B3) + 0.10 | 0.886 vs 0.880 + 0.10 and 0.880 + 0.10 | **FAIL** |
| C2 | NW t of mean(T1 − B4) ≥ 2.0 | 0.65 | **FAIL** |
| C3 | DSR(T1), N = 4, ≥ 0.95 | 0.998 | pass |
| C4 | sign of mean(T1 − B4) unchanged under 2× costs | +0.00033 → +0.00031 | pass |

T2, T3 and T4: C1 FAIL, C2 FAIL, C3 pass, C4 pass, each.

## Nine assets without IEF (§9.6, §2.4; base costs)

| | Ann. return | Ann. vol | Sharpe | Max DD (monthly) | Turnover p.a. | Gross exposure |
|---|---|---|---|---|---|---|
| B1 | 6.87% | 10.84% | 0.563 | −30.0% | 0.46 | 1.00 |
| B3 | 5.09% | 4.72% | 0.838 | −9.5% | 0.89 | 0.93 |
| B4 = B3 × 0.7764 | 4.22% | 3.68% | 0.838 | −7.3% | 0.69 | 0.72 |
| **T1** | **4.70%** | **4.05%** | **0.879** | **−5.4%** | **1.86** | **0.72** |
| T2 / T3 / T4 | 4.11% / 3.90% / 4.30% | 3.76% / 3.67% / 3.69% | 0.793 / 0.756 / 0.858 | −5.9% / −6.4% / −5.2% | 2.30 / 3.19 / 2.20 | 0.67 / 0.64 / 0.68 |

T1 vs B4: NW mean +0.00040, t = 0.74; LW Sharpe difference +0.041, p = 0.85; DSR 0.998 at N = 4 (the trial-variance floor was applied: the four trials' monthly Sharpe ratios were closer than the floor). C1 FAIL (0.879 vs 0.938), C2 FAIL, C3 pass, C4 pass: **the same four outcomes as the ten-asset run**, so the one non-blind asset does not change the in-sample reading. 150 switches.

## Pre-registered descriptives (§9.6; no decision weight)

**Per-asset attribution, T1 (ten assets).** Contribution to the arithmetic annual return (the ten legs sum to 4.2% a year; the remainder of the 4.6% is the cash leg) and share of the gross return's variance; asset-months on out of months present: IWM 0.45% / 10% / 139 of 180; EFA 0.53% / 12% / 123; EEM 0.48% / 10% / 122 of 176; SHY 0.28% / 2% / 124; IEF 0.46% / 11% / 123; TLT 0.31% / 11% / 123; LQD 0.50% / 15% / 124; HYG 0.38% / 8% / 97 of 128; GLD 0.40% / 8% / 98 of 157; VNQ 0.41% / 12% / 119 of 159. No asset dominates; the risk is spread as the sizing intends. Each asset's own long/flat position against its own always-on position (annualised Sharpe of the weighted excess return): the signal helped in EFA (0.55 vs 0.43), EEM (0.54 vs 0.46), SHY (0.88 vs 0.67), HYG (0.66 vs 0.41) and hurt in IEF (0.38 vs 0.50), TLT (0.25 vs 0.49), LQD (0.45 vs 0.52), VNQ (0.49 vs 0.53); IWM and GLD were a wash. **Timing the Treasury legs cost the most**, the same reading Study 003 reached for IEF alone.

**Crisis table (in-sample window, §9.6).** 2008-09-01 to 2009-02-28, cumulative: T1 **+2.4%**, B1 −20.7%, B2 −24.4%, B3 −5.3%, B4 −4.2%, SPY −41.4%, IEF +6.4%. This is the episode the design exists for and the signal did what it should: by September 2008 the equity, credit and real-asset legs were flat and the book sat in Treasuries and cash. It is one episode, as the 2022 exit was for Study 003. Nine-asset run: T1 +1.9%, B3 −6.5%, B4 −5.1%.

**Correlations (monthly excess returns, in-sample).** T1 with SPY 0.30, with IEF 0.43; B3 with SPY 0.54, with IEF 0.42. The signal roughly halves the equity beta of the volatility-scaled book while leaving the Treasury beta unchanged; this, not the Sharpe ratio, is where the 2008 figure comes from.

**Volatility forecast against realised.** The ex-ante diagonal forecast √(Σ w_i² σ_i²) of T1's annualised volatility averaged 2.4%; the realised rolling 12-month figure averaged 3.7%; mean ratio 1.58; realised exceeded forecast by more than half in **53% of the 169 months compared** (B3: 2.6% vs 4.2%, ratio 1.61, 54%). As §9.6 anticipated, the diagonal forecast understates the portfolio's volatility by a large factor because it ignores the positive correlations between the legs. This is the first input to the risk model the programme builds next; it is a finding about the forecast, not a tuning target.

**Breakeven cost curve (ten assets, k frozen).** Sharpe(T1) − Sharpe(B4) at 0×, 0.5×, 1×, 2×, 3×, 5× base cost: +0.013, +0.009, +0.005, −0.002, −0.010, −0.025; **zero crossing at 1.70× base cost**. Even with no costs at all the advantage is 0.013 Sharpe, an eighth of the C1 margin. Nine assets: +0.047 at 0× falling to +0.016 at 5×, no crossing.

**Sub-periods (by holding-period start month; Sharpe, annual return, monthly max DD).**

| Period | B1 | B3 | B4 | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|---|---|
| 2004-01..2008-12 | 0.34, 6.3%, −26.0% | 0.62, 5.8%, −8.3% | 0.62, 5.2%, −6.6% | **1.01, 7.0%, −4.1%** | 0.59, 5.0%, −4.1% | 0.69, 5.4%, −4.0% | 0.83, 5.9%, −4.1% |
| 2009-01..2015-12 | 0.82, 7.7%, −8.5% | 1.16, 4.9%, −5.5% | 1.16, 3.9%, −4.4% | 1.13, 4.2%, −4.0% | 0.94, 3.3%, −6.1% | 0.90, 3.3%, −5.6% | 1.06, 3.7%, −5.1% |
| 2016-01..2018-12 | 0.70, 4.7%, −5.3% | 0.68, 3.7%, −4.6% | 0.68, 3.1%, −3.7% | **0.17, 1.6%, −5.2%** | 0.45, 2.6%, −4.1% | 0.53, 2.5%, −3.2% | 0.36, 2.2%, −4.2% |

The whole of T1's in-sample advantage sits in 2004–2008, which contains the one crisis; in 2009–2015 it matched B3 and in 2016–2018 it lost clearly (Sharpe 0.17 against 0.68), the pattern the agenda called trend's 2010s decay.

**Power statement (§9.6).** 167 on/off switches across the ten assets in-sample, 0.6 (SHY) to 1.7 (TLT, LQD, GLD) per asset per year; threshold 40; **the in-sample test is "as registered"**, not low-powered. The §9.5 failures are therefore not for want of signal changes.

Plots: `results/insample/exposure_drawdown_10assets.png` (T1 gross exposure and assets on; daily drawdown of T1, B3, B4), `onoff_strips_10assets.png`, and the nine-asset pair.

## What did not work (§9.7; in-sample)

- **C1 and C2 for every trial.** T1's Sharpe advantage over B3 and B4 is 0.005; the margin was 0.10. The monthly difference against B4 has t = 0.65. T2 (6-month), T3 (3-month) and T4 (blend) are worse than T1 and worse than B3 on Sharpe (0.72, 0.77, 0.84 against 0.88), with two to three and a half times B3's turnover.
- **The shorter lookbacks lose to the long-only book.** T2's NW t against B3 is −1.68 and its Ledoit–Wolf Sharpe difference −0.16 a year; T3's −1.53 and −0.11. The horizon that practitioners blend in did not help here.
- **2016–2018.** T1's Sharpe 0.17 against B3's 0.68: three years of whipsaw in which being flat cost return without avoiding a drawdown (T1's monthly max DD −5.2% was *larger* than B3's −4.6% in that sub-period).
- **Timing Treasuries.** IEF's and TLT's own long/flat positions had lower Sharpe ratios than their always-on positions (0.38 vs 0.50; 0.25 vs 0.49), and LQD's too. The signal added value in the equity and credit legs and in SHY only.
- **The diagonal volatility forecast** understated realised volatility by about 60% on average and by more than half in 53% of months, for T1 and for B3 alike.
- **Costs.** At base costs T1 pays 2.07 one-way turnover a year against B3's 0.87; the 0.013 zero-cost Sharpe advantage is gone at 1.7× base cost. Any realistic slippage above the allowances removes what little there is.
- **Universe.** Two of the twelve pre-registered instruments never entered (data gate), so the equity class had no large-cap US leg and the real-asset class no commodity leg; the published cross-asset results rest heavily on commodities and currencies, which this study does not hold.
- **Weakest result:** T1 against B4 in the 2016–2018 sub-period and T2 against B3 over the full window.

## Limitations of what can be concluded (in-sample)

- The window contains one crisis (2008) and a long recovery; the signal's whole measured advantage is in the five years that contain the crisis. One episode is not evidence of an edge, as Study 003's note said of 2022.
- Survivorship: all ten funds exist today; B1–B4 and T1–T4 carry the same upward bias.
- The cash leg before 2007-06 is unchecked against any actual bill ETF (inherited limitation, §5.2).
- Today's cost allowances are applied to 2004–2008, which overstates implementability then.
- The vendor SPY series used in B2 and the crisis and correlation rows failed the universe gate by +0.31% p.a. on 2016–2018; B2's level carries that uncertainty.
- B3 and B4 share one Sharpe ratio, so C1's two conditions coincide; the design intended them as two bars and they turned out to be one.
- No covariance-based sizing, no shorting, no futures, no currencies: this does not test the published long/short futures trend result and does not claim to.

## Out-of-sample results (§8.2, §14 step 8; 2019-01-02 to 2026-09-30, 93 holding periods; run once; base costs)

Run once by `reproduce.sh --oos` on code 1697e9d (2026-10-22 23:20–23:23 London, 2 min 52 s; results commit 784f6ed) on the same vendor series with actual BIL as cash, k frozen at 0.8018 (ten) and 0.7764 (nine). **End bar (§16, decided and committed before the run):** §8.2 asked for the last holding period to end at the first execution date of October 2026, but the ten fetched files stop at 2026-09-30 (the reused IEF and BIL files reach further), so without a change the engine would have ended IEF and the cash leg on 2026-10-01 while forward-filling the other nine assets from 2026-09-30, silently. The window therefore ends at the common last bar, 2026-09-30, for every instrument alike: the last period is one trading day short, and the 2026-09-30 signal is computed (the terminal position, the shadow record's first entry) but starts no period. Study 003's window ended on 2026-10-01; the one-day difference is recorded so that nobody reads it as a choice.

### Ten assets

| | Ann. return | Ann. vol | Sharpe | Max DD (monthly) | Max DD (daily) | Hit rate (excess > 0) | One-way turnover p.a. | Mean gross exposure | Skew / kurtosis |
|---|---|---|---|---|---|---|---|---|---|
| B0 cash (BIL) | 2.65% | 0.58% | — | −0.1% | −0.2% | — | 0 | 0 | — |
| B1 equal weight | 6.61% | 10.10% | 0.426 | −19.6% | −22.4% | 0.581 | 0.41 | 1.00 | −0.50 / 4.6 |
| B2 60/40 (vendor SPY) | 10.62% | 10.92% | 0.742 | −18.8% | −21.2% | 0.645 | 0.36 | 1.00 | −0.45 / 4.0 |
| B3 vol-scaled, always long | 3.75% | 6.43% | 0.199 | −13.8% | −15.5% | 0.548 | 1.01 | 0.95 | −0.62 / 4.7 |
| B4 = B3 × 0.8018 | 3.57% | 5.17% | 0.199 | −11.1% | −12.4% | 0.548 | 0.81 | 0.76 | −0.62 / 4.7 |
| **T1 12-month, long/flat** | **3.95%** | **4.04%** | **0.336** | **−4.1%** | **−11.4%** | **0.538** | **2.16** | **0.63** | **−0.76 / 4.6** |
| T2 6-month | 3.74% | 3.85% | 0.293 | −4.2% | −11.1% | 0.527 | 3.20 | 0.62 | −0.33 / 4.8 |
| T3 3-month | 3.33% | 3.68% | 0.197 | −6.7% | −7.2% | 0.505 | 4.39 | 0.59 | −0.40 / 4.8 |
| T4 blend | 3.80% | 3.67% | 0.322 | −4.6% | −10.1% | 0.559 | 2.81 | 0.63 | −0.40 / 3.9 |

Stress costs (2× base): Sharpe T1 0.323, B3 0.196, B4 0.196, T2 0.274, T3 0.169, T4 0.304; the sign of T1 − B4 holds. Source: `results/oos/metrics_10assets_base.csv`, `summary.json`.

Reading: T1 returned 1.3% a year over bills at 4% volatility. Its Sharpe advantage over B3 and B4 comes from a lower volatility and a far smaller monthly drawdown, not from a higher return (3.95% against 3.75% for B3); the daily drawdowns are close (−11.4% against −12.4% for B4), because the March 2020 fall happened inside one holding period, where a monthly rule cannot act. The ranking of the trials is the in-sample one (T1 > T4 > T2 > T3).

### Inference (§9.3 items 7–9) and criteria (§9.5)

| Trial | Sharpe 95% CI (stationary bootstrap, 10,000) | vs B3: NW mean (monthly) / t | vs B3: LW Sharpe diff (ann.) / p | vs B4: NW mean / t | vs B4: LW diff / p | O1 | O2 |
|---|---|---|---|---|---|---|---|
| T1 | −0.19 to 0.88 | +0.00006 / 0.06 | +0.137 / 0.45 | **+0.00027 / 0.35** | +0.137 / 0.46 | pass | pass |
| T2 | −0.34 to 0.85 | −0.00012 / −0.10 | +0.095 / 0.69 | +0.00009 / 0.10 | +0.095 / 0.69 | pass | pass |
| T3 | −0.56 to 1.01 | −0.00046 / −0.36 | −0.003 / 0.99 | −0.00025 / −0.24 | −0.003 / 0.99 | FAIL | FAIL |
| T4 | −0.35 to 0.91 | −0.00008 / −0.07 | +0.124 / 0.56 | +0.00013 / 0.16 | +0.124 / 0.57 | pass | pass |

No resample was degenerate. T1's Sharpe interval includes zero: the window cannot distinguish the rule from no edge. Deflated Sharpe ratio on the window (descriptive; no out-of-sample criterion uses it): T1 PSR 0.81, DSR 0.77 at N = 4, 0.75 at N = 10.

| Criterion (T1, base costs) | Required | Observed | Result |
|---|---|---|---|
| C1–C4 (in-sample) | all four | C1 FAIL, C2 FAIL, C3 pass, C4 pass | **FAIL** |
| O1 | mean(T1 − B4) > 0 | +0.00027 per month (t 0.35) | pass |
| O2 | Sharpe(T1) > Sharpe(B3) | 0.336 > 0.199 | pass |
| Drawdown clause | monthly max DD of T1 not worse than B4's | −4.1% vs −11.1% | not triggered |
| **Verdict for T1** | §9.5 table, precedence not supported > inconclusive > supported | any of C1–C4 fails | **not supported** |

T2–T4 do not affect the verdict; they are reported in full above. Had C1–C4 held, O1 and O2 would have made T1 "supported" and T3's out-of-sample failure would have downgraded it to "inconclusive" under the §9.5 clause on T2–T4; neither applies.

### Nine assets without IEF (§9.6, §2.4)

| | Ann. return | Ann. vol | Sharpe | Max DD (monthly) | Max DD (daily) | Mean gross exposure |
|---|---|---|---|---|---|---|
| B1 equal weight | 7.26% | 10.85% | 0.460 | −20.1% | −23.0% | 1.00 |
| B3 vol-scaled, always long | 4.36% | 6.96% | 0.273 | −13.3% | −16.8% | 0.93 |
| B4 = B3 × 0.7764 | 4.02% | 5.42% | 0.273 | −10.3% | −13.0% | 0.72 |
| **T1** | **4.09%** | **4.43%** | **0.340** | **−6.0%** | **−13.3%** | **0.62** |
| T2 / T3 / T4 | 3.84% / 3.55% / 3.95% | 4.27% / 3.84% / 3.97% | 0.291 / 0.245 / 0.339 | −5.5% / −6.1% / −4.7% | −12.9% / −8.0% / −11.4% | 0.61 / 0.58 / 0.61 |

T1: O1 pass (mean T1 − B4 +0.00002 per month, t 0.03; against B3 −0.00033, t −0.33), O2 pass (0.340 > 0.273), drawdown clause not triggered (−6.0% against −10.3%); verdict **not supported** on the same in-sample grounds. T2, T3 and T4 all fail O1 here (T3 fails O2 as well). The asset the author had seen is not what made the sign conditions hold for T1, but it is part of what made them hold for T2 and T4; the ten-asset run decides nothing either way, as registered. Source: `results/oos/metrics_9assets_base.csv`.

### Pre-registered descriptives for the window (§9.6; no decision weight)

**Crisis table** (cumulative return over the public dates fixed in §9.6; ten assets):

| Window | T1 | B1 | B2 | B3 | B4 | SPY (vendor) | IEF |
|---|---|---|---|---|---|---|---|
| 2020-02-19 to 2020-03-23 | −8.5% | −16.9% | −18.7% | −11.8% | −9.5% | −33.7% | +6.4% |
| 2020-02-19 to 2020-08-31 | −3.8% | +3.3% | +7.0% | −4.0% | −3.2% | +4.3% | +7.8% |
| 2022-01-01 to 2022-10-31 | −3.1% | −19.3% | −17.0% | −13.4% | −10.8% | −18.2% | −16.1% |

2022 is the episode the rule exists for, and it did what the literature says such rules do: with bonds, equities and credit falling together, the long/flat book was mostly in bills. 2020 is the episode a monthly long/flat rule handles worst: it was fully invested when the crash came, cut the book at the March month-end near the low, and sat out most of the rebound. Over the whole window those two episodes net to the Sharpe advantage above and nothing more.

**Per-asset attribution and timing** (T1, ten assets): GLD contributed +0.79% a year to T1's return, EEM +0.54%, HYG +0.43%, EFA +0.34%, LQD +0.29%, SHY +0.27%, IEF +0.23%, TLT +0.12%; IWM −0.08% and VNQ −0.08%. HYG, VNQ and LQD carried the largest variance shares (20%, 16%, 15%). Each asset's own long/flat Sharpe against its always-on volatility-scaled position: the signal **helped** on the four fixed-income legs (SHY 0.44 against −0.45, IEF 0.13 against −0.27, TLT 0.13 against −0.29, LQD 0.13 against −0.13) and on EEM (0.67 against 0.39); it **hurt** on IWM (−0.24 against 0.22), VNQ (−0.17 against 0.18), EFA (0.27 against 0.44), GLD (0.76 against 0.93) and HYG (0.03 against 0.13). This is the mirror image of the in-sample attribution, where the Treasury legs were the worst-timed: the signal's value here is one 2021–2024 exit from duration, which Study 003 found on IEF alone.

**Correlations** (monthly excess returns): T1 with SPY 0.53, with IEF 0.33; B3 with SPY 0.72, with IEF 0.60. The signal reduced the book's equity and duration correlation, as in-sample.

**Volatility forecast against realised** (diagonal, √Σ w²σ²): T1's realised 12-month volatility averaged 1.82× its forecast (74 months compared; 69% of months above 1.5×); B3's 2.32× (91% of months). Worse than in-sample (1.58×), for the reason §9.6 anticipated: the diagonal forecast ignores correlations, and 2020 and 2022 were the years in which everything moved together. First input to the programme's risk model.

**Power**: 122 on/off switches across the ten assets (floor 40), "as registered". Plots: `results/oos/exposure_drawdown_10assets.png` (gross exposure with the number of assets on; drawdown of T1 against B3 and B4) and `onoff_strips_10assets.png`; the nine-asset versions beside them. *Added 2026-10-23: the same daily index and metrics drawn to the chart standard of that date are in `charts/` (`oos_drawdown_10assets`, `oos_growth_10assets`, and the in-sample pair, SVG + PNG, built by `charts/make_charts.py` from the committed files with every title number in `charts/manifest.json`); the results/ charts stay as the run wrote them. On the daily series the deepest drawdown is −11.4% for T1 against −12.4% for B4 and −15.5% for B3, beside the monthly −4.1% against −11.1% above: the monthly figure is what the pre-registration scores, the daily one shows how little of it survives inside the month, which §9.7 already lists.*

## What did not work (§9.7; out-of-sample)

- The 3-month lookback (T3) failed both sign conditions: Sharpe 0.197 against 0.199 for B3, at 4.4× turnover; monthly trend with a one-quarter window is noise at these costs.
- Volatility targeting without leverage gave up the window's return: every vol-scaled variant (B3, B4, T1–T4) earned between 3.3% and 4.0% a year against 6.6% for equal weight and 10.6% for 60/40, and lost to both on Sharpe. The design choice §15 fixed (no leverage, 10% per asset) is the reason, and it was the right choice for a paper account that cannot borrow; it is also why this rule, even if it had been supported, would not have been worth trading over this window.
- The daily drawdown did not improve (−11.4% against −12.4% for B4): a monthly rule cannot act inside a month, and the one month that mattered (March 2020) fell inside a period.
- The 2020 exit cost more than it saved: −8.5% into the trough, then −3.8% by August while equal weight was up 3.3%.

## Limitations of what can be concluded (out-of-sample)

Ninety-three months of one window, with one episode (2022) carrying the whole advantage and one (2020) carrying the whole cost. The Sharpe interval for T1 (−0.19 to 0.88) contains zero. The author had seen IEF's path, and IEF's leg was one of the four where the signal helped; the nine-asset run says the sign conditions for T1 do not depend on it, and says nothing more. Ten instruments, not twelve; SPY's absence leaves the equity class small, and the study cannot say what the signal would have done on the largest equity ETF. Base costs are a model (2.0–3.5 bp per side); the sign held at double. Nothing here supports trading the rule; the pre-registered verdict says so, and the descriptives above are consistent with the published literature's claim that trend rules earn their keep in prolonged drawdowns and pay for it in sharp reversals, which is a statement about the 2019–2026 window and not evidence of an edge.

## Forward record (§11)

No paper order. The shadow record starts at the first month-end after this note's publication (2026-10-30): the terminal position from the 2026-09-30 signal is in `results/oos/signal_s12_10assets.csv` and `t1_periods_10assets_base.csv`; `paper-log/decisions/` and `paper-log/shadow.csv` are written from that date, never backdated.

*Addition, 2026-10-23 (§14 step 11, commit 5ad2453): the record's code is built and tested before its first month-end.* `./reproduce.sh --forward decide --signal-date t --fetch` writes the §11.1 decision record after 21:15 UTC on the last NYSE trading day of a month, from the broker's `adjustment='all'` bars, with the library functions the backtest called; `shadow` appends the §11.2 line for the period that ended at `t`'s execution date, marking three notional 10,000 USD books (T1, B3, B4) in the engine's own arithmetic (tested against `qune_research.engine.run`). The books start all cash on 2026-11-02; the holding period 2026-10-01 to 2026-11-02 belongs to the window's terminal signal and is counted nowhere. Gates, decisions and what is not built are in §16 (entry of 2026-10-23 15:2x) and in [paper-log/README.md](paper-log/README.md). A check-only run for 2026-08-31 and 2026-09-30 from the frozen vendor files reproduced the committed signal, volatility and weight files to 1e-16; nothing was written. First record: 2026-10-30; first shadow line after 2026-12-01. The verdict is unchanged: not supported.

## Reproduce

Tests (no data needed): `pip install -r requirements.txt` then `python -m pytest -q` here and in `qune_research/`. The run itself needs the vendor files (licensed, not committed) and the `APPROVED` file; `./reproduce.sh --check` then `--insample` reproduce `results/checks/` and `results/insample/` from the manifest's data (the vendor re-bases adjusted closes on each fetch, so file hashes will differ while every return ratio is unchanged); `--oos` refuses while `results/oos/` exists, as §8.2 requires (move it aside to reproduce the window; the committed output is the one that counts). Every statistic in this note is in `results/insample/summary.json` and `results/oos/summary.json`.

## Independent review (§14 step 10)

Reviewed on 2026-10-23 by a separate agent session that did not write the code, the pre-registration or this note: [REVIEW.md](REVIEW.md). Headline: **confirmed with findings.** The reviewer reran both test suites (18 study, 71 library, all passed), rebuilt every signal, weight, monthly return and daily index from the raw vendor files with its own engine (agreement to machine precision), recomputed 1,961 rows against `summary.json`, the CSVs and this note's text with `review_recompute.py` (1,937 match, 14 mismatch, 10 informational; no value in any results file mismatches), verified the 26 manifest hashes, applied the §9.5 table itself to its own numbers (same verdict for every trial and both universes), and checked from the commit times that every governing commit precedes the result it governs, including the end-bar amendment `1697e9d` before the out-of-sample results `784f6ed`. No must-fix findings; two should-fix; five notes.

Author's response, 2026-10-23, in the reviewer's order. (1) **Confirmed and corrected in place** (unlike Study 002's prose margin, which was a single phrase left with a note, these are table and text digits that a reader would copy): the fourteen figures had been rounded twice, first to one extra digit and then half-up, and each is now rounded once from the stored value. The changes, old → new: out-of-sample B3 and B4 Sharpe 0.200 → 0.199 (opening paragraph, the out-of-sample table, the O2 row and the T3 line of "What did not work"); out-of-sample T2 Sharpe 0.294 → 0.293; nine-asset in-sample B1 monthly drawdown −30.1% → −30.0%; nine-asset out-of-sample B1 Sharpe 0.461 → 0.460; in-sample T3 bootstrap interval 0.30 to 1.28 → 0.29 to 1.27; "advantage over B3 and B4 is 0.006" → 0.005; TLT variance share 12% → 11%; EFA and SHY long/flat Sharpe 0.56 → 0.55 and 0.89 → 0.88; sub-period 2004–2008 B1 return 6.4% → 6.3% and T2 drawdown −4.2% → −4.1%; sub-period 2016–2018 T3 Sharpe 0.54 → 0.53. The pre-correction text is in commit `4bd9187`; the trial log's O2 row and the root README's rows carried the same 0.200 and are corrected by a dated row and in place respectively. None of the fourteen is a criterion input; O2 is 0.336 against 0.199 either way. (2) **Confirmed**: five time labels in `trials.md` and one §16 heading were entered as estimates (20:3x, 20:4x, 21:3x, 22:4x, 23:3x) and never corrected; a dated correction row in `trials.md` and a dated §16 entry now give the committer times (20:27, 20:29, 21:25, 22:25, 23:20). The order of events is unchanged, as the reviewer's §5 shows. (3) Agreed: "any of C1–C4 fails" fixes the verdict on its own; the precedence rule is mentioned because §9.5 states it, not because it is needed. (4) Agreed; `fraction_asset_months_on` is a results-file column not used on this page and is left as computed, with this note as its errata. (5), (6), (7): no change.

Author's rerun of the reviewer's script before and after the corrections: 1,937 match, 14 mismatch, the same fourteen rows, because the script types the note's figures as they stood at `4bd9187` and keeps them as the record of what was found; its recomputed column is what the note now prints. `pytest`: 18 and 71 passed. Nothing re-run, no results file changed.

## Risk report (post hoc, 2026-10-23)

After the review, the shared library gained a risk module and this study was its first worked case: [risk/README.md](risk/README.md). It carries no decision weight and re-runs nothing; it reads the committed weights, volatilities and daily indices and the hash-checked raw files. Headline: the diagonal forecast's gap (1.60× in-sample, 1.79× out of sample on the holding-period definition) is entirely the missing correlations; a full 42-day-half-life covariance forecast from the same bars is unbiased in the mean in both windows (1.01, 1.03), shrinkage changes nothing on ten assets and 252 bars, and the normal one-day 99% VaR from that forecast was exceeded on 2.1% and 2.6% of days against 1% planned. The last book (2026-08-31 signal) is HYG at the cap plus small equity, property and gold legs, 49% in bills, with a frozen-book loss of −16.2% through the 2008 window and −13.8% through the 2020 one. Nothing here changes the verdict.

## Multiple-testing report (post hoc, 2026-10-23)

The shared library then gained a multiple-testing module and this study was its first worked case: [multiple/README.md](multiple/README.md). No decision weight, nothing re-run; it reads the committed monthly returns and metrics. Headline: taking T1–T4 as a family against B4, the best trial (T1 in every row) has a one-sided p-value of its own of 0.20 in-sample and 0.33 out of sample before any correction, and the family-wise p-values are 0.38 and 0.50 by Hansen's consistent SPA test (0.39 and 0.53 by White's Reality Check); against the unscaled B3 every trial has a lower mean return, so the statistic is zero. The minimum track record to be 95% confident that T1's Sharpe ratio exceeds B4's at the observed gap is about 1.4 million months in-sample and 1,900 out of sample, against 180 and 93 available. The deflated Sharpe ratio of §9.4 (0.998) and these tests do not conflict: one asks whether the best of four long-only books earns a positive Sharpe ratio, the other whether it beats the benchmark that already holds the same risk premium. The second is the study's question and the answer is the verdict above.
