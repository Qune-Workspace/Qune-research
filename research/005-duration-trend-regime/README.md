# Study 005 — Trend exits from duration, conditional on the stock-bond correlation regime

**In-sample check: refuted in-sample** (pre-registered row, §9.5; run once on 2026-10-23). The hypothesis was that Study 003's 12-month trend exit from IEF adds value when the trailing 63-day SPY–IEF correlation is positive and costs when it is negative. **Over 2003-08 to 2018-12 the exit cost more in the positive regime, not less**: the trend-minus-hold return d_t averaged **−0.32% a month in the 26 positive-regime months** against **−0.03% in the 159 negative-regime months**, a conditional edge Δ of **−0.30% a month** (Newey–West t −2.31; stationary-bootstrap 95% interval [−0.52%, +0.03%] a month). The interval's upper bound, +0.03% a month, is below the smallest believable edge written down beforehand (0.083% a month, 1% a year), which is the refuted row. The minimum detectable effect at the actual regime counts, filled in before any return was seen, was 4.37% a year (§16), so this window could never have supported the hypothesis; it could refute it, and it did. The 252-day variant (T2, descriptive) is refuted on the same row (Δ −0.59% a month, t −3.11, interval [−2.11%, −0.11%]); the inflation-regime variant (T3, descriptive) is **sign consistent** (Δ +0.10% a month, t 0.81, interval [−0.12%, +0.30%]): both half-means have the predicted sign but the interval contains zero and the edge is a third of the detectable size, so the row says what it is, not a confirmation. Where T1 and T3 disagree, T1 is the registered primary and its row stands.

**This study has no "supported" row from history and places no paper order.** The 2019–2026 window generated the hypothesis and is run once under that label with no decision weight (below, when done). The forward record (§11) is kept from the first month-end after this note's publication, labelled "refuted in-sample", and scored once by the stopping rule.

Everything on this page is a backtest on historical ETF prices and bill yields. Nothing here is a track record, a forecast or investment advice. The question, hypothesis, regime variables, benchmarks, costs, criteria and order of operations were fixed in [`PREREGISTRATION.md`](PREREGISTRATION.md) before any fetch, correlation or return (`60f211e`); the trial log is [`trials.md`](trials.md).

What happened, in order (every step is a dated commit; times are London):

1. 2026-10-23, 08:2x: question note committed (`b9ad02e`), then the pre-registration (`60f211e`, 09:2x). No fetch, no regime share, no return.
2. 2026-10-23, 10:2x–11:2x: code and tests (`0281f89`, `218519b`): five Study 003 modules copied frozen so that the ported unconditional rule reproduces Study 003's committed monthly file to 1e−10 (test (i), passed on this machine); 29 tests. `APPROVED` written after `reproduce.sh` had refused without it.
3. 2026-10-23, 11:21–11:22: the two fetches of §5.3.3, each logged first (`80a2a2f` → `1fc0178` → `3f20db5`): Alpaca SPY 2018-09-04 to 2026-09-30 (2,029 bars) and FRED CPIAUCNS (1,365 months). Both succeeded on the first attempt; no branch taken.
4. 2026-10-23, 11:22–11:25: the data checks (`85381f2`), three invocations of one script: the first stopped in D3 on a missing CPI print (the BLS published no October 2025 CPI), the second on an idempotency fault in this study's file reuse, the third completed; D0 and D1 were identical in all three (diff observed). Each stop and fix is a dated §16 entry or commit written before the next invocation, and no regime share, correlation on a signal date or return had been seen when they were written.
5. 2026-10-23, 11:27: T1–T3 run rows logged (`840cdbd`), then `reproduce.sh --insample`, the single in-sample run, committed as written (`e60ab05`). Results below.

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

Not yet run (§14 step 8). It will be run once after this in-sample section is committed and reported here under this heading.

## Forward record (§11)

Starts at the first month-end after this note's publication date; labelled "refuted in-sample"; no order. Not yet started.

## Reproduction

```
./reproduce.sh --check      # D0, D1, D3 -> results/checks/   (one run; this study's were run 2026-10-23)
./reproduce.sh --insample   # refuses: results/insample/ exists
./reproduce.sh --episode    # once, after the in-sample results are committed
```

Tests: `pytest` in this folder (29; test (i) and the overlap-reuse test need the raw files and skip in CI). Vendor data are not committed; `results/data_manifest.json` holds every file's SHA-256 and provenance.
