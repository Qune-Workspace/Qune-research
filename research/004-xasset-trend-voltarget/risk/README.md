# Risk report for Study 004's T1 book (post hoc)

**Status:** descriptive, built 2026-10-23 after the study's results and its independent review. It changes nothing in `results/`, carries no decision weight and is not a re-run: `risk_report.py` reads the committed weights, volatilities and daily indices, re-opens the same raw vendor files (each SHA-256 checked against `results/data_manifest.json` before use, refusing on a mismatch) and applies the shared library's risk module (`qune_research/risk.py`, 18 tests on constructed data). Every number on this page is in `report.json`; the per-month rows are in the CSV files beside it. The script ran once, in 6 seconds, at the commit named in `report.json`.

The question it answers is the one the study left open (§9.6, README "Volatility forecast against realised"): the pre-registered diagonal forecast √(Σ w²σ²) understated the book's realised volatility by about 1.6× in-sample and 1.8× out of sample. How much of that gap is the missing correlations, and would a full covariance forecast made with the same information have described what followed?

## 1. Volatility forecasts against the holding period that followed

At each signal date t the four forecasts use only bars up to t: the study's own diagonal figure; a full covariance exponentially weighted over the last 252 bars with a 42-day half-life (`ewma`); the same shrunk toward constant correlation with the Ledoit-Wolf (2004) intensity estimated on the window (`shrunk`); and the equal-weighted 252-bar sample covariance (`sample`). Realised is the annualised standard deviation of T1's daily net index over the holding period the forecast covered (execution close to period end, about 21 days). Months in cash have no forecast (nine out of sample, none in-sample).

| Window | Forecast | Months | Mean forecast | Mean realised | Mean ratio realised/forecast | Median ratio | Share of months realised > 1.5× forecast | Mean log ratio | Slope through origin |
|---|---|---|---|---|---|---|---|---|---|
| In-sample 2004–2018 | diagonal (the study's) | 180 | 2.47% | 3.96% | 1.60 | 1.47 | 47% | +0.41 | 1.60 |
| | ewma 42d | 180 | 4.00% | 3.96% | 1.01 | 0.90 | 8% | −0.05 | 0.98 |
| | shrunk ewma | 180 | 4.00% | 3.96% | 1.01 | 0.90 | 8% | −0.05 | 0.98 |
| | sample 252d | 180 | 4.30% | 3.96% | 0.97 | 0.89 | 9% | −0.10 | 0.87 |
| Out of sample 2019–2026 | diagonal (the study's) | 84 | 2.22% | 4.04% | 1.79 | 1.63 | 57% | +0.48 | 1.83 |
| | ewma 42d | 84 | 4.06% | 4.04% | 1.03 | 0.93 | 6% | −0.07 | 0.96 |
| | shrunk ewma | 84 | 4.06% | 4.04% | 1.03 | 0.94 | 6% | −0.07 | 0.96 |
| | sample 252d | 84 | 4.56% | 4.04% | 0.97 | 0.82 | 10% | −0.15 | 0.80 |

**Reading.** The whole of the study's forecast gap is the missing correlations: a full covariance forecast from the same bars is unbiased in the mean in both windows (ratio 1.01 and 1.03), with no change in the ordering of months. Shrinkage adds nothing here: the mean Ledoit-Wolf intensity is 0.08 in-sample and 0.15 out of sample on a 252-bar window of ten assets, so the shrunk and unshrunk forecasts are the same to the second decimal. The equal-weighted sample covariance over-forecasts (mean ratio 0.97, slope 0.80–0.87) because it carries old volatility for a year. The median ratio of 0.90–0.94 beside a mean of 1.01–1.03 says realised volatility is right-skewed around the forecast: most months come in a little under it and a few come in far over, which no covariance forecast made at t can see. The numbers agree with the study's own rolling-window figures (1.58 and 1.82) within the difference of definition.

## 2. One-day 99% value at risk from the shrunk forecast, backtested

A normal 1-day 99% VaR from each month's shrunk covariance was compared with T1's daily net returns in that holding period.

| Window | Days | Exceedances | Rate | Expected |
|---|---|---|---|---|
| In-sample | 3,780 | 80 | 2.1% | 1.0% |
| Out of sample | 1,756 | 46 | 2.6% | 1.0% |

The normal tail is too thin by a factor of two to two and a half, even with an unbiased volatility: the loss days cluster and are fatter than the model. Out of sample the historical 1-day 99% VaR of T1's daily index was 0.80% (expected shortfall 1.30%, 20 tail days of 1,945), against a parametric figure of 0.64% for the last book. A desk that sized on the normal VaR would have been surprised about twice as often as it planned to be; the honest use of the number is as a scale, with the exceedance rate printed beside it.

## 3. Where the risk sat

Euler contributions to variance from the shrunk covariance, averaged over the months the asset was held.

| Asset | In-sample mean share | Out-of-sample mean share |
|---|---|---|
| IWM | 13% | 10% |
| EFA | 13% | 15% |
| EEM | 12% | 10% |
| SHY | 3% | 2% |
| IEF | 11% | 6% |
| TLT | 10% | 5% |
| LQD | 11% | 11% |
| HYG | 9% | 16% |
| GLD | 7% | 14% |
| VNQ | 11% | 11% |

Volatility targeting made the weights unequal but the risk roughly equal across the three equity legs, credit and property, with the Treasury legs carrying less and SHY almost none; out of sample the Treasury share halved as the signal took them out, and HYG and gold grew. The pre-registered diagonal sizing aimed at equal *stand-alone* risk per leg; the realised contributions show that the correlated legs (equities, credit, property) dominated the book's variance.

## 4. The last book through four historical windows

The weights set at the 2026-08-31 signal (held through September 2026): HYG 25.0% (at the cap), EFA 6.7%, VNQ 6.6%, IWM 6.0%, GLD 3.7%, EEM 3.1%; no Treasuries, no LQD; 49% in bills. Full-covariance volatility forecast 4.4% against the diagonal's 2.4%; shrunk-forecast 1-day 99% VaR 0.64%. Held unchanged through each window, with the cash part in BIL:

| Window | Book return | Largest leg |
|---|---|---|
| GFC 2008-09-01..2009-02-28 | −16.2% | HYG −5.8% |
| Taper 2013-05-21..2013-09-05 | −2.3% | VNQ −1.2% |
| COVID 2020-02-19..2020-03-23 | −13.8% | HYG −5.5% |
| 2022 2022-01-01..2022-10-31 | −8.4% | HYG −3.1% |

The book that the rule holds today is a credit-and-equity book with half its value in bills; its risk is HYG's. A trend rule would have exited some legs inside the longer windows, so these are the losses of the *frozen* book, the right number for a limit and the wrong number for a backtest.

## 5. A drawdown rule, described and not applied

A linear rule cutting exposure in proportion to the drawdown from the running high, to zero at a 10% drawdown, applied after the fact to T1's daily index: it would have reduced exposure on 87% of in-sample days and 88% of out-of-sample days (the book was below its high most of the time, as a 4%-volatility book is), reaching a minimum multiplier of 0.32 in-sample (2018-10-26, drawdown −6.8%) and 0.00 out of sample (2020-03-19, drawdown −11.4%). At this volatility a 10% limit is a rule that is almost always on and would have taken the book flat at the bottom of March 2020, one week before the rebound; a limit scaled to the forecast volatility (say 2.5 forecast standard deviations) would be the thing to pre-register, and nothing is pre-registered here.

## 6. What this is and is not

- It is a description of a published result's risk, made with information available at each date, and a test of the library's covariance forecasts on a real book. The diagonal forecast's gap is explained; the full forecast is unbiased; its normal VaR is not.
- It is not a new rule, a tuning of Study 004 or evidence about trend-following. The half-life (42 days), the lookback (252 bars), the VaR level and the drawdown limit were chosen once, before the script ran, and were not varied.
- The next study that sizes on volatility should pre-register the full covariance forecast (Study 005, if its question calls for sizing) and its own VaR exceedance target.

## Files

- `risk_report.py`: the script; `report.json`: every number here with the commit, file hashes and settings.
- `forecasts_insample.csv`, `forecasts_oos.csv`: per month, the four forecasts, the realised volatility, the Ledoit-Wolf intensity, the 1-day VaR and the exceedances.
- `risk_contributions_insample.csv`, `risk_contributions_oos.csv`: per month, the Euler shares.
- `stress_last_book.csv`: the four windows for the last book, by leg.
