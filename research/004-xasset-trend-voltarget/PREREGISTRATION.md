# Study 004 — Cross-asset time-series momentum with volatility targeting, long-only and long/flat, on twelve liquid ETFs

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-10-22 |
| Status | pre-registered; **no data fetched for this study, no data check run, no return of any rule or benchmark computed** |
| Version | 1.0 (any change after this commit requires a dated amendment appended to §16 before any further step is run) |
| Study type | cross-asset (programme stage 3, the flagship question of `RESEARCH_AGENDA.md` §5 item 1); one pre-registered hypothesis, long-only or flat, monthly, twelve instruments, **actual ETF history only** |
| Instruments | SPY, IWM, EFA, EEM, SHY, IEF, TLT, LQD, HYG, GLD, DBC, VNQ (§4). IEF is the only one of these with a paper-trading approval on record; the others are used for research only (§11) |
| Approval | The owner delegated all decisions on this research programme to the orchestrator on 2026-10-21 (recorded in the workspace decision log), including the use of liquid ETFs beyond the approved paper symbols for research. This document is approved by the orchestrator under that delegation on the date of its commit. **No paper order is part of this study** (§11). |
| Total trial count registered | **4** (§7). The three trials of Study 003 tested a different hypothesis on one instrument; they do not count here (§7). |
| Author | the orchestrator (Qune) |

Nothing in this document reports or implies the performance of any rule. **What the author has seen** of the data this study uses is listed in §2.4 and is more than in the earlier studies: it includes every published number of Study 003, which used two of this study's twelve instruments, in both the in-sample and the out-of-sample window. The consequences are drawn in §2.4 and §8.3 and are not hidden. No return of any of the other ten instruments has been computed by any study; no signal, weight or return of any rule or benchmark of this study has been computed on any data by anyone.

---

## 0. Why this question

The research agenda (`RESEARCH_AGENDA.md`, committed before this document) ranked cross-asset trend with volatility targeting first, for three reasons it gives in full: the published evidence is the strongest of any rule the programme can test with ETFs (Moskowitz, Ooi and Pedersen, 2012; Hurst, Ooi and Pedersen, 2017; Georgopoulou and Wang, 2017); the held-back window contains the clearest out-of-sample episode (2022); and the critics of that evidence (Kim, Tse and Wald, 2016; Huang, Li, Wang and Zhou, 2020; Goyal and Jegadeesh, 2018) have said exactly which benchmark a credible test needs, which lets this study pre-register it. Study 003 asked the single-asset, unscaled form of the question on IEF alone and found it not supported in-sample; the agenda names that as one instance of a general finding (single-instrument trend is a low-power test). This study asks the question in the form the literature actually makes its claim: many assets, each scaled to a volatility target, positions decided by each asset's own trend.

**Carried over unchanged from Studies 001 and 003:** the execution timing convention (signal at a month-end close, trade at the close of the next NYSE day), monthly rebalancing, no leverage, the cash-leg construction from DTB3 in-sample and actual BIL out-of-sample (§5.2), the twelve core metrics and the statistical tests (Newey–West, Ledoit–Wolf, stationary bootstrap, deflated Sharpe ratio), the verdict precedence (not supported > inconclusive > supported), the "What did not work" section, the out-of-sample window 2019-01-01 to 2026-09-30 run exactly once, and the rule that every trial is logged before it runs.

**What is different:** the universe (§4), the vendor plan (§5.1, one vendor for every return, with a per-symbol second-vendor overlap check), the signal and the sizing (§6), the cost model (§9.2, per ETF), the benchmarks (§9.1, built to separate the trend signal from the long bias and from volatility scaling), the criteria (§9.5, against the exposure-matched vol-scaled benchmark), the descriptive set (§9.6: attribution, crisis table, correlations, forecast-versus-realised volatility, breakeven cost curve), and the absence of a paper sleeve (§11).

## 1. Question

**Across twelve liquid ETFs spanning equities, Treasuries, credit and real assets, does holding each asset only when its own trailing 12-month return exceeds the return on bills, with every position scaled to the same volatility target and no leverage, improve risk-adjusted return over holding the same volatility-scaled portfolio throughout, after per-asset costs?** In plain words: a diversified, risk-balanced portfolio that steps out of each asset after a bad year and back in after a good one, against the same portfolio that never steps out.

## 2. Hypothesis

### 2.1 Statement

- **H1:** the sign of each asset's own 12-month excess return predicts the sign of its next-month excess return, so that the long/flat trend portfolio (T1, §6) earns a higher Sharpe ratio after costs than the always-long volatility-scaled portfolio with the same average gross exposure (B4, §9.1), by the margin and at the significance fixed in §9.5.
- **H0:** monthly excess returns are not predictable from each asset's own 12-month history; T1's return equals that of the exposure-matched vol-scaled portfolio minus trading costs, and any Sharpe difference is within noise.

### 2.2 Economic grounding

1. **Under-reaction and slow diffusion** (Moskowitz, Ooi and Pedersen, 2012; the behavioural account of trend): prices adjust to information over months, not days, across asset classes, so a 12-month return carries information about the next month's sign.
2. **Diversification of a weak signal.** The single-asset test in Study 003 had three or four independent cycles in fifteen years. Twelve assets across four classes, with pairwise correlations well below one, multiply the number of independent trend episodes and give a monthly test the power one instrument cannot have (Hurst, Ooi and Pedersen, 2017, report the effect in every asset class and every decade of their century).
3. **Volatility scaling is part of the published claim.** The literature's Sharpe ratios come from positions scaled to equal ex-ante risk (Kim, Tse and Wald, 2016, show how much); testing the signal without the scaling, as Study 003 did, is a different and weaker claim. This study scales positions as the literature does, and then charges the scaling to the benchmark too, so that only the signal is on trial.
4. **Crisis behaviour.** The documented value of trend is concentrated in prolonged drawdowns (Hamill, Rattray and van Hemert, 2016): 2008 in-sample, 2022 out-of-sample. A long/flat version keeps the defensive half of that claim (it steps aside) and gives up the offensive half (it never shorts).

### 2.3 Why the edge might not be there, or not survive

- **Long bias.** Over 2004–2018 most of these assets drifted up. Huang et al. (2020) show that much of what looks like time-series momentum is "assets with a positive drift were mostly long". A long-only rule on an upward-drifting universe can look good against cash and bad against the always-long portfolio; the verdict therefore rests on B3 and B4 (always long, same scaling), not on cash or an equal-weight benchmark.
- **Volatility scaling, not trend, may do the work.** Vol-scaled long-only portfolios of risk assets have their own documented Sharpe improvement (Moreira and Muir, 2017; Harvey et al., 2018). B3 removes that from the rule's credit. If T1 beats B1 (equal weight) but not B3, the honest reading is "scaling helps, trend does not", and the pre-registered criteria return that reading.
- **Long/flat throws away the short side.** The published strategy earns a large share of its crisis return from short positions; a long/flat ETF version cannot, and in a V-shaped crash (2020) it is flat at the bottom and late back in. Published Sharpe ratios do not transfer and are not the bar.
- **Whipsaw and cost.** Twelve assets switching independently can generate more turnover than a single switch; the per-ETF cost model (§9.2) and the breakeven cost curve (§9.6) are there so that a result cannot be reported without its cost sensitivity.
- **Decay and crowding.** Trend following is an industry and the evidence has been public for a decade; the agenda records the 2010s drawdown of the trend indices (`RESEARCH_AGENDA.md` §2–§3). The out-of-sample window is post-publication.
- **The designer is not blind to two of the twelve assets** (§2.4). This is the specific weakness of this study and is treated in §2.4, §8.3 and §9.6.

### 2.4 Designer's prior knowledge (disclosed in full)

Public knowledge: the broad course of US and global markets 2003–2026, including the 2008 crisis, the 2009–2018 recovery in equities and credit, the 2013 taper episode, the 2015–2016 commodity and emerging-market drawdowns, the 2018 fourth-quarter equity drawdown, the 2020 crash and recovery, and the 2022 year in which equities and bonds fell together. The author therefore expects, before any computation, that T1 will lag B3 and B4 in the long 2009–2018 risk-asset bull market (it is flat after every scare and late back in), that 2008 is the in-sample episode in which it should gain most, and that 2022 is the out-of-sample episode the rule exists for while 2020 is the one it should handle worst. None of these expectations sets a parameter: every parameter of §6 is a round number fixed in this document from the literature's conventions and the no-leverage constraint.

**Seen numbers (this is more than the earlier studies disclosed, and it matters):**

- Everything published by **Study 003** on **IEF and BIL**: monthly returns and the 12-month trend signal of IEF over 2003–2018 and 2019–2026, in-sample and out-of-sample; in particular that a 12-month long/flat rule on IEF held bills from February 2021 to July 2024 and side-stepped most of the 2022 drawdown, with a Sharpe of 0.16 against −0.26 for buy-and-hold out-of-sample. **For one of this study's twelve assets, the out-of-sample path of the primary signal is therefore known to the designer before this document was written.**
- Studies 001 and 002: IEF and BIL daily returns 2016–2018 and the validation statistics listed in Study 003 §2.4.
- The desk's own trading backtests used daily history of **SPY, IWM, QQQ and DIA** from the same vendor for unrelated hourly rules; the author has seen summary statistics of those backtests (returns and drawdowns of those rules), not any trend signal, monthly return or vol estimate of SPY or IWM.
- **Nothing** of EFA, EEM, SHY, TLT, LQD, HYG, GLD, DBC or VNQ: no return, no price series, no statistic, from any source, in any window.

Consequences, decided now:

1. IEF stays in the universe, because a rates sleeve without the intermediate Treasury would be a strange portfolio and the point of the study is the twelve-asset portfolio, not any one asset. The cost of that choice is that the out-of-sample test is not blind for one twelfth of the universe.
2. A pre-registered descriptive run **without IEF** (eleven assets, same rule, same benchmarks, same windows) is reported next to every headline table (§9.6). It has no decision weight, because choosing between the two after seeing them would be selection; it is there so that a reader can see whether the verdict depends on the one asset the designer could not be blind to.
3. No parameter of §6 is derived from anything seen. The lookback (12 months) and the hold (1 month) are the canonical ones; the volatility window (63 trading days), the per-asset volatility scale (10% p.a.) and the weight cap (25%) are round numbers fixed from conventions and the no-leverage constraint before any computation, and the lookbacks of T2 and T3 (6 and 3 months) are the standard shorter horizons in the same literature.

### 2.5 What Studies 001–003 taught, applied here

- **One vendor for every return in a window; no splice.** Here one vendor supplies every instrument in both windows (§5.1) and the second vendor is used only to check it.
- **A gate must test what the series is used for.** The overlap gate is on the level (annualised mean difference), not on daily correlation, for the reason Study 003 §5.3.2 gave and its data step confirmed (quantisation and distribution-booking differences dominate daily statistics without touching a monthly rule).
- **Pre-commit every branch.** §5.3 states, before any fetch, what happens when a symbol fails its overlap check, when the second vendor is unreachable, and when too many symbols fail.
- **Statistics code must not fail on a degenerate sample.** Study 003 found that the bootstrap intervals are undefined when a trial's excess return is exactly zero in most months (it held the cash benchmark). The shared library built for this study (§13) defines the bootstrap Sharpe interval on resamples with non-zero variance and reports the number of degenerate resamples dropped; the unit tests cover the degenerate case (§5.3.4 vii).
- **Do not inherit a criterion without saying what it means here.** Study 003 inherited its criteria by reference; this document writes them out (§9.5) because the benchmarks have changed.

## 3. Literature

All DOIs were checked against the Crossref registry on 2026-10-22 for `RESEARCH_AGENDA.md` (`tools/citations_check.txt`); the agenda's keys are given in brackets.

- [MOP12] Moskowitz, Ooi and Pedersen (2012). "Time Series Momentum." *Journal of Financial Economics* 104(2), 228–250. doi:10.1016/j.jfineco.2011.11.003. The hypothesis, the 12-month/1-month convention and volatility scaling to a constant target.
- [HOP17] Hurst, Ooi and Pedersen (2017). "A Century of Evidence on Trend-Following Investing." *Journal of Portfolio Management* 44(1), 15–29. doi:10.3905/jpm.2017.44.1.015. Multi-horizon (1, 3, 12 months) evidence across asset classes; the source of T2–T4.
- [GW17] Georgopoulou and Wang (2017). "The Trend Is Your Friend." *Review of Finance* 21(4), 1557–1592. doi:10.1093/rof/rfw048. Independent evidence across equities and commodities.
- [KTW16] Kim, Tse and Wald (2016). "Time Series Momentum and Volatility Scaling." *Journal of Financial Markets* 30, 103–124. doi:10.1016/j.finmar.2016.05.003. Why the vol-scaled long-only benchmark (B3) exists.
- [HLWZ20] Huang, Li, Wang and Zhou (2020). "Time Series Momentum: Is It There?" *Journal of Financial Economics* 135(3), 774–794. doi:10.1016/j.jfineco.2019.08.004. Why the exposure-matched benchmark (B4) exists.
- [GJ18] Goyal and Jegadeesh (2018). "Cross-Sectional and Time-Series Tests of Return Predictability." *Review of Financial Studies* 31(5), 1784–1824. doi:10.1093/rfs/hhx131. Time-series momentum's net long position as the source of much of its return.
- [MM17] Moreira and Muir (2017). "Volatility-Managed Portfolios." *Journal of Finance* 72(4), 1611–1644. doi:10.1111/jofi.12513; [HHKRSV18] Harvey et al. (2018). "The Impact of Volatility Targeting." *Journal of Portfolio Management* 45(1), 14–33. doi:10.3905/jpm.2018.45.1.014; [COWY20] Cederburg et al. (2020). *Journal of Financial Economics* 138(1), 95–117. doi:10.1016/j.jfineco.2020.04.015. What volatility scaling does on its own, and the dispute about it; the reason B3 is reported against B1.
- [BK12] Baltas and Kosowski (2012). "Improving Time-Series Momentum Strategies." SSRN. doi:10.2139/ssrn.2140091. Volatility estimators and turnover; this study uses the plain close-to-close estimator and reports turnover, as [BK12] recommend reporting.
- [HRvH16] Hamill, Rattray and van Hemert (2016). "Trend Following: Equity and Bond Crisis Alpha." SSRN. doi:10.2139/ssrn.2831926. The crisis table of §9.6.
- [BLdP14] Bailey and López de Prado (2014). *Journal of Portfolio Management* 40(5), 94–107. doi:10.3905/jpm.2014.40.5.094. The deflated Sharpe ratio. [LW08] Ledoit and Wolf (2008). doi:10.1016/j.jempfin.2008.03.002. [PR94] Politis and Romano (1994). doi:10.1080/01621459.1994.10476870. The tests of §9.3.

## 4. Instruments

Twelve US-listed ETFs, chosen before any data were fetched on three criteria written here: (i) liquid, large and old enough to give at least ten in-sample years (inception before 2008-04, so that the asset's first signal date falls inside the in-sample window with at least ten years to follow); (ii) four asset classes with at least two instruments each, so that no class is one asset; (iii) no currency ETFs (the agenda's reason: poorly proxied, crowded, crash-prone; `RESEARCH_AGENDA.md` §5). Inception dates are public fund facts as known to the author; each is **confirmed or corrected from the first bar in the vendor file at §5.3.1**, and nothing in the design depends on the exact date beyond the asset's entry month (§8.1).

| Class | Symbol | Fund | Inception (to confirm) | Expected first signal date (§8.1) |
|---|---|---|---|---|
| Equities | SPY | SPDR S&P 500 | 1993-01 | 2003-12-31 (first in-sample signal) |
| Equities | IWM | iShares Russell 2000 | 2000-05 | 2003-12-31 |
| Equities | EFA | iShares MSCI EAFE | 2001-08 | 2003-12-31 |
| Equities | EEM | iShares MSCI Emerging Markets | 2003-04 | 2004-04-30 |
| Treasuries | SHY | iShares 1–3 Year Treasury | 2002-07 | 2003-12-31 |
| Treasuries | IEF | iShares 7–10 Year Treasury | 2002-07 | 2003-12-31 |
| Treasuries | TLT | iShares 20+ Year Treasury | 2002-07 | 2003-12-31 |
| Credit | LQD | iShares iBoxx Investment Grade Corporate | 2002-07 | 2003-12-31 |
| Credit | HYG | iShares iBoxx High Yield Corporate | 2007-04 | 2008-04-30 |
| Real assets | GLD | SPDR Gold Shares | 2004-11 | 2005-11-30 |
| Real assets | DBC | Invesco DB Commodity Index Tracking | 2006-02 | 2007-02-28 |
| Real assets | VNQ | Vanguard Real Estate | 2004-09 | 2005-09-30 |

Cash: BIL (actual, out-of-sample and in the signal from 2019) and the DTB3 accrual of §5.2 (in-sample). Expense ratios are embedded in the ETF returns and are not charged again.

## 5. Data

### 5.1 Sources

| Series | Source | Field | Used for | Window |
|---|---|---|---|---|
| Daily split- and distribution-adjusted close, all twelve ETFs and BIL | Tiingo end-of-day (the desk's existing credential, read from the environment, never logged; no credential created). IEF and BIL files already on disk from Studies 002 and 003 are reused after a SHA-256 check against their manifests; the other eleven are fetched under §5.3.1 | `adjClose` | **every instrument return and every signal, in both windows** (one vendor, no splice) | 2002-07 to 2026-09 |
| Daily bars, `adjustment='all'`, all twelve ETFs | Alpaca Market Data (the desk's existing broker-data access; IEF and BIL bars reused from Study 001 after a SHA-256 check) | adjusted close | **the per-symbol second-vendor overlap check only** (§5.3.2); never an input to a return of any rule | 2016-01-04 to 2018-12-31 |
| DTB3 | FRED (the file on disk from Study 003, SHA-256 checked; re-fetched if reachable) | discount yield | the in-sample cash leg (§5.2) | in-sample |

Vendor data are licensed and are never committed; `data/raw/` is git-ignored and every file's provenance (vendor, URL, timestamp, rows, first and last dates, SHA-256) goes into `results/data_manifest.json`. Daily total return of an ETF on trading day t: `r_t = adjclose_t / adjclose_{t−1} − 1`. The vendor re-bases adjusted closes on each fetch, so file hashes change between fetches while every return ratio is unchanged; the manifest records the hash of the file actually used.

Why one vendor for both windows, unlike Study 003 (which used the broker's bars out-of-sample): this study places no paper order (§11), so there is no execution path to match, and a single series per instrument removes the splice question entirely. The broker's bars are used only to check the vendor on the three years both cover.

### 5.2 The cash leg

Unchanged from Study 001 §5.2 and Study 003 §5.2: the 3-month bill discount yield from FRED converted to a bond-equivalent yield, accrued over calendar days, less BIL's expense ratio pro rata, compounded into a daily index `TRI_cash`. It is the instrument held when the portfolio is not fully invested (in-sample), and the cash return in every signal (in-sample). Out-of-sample both roles are filled by actual BIL. Its level check against actual BIL over 2007-06 to 2018-12 was run once under Study 003 (§5.3.3 there: +0.0366% p.a. against a ±0.30% gate, inside the ex-ante band) with the same code; **it is not re-run here**, and this study inherits that result and its limitation (the series is unchecked before 2007-06, where bill yields were above zero and the accrual's model error is the same in kind as in 2007–2008, the years the check covered).

### 5.3 Data checks (one run; no rule applied; order and branches fixed now)

#### 5.3.1 D0: fetch and coverage

Fetch daily adjusted closes for the eleven ETFs not yet on disk from the vendor from 2002-07-01 (or the fund's first bar) to 2026-09-30, one GET per symbol; record provenance including each file's first bar, which **sets the asset's entry date** (§8.1) and confirms or corrects the inception column of §4. Coverage: from each file's first bar, a bar on every NYSE trading day to 2026-09-30 with at most three consecutive missing days anywhere. A file that fails coverage is re-fetched once; if it still fails, **the symbol is excluded** (branch X below) and the failure is recorded. A vendor fetch that fails for a symbol after two attempts: branch X. Commit the manifest before §5.3.2.

#### 5.3.2 D1: per-symbol second-vendor overlap check (pre-committed branches)

For each of the twelve symbols, on common return days 2016-01-04 to 2018-12-31: annualised mean daily return difference, vendor − broker (`adjustment='all'`). **Acceptance: within ±0.20% p.a.** Correlation, tracking error and the largest daily gap are reported but are not thresholds (Study 003 §5.3.2's reason). The gate is wider than Study 003's ±0.05% because nine of the twelve funds pay dividends that two vendors may book on different days or with different reinvestment conventions, and a monthly sign rule inherits only the level; the ex-ante expectation is that every symbol passes with a difference under 0.10% p.a. in absolute value, and the note must say which symbols did not.

- **Pass:** the symbol stays. **Fail:** **branch X**, the symbol is excluded from the universe before any return of any rule is computed, its statistics are published, and §16 records the exclusion with N unchanged (an exclusion on a data check is not a trial).
- **Broker bars unavailable for a symbol** (fetch fails after two attempts, or the desk's broker-data access is not usable from the run environment): the check is **skipped for that symbol**, which stays in the universe labelled "single-vendor, unchecked" in every table; this is a disclosed weakening, not a choice.
- **Halt rule:** if more than three symbols are excluded under branch X, or any asset class is left with fewer than two instruments, **the study halts permanently** before any rule is tested, and every statistic is published.

#### 5.3.3 D2: cash leg

Inherited from Study 003 (§5.2 above); no run.

#### 5.3.4 Engine checks (unit tests in the shared library and the study, run before any data check)

(i) With every signal forced to 1 at zero cost, T1 equals B3 to machine precision; forced to 0, T1 equals B0. (ii) Shifting every price and yield series forward by one trading day moves every signal and execution date by one day and changes no weight. (iii) Perturbing any price dated after a signal date leaves that date's signals, volatility estimates and weights unchanged (no look-ahead). (iv) On a constructed series the 12-month, 6-month and 3-month excess returns equal the product of the calendar-month returns ending at the signal month, less the same for cash. (v) On a constructed series with known daily volatilities the weights equal `min(σ_a/(N·σ_i), w_cap)` and sum to at most 1, and the proportional scale-down fires exactly when the sum would exceed 1. (vi) The cost charged in a month equals Σ_i |Δw_i| × c_i on the pre-trade portfolio value, with no cost when no weight changes. (vii) The bootstrap Sharpe interval is finite on a return series that is zero in 60% of months, and the number of dropped resamples is reported. (viii) k (the exposure ratio for B4) equals the in-sample mean of T1's gross exposure divided by B3's and is a function of signals and volatilities only.

#### 5.3.5 Halt rule

The halt grounds are those of §5.3.1–§5.3.2 (coverage or vendor failure leaving fewer than nine symbols, or any class with fewer than two). There is no other halt ground: the cash leg's check is inherited. A halt is "inconclusive" and every statistic is published.

### 5.4 Data availability (dates only, from the files on disk on 2026-10-22)

IEF (vendor): 6,099 rows, 2002-07-26 to 2026-10-21. BIL (vendor): 4,881 rows, 2007-05-30 to 2026-10-21. IEF and BIL (broker): 2,716 bars each, 2016-01-04 to 2026-10-21. DTB3: valid to 2026-10-20. The other ten ETFs: not yet fetched from either source; first bars recorded at §5.3.1.

## 6. Exact rule specification

### 6.1 Signal (per asset)

Let `TRI_i` be asset i's adjusted-close total-return index and `TRI_cash` the cash index. On signal date t (§6.3), with t_L the last NYSE trading day of the calendar month L months before t's month:

```
mom_i,t(L) = TRI_i(t) / TRI_i(t_L) − TRI_cash(t) / TRI_cash(t_L)      (L-month excess return, decimal)
s_i,t      = 1 if mom_i,t(12) > 0 else 0                                (T1: long or flat; threshold exactly zero)
```

### 6.2 Volatility estimate and sizing

```
σ_i,t  = annualised standard deviation of asset i's daily simple returns over the 63 trading days ending at t (√252)
N_t    = number of assets in the universe at t (§8.1; every asset that has entered, long or flat)
w_i,t  = s_i,t × min( σ_a / (N_t × σ_i,t), w_cap ),   σ_a = 10% p.a.,  w_cap = 25%
if Σ_i w_i,t > 1: w_i,t ← w_i,t / Σ_i w_i,t   (proportional scale-down; no leverage)
cash weight = 1 − Σ_i w_i,t
```

Reading: each asset that is "on" is sized so that, on its own, it contributes σ_a/N_t of annualised volatility to the portfolio (10% split equally across the universe), capped at a quarter of the portfolio so that the lowest-volatility asset (SHY) cannot become the whole book; the portfolio never borrows. Because the assets are imperfectly correlated the portfolio's realised volatility will be well below 10%; the ex-ante diagonal forecast and the realised figure are both reported (§9.6) and the gap is a result, not a tuning target. The estimator is the plain close-to-close standard deviation because the vendor supplies closes; [BK12]'s range-based estimators are named in §15 as not used.

### 6.3 Timing and look-ahead control

- **Signal date t** = the last NYSE trading day of calendar month m. Signals, volatilities and weights use closes dated ≤ t only.
- **Execution date e** = the first NYSE trading day strictly after t; every trade fills at the official close of e; the weights set on e are held, with the assets' returns drifting them, to the close of the next execution date, where the portfolio is rebalanced to the new weights. Same one-day lag as Studies 001–003.
- No observation dated after t is used in forming any weight for e (unit tests §5.3.4 ii–iii).

### 6.4 Rebalancing, costs, missing data

Monthly at e only: every asset is traded to its new weight; the cost of the month is Σ_i |Δw_i| × c_i (§9.2) on the pre-trade portfolio value, where Δw_i is the change from the drifted weight to the target. No band, no tolerance (a tolerance is a parameter, and this study has none to tune; turnover is reported so that a reader can judge it). No intra-month stops. A missing bar on an execution date moves every trade of that date to the next bar and logs the slip; more than three consecutive missing bars in any asset halts the study (§5.3.1 makes this unlikely). The cash accrual needs no special case.

### 6.5 Pseudo-code (monthly loop)

```
weights = all cash
for each calendar month m from 2003-12 (in-sample) or 2018-12 (out-of-sample):
    t = last NYSE trading day of m;  universe_t = assets with a bar at t_12 (and 63 days of returns to t)
    for i in universe_t:
        mom_i = TRI_i[t]/TRI_i[t_12] − TRI_cash[t]/TRI_cash[t_12]
        s_i   = 1 if mom_i > 0 else 0
        σ_i   = std(daily returns of i over the 63 trading days to t) × √252
        w_i   = s_i × min(0.10 / (|universe_t| × σ_i), 0.25)
    if Σ w_i > 1: scale all w_i by 1/Σ w_i
    e = first NYSE trading day > t
    charge Σ_i |w_i − drifted weight_i| × c_i;  set weights at close[e]
    accrue the portfolio's return (assets at their weights, the rest in cash) from close[e] to close[e_next]
```

## 7. Registered trials (N = 4)

| ID | Name | Difference from T1 | Purpose |
|---|---|---|---|
| T1 | Primary: 12-month long/flat, vol-scaled | — | The hypothesis [MOP12] |
| T2 | 6-month lookback | `s_i` from `mom_i,t(6)` | The intermediate horizon of [HOP17] |
| T3 | 3-month lookback | `s_i` from `mom_i,t(3)` | The short horizon of [HOP17] |
| T4 | Blend | `s_i = (s_i(12) + s_i(6) + s_i(3)) / 3`, so each asset is on at 0, ⅓, ⅔ or full size | The practitioners' ensemble [HOP17], which trades the horizon decision for turnover |

All four run on the same holding periods, with the same σ, caps, costs and benchmarks. Logged in `trials.md` before any is run. The deflated Sharpe ratio is reported at N = 4 (decision) and N = 10 (sensitivity, for the implicit search over well-known trend definitions). The three trials of Study 003 tested one instrument with a different benchmark set and their returns were seen; they are not trials of this hypothesis, but they are why §2.4 discloses what was seen. No other variant will be run: no other lookback, threshold, volatility window, target, cap, estimator, universe, rebalancing band or short position. Any addition is appended to `trials.md` with a date before it runs and N increases.

## 8. Sample split

### 8.1 In-sample

**2004-01 to 2018-12.** First signal date 2003-12-31 (the first month-end at which the 2002-07 funds have a 12-month lookback and 63 days of returns with a margin); first execution date the first NYSE trading day of January 2004; last holding period ends at the first execution date of January 2019: **180 monthly holding periods**. **Staggered entry:** an asset enters the universe at the first signal date t at which the vendor file has a bar at t_12 and 63 trading days of returns to t; before that it is absent (not flat: it does not count in N_t). Expected entry dates are in §4; the actual ones come from the first bars recorded at §5.3.1 and are published. An asset never leaves once it has entered (except under branch X, before any return).

### 8.2 Out-of-sample (held back; touched once by this study)

**2019-01-01 to 2026-09-30**, the window shared by Studies 001–003. First signal date the last NYSE trading day of December 2018; last holding period ends at the first execution date of October 2026: about 93 holding periods. All twelve assets are in the universe throughout. Instruments and signals from the vendor series; cash from actual BIL. Run exactly once by `reproduce.sh --oos` after the in-sample results, the data checks and the trial log are committed; output to `results/oos/`, never re-run. A bug fix in shared code after the run is an amendment that keeps both outputs.

### 8.3 Why this boundary, and what the author knows about the window

The boundary is inherited unchanged so that the programme has one test period. The author states plainly: the window contains the 2020 crash and V-shaped recovery (the episode a long/flat monthly rule should handle worst), the 2022 year in which equities, Treasuries and credit fell together (the episode it exists for), the 2023–2024 recovery in equities and gold, and **for IEF and BIL the author has already seen the window's result under Study 003** (§2.4). The study's claim about the window is therefore weaker than Study 003's was, and the note must say so in its first paragraph. Three things limit the damage: no parameter was set after that viewing (§2.4 item 3); the eleven-asset run without IEF is pre-registered (§9.6); and ten of the twelve assets are blind. The window is still informative because 93 months of a twelve-asset portfolio contain many more independent trend episodes than 93 months of one bond ETF; it still cannot establish a Sharpe difference of 0.2 at conventional significance, so O1–O2 remain sign conditions.

### 8.4 Forward period

A forward shadow record from the publication date of the note, never backdated (§11).

## 9. Benchmarks, metrics and decision criteria (fixed now)

### 9.1 Benchmarks

| ID | Benchmark | Definition | What it separates |
|---|---|---|---|
| B0 | Cash | 100% cash (accrual in-sample; actual BIL out-of-sample) | — |
| B1 | Equal weight, long-only | 1/N_t in each asset of the universe at t, rebalanced monthly, same costs | What the universe did; the allocator's naive benchmark |
| B2 | 60/40 | 60% SPY / 40% IEF rebalanced monthly, same costs | The allocator's conventional benchmark |
| B3 | Vol-scaled long-only | `s_i ≡ 1` with exactly §6.2's σ, σ_a, w_cap, scale-down and cash remainder, same costs | Removes volatility scaling from the rule's credit [KTW16, MM17] |
| B4 | Exposure-matched vol-scaled long-only | B3's weights multiplied by k, where **k = the in-sample mean over months of (Σ_i w^{T1}_i,t) / (Σ_i w^{B3}_i,t)**, computed once from in-sample signals and volatilities only, frozen, and applied unchanged out-of-sample; the remainder in cash; same costs | Removes the long bias too [HLWZ20, GJ18]: B4 holds the same average gross exposure as T1 with no timing, so T1 − B4 is the timing contribution |

### 9.2 Costs (per ETF, one side, bp of traded notional)

The broker charges no commission on US ETFs; the cost of a trade is the half-spread plus slippage against the close. Allowances fixed now from typical quoted spreads as the author knows them, not measured on the data:

| Symbol | Base | Symbol | Base | Symbol | Base |
|---|---|---|---|---|---|
| SPY | 2.0 | SHY | 2.0 | GLD | 2.0 |
| IWM | 2.0 | IEF | 2.0 | DBC | 3.5 |
| EFA | 2.5 | TLT | 2.0 | VNQ | 2.5 |
| EEM | 3.0 | LQD | 2.5 | HYG | 3.0 |

Each base figure is half-spread allowance plus 1.5 bp slippage (SPY, IWM, SHY, IEF, TLT, GLD: 0.5 bp half-spread; EFA, LQD, VNQ: 1.0; EEM, HYG: 1.5; DBC: 2.0). **Stress = 2× base.** Costs are charged on |Δw| at every rebalance for every strategy and benchmark (B0 pays nothing after the initial purchase; B1–B4 pay on their rebalancing turnover). Today's costs are applied across the whole sample, which overstates implementability in 2004–2008 and answers the question actually asked (would it be worth trading now). The breakeven cost curve (§9.6) reports the multiple of base cost at which T1's advantage over B4 is zero.

### 9.3 Metrics (T1–T4, B0–B4; in-sample and out-of-sample; base and stress)

From monthly holding-period returns, excess over B0, as Study 001 §9.3 items 1–4, 6–11 unchanged (annualised return, volatility, Sharpe, maximum drawdown from monthly and from daily data, hit rates, Newey–West timing difference with 6 Bartlett lags against B3 and B4, the Ledoit–Wolf Sharpe-difference test against B3 and B4 with 12-month blocks and 10,000 resamples, the stationary-bootstrap Sharpe interval, PSR and DSR, skewness and kurtosis). Item 5 (turnover) becomes: annualised one-way turnover Σ_t Σ_i |Δw_i,t|, average gross exposure Σ_i w_i, the fraction of asset-months "on", and the number of on/off switches per asset per year. Item 12 is §9.6.

### 9.4 Deflated Sharpe ratio

As Study 001 §9.4 with **N = 4** registered trials (decision) and N = 10 (sensitivity), the variance of the monthly Sharpe ratios across T1–T4, the floor V = (0.05/√12)² if degenerate, and the non-normality adjustment from each trial's monthly excess returns.

### 9.5 Decision criteria (ex ante)

In-sample, at base costs, for T1:

- **C1:** Sharpe(T1) ≥ Sharpe(B4) + 0.10 **and** Sharpe(T1) ≥ Sharpe(B3) + 0.10 (annualised units).
- **C2:** Newey–West t-statistic (6 lags) of mean(T1 − B4) ≥ 2.0.
- **C3:** DSR(T1) with N = 4 ≥ 0.95.
- **C4:** the sign of mean(T1 − B4) is unchanged under stress costs.

Out-of-sample, base costs, run once:

- **O1:** mean(T1 − B4) > 0.
- **O2:** Sharpe(T1) > Sharpe(B3).

| Verdict | Condition |
|---|---|
| **Supported** | C1–C4 all hold, and O1 and O2 both hold. |
| **Not supported** | Any of C1–C4 fails; or O1 fails with Newey–West t ≤ −1.0; or the out-of-sample maximum drawdown (monthly) of T1 exceeds that of B4. |
| **Inconclusive** | C1–C4 hold but O1 or O2 fails with the out-of-sample t-statistic of (T1 − B4) in (−1.0, +1.0); or the study halts under §5.3.5. |

Precedence, as fixed for the programme in Study 001 §16: **not supported > inconclusive > supported**. T2–T4 do not affect the verdict and are reported in full; if T1 is "supported" but any of T2–T4 would be "not supported" on the same criteria, the note says so prominently and the verdict is downgraded to "inconclusive". The eleven-asset run of §9.6 does not affect the verdict either way; if it would reach a different verdict than the twelve-asset run, the note says so in its first paragraph.

Why B4 and not B1 is the bar: beating equal weight could come from scaling alone (B3 answers that), and beating B3 could come from holding less of a falling market on average (B4 answers that). C1 asks for both, so that "scaling helps, trend does not" and "trend only helps by being out more" each return "not supported".

### 9.6 Pre-registered descriptive sub-analyses (no decision weight, no selection)

- **Without IEF:** every headline table for T1 and B0–B4 on the eleven other assets (§2.4). Reported next to the twelve-asset table everywhere the latter appears.
- **Per-asset attribution:** each asset's contribution to T1's annualised return and to its variance (in-sample and out-of-sample), and the same for B3; the asset-months on; each asset's own long/flat Sharpe against its own always-on vol-scaled position.
- **Crisis table** [HRvH16]: cumulative return of T1, B1, B2, B3, B4, SPY and IEF over 2008-09-01 to 2009-02-28 (in-sample), 2020-02-19 to 2020-03-23 and 2020-02-19 to 2020-08-31 (out-of-sample), and 2022-01-01 to 2022-10-31 (out-of-sample); the windows are fixed here by public dates and are not chosen on the results.
- **Correlations:** monthly correlation of T1 and B3 excess returns with SPY and IEF, by window.
- **Volatility forecast versus realised:** the ex-ante diagonal forecast of T1's and B3's annualised volatility (√(Σ_i w_i² σ_i²)) against the realised 12-month rolling figure; mean ratio and the share of months in which realised exceeded forecast by more than half. A finding that the diagonal forecast understates realised volatility by a large factor is expected (correlations are ignored) and is the first input to the risk model the programme plans next.
- **Breakeven cost curve:** Sharpe(T1) − Sharpe(B4) at 0×, 0.5×, 1×, 2×, 3× and 5× base costs, in-sample; the multiple at which it crosses zero, by interpolation.
- **Sub-periods** by holding-period start: 2004-01 to 2008-12, 2009-01 to 2015-12, 2016-01 to 2018-12. Metrics 1–6 for each.
- **Power statement:** the number of on/off switches across all assets in-sample is reported; if T1 has fewer than 40 switches in total in-sample (about one per asset every four years), the note labels the in-sample test "low-powered" in its first paragraph.
- Plots: gross exposure of T1 over time with the number of assets on; drawdown of T1 against B3 and B4; per-asset on/off strips.

### 9.7 What did not work

As Study 001 §9.7: a mandatory section listing every trial, sub-period, cost case and asset where T1–T4 failed any criterion or where the result was weakest; an empty section is not acceptable.

## 10. Known pitfalls and how the design avoids them

| Pitfall | Treatment |
|---|---|
| Long bias mistaken for trend [HLWZ20, GJ18] | B4 holds T1's average gross exposure with no timing; C1, C2 and O1 are against B4. |
| Volatility scaling mistaken for trend [KTW16] | B3 scales exactly as T1 does; C1 and O2 are against B3 as well. |
| The designer has seen IEF's out-of-sample path | Disclosed (§2.4, §8.3); no parameter set after it; eleven-asset run pre-registered and reported next to every headline table. |
| Survivorship in the universe | All twelve funds exist today and were chosen for size and age; a universe chosen today of funds that survived is a known upward bias for long-only benchmarks and is stated in the note's limitations. Nothing in the rule depends on it, and B1–B4 carry the same bias. |
| Staggered entry chosen to help the rule | Entry is a function of the vendor file's first bar and the 12-month lookback only (§8.1), fixed before any return. |
| Turnover hidden | Turnover, gross exposure, per-ETF costs and the breakeven curve are mandatory outputs (§9.3, §9.6). |
| Vol estimate look-ahead | σ uses the 63 days ending at t; unit test §5.3.4 iii. |
| Diagonal vol forecast overstates diversification | Reported against realised (§9.6); the portfolio target is a per-asset scale, not a promise about the portfolio (§6.2). |
| Second-vendor gate chosen after seeing the numbers | ±0.20% p.a. fixed here with its reason; every branch of §5.3.2 fixed here. |
| Degenerate bootstrap (Study 003's finding) | Library defines the interval on non-degenerate resamples and reports the count; unit test §5.3.4 vii. |
| Multiple testing | N = 4 logged before any run; DSR at N = 4 decides, N = 10 reported; no further trial without a dated log entry. |

## 11. Forward record (no paper order)

This study **places no paper order**. Its universe is beyond the symbols approved for paper trading (only IEF and BIL are on record, scoped to Study 001 at the time of writing), and a not-yet-supported rule earns no approval request. Instead, from the publication date of the note:

- **11.1 Shadow record.** On the last NYSE trading day of each month, after the close, compute the twelve signals, volatilities and T1 weights from the broker's daily bars (`adjustment='all'`), write a dated decision record to `paper-log/decisions/<signal_date>.json` (signals, σ, weights, cash, the bars' last dates), and mark a notional 10,000 USD book at the next session's closes; never backdated, never rewritten; a missing bar is logged as "signal unavailable" and the previous weights are carried.
- **11.2 Monthly line** appended to `paper-log/shadow.csv`: date, T1 book value, B3 and B4 book values from the same closes, SPY and IEF.
- **11.3 Promotion** to real paper orders would need: a "supported" verdict or an explicit owner decision to trade a not-supported rule as pre-registered; symbol approvals for the universe; Independent Risk clearance of a sleeve within the desk's limits (per-order cap 2,500 USD, which with twelve assets means a sleeve of at most 2,500 USD per asset-order); and an execution path that can trade twelve assets inside the 15:30–16:00 ET window. None of this is part of this study.

## 12. Risk limits

None apply to a shadow record. If §11.3 is ever invoked, Study 003 §12 as amended (sleeve, caps, drawdown halt, one-day review, order window) is the starting point, tightened per asset, and Independent Risk writes `RISK_CLEARANCE.md` before the first order.

## 13. Repository layout and the shared library

```
research/004-xasset-trend-voltarget/
  PREREGISTRATION.md   this document (immutable except §16 amendments)
  trials.md            trial log and data-check log
  README.md            the study note (written only after results; includes "What did not work")
  APPROVED             written at §14 step 3
  reproduce.sh         --check | --insample | --oos (--oos refuses if results/oos/ exists)
  requirements.txt
  src/                 config.py (this study's constants: universe, costs, σ_a, w_cap, windows),
                       data.py (vendor fetch + manifest, reusing the 003 adapters by attribution),
                       checks.py (§5.3.1–§5.3.2), run.py (the three modes)
  tests/               §5.3.4 (i)–(viii) and the data-check branches
  data/raw/            git-ignored
  results/             data_manifest.json, checks/, insample/, oos/ (written once)
  paper-log/           the forward shadow record (§11)
qune_research/         the shared library, built for this study (§14 step 2), with its own tests:
  calendar, data adapters with hashing, cost model, vectorised monthly engine with an event check,
  stats (Sharpe with HAC standard errors, PSR, DSR, Ledoit–Wolf, stationary bootstrap with the
  degenerate-resample rule), report (tables and plots)
```

Studies 001–003 keep their frozen code and are not edited.

## 14. Order of operations

1. Commit this document and `trials.md` (this commit). No fetch, no check, no return.
2. Build `qune_research/` and the study's `src/` and `tests/`; all tests pass including §5.3.4 (i)–(viii); add the study and the library to CI; commit.
3. Write `APPROVED`; commit.
4. `reproduce.sh --check`: §5.3.1 fetch and coverage, then §5.3.2 overlap per symbol; outputs to `results/checks/`; the manifest, exclusions and the entry dates recorded in `trials.md` and §16; **one run**; commit whatever the outcome; halt if §5.3.5 says so.
5. Append run dates for T1–T4 to `trials.md`; commit.
6. `reproduce.sh --insample` → `results/insample/` (including the eleven-asset run, k, and every §9.6 item); commit.
7. In-sample part of README.md, including "What did not work" and the power statement; commit.
8. `reproduce.sh --oos` once → `results/oos/`; commit. Verdict per §9.5.
9. Finish README.md; publication date = commit date; root README rows.
10. Independent review (separate agent, did not write the code): `REVIEW.md`, with a recompute script of its own.
11. Shadow record from the first month-end after publication (§11).

No step may be reordered. Step 4 shows no return of any rule; steps 6 and 8 are the only times the author sees any rule return before the review.

## 15. Things this study deliberately does not do

No short positions, no leverage, no currency ETFs, no single stocks, no futures. No lookback other than 12, 6 and 3 months, no threshold other than zero, no volatility window other than 63 days, no estimator other than close-to-close (no Yang–Zhang or Parkinson), no target other than 10% per asset, no cap other than 25%, no rebalancing band, no covariance-based (as opposed to diagonal) sizing, no transaction-cost optimisation, no signal smoothing, no regime filter, no carry or value overlay. No choice of anything on the out-of-sample window. It does not re-check the cash leg. It does not claim that a long/flat ETF portfolio reproduces the published long/short futures results, and it does not place a paper order.

## 16. Amendments

(Append dated entries here; each must state what changed, why, which results had already been seen at the time, and the trial count N.)

### 2026-10-22: engine check (ii) made testable; library piece 1 built (§14 step 2, in progress); no data fetched, nothing seen

- **What changed:** the wording of engine check §5.3.4 (ii). As written ("shifting every series forward by one trading day moves every signal and execution date by one day and changes no weight") it cannot hold in general: a one-trading-day shift changes which bar is the last of a calendar month, so the month-end signal dates and the 12-month lookback bars are not the same bars shifted. The test implements the check's purpose (no date is hard-coded; every signal, execution date and weight follows the data) with a shift that preserves each bar's calendar month and ordering, one calendar year, and asserts that every signal date, execution date, weight and period return moves with it unchanged. The design (§6) is untouched.
- **Built:** `qune_research/` piece 1: `dates` (month-end signal dates, next-bar execution dates, the lookback bar with the entry rule of §8.1), `sizing` (excess momentum, long/flat signal, 63-day close-to-close volatility, the capped inverse-volatility weights with the proportional scale-down), `engine` (multi-asset monthly backtest with drift and per-asset costs, the exposure ratio k for B4). Tests for §5.3.4 (i), (ii), (iii), (v), (vi), (viii) on constructed data: 9 pass; added to CI. Not yet built: the data adapters with hashing, the statistics module with the degenerate-resample rule (check vii), the report, the study's own `src/` and `reproduce.sh`.
- **What had been seen when this was written:** nothing of this study's data; no file for the ten unfetched ETFs exists on disk. **N = 4**, unchanged.
- **Later the same evening (piece 2):** `qune_research/stats.py` ported from Study 003's frozen `src/stats.py` by attribution with one change, the degenerate-resample rule of §2.5 (resamples with zero variance are dropped from the bootstrap Sharpe interval and their count is reported; an all-zero series raises instead of returning NaN). Study 003's statistics tests rerun against the port, plus the check (vii) test: 21 library tests pass. Nothing seen; N = 4.

### 2026-10-22 (21:2x London): §5.3 data checks run once; SPY and DBC excluded under branch X; N = 4 unchanged; no return of any rule computed

**What was seen at the time of writing:** `results/checks/` only (D0 dates and coverage; D1 overlap statistics on 2016-01-04 to 2018-12-31). No signal, weight, benchmark or portfolio return has been computed.

**D0 (§5.3.1), commit 24a40fe:** eleven vendor files fetched (2002-07-01 or the fund's first bar, to 2026-09-30), IEF and BIL reused byte for byte from Studies 002 and 003. All thirteen pass coverage from their first bar with no missing NYSE trading day at all; no retry was needed; nothing excluded. Inception confirmed for the nine funds whose first bar lies after the fetch start (EEM 2003-04, SHY/IEF/TLT/LQD 2002-07, HYG 2007-04, GLD 2004-11, DBC 2006-02, VNQ 2004-09); SPY, IWM and EFA start at the fetch start as expected. **Every entry signal date equals the §4 expectation** (eight at 2003-12-31; EEM 2004-04-30, VNQ 2005-09-30, GLD 2005-11-30, DBC 2007-02-28, HYG 2008-04-30).

**D1 (§5.3.2), commit 6f01969:** broker bars were available for every symbol, so no symbol is single-vendor. On 753 common return days, the annualised mean daily difference vendor − broker was within ±0.20% p.a. for ten symbols and outside it for two: **SPY +0.3146% p.a.** and **DBC −0.4648% p.a.** Both are **excluded from the universe under branch X**, as written, before any return of any rule was computed. The ex-ante expectation (every symbol under 0.10% in absolute value) was wrong for three symbols: the two excluded and HYG (+0.1410%, inside the gate, stays). The remaining nine were within 0.09%; IEF's +0.0494% is the figure Study 002 recorded on the same overlap. Descriptive figures (no decision weight): SPY's gap comes with 14 days over 10 bp and a largest daily gap of 51 bp, DBC's with a largest daily gap of 139 bp; the author has not looked at which days these are and does not investigate, because the branch is fixed and an investigation would be a choice made after seeing the data.

**§5.3.5:** two exclusions (at most three allowed); every class keeps at least two instruments (equities IWM, EFA, EEM; Treasuries SHY, IEF, TLT; credit LQD, HYG; real assets GLD, VNQ). **The study proceeds with ten instruments.** N_t in §6.2 counts the ten.

**Consequences written now, before any return, with no new parameter:**
1. The "without IEF" run of §9.6 is a nine-asset run. Every table that §9.6 says is reported "next to the twelve-asset table" is reported next to the ten-asset table.
2. B2 (60% SPY / 40% IEF), the crisis table's SPY row and the SPY correlations of §9.6 keep the vendor SPY series exactly as pre-registered: branch X removes a symbol from the *universe*; it does not say which SPY series the descriptive benchmark uses, and choosing a different one now would be a choice made after seeing the check. The note must say, wherever B2 or SPY appears, that the SPY series failed the universe gate against the broker by +0.31% p.a. on 2016–2018, so B2's level carries that uncertainty. B2 is descriptive; the decisive benchmark B4 is built from the ten universe assets and is unaffected.
3. The cost table (§9.2) applies to the ten; SPY's and DBC's rows are unused.
4. The power statement's threshold (40 switches in-sample) is unchanged; with ten assets it is slightly stricter per asset, which is the conservative direction.
5. The disclosure of §2.4 and §8.3 stands: one of the ten (IEF) is not blind.

What this costs the study, said plainly: the equity class loses its largest and most liquid instrument and the real-asset class loses its only broad commodity index, so the portfolio tested is less representative of the published cross-asset universe than the one pre-registered. The gate was set at ±0.20% because the author expected dividend-booking differences of under 0.10%; two symbols exceeded that by a wide margin and the pre-registered consequence is applied without exception. N = 4.

### 2026-10-22 (22:3x London): in-sample run executed once (§14 step 6); C1 and C2 fail; seed and two procedural notes; N = 4 unchanged

**What was seen at the time of writing:** `results/insample/` (commit 02eb987): every in-sample table for T1–T4 and B0–B4, ten and nine assets, base and stress. **No out-of-sample return has been computed.**

- **Result:** T1 Sharpe 0.886 against 0.880 (B3) and 0.880 (B4); Newey–West t of mean(T1 − B4) 0.65; DSR 0.998 at N = 4; sign unchanged under stress. **C1 and C2 fail, C3 and C4 pass**, for T1 and for T2–T4 alike; the nine-asset run without IEF gives the same four outcomes. Under §9.5 the verdict is already "not supported"; step 8 (the single out-of-sample run) proceeds as registered. k frozen: 0.8018 (ten), 0.7764 (nine). Power: 167 switches, "as registered".
- **Bootstrap seed (procedural gap):** this document fixed no seed for the stationary bootstrap and the Ledoit–Wolf test (§9.3 refers to Study 001's items, whose seed lived in that study's §13). The run uses Study 003's seed 20261021, set in `src/config.py` before the run (commit bff736c), so that every resample is reproducible. No result was seen before the seed was fixed.
- **Trial-log time (correction):** the run dates for T1–T4 were entered in `trials.md` before the run (step 5, commit bff736c) as "22:5x London", an estimate of when the run would start; it started at 22:26. The rows were corrected to the actual time in the results commit (02eb987) and say so. Nothing else in the rows changed.
- **Cash leg data:** DTB3 was re-fetched from FRED at run time, as §5.1 allows ("re-fetched if reachable"), and recorded in the manifest; it is the same series Study 003's file holds, extended to 2026-10-21.
- **Observation on the design, recorded for the note and for successors, not acted on:** B3 and B4 have the same Sharpe ratio by construction (B4 is B3 scaled with the remainder in cash and costs scale with it), so C1's two conditions are one bar. B4's distinct role is in C2 and O1 (the mean difference). The criteria are applied exactly as written.
- **N = 4**, unchanged. No parameter, threshold, window or universe changed.

### 2026-10-22 (23:3x London): the out-of-sample end bar fixed before the single run (§8.2 against §5.3.1); N = 4 unchanged

**What was seen at the time of writing:** every in-sample result (§16 entry above). **No out-of-sample return has been computed.** This entry is committed before `reproduce.sh --oos` runs.

- **The conflict:** §8.2 says the last out-of-sample holding period ends at the first execution date of October 2026, but §5.3.1 fetched every vendor file to 2026-09-30, so the ten fetched files hold no October bar. The two files reused by hash from earlier studies (IEF from Study 002, BIL from Study 003) reach 2026-10-21. The code built the bar index as the union of the universe's dates, so without a change the schedule would **not** have refused (the previous run's note said it would; that was an inference, and it was wrong): the last period would have ended on 2026-10-01 for IEF and for the BIL cash leg, while the other nine assets were forward-filled from their 2026-09-30 close, one trading day short. That is an inconsistency between instruments inside one holding period, and it would have passed silently.
- **Decision (before the run):** the held-back window ends at the **common last bar of every instrument and the cash ETF, 2026-09-30**. The last holding period runs from the close of 2026-09-01 to the close of 2026-09-30 instead of 2026-10-01, one trading day short, the same for every instrument; the 2026-09-30 signal is computed and published (it is the terminal position, the first entry of the shadow record) but starts no period. 93 holding periods, as §8.2 expected. The window's label "2019-01-01 to 2026-09-30" is honoured literally.
- **Alternatives not taken, and why:** (a) fetching the 2026-10-01 bar for the ten files would be a second fetch after a result had been seen; the vendor re-bases adjusted closes between fetches (§5.1), so a one-bar append could not be spliced safely and a full re-fetch would replace the files whose hashes the in-sample manifest records and would need the §5.3.1 coverage check again, which is registered as one run. (b) Dropping the 2026-08-31 signal would discard a whole month of the window for want of one day. Neither alternative was tried; no return under any of the three was computed.
- **Implementation:** `qune_research.dates.schedule` gains `end_at_last_bar` (default off; the in-sample path is untouched and the library's earlier behaviour is unchanged when the bars reach the next execution date), which only applies when the *last* signal has no later bar; `src/run.py` cuts the out-of-sample bar index at the common last bar of the universe and the cash ETF and records `common_last_bar` and `last_period_ends_at_last_bar` in `results/oos/summary.json`. Two tests (library and study) cover the cut, the unchanged case and the refusal when more than the last signal lacks a bar.
- **What this costs the study:** one trading day of the last period (2026-10-01), nothing else. Study 003's out-of-sample window did end at 2026-10-01 because its broker bars held that date, so the two studies' windows differ by that one day; recorded here so that nobody reads the difference as a choice.
- **N = 4**, unchanged. No parameter, threshold or universe changed; no out-of-sample return seen.

### 2026-10-23 (00:4x London): independent review done; corrections of record, no run, N = 4 unchanged

- The study was reviewed by a separate agent session (REVIEW.md): confirmed with findings, no must-fix. Two should-fix items are answered here and in the note.
- **Time labels.** The heading of the 2026-10-22 entry above reads "(23:3x London)"; the commit that carries it, `1697e9d`, was made at 23:20:12 London. Five trial-log rows carry the same kind of estimate (20:3x, 20:4x, 21:3x, 22:4x, 23:3x against committer times 20:27, 20:29, 21:25, 22:25, 23:20). Corrected by this entry and a dated row in `trials.md`; the earlier text is left as written. The order of events is unchanged.
- **Fourteen README figures** were rounded twice and are one unit off in their last digit (the largest: B3 and B4's out-of-sample Sharpe, 0.200 for a stored 0.19947). Corrected in place in the note, with every change listed in its review section. No criterion input is affected; no results file changed.
- No parameter, threshold, universe or result changed. Nothing was run.

### 2026-10-23 (15:2x London): the forward shadow record's code (§14 step 11, before the first forward month-end); implementation decisions; no forward month exists; N = 4 unchanged

**What was seen at the time of writing:** every in-sample and out-of-sample result (committed, reviewed). **No forward month exists; nothing is written under `paper-log/`; no return of this study was computed by this step.** Code: `src/forward.py`, `reproduce.sh --forward decide|shadow`, `tests/test_forward.py` (commit 5ad2453).

- **Universe of the record.** §11.1 says "the twelve signals"; branch X excluded SPY and DBC before any return (entry of 2026-10-22 21:2x). The forward record computes the **ten** instruments the data checks left, read from `results/checks/data_checks.json` as the backtest did; SPY is fetched as the §9.6 reference and never held. N_t counts the ten.
- **Inputs.** The broker's `adjustment='all'` daily bars, as §11.1 says, for the ten, the cash ETF and SPY, fetched from 2025-06-02 (covers the 12-month lookback bar and the 63 return days of every record) into `paper-log/raw/` with their own `paper-log/manifest.json`; the study's `data/raw/` and `results/data_manifest.json` are never touched. The signal is a ratio of closes, so the vendor/broker scale difference does not enter; the broker's SPY serves only as a reference return.
- **Functions.** The record calls the library functions the backtest called (`sizing.excess_momentum`, `realised_vol`, `target_weights`); B3's weights from the same volatilities with every signal on; B4 = B3 × k with k read from `results/insample/summary.json` (0.8018), never recomputed. A record for 2026-08-31 and one for 2026-09-30 computed from the frozen vendor files (check only, nothing written) reproduce the committed `signal_s12`, `signal_vol` and `t1_periods` files to 1e-16.
- **Close gate.** §11.1 said "after the close" without an hour. No record before **21:15 UTC** on the signal date (the 16:00 New York close under EDT or EST, plus the broker's end lag); a bar fetched during the session would be the partial day. Also: no record before 2026-10-30, none on a date that is not the last NYSE trading day of its month, none without the cash ETF's bar at t (every signal needs the cash index at t, §6.1). A refused run writes nothing.
- **Missing bar.** As §11.1 says: an instrument without a bar at t is logged "signal unavailable" in the record and its previous weight is carried; the other instruments are sized at their count (N = those signalled), and the §6.2 scale-down applies to the carried book as a whole. The record's status names the carried instruments.
- **Books.** Three notional 10,000 USD books (T1, B3, B4) that **start all cash at the first execution date, 2026-11-02, the initial purchase charged like any trade** (the engine's own first-period convention, §6.4). Each shadow line marks them at the period's closes with one period of the engine's arithmetic (`period_step`, tested against `qune_research.engine.run` to 1e-14 over eight consecutive periods); the drifted weights go to `paper-log/books/<period_end>.json` so the next period's cost is charged from them. A period runs between the first bars on or after the two execution dates that every instrument and the cash ETF have (a missing execution bar moves the trade to the next bar, slippage recorded, §6.4). Base costs; the stress multiple is not marked.
- **The uncounted month.** The held-back window's last period ended at the common last bar 2026-09-30 (entry of 2026-10-22 23:3x); the 2026-09-30 signal's weights (the terminal position: four instruments on, IWM, EFA, EEM and GLD, gross exposure 76.6%, from the committed signal and volatility files) would have been held from 2026-10-01 to 2026-11-02. That period is counted in neither the window nor the forward record, and the forward books do not start from those weights: they start in cash, so the first line's cost is a purchase from cash, not a rebalance. The 2026-10-30 record reports the terminal position as `holding_before` and the turnover against it, for information. Disclosed here rather than attached to either window after the fact.
- **The first shadow line** can only be written after the close of the second record's execution date (2026-12-01), for the period 2026-11-02 to 2026-12-01. The 2026-10-30 run produces a decision record only.
- **What is not built:** no scoring rule (§11 registers none for the shadow record; its figures are descriptive and the verdict stays "not supported"); no interim summary beyond the line itself; no chart. Promotion to a paper order needs everything in §11.3; none of it is asked for.
- **N = 4**, unchanged. No parameter, threshold, window or universe changed.
