# Post-hoc: NaN bootstrap intervals for T1 out-of-sample (descriptive, no decision weight)

T1's excess return over B0 is exactly zero in 50 of 93 out-of-sample months (the months it held BIL, which is B0). Resamples drawn only from those months have zero variance and an undefined Sharpe ratio, and a quantile over a vector containing NaN is NaN. The point estimates, t-statistics and p-values in `summary.json` are unaffected.

| Statistic | As published | Dropping degenerate resamples |
|---|---|---|
| Stationary-bootstrap 95% CI of T1's annualised Sharpe | NaN, NaN | [-0.698, 0.947] (1 of 10000 resamples dropped) |
| Ledoit-Wolf 95% CI of the annualised Sharpe difference, T1 - B3 | NaN, NaN | [-0.460, 1.429] (4 dropped; p = 0.332 on finite resamples, 0.332 as published) |

Nothing in `results/oos/summary.json` or the CSVs was changed. A successor study should define the Sharpe ratio of a resample with zero variance (or exclude such resamples by a rule) before running.
