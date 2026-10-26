# Study 010: question choice and design constraints (step 0, before the pre-registration)

*Qune, 2026-10-26 (the commit's time is the record; London = UTC). Committed before `PREREGISTRATION.md` exists, before any file of the Kenneth French Data Library is downloaded, and before any factor return is read on any window. This is the question the agenda's power-first decision of 2026-10-26 06:2xZ fixed on the French US history ([`RESEARCH_AGENDA.md`](../../RESEARCH_AGENDA.md), dated addition; [`tools/power_offduration.txt`](../../tools/power_offduration.txt), commit `9707d55`). That addition required a question note that "names the source paper and its rule, the family count, the in-sample and post-sample rows and their power, and the vintage plan, written before any return is read". This note does those five things. Where it and the later pre-registration differ, the pre-registration governs and must say why.*

## 1. The question, the source paper and its rule

**Decision: time-series factor momentum on the source paper's US factors that the library publishes from before 1963.** The question:

> **Does holding each US equity factor long after a year in which it rose, and short after a year in which it fell, earn more than holding the same average position in each factor throughout, on 1927–2026?**

**Source paper.** Ehsani and Linnainmaa, "Factor Momentum and the Momentum Factor", NBER Working Paper 25551, February 2019, doi:10.3386/w25551, read 2026-10-26 from the NBER PDF (SHA-256 `00af3d63…fdd3` of the copy read; text extracted locally, not committed). What it says (reported, quoted from that copy):

- The factors: 15 US and 7 global; "The 15 anomalies that use U.S. data are accruals, betting against beta, cash-flow to price, investment, earnings to price, book-to-market, liquidity, long-term reversals, net share issues, quality minus junk, profitability, residual variance, market value of equity, short-term reversals, and momentum"; the strategies "trade the 20 non-momentum factors listed in Table 1" (Table A2's caption), so the momentum factor is not traded, and the market factor is not in the list.
- The rule: "The time-series factor momentum strategy is long factors with positive returns over the prior one-year period (winners) and short factors with negative returns (losers)"; the formation period is the "prior one-year period"; the paper's equation (1), for its cross-sectional decomposition, gives as an example "from month t − 12 to month t − 1", and this note takes that window for the time-series rule too (no skipped month: inferred from that example, not stated for the rule); "We rebalance all strategies monthly"; factors are equal-weighted.
- The sample: for the US factors, "the return data for these factors begin in July 1963" (liquidity January 1968); the strategy tables run from July 1964 to December 2015 ("T = 618"; "the 52-year sample period").
- The result: "The time-series factor momentum strategy earns an annualized return of 4.2% (t-value = 7.04)" across up to 20 factors, July 1964 to December 2015; in the same Table 3 the equal-weighted portfolio of those factors earns 4.21% (t 7.60), so the 4.2% is reported beside that benchmark, not as an excess over it. It is a long-short return, not a timing difference against an exposure-matched benchmark, so it is not comparable with the detectable edges in §2.3.
- "Because time-series losers earn premiums that are close to zero, the choice of being long or short a factor following periods of negative returns is inconsequential from the viewpoint of average returns."

The published version (Journal of Finance, 2022) was not read: it is behind the publisher's paywall. If its rule or sample differs from the working paper's, the pre-registration says so; the working paper is the source of record here because it is the text read.

**Primary rule T1.** Factors: the four of the paper's non-momentum US factors that the library publishes from before 1963: size (SMB) and book-to-market (HML) from July 1926, short-term reversal (ST_Rev) from February 1926 and long-term reversal (LT_Rev) from January 1931 (detail pages, read 2026-10-26 06:1xZ and 07:20Z; dates only). As in the paper, a factor joins the equal-weight average when its first 12-month formation return exists: three factors from 1927-07, four from 1932-01. The library builds each factor from 2 × 3 value-weight sorts; the paper, for factors whose returns are not published, uses "the average return on the three top deciles minus that on the three bottom deciles", so the reversal factors here may differ in construction from the paper's (it does not say which source it used for them); disclosed, not adjusted. For each factor k and month t, the formation return R_k,t is the compounded return of k over months t − 12 to t − 1; the position is h_k,t = +1 if R_k,t > 0 and −1 otherwise; the rule's return is the equal-weight average of h_k,t × f_k,t. The decision difference is

  d_t = (1/K_t) Σ_k (h_k,t − h̄_k) f_k,t,

where the sum and K_t run over the factors available in month t (three to 1931-12, four from 1932-01; two in T1a) and h̄_k is the mean of h_k over that factor's months in the decision window, computed from signals only (the convention of Study 007's B3: the benchmark holds the rule's own average position). Because h is ±1, d for the paper's long-short form is exactly twice d for a long-or-flat form (h ∈ {0, 1}), so the two give the same t and Sharpe ratio: being flat instead of short after a losing year does not move this test. (The paper's "inconsequential" remark is about a different choice, long or short after a losing year; being long after every year makes h constant and d zero.) The rule's own return and the paper's comparison (against holding every factor long, h = +1) are reported beside d, with no decision weight.

**Not in the set, and why.** The momentum factor (Mom): the paper does not trade it (its claim is that factor momentum explains it). The market factor (Mkt-RF): it is not one of the paper's factors, and trend on the US market over a century is a question [HOP17] already reports on a sample overlapping this one. The paper's other ten US factors: none reaches back to the 1920s. Two could be built from decile portfolios the library publishes from the 1950s (earnings to price from July 1951, per its detail page, read by the separate-session reviewer today; cash flow to price probably similar, not checked), as the paper builds unpublished factors ("the average return on the three top deciles minus that on the three bottom deciles"); the rest start in 1963 or later or are not in the library. They are left out, decided now before any return: the reason for this sample is its length to the 1920s, a factor joining in the 1950s would change the pool mid-history on a construction this note would have to choose, and both are value measures close to HML (inferred). A departure from the paper, disclosed. A note on the agenda's wording: the power decision named the 3-factor and momentum files (F3, F2); because the paper does not trade momentum, the sample here is the 3-factor file (from July 1926) and the two reversal files (ST_Rev from February 1926; LT_Rev from January 1931, joining 54 months after the start, as the paper adds factors when they start). ST_Rev could start its holding months in 1927-02; the common start is 1927-07, when SMB and HML can. No return of any of them has been read.

## 2. Trials, family count and power

### 2.1 Registered trials (N = 3)

Each companion moves a choice that changes the position path on the decision window (the lesson of Study 007's companions, kept from Study 008):

| ID | Rule | Why registered |
|---|---|---|
| T1 | SMB, HML, ST_Rev, LT_Rev; 12-month formation (t − 12 to t − 1); monthly | the question, as the paper defines it |
| T1a | SMB and HML only (the 3-factor file the power decision named) | fragility companion: the factor set. The reversal factors are themselves built from past stock returns (1 month; 13 to 60 months), so a result carried by them alone would be a narrower claim (inferred) |
| T1b | the four factors, 6-month formation (t − 6 to t − 1) | fragility companion: the formation window, the paper's one free parameter. Its Table A2 (20 non-momentum factors, one-month holding) reports 0.33, t 6.44, at 6 months against 0.36, t 6.77, at 12 (reported, read today; the paper's sample, not this one; the caption says "annualized average returns", but the magnitudes and the text's "basis points per month" suggest percent a month: inferred) |

"Supported in history" for T1 needs T1a and T1b not "not supported" on the same criteria (006's fragility rule, kept).

### 2.2 Family count

This is a new family for the programme: no earlier study timed an equity factor or used this library. **N = 3**, used for criterion C3 (deflated Sharpe ratio ≥ 0.95). Because the sample was chosen after ten earlier studies on other questions, the programme-wide trial count, re-counted from every `research/*/trials.md` immediately before the history run, is reported beside it with the deflated Sharpe ratio at that count; it has no decision weight, and the note says so before any result.

### 2.3 Power of each row ([`tools/power_study010.py`](../../tools/power_study010.py), output [`tools/power_study010.txt`](../../tools/power_study010.txt))

Arithmetic on month counts only, the method of `power_offduration.txt` (K = 2.842 for a Newey–West t ≥ 2.0 at 80% power; nw = 1.00 and 1.108, the largest ratio observed in the programme, not a bound). First holding month 1927-07, when SMB and HML have their first 12-month formation; last month August 2026 per the library's detail page (the data step fixes it from the snapshot).

| Row | Months | Holding periods | Detectable Sharpe(d) | vs the 006–008 pool's 0.321 | Status |
|---|---|---|---|---|---|
| H, full history | 1927-07 to 2026-08 | 1,190 | 0.285 / 0.316 | 0.89× / 0.99× | **the decision row**; 630 of its months are in the paper's data window |
| P1, before the paper's data | 1927-07 to 1963-06 | 432 | 0.474 / 0.525 | 1.48× / 1.63× | low-power check |
| L, the paper's US data window | 1963-07 to 2015-12 | 630 | 0.392 / 0.435 | 1.22× / 1.35× | in-sample for the literature (its strategy months are 1964-07 to 2015-12, 618; the first year is its formation data, counted in-sample here) |
| P2, after the paper's sample end | 2016-01 to 2026-08 | 128 | 0.870 / 0.964 | 2.71× / 3.00× | low-power check |
| P = P1 + P2, outside the paper's window | | 560 | 0.416 / 0.461 | 1.30× / 1.44× | low-power check; carries the window rule below |

In return units, the 2%-a-year bar holds for H if sd(d) ≤ 7.01% (6.32% at nw 1.108); whether it does is unknown until the data step (the paper's Table 1 gives its US factors annualised standard deviations from 6.7% to 17.6%, and d averages two to four factors); if it does not, H is a test in Sharpe units only and its title says so. What H cannot see: an edge below about 0.29 Sharpe of d, which covers every single-study edge the programme has measured (003 0.092, 004 0.185, 008 0.227, 006 0.282, 007 0.309 at nw 1.108 only) and leaves only the 006–008 pool's 0.321 just inside.

**Window rule (fixed now).** If T1 meets the criteria on H but the mean of d over P is ≤ 0, the verdict is **"inconclusive (paper's window only)"**: an edge found only inside the sample the paper used is not this study's evidence. P1 and P2 are also reported separately; neither has decision weight alone.

## 3. What the author knows before choosing, and the vintage plan

### 3.1 Known before any data (general knowledge, not read from this repository)

The paper's positive result over 1964–2015 (§1); that momentum crashed in 1932 and in 2009 [DM16] (Mom is not traded here, but the reversal factors are built from past returns and may move with it); that value (HML) had a long drawdown to 2020; that the size premium was weak after the early 1980s; that short-term reversal was reported to weaken in recent decades (general knowledge, no source read); that US markets fell in 1929–32. The author has not seen any of these factors' 12-month signs computed over 1928–1963 or 2016–2026, and does not know their sign path. What the known episodes imply for d is not foreseeable from them alone (a crash month hurts d only if the rule was long the factor going in, which depends on the prior year's sign), so no episode is used to choose anything. The episodes are listed so that a reviewer can check the choices against them: the factor set, the formation window and the windows were all fixed by the paper and the library's start dates, not by an episode.

### 3.2 Vintage

The library rebuilds its whole history each month, and says historical returns can change (for example when CRSP revises its data); since its January 2025 release the US monthly returns are compounded from daily returns with dividends reinvested on ex-dates (read from the library page, 2026-10-26 06:1xZ). Decisions:

- **One snapshot.** The data step downloads the three files (US 3 factors; short-term reversal; long-term reversal), monthly, once; records SHA-256, byte size, the download time and the release named in each file's header; and commits them with a manifest. Every history row uses that snapshot only. No second download before the history run.
- **The vintage is part of the sample.** The note names the release; a later reader with a later release may get other numbers, and that is a property of the source, stated in the README.
- **Forward record.** Shadow only: long-short factors cannot be held with the approved instruments, so there is no paper sleeve. At each later month end the rule's positions for the next month are recorded from the latest release, with that release's hash. At scoring (after 60 months) the realised returns come from one release, named then, and the differences between that release and the snapshot over the overlapping months are reported as a vintage row.

## 4. Why not the alternatives

- **Volatility-managed factors [MM17] (the agenda's question 4 in its long-history form).** Its claimed effect is a lower variance at the same mean, so its test is a Sharpe-ratio difference or a spanning alpha, not the mean of d that `power_offduration.txt` powered; its power in its own units has not been computed, so the rule forbids fixing it now. It stays a candidate for a later power step.
- **Cross-sectional factor momentum** (the paper's second strategy). Long above-median factors, short the rest, among two to four factors: with so few factors it is close to a pairwise switch, a different and noisier object; the paper reports the time-series form as the stronger (4.2%, t 7.04, against 2.8%, t 5.74), and that form is followed.
- **The French Developed sample (F1) or the ETF era (E1, E2).** Above the bar (`power_offduration.txt`); they may run only as labelled low-power checks, and none is run here.
- **More factors from other sources** (for example AQR's data sets). Not checked for start dates; adding sources adds choices, and the library alone gives the length the power decision needed.
- **Adding Mom as a companion.** The paper's claim is about the non-momentum factors; Mom in the set would test something the paper excludes.

## 5. What this note does not do

No file was downloaded or read for this study; no factor return, formation return or position was computed on any window; no parameter was chosen on any data. Every figure is from `tools/power_study010.txt`, `tools/power_offduration.txt` or the source paper as quoted. Order of operations after this note: pre-registration and `trials.md` (three rows), reviewed for design by a separate session before commit (the rule adopted after the second cold read), pushed before the data step; data step (one snapshot, hashes, manifest; dates and counts only); signal and scoring code with tests; `APPROVED`; history run once; note; separate-session recomputation; forward record. Time labels are written from `git log`, not estimated.

Literature: [HOP17], [DM16] and [MM17] from the agenda's register (Crossref-checked, `tools/citations_check.txt`). The source paper is added to the register as [EL19] in the same commit as this note.
