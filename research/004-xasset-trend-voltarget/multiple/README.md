# Multiple-testing report for Study 004's four trials (post hoc)

**Status:** descriptive, built 2026-10-23 after the study's results and its independent review. It changes nothing in `results/`, carries no decision weight and is not a re-run: `spa_report.py` reads the committed monthly holding-period returns and metrics files and applies two tests the pre-registration did not name. The study's verdict stands on §9.5 alone; this page says what the family of trials looks like under a correction the deflated Sharpe ratio of §9.4 approximates in a different way. Every number here is in `report.json` (settings, library commit, every test's full output) and `family_tests.csv`.

The question. The study registered four trials (T1 12-month, T2 6-month, T3 3-month, T4 the 12-month sign on the 10-month SMA) and tested the first against the exposure-matched volatility-scaled book B4 with C1 and C2. A reader who sees T1 "pass both out-of-sample sign conditions" might ask what the best of four lookbacks is worth once the choice among four is paid for. White's (2000) Reality Check and Hansen's (2005) SPA test answer that for the family: the null is that **no** trial beats the benchmark in expectation, and the p-value is for the best trial's statistic under that null, with the search accounted for by bootstrapping the whole family together (stationary bootstrap, 10,000 resamples, 12-month expected block, the study's own §9.3 values; seed 20261023, chosen once). Hansen's consistent version keeps a plainly poor trial's negative mean in the bootstrap instead of recentring it to zero, so a family padded with bad trials cannot look better than it is; the lower and upper p-values bracket it.

*Correction by dated addition, 2026-10-24 (found while checking the post-hoc labels after the [cold read](../../../COLD_READ.md), point 10):* the sentence above misdescribes T4. As registered (`PREREGISTRATION.md` §7, `trials.md`, `src/config.py` `LOOKBACKS_MONTHS`), T4 is the **blend**: each asset is on at the average of its 12-, 6- and 3-month signals (0, ⅓, ⅔ or full size). No 10-month moving average is used anywhere in Study 004 (that rule is Study 003's T3). The tests below read the committed T4 return column, so no figure changes; only the description was wrong.

## 1. Family tests: the best of T1–T4 against the benchmark

| Window | Universe | Benchmark | Best trial | SPA statistic | SPA p (lower / consistent / upper) | Reality Check p | Trial t-statistics T1 / T2 / T3 / T4 | Best trial's own one-sided p |
|---|---|---|---|---|---|---|---|---|
| In-sample 2004–18 (180 months) | ten | B4 | T1 | 0.82 | 0.26 / 0.38 / 0.38 | 0.39 | 0.82 / −0.83 / −0.65 / −0.14 | 0.20 |
| In-sample | ten | B3 | T1 | 0.00 | 1.00 / 1.00 / 1.00 | 0.89 | −0.61 / −1.83 / −1.88 / −1.53 | 0.73 |
| In-sample | nine without IEF | B4 | T1 | 0.96 | 0.25 / 0.31 / 0.31 | 0.33 | 0.96 / −0.17 / −0.61 / 0.18 | 0.16 |
| In-sample | nine | B3 | T1 | 0.00 | 1.00 / 1.00 / 1.00 | 0.90 | −0.66 / −1.38 / −1.91 / −1.37 | 0.73 |
| Out-of-sample 2019–26 (93 months) | ten | B4 | T1 | 0.41 | 0.47 / 0.50 / 0.50 | 0.53 | 0.41 / 0.11 / −0.26 / 0.18 | 0.33 |
| Out-of-sample | ten | B3 | T1 | 0.06 | 0.54 / 0.60 / 0.60 | 0.61 | 0.06 / −0.11 / −0.40 / −0.08 | 0.45 |
| Out-of-sample | nine | B4 | T1 | 0.04 | 0.59 / 0.67 / 0.67 | 0.66 | 0.04 / −0.25 / −0.47 / −0.16 | 0.48 |
| Out-of-sample | nine | B3 | T1 | 0.00 | 1.00 / 1.00 / 1.00 | 0.75 | −0.39 / −0.53 / −0.69 / −0.48 | 0.63 |

The t-statistics are √n × mean(trial − benchmark) / ω with ω the bootstrap standard deviation of the scaled mean (Hansen's eq. 7 from the resamples); they are not the Newey-West t of the note, which is on T1 − B4 alone (0.65 in-sample, 0.35 out of sample) and uses a Bartlett kernel instead of the bootstrap. The two agree in sign and order of magnitude in every row.

What the table says:

- **Against B4, nothing survives, and nothing needed correcting to see it.** The best trial is T1 in every row, with a one-sided p-value of its own of 0.20 in-sample and 0.33 out of sample before any correction; the family-wise p-values are 0.38 and 0.50. The mean advantage of T1 over B4 is 3.3 basis points a month in-sample and 2.7 out of sample.
- **Against B3, the unscaled book, every trial has a lower mean return**, so the SPA statistic is zero and the p-value is one in both windows: volatility scaling with no leverage gives up mean return (the note's "What did not work"); the trend signal does not win it back.
- **The consistent and upper p-values coincide against B4** because no trial is far enough below zero to cross Hansen's threshold −√(2 log log n) (−1.8 at these lengths): the family holds no plainly bad trial, so the Reality Check's recentring and Hansen's agree. Against B3 in-sample, two (ten assets) and one (nine) trials cross it, which is why the Reality Check p there (0.89, 0.90) sits below the SPA's 1.00: the SPA refuses to let T2 and T3's poor showing improve the family's chances.
- **The deflated Sharpe ratio of the note (0.998 at N = 4) and this page are not in conflict.** The DSR asks whether T1's Sharpe ratio is above zero after the expected maximum of four near-identical trials; it is, comfortably, because every trial earns the market's risk premium through the long-only book. The SPA asks whether the best trial beats the *benchmark that already holds that premium*; it does not. The second is the study's question.

## 2. Minimum track-record length (Bailey and Lopez de Prado, 2012)

How many months of T1's own record, at its observed monthly Sharpe ratio, skewness and kurtosis, would be needed to be 95% confident that its Sharpe ratio exceeds a benchmark level?

| Window | Universe | T1 Sharpe (monthly) | B4 Sharpe (monthly) | T1 skew / kurtosis | Months for SR > 0 at 95% | Months for SR > B4's at 95% | Months available |
|---|---|---|---|---|---|---|---|
| In-sample | ten | 0.256 | 0.254 | −0.44 / 3.89 | 49 | 1,372,470 | 180 |
| In-sample | nine | 0.254 | 0.242 | −0.53 / 3.69 | 51 | 23,023 | 180 |
| Out-of-sample | ten | 0.097 | 0.058 | −0.76 / 4.64 | 313 | 1,893 | 93 |
| Out-of-sample | nine | 0.098 | 0.079 | −1.06 / 6.27 | 314 | 8,109 | 93 |

The record is long enough to say T1 earns a positive Sharpe ratio in-sample (49 months needed, 180 available) and not yet out of sample (313 needed, 93 available). Against B4's Sharpe ratio the gaps are so small (0.0015 a month in-sample) that the required record is measured in centuries and millennia: at the observed difference the question "does the signal add to volatility scaling?" cannot be settled by any track record anyone will have. This is the quantitative form of the note's power statement: the test was not low-powered by the registered switch count, and the effect it measured is close to zero.

## 3. What this page does not do

It does not change the verdict, re-run a window, add a trial or re-weight anything. The tests use the trials as registered (N = 4) and the benchmark the pre-registration made decisive. The seed and settings were chosen once before the script ran and were not varied; the script was run once on commit `0a1c7e8` of the library (`report.json`, field `commit_before_run`). Nothing here is advice.

Library: `qune_research/multiple.py` (nine tests on constructed data; 98 in the library suite). References with DOIs are in the module docstring.
