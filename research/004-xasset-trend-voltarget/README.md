# Study 004: cross-asset time-series momentum with volatility targeting, ten liquid ETFs, long-only or flat

**Status: in-sample complete (§14 step 7); out-of-sample not yet run.** The verdict will be set by the §9.5 table after the single out-of-sample run. Pre-registration: [PREREGISTRATION.md](PREREGISTRATION.md) (committed before any data were fetched); trial log: [trials.md](trials.md); data checks: [results/checks/data_checks.md](results/checks/data_checks.md); in-sample outputs: `results/insample/`.

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
| T3 | 0.30 to 1.28 | −0.00090 / −1.53 | −0.114 / 0.54 | −0.00027 / −0.56 | −0.114 / 0.54 | −0.00032 / −0.68 |
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
| B1 | 6.87% | 10.84% | 0.563 | −30.1% | 0.46 | 1.00 |
| B3 | 5.09% | 4.72% | 0.838 | −9.5% | 0.89 | 0.93 |
| B4 = B3 × 0.7764 | 4.22% | 3.68% | 0.838 | −7.3% | 0.69 | 0.72 |
| **T1** | **4.70%** | **4.05%** | **0.879** | **−5.4%** | **1.86** | **0.72** |
| T2 / T3 / T4 | 4.11% / 3.90% / 4.30% | 3.76% / 3.67% / 3.69% | 0.793 / 0.756 / 0.858 | −5.9% / −6.4% / −5.2% | 2.30 / 3.19 / 2.20 | 0.67 / 0.64 / 0.68 |

T1 vs B4: NW mean +0.00040, t = 0.74; LW Sharpe difference +0.041, p = 0.85; DSR 0.998 at N = 4 (the trial-variance floor was applied: the four trials' monthly Sharpe ratios were closer than the floor). C1 FAIL (0.879 vs 0.938), C2 FAIL, C3 pass, C4 pass: **the same four outcomes as the ten-asset run**, so the one non-blind asset does not change the in-sample reading. 150 switches.

## Pre-registered descriptives (§9.6; no decision weight)

**Per-asset attribution, T1 (ten assets).** Contribution to the arithmetic annual return (the ten legs sum to 4.2% a year; the remainder of the 4.6% is the cash leg) and share of the gross return's variance; asset-months on out of months present: IWM 0.45% / 10% / 139 of 180; EFA 0.53% / 12% / 123; EEM 0.48% / 10% / 122 of 176; SHY 0.28% / 2% / 124; IEF 0.46% / 11% / 123; TLT 0.31% / 12% / 123; LQD 0.50% / 15% / 124; HYG 0.38% / 8% / 97 of 128; GLD 0.40% / 8% / 98 of 157; VNQ 0.41% / 12% / 119 of 159. No asset dominates; the risk is spread as the sizing intends. Each asset's own long/flat position against its own always-on position (annualised Sharpe of the weighted excess return): the signal helped in EFA (0.56 vs 0.43), EEM (0.54 vs 0.46), SHY (0.89 vs 0.67), HYG (0.66 vs 0.41) and hurt in IEF (0.38 vs 0.50), TLT (0.25 vs 0.49), LQD (0.45 vs 0.52), VNQ (0.49 vs 0.53); IWM and GLD were a wash. **Timing the Treasury legs cost the most**, the same reading Study 003 reached for IEF alone.

**Crisis table (in-sample window, §9.6).** 2008-09-01 to 2009-02-28, cumulative: T1 **+2.4%**, B1 −20.7%, B2 −24.4%, B3 −5.3%, B4 −4.2%, SPY −41.4%, IEF +6.4%. This is the episode the design exists for and the signal did what it should: by September 2008 the equity, credit and real-asset legs were flat and the book sat in Treasuries and cash. It is one episode, as the 2022 exit was for Study 003. Nine-asset run: T1 +1.9%, B3 −6.5%, B4 −5.1%.

**Correlations (monthly excess returns, in-sample).** T1 with SPY 0.30, with IEF 0.43; B3 with SPY 0.54, with IEF 0.42. The signal roughly halves the equity beta of the volatility-scaled book while leaving the Treasury beta unchanged; this, not the Sharpe ratio, is where the 2008 figure comes from.

**Volatility forecast against realised.** The ex-ante diagonal forecast √(Σ w_i² σ_i²) of T1's annualised volatility averaged 2.4%; the realised rolling 12-month figure averaged 3.7%; mean ratio 1.58; realised exceeded forecast by more than half in **53% of the 169 months compared** (B3: 2.6% vs 4.2%, ratio 1.61, 54%). As §9.6 anticipated, the diagonal forecast understates the portfolio's volatility by a large factor because it ignores the positive correlations between the legs. This is the first input to the risk model the programme builds next; it is a finding about the forecast, not a tuning target.

**Breakeven cost curve (ten assets, k frozen).** Sharpe(T1) − Sharpe(B4) at 0×, 0.5×, 1×, 2×, 3×, 5× base cost: +0.013, +0.009, +0.005, −0.002, −0.010, −0.025; **zero crossing at 1.70× base cost**. Even with no costs at all the advantage is 0.013 Sharpe, an eighth of the C1 margin. Nine assets: +0.047 at 0× falling to +0.016 at 5×, no crossing.

**Sub-periods (by holding-period start month; Sharpe, annual return, monthly max DD).**

| Period | B1 | B3 | B4 | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|---|---|
| 2004-01..2008-12 | 0.34, 6.4%, −26.0% | 0.62, 5.8%, −8.3% | 0.62, 5.2%, −6.6% | **1.01, 7.0%, −4.1%** | 0.59, 5.0%, −4.2% | 0.69, 5.4%, −4.0% | 0.83, 5.9%, −4.1% |
| 2009-01..2015-12 | 0.82, 7.7%, −8.5% | 1.16, 4.9%, −5.5% | 1.16, 3.9%, −4.4% | 1.13, 4.2%, −4.0% | 0.94, 3.3%, −6.1% | 0.90, 3.3%, −5.6% | 1.06, 3.7%, −5.1% |
| 2016-01..2018-12 | 0.70, 4.7%, −5.3% | 0.68, 3.7%, −4.6% | 0.68, 3.1%, −3.7% | **0.17, 1.6%, −5.2%** | 0.45, 2.6%, −4.1% | 0.54, 2.5%, −3.2% | 0.36, 2.2%, −4.2% |

The whole of T1's in-sample advantage sits in 2004–2008, which contains the one crisis; in 2009–2015 it matched B3 and in 2016–2018 it lost clearly (Sharpe 0.17 against 0.68), the pattern the agenda called trend's 2010s decay.

**Power statement (§9.6).** 167 on/off switches across the ten assets in-sample, 0.6 (SHY) to 1.7 (TLT, LQD, GLD) per asset per year; threshold 40; **the in-sample test is "as registered"**, not low-powered. The §9.5 failures are therefore not for want of signal changes.

Plots: `results/insample/exposure_drawdown_10assets.png` (T1 gross exposure and assets on; daily drawdown of T1, B3, B4), `onoff_strips_10assets.png`, and the nine-asset pair.

## What did not work (§9.7; in-sample)

- **C1 and C2 for every trial.** T1's Sharpe advantage over B3 and B4 is 0.006; the margin was 0.10. The monthly difference against B4 has t = 0.65. T2 (6-month), T3 (3-month) and T4 (blend) are worse than T1 and worse than B3 on Sharpe (0.72, 0.77, 0.84 against 0.88), with two to three and a half times B3's turnover.
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

## Out-of-sample (§8.2, §14 step 8)

Not yet run. It will be run once by `reproduce.sh --oos` on the same vendor series with actual BIL as cash, k frozen at 0.8018 (ten) and 0.7764 (nine), after this note is committed; its outputs go to `results/oos/` and are never re-run. The §9.5 verdict for T1 is already fixed as **not supported** by the in-sample C1 and C2 failures; the out-of-sample section will report O1, O2, the 2020 and 2022 crisis windows and the drawdown clause as pre-registered, and say plainly that IEF's path in that window was not blind to the author.

## Reproduce

Tests (no data needed): `pip install -r requirements.txt` then `python -m pytest -q` here and in `qune_research/`. The run itself needs the vendor files (licensed, not committed) and the `APPROVED` file; `./reproduce.sh --check` then `--insample` reproduce `results/checks/` and `results/insample/` from the manifest's data (the vendor re-bases adjusted closes on each fetch, so file hashes will differ while every return ratio is unchanged). Every statistic in this note is in `results/insample/summary.json`.
