# Study 003 — Time-series momentum in intermediate Treasuries: hold IEF when its trailing 12-month excess return is positive, bills (BIL) otherwise

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-10-22 |
| Status | pre-registered; **no data check run, no return of any rule or benchmark computed** |
| Version | 1.0 (any change after this commit requires a dated amendment appended to §16 before any further step is run) |
| Study type | fixed income / macro (programme stage 2); a single pre-registered hypothesis, long-only, monthly, two instruments, **actual ETF history only** (no synthetic duration series) |
| Instruments | **IEF**, **BIL** (approved by the owner for paper trading on 2026-10-21 under Study 001; no new symbol) |
| Approval | The owner approved Study 001's design and symbols on 2026-10-21 and, the same day, delegated all further decisions on this research programme to the orchestrator (recorded in the workspace decision log). This document is approved by the orchestrator under that delegation on the date of its commit. Independent Risk clearance of §11–§12 is still required before the first paper order. |
| Total trial count registered | **3** (§7). Studies 001 and 002 registered three trials of a different hypothesis and never ran them; they do not count here (§7). |
| Author | the orchestrator (Qune) |

Nothing in this document reports or implies the performance of any rule. **What the author has seen** of the data this study uses is listed in §2.4; in one line: IEF and BIL daily returns inside 2016-01-04 to 2018-12-31, the vendor-overlap and validation statistics of Studies 001 and 002 (correlations, slopes, tracking errors, mean gaps, and IEF's annual volatility for each year 2003–2015), and nothing else. No 12-month return of IEF, no signal value, no return of T1, T2, T3 or any benchmark has been computed on any data by anyone. The out-of-sample window (2019-01 to 2026-09) has never been touched by any study.

---

## 0. Why this question, and what carries over

Studies 001 and 002 asked whether the sign of the 10-year minus 3-month term spread should decide between IEF and bills. Both halted at their pre-registered data check: the long pre-ETF history they needed had to be built from yields, and the synthetic series failed a fidelity threshold each time (001: level; 002: tracking error on 2003–2015). No rule was tested. The orchestrator's decision of 2026-10-22, recorded in the workspace decision log and in the 002 halt note, was that the next study would need **no synthetic duration series at all**: actual ETF history only, from the ETFs' own inception, with the same untouched out-of-sample window.

That constraint fixes the sample (IEF from 2002-07; about fifteen in-sample years) and therefore the kind of question that can be answered: one whose signal changes sign often enough in fifteen years to be tested. Four candidates were considered (bond time-series momentum; a real-yield or breakeven signal between TIP and IEF; a stock–bond correlation regime for an SPY/IEF mix; dollar trend via UUP). Time-series momentum was chosen because: (i) it is the most-studied rule in the literature for this asset class, with a canonical definition that leaves nothing to tune (§3, §6); (ii) it is independent of the term-spread hypothesis (a price signal, not a curve signal); (iii) it needs no new symbol, so paper trading can start under the approvals already on record; (iv) its signal is expected to change sign several times in 2003–2018 (hiking cycle 2004–2006, 2008, 2013, 2016–2018; §2.4), which the term-spread rule on the same window would not (the 10-year minus 3-month curve was inverted for less than a year of it, in 2006–2007). The breakeven and dollar questions remain open for later studies; neither needed to be rejected on its merits.

**Carried over unchanged from Study 001's pre-registration (commit `b6db436`) and the §16 clarification there:** instruments (§4), the cash-leg construction from DTB3 (§5.2 there, the only modelled series here), execution timing convention (signal at a month-end close, trade at the close of the next NYSE day), 100% sizing, monthly rebalancing, the cost cases (2 bp and 4 bp per side), benchmarks B0–B3 with B3's weight frozen from in-sample signals, the twelve metrics, the deflated Sharpe ratio at N = 3 and N = 10, decision criteria C1–C4 and O1–O2, the verdict table and its precedence (not supported > inconclusive > supported), the mandatory "What did not work" section, the out-of-sample window 2019-01-01 to 2026-09-30 run exactly once, the paper-trading plan and risk limits (fixed sleeve of 4 500 USD). The backtest engine (`backtest.py`, `stats.py`, `report.py`, `calendar` conventions) is copied from Study 002 by attribution in the commit; only the signal module and the data path are new.

**What is different:** the question and hypothesis (§1–§2); the signal (§6); the trials (§7); the in-sample window, 2003-08 to 2018-12 (§8.1); the data path, with actual ETF prices for the duration leg throughout and a single modelled cash leg checked over BIL's full history (§5); the sub-periods (§9.6); the paper-trading signal source (§11).

## 1. Question

**Does holding IEF only when its trailing 12-month return exceeds the trailing 12-month return on bills, and holding BIL otherwise, improve risk-adjusted return over holding IEF throughout, after realistic costs?** In plain words: when intermediate Treasuries have beaten cash over the past year, stay in them; when they have not, step aside into bills. Is that better than just holding them?

## 2. Hypothesis

### 2.1 Statement

- **H1:** the sign of IEF's past 12-month excess return over bills predicts the sign of its next-month excess return, so that the switching rule (T1 in §6) earns a higher Sharpe ratio than both buy-and-hold IEF and a constant-mix portfolio with the same average IEF exposure, after costs (criteria C1–C4 in Study 001 §9.5, applied as written).
- **H0:** monthly excess returns of IEF are not predictable from their own 12-month history; the rule's return equals that of the exposure-matched constant mix minus trading costs, and any Sharpe difference is within noise.

### 2.2 Economic grounding

1. **Policy persistence.** Central banks move the policy rate in sequences, not single steps, and intermediate yields follow the expected path of policy. A year in which yields have risen enough for IEF to lag bills has usually been a year of tightening, and tightening cycles have historically lasted longer than one year, so the conditions that produced the negative excess return tend to persist into the next month. The opposite holds in easing cycles.
2. **Slow diffusion and under-reaction.** The behavioural account of trend (initial under-reaction to information, then a delayed drift) is the standard explanation offered for time-series momentum across asset classes (Moskowitz, Ooi and Pedersen, 2012); bond markets are not exempt from it in that evidence.
3. **The evidence is cross-asset and long.** Time-series momentum with a 12-month lookback and a one-month hold is documented across 58 futures contracts including government bonds, 1985–2009 (Moskowitz et al., 2012), and over more than a century of data (Hurst, Ooi and Pedersen, 2017). Bonds are among the asset classes in which the effect is reported. A long-only, unlevered, single-asset version is a much weaker form of the same claim, which is why the benchmarks in §9 remove the unconditional duration exposure before the rule is given credit.

### 2.3 Why the edge might not be there, or not survive

- **Huang, Li, Wang and Zhou (2020)** show that the predictive regression behind time-series momentum has little power once the unconditional mean return of each asset is accounted for: much of what looks like trend is "assets with a positive drift were mostly long". That is exactly the confound an exposure-matched benchmark (B3) is built to remove, and the study's verdict rests on B3, not on buy-and-hold alone.
- **One asset, few cycles.** Fifteen in-sample years contain perhaps three or four independent rate cycles; a monthly switching rule on one instrument is a low-power test however it is dressed, and 2003–2018 was, on balance, a bull market in Treasuries in which a momentum rule would have been long most of the time. The in-sample test may be unable to separate H1 from H0 at the pre-set bar; §9.6 pre-registers how that is reported.
- **Whipsaw.** In a range-bound market the 12-month return crosses zero repeatedly; each crossing costs a round trip and the rule can lose to the constant mix with no change in the underlying premium.
- **Publication and crowding.** Time-series momentum has been public since 2012 and is widely implemented; the out-of-sample window (2019–2026) is a post-publication test.
- **No volatility scaling.** The published results scale positions by inverse volatility; this study holds 100% or 0% of a single ETF (no leverage, no scaling), so published Sharpe ratios do not transfer and are not the bar.

### 2.4 Designer's prior knowledge (disclosed)

The author knows the broad history of US rates and Treasury returns from 2002 to 2026 as public knowledge: the 2004–2006 hiking cycle, the 2008 rally, the 2009 and 2013 sell-offs, the 2016–2018 normalisation, the 2019–2020 rally, and the 2022 sell-off, which is the largest drawdown in IEF's history. The author therefore expects, before any computation, that T1 will be in cash for a minority of in-sample months (a prior of roughly 20–35%) with roughly 10–20 switches, and that the out-of-sample window contains the single episode the rule most exists for. None of these expectations is used to set a parameter: the rule has none (§6).

Of the data this study uses, the author has seen: IEF and BIL daily returns inside 2016-01-04 to 2018-12-31 (Studies 001 and 002, validation window 1); the statistics of Study 002's window 2 (correlation, slope, tracking error and mean gap of IEF against a synthetic series over 2003-01-02 to 2015-12-31, and a post-hoc table giving those statistics and IEF's realised daily volatility for each calendar year 2003–2015); the Tiingo-versus-Alpaca overlap statistics for IEF over 2016–2018; and BIL's mean gap and tracking error against the cash accrual over 2016–2018 (−0.110% p.a. and 0.288% p.a. in Study 002's run). The author has seen **no** 12-month return of IEF, no monthly return of IEF before 2016, no signal value and no return of any rule or benchmark.

Mitigations: the rule and its lookback are the canonical ones from the literature and are not tuned; the threshold is zero; the benchmark set removes the average exposure; the out-of-sample boundary is unchanged from Studies 001 and 002, fixed on 2026-10-21 before any computation; forward paper trading is the only fully clean test.

### 2.5 What Studies 001 and 002 taught, applied here

- **No modelled series on the path to the result unless its bias is written down first and it can be checked on history the designer has not seen.** The duration leg is now the actual ETF throughout. The one modelled series left, the cash accrual, carries an ex-ante estimate (§5.3.3) and is checked over BIL's full history from 2007 (eleven and a half years, of which the designer has seen three).
- **A threshold must test what the series is used for.** Study 002 failed on a daily tracking-error limit set in a calm regime and applied to a volatile one, for a monthly rule that never uses daily tracking. The cash-leg check here therefore gates on the **level** (B1), which is what a monthly rule inherits from a cash leg, and reports the daily tracking error (B2) descriptively against its historical reference. This is decided now, with the reasoning, so that it cannot be re-derived after the number is seen.
- **Pre-commit every branch.** Every conditional step in §5.3 states, before any run, what happens on each outcome, including the one in which the second vendor's BIL series fails its overlap check.
- **Zero corrections.** Any data-check failure that is a halt ground is a permanent halt; nothing is re-derived after the result.

## 3. Literature

Checked against the Crossref registry on 2026-10-22 (DOI, title, authors, journal, volume, issue and pages matched; the year is the print year):

- Moskowitz, T. J., Ooi, Y. H. and Pedersen, L. H. (2012). "Time Series Momentum." *Journal of Financial Economics* 104(2), 228–250. doi:10.1016/j.jfineco.2011.11.003. The hypothesis tested here, in its canonical 12-month-lookback, 1-month-hold form; bonds are among the asset classes studied.
- Hurst, B., Ooi, Y. H. and Pedersen, L. H. (2017). "A Century of Evidence on Trend-Following Investing." *Journal of Portfolio Management* 44(1), 15–29. doi:10.3905/jpm.2017.44.1.015. Long-sample evidence including fixed income.
- Huang, D., Li, J., Wang, L. and Zhou, G. (2020). "Time Series Momentum: Is It There?" *Journal of Financial Economics* 135(3), 774–794. doi:10.1016/j.jfineco.2019.08.004. The critique in §2.3; the reason the verdict rests on the exposure-matched benchmark.
- Asness, C. S., Moskowitz, T. J. and Pedersen, L. H. (2013). "Value and Momentum Everywhere." *Journal of Finance* 68(3), 929–985. doi:10.1111/jofi.12021. The 12-1 convention (skipping the most recent month) used by trial T2.
- Kim, A. Y., Tse, Y. and Wald, J. K. (2016). "Time Series Momentum and Volatility Scaling." *Journal of Financial Markets* 30, 103–124. doi:10.1016/j.finmar.2016.05.003. Shows how much of the published result depends on volatility scaling, which this study does not use (§2.3).

Cited as reported, not verified against a registry (no DOI): Faber, M. T. (2007). "A Quantitative Approach to Tactical Asset Allocation." *Journal of Wealth Management* 9(4), 69–79 (SSRN 962461). The 10-month moving-average rule used by trial T3.

## 4. Instruments

Unchanged from Study 001 §4: **IEF** (iShares 7–10 Year Treasury Bond ETF; expense ratio 0.15%, inception 2002-07-22, both verified 2026-10-21 from a secondary source) and **BIL** (SPDR Bloomberg 1–3 Month T-Bill ETF; expense ratio 0.1356% as recorded in Study 001, not re-verified; inception 2007-05-25 per the first bar in the vendor series fetched under §5.3.2, to be recorded there). Both approved for paper trading on 2026-10-21.

## 5. Data

### 5.1 Sources

| Series | Source | Field | Used for | Window |
|---|---|---|---|---|
| IEF daily, split- and distribution-adjusted close | Tiingo (the desk's existing credential; the file fetched under Study 002 §5.3.4 step 1 on 2026-10-21, 6,099 rows from 2002-07-26, reused after a SHA-256 check against Study 002's manifest) | `adjClose` | in-sample duration leg and signal, 2002-07-31 to 2018-12-31 | in-sample |
| IEF, BIL daily bars, `adjustment='all'` | Alpaca Market Data (the files fetched under Study 001 on 2026-10-21, reused after a SHA-256 check) | adjusted close | out-of-sample instruments and signal from 2019-01; the BIL vendor overlap check (§5.3.2) | out-of-sample; overlap |
| BIL daily, split- and distribution-adjusted close | Tiingo, fetched under §5.3.2 step 1 of this study | `adjClose` | the cash-leg level check over 2007–2018 (§5.3.3); not an input to any return of the rule | check only |
| DTB3 | FRED (the file downloaded under Study 001 on 2026-10-21, reused after a SHA-256 check; re-fetched if FRED is reachable) | discount yield | the in-sample cash leg (§5.2) | in-sample |

Vendor data are licensed and are never committed; `data/raw/` is git-ignored and every file's provenance (vendor, URL, timestamp, rows, first and last dates, SHA-256) goes into `results/data_manifest.json`. The Tiingo IEF series was accepted as a stand-in for Alpaca's by the pre-registered overlap check of Study 002 (§5.3.4 step 2 there; 753 common days 2016–2018: correlation 0.999591, annualised mean difference +0.0494% p.a. against ±0.05%, recorded at commit `45743fa`). This study uses it for the whole in-sample period, including 2016–2018, so that the in-sample duration leg comes from one vendor and has no splice; the known +0.05% p.a. offset against Alpaca's convention is disclosed and is immaterial to a monthly sign rule.

Daily total return of an ETF on trading day t: `r_t = adjclose_t / adjclose_{t−1} − 1`. Tiingo's adjusted close is re-based to the latest date on each fetch, so the file's hash changes between fetches while every return ratio is unchanged; the manifest records the hash of the file actually used.

### 5.2 The cash leg (the only modelled series), unchanged from Study 001 §5.2

On each FRED business day t with a valid DTB3 observation at the previous valid observation s:

```
bey_s = 365 × (DTB3_s/100) / (360 − 91 × (DTB3_s/100))     (discount yield → bond-equivalent yield)
r_t   = bey_s × days(s, t) / 365 − 0.001356 × days(s, t) / 365
```

That is: the 3-month bill yield accrued over calendar days, less BIL's expense ratio pro rata, compounded into a daily total-return index `TRI_cash`. It is a rate, not a bond: it has no duration and no curve, and is used (i) as the instrument held when the rule is out of IEF, 2003-08 to 2018-12, and (ii) as the cash return in the signal (§6.1), in-sample. Out-of-sample both roles are filled by actual BIL from Alpaca. The construction is the one that passed B1 and B2 in Study 001's two validation runs and in Study 002's run on 2016–2018 (last reading −0.110% p.a. and 0.288% p.a.).

### 5.3 Data checks (one run; no rule applied; order and branches fixed now)

#### 5.3.1 D0: coverage of the in-sample IEF series

The Tiingo IEF file must contain a bar on every NYSE trading day from 2002-07-31 to 2018-12-31 with at most three consecutive missing days anywhere (the §6.5 rule); its first bar must be on or before 2002-07-31 (needed for the first 12-month return). Failure is a halt ground (the in-sample series would be unusable), and is not expected: the file's first row is 2002-07-26 and its row count is consistent with full coverage.

#### 5.3.2 D1: second-vendor BIL series and its overlap check (data check, pre-committed branches)

1. **Fetch** daily BIL from Tiingo from 2007-05-01 with the desk's existing credential (token read from the environment, sent as a header, never logged; no credential created). Record provenance in the manifest, including BIL's first bar. If the fetch fails, record the attempt in `trials.md` and §16; **branch F** below applies. Commit before step 2.
2. **Overlap check** over 2016-01-04 to 2018-12-31 against Alpaca's `adjustment='all'` BIL returns: **acceptance = annualised mean return difference, vendor − Alpaca, within ±0.05% p.a.** Correlation and tracking error are reported but are not thresholds, because BIL's daily return is quantised at about one basis point (a one-cent tick on a ~91-dollar price) and a one-day difference in how two vendors book a monthly distribution dominates both statistics without affecting the level, which is the only property the cash check in §5.3.3 needs. This is stated now so that it cannot be argued after the fact. Pass → §5.3.3 runs on 2007-06-01 to 2018-12-31 with the vendor series. Fail → **branch F**.
3. **Branch F** (vendor unavailable or overlap failed): §5.3.3 runs on 2016-01-04 to 2018-12-31 with Alpaca BIL only. That window has been seen (§2.4), so in branch F the cash leg before 2016 is **unchecked**, the study continues (the cash leg is a rate minus a published fee, not a model of a bond, and its level over 2009–2015 is bounded by bill yields that were near zero), and the note must say in its limitations that the pre-2016 cash leg rests on the 2016–2018 check alone.

#### 5.3.3 D2: cash-leg level check, with an ex-ante estimate

Statistic: annualised mean daily return difference, **BIL − TRI_cash**, on common trading days (the accrual compounded onto the ETF's trading intervals, as in Study 001 §5.3), over the window determined by §5.3.2.

Ex-ante estimate, written from fund facts and bill-curve shape only, % p.a., for 2007-06 to 2018-12:

| Component | Estimate | Reasoning |
|---|---|---|
| BIL holds 1–3-month bills against the 3-month rate in DTB3 | −0.02 ± 0.05 | Shorter bills yield less when the bill curve slopes up (2007–2008, 2016–2018), about the same when it is flat at zero (2009–2015). |
| Portfolio yield lags the spot rate by about a month | +0.04 ± 0.04 | The fund earns above spot when rates fall quickly (2007–2008: about 500 bp in eighteen months) and below spot when they rise (2016–2018); over this window the fall dominates. |
| Expense ratio | 0 ± 0.02 | 0.1356% deducted inside TRI_cash; the historical ratio may have differed by a few basis points. |
| Securities lending and other income | +0.01 (0 to +0.03) | Small for a bill fund. |
| Price versus NAV at the window ends | 0 ± 0.01 | Negligible over eleven years. |
| Daily reset and day-count conventions | 0 ± 0.03 | The accrual uses calendar days at a bond-equivalent yield; the fund's accounting differs slightly. |
| **Central estimate** | **+0.03 → 0.00** | rounded to 0.05 |
| **Sum of absolute ranges** | **0.18 → 0.20** | rounded up to 0.05 |

**Threshold: B1 within ±0.30% p.a.**, the value inherited from Study 001, which is wider than the sum of the ranges above (0.20); it is kept rather than tightened because the inherited value has been in force since 2026-10-21 and the point of the estimate is to be able to say, after the run, which component was wrong. **Failure is a permanent halt before any rule is tested (§5.3.5).** The bound is proportionate to what it protects: a level error of at most 0.30% p.a. on the cash leg, held in a minority of months, moves the strategy's annualised return by at most a few basis points against a C1 margin of 0.10 in Sharpe units (about 0.5% p.a. at IEF's volatility).

Reported descriptively, no decision weight: **B2**, the annualised tracking error of the same daily difference, against its historical reference of 0.50% p.a. (Study 001's threshold) and its 2016–2018 reading of 0.288%; and the mean gap in each calendar year of the window. The reason B2 does not gate is in §2.5: a monthly rule inherits the cash leg's level, not its daily noise, and 2008 is the kind of regime in which the daily noise of a bill fund was large while its monthly level was not.

#### 5.3.4 Engine checks (unit tests, run before any data check)

(i) With the signal forced to "always IEF" at zero cost, T1 equals B1 to machine precision; forced "always BIL", it equals B0. (ii) Shifting every price and yield series forward by one day moves every signal and execution date by one day and changes no target. (iii) Perturbing any price dated after a signal date leaves that date's signal unchanged (no look-ahead). (iv) On a constructed price series the 12-month return equals the product of the twelve calendar-month returns ending at the signal month, and the 12-1 variant excludes exactly the most recent month. (v) On a constructed series the 10-month moving-average signal (T3) flips on the month the price first crosses the average, not before. (vi) The B3 weight equals the fraction of in-sample holding periods in which T1 holds IEF.

#### 5.3.5 Halt rule

If D0 fails, or D2 fails (B1 outside ±0.30% p.a. on the window §5.3.2 determines), **the study halts permanently before any rule is tested.** No correction of the cash leg is allowed under this study. Every statistic is published whatever the outcome, with the ex-ante estimate next to the observed value. A failed overlap check (§5.3.2) is not a halt ground; it selects branch F.

### 5.4 Data availability (verified from the files on disk on 2026-10-22, dates only)

IEF (Tiingo): 6,099 rows, 2002-07-26 to 2026-10-21. IEF and BIL (Alpaca): 2,716 bars each, 2016-01-04 to 2026-10-21. DTB3 (FRED): valid from 1954-01-04 to 2026-10-19. BIL (Tiingo): not yet fetched; its first bar is recorded at §5.3.2 step 1.

## 6. Exact rule specification

### 6.1 Signal

Let `TRI_IEF` be IEF's adjusted-close total-return index and `TRI_cash` the cash index (§5.2 in-sample; actual BIL out-of-sample). On signal date t (§6.3), with t₁₂ the last NYSE trading day of the calendar month twelve months before t's month:

```
mom_t = TRI_IEF(t) / TRI_IEF(t₁₂) − TRI_cash(t) / TRI_cash(t₁₂)        (12-month excess return, decimal)
```

Primary rule (T1): `target_t = IEF if mom_t > 0 else BIL`. Threshold exactly zero; no smoothing, no band, no volatility scaling, no parameter.

### 6.2 Position sizing

Unchanged from Study 001 §6.2: 100% of the sleeve in the target ETF, whole shares, no leverage.

### 6.3 Timing and look-ahead control

- **Signal date t** = the last NYSE trading day of calendar month m (the last bar of the month in the ETF series). The signal uses closes dated ≤ t only.
- **Execution date e** = the first NYSE trading day strictly after t; the trade is assumed to fill at the official close of e. The position set on e is held to the close of the next execution date. This is the same one-day lag as Studies 001 and 002, kept so that the three studies share a convention; for a price signal known at the close of t it is conservative.
- No observation dated after t is used in forming `target_t` (unit tests §5.3.4 ii–iii).

### 6.4 Rebalancing and 6.5 Missing data

Unchanged from Study 001 §6.4–6.5: monthly at e only; no order and no cost when the target equals the holding; no intra-month stops in the backtest; a missing bar on an execution date moves the trade to the next bar and logs the slip; more than three consecutive missing bars halts the study. The cash accrual is defined between consecutive FRED observations and needs no special case.

### 6.6 Pseudo-code (monthly loop)

```
holding = BIL
for each calendar month m from 2003-07 (in-sample) or 2018-12 (out-of-sample):
    t    = last NYSE trading day of m
    t12  = last NYSE trading day of month m − 12
    mom  = TRI_IEF[t]/TRI_IEF[t12] − TRI_cash[t]/TRI_cash[t12]
    target = IEF if mom > 0 else BIL                   # T1
    e    = first NYSE trading day > t
    if target != holding: charge c on the sale and c on the purchase; holding = target
    accrue return of holding from close[e] to close[e_next]
```

## 7. Registered trials (N = 3)

| ID | Name | Difference from T1 | Purpose |
|---|---|---|---|
| T1 | Primary: 12-month excess return sign | — | The hypothesis (Moskowitz et al., 2012) |
| T2 | V1: 12-1 (skip the most recent month) | `mom` computed from t₁₂ to t₁, the last NYSE day of month m − 1, instead of to t | Robustness to short-term reversal in the most recent month (the convention of Asness et al., 2013) |
| T3 | V2: 10-month moving average (Faber, 2007) | `target = IEF if adjclose_t > mean of the last 10 month-end adjusted closes (including t) else BIL`; price only, no cash term | Tests whether a different, equally canonical, trend definition changes the conclusion |

All three run on the same holding periods (2003-08 to 2018-12 in-sample). Logged in `trials.md` before any is run. The deflated Sharpe ratio is reported at N = 3 (decision) and N = 10 (sensitivity, for the implicit search over well-known trend rules). Why Studies 001 and 002's three trials do not count: they tested a different hypothesis with a different signal, and no return of them was ever computed or seen; a trial counts when a return is seen. No other variants will be run: no other lookback, no threshold other than zero, no volatility scaling, no second asset. Any addition is appended to `trials.md` with a date before it runs and N increases.

## 8. Sample split

### 8.1 In-sample

**2003-08 to 2018-12.** First signal date the last NYSE trading day of July 2003 (its 12-month lookback reaches the last trading day of July 2002, 2002-07-31, which the vendor file covers); first execution date the first NYSE trading day of August 2003; last holding period ends at the first execution date of January 2019. About 185 monthly holding periods. Instruments: IEF from the vendor series, cash from §5.2, throughout.

### 8.2 Out-of-sample (held back, touched once)

**2019-01-01 to 2026-09-30**, unchanged from Studies 001 and 002 and never touched by either. First signal date the last NYSE trading day of December 2018 (lookback into Alpaca's 2017–2018 bars); last holding period ends at the first execution date of October 2026. About 93 monthly holding periods. Instruments and signal entirely from Alpaca `adjustment='all'` bars for IEF and BIL. Run exactly once by `reproduce.sh --oos` after the in-sample results, data checks and trial log are committed; output to `results/oos/`, never re-run. A bug fix in shared code after the run is an amendment that keeps both outputs.

### 8.3 Why this boundary, and what the author knows about the window

The boundary is inherited; it was fixed on 2026-10-21 before any computation under any study and keeping it means the three studies share one untouched test period. The author states plainly that the window contains the 2022 Treasury sell-off, the largest drawdown in IEF's history and the kind of episode a trend rule exists to side-step, as well as the 2019–2020 rally in which a trend rule would have been long. That is why the window is informative and why O1–O2 are sign conditions: 93 months cannot establish a Sharpe difference of 0.2 at conventional significance, and a single large episode can decide the sign either way.

### 8.4 Forward period

Paper trading from the publication date of the note with results, never backdated (§11).

## 9. Benchmarks, metrics and decision criteria

Unchanged in full from Study 001 §9.1–9.5 and §9.7 and the §16 verdict-precedence clarification there: B0 cash, B1 buy-and-hold IEF, B2 50/50 rebalanced monthly, B3 the constant mix at T1's in-sample IEF fraction w (frozen; the same w out-of-sample); costs 2 bp base and 4 bp stress per side; the twelve metrics; deflated Sharpe at N = 3 and N = 10 with the stated variance floor; C1–C4 in-sample, O1–O2 out-of-sample; verdicts supported / not supported / inconclusive with precedence not supported > inconclusive > supported; a downgrade to inconclusive if T2 or T3 would be "not supported" where T1 is "supported"; a mandatory "What did not work" section. A halt under §5.3.5 is "inconclusive".

Two additions, both descriptive, both fixed now:

**9.6 Pre-registered descriptive sub-analyses (no decision weight, no selection).**
- Sub-periods by the calendar month of the holding period's start: 2003-08 to 2008-12 (hiking cycle and crisis), 2009-01 to 2015-12 (zero lower bound and QE), 2016-01 to 2018-12 (normalisation). Metrics 1–6 for each.
- Mechanism check: months in which T1 held BIL: count, number and mean length of cash episodes, and the realised return of IEF versus cash in those months (the rule can add value only through these months).
- **Power statement.** The number of in-sample switches and the share of months in cash are reported next to the author's prior in §2.4. If T1 switches fewer than 8 times in-sample, the note must label the in-sample test "low-powered" in its first paragraph, because C2 (a Newey–West t of 2.0 on the timing difference) is then close to unreachable whatever the truth. The criteria are not changed by this; the labelling is.
- Time-series plot of `mom_t` with the holding shaded; drawdown of T1 versus B1.

**9.7** (as Study 001 §9.7, "What did not work").

## 10. Known pitfalls and how the design avoids them

The Study 001 table applies where relevant (look-ahead, overlapping returns, multiple testing, distribution handling, out-of-sample contamination, engine bugs). Rows that change or are added:

| Pitfall | Treatment |
|---|---|
| Momentum "found" because the asset drifted up (Huang et al., 2020) | B3 holds the same average IEF exposure with no timing; C1 and C2 are against B3, not only against buy-and-hold. |
| Low power on one asset in a bull market | Disclosed in §2.3 and §2.4; a pre-registered power statement in §9.6 governs how the in-sample result is labelled; the out-of-sample window and forward paper trading carry the weight. |
| Vendor splice | None in-sample (one vendor throughout) and none out-of-sample (Alpaca throughout); the two vendors' agreement over 2016–2018 is on record from Study 002. |
| The only modelled series (cash) could carry an unnamed bias | Ex-ante component estimate (§5.3.3) checked over eleven and a half years of actual BIL, eight and a half of them unseen by the designer; a level gate with a halt; daily tracking reported, not gated, for the reason given in advance. |
| Optional branch could be chosen after seeing numbers | Every branch of §5.3 is written with its trigger before any fetch; branch F is a disclosed weakening, not a choice. |
| Designer's knowledge of 2022 | Disclosed in §8.3; the window was fixed on 2026-10-21 for a different study and is inherited unchanged. |
| Tiingo adjusted closes re-based on each fetch | Return ratios are invariant; the manifest records the hash of the file used; D0 checks coverage. |

## 11. Paper-trading plan (from publication date, never backdated)

As Study 001 §11 (account, 4 500 USD sleeve, IEF and BIL only, position limits, engine stop as a logged supervisory overlay, 20% drawdown halt, data-failure and price-sanity rules, logging layout), with the signal source changed:

- **11.2 Schedule.** On the last NYSE trading day of each month after 17:00 ET: fetch Alpaca daily bars (`adjustment='all'`) for IEF and BIL; confirm the bar for date t is present; compute `mom_t` from the adjusted closes at t and t₁₂ and `target_t`; write a decision record. On the next NYSE trading day between 15:45 and 15:55 ET: if `target_t` differs from the holding, sell the holding, wait for the fill, buy the target with the proceeds (whole shares). If the month-end bar is missing or stale, re-check each NYSE day at 15:30 ET for up to three days, then hold, log "signal unavailable" and alert the owner. No other orders.
- **11.5 Logging.** As Study 001, with the fields `dgs10`, `dtb3`, `bey`, `spread` replaced by `tri_ief_t`, `tri_ief_t12`, `tri_cash_t`, `tri_cash_t12`, `mom`.

## 12. Risk limits for the paper strategy

Unchanged from Study 001 §12 (written 2026-10-21): IEF and BIL only; sleeve 4 500 USD, never more than 5 000 USD in one position; net long, no margin, no derivatives; 20% drawdown halt; 3% one-day loss review; at most one switch per month; order notional within ±2% of target; orders only 15:30–16:00 ET. Independent Risk clearance is recorded as `RISK_CLEARANCE.md` in this folder before the first paper order.

## 13. Repository layout

```
research/003-bond-tsmom-ief/
  README.md            the study note (written only after results; includes "What did not work")
  PREREGISTRATION.md   this document (immutable except §16 amendments)
  trials.md            trial log and data-check log
  APPROVED             approval chain (written at §14 step 3)
  reproduce.sh         --check | --insample | --oos (the --oos flag refuses if results/oos/ exists)
  requirements.txt
  src/                 copied from Study 002 with attribution: backtest.py, stats.py, report.py, fred.py,
                       alpaca_bars.py, tiingo_bars.py, reuse_bars.py, bey.py (bill conversion only);
                       new: config.py (this study's constants), signal.py (T1–T3 from price indices),
                       cash.py (§5.2 accrual index), checks.py (§5.3 D0–D2), calendar.py (month-end
                       NYSE signal dates from the bar index)
  tests/               Study 002's engine and statistics tests; new tests for §5.3.4 (i)–(vi)
  data/raw/            git-ignored
  results/             data_manifest.json, checks/, insample/, oos/ (written exactly once)
  paper-log/           forward record from publication
```

## 14. Order of operations

1. Commit this document and `trials.md` (this commit). No fetch, no check, no return.
2. BIL vendor fetch and overlap check (§5.3.2 steps 1–2), each committed before the next; branch recorded in `trials.md` and §16.
3. Implement `src/` and `tests/`; all tests pass including §5.3.4 (i)–(vi); write `APPROVED`; commit.
4. `reproduce.sh --check` → `results/checks/`: D0, D2 (and the B2 descriptive), **one run**. Proceed or halt (§5.3.5); commit the outputs whatever the outcome.
5. Append run dates for T1–T3 to `trials.md`; commit.
6. `reproduce.sh --insample` → `results/insample/`; commit.
7. In-sample part of README.md, including "What did not work" and the §9.6 power statement; commit.
8. `reproduce.sh --oos` once → `results/oos/`; commit. Verdict per Study 001 §9.5.
9. Finish README.md; publication date = commit date.
10. Independent review (separate agent, did not write the code): `REVIEW.md`.
11. Paper trading from the first month-end after publication, after Independent Risk clearance.

No step may be reordered. Steps 4 and 6 are the only times the author sees any in-sample number before step 8; step 4 shows no rule return.

## 15. Things this study deliberately does not do

No synthetic duration series and no pre-2002 history. No volatility scaling, no leverage, no short positions, no second asset, no lookback other than twelve months (T1, T2) or ten (T3), no threshold other than zero, no combination with the term-spread signal of Studies 001–002, no choice of anything on the out-of-sample window. It does not change the benchmarks, costs, criteria or out-of-sample window inherited from Study 001. It does not claim that a result on one unlevered ETF generalises to the published multi-asset, volatility-scaled strategy.

## 16. Amendments

(Append dated entries here; each must state what changed, why, which results had already been seen at the time, and the trial count N.)

### 2026-10-22: BIL vendor decision (§5.3.2 steps 1–2; §14 step 2): **vendor accepted**

- **What changed:** nothing in the design. This entry records the outcome of the pre-committed procedure.
- **Step 1 (fetch):** Tiingo daily BIL prices fetched 2026-10-22T05:27Z with the desk's existing credential (token read from the environment, sent as a header, never logged; no credential created): 4,881 rows, 2007-05-30 to 2026-10-21, provenance in `results/data_manifest.json`. The series starts before 2007-06-01, so the full cash-check window is available. Committed (521e033) before step 2 ran. Correction to §4: the vendor's first bar is 2007-05-30, so the fund's inception date of 2007-05-25 is not confirmed by this file and stays unverified; nothing depends on it.
- **Step 2 (overlap check, pre-registered pass/fail):** on 753 common return days 2016-01-05 to 2018-12-31, Tiingo `adjClose` returns against Alpaca `adjustment='all'` returns: annualised mean difference vendor − Alpaca **−0.0001% p.a.** (within ±0.05%: pass). Descriptive, no decision weight: correlation 0.9507, tracking error 0.088% p.a., largest daily gap 3.0 bp, no day over 10 bp; by year +0.006%, −0.000%, −0.006%. The correlation is low while the largest gap is three basis points, which is the quantisation effect §5.3.2 described in advance and the reason correlation was not a threshold. Full statistics in `results/checks/bil_vendor_decision.{json,md}`.
- **Consequence:** §5.3.3 (D2, the cash-leg level check) runs over **2007-06-01 to 2018-12-31** on the vendor series. Branch F does not apply.
- **What had been seen when this was written:** BIL returns inside 2016–2018 from both vendors (already seen under Studies 001 and 002 for Alpaca) and the BIL file's row count and first/last dates. No cash-leg series was built, no return before 2016 was read, no rule was run. **N = 3**, unchanged.

### 2026-10-22: data checks D0 and D2 (§5.3.1, §5.3.3; §14 step 4): **both pass, the study proceeds**

- **What changed:** nothing in the design. This entry records the outcome of the single pre-committed run (`reproduce.sh --check`, 07:30:55Z, after the code (987b161), `APPROVED` and the trial-log row (8076ecc) were committed).
- **D0:** the vendor IEF file has a bar on all 4,134 NYSE trading days from 2002-07-31 to 2018-12-31 (longest gap 0 days; first bar 2002-07-26, before the required 2002-07-31). Dates only. Pass.
- **D2:** on 2,916 common return days from 2007-06-04 to 2018-12-31, BIL (vendor adjusted close) minus the §5.2 cash accrual: **B1 = +0.0366% p.a.**, inside the ±0.30% gate and inside the ex-ante band 0.00 ± 0.20. Read against the component table: the observed gap sits next to the +0.03 central estimate before rounding, and its sign by year (+0.26 to +0.32% in 2007–2009 while bill rates fell fast; −0.07 to −0.12% in 2016–2018 while they rose) is the pattern the "portfolio yield lags the spot rate" component described in advance. **B2 (descriptive, no decision weight): tracking error 0.586% p.a.**, above the 0.50% historical reference and twice the 2016–2018 reading of 0.288%; by year 0.90% (2007), 1.56% (2008), 0.68% (2009) and 0.21–0.31% thereafter; largest daily gap 43 bp; daily correlation 0.09. This is the regime effect §2.5 and §5.3.3 anticipated when B2 was made descriptive: a bill fund's daily noise was large in 2007–2009 while its level stayed within a third of a percentage point of the accrual. Had Study 002's rule (a daily tracking-error gate set in a calm window) been carried over, it would have halted this study on daily noise that a monthly rule never inherits; the decision not to carry it over was taken and written before the number was seen, and the number is published either way.
- **Consequence:** §14 step 5 (T1–T3 run dates in `trials.md`), then the in-sample run.
- **What had been seen when this was written:** everything in the D2 table (BIL and cash-accrual returns 2007–2018) and the D0 dates. **No IEF return, no 12-month return, no signal value and no return of any rule or benchmark.** The out-of-sample window is untouched. **N = 3**, unchanged.

### 2026-10-22: in-sample and out-of-sample runs (§14 steps 6 and 8) and the verdict; one disclosure, no change

- **What changed:** nothing in the design, the criteria or the code. This entry records the two runs and one limitation of the inherited statistics found after the out-of-sample run.
- **In-sample** (08:33 London, after the trial-log row 106696e): T1 Sharpe 0.452 against 0.555 (B1) and 0.554 (B3); C1 fail, C2 fail (t = 0.37), C3 pass (0.951), C4 pass; 18 switches, 30.8% of months in cash, power label "as registered". Committed with the in-sample section of the note (7e44a4c) before the out-of-sample run.
- **Out-of-sample** (08:37 London, the single run): T1 Sharpe 0.157 against −0.259 (B1, B3); O1 and O2 hold; daily maximum drawdown −6.5% against −23.9%; t against B3 1.31. **Verdict for T1: not supported** under §9.5 as inherited and the precedence rule of Study 001's §16 (any in-sample criterion failing). `results/oos/` written once.
- **Disclosure (limitation, not a correction):** two of T1's out-of-sample intervals (the stationary-bootstrap Sharpe interval, §9.3 item 8, and the Ledoit–Wolf interval, item 9) are NaN because T1's excess return over B0 is exactly zero in 50 of 93 months (it held the cash benchmark itself) and a resample drawn only from those months has no Sharpe ratio. The point estimates, t-statistics and p-values are unaffected. The published files are untouched; `posthoc_bootstrap_nan.py` reports the intervals with the degenerate resamples dropped (1 and 4 of 10,000) as a descriptive supplement. The shared statistics code is not changed under this study; a successor should fix the definition before running.
- **What had been seen when this was written:** everything in `results/insample/` and `results/oos/`. **N = 3**, unchanged; no further trial will be added.
