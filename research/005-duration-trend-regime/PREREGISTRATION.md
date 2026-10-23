# Study 005 — Trend exits from duration, conditional on the stock-bond correlation regime: does Study 003's 12-month trend exit from IEF add value when the trailing SPY–IEF correlation is positive and cost when it is negative?

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-10-23 |
| Status | pre-registered; **no file fetched for this study, no regime share computed, no return of any rule, benchmark or conditional statistic computed** |
| Version | 1.0 (any change after this commit requires a dated amendment appended to §16 before any further step is run) |
| Study type | fixed income / macro (programme stage 2); one pre-registered conditional hypothesis built from the programme's own finding (`QUESTION.md`); long-only, monthly, two traded instruments, **actual ETF history only**; **no paper order** (§11) |
| Instruments | **IEF**, **BIL** (held in the record); **SPY** as the regime input only, never held, never a return in any table (§4) |
| Approval | The owner approved Study 001's design and symbols on 2026-10-21 and, the same day, delegated all further decisions on this research programme to the orchestrator (workspace decision log). This document is approved by the orchestrator under that delegation on the date of its commit. No Independent Risk clearance is needed because the study places no order (§11). |
| Total trial count registered | **3** (§7): the primary regime variable and two descriptive alternatives |
| Author | the orchestrator (Qune) |
| Governing note | `QUESTION.md` (commit `b9ad02e`, 2026-10-23 08:2x London) fixed the question and three design decisions before this document. Where the two differ, this document governs and §0 says why. |

**Said in the first paragraph, as `QUESTION.md` §2.1 requires: this study cannot deliver a "supported" verdict from history.** The hypothesis was formed from Study 003's result on the programme's shared 2019–2026 out-of-sample window, so that window is the hypothesis-generating episode for this study and carries no decision weight (§8.2). The in-sample window 2003–2018 cannot detect a believable conditional edge (§9.6: minimum detectable effect 4.8–7.3% a year against a believable one to three), so it is a sign and mechanism check that can refute the hypothesis or leave it open, never confirm it (§9.5). The only clean test is the forward record, scored once under the stopping rule of §11, and it is weak too (about 8% a year detectable). The study is written around that honesty: it reuses Study 003's frozen rule and the shared library, adds one regime variable, and spends its effort on a record nobody has seen.

**What the author has seen** of the data this study uses is in §2.4. In one line: every published figure of Studies 003 and 004 (both windows), the desk view's stock-bond correlation proxy over 2017–2026 (an index-and-yield proxy, not the SPY–IEF ETF correlation this study defines), Study 004's SPY vendor-versus-broker statistics over 2016–2018, and nothing of the SPY–IEF correlation or its regime split before 2017.

---

## 0. What this document inherits, what it adds, and one departure from the question note

**Inherited unchanged from Study 003's pre-registration (`research/003-bond-tsmom-ief/PREREGISTRATION.md`, committed `b7f7b63` on 2026-10-22, v1.0 with its §16 entries) and through it from Study 001 (`b6db436`):** the trend signal and its exact arithmetic (003 §6.1: `mom_t` = IEF's 12-month total return minus the cash index's 12-month return at the month-end close, threshold exactly zero), the cash leg from DTB3 in-sample and actual BIL afterwards (003 §5.2, with the D2 cash-leg check that passed on 2007–2018 at +0.0366% p.a. inherited by reference and not re-run), the execution convention (signal at the last NYSE close of the month, trade at the close of the next NYSE day), 100% sizing in whole shares, monthly rebalancing, the cost cases (2 bp base and 4 bp stress per side), the missing-data rule, the twelve metrics (001 §9.3), the deflated Sharpe ratio formula (001 §9.4) with its variance floor, the stationary and circular block bootstrap settings (block 12 months, 10,000 resamples), the Newey–West convention (Bartlett, 6 lags), the in-sample window 2003-08 to 2018-12, the mandatory "What did not work" section, and the amendment rule.

**New here:** the regime variable and the conditional rule (§6), the trials (§7), the role of each window (§8), the quantity on trial and its statistics (§9.2–9.4), decision rows built around the conditional edge with no "supported from history" row (§9.5), the power statement with a slot for the actual regime share (§9.6), the data path for SPY (§5), the engine checks (§5.3.4), the forward record and its stopping rule (§11), and the layout on the shared library (§13).

**One departure from `QUESTION.md`.** §2.3 of the note says the CPI regime (T3) uses "trailing 12-month headline CPI inflation above 3%, using the value published before the signal date with a two-month lag". This document keeps the two-month lag and fixes the series as FRED **CPIAUCNS** (not seasonally adjusted) rather than the seasonally adjusted CPIAUCSL, because the twelve-month change of the unadjusted index is the published headline rate and the series is not revised by annual seasonal-factor updates, so the value used at a signal date is the value that existed then. The note did not name a series; nothing else differs.

## 1. Question

**Does Study 003's trend exit from IEF add value when the trailing stock-bond correlation is positive and cost when it is negative?** Plainly: the 12-month trend rule sells intermediate Treasuries after a bad year. When stocks and bonds have been falling together, that sale manages a risk; when bonds have been hedging stocks, it gives up the hedge. Is the rule's value conditional on which of the two the recent past has been?

## 2. Hypothesis

### 2.1 Statement

Let d_t be the holding-period return of the unconditional trend rule (Study 003's T1, here B2) minus the return of holding IEF (B1) in holding period t, and let the regime of period t be the sign of the trailing SPY–IEF correlation at its signal date (§6.1). The **conditional edge** is

```
Δ = E[d_t | positive regime] − E[d_t | negative regime]
```

- **H1:** Δ > 0, with both halves in the predicted direction: E[d | positive] > 0 (the exit adds value when stocks and bonds move together) and E[d | negative] < 0 (the exit costs when bonds hedge stocks). The conditional rule T1 (§6.2), which applies the trend exit only in the positive regime, therefore earns a higher mean return than B2 after costs.
- **H0:** Δ = 0; the trend rule's value, whatever it is, does not depend on the stock-bond correlation regime; conditioning changes nothing but the number of switches.

### 2.2 Economic grounding

1. **Which shock dominates decides what duration is.** Campbell, Pflueger and Viceira (2020) show that when inflation (supply) shocks dominate, nominal bonds fall with equities and carry a positive beta to the market, so duration is a risk to be managed; when demand shocks dominate, bonds rise as equities fall and duration is a hedge. The trailing stock-bond correlation is the market's own reading of which regime is in force.
2. **A trend exit is a risk-management device, not a return forecast.** In the inflation regime, a year of negative excess returns on IEF has usually come with tightening that persists (Study 003 §2.2), and the exit sidesteps the continuation. In the hedge regime, the same signal fires after a sell-off that is likelier to reverse when equities fall, and the exit forgoes exactly the months in which duration pays.
3. **The regime is long-lived and has reversed.** Ilmanen (2003) documents the positive correlation of the 1970s–1990s and its turn negative around 2000; Brixton, Brooks, Hecht, Ilmanen, Maloney and McQuinn (2023) document the 2022 reversal and tie it to inflation uncertainty. Study 003's two windows sit on opposite sides of that reversal, which is why its in-sample failure and out-of-sample success are both what the mechanism predicts. The desk view of 2026-10-23 reads the current regime as positive.

### 2.3 Why the edge might not be there, or might not be testable

- **The hypothesis was fitted to one episode.** Study 003's out-of-sample advantage is one exit, February 2021 to July 2024. A story that explains one episode is cheap. §8.2 is the answer: that episode is reported under its own label and decides nothing.
- **The in-sample regime may be almost absent.** If the positive regime covers a tenth of 2003–2018, the conditional edge is estimated from about nineteen months and the minimum detectable effect is above 7% a year (§9.6). The in-sample check may say nothing either way; §9.5 pre-commits how that is reported, including the case in which it is not applied at all.
- **The regime variable and the trend signal share an input.** Both are built from IEF's returns. In a bond sell-off that coincides with falling equities the correlation is positive and the 12-month signal is likelier to be negative, so the two will co-move. That is the mechanism, not a flaw, but it means the conditional rule's extra value, if any, comes from a small number of months and the verdict rests on the difference of means with a HAC standard error, not on a Sharpe ratio.
- **The correlation sign is noisy at 63 days.** A three-month window flips sign on noise around zero; no dead band is used, so that nothing can be tuned, and T2 (252 days) shows how much the result depends on the window. The forward record counts positive-regime months, so a noisy variable makes the stopping rule arrive sooner with less information per month.
- **The forward record is weak too.** §11 says by how much. It is nonetheless the only test in which the hypothesis was fixed before the data existed.

### 2.4 Designer's prior knowledge (disclosed)

Of the data this study uses, the author has seen: every file under `research/003-bond-tsmom-ief/results/` (IEF and cash returns, the trend signal, T1–T3 and B0–B3 paths and statistics, both windows, including the monthly returns of B2 and B1 that define d_t for every in-sample and 2019–2026 month, though never split by regime); every file under `research/004-xasset-trend-voltarget/results/` (SPY was excluded from the traded universe there by the D1 gate, so those files hold no SPY signal or weight, but they do report SPY's cumulative return in the crisis-window table and the monthly correlation of the 004 strategies with SPY, in both windows, and SPY's vendor-versus-broker overlap statistics over 2016–2018: mean gap +0.3146% p.a., 14 days over 10 bp, largest daily gap 51 bp); the desk view of 2026-10-23, whose stock-bond correlation proxy (daily S&P 500 index returns against the daily fall in the 10-year constant-maturity yield, 63-day window) was positive on 61% of days since 2022 and 8% in 2017–2021 and stood at +0.41 on 21 October 2026. The proxy is not this study's variable (an index and a yield, not two ETF total-return series) but it is close to it over 2017–2026, so the author expects, before any computation, a mostly negative regime in 2017–2021 and a mostly positive one in 2022–2026. The author has seen **no** SPY–IEF correlation value, no regime flag and no regime split of any return before 2017. From public knowledge the author expects the in-sample positive-regime share to be small (Ilmanen 2003 and Brixton et al. 2023 place 2003–2018 in the negative-correlation era, with episodes around 2005–2007 and 2013 as the candidates for positive readings), and holds the §9.6 prior of 10–30%.

Mitigations: the rule has no parameter (§6); the regime window is the desk view's convention adopted before this study; T1 is named primary now; the in-sample check cannot support; the 2019–2026 episode decides nothing; the forward record is scored by a stopping rule, not by the author.

### 2.5 What Studies 001–004 taught, applied here

- **A test must be able to say no.** The in-sample check has a pre-committed "refuted" row (§9.5) with a magnitude, so the study can fail on history even though it cannot pass on it.
- **A gate must test what the series is used for.** The SPY vendor-versus-broker level gap that excluded SPY from Study 004's traded universe is irrelevant to a correlation sign over 63 days (a 0.31% a year level offset is 0.0012% a day against a daily volatility near 1%); the overlap is therefore carried as a descriptive sign-agreement check (§5.3.2), not a gate, and this is decided now.
- **Pre-commit every branch,** including the one in which the broker's SPY history cannot be fetched (§5.3.3 branch S).
- **Wording is computed, not typed.** Every title and verdict phrase in the note follows from the numbers by rules written in the code, after the chart review of 2026-10-23.
- **Zero corrections.** Nothing is re-derived after a number is seen; a bug fix after a run is an amendment that keeps both outputs.

## 3. Literature

Checked against Crossref by `tools/check_citations.py` on 2026-10-23 (output `citations_check.txt`):

- [CPV20] Campbell, Pflueger, Viceira (2020). Macroeconomic Drivers of Bond and Equity Risks. Journal of Political Economy 128(8):3148–3185. doi:10.1086/707766
- [I03] Ilmanen (2003). Stock-Bond Correlations. The Journal of Fixed Income 13(2):55–66. doi:10.3905/jfi.2003.319353
- [BBHIMM23] Brixton, Brooks, Hecht, Ilmanen, Maloney, McQuinn (2023). A Changing Stock–Bond Correlation: Drivers and Implications. The Journal of Portfolio Management 49(4). doi:10.3905/jpm.2023.1.459

[CPV20] is the mechanism in §2.2; [I03] the regime's history and drivers; [BBHIMM23] the 2022 reversal.

By reference, through Study 003 §3: Moskowitz, Ooi and Pedersen (2012) for the trend rule; Huang, Li, Wang and Zhou (2020) for the drift confound, which is why B3 is kept.

## 4. Instruments

**IEF** and **BIL** as Study 003 §4 (the only instruments held in the record). **SPY** (SPDR S&P 500 ETF Trust, inception 1993-01; expense ratio not needed because SPY is never held) enters only through its daily total return in the regime variable. SPY is not approved for paper trading and does not need to be: this study places no order (§11) and holds no SPY in any table.

## 5. Data

### 5.1 Sources

| Series | Source | Used for | Window |
|---|---|---|---|
| IEF daily adjusted close | Tiingo, the file fetched under Study 002 and reused by Studies 003 and 004, **reused after a SHA-256 check against Study 004's manifest** (6,099 rows from 2002-07-26) | in-sample duration leg, trend signal and regime input | in-sample |
| SPY daily adjusted close | Tiingo, the file fetched under Study 004 §5.3.1, **reused after a SHA-256 check against Study 004's manifest** (6,102 rows, 2002-07-01 to 2026-09-30) | in-sample regime input only | in-sample |
| DTB3 | FRED, the file reused by Study 003 (SHA-256 check) | in-sample cash leg, exactly as Study 003 §5.2 | in-sample |
| IEF, BIL daily bars, `adjustment='all'` | Alpaca, the files fetched under Study 001 and reused by Study 003 (SHA-256 check) | returns and trend signal in the 2019–2026 episode (§8.2), so that B2 reproduces Study 003's T1 path byte for byte | episode |
| SPY daily bars, `adjustment='all'`, 2018-09-01 to 2026-09-30 | Alpaca, **fetched under §5.3.3 step 1 of this study** with the desk's existing credential (no credential created) | regime input in the 2019–2026 episode and the forward record | episode, forward |
| CPIAUCNS | FRED, fetched under §5.3.3 step 2 of this study | trial T3's inflation regime | all windows |

Vendor data are licensed and never committed; `data/raw/` is git-ignored and every file's provenance and SHA-256 go into `results/data_manifest.json` through `qune_research.data`. Daily total return `r_t = adjclose_t / adjclose_{t−1} − 1`.

### 5.2 The cash leg

Study 003 §5.2 unchanged, and its D2 check (B1 = +0.0366% p.a. over 2007–2018, inside ±0.30%) inherited by reference. No new check of the cash leg: nothing about it has changed and re-running a passed gate on seen data would add nothing.

### 5.3 Data checks (one run; no rule applied; order and branches fixed now)

#### 5.3.1 D0: coverage

The Tiingo IEF and SPY files must have a bar on every NYSE trading day from **2003-04-01** to 2018-12-31 (63 trading days before the first signal date of 2003-07-31 fall in late April 2003; the margin is deliberate) with at most three consecutive missing days; IEF's first bar on or before 2002-07-31 (Study 003's D0, already passed). The Alpaca SPY, IEF and BIL files must cover 2018-09-04 to 2026-09-30 the same way (the first episode signal date is 2018-12-31; 63 trading days before it fall in late September 2018). Failure for IEF is a halt ground; failure for SPY in either window makes the regime variable unavailable for that window and is a halt ground for that window's analysis. Neither is expected: Study 004's D0 passed both Tiingo files from their first bar.

#### 5.3.2 D1: regime sign agreement across vendors (descriptive, no gate)

Over 2016-01-04 to 2018-12-31 the 63-day SPY–IEF correlation is computed twice, from Tiingo adjusted closes and from Alpaca `adjustment='all'` bars (Study 004's overlap files), on every trading day of the window: reported are the share of days on which the two signs agree, the mean absolute difference of the two correlations, and the largest difference. **No threshold.** The reason is in §2.5: the SPY level gap that failed Study 004's gate does not bear on a correlation sign, and the author has decided this before seeing the figure. If sign agreement is below 95%, the note must discuss it in its limitations and T1 is still run as written. The agreement rate is also the natural answer to "does it matter that the in-sample regime comes from one vendor and the episode and forward record from another".

#### 5.3.3 Fetches, each committed before the next step runs

1. **Alpaca SPY bars** 2018-09-01 to 2026-09-30, `adjustment='all'`, with the desk's existing credential read from the environment, never logged. Provenance to the manifest. **Branch S** if the fetch fails after two attempts on separate runs: the 2019–2026 episode's regime input is the Tiingo SPY file (which runs to 2026-09-30, the episode's last day) against Alpaca IEF returns; the note says so; the forward record then fetches Alpaca SPY afresh each month-end and the branch is revisited at the first forward signal date. Branch S weakens nothing that carries decision weight (the episode has none) and is written here so it cannot be chosen after a number is seen.
2. **CPIAUCNS** from FRED, full history. If FRED is unreachable on two runs, T3 is logged as "not run: series unavailable" in `trials.md`, N stays 3 (the trial was registered and its slot is kept), and T1 and T2 run.

#### 5.3.4 D3: regime shares and the power statement, filled before any return of a rule is computed

From the files that pass D0, for each in-sample signal date (the last NYSE trading day of each month 2003-07 to 2018-11, 185 dates, matching Study 003's holding periods): the 63-day and 252-day SPY–IEF correlations and the two regime flags (T1, T2), and the T3 inflation flag. Reported: the number and share of positive-regime signal dates, the number of regime changes, the mean and longest regime episode, for each of T1–T3, in-sample; the same for the 2019–2026 episode's 93 signal dates, **labelled as the episode's**. Then the minimum detectable effect of §9.6 is evaluated at the actual counts, with σ_d computed exactly from Study 003's committed `results/insample/monthly_base.csv` (d_t = T1 − B1 there; those numbers are public and already seen) and written into §16 together with the shares. **This step computes correlations of instrument returns and reads a committed file; it computes no return of any rule, benchmark or conditional statistic of this study.** If the in-sample positive-regime count for T1 is below 12, §9.5's in-sample rows are not applied (the check is reported as "not informative") and the study proceeds to the forward record; this is fixed now.

#### 5.3.5 Engine checks (unit tests, run before any data check)

(i) With the regime forced "always positive", T1 equals B2 to machine precision, and B2's in-sample monthly returns equal Study 003's committed `monthly_base.csv` column for T1 to 1e−10 (same files, same engine conventions; a failure here means the port is wrong and nothing runs). With the regime forced "always negative", T1 equals B1. (ii) Shifting every price series forward by one day moves every signal, regime and execution date by one day and changes no target. (iii) Perturbing any SPY or IEF price dated after a signal date leaves that date's correlation, regime and target unchanged (no look-ahead). (iv) On constructed series with a known correlation sign the regime flags are correct, and the count-based window uses exactly 63 (or 252) common return days ending at the signal date, also across a constructed gap. (v) The T3 flag at the signal date of month m reads the CPIAUCNS twelve-month change for month m−2 and no later month. (vi) The B3 weight equals the fraction of in-sample holding periods in which T1 holds IEF. (vii) On constructed d_t and regime flags with known group means, Δ, the Newey–West t and the bootstrap interval match hand-computed values, and the two half-means are reported with the correct signs. (viii) The forward stopping rule fires on the first month at which 24 positive-regime months or 60 months are reached, on constructed sequences, and not before.

#### 5.3.6 Halt rule

If D0 fails for IEF or for in-sample SPY, the study halts before any rule is tested; every statistic is published. A D0 failure for the Alpaca SPY file halts the episode report and leaves the in-sample check and the forward record intact. D1 has no gate. A low regime count under D3 does not halt; it switches off the in-sample verdict rows as §5.3.4 says.

### 5.4 Data availability (verified from the files on disk, dates only)

Tiingo IEF: 6,099 rows, 2002-07-26 to 2026-10-21. Tiingo SPY: 6,102 rows, 2002-07-01 to 2026-09-30 (Study 004's manifest, fetched 2026-10-22). Alpaca IEF and BIL: 2,716 bars each, 2016-01-04 to 2026-10-21. Alpaca SPY: 754 bars, 2016–2018 only (Study 004's overlap fetch); the episode window is fetched under §5.3.3. DTB3: valid to 2026-10-20. CPIAUCNS: not yet fetched.

## 6. Exact rule specification

### 6.1 Regime variable

On signal date t (the last NYSE trading day of calendar month m), let the **regime window** be the 63 most recent trading days on or before t on which both SPY and IEF have a daily total return from the window's vendor (in-sample: Tiingo for both; episode and forward: Alpaca for both). The count is of return days, so a missing bar lengthens the calendar span and never shortens the sample.

```
ρ_t = Pearson correlation of (r_SPY, r_IEF) over those 63 days
R_t = positive if ρ_t > 0 else negative            (T1; threshold exactly zero, no dead band, no smoothing)
```

T2: the same with 252 return days. T3: positive if the CPIAUCNS twelve-month change for month m−2 exceeds 3.0%, else negative. No regime variable has a parameter beyond those three numbers, all fixed here.

### 6.2 Conditional rule

With `mom_t` exactly as Study 003 §6.1 (12-month total return of IEF minus the same for the cash index, at the close of t):

```
unconditional target (B2, Study 003's T1):  IEF if mom_t > 0 else BIL
conditional target (T1):                     (IEF if mom_t > 0 else BIL) if R_t is positive, else IEF
```

In the negative regime the trend signal is ignored and IEF is held. The rule never holds SPY and never shorts.

### 6.3 Timing, sizing, rebalancing, missing data

As Study 003 §6.2–6.5: signal at the close of t, execution at the close of the first NYSE day after t, 100% in the target in whole shares, no order and no cost when the target equals the holding, at most one switch a month, more than three consecutive missing bars halts.

### 6.4 Pseudo-code (monthly loop)

```
holding = BIL
for each calendar month m from 2003-07 (in-sample) or 2018-12 (episode):
    t     = last NYSE trading day of m
    mom   = TRI_IEF[t]/TRI_IEF[t12] − TRI_cash[t]/TRI_cash[t12]
    rho   = corr(r_SPY, r_IEF) over the 63 return days ending at t
    trend = IEF if mom > 0 else BIL                  # B2
    target = trend if rho > 0 else IEF               # T1
    e     = first NYSE trading day > t
    if target != holding: charge c on the sale and c on the purchase; holding = target
    accrue the return of holding from close[e] to close[e_next]
    d[m]  = return(trend path) − return(IEF) over the same holding period
```

## 7. Registered trials (N = 3)

| ID | Name | Regime variable | Purpose |
|---|---|---|---|
| T1 | Primary: 63-day correlation sign | ρ over 63 return days, as §6.1 | The hypothesis, with the desk view's window adopted before this study |
| T2 | 252-day correlation sign | ρ over 252 return days | How much the result depends on the window: slower, fewer regime changes |
| T3 | Inflation regime | CPIAUCNS twelve-month change for month m−2 above 3.0% | The mechanism's cause in place of its symptom, as [CPV20] would have it |

All three run on the same holding periods and the same trend signal. T2 and T3 are descriptive: they do not change any verdict row and are reported in full. The deflated Sharpe ratio for T1 is reported at N = 3 and N = 10 as the programme requires but carries no decision weight in this study (§9.5). No other window, threshold, dead band, smoothing or combination will be run. Any addition is appended to `trials.md` with a date before it runs and N increases.

## 8. Sample split and the role of each window

### 8.1 In-sample: 2003-08 to 2018-12 (sign and mechanism check)

Study 003's in-sample window, 185 holding periods, first signal date 2003-07-31, first execution date the first NYSE day of August 2003, last period ending at the first execution date of January 2019. Instruments and cash leg as Study 003. The author has seen the unconditional rule's result here (it lost) and nothing about the regime split. The window is used for the check in §9.5 within the limits of §9.6.

### 8.2 The 2019–2026 window: the hypothesis-generating episode, not a test

2019-01-01 to 2026-09-30, 93 holding periods, the programme's shared out-of-sample window. Study 003 touched it once and the author saw the result; this study's hypothesis came from that result. Under the programme's rule it cannot be a test for this hypothesis, and **the stock-bond-regime hypothesis on IEF has spent the programme's 2019–2026 window: no later study may use it as a test of this hypothesis family either.** The window is nonetheless run exactly once under this study, after the in-sample results are committed, and reported in full with the same tables, in a section headed "Hypothesis-generating episode (no decision weight)", so that the reader sees the episode the question came from and how much of it is one exit. No number from it enters any verdict row.

### 8.3 Forward record (the test)

From the first month-end after the note's publication date, as §11. Never backdated.

## 9. Benchmarks, metrics and decision criteria

### 9.1 Benchmarks

| ID | Definition | Why |
|---|---|---|
| B0 | Cash (the cash index in-sample, BIL afterwards) | Excess returns and Sharpe ratios |
| B1 | Hold IEF throughout | What the conditional rule reverts to in the negative regime |
| B2 | The unconditional trend rule, Study 003's T1, same engine | The thing being conditioned; its in-sample and 2019–2026 paths are known to the author |
| B3 | Constant mix of IEF and cash at T1's in-sample IEF fraction w, frozen, the same w in every window | Removes the long bias, as Huang et al. (2020) require |

### 9.2 The quantity on trial

d_t = r(B2)_t − r(B1)_t per holding period, at base costs (B2's switching costs included, B1's none; the stress case also reported). The regime of period t is R at its signal date. Reported: n_pos, n_neg, mean(d | positive), mean(d | negative), Δ = the difference, the share of months in which B2 held bills within each regime, and IEF's mean excess return over cash within each regime (the mechanism's raw material).

### 9.3 Statistics on Δ

1. **Newey–West t-statistic** of Δ from the regression d_t = a + Δ·1[R_t positive] + ε_t with a Bartlett kernel and 6 lags, the programme's convention.
2. **Stationary-bootstrap 95% interval** for Δ (Politis and Romano; expected block length 12 months; 10,000 resamples; seed 2005 fixed here), resampling the (d_t, R_t) pairs jointly so that regime persistence is kept.
3. The same two for each half-mean.

### 9.4 Metrics for T1–T3, B0–B3

The twelve metrics of Study 001 §9.3 for every strategy and benchmark, both cost cases, each window separately, plus: the number of regime changes and the mean regime episode length; T1's switches against B2's; the mean and Newey–West t of (T1 − B2) and (T1 − B3); T1's deflated Sharpe ratio at N = 3 and N = 10, reported, no decision weight.

### 9.5 Decision rows

**In-sample (2003-08 to 2018-12), T1, base costs; applied only if n_pos ≥ 12 under D3, otherwise the check is "not informative" and no row applies.** Let [L, U] be the bootstrap interval for Δ in percent per month; the smallest believable edge is 1% a year, 0.083% per month.

| Row | Condition | Reading |
|---|---|---|
| **Refuted in-sample** | U < 0.083 | The in-sample data exclude even the smallest believable conditional edge. The study stops at the note; the forward record is still kept, labelled "refuted in-sample". |
| **Sign consistent, forward record decides** | Δ̂ > 0, mean(d \| positive) > 0 and mean(d \| negative) < 0 | Both halves of the mechanism have the predicted sign. Not a confirmation (§9.6); the row's title says what it is. |
| **Inconclusive, forward record decides** | Anything else | Including Δ̂ > 0 with a half-mean of the wrong sign, and Δ̂ ≤ 0 with U ≥ 0.083. |

There is **no "supported" row**. The verdict table of Studies 001–004 (supported / not supported / inconclusive) is replaced by the three rows above for the in-sample check and by the forward table in §11.4; the precedence is refuted > inconclusive > sign consistent. If T1 is "sign consistent" and T2 is "refuted" on the same rows, the note must say so in its first paragraph.

**The 2019–2026 episode** has no row (§8.2).

### 9.6 Power statement (written now, completed under D3)

σ_d at registration, from Study 003's published in-sample figures (not a new computation): IEF's annualised volatility 6.27%, so its monthly excess return has a standard deviation near 1.8%; B2 was in bills in 30.8% of months; d_t is zero when B2 holds IEF and equals minus IEF's excess return otherwise, so σ_d ≈ 1.8% × √0.308 ≈ 1.0% per month. The exact σ_d from the committed 003 file replaces this under D3.

Minimum detectable effect at a one-sided 5% level with 80% power over 185 months, MDE = (1.645 + 0.842) × σ_d × √(1/n_pos + 1/n_neg):

| Positive-regime share | n_pos | MDE per month | MDE a year |
|---|---|---|---|
| 10% | 19 | 0.61% | 7.3% |
| 20% | 37 | 0.46% | 5.5% |
| 30% | 56 | 0.40% | 4.8% |
| **actual (D3)** | — | — | — |

A believable conditional edge is one to three percent a year. The in-sample window cannot detect it at any plausible share, which is why §9.5 has no supporting row and why the note's first paragraph must carry the actual MDE.

### 9.7 Pre-registered descriptive sub-analyses (no decision weight)

- d_t by regime and by Study 003's three sub-periods (2003-08 to 2008-12, 2009-01 to 2015-12, 2016-01 to 2018-12).
- The list of positive-regime episodes in-sample with their dates, lengths, B2's holding in them and IEF's excess return in them.
- The same tables for T2 and T3.
- Charts through `qune_research/style.py`: ρ_t with the positive regime shaded and B2's bill months marked; growth of one unit of T1, B1 and B2 by window; d_t by regime. Titles computed from the numbers.

### 9.8 "What did not work"

Mandatory, as Study 001 §9.7.

## 10. Known pitfalls and how the design avoids them

| Pitfall | Treatment |
|---|---|
| Post-hoc story confirmed on the data that suggested it | §8.2: the 2019–2026 window has no decision weight and is spent for this hypothesis family. |
| A check too weak to fail | §9.5 has a refuted row with a magnitude; §5.3.4 switches the rows off when the regime count is too small to mean anything, and says so. |
| Look-ahead in the regime variable | Count-based trailing window ending at t; tests (ii)–(iii); the CPI value lags two months. |
| Vendor mismatch between windows | One vendor per window for both legs of the correlation; D1 sign-agreement reported; the level gap argued irrelevant in advance (§2.5). |
| Regime and signal share IEF's returns | Disclosed in §2.3; the verdict rests on the difference of means with a HAC standard error, not on a Sharpe ratio. |
| Selection among windows and thresholds | T1 named primary now; 63 is the desk view's prior convention; 252 and 3% are round numbers fixed without computation; nothing else is run. |
| Choosing when to score the forward record | §11.3 stopping rule fixed now; interim figures labelled. |
| Tiingo adjusted closes re-based on each fetch | Files reused by hash from Studies 003 and 004; return ratios are invariant. |
| Owner's or author's knowledge of 2022 | Disclosed in §2.4 and §8.2; it is the reason the window is not a test. |

## 11. Forward record (no paper order)

This study **places no paper order**: a conditional rule whose only clean test is still to come earns no sleeve, and the programme's paper record belongs to Study 003's pre-registered rule. SPY is not approved for trading and is never held. Promotion to any order would need an explicit owner decision and Independent Risk clearance; none is asked for.

- **11.1 Decision record.** On the last NYSE trading day of each month from the first month-end after the note's publication, after the close: fetch Alpaca `adjustment='all'` daily bars for SPY, IEF and BIL; confirm the bar for t is present; compute ρ_t (63 and 252 days), the T3 flag from the latest CPIAUCNS, `mom_t`, the unconditional target (B2) and the conditional target (T1); write `paper-log/decisions/<signal_date>.json` with every input value, the file hashes and the UTC time written. Never rewritten.
- **11.2 Monthly line** appended to `paper-log/shadow.csv` after each execution date: the holding-period return of B1, B2 and T1 from the same closes, d_t, and the regime flags. Interim statistics (n_pos, Δ̂ so far) are published in the folder README under the heading **"Not yet scored"** and never in a verdict sentence.
- **11.3 Stopping rule.** The record is **scored once**, at the first month-end at which **either 24 positive-regime months (T1's variable) have accumulated or 60 holding periods have passed**, whichever is first. The purpose is to stop the author choosing when to score; the rule buys no power: at 24 positive and 36 negative months the §9.6 formula gives about 0.65% per month, roughly 8% a year, and at 24 positive and fewer negative months more. The scoring date is written in the decision record of the month in which the rule fires, before the statistics are computed.
- **11.4 Forward verdict**, on Δ̂ from the forward d_t with the §9.3 statistics (Newey–West t at 6 lags; bootstrap interval, seed 2005):

| Row | Condition |
|---|---|
| **Supported (forward)** | Δ̂ > 0, Newey–West t ≥ 2.0, and both half-means have the predicted sign |
| **Refuted (forward)** | U < 0.083% per month, or Newey–West t ≤ −2.0 |
| **Inconclusive (forward)** | Anything else; the note says that 60 months were not enough and records what effect size they could have detected |

A "supported" forward verdict after a "refuted in-sample" check is reported as both, in that order, with the conflict named; the forward record does not overrule history by precedence, it is reported beside it.

- **11.5 What is published every month:** the decision record, the shadow line, the interim figures under their label, and nothing else. Nothing is backdated; a missed month-end is logged as missed.

## 12. Risk limits

None are needed: no order is placed. The Study 003 paper sleeve and its limits are untouched by this study.

## 13. Repository layout

```
research/005-duration-trend-regime/
  QUESTION.md          step 0: the question and design decisions (committed b9ad02e)
  PREREGISTRATION.md   this document (immutable except §16 amendments)
  trials.md            trial log and data-check log
  citations_check.txt  Crossref check output
  APPROVED             approval chain (written at §14 step 2)
  reproduce.sh         --check | --insample | --episode | --forward (the --insample and --episode
                       flags refuse if their results folder exists)
  requirements.txt     pins, as Study 004
  src/                 imports qune_research (data, nyse, dates, engine, stats, datacheck, style);
                       trend_signal.py copied from Study 003's src/signal.py with attribution, frozen;
                       cash.py copied from Study 003's src/cash.py with attribution, frozen;
                       new: config.py, regime.py (§6.1, three variables), conditional.py (§6.2),
                       edge.py (§9.2–9.3), checks.py (§5.3), report.py, forward.py (§11)
  tests/               §5.3.5 (i)–(viii) and the regime, edge and stopping-rule unit tests
  data/raw/            git-ignored; results/data_manifest.json records every file
  results/             checks/, insample/ (written once), episode/ (written once)
  paper-log/           decisions/, shadow.csv, README.md (interim figures, "Not yet scored")
```

## 14. Order of operations

1. Commit this document and `trials.md` (this commit). No fetch, no check, no return.
2. Implement `src/` and `tests/`; all tests pass including §5.3.5 (i)–(viii) (test (i) needs the raw files on disk and skips in CI); write `APPROVED`; add the study to the CI matrix; commit.
3. Fetches (§5.3.3 steps 1–2), each logged in `trials.md` before it runs and committed after; branch recorded.
4. `reproduce.sh --check` once → `results/checks/`: D0, D1, D3. Append the §16 entry with the regime shares and the actual MDE, and whether §9.5's in-sample rows apply. Commit.
5. Append the run row for T1–T3 to `trials.md`; commit.
6. `reproduce.sh --insample` once → `results/insample/`; commit.
7. In-sample part of `README.md` with the §9.5 row, the power statement and "What did not work"; commit.
8. `reproduce.sh --episode` once → `results/episode/`, under its label; commit.
9. Finish `README.md`; publication date = commit date; root README "Latest result" and index.
10. Independent review (separate agent, did not write the code): `REVIEW.md`.
11. Forward record from the first month-end after step 9 (§11); if step 9 lands before 2026-10-30, the first decision record is 2026-10-30.

No step may be reordered. Step 4 shows regime shares and correlation statistics; step 6 is the first time any return of a rule or any conditional statistic of this study is seen.

## 15. Things this study deliberately does not do

No dead band, smoothing or alternative threshold on the correlation; no window other than 63 and 252 days; no CPI threshold other than 3%; no SPY position; no volatility scaling, leverage or short; no change to the trend signal, cash leg, costs, timing or metrics inherited from Study 003; no paper order; no test on the 2019–2026 window; no use of the 2019–2026 window as a test of this hypothesis family by any later study; no "supported" verdict from history.

## 16. Amendments

(Append dated entries here; each must state what changed, why, which results had already been seen at the time, and the trial count N.)

**2026-10-23 (§14 step 2, first part; no fetch, no data check, no regime share, no return of this study computed; N = 3).** Layout notes recorded before any run, none changing a rule, a number or a step:
1. `src/` carries five frozen copies of Study 003 modules, not two: `trend_signal.py` (003 `signal.py`), `cash.py`, `bey.py`, `switching.py` (003 `backtest.py`, the two-instrument monthly engine) and `schedule.py` (003 `calendar.py`). The engine and schedule are copied so that §5.3.5 (i) holds exactly rather than approximately: the test reproduces Study 003's committed in-sample `monthly_base.csv` (T1, B0, B1, B3 columns and the signal values) to 1e−10 from the hash-checked files, and it passed on this machine (observed). `pipeline.py` wires them; `data.py` holds the loaders.
2. Precedence in the forward table (§11.4) when a result meets both the supported and the refuted condition (possible: Δ̂ > 0 with t ≥ 2.0 and an interval whose upper bound is still below 0.083% a month): the refuted row is tested first, as in §9.5, and the note names the conflict. Fixed in `forward.py` before any forward month exists.
3. The §9.6 table's rows were evaluated at the unrounded share × 185 (18.5, 37, 55.5 months); at the integer count of 19 months the 10% row reads 7.2%, not 7.3%. The formula is unchanged; D3 fills the actual row from the actual counts.
4. The 2016–2018 broker SPY file reused from Study 004 for D1 is kept in `data/raw/overlap/` and recorded in the manifest under `overlap/alpaca_SPY_1Day_all.csv`, so it cannot collide with the episode fetch of the same symbol (§5.3.3 step 1).
Results seen at the time of writing: none of this study's. `APPROVED` is not yet written: it follows the second part of step 2 (`report.py`, `reproduce.sh`), so that the refusal gate protects every computation that touches a return.

**2026-10-23 (§14 step 2, second part; no fetch, no data check, no regime share, no return of this study computed; N = 3).** Layout notes recorded before any run, none changing a rule, a number or a step:
1. A descriptive trial (T2, T3) runs on the holding periods on which its regime variable is defined, which can start later than T1's: the 252-day window and the lagged CPI change need history that the broker's SPY file, fetched from 2018-09-01 (§5.3.3 step 1), does not reach for the first episode months, and the in-sample CPI flag needs the series back to 2002. Each trial's tables name its own first period and its own month count; its edge is computed on its own months. T1 must be defined on every period of a window, else the run stops (§5.3.6). `d_t` is one series per window (B2 − B1 does not depend on the regime). Fixed in `report.py`.
2. The §9.5 row is computed for T2 and T3 as well as T1 at base costs and reported as descriptive, so that the sentence §9.5 requires when T1 and T2 disagree can be written from the file; the stress case carries no row. The episode's summary carries no row and says so.
3. The deflated Sharpe ratio's variance across trials (§9.4, no decision weight) is taken over the trials that ran; if T3 is "not run: series unavailable" (§5.3.3 step 2) the variance is over two trials, which the file records.
4. The §9.7 charts are drawn from the committed results files by a separate `charts.py` after the results are committed (as Studies 001, 002 and the desk view do it), not by `report.py`, so that every published number exists in a results file before any picture of it. The chart commit changes no result file.
5. `reproduce.sh --forward` exists in the script's usage (§13) and refuses until §14 step 11 adds the decision record, before the first forward month-end.
Results seen at the time of writing: none of this study's. `APPROVED` is written in this commit, after `reproduce.sh --check` had refused without it (exit 1, observed).
