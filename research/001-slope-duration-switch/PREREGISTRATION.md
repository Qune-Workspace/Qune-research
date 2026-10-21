# Study 001 — Term-spread duration switch (long-only, 10-year vs bills)

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-10-21 |
| Status | proposed, awaiting approval; **no test run** |
| Version | 1.0 (any change after approval requires a dated amendment appended to §16 before any further test is run) |
| Study type | single pre-registered hypothesis, long-only, monthly, two instruments |
| Instruments requiring approval | **IEF**, **BIL** (see §4) |
| Reviews required | Owner approval before any computation on returns; Independent Risk clearance of §11–§12 before the first paper order |
| Total trial count registered | **3** (primary + 2 robustness variants, §7) |
| Author | the desk (owner approval required before any computation that touches returns) |

Nothing in this document reports or implies the performance of any rule. The author has not computed, plotted or looked at the return of any candidate rule on any data. The only data inspection performed before writing this document was a check of which FRED series exist and over which dates (§5.4), and the orchestrator's confirmation that Alpaca daily bars exist for the candidate ETFs from 2016-01-04.

---

## 1. Question

**Does conditioning a long-only intermediate-duration position on the sign of the 10-year minus 3-month term spread improve risk-adjusted return over an unconditional long position in the same instrument, after realistic costs?**

In plain terms: hold the 7–10-year Treasury ETF when the yield curve is upward-sloping, hold Treasury bills when it is flat or inverted. Is that better than simply holding the 7–10-year ETF?

One question, one primary rule, one in-sample test, one out-of-sample test, then paper trading forward.

## 2. Hypothesis and economic grounding

### 2.1 Primary hypothesis (H1)

H1: Over the in-sample period, the monthly excess return (over bills) of the switching rule in §6 has a higher Sharpe ratio than (a) buy-and-hold of the 10-year leg and (b) a static mix with the same average duration exposure, and the difference is not explained by selection among the registered trials (deflated Sharpe ratio ≥ 0.95, §9).

Null H0: the switch does not improve risk-adjusted return; the slope carries no usable information about the sign of the next month's bond excess return once costs are paid.

### 2.2 Why the edge might exist

1. **Term premium / carry.** When the curve is steep, a long bond earns the yield pick-up over bills plus roll-down, and the expectations hypothesis says future short rates should rise enough to offset this. Empirically they do not rise by enough: the yield spread forecasts bond excess returns with the "wrong" sign relative to the expectations hypothesis (Fama and Bliss, 1987; Campbell and Shiller, 1991). The spread is therefore a (noisy) measure of the compensation on offer for bearing duration risk. Koijen, Moskowitz, Pedersen and Vrugt (2018) show that bond "carry" (slope plus roll-down) predicts returns across countries and that a carry-timed bond position has a positive Sharpe ratio.
2. **Slow-moving risk premium.** The spread moves slowly and is tied to the monetary-policy cycle. Inverted curves coincide with tightening cycles and precede recessions (Estrella and Mishkin, 1998); periods of flat or inverted curves are when the expected excess return on duration is lowest or negative, and historically the bill has been the better long-only holding in those periods according to the cited literature.
3. **Implementation is cheap.** The rule trades at most a handful of times per year in two of the most liquid ETFs in the world, so the gross edge, if it exists, does not need to be large to survive costs.

### 2.3 Why the edge might NOT survive

1. **Secular bull market.** From 1981 to 2020 yields fell almost monotonically. Any rule that is long duration most of the time will look good over that window regardless of skill. The design addresses this by starting the sample in 1962 (including the 1962–1981 rising-rate period), by benchmarking against a static mix with the *same* average exposure (so that only the *timing* contribution is scored), and by reporting excess returns over cash rather than total returns.
2. **Zero lower bound and QE (2009–2015, 2020–2021).** With the short rate pinned at zero the spread is mechanically positive, so the rule is always long; its information content in those years is close to nil and QE compressed the term premium. Sub-period results are pre-registered (§9.6) so this cannot be hidden.
3. **Publication decay and crowding.** The slope result has been public since 1987/1991. McLean and Pontiff (2016) document post-publication decay of published predictors. The out-of-sample period (2019–2026) and the forward paper-trading period both post-date publication by decades, so they are a genuine test of whether anything remains.
4. **Statistical fragility of predictive regressions.** Bauer and Hamilton (2018) show that much of the apparent predictability of bond excess returns from yield-curve variables is a small-sample artefact of persistent regressors (Stambaugh, 1999). This study does not use a predictive regression as its evidence: it uses a *sign rule* fixed in advance, scored on realised portfolio returns with heteroskedasticity-and-autocorrelation-consistent and bootstrap inference, non-overlapping monthly returns, and a held-back out-of-sample period. That sidesteps the Stambaugh bias, at the cost of ignoring the magnitude of the spread.
5. **Low power by construction.** If the spread is positive in roughly four-fifths of months (the author does not know the exact fraction and has not computed it), the rule differs from buy-and-hold in only one month in five. The timing contribution may be real but undetectable in 57 years of monthly data. "Inconclusive" is therefore a live outcome and is defined in advance (§9.5).

### 2.4 Designer's prior knowledge (disclosed)

The author knows, from general market knowledge, the broad shape of rate history including the 2019 inversion, the 2020 cut to zero, the 2022–2023 hiking cycle and bond sell-off, the 2022–2024 inversion, and the 2024–2025 re-steepening. This is unavoidable and is a form of look-ahead at the design stage. Mitigations: (i) the hypothesis and rule are the canonical ones from the 1987/1991 literature, not chosen after inspecting recent data; (ii) the threshold is zero (the only parameter-free choice) and no parameter is tuned; (iii) the out-of-sample boundary was chosen for the structural reasons in §8.3, not to include or exclude a known episode; (iv) the forward paper-trading period is the only test wholly free of this problem and is treated as such.

## 3. Literature (checked against the author's knowledge; web search was unavailable in the authoring environment, so DOIs and page numbers must be verified at implementation and recorded in README.md)

- Fama, E. F. and Bliss, R. R. (1987). "The Information in Long-Maturity Forward Rates." *American Economic Review* 77(4), 680–692.
- Campbell, J. Y. and Shiller, R. J. (1991). "Yield Spreads and Interest Rate Movements: A Bird's Eye View." *Review of Economic Studies* 58(3), 495–514.
- Cochrane, J. H. and Piazzesi, M. (2005). "Bond Risk Premia." *American Economic Review* 95(1), 138–160.
- Koijen, R. S. J., Moskowitz, T. J., Pedersen, L. H. and Vrugt, E. B. (2018). "Carry." *Journal of Financial Economics* 127(2), 197–225.
- Moskowitz, T. J., Ooi, Y. H. and Pedersen, L. H. (2012). "Time Series Momentum." *Journal of Financial Economics* 104(2), 228–250. (Not tested here; cited as the obvious alternative hypothesis for a later study.)
- Asness, C. S., Moskowitz, T. J. and Pedersen, L. H. (2013). "Value and Momentum Everywhere." *Journal of Finance* 68(3), 929–985.
- Brooks, J. and Moskowitz, T. J. (2017). "Yield Curve Premia." Working paper, SSRN.
- Ilmanen, A. (2011). *Expected Returns*. Wiley. Chapters on the bond risk premium.
- Bauer, M. D. and Hamilton, J. D. (2018). "Robust Bond Risk Premia." *Review of Financial Studies* 31(2), 399–448.
- Stambaugh, R. F. (1999). "Predictive Regressions." *Journal of Financial Economics* 54(3), 375–421.
- Welch, I. and Goyal, A. (2008). "A Comprehensive Look at the Empirical Performance of Equity Premium Prediction." *Review of Financial Studies* 21(4), 1455–1508. (Out-of-sample discipline.)
- Estrella, A. and Mishkin, F. S. (1998). "Predicting U.S. Recessions: Financial Variables as Leading Indicators." *Review of Economics and Statistics* 80(1), 45–61.
- McLean, R. D. and Pontiff, J. (2016). "Does Academic Research Destroy Stock Return Predictability?" *Journal of Finance* 71(1), 5–32.
- Harvey, C. R., Liu, Y. and Zhu, H. (2016). "… and the Cross-Section of Expected Returns." *Review of Financial Studies* 29(1), 5–68.
- Bailey, D. H. and López de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality." *Journal of Portfolio Management* 40(5), 94–107.
- Ledoit, O. and Wolf, M. (2008). "Robust Performance Hypothesis Testing with the Sharpe Ratio." *Journal of Empirical Finance* 15(5), 850–859.
- Newey, W. K. and West, K. D. (1987). "A Simple, Positive Semi-definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix." *Econometrica* 55(3), 703–708.
- Politis, D. N. and Romano, J. P. (1994). "The Stationary Bootstrap." *Journal of the American Statistical Association* 89(428), 1303–1313.
- Henriksson, R. D. and Merton, R. C. (1981). "On Market Timing and Investment Performance. II." *Journal of Business* 54(4), 513–533.
- Swinkels, L. (2019). "Treasury Bond Return Data Starting in 1962." *Data* 4(3), 91. (Constructs constant-maturity Treasury total returns from FRED yields; the approximation in §5.2 follows this approach.)
- Board of Governors of the Federal Reserve System. *H.15 Selected Interest Rates*, release notes: "The release is posted daily Monday through Friday at 4:15pm. The release is not posted on holidays or in the event that the Board is closed." (Checked 2026-10-21.)

## 4. Instruments and symbol list requiring approval

| Role | Symbol | Fund | Index | Why this one |
|---|---|---|---|---|
| Duration leg | **IEF** | iShares 7–10 Year Treasury Bond ETF | ICE US Treasury 7–10 Year | Matches the 10-year constant-maturity yield (DGS10), which is the only long-maturity FRED series unbroken since 1962 (DGS20 has a 1987–1993 gap; DGS30 is extrapolated 2002–2006). Intermediate duration keeps drawdowns within the risk limits in §12 without leverage. The 10-year is the maturity used in the carry literature (Koijen et al., 2018). |
| Cash leg and cash benchmark | **BIL** | SPDR Bloomberg 1–3 Month T-Bill ETF | Bloomberg 1–3 Month US Treasury Bill | Closest listed proxy for the 3-month bill (DTB3) used in the signal and the synthetic cash return. |

**Minimal list: IEF, BIL.** No other symbol will be traded. SHV (iShares Short Treasury) is named here only as the designated substitute for BIL if BIL becomes untradable on the paper account; using it would require a separate approval and a dated amendment.

Issuer launch dates (from the author's knowledge; to be verified from issuer documents at implementation, not load-bearing because the study uses Alpaca bars only from 2016-01-04): IEF 2002-07, BIL 2007-05, SHV 2007-01. Expense ratios assumed: IEF 0.15% p.a., BIL 0.1356% p.a. (to be verified and recorded; used only as a drag on the synthetic series, §5.2).

No margin, no shorting, no options, no leverage, no other ETFs.

## 5. Data

### 5.1 Sources (free, no key, no sign-up)

| Series | FRED id | Content | First valid obs | Used for |
|---|---|---|---|---|
| 10-year CMT yield | DGS10 | Treasury constant-maturity par yield, % p.a., bond-equivalent basis | 1962-01-02 | Signal; synthetic 10-year return |
| 3-month bill, secondary market | DTB3 | Discount-basis yield, % p.a. | 1954-01-04 | Signal (after conversion); synthetic cash return |
| 7-year CMT yield | DGS7 | As DGS10 | 1969-07-01 | Variant V2 only (roll-down) |

Endpoint: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>`. Missing values appear as an empty field (the CSV contains a row for every weekday including holidays, with an empty value on holidays). Scripts must treat empty, "." and NaN as missing.

The 3-month short rate is DTB3 converted from discount yield to bond-equivalent yield, following the Federal Reserve Bank of New York's convention for the 10-year minus 3-month spread:

```
d   = DTB3 / 100                      (discount yield, decimal)
bey = 365 * d / (360 - 91 * d)        (bond-equivalent yield, decimal)
```

Using one bill series throughout (rather than splicing DGS3MO, which starts 1981-09-01) avoids a splice and keeps the signal definition identical in 1962 and 2026.

ETF bars: Alpaca Market Data, daily bars, SIP feed, **`adjustment='all'`** (splits and distributions). Distributions are most of the return of a bond ETF; `adjustment='split'` (the default of the existing desk helper) would discard the coupon income and must not be used. Alpaca bars are licensed data and are **not redistributable**: the scripts fetch them into `data/raw/` (git-ignored) and nothing derived from them that reproduces the bars is committed. Only aggregate statistics and the comparison plots in §5.3 are committed. Everything derived from FRED is fully reproducible by anyone.

Daily ETF total return on NYSE trading day t: `r_t = close_adj_t / close_adj_{t-1} − 1` from the `adjustment='all'` series.

Download provenance: every script records the download timestamp (UTC), the URL, the row count and the SHA-256 of each raw file in `results/data_manifest.json`. FRED constant-maturity yields are, in practice, not revised after publication, but the manifest makes any revision detectable. ALFRED vintages are not needed because the signal is a function of the same-day release which is final.

### 5.2 Synthetic constant-maturity total returns (pre-ETF history)

Reproducibility is preferred over fidelity for the in-sample period: the long history cannot be obtained any other way without paid data, and anyone can re-run it from FRED. Fidelity is checked explicitly in §5.3, and the out-of-sample period uses actual ETF returns.

**Synthetic 10-year leg.** On each FRED business day t with a valid DGS10 observation at t and at the previous valid observation s (s < t):

```
y_s   = DGS10_s / 100 ;  y_t = DGS10_t / 100
P_t   = price per 100 of a bond with annual coupon y_s paid semi-annually,
        exactly 10 years to maturity (20 periods), discounted at yield y_t
        with semi-annual compounding:
        P_t = (y_s/2) * 100 * (1 - (1 + y_t/2)^-20) / (y_t/2) + 100 * (1 + y_t/2)^-20
days  = calendar days from s to t
r_t   = (P_t / 100 - 1) + y_s * days / 365 - 0.0015 * days / 365
```

That is: exact repricing of a par bond bought at yield y_s and sold at yield y_t, plus accrued carry at the purchase yield, minus the ETF expense ratio pro rata. The one-day shortening of maturity is ignored (it is of order 1/3650 of a year of roll-down and is far below the approximation error that §5.3 measures). A duration/convexity version (`r ≈ y_s·days/365 − D_mod·Δy + ½·C·Δy²`) is computed as a cross-check and must agree with the exact repricing to within 0.5 bp per day on average; it is not used for results.

**Synthetic cash leg.** On each FRED business day t with valid DTB3 at the previous valid observation s:

```
bey_s = 365 * (DTB3_s/100) / (360 - 91 * (DTB3_s/100))
r_t   = bey_s * days / 365 - 0.001356 * days / 365
```

Both synthetic series are daily; the monthly strategy return is the compounded daily return over the holding period defined in §6.4.

### 5.3 Validation of the synthetic series against actual ETFs (data check, not a performance test)

Window: 2016-01-04 to 2018-12-31 (the ETF-era part of the in-sample period; the out-of-sample window is not touched). Comparison is of **instrument returns only**; no rule is applied.

Daily, on NYSE trading days common to both series (synthetic return compounded across any FRED-only or NYSE-only days so that both series cover the same calendar intervals):

| Check | Statistic | Acceptance threshold |
|---|---|---|
| A1 | Pearson correlation of daily returns, IEF vs synthetic 10-year | ≥ 0.95 |
| A2 | OLS slope of IEF daily return on synthetic 10-year daily return | in [0.80, 1.05] (the 7–10-year index has slightly less duration than a 10-year par bond; this is the ETF-versus-index mismatch and is expected to show as a slope below 1) |
| A3 | Annualised tracking error (std of daily difference × √252) | ≤ 1.5% p.a. |
| A4 | Annualised mean return difference (IEF − synthetic) | within ±0.40% p.a. |
| B1 | Annualised mean return difference (BIL − synthetic cash) | within ±0.30% p.a. |
| B2 | Annualised tracking error, BIL vs synthetic cash | ≤ 0.50% p.a. |

If every threshold is met, the study proceeds as written. If any threshold fails, **the study halts before any rule is tested**, the failure is recorded in README.md, and an amendment (§16) specifying the corrected construction (e.g. a 7-year/10-year blend using DGS7 from 1969) is written and dated before anything else is run. The validation statistics are reported in full whatever the outcome.

### 5.4 Data availability verified on 2026-10-21 (dates only; no returns computed)

| FRED id | Rows | Missing (holidays) | First valid | Last valid | Gaps > 10 days |
|---|---|---|---|---|---|
| DGS10 | 16 905 | 721 | 1962-01-02 | 2026-10-19 | none |
| DTB3 | 18 991 | 801 | 1954-01-04 | 2026-10-19 | none |
| DGS7 | — | — | 1969-07-01 | 2026-10-19 | none |
| DGS5 | 16 905 | 721 | 1962-01-02 | 2026-10-19 | none |
| DGS2 | 13 145 | 553 | 1976-06-01 | 2026-10-19 | none |
| DGS3MO | 11 775 | 493 | 1981-09-01 | 2026-10-19 | none |
| DGS1MO | 6 580 | 274 | 2001-07-31 | 2026-10-19 | none |
| DGS20 | 16 905 | 2 410 | 1962-01-02 | 2026-10-19 | **1986-12-31 to 1993-10-01** |
| DGS30 | 12 960 | 546 | 1977-02-15 | 2026-10-19 | none as published, but 2002-02 to 2006-02 values are Treasury extrapolations |
| DFF | 26 409 | 0 | 1954-07-01 | 2026-10-19 | none |

Publication timing: the H.15 release for day t is posted at 4:15pm ET on day t; FRED's `fredgraph.csv` for DGS10 on 2026-10-21 contained observations through 2026-10-19 (two business days earlier). The study therefore assumes a FRED lag of up to one business day and never acts on a yield before it is visible in the FRED CSV (§6.3).

Alpaca: daily bars for IEF, BIL, IEI, SHY, SHV and TLT confirmed available from 2016-01-04 (orchestrator check). Only IEF and BIL are used.

## 6. Exact rule specification

### 6.1 Signal

On signal date t (defined in §6.3):

```
spread_t = DGS10_t / 100  −  bey_t          (decimal, from the same observation date t)
```

Primary rule (T1): `target_t = IEF if spread_t > 0 else BIL`.

Threshold is exactly zero. There is no smoothing, no lag beyond the publication lag, no hysteresis band and no parameter to tune.

### 6.2 Position sizing

100% of account equity in the target ETF, rounded down to whole shares; the residual (less than one share's value) stays in cash and is ignored in the backtest. Never both ETFs at once except intraday during a switch. No leverage; buying power used must not exceed cash.

### 6.3 Timing and look-ahead control

- **Signal date t** = the last FRED business day of calendar month m on which both DGS10 and DTB3 have a non-missing value. (If the last weekday of the month is a bond-market holiday, t is the previous valid day.)
- **Execution date e** = the first NYSE trading day strictly after t. By then the H.15 release for day t (posted 4:15pm ET on day t, after the 4:00pm ETF close) is public, and FRED has normally ingested it. In the backtest the trade is assumed to fill at the official close of day e. In paper trading the script first confirms that the FRED CSV contains the observation for date t; if it does not, it waits one NYSE day and re-checks, up to three NYSE days (§11.4).
- The position set on e is held until the next execution date. Holding-period return runs from close of e to close of e′ (next execution date).
- No observation dated after t is used in forming `target_t`. Unit test: shifting all yield data forward by one day must change the trade dates by one day and nothing else.

### 6.4 Rebalancing

Monthly, at execution date e only. If `target_t` equals the current holding, no order is sent and no cost is charged. Between execution dates nothing is done; there are no intra-month stops in the backtest (the paper-trading halt in §12 is a supervisory limit, not part of the rule, and its effect is logged separately if ever triggered).

### 6.5 Missing data

- FRED value missing on the planned signal date: use the previous valid observation within the same month (this is already the definition of t).
- Both DGS10 and DTB3 missing for every day of a month (has never happened in the verified data): hold the existing position, log "no signal", count the month as a hold.
- ETF bar missing on an execution date in the out-of-sample or validation data: execute at the next available bar's close and log the slippage of one day; if more than three consecutive bars are missing, the study is halted and the data problem documented.
- Synthetic series: the daily return is defined only between consecutive valid FRED observations, so holidays are handled by the calendar-day accrual term and need no special case.

### 6.6 Pseudo-code (monthly loop)

```
holding = BIL                                   # starting position, first execution date
for each calendar month m in sample:
    t  = last FRED business day in m with valid DGS10 and DTB3
    e  = first NYSE trading day > t
    spread = DGS10[t]/100 - bey(DTB3[t])
    target = IEF if spread > 0 else BIL         # T1
    if target != holding:
        charge cost c (bp) on 100% of equity for the sale and c on the purchase
        holding = target
        trades += 1
    accrue return of holding from close[e] to close[e_next]
```

## 7. Registered trials (N = 3)

Every trial below is logged in `trials.md` before it is run; the deflated Sharpe ratio in §9.4 uses N = 3. Any further rule, parameter or sub-sample choice tested later must be appended to `trials.md` with a date before it is run, and N increases accordingly.

| ID | Name | Difference from T1 | Purpose |
|---|---|---|---|
| T1 | Primary: month-end sign of 10y–3m spread | — | The hypothesis |
| T2 | V1: 21-observation mean of the spread | `spread_t` replaced by the mean of the last 21 valid daily spreads ending on t | Robustness to month-end noise and calendar snooping |
| T3 | V2: carry including roll-down (Koijen et al., 2018) | `carry_t = spread_t + D_mod(DGS10_t) × (DGS10_t − DGS7_t)/3`, with D_mod the modified duration of a 10-year par bond at yield DGS10_t; `target = IEF if carry_t > 0`. Sample starts 1969-07 because DGS7 starts then. | Tests whether adding the roll-down component changes the conclusion |

No other variants will be run. In particular: no threshold other than zero, no other maturities, no momentum overlay, no vol targeting. These are explicitly deferred to future studies with their own pre-registrations.

## 8. Sample split

### 8.1 In-sample

**1962-02-01 to 2018-12-31.** Signal dates from the last FRED business day of January 1962; first execution date the first NYSE trading day of February 1962; last holding period ends at the first execution date of January 2019. Approximately 683 monthly holding periods. Instrument returns: synthetic (§5.2) throughout, including 2016–2018 (where actual ETF returns are used only for the validation in §5.3).

### 8.2 Out-of-sample (held back, touched once)

**2019-01-01 to 2026-09-30.** First signal date the last FRED business day of December 2018 (position effective first NYSE trading day of January 2019); last holding period ends at the first execution date of October 2026. Approximately 93 monthly holding periods. Instrument returns: actual IEF and BIL from Alpaca (`adjustment='all'`) as the primary series; the synthetic series is also run over the same window and reported alongside so that the public can reproduce the out-of-sample result from FRED alone.

The out-of-sample backtest is executed **exactly once**, by `reproduce.sh --oos`, after the in-sample results, validation statistics and trial log are committed. Its output is committed as `results/oos/` and never re-run with any change to the rule. If a bug is later found in shared code, the fix and the re-run are recorded as an amendment with both the old and new output retained.

### 8.3 Why this boundary

- It leaves three full years of ETF-era data (2016–2018) inside the in-sample period for the synthetic-versus-actual validation, which must be done before any rule is tested.
- The out-of-sample window is long enough (~93 months) to contain more than one monetary regime and more than one change of sign in the spread, which is the only kind of period in which a switching rule can be distinguished from buy-and-hold.
- It post-dates the publication of every paper in §3 by at least one year, so it is a fair test of post-publication survival.
- It is a round calendar boundary chosen before any computation; see §2.4 for the disclosure that the author knows the broad history of the period.

### 8.4 Forward period

Paper trading from the publication date of the study note (the date the README.md with results is committed), never backdated (§11). This is the second, fully clean, out-of-sample period.

## 9. Benchmarks, metrics and decision criteria (fixed now)

### 9.1 Benchmarks

| ID | Benchmark | Definition |
|---|---|---|
| B0 | Cash | 100% BIL (synthetic cash pre-2016 in-sample; actual BIL out-of-sample) |
| B1 | Buy-and-hold | 100% IEF (synthetic 10-year in-sample; actual IEF out-of-sample) |
| B2 | Static 50/50 | 50% IEF / 50% BIL, rebalanced to 50/50 at every execution date, same costs |
| B3 | Same-exposure static | w% IEF / (1−w)% BIL rebalanced at every execution date, where w = the fraction of in-sample months in which T1 held IEF. w is a function of the signal only (not of any return), is computed once from in-sample data and frozen; the same w is used out-of-sample. This isolates the timing contribution (Henriksson and Merton, 1981) from the average duration exposure. |

Benchmark costs: B2 and B3 pay the same per-trade cost on the rebalanced notional; B0 and B1 pay no trading cost after the initial purchase.

### 9.2 Costs

Alpaca charges no commission on US ETFs. The round-trip cost of switching is dominated by the bid–ask spread and any slippage versus the close. IEF and BIL typically quote at one cent wide on prices around 90–100 dollars, i.e. roughly 1 bp full spread.

| Case | Cost per trade per ETF (one side) | Cost of one full switch (sell one, buy other) |
|---|---|---|
| Base | **2 bp** of traded notional (≈ half-spread 0.5 bp + 1.5 bp slippage/market impact allowance) | 4 bp |
| Stress | **4 bp** (2×) | 8 bp |

Costs are applied at today's levels across the whole sample, including the pre-ETF era when the strategy could not have been traded this cheaply (or at all, by a retail account). This overstates historical implementability but answers the question actually asked: would the rule be worth trading *now*. The paper-trading log records realised slippage versus the official close so that the base assumption can be audited (§11.5). If the realised 12-month average slippage exceeds the base assumption, the stress case becomes the headline case in any follow-up.

ETF expense ratios are already deducted inside the synthetic series (§5.2) and are embedded in actual ETF returns, so they are not charged again.

### 9.3 Metrics (reported for T1, T2, T3, B0–B3; in-sample and out-of-sample separately; base and stress costs)

All from monthly holding-period returns (non-overlapping). Excess return = strategy return − B0 return in the same holding period.

1. Annualised geometric return.
2. Annualised volatility (monthly std × √12).
3. Sharpe ratio versus cash (annualised mean excess return / annualised std of excess return; also the monthly-unit Sharpe needed for §9.4).
4. Maximum drawdown of the total-return index, from monthly data; also from daily data for the actual-ETF out-of-sample run.
5. Turnover: number of switches per year; fraction of months in IEF.
6. Hit rate: (a) fraction of months in which the instrument held outperformed the instrument not held; (b) fraction of months with positive excess return.
7. Timing difference: mean and Newey–West t-statistic (Bartlett kernel, 6 lags) of the monthly return difference (strategy − B3) and (strategy − B1).
8. Sharpe-difference test versus B1 and B3 using the Ledoit–Wolf (2008) studentised circular block bootstrap (block length 12 months, 10 000 resamples).
9. Stationary bootstrap (Politis and Romano, 1994; expected block length 12 months; 10 000 resamples) 95% confidence interval for the annualised Sharpe ratio.
10. Probabilistic and deflated Sharpe ratio (§9.4).
11. Skewness and excess kurtosis of monthly excess returns (inputs to §9.4).
12. Sub-period descriptives (§9.6).

### 9.4 Deflated Sharpe ratio (Bailey and López de Prado, 2014)

With N = 3 registered trials, T = number of monthly observations, γ₃ = skewness, γ₄ = kurtosis (non-excess) of the trial's monthly excess returns, SR the monthly-unit Sharpe ratio of the trial, and V the variance of the monthly Sharpe ratios across the N trials:

```
SR* = sqrt(V) * ( (1 − γ_E) * Φ⁻¹(1 − 1/N) + γ_E * Φ⁻¹(1 − 1/(N·e)) ),   γ_E = 0.5772…
DSR = Φ( (SR − SR*) * sqrt(T − 1) / sqrt(1 − γ₃·SR + (γ₄ − 1)/4 · SR²) )
```

Reported with N = 3 (registered) and, as a conservative sensitivity acknowledging the implicit trials embodied in choosing a well-known rule from the literature, with N = 10. The decision criterion uses N = 3; the N = 10 value is reported next to it in every table. If V is degenerate because the three trials are nearly identical, the floor V = (0.05/√12)² (i.e. a 0.05 annualised Sharpe spread) is used, and this is stated.

### 9.5 Decision criteria (ex ante)

In-sample, at base costs, for T1:

- C1: Sharpe(T1) ≥ Sharpe(B1) + 0.10 and Sharpe(T1) ≥ Sharpe(B3) + 0.10 (annualised units).
- C2: Newey–West t-statistic of mean(T1 − B3) ≥ 2.0.
- C3: DSR(T1) with N = 3 ≥ 0.95.
- C4: the sign of mean(T1 − B3) is unchanged under stress costs.

Out-of-sample, actual ETF returns, base costs, run once:

- O1: mean(T1 − B3) > 0.
- O2: Sharpe(T1) > Sharpe(B1).

| Verdict | Condition |
|---|---|
| **Supported** | C1–C4 all hold, and O1 and O2 both hold. |
| **Not supported** | Any of C1–C4 fails; or O1 fails with Newey–West t ≤ −1.0; or the out-of-sample maximum drawdown of T1 exceeds that of B1. |
| **Inconclusive** | C1–C4 hold but O1 or O2 fails with the out-of-sample t-statistic of (T1 − B3) in (−1.0, +1.0); or the validation in §5.3 fails and the study halts. |

T2 and T3 do not affect the verdict. They are reported in full. If T1 is "supported" but T2 or T3 would be "not supported" on the same criteria, the note must say so prominently and the verdict is downgraded to "inconclusive" (fragility to a trivial perturbation is evidence of noise).

The out-of-sample period has roughly 93 monthly observations; the study therefore cannot distinguish a true annualised Sharpe improvement of 0.2 from zero at conventional significance. That is why O1–O2 are sign conditions and why "inconclusive" exists. The forward paper-trading record is the arbiter over time.

### 9.6 Pre-registered descriptive sub-analyses (no decision weight; no selection)

- Sub-periods: 1962-02 to 1981-12 (rising rates), 1982-01 to 2008-12 (disinflation), 2009-01 to 2018-12 (zero lower bound and QE). Metrics 1–6 for each.
- Months in which the spread was ≤ 0: count, average length of inverted episodes, and realised return of IEF versus BIL in those months (this is the mechanism check: the rule can only add value through these months).
- Time-series plot of the spread with the holding shaded, and the drawdown of T1 versus B1.

### 9.7 What did not work

The note must contain a section "What did not work" listing every trial, sub-period and cost case where T1, T2 or T3 failed any of C1–C4 or O1–O2, every validation threshold that was near its limit, and any implementation problem encountered. An empty section is not acceptable; at minimum it must state what was weakest.

## 10. Known pitfalls and how the design avoids them

| Pitfall | Treatment |
|---|---|
| Look-ahead in the signal | Signal uses only observations dated ≤ t; H.15 posts at 4:15pm ET after the 4:00pm ETF close; execution is at the close of the next NYSE day; paper trading checks the FRED CSV actually contains date t before trading. Unit test in §6.3. |
| Look-ahead in the design (author's knowledge of recent history) | Disclosed in §2.4; rule and threshold are canonical and untuned; forward paper trading is the clean test. |
| Data revisions | CMT yields are final at release; raw-file hashes and download timestamps are recorded; a revision would show as a hash change. |
| Survivorship | Not applicable: two instruments, both still listed, and the synthetic series does not depend on any fund's survival. |
| Overlapping returns | None: monthly non-overlapping holding periods; inference by Newey–West and block bootstrap anyway. |
| Persistent-regressor bias (Stambaugh; Bauer–Hamilton) | No predictive regression is used for the decision; evidence is realised portfolio returns of a pre-fixed sign rule. |
| Multiple testing | N = 3 registered trials, logged before running; DSR with N = 3 and N = 10; no parameter sweeps; any addition increments N before it runs. |
| ETF versus index mismatch | IEF holds 7–10-year bonds; the synthetic is a 10-year par bond. Quantified by A1–A4 in §5.3 with acceptance thresholds; out-of-sample uses the actual ETF. |
| Distribution handling | `adjustment='all'` mandatory for Alpaca bars (coupons are most of the return). |
| Holiday calendars | Signal dates follow the FRED (bond-market/federal) calendar; execution dates follow the NYSE calendar; the mapping is "first NYSE trading day strictly after t". Synthetic accrual uses calendar days so weekends and holidays earn carry. Validation compounds the synthetic series onto NYSE intervals before comparison. |
| Secular decline in yields | Sample starts in 1962; benchmarks B1 and B3 remove the unconditional duration exposure; excess returns over cash. |
| Zero lower bound | Spread mechanically positive; disclosed; sub-period 2009–2018 reported. |
| Costs understated for the past | Disclosed in §9.2; stress case; realised slippage logged forward. |
| Discount-yield convention | DTB3 converted to bond-equivalent yield with the stated formula before being compared with DGS10 (which is bond-equivalent). |
| Out-of-sample contamination | Run once by a script with a flag; output committed; any re-run is an amendment. |
| Backtest-engine bugs | Unit tests: zero-cost T1 with a signal forced to "always IEF" must equal B1 to machine precision; forced "always BIL" must equal B0; shifting data by one day moves trades by one day. |

## 11. Paper-trading plan (from publication date, never backdated)

### 11.1 Account, instruments and sleeve size

Alpaca paper account (nominally 100 000 USD), margin disabled, IEF and BIL only. The desk's current paper limits (RISK_FRAMEWORK.md) cap any one position at 5 000 USD and 5% of equity, so the strategy runs as a **fixed sleeve of 4 500 USD** (headroom for price drift under the 5 000 USD cap), never topped up. All performance is reported in percentage terms on the sleeve, which is what the backtest measures; the dollar size changes nothing in the rule. Running the rule at 100% of the account would need the owner to loosen the limits and is not requested. The starting position is BIL until the first scheduled execution date after publication.

### 11.2 Schedule

- On the last weekday of each month after 17:00 ET: fetch DGS10 and DTB3 from FRED; if the observation for the intended signal date t is present, compute `spread_t` and `target_t`; write a decision record (§11.5).
- On the first NYSE trading day after t, between 15:45 and 15:55 ET: if `target_t` differs from the current holding, submit a market order to sell the whole holding, wait for the fill, then submit a market order to buy the target with the resulting cash (whole shares, rounding down). Log both fills.
- If FRED does not yet contain date t, re-check each NYSE day at 15:30 ET for up to three NYSE days; on the third failure hold the current position, log "signal unavailable", and alert the owner.
- No other orders at any other time, except the halt in §12.

### 11.3 Position limits

Maximum 100% of the sleeve in one ETF (sleeve ≤ 5 000 USD, within the desk's per-position and concentration caps); no leverage (order notional ≤ available cash); no short positions; at most one sell and one buy per month, except a halt liquidation.

### 11.4 Switch-off conditions

- **Engine stop (required by the desk's risk engine)**: every entry must carry a stop with at most 250 USD at risk. For the sleeve this is a protective stop about 5% below the IEF entry price (BIL's stop is set at the same dollar risk and is, in practice, unreachable). If the IEF stop is hit, the sleeve moves to BIL and waits for the next scheduled signal date. This is a supervisory overlay, not part of the tested rule: every trigger is logged, and its effect on the paper record is computed separately against the no-stop rule. The backtest reports, as a descriptive item with no decision weight, how many holding periods saw IEF fall 5% or more below its entry close.
- **Drawdown halt**: if end-of-day sleeve equity falls more than 20% below its running peak since the start of paper trading, liquidate to BIL at the next session's close, stop trading, and write a halt record. Resumption requires a dated amendment by the owner.
- **Data failure**: FRED unreachable or stale (no new DGS10 observation for 5 consecutive business days) → hold, alert; Alpaca order rejected → retry next session, up to three sessions, then hold and alert.
- **Price sanity**: if the fill price differs from the last quoted mid by more than 0.5%, the next order is not sent until the owner has reviewed the log.
- **Code change**: any change to `src/` after publication is a dated amendment; the paper record before and after is kept separate.

### 11.5 Logging (`paper-log/`)

One JSON record per decision and per order, committed monthly:

```
{ "signal_date", "execution_date", "dgs10", "dtb3", "bey", "spread", "target",
  "holding_before", "orders": [ { "symbol", "side", "qty", "submitted_at",
  "filled_at", "fill_price", "official_close", "slippage_bp" } ],
  "equity_close", "peak_equity", "drawdown", "notes" }
```

plus `paper-log/summary.csv` (one row per month: equity, holding, return, cumulative slippage) and a monthly comparison with the same-dated live B0, B1 and B3 benchmarks computed from the same Alpaca bars. Realised slippage in bp versus the official close is compared with the 2 bp base assumption every twelve months.

## 12. Risk limits for the paper strategy (written 2026-10-21)

1. Instruments: IEF and BIL only.
2. Sleeve of 4 500 USD, never more than 5 000 USD in one position; gross exposure ≤ 100% of the sleeve; the desk-wide limits in RISK_FRAMEWORK.md apply on top and win where tighter; net long only; no margin, no shorting, no derivatives.
3. Single-name concentration: 100% in one Treasury ETF is permitted by design; both legs are US Treasury funds.
4. Maximum drawdown before halt: 20% of peak paper equity (§11.4). For reference, IEF's duration is about 7.5–8 years, so a 20% loss corresponds to roughly a 250 bp parallel rise in 7–10-year yields within a short period; this is a supervisory limit, not a stop within the rule.
5. Daily loss review trigger: a one-day loss of more than 3% of the sleeve triggers a written review in the log (no trade).
6. Turnover cap: at most one switch (sell + buy) per calendar month.
7. Order size: each order notional within ±2% of the intended target; otherwise reject and log.
8. Operational: no orders outside 15:30–16:00 ET; no orders if the previous session's log record is missing.

## 13. Repository layout

```
research/001-slope-duration-switch/
  README.md            the study note (written only after results; includes "What did not work")
  PREREGISTRATION.md   this document (immutable after approval except §16 amendments)
  trials.md            trial log: id, date logged, description, date run, commit hash of the code that ran it
  reproduce.sh         `./reproduce.sh --validate`, `--insample`, `--oos` (the --oos flag refuses to run
                       if results/oos/ already exists)
  requirements.txt     numpy, pandas, matplotlib, statsmodels, requests (pinned versions)
  src/
    fred.py            download + parse FRED CSV; manifest with hash and timestamp; missing-value handling
    alpaca_bars.py     fetch daily bars, adjustment='all', into data/raw/ (never committed)
    bey.py             discount-to-bond-equivalent conversion; duration of a par bond
    synthetic.py       §5.2 synthetic 10-year and cash daily returns (exact repricing + D/C cross-check)
    validate.py        §5.3 statistics A1–A4, B1–B2 and plots
    calendar.py        FRED signal dates → NYSE execution dates
    signal.py          T1, T2, T3 signals
    backtest.py        monthly loop, costs, benchmarks B0–B3
    stats.py           Sharpe, drawdown, Newey–West, Ledoit–Wolf, stationary bootstrap, PSR/DSR
    report.py          tables and figures into results/
    paper_trade.py     §11 schedule, orders, logging (reads a local .env for keys; never committed)
  tests/
    test_lookahead.py  shift test (§6.3); forced-signal tests (§10)
    test_synthetic.py  exact repricing vs duration/convexity; par bond prices at 100
  data/raw/            git-ignored; re-fetched by scripts
  results/
    data_manifest.json, validation/, insample/, oos/   (oos/ written exactly once)
  paper-log/           JSON decision/order records and summary.csv
```

Python stack: numpy, pandas, matplotlib, statsmodels (Newey–West via `statsmodels.stats.sandwich_covariance` or `OLS(...).fit(cov_type='HAC')`), requests. No other dependencies. Random seed for all bootstraps: 20261021.

## 14. Order of operations after approval

1. Owner approves symbol list (IEF, BIL) and this document; approval date recorded at the top of `trials.md`.
2. Implement `src/` and `tests/`; tests pass.
3. `reproduce.sh --validate` → `results/validation/`. Decision: proceed or halt (§5.3).
4. Append T1, T2, T3 to `trials.md` with timestamps; commit.
5. `reproduce.sh --insample` → `results/insample/`; commit.
6. Write the in-sample part of README.md including "What did not work" so far; commit.
7. `reproduce.sh --oos` once → `results/oos/`; commit. Verdict per §9.5.
8. Finish README.md; publication date = commit date.
9. Start paper trading at the first scheduled signal date after publication.

No step may be reordered. Steps 3 and 5 are the only times the author sees any return of any rule before step 7.

## 15. Things this study deliberately does not do

- Does not use the magnitude of the spread, a lagged spread, momentum, or volatility scaling.
- Does not trade TLT, IEI, SHY, SHV, TLH or GOVT.
- Does not fit any regression whose coefficient feeds a trading decision.
- Does not optimise any parameter.
- Does not claim anything about real-money trading; all results are backtests and paper trades.

## 16. Amendments

(Append dated entries here; each must state what changed, why, which results had already been seen at the time, and the new trial count N.)

- **2026-10-21, clarification before approval, no results seen, N unchanged (3).** §9.5 verdict precedence: the "supported" conditions and the "not supported" clause on out-of-sample drawdown can both hold. Precedence is fixed as: **not supported** wins over **inconclusive**, which wins over **supported**. Found while implementing the criteria in code, before any return had been computed.
