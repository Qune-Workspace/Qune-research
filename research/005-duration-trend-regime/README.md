# Study 005 — Trend exits from duration, conditional on the stock-bond correlation regime

**In-sample check: refuted in-sample** (pre-registered row, §9.5; run once on 2026-10-23). The hypothesis was that Study 003's 12-month trend exit from IEF adds value when the trailing 63-day SPY–IEF correlation is positive and costs when it is negative. **Over 2003-08 to 2018-12 the exit cost more in the positive regime, not less**: the trend-minus-hold return d_t averaged **−0.32% a month in the 26 positive-regime months** against **−0.03% in the 159 negative-regime months**, a conditional edge Δ of **−0.30% a month** (Newey–West t −2.31; stationary-bootstrap 95% interval [−0.52%, +0.03%] a month). The interval's upper bound, +0.03% a month, is below the smallest believable edge written down beforehand (0.083% a month, 1% a year), which is the refuted row. The minimum detectable effect at the actual regime counts, filled in before any return was seen, was 4.37% a year (§16), so this window could never have supported the hypothesis; it could refute it, and it did. The 252-day variant (T2, descriptive) is refuted on the same row (Δ −0.59% a month, t −3.11, interval [−2.11%, −0.11%]); the inflation-regime variant (T3, descriptive) is **sign consistent** (Δ +0.10% a month, t 0.81, interval [−0.12%, +0.30%]): both half-means have the predicted sign but the interval contains zero and the edge is a third of the detectable size, so the row says what it is, not a confirmation. Where T1 and T3 disagree, T1 is the registered primary and its row stands.

**This study has no "supported" row from history and places no paper order.** The 2019–2026 window generated the hypothesis and was run once under that label with no decision weight (below): the exit helped there, but the correlation regime did not flag the months in which it helped, because the correlation turned positive five months into the 2022 sell-off; the conditional rule gave back more than half of what the exit had saved. The forward record (§11) is kept from the first month-end after this note's publication, 2026-10-30, labelled "refuted in-sample", and scored once by the stopping rule. Published 2026-10-23; independent review (§14 step 10) to follow.

Everything on this page is a backtest on historical ETF prices and bill yields. Nothing here is a track record, a forecast or investment advice. The question, hypothesis, regime variables, benchmarks, costs, criteria and order of operations were fixed in [`PREREGISTRATION.md`](PREREGISTRATION.md) before any fetch, correlation or return (`60f211e`); the trial log is [`trials.md`](trials.md).

What happened, in order (every step is a dated commit; times are London):

1. 2026-10-23, 08:2x: question note committed (`b9ad02e`), then the pre-registration (`60f211e`, 09:2x). No fetch, no regime share, no return.
2. 2026-10-23, 10:2x–11:2x: code and tests (`0281f89`, `218519b`): five Study 003 modules copied frozen so that the ported unconditional rule reproduces Study 003's committed monthly file to 1e−10 (test (i), passed on this machine); 29 tests. `APPROVED` written after `reproduce.sh` had refused without it.
3. 2026-10-23, 11:21–11:22: the two fetches of §5.3.3, each logged first (`80a2a2f` → `1fc0178` → `3f20db5`): Alpaca SPY 2018-09-04 to 2026-09-30 (2,029 bars) and FRED CPIAUCNS (1,365 months). Both succeeded on the first attempt; no branch taken.
4. 2026-10-23, 11:22–11:25: the data checks (`85381f2`), three invocations of one script: the first stopped in D3 on a missing CPI print (the BLS published no October 2025 CPI), the second on an idempotency fault in this study's file reuse, the third completed; D0 and D1 were identical in all three (diff observed). Each stop and fix is a dated §16 entry or commit written before the next invocation, and no regime share, correlation on a signal date or return had been seen when they were written.
5. 2026-10-23, 11:27: T1–T3 run rows logged (`840cdbd`), then `reproduce.sh --insample`, the single in-sample run, committed as written (`e60ab05`). Results below. The in-sample section of this note was committed at 11:29 (`24086b3`).
6. 2026-10-23, 12:16: the 2019–2026 episode logged (`7f01c30`), then `reproduce.sh --episode`, run once, committed as written (`94c93a3`). Reported below under its label, no decision weight.
7. 2026-10-23, 12:xx: this note finished and published (the commit carrying this line); forward record from 2026-10-30; independent review next. *Corrected 2026-10-23 13:3x: 12:21 London, commit 6826dd3 (review finding 3).*
8. 2026-10-23, 13:2x: the §9.7 charts (`charts/`, commit 1822ae0). 13:3x: independent review published (`REVIEW.md`, §14 step 10): **confirmed with findings**, no must-fix; the findings are answered in the review section below by dated additions, nothing above rewritten.

## Data checks (§5.3; dates, correlations of instrument returns and a reading of a committed file; no rule applied)

| Check | Statistic | Threshold | Observed | Result |
|---|---|---|---|---|
| D0 | Tiingo IEF and SPY bars on NYSE trading days 2003-04-01 to 2018-12-31; IEF's first bar | all days, ≤ 3 consecutive missing; first bar ≤ 2002-07-31 | complete; IEF first bar 2002-07-26 | pass |
| D0 | Alpaca SPY, IEF, BIL bars 2018-09-04 to 2026-09-30 | all days, ≤ 3 consecutive missing | complete | pass |
| D1 | Share of days 2016-01-04 to 2018-12-31 on which the 63-day correlation's sign agrees between Tiingo and Alpaca closes | none (descriptive; discussion owed below 95%) | **1.0000** on 691 days; mean absolute difference of the correlations 0.0060, largest 0.0190 | no discussion owed |
| D3 | σ_d from Study 003's committed in-sample file; positive-regime months (T1) | rows apply at ≥ 12 | σ_d = 0.692% a month; **26 of 185 (14.1%)**; MDE **4.37% a year** | rows apply |

D3 in full (`results/checks/d3.json`): T1 had 9 positive episodes of mean 2.9 months (longest 7); T2 12 positive months in 3 episodes; T3 43 positive months in 6 episodes (longest 14). In the 2019–2026 episode (no decision weight) the T1 regime was positive on 38 of 93 signal dates, three times the in-sample share: the window the question came from looks unlike the window that tests it, and that was the first number to say so. One T3 month in the episode (the 2025-12 signal date) reads September 2025's CPI print under the §16 amendment for the missing October 2025 value; no in-sample month is affected.

## In-sample results (2003-08 to 2018-12, 185 monthly holding periods; `results/insample/`)

The conditional edge (§9.2–9.3), base costs (2 bp per side on B2's switches, none on B1):

| Trial | Regime | n_pos | n_neg | mean(d \| pos) | mean(d \| neg) | Δ per month | NW t | 95% bootstrap interval for Δ | §9.5 row |
|---|---|---|---|---|---|---|---|---|---|
| **T1** | 63-day correlation > 0 | 26 | 159 | **−0.325%** | −0.029% | **−0.296%** | **−2.31** | [−0.519%, **+0.027%**] | **refuted in-sample** |
| T2 (descriptive) | 252-day correlation > 0 | 12 | 173 | −0.625% | −0.032% | −0.593% | −3.11 | [−2.110%, −0.108%] | refuted in-sample |
| T3 (descriptive) | CPI 12-month change (m−2) > 3% | 43 | 142 | +0.007% | −0.094% | +0.101% | 0.81 | [−0.125%, +0.302%] | sign consistent, forward record decides |

Stress costs (4 bp) move Δ by at most 0.007% a month (T2) and change no row. T2's bootstrap dropped 480 of 10,000 resamples that contained no positive-regime month (12 positive months in 3 episodes resample to none often); T1 and T3 dropped none. The half-mean intervals: T1's positive-regime mean is [−0.51%, −0.04%] (the whole interval negative), its negative-regime mean [−0.12%, +0.07%].

**The mechanism, in the numbers it was supposed to run on.** In the positive-regime months B2 was in bills 62% of the time (against 26% in the negative regime), so the regime did catch the months in which the trend rule exits. But IEF's mean excess return over cash in those months was **+0.22% a month**, not negative: the exits in the positive regime were exits from a rising bond market. Of the nine positive episodes (`results/insample/positive_episodes_T1.csv`), IEF's excess return was positive in six, including the longest (April to October 2006, seven months, B2 in bills throughout, IEF +4.5% over cash); the three episodes in which IEF fell (July–August 2005, May 2015, September–October 2016; five months together) were all ones in which B2 held IEF. The hypothesis needed positive-regime months to be the months in which bonds fell; in 2003–2018 they were, on average, months in which bonds rose.

By sub-period (base costs, T1; §9.7, no decision weight): 2003-08 to 2008-12 had 19 of the 26 positive months and Δ = −0.48% a month; 2009-01 to 2015-12 had 5 and Δ = −0.11%; 2016-01 to 2018-12 had 2 and Δ = +0.13% (two months). The sign of the result is the first sub-period's, where most of the positive-regime months are.

Strategies and benchmarks (base costs; the twelve metrics of Study 001 §9.3 are in `metrics_base.csv`):

| | Ann. return | Ann. vol | Sharpe (excess over cash) | Max drawdown (monthly) | Switches | Share of months in IEF |
|---|---|---|---|---|---|---|
| **T1** conditional rule | 3.93% | 6.17% | 0.471 | −8.3% | 9 | 91.4% |
| T2 (252-day) | 3.99% | 6.19% | 0.479 | −8.1% | 9 | 94.6% |
| T3 (CPI regime) | 4.53% | 6.19% | 0.565 | −8.1% | 5 | 91.9% |
| B0 cash | 1.14% | 0.47% | — | −0.4% | 0 | 0% |
| B1 hold IEF | 4.51% | 6.27% | 0.555 | −8.1% | 0 | 100% |
| B2 Study 003's trend rule | 3.66% | 5.82% | 0.452 | −8.6% | 18 | 69.2% |
| B3 constant mix at T1's IEF share (w = 0.914) | 4.23% | 5.73% | 0.555 | −7.4% | 0 | 91.4% |

T1 made 9 of B2's 18 switches and sat between B2 and B1, as a rule that applies B2's exits in 14% of months must: T1 − B2 averaged +0.024% a month (NW t 0.51), T1 − B3 −0.022% (t −0.79). Its Sharpe interval is [0.00, 0.89]. The deflated Sharpe ratio at N = 3 is 0.959 (0.945 at N = 10), reported without decision weight as §9.4 says; it tests a Sharpe of 0.47 against zero, which is not the question. B2's figures reproduce Study 003's committed in-sample results exactly (test (i)); B3's weight is T1's, not Study 003's, as §5.3.5 (vi) fixes.

### Power statement (§9.6, completed under D3 before any return)

σ_d from Study 003's committed file was 0.692% a month (the registration assumed 1.0%); with 26 positive and 159 negative months the minimum detectable effect at a one-sided 5% level and 80% power was 0.364% a month, **4.37% a year**. A believable conditional edge was one to three percent a year. The window could not have supported the hypothesis at any believable size; the pre-registration said so and gave the in-sample check only the refuted, sign-consistent and inconclusive rows. The observed Δ is of the detectable size with the wrong sign, which is why the refuted row applies rather than inconclusive: the interval excludes the smallest believable positive edge.

### What did not work (§9.8)

- The primary regime variable (63-day correlation sign) selected the trend rule's exit months well (62% in bills) and the hypothesis still failed, because the selected months were not bad months for bonds. The failure is in the premise, not in the detection.
- The 252-day regime made it worse: 12 positive months, 10 of them one episode from May 2006 to February 2007, Δ −0.59% a month.
- The inflation regime is the only variant with the predicted signs, on a Δ of +0.10% a month with t 0.81 and an interval containing zero. It is reported as sign consistent and nothing more. It is also the variant furthest from the Campbell–Pflueger–Viceira mechanism as stated in §2.2, which is about the correlation, not the CPI threshold.
- No alternative window, dead band or threshold was tried (§15). N = 3.

### Limitations

- The in-sample regime comes from one vendor's adjusted closes and the episode and forward record from the broker's; D1 found the sign identical on every day of the 2016–2018 overlap, so this is not a limitation in practice.
- The regime was defined on daily total returns over a count-based window with no dead band, so a correlation of +0.01 is "positive"; this was fixed before any return and no alternative was run.
- Sixteen of the 26 positive-regime months fall in 2004–2006, one tightening cycle. The sub-period table shows the result is that cycle's.
- The 2019–2026 window, in which the regime was positive 41% of the time, is not a test (§8.2). The forward record is.

## Hypothesis-generating episode, 2019–2026 (no decision weight)

This is the window the question came from: Study 003 ran it once as its out-of-sample window, the author saw the rule sit in bills through 2022, and this study's hypothesis followed. Under §8.2 it is not a test of this hypothesis, it is run exactly once under this heading, no number from it enters any verdict row, and the hypothesis family has now spent the programme's 2019–2026 window. It was run on 2026-10-23 at 12:16 London (`reproduce.sh --episode`, logged first in `trials.md`, results committed as written in `94c93a3`), after the in-sample section above was committed (`24086b3`). Instruments and regime entirely from the broker's `adjustment='all'` bars (Study 001's and Study 003's fetches and this study's SPY fetch, SHA-256 verified); 93 holding periods, 2019-01-02 to 2026-10-01; B3's weight frozen at T1's in-sample IEF share, 0.914. B0, B1 and B2 reproduce Study 003's committed out-of-sample metrics exactly (every one of the fourteen numeric columns of `metrics_base.csv`, difference 0.0; observed); B3 differs because its weight is this study's, as §5.3.5 (vi) fixes.

| Trial | Regime | n_pos | n_neg | mean(d \| pos) | mean(d \| neg) | Δ per month | NW t | 95% bootstrap interval for Δ | Row |
|---|---|---|---|---|---|---|---|---|---|
| T1 | 63-day correlation > 0 | 38 | 55 | +0.072% | +0.304% | **−0.232%** | −0.72 | [−0.878%, +0.439%] | none (§8.2) |
| T2 | 252-day correlation > 0 (84 months from 2019-09, for want of broker history) | 38 | 46 | +0.016% | +0.405% | −0.389% | −1.05 | [−1.300%, +0.408%] | none |
| T3 | CPI 12-month change (m−2) > 3% | 44 | 49 | +0.429% | +0.012% | +0.417% | 1.35 | [−0.207%, +0.969%] | none |

Stress costs move Δ by at most 0.005% a month and no sign. T3's bootstrap dropped 1 of 10,000 resamples; T1 and T2 none.

**What the episode shows, and why the hypothesis came out of it wrong.** The regime was positive on 38 of 93 signal dates (41%, against 14% in-sample), in seven episodes, and B2 was in bills in 36 of those 38 months. IEF's excess return over cash averaged **−0.03% a month** over the 38 positive months (−0.08% over the 36 in which B2 was in bills): the exits in the positive regime were, over the episode, exits from a flat bond market, and d summed to +2.8 points over them. The trend rule's gain over holding IEF came somewhere else: in the **19 negative-regime months in which B2 was in bills**, d summed to **+16.9 points**, of which **+9.7 points fell in the five holding periods January to May 2022** (February and March 2022 alone +9.9). The 63-day correlation turned positive at the 2022-06-30 signal date, five months into the 2022 sell-off, after IEF had already fallen; the trend rule had been in bills since the February 2021 signal. In the regime's terms the 2022 exit was negative-regime work. Over the twelve holding periods of calendar 2022, holding IEF lost 13.7%, Study 003's rule made 1.4%, and the conditional rule T1, which held IEF whenever the regime was negative, lost 7.6%: it gave back more than half of what the exit had saved.

So the episode that generated the hypothesis does not, on its own numbers, show the pattern the hypothesis described: the exit helped, but the correlation-regime variable did not flag the months in which it helped, because the correlation lagged the sell-off. The in-sample check found the opposite sign for a different reason (positive-regime months in 2004–2006 were rising months for bonds). The two windows agree only that the conditional rule is worse than the unconditional one. The 2019–2026 figures carry no decision weight; the in-sample row stands and the forward record is the test.

Over the whole episode T1 held IEF in 19 months in which B2 held bills (the 2018-12, 2021-07 to 2022-05, 2023-03 to 2023-06 and three 2025 signal months) and made 14 switches to B2's 10. Cumulative over the 93 months: B2 +27.7%, T3 +26.5%, cash +22.5%, T1 +7.3%, B3 +5.2%, B1 +3.6%; T2 −4.4% over its 84. T1 against B2: −0.18% a month, NW t −1.69; against B3: +0.01% a month, t 0.11.

The CPI regime (T3) is the only one whose positive months contain the sell-off: it was positive for 26 consecutive months from the June 2021 to the July 2023 signal date, B2 was in bills throughout, and IEF's excess return in them averaged −0.76% a month (−19.7 points in total). That is where T3's +0.43% a month in the positive regime comes from, and it is why T3 ends the episode about a point behind B2. Its edge is of the predicted sign in both windows and inside an interval that contains zero in both; it is a descriptive trial and reported as sign consistent, nothing more. It is also the variant furthest from the stated mechanism (§2.2), and the pre-registration gives it no path to a verdict.

Strategies and benchmarks over the episode (base costs; `results/episode/metrics_base.csv`):

| | Ann. return | Ann. vol | Sharpe (excess over cash) | Max drawdown (monthly) | Switches | Share of months in IEF |
|---|---|---|---|---|---|---|
| T1 conditional rule | 0.91% | 4.96% | −0.325 | −17.8% | 14 | 61.3% |
| T2 (252-day; 84 months) | −0.64% | 5.36% | −0.602 | −22.2% | 12 | 60.7% |
| T3 (CPI regime) | 3.08% | 4.33% | 0.115 | −7.1% | 8 | 55.9% |
| B0 cash | 2.66% | 0.59% | — | −0.2% | 0 | 0% |
| B1 hold IEF | 0.45% | 7.39% | −0.259 | −22.2% | 0 | 100% |
| B2 Study 003's trend rule | 3.21% | 3.89% | 0.157 | −5.5% | 10 | 40.9% |
| B3 constant mix at T1's IEF share (w = 0.914) | 0.66% | 6.76% | −0.259 | −20.1% | 0 | 91.4% |

T1's bootstrap Sharpe interval is [−1.23, 0.63]. The positive episodes with their dates, B2's holding and IEF's excess return in them are in `results/episode/positive_episodes_T1.csv` (the longest: 13 months from the July 2023 to the July 2024 signal date, B2 in bills throughout, IEF +0.9 points over cash in total), `_T2.csv` and `_T3.csv`. At the last signal date in the files, 2026-09-30, all three regimes are positive (ρ₆₃ = 0.55) and the trend signal is in bills (−7.4% against cash).

**Charts** (§9.7) are not in this commit: they are drawn next from the committed files by a `charts.py` through the house style, titles computed from the numbers, and reviewed against the chart standard before they are linked here.

*Added 2026-10-23 13:2x: the §9.7 charts are in [`charts/`](charts/), drawn by [`charts/make_charts.py`](charts/make_charts.py) from the committed `monthly_base.csv` and `summary.json` of both windows through `qune_research/style.py` (SVG + 2x PNG, every title number in [`charts/manifest.json`](charts/manifest.json) with the input hashes). No result file was changed. The five pictures: the 63-day correlation at every signal date with the positive regime shaded and the trend rule's bill months marked ([rho63_regime_and_bill_months](charts/rho63_regime_and_bill_months.png)); the growth of one unit of T1, B1 and B2 in-sample ([insample_growth_T1_B1_B2](charts/insample_growth_T1_B1_B2.png)) and over the episode ([episode_growth_T1_B1_B2](charts/episode_growth_T1_B1_B2.png)); and d_t by regime with the two conditional means, in-sample ([insample_d_by_regime](charts/insample_d_by_regime.png)) and over the episode ([episode_d_by_regime](charts/episode_d_by_regime.png)). The Tester's check of the five against the chart standard (separate agent, Fable, isolated, 2026-10-23 13:3x) found **no must-fix**: every title number matches `charts/manifest.json`, `summary.json` and an independent recomputation from `monthly_base.csv`, and two charts passed outright; three should-fix items (the ρ₆₃ title carried two messages, the episode growth subtitle left an orphan line and its hold-IEF line vanished in the 2022 band, the episode d chart mixed sign conventions) were fixed the same day (13:4x) and the charts redrawn. One correction found while computing the titles: in the cumulative list four paragraphs above, B1's episode figure is **+3.5%** (1.03548 from the committed monthly returns, printed here as +3.6%); the other five figures in that list and the per-month figures recompute as printed.*

![Over 2019–2026 the conditional rule kept 15% of what the trend exit gained over holding IEF: +7.3% against +27.7% for the trend rule and +3.5% for holding IEF. Growth of 1 unit, monthly holding periods, 2019-01 to 2026-09, after costs; hypothesis-generating episode, no decision weight](charts/episode_growth_T1_B1_B2.png)

![In-sample, the trend exit returned −0.32% a month against holding IEF in the 26 positive-regime months and −0.03% in the other 159: a conditional edge of −0.30% a month (t −2.31), the wrong sign. d = B2 minus B1 by month, 2003-08 to 2018-12, positive-regime months in the accent colour](charts/insample_d_by_regime.png)

## Forward record (§11)

Publication date of this note: 2026-10-23 (§14 step 9; the commit that carries this sentence). The forward record therefore starts at the first month-end after it, **2026-10-30** (§14 step 11): a decision record with every input value, written after the close and never rewritten, a monthly shadow line of B1, B2 and T1 from the same closes, and interim figures only under "Not yet scored". Label: **refuted in-sample**. No paper order; SPY is never held. The record is scored once, at 24 positive-regime months or 60 holding periods, whichever comes first (§11.3), on the §11.4 table. The `--forward` mode of `reproduce.sh` is added before 2026-10-30 and refuses until then.

*Added 2026-10-23 14:3x (§14 step 11, built and tested; no forward month exists yet).* The forward record lives in [`paper-log/`](paper-log/README.md) and is produced by `src/forward.py` through `./reproduce.sh --forward`: `decide --signal-date t` writes the §11.1 decision record after the close of the last NYSE trading day of a month (`mom_t` through the frozen `trend_signal.excess_momentum`, ρ₆₃ and ρ₂₅₂ through `regime.trailing_correlation`, the CPI flag through `regime.cpi_regime`, the unconditional target B2, the conditional target T1 and the descriptive T2 and T3, every input value, the input hashes, the UTC time written); `shadow --signal-date t` appends the §11.2 line for the holding period that ended at `t`'s execution date (B1, B2, T1 from the same closes, `d_t`, the period's regime flags) and rewrites the interim figures under "Not yet scored"; scoring (§11.3–11.4) is wired to the same `edge.conditional_edge` and seed as the in-sample run and refuses until the stopping rule fires. Four gates, each tested: no record before **2026-10-30**, none before **21:15 UTC** on the signal date (after the New York close under EDT or EST, so a fetched daily bar can never be the partial day), none on a date that is not the last NYSE trading day of its month, none without the three bars for `t`; records and lines are never overwritten and a period that does not follow the last one is refused. Forward fetches go to `paper-log/raw/` (git-ignored) with their own `paper-log/manifest.json`, so the study's `data/raw/` hashes stay frozen. Check run once against the committed episode (observed, nothing written): the record for 2026-09-30 from the study's frozen files reproduces the episode summary's terminal values exactly (`mom` −0.0741677714, ρ₆₃ 0.5525133399, ρ₂₅₂ 0.3149659639, CPI change 0.0336482504 read for 2026-07; every target BIL). The first forward period starts at the 2026-10-30 record's execution date (2026-11-02); the holding period 2026-10-01 to 2026-11-02 belongs to the episode's last signal (2026-09-30) and is counted nowhere, which §16 records. Fourteen tests (43 in the suite). Nothing in this addition changes a result file.

## Independent review (§14 step 10)

*Added 2026-10-23 13:3x.* A separate Tester agent that did not write the code, the pre-registration or this note reviewed the study at commit 6826dd3 and published [`REVIEW.md`](REVIEW.md) with [`review_recompute.py`](review_recompute.py): **confirmed with findings, no must-fix.** The reviewer rebuilt the schedule, the trend signal, the three regime variables and every monthly return of B0–B3 and T1–T3 from the raw vendor files with its own engine (max abs diff 1e−16), recomputed Δ, the Newey–West t and the bootstrap interval with the pre-registered seed, applied the §9.5 rows itself (refuted in-sample for T1), confirmed that B0/B1/B2 reproduce Study 003's committed files and that the commit chain is in the pre-registered order; 1,337 of 1,349 comparison rows match, the 4 misses being README figures one unit off in their last printed digit. Qune reran `review_recompute.py` (same 1,349 rows, same 4 misses) and both test suites (29 and 107 passed) before accepting. Answers, by dated addition only:

- **Finding 1 (four last-digit figures).** Corrected readings from the committed files: stress costs move Δ by at most **0.0065%** a month (printed "0.007%" in the in-sample section); T1's negative-regime half-mean interval is **[−0.11%, +0.07%]** (printed "[−0.12%, +0.07%]"); over the 38 positive-regime months of the episode d summed to **+2.75 points** (printed "+2.8"; +2.79 is the sum over the 36 of them in which B2 held bills); B1's episode cumulative return is **+3.5%** (printed "+3.6%"; already corrected in the charts addition above). Cause in all four: rounding a figure that had itself been rounded. No criterion input is affected.
- **Finding 2 (two conventions in one sentence).** In the episode sentence "+9.7 points fell in the five holding periods January to May 2022 (February and March 2022 alone +9.9)", the first figure is the sum over the periods *executed* in January to May 2022 (signal months 2021-12 to 2022-04), the same convention as the calendar-2022 figures, and the second is the sum over the *signal* months 2022-02 and 2022-03 (executed in March and April 2022). By signal months January to May 2022 sum to +7.7; by execution months February and March sum to +4.8. The file's `month` column is the signal month.
- **Finding 3 (time labels).** Step 7 above said "12:xx": 12:21 London (6826dd3). `trials.md` said "10:5x" for the first code commit (10:25, 0281f89) and "12:2x" for the episode log row (12:15, 7f01c30). Corrected by dated lines in `trials.md`; the order of events is unchanged.
- **Notes 4–5 (episode `summary.json`).** Its `rows_9_5` strings ("inconclusive, forward record decides") stand beside `rows_9_5_note` ("no row applies"); the note governs, and no result file is edited after its run. The `subperiods_d_by_regime` block of the episode summary is empty by construction (the sub-periods are in-sample dates). Both are left as written.
- **Note 6 (first-draft corrections).** The five claims corrected against the files before the commits 24086b3 and 6826dd3 are now listed in `trials.md` as well as in those commit messages.
- **Notes 7–9.** T3's sign-consistent row rests on a positive-regime mean of +0.007% a month, as the in-sample section says; the run rows name the tree three ways (85381f2, 17ffd04, 840cdbd), all the same code; the first-period purchase cost convention is inherited from Study 003. Recorded, nothing to change.

## Reproduction

```
./reproduce.sh --check      # D0, D1, D3 -> results/checks/   (one run; this study's were run 2026-10-23)
./reproduce.sh --insample   # refuses: results/insample/ exists
./reproduce.sh --episode    # refuses: results/episode/ exists (run once, 2026-10-23)
./reproduce.sh --forward decide --signal-date 2026-10-30 --fetch   # section 11.1, after 21:15 UTC on the signal date; refuses before
./reproduce.sh --forward shadow --signal-date 2026-11-30 --fetch   # section 11.2, after the execution date's close; the first line follows the second record
./reproduce.sh --forward interim                                    # paper-log/interim.json under "Not yet scored"
```

Tests: `pytest` in this folder (43; test (i) and the overlap-reuse test need the raw files and skip in CI). Vendor data are not committed; `results/data_manifest.json` holds every file's SHA-256 and provenance.
