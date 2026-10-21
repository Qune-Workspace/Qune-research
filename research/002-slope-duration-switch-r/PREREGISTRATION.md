# Study 002 — Term-spread duration switch, re-tested with a roll-down-aware synthetic series (IEF vs BIL)

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-10-21 |
| Status | pre-registered; **no validation run, no return of any rule or benchmark computed** |
| Version | 1.0 (any change after this commit requires a dated amendment appended to §16 before any further step is run) |
| Study type | successor to [Study 001](../001-slope-duration-switch/README.md): the same single pre-registered hypothesis, long-only, monthly, two instruments; corrected instrument construction |
| Instruments | **IEF**, **BIL** (approved by the owner for paper trading on 2026-10-21 under Study 001; the approval is for the symbols and is carried over, §4) |
| Approval | Study 001's design was approved by the owner on 2026-10-21. On the same day the owner delegated all further decisions on this research programme to the orchestrator. This document is therefore approved by the orchestrator under that delegation, on the date of its commit, and the delegation is recorded in the workspace decision log. Independent Risk clearance of §11–§12 is still required before the first paper order. |
| Total trial count registered | **3**, carried over from Study 001 (same three trials, which were registered there and never run; §7) |
| Author | the orchestrator (Qune) |

Nothing in this document reports or implies the performance of any rule. **What the author has seen** (and the only thing seen beyond what is public in Study 001): the §5.3 validation statistics of Study 001 for both of its constructions (A1–A4, B1–B2), the validation figure, and the year-by-year mean gap between IEF and the Study 001 synthetic series over 2016–2018 (+0.47%, +0.50% and +0.38% p.a.). No return of T1, T2, T3 or any benchmark has been computed on any data, by anyone, under either study. The out-of-sample window (2019-01 to 2026-09) has never been touched.

---

## 0. Relationship to Study 001

Study 001 halted permanently at its pre-registered data check (§5.3 there): the synthetic constant-maturity bond series used for the pre-ETF history earned about 0.45% p.a. less than the actual ETF over 2016–2018, twice, under two constructions, against a ±0.40% allowance. No rule was ever tested. The halt note's reading of the failure (inferred, not tested) was that the construction held maturity constant and therefore omitted roll-down, which its own text had called negligible. The halt note said a successor needs "an instrument construction whose expected bias against the ETF is written down before validation, with thresholds set around it". This document is that successor.

**Everything not restated here is inherited unchanged from Study 001's pre-registration at commit `b6db436`**: the question (§1), hypothesis and economic grounding (§2.1–2.3), literature (§3, verified against Crossref on 2026-10-21), instruments (§4), FRED sources and the bill conversion (§5.1), the synthetic cash leg (§5.2, cash), the exact rule, sizing, timing, rebalancing and missing-data handling (§6), the registered trials (§7), the out-of-sample window (§8.2), benchmarks, costs, metrics, deflated Sharpe ratio, decision criteria and verdict precedence (§9 and the §16 clarification), the pitfalls table (§10), the paper-trading plan and the risk limits (§11–§12, sleeve of 4 500 USD). The reader should open that document for those sections; they are not paraphrased here so that nothing drifts.

**What changes** (and nothing else):

1. §5.2 duration leg: a single 8.5-year par bond that **ages and is repriced on a curve interpolated between DGS7 and DGS10**, so that roll-down is inside the instrument (§5.2 below).
2. §5.3: an **ex-ante bias estimate per component**, written before any comparison, and fidelity thresholds derived from it by a stated rule (§5.3 below). One validation attempt; failure = permanent halt, no correction allowed.
3. §5.3: a **second validation window, 2003–2015**, from a second price source, conditional only on the data being obtainable, with the decision to include or exclude it committed before any validation runs (§5.3.4).
4. §8.1: in-sample from **1969-08** (first month with DGS7), as Study 001's §16 decision already fixed.
5. §7: trial count carried over (N = 3), with the reasoning stated.
6. §2.4: the designer's disclosed knowledge now includes Study 001's validation statistics.

## 1. Question

Unchanged: **does conditioning a long-only intermediate-duration position on the sign of the 10-year minus 3-month term spread improve risk-adjusted return over an unconditional long position in the same instrument, after realistic costs?** Hold IEF when the curve is upward-sloping, BIL when it is flat or inverted; is that better than holding IEF?

## 2. Hypothesis

H1, H0, the economic grounding and the reasons the edge might not survive are unchanged (Study 001 §2.1–2.3).

### 2.4 Designer's prior knowledge (disclosed; extends Study 001 §2.4)

In addition to the general knowledge of rate history disclosed in Study 001, the author now knows:

- Study 001's validation statistics for both constructions. In particular, that a 7/10-year par-bond blend without roll-down tracked IEF with correlation 0.970, slope 0.946 and tracking error 1.145% p.a., and under-earned it by 0.451% p.a. over 2016–2018, with year gaps of +0.47%, +0.50% and +0.38%.
- Consequently, that the roll-down estimate in §5.3 (0.37% p.a. over the same window, computed from yields) accounts for most of that gap, and that the construction below is **expected** to pass the level check A4 on the 2016–2018 window. The author states this plainly: **A4 on window 1 is a weak test in this study**, because the designer has seen what it needs to explain. It is kept because the construction must still clear it, and because the year-by-year pattern is informative (the roll-down estimate is 0.53%, 0.44% and 0.15% in 2016, 2017 and 2018, while the observed gaps were 0.47%, 0.50% and 0.38%: the term explains the average well and the 2018 figure poorly, which is why §5.3.2 keeps a non-zero allowance for unnamed effects rather than claiming the gap is fully understood).
- The strong test is therefore **window 2 (2003–2015)**, which the author has never seen under any construction, where the 7–10-year curve slope averaged 40 bp against 14 bp in window 1, so the roll-down term the construction must get right is about 1.0% p.a. rather than 0.37%. If the construction is wrong, window 2 is where it will show. If window 2 cannot be obtained (§5.3.4), this study's validation is weaker than Study 001's was, and the note must say so.

Mitigations unchanged from Study 001: canonical rule, zero threshold, nothing tuned, out-of-sample boundary fixed before any computation, forward paper trading as the only fully clean test.

### 2.5 What Study 001 taught, applied here

- A synthetic series must carry a written estimate of its bias against the traded instrument before it is checked, and the threshold must be set around that estimate by a stated rule. Done in §5.3.
- A term that is "negligible per day" can be large per year if it never changes sign. Roll-down is now inside the construction.
- One correction after seeing a comparison is one too many if the failure is not understood. This study allows **zero** corrections: the construction is final at this commit and the validation runs once.
- The same quantity should not be treated as a signal in one place and as noise in another. Trial T3 uses roll-down as a signal; the instrument now earns it.

## 3. Literature

Unchanged (Study 001 §3 and its verification table). The construction in §5.2 is the standard constant-maturity total-return construction: buy the par bond, hold it for one period, reprice it with its shortened maturity off the interpolated par curve, add the coupon accrual (Swinkels, 2019, uses the same ingredients at monthly frequency; the roll-down and carry decomposition is the one in Koijen, Moskowitz, Pedersen and Vrugt, 2018).

## 4. Instruments

Unchanged: IEF (duration leg) and BIL (cash leg and cash benchmark), approved by the owner on 2026-10-21. Verified on 2026-10-21 from a secondary source (stockanalysis.com; the issuer's page refuses automated readers): IEF expense ratio **0.15%**, inception **2002-07-22**, index ICE US Treasury 7–10 Year (market-value weighted, 7–10 years remaining maturity). BIL's expense ratio of 0.1356% is taken from Study 001 and not re-verified; it enters only the cash leg, which passed its checks in Study 001 by a wide margin and is unchanged here.

## 5. Data

### 5.1 Sources

Unchanged: DGS10, DTB3 and DGS7 from FRED (DGS7 is now core, not variant-only); Alpaca daily bars with `adjustment='all'` for IEF and BIL from 2016-01-04 (licensed, never committed). One addition, used only for validation window 2 (§5.3.4): daily IEF closes adjusted for splits and distributions from a second vendor, from 2002-07-22, fetched into `data/raw/` and never committed; provenance (vendor, URL, timestamp, rows, SHA-256) in `results/data_manifest.json`.

### 5.2 Synthetic duration leg: an 8.5-year par bond that ages (replaces Study 001 §5.2, duration leg)

On each FRED business day t with valid DGS7 and DGS10 at t and at the previous valid observation s (s < t):

```
y7_s, y10_s, y7_t, y10_t   = DGS7_s/100, DGS10_s/100, DGS7_t/100, DGS10_t/100
days  = calendar days from s to t
dt    = days / 365
n     = 8.5                                      (years to maturity at purchase)
m_s   = 2 n = 17                                 (semi-annual periods at purchase)
m_t   = 2 (n − dt)                               (periods remaining at t; not an integer)

y_s   = y7_s + (y10_s − y7_s) × (n − 7) / 3      = (y7_s + y10_s) / 2      (interpolated par yield at 8.5 years)
y_t   = y7_t + (y10_t − y7_t) × (n − dt − 7) / 3                            (interpolated par yield at 8.5 − dt years)

P(c, y, m) = 100 × [ (c / y) × (1 − (1 + y/2)^−m) + (1 + y/2)^−m ]         (price per 100 of a bond with annual
                                                                              coupon c paid semi-annually, m periods
                                                                              to maturity, yield y; at y = 0 the
                                                                              first term is 100 × c × m / 2)
P_s   = P(y_s, y_s, m_s) = 100                                               (bought at par)
P_t   = P(y_s, y_t, m_t)                                                     (same bond, shorter, repriced)

r_t   = (P_t / 100 − 1) + y_s × dt − 0.0015 × dt
```

That is: a bond bought at par at the interpolated 8.5-year yield, sold one observation later with its maturity shortened by the elapsed time, repriced at the interpolated par yield **for that shortened maturity**, plus coupon accrual at the purchase yield, minus the ETF expense ratio pro rata. The daily reset (a fresh 8.5-year bond every observation) is the constant-maturity convention. The price formula is the standard annuity formula extended to a non-integer number of periods; it is exact for integer m, equals 100 whenever c = y for any m (so the purchase price is exactly par and roll-down enters only through y_t), and for dt of a few days differs from a day-count-precise price by an amount far below the 0.5 bp cross-check tolerance.

Why 8.5 years and why these two series: the index holds bonds with 7 to 10 years remaining, so a bond at the midpoint of that range is the natural single-instrument proxy, and 8.5 ± dt lies inside the 7–10 segment on every day, so the interpolation never extrapolates and needs no third series (DGS5 is not used). At the window-1 mean yield the 8.5-year par bond has a modified duration of 7.69 years, which is within 0.03 years of the 7/10-year blend that gave slope 0.946 in Study 001, so the slope and tracking checks are expected to behave as they did there. Why linear interpolation: the 7–10-year segment of the par curve is short and nearly straight; the error of a chord against a mildly concave curve at the midpoint is second order, and §5.3.2 charges 15% of the roll-down term for it.

**Cross-check (as in Study 001):** the duration/convexity approximation `r ≈ y_s·dt − D_mod·Δy + ½·C·Δy² − 0.0015·dt` with `Δy = y_t − y_s` and D_mod, C of the 17-period par bond at y_s must agree with the exact r_t to within 0.5 bp per day on average over any window used; it is not used for results.

**Unit tests the implementation must pass before validation:** (i) P(c, c, m) = 100 for m in {17, 16.99, 16.5, 1}; (ii) P(c, y, 17) equals Study 001's integer-period par-bond price; (iii) on a flat curve (DGS7 = DGS10 constant) r_t equals carry minus fee, so there is no roll-down; (iv) on a constant upward-sloping curve (yields unchanged over time) r_t exceeds carry minus fee by approximately D_mod × (y10 − y7)/3 × dt (roll-down); (v) shifting all yields forward by one day moves every return date by one day and changes nothing else.

**Synthetic cash leg:** unchanged from Study 001 §5.2 (DTB3 converted to bond-equivalent yield, accrued over calendar days, minus BIL's expense ratio).

### 5.3 Validation: ex-ante bias estimate, threshold rule, and two windows (data check, not a performance test)

#### 5.3.1 Ex-ante bias estimate per component

All figures are for **IEF minus synthetic**, % p.a., estimated **from yields and public fund facts only** before any comparison. The yield-based quantities are produced by `exante_bias.py` in this folder from the FRED files; its output on 2026-10-21 is reproduced in §5.3.5. "Range" is the author's honest bound on each component, not a fitted number.

| # | Component | Window 1 (2016-01-04 to 2018-12-31) | Window 2 (2003-01-02 to 2015-12-31) | Reasoning |
|---|---|---|---|---|
| 1 | Roll-down omitted by the construction | **0** (it is inside the construction) | 0 | The roll-down the construction earns is 0.373% p.a. (W1) and 1.002% p.a. (W2) by D_mod × (DGS10 − DGS7)/3 averaged daily. What remains is the error of that term: component 2. |
| 2 | Interpolation and maturity-profile error in the roll-down term | 0 ± 0.06 | 0 ± 0.15 | Linear interpolation on a mildly concave segment, and an index whose market-value-weighted maturity is not exactly 8.5 years. Charged at **15% of the roll-down term** (0.37% → 0.06; 1.00% → 0.15). |
| 3 | Duration mismatch | **+0.07** ± 0.03 | **−0.05** ± 0.03 | Study 001's slope of 0.946 for a 7.66-year blend implies an ETF duration about 0.4 years shorter than the synthetic. A shorter instrument loses less when yields rise: 0.40 × (+16.4 bp/yr) = +0.066% in W1; yields fell 12.8 bp/yr in W2, giving −0.051%. |
| 4 | Expense ratio | 0 ± 0.01 | 0 ± 0.01 | 0.15% p.a. deducted inside the synthetic series; verified 2026-10-21 (§4). Historical ratio may have differed slightly. |
| 5 | Securities-lending income | **+0.02** (0 to +0.05) | +0.02 (0 to +0.05) | Treasury funds lend; income is small. Issuer figure not obtained (page blocks automated readers); general-knowledge estimate. |
| 6 | Off-par coupons of seasoned index bonds | 0 ± 0.05 | 0 ± 0.08 | Index bonds carry coupons from issuance, so their duration and yield differ slightly from a par bond of the same maturity. In W2 the bucket held 4–5% coupons against 2–3% yields (premium bonds, lower duration), so the range is wider. Sign unknown. |
| 7 | Fund tracking beyond the fee (cash drag, sampling, internal transaction costs) | **−0.03** ± 0.03 | −0.03 ± 0.03 | Typical for a large Treasury index fund. |
| 8 | ETF close versus NAV at the window ends (premium/discount) | 0 ± 0.05 | 0 ± 0.02 | A 15 bp premium or discount at either end moves a 3-year mean by 0.05% p.a.; over 13 years the same moves it by 0.01–0.02%. |
| 9 | Daily reset of the synthetic versus the index's monthly rebalancing | 0 ± 0.03 | 0 ± 0.03 | Convention difference; small, sign unknown. |
| | **Central estimate** (sum of signed terms) | **+0.06 → +0.05** | **−0.06 → −0.05** | Rounded to 0.05. |
| | **Sum of absolute ranges** | 0.29 → **0.30** | 0.38 → **0.40** | Rounded up to 0.05. |

#### 5.3.2 Threshold rule

The level threshold (A4) is **the central estimate ± the sum of the absolute ranges**, rounded as above. The band is the sum, not the root-sum-square, because the question the check asks is "is there a term the construction does not name?", and a halt should happen only when the gap exceeds what every named component could produce together, in the same direction. That is the question Study 001's construction failed. The rule is written here so that it cannot be re-derived after the comparison.

The other thresholds are **unchanged from Study 001**, because they test tracking rather than level, they were met there by the 7/10 blend whose duration this construction matches, and changing them would be tuning.

#### 5.3.3 Window 1 (required): 2016-01-04 to 2018-12-31, IEF from Alpaca, `adjustment='all'`

Daily, on NYSE trading days common to both series, synthetic returns compounded onto NYSE intervals as in Study 001 §5.3. Instrument returns only; no rule applied.

| Check | Statistic | Threshold | Origin |
|---|---|---|---|
| A1 | Pearson correlation of daily returns, IEF vs synthetic | ≥ 0.95 | unchanged |
| A2 | OLS slope of IEF daily return on synthetic | in [0.80, 1.05] | unchanged |
| A3 | Annualised tracking error (std of daily difference × √252) | ≤ 1.5% p.a. | unchanged |
| **A4** | Annualised mean return difference, IEF − synthetic | **in [−0.25%, +0.35%] p.a.** (centre +0.05, half-width 0.30) | §5.3.1–5.3.2 |
| B1 | Annualised mean difference, BIL − synthetic cash | within ±0.30% p.a. | unchanged |
| B2 | Annualised tracking error, BIL vs synthetic cash | ≤ 0.50% p.a. | unchanged |
| D1 (descriptive, no halt) | Mean difference IEF − synthetic in each calendar year 2016, 2017, 2018 | reported against the year's roll-down estimate (0.53%, 0.44%, 0.15%) | new; no decision weight because a single year's mean is dominated by premium/discount noise at its ends |

#### 5.3.4 Window 2 (conditional on data; decision committed before any validation runs): 2003-01-02 to 2015-12-31

IEF daily closes adjusted for splits and distributions from a second vendor. The desk already holds credentials for Tiingo, which it used in October 2026 for 1994–2015 ETF history; Stooq was checked on 2026-10-21 and serves its CSV only behind a browser challenge, so it is not usable. No new account or credential will be created (hard line).

Procedure, in this order, each step committed before the next:

1. **Before `reproduce.sh --validate` is run on any window**, fetch the vendor series for IEF (and, for the overlap check, nothing else). Record provenance in the manifest. If the fetch fails or the series does not start by 2003-01-02, record the attempt and its error in `trials.md` and §16; window 2 is then **excluded for unavailability** and this is the only ground on which it may be excluded. The decision is committed before any comparison on any window.
2. **Overlap check (data check, not a threshold on the construction):** over 2016-01-04 to 2018-12-31 the vendor's daily returns are compared with Alpaca's `adjustment='all'` returns. Acceptance: correlation ≥ 0.999 and annualised mean difference within ±0.05% p.a. If this fails, the vendor's distribution adjustment is not trusted, window 2 is excluded for data quality, and the statistics are published. This check uses only IEF returns the author has already seen (Study 001's window) and no synthetic series.
3. If the vendor series is accepted, window 2 is checked with **the same statistics A1–A3** at the same thresholds and **A4 in [−0.45%, +0.35%] p.a.** (centre −0.05, half-width 0.40, §5.3.1). The cash leg is not checked on window 2 (BIL starts 2007-05 and its checks are unchanged from Study 001).

Window 2 is the stronger test (§2.4): the roll-down term it must get right is about 1.0% p.a., nearly three times window 1's, and the author has seen no ETF return from those years under any construction.

#### 5.3.5 Halt rule

**If any threshold in §5.3.3 fails, or any threshold in §5.3.4 step 3 fails when window 2 is included, the study halts permanently before any rule is tested.** No correction of the construction is allowed under this study; a further successor would need a new number and a new pre-registration. All statistics are published whatever the outcome, with the ex-ante estimate next to the observed value so that the reader can see which component was wrong.

Output of `exante_bias.py` on the FRED files downloaded 2026-10-21 (DGS7 and DGS10; yields only):

```
W1 2016-01-04..2018-12-31  (749 obs, 3.0 years)
  mean yields: 7y 2.214%  10y 2.359%  8.5y 2.286%
  10y-7y spread: mean 14.4 bp, min 2, max 28, share negative 0.000
  8.5y par bond: mean D_mod 7.69 years
  roll-down estimate (D_mod x spread/3, daily, averaged): 0.373% p.a.
  8.5y yield change: 2.15% -> 2.64%, i.e. +16.4 bp per year
  duration-mismatch term for a 0.40-year shorter instrument: +0.066% p.a.
    2016: spread 20.3 bp, roll-down 0.533% p.a.
    2017: spread 17.1 bp, roll-down 0.438% p.a.
    2018: spread 5.9 bp, roll-down 0.147% p.a.

W2 2003-01-02..2015-12-31  (3254 obs, 13.0 years)
  mean yields: 7y 2.967%  10y 3.366%  8.5y 3.166%
  10y-7y spread: mean 40.0 bp, min -2, max 82, share negative 0.004
  8.5y par bond: mean D_mod 7.41 years
  roll-down estimate (D_mod x spread/3, daily, averaged): 1.002% p.a.
  8.5y yield change: 3.85% -> 2.18%, i.e. -12.8 bp per year
  duration-mismatch term for a 0.40-year shorter instrument: -0.051% p.a.

IS 1969-07-01..2018-12-31  (12364 obs, 49.5 years)
  mean yields: 7y 6.255%  10y 6.413%  8.5y 6.334%
  10y-7y spread: mean 15.8 bp, min -52, max 82, share negative 0.210
  8.5y par bond: mean D_mod 6.57 years
  roll-down estimate (D_mod x spread/3, daily, averaged): 0.383% p.a.
  8.5y yield change: 6.81% -> 2.64%, i.e. -8.4 bp per year
```

The in-sample line is descriptive: over 1969–2018 the 7–10-year segment was inverted on 21% of days, so the roll-down term the construction adds is negative in those months. That is the correct behaviour of a constant-maturity series and is not a bias.

### 5.4 Data availability

As Study 001 §5.4 (FRED series, dates only, verified 2026-10-21), plus: IEF Alpaca bars 2016-01-04 to 2026-10-21 already fetched under Study 001 (manifest there); the window-2 vendor series is fetched under §5.3.4 step 1 and its first and last dates recorded then.

## 6. Exact rule specification

Unchanged (Study 001 §6: signal `DGS10/100 − bey(DTB3)` on the last FRED business day of the month, threshold zero, IEF if positive else BIL, executed at the close of the first NYSE trading day strictly after the signal date, 100% of equity, monthly, no stops in the backtest).

## 7. Registered trials (N = 3, carried over)

The same three trials as Study 001 §7, with the same definitions: T1 (month-end sign of the spread), T2 (21-observation mean of the spread), T3 (carry including roll-down, `spread + D_mod(DGS10) × (DGS10 − DGS7)/3`). They are logged in `trials.md` with their original registration date (2026-10-21, under Study 001) and are run, if at all, only under this study.

Why N stays at 3 rather than 6: a trial counts when a return of the rule is computed and seen. None was. Study 001's two validation runs computed instrument returns only, under constructions that are not reused here, and the designer saw no rule return. The deflated Sharpe ratio is reported at N = 3 (decision) and N = 10 (sensitivity) exactly as in Study 001 §9.4, and the note must state that the N = 10 figure also covers the implicit search over the instrument construction (three constructions across the two studies).

No other variants will be run. Any addition is appended to `trials.md` with a date before it runs and N increases.

## 8. Sample split

### 8.1 In-sample

**1969-08 to 2018-12** (first signal date the last FRED business day of July 1969, the first month with DGS7; last holding period ends at the first execution date of January 2019). About 593 monthly holding periods. Synthetic instruments (§5.2) throughout, including 2016–2018, where actual ETF returns are used only for validation window 1. The §9.6 sub-periods are those fixed by Study 001's §16 decision: 1969-08 to 1981-12, 1982-01 to 2008-12, 2009-01 to 2018-12.

### 8.2 Out-of-sample (held back, touched once)

Unchanged: **2019-01-01 to 2026-09-30**, actual IEF and BIL from Alpaca as the primary series, synthetic alongside; run exactly once by `reproduce.sh --oos` after the in-sample results, validation statistics and trial log are committed; output committed to `results/oos/` and never re-run. It has never been touched under either study.

### 8.3 Forward period

Paper trading from the publication date of this study's note with results, never backdated (Study 001 §8.4, §11).

## 9. Benchmarks, metrics and decision criteria

Unchanged in full (Study 001 §9.1–9.7 and the §16 verdict-precedence clarification): benchmarks B0–B3 with B3's weight frozen from in-sample signals; costs 2 bp base and 4 bp stress per side; the twelve metrics; deflated Sharpe at N = 3 and N = 10; criteria C1–C4 in-sample and O1–O2 out-of-sample; verdicts "supported", "not supported", "inconclusive" with precedence not supported > inconclusive > supported; a mandatory "What did not work" section. A halt at validation is "inconclusive".

## 10. Known pitfalls

The Study 001 table applies. Three rows change or are added:

| Pitfall | Treatment |
|---|---|
| ETF versus synthetic mismatch (level) | The bias is estimated per component before the check (§5.3.1); the threshold follows from the estimate by a stated rule (§5.3.2); the construction is final at this commit. |
| Designer has seen the window-1 comparison under earlier constructions | Disclosed (§2.4); window 1's A4 is called a weak test in advance; window 2 (never seen) is the strong test; forward paper trading remains the clean test. |
| Optional second window could be dropped if it looked risky | It can be excluded only for unavailability or a failed overlap check, by a step committed before any validation statistic exists (§5.3.4). |

## 11–12. Paper-trading plan and risk limits

Unchanged from Study 001 §11–§12 (fixed sleeve of 4 500 USD on the Alpaca paper account, IEF and BIL only, monthly schedule, engine stop, 20% drawdown halt, logging). Independent Risk clearance of these sections is required before the first paper order and is recorded as `RISK_CLEARANCE.md` in this folder.

## 13. Repository layout

As Study 001 §13 under `research/002-slope-duration-switch-r/`, with: `exante_bias.py` (this document's §5.3 numbers, yields only); `src/` reused from Study 001 by copy with attribution in the commit, with `synthetic.py` replaced by the §5.2 construction and `config.py` carrying this study's thresholds and windows; `tests/` extended with the §5.2 unit tests; `results/validation/window1/` and `results/validation/window2/`.

## 14. Order of operations

1. Commit this document and `trials.md` (this commit). No validation, no return.
2. Window-2 data decision (§5.3.4 steps 1–2): fetch, overlap check, decision recorded in `trials.md` and §16; commit.
3. Implement `src/` and `tests/`; all tests pass, including the five §5.2 tests; commit.
4. `reproduce.sh --validate` → `results/validation/`; **one run**. Proceed or halt (§5.3.5); commit the outputs whatever the outcome.
5. Append run dates for T1–T3 to `trials.md`; commit.
6. `reproduce.sh --insample` → `results/insample/`; commit.
7. In-sample part of README.md including "What did not work"; commit.
8. `reproduce.sh --oos` once → `results/oos/`; commit. Verdict per §9.5.
9. Finish README.md; publication date = commit date.
10. Independent review (separate agent) of this study together with the Study 001 halt; `REVIEW.md`.
11. Paper trading from the first scheduled signal date after publication, after Independent Risk clearance.

No step may be reordered. Steps 4 and 6 are the only times the author sees any return before step 8.

## 15. Things this study deliberately does not do

As Study 001 §15, plus: it does not change the signal, the threshold, the benchmarks, the costs, the criteria or the out-of-sample window to accommodate the new construction; it does not use a published index history (not freely available); it does not use DGS5 or DGS20; it does not allow any correction to the construction after validation.

## 16. Amendments

(Append dated entries here; each must state what changed, why, which results had already been seen at the time, and the trial count N.)
