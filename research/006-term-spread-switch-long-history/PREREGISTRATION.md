# Study 006 — Term-spread duration switch on the long history (1969–2018), with a fidelity gate tied to the decision it protects

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-10-25 |
| Status | pre-registered; **no file read for this study, no gate statistic, signal path, instrument return or rule return computed** |
| Version | 1.0 (any change after this commit requires a dated amendment appended to §16 before any further step is run) |
| Study type | new study on Study 001's question; Study 002's instrument construction frozen as committed; **gate redesigned after Study 002's halt (cold read, point 7)**: [`QUESTION.md`](QUESTION.md), [`COLD_READ.md`](../../COLD_READ.md) |
| Instruments | synthetic constant-maturity series from FRED for the test; IEF and BIL (approved under Study 001 on 2026-10-21) only in the gate, the 2019–2026 episode and the forward shadow record. **No paper order** (§11). |
| Approval | approved by the orchestrator under the delegation of 2026-10-21 (all decisions on this research programme), on the date of this commit. An `APPROVED` file is written at implementation time (§14 step 4), after this commit, so that `reproduce.sh` keeps its refusal gate. |
| Total trial count registered | **3**, carried over from Studies 001 and 002, where the same three trials were registered and never run (§7) |
| Author | the orchestrator (Qune) |

Nothing in this document reports or implies the performance of any rule. **No return of T1, T2, T3 or any benchmark exists on any window, under this study or Studies 001 and 002** (neither study's `results/` folder holds an `insample/` or `oos/` run). What the author has seen is listed in §2.4. The question note (`QUESTION.md`, commits `07962f7`, `1f20f16`) fixed the signal, the gate, the windows and the order of operations; this document writes them out as rules. Where the two differ, this document governs and says why (§0, item 9).

---

## 0. Relationship to Studies 001 and 002, and what changes

Study 001 halted at its data check (a synthetic 10-year series without roll-down under-earned IEF by about 0.45% a year, twice). Study 002 rebuilt the duration leg as an ageing 8.5-year par bond, passed both level checks (+0.10% a year on 2016–2018, −0.008% on 2003–2015) and failed an absolute daily tracking-error limit carried over from a calmer window (2.02% a year against 1.5% on 2003–2015). **Both verdicts stand: halted, inconclusive.** This study does not reopen either; it is a new study with its own number, trial log and verdict.

**Inherited unchanged from Study 001's pre-registration at commit `b6db436`** (the commit that closed it, so the §16 decisions on the 1969-08 start and verdict precedence are included): the question (§1), hypothesis and grounding (§2.1–2.3), literature (§3, Crossref-checked 2026-10-21; no new references), FRED sources and the bill conversion (§5.1), the synthetic cash leg (§5.2, cash), the rule, sizing, timing, rebalancing and missing-data handling (§6), the three trials (§7), benchmarks B0–B3 with B3's weight frozen from the test window's signals, costs, the twelve metrics, the deflated Sharpe ratio, criteria C1–C4 and the verdict precedence (§9.1–9.5 and the §16 clarification), the "What did not work" requirement (§9.7) and the pitfalls table (§10).

**Inherited unchanged from Study 002 at commit `a2b713b`**: the duration leg (§5.2 there: one 8.5-year par bond that ages and is repriced on a curve interpolated between DGS7 and DGS10) and the code that builds it, copied without any change of any kind.

The reader should open those documents for the inherited sections; they are not paraphrased so that nothing drifts. **What changes, and nothing else:**

1. **The fidelity gate** (§5.3): Study 002's daily tracking limits are replaced by the error that the synthetic series puts into the monthly timing differential, computed without forming any rule return. One attempt.
2. **A volatility check** (§5.4) on the whole history, before any rule return, from the committed power bar, with a fixed consequence.
3. **The windows** (§8): the test is 1969-08 to 2018-12; the 2019–2026 window is a labelled episode, not a test; the forward record is the clean test and is scored once (§11).
4. **The verdict table** (§9.5): no out-of-sample rows O1–O2; a volatility row; "supported in history; forward record pending".
5. **No paper order** (§11–§12).
6. **Repository layout and order of operations** (§13–§14).
7. **The deflated Sharpe ratio** at the programme-level family count is reported beside N = 3 and N = 10, descriptive (decision of 2026-10-24).
8. **Designer's prior knowledge** extended (§2.4).
9. **Where this document is more specific than `QUESTION.md`**: the vendor rule per holding period (§5.3.2) and the BIL source (Tiingo, from Study 003/004's file) were not named in the note; the forward stopping rule's power (§11.4) is computed here; the note's "programme-level family count" is defined in §9.4. Nothing in the note is reversed.

## 1. Question

Unchanged (Study 001 §1): **does conditioning a long-only intermediate-duration position on the sign of the 10-year minus 3-month term spread improve risk-adjusted return over an unconditional long position in the same instrument, after realistic costs?** Here the instrument is the synthetic 8.5-year leg over 1969-08 to 2018-12.

## 2. Hypothesis

H1, H0, the grounding and the reasons the edge might not survive are unchanged (Study 001 §2.1–2.3).

### 2.4 Designer's prior knowledge (disclosed; extends Study 001 §2.4 and Study 002 §2.4)

- **Both earlier validations**, all statistics: Study 001's two constructions and Study 002's two windows (A1–A4, B1–B2), Study 002's year-by-year level gap on 2003–2015 ([chart](../002-slope-duration-switch-r/charts/level_gap_by_year.png)) and its daily tracking error by year ([`posthoc_by_year.md`](../002-slope-duration-switch-r/results/validation/window2/posthoc_by_year.md)): ratio to IEF's volatility 0.25 on 2016–2018 and 0.29 on 2003–2015, single years up to 0.37 (2007) and 0.36 (2008).
- **IEF and BIL returns on 2003–2026**, from Studies 003, 004 and 005 (buy-and-hold rows, 12-month trend rules, the 2022 drawdown). The committed power file reads IEF's excess-return volatility on 2003–2018 as 6.26% a year.
- **General rate history**: when the 10-year/3-month curve was inverted (broadly 1973–74, 1978–80, 1981, 1989, 2000, 2006–07, 2019 and 2022–24) and that rates were most volatile around 1979–82. The literature in Study 001 §3 says a steep curve predicts higher bond excess returns; the author therefore expects the rule's months in cash to cluster in late-cycle tightening, and does not know their realised bond returns on this construction.
- **Not seen, by anyone**: h_t on any window, e_t, the gate statistics G1 and G2 at monthly frequency, the 1969–2018 volatility of the synthetic leg, and any return of T1, T2, T3 or B2–B3.

What this does to each check is stated where the check is defined (§5.3.5, §5.4). Mitigations unchanged: canonical rule, zero threshold, nothing tuned, construction frozen, one gate attempt, forward record scored by a stopping rule.

### 2.5 What Studies 001 and 002 taught, applied here

- A fidelity limit carried from one window to another measures the window's volatility as much as the series' quality. The gate here is scaled to the decision (a share of the C2 standard error), not to a level of daily noise.
- A constant level gap between a synthetic series and an ETF does not move a timing differential: its weight, the mean of h_t − w, is zero by construction. Only a gap that coincides with the rule's positions can bias the decision; G1 measures exactly that.
- The gate must not see the rule's return, or it becomes a second test. The gate module cannot import the backtest (§13, test 1).

## 3. Literature

Study 001 §3, unchanged; no new references.

## 4. Instruments

No symbol is traded. IEF and BIL (approved 2026-10-21 under Study 001; the approval stays with the studies that hold a sleeve) appear only as data: in the gate (§5.3), the 2019–2026 episode (§8.2) and the forward shadow record (§11).

## 5. Data

### 5.1 Sources: no fetch; every file is reused byte for byte and hash-checked

| File | Taken from | Use |
|---|---|---|
| `fred_DGS10.csv`, `fred_DGS7.csv`, `fred_DTB3.csv` (downloaded 2026-10-21, last valid 2026-10-19) | Study 002 `data/raw/` (same bytes as Study 001's) | signal; synthetic legs |
| `tiingo_IEF_daily.csv` (2002-07-26 to 2026-10-21) | Study 002 `data/raw/` | gate, holding periods not covered by Alpaca at both ends (§5.3.2) |
| `alpaca_IEF_1Day_all.csv`, `alpaca_BIL_1Day_all.csv` (2016-01-04 to 2026-10-21) | Study 002 `data/raw/` | gate from 2016; the episode |
| `tiingo_BIL_daily.csv` (2007-05-30 to 2026-10-21; passed Study 004's coverage check D0) | Study 004 `data/raw/` (same bytes as Study 003's) | gate, 2007–2015 holding periods (§5.3.2) |

Each file is copied into this study's `data/raw/` only after its SHA-256 matches the source study's `results/data_manifest.json`; the match, the source and the time are written to this study's manifest. A mismatch stops the study before the gate. The forward record (§11) fetches new FRED and Alpaca data each month; nothing else is fetched.

### 5.2 Instruments

Duration leg: Study 002 §5.2, code at `a2b713b`, unchanged. Cash leg: Study 001 §5.2 (cash), unchanged. Both include today's expense ratios, as there.

### 5.3 The gate (instrument returns and the signal path only; no rule return)

#### 5.3.1 Quantities

Holding periods: the 192 monthly periods of Study 001's execution calendar (§6.3 there) whose execution dates run from the first NYSE trading day of January 2003 to that of January 2019 (signal dates: the last FRED business days of December 2002 to November 2018).

For each period t:

- h_t = 1 if T1's signal (`spread_t > 0`, Study 001 §6.1) holds the duration leg for period t, else 0. From FRED yields only.
- x_t(synthetic) = D_t(synthetic) − C_t(synthetic), the duration leg's simple return over the period minus the cash leg's.
- x_t(ETF) = IEF_t − BIL_t, from adjusted closes on the two execution dates; where BIL is not available for the period (§5.3.2), C_t(synthetic) replaces BIL_t on both sides, so g_t is the duration-leg gap alone.
- g_t = x_t(synthetic) − x_t(ETF).
- w_o = mean of h_t over the 192 periods; e_t = (h_t − w_o) · g_t.

No cost enters: costs depend on h alone and are identical for both series.

#### 5.3.2 Vendor per holding period (fixed now; no choice later)

- IEF: Alpaca when Alpaca has a bar on both execution dates of the period, otherwise Tiingo, both ends from the same vendor. Alpaca's first bar is 2016-01-04, so every period ending before or on it uses Tiingo.
- BIL: the same rule, with Tiingo's BIL file. A period uses BIL only if the chosen vendor has a bar on both of its execution dates; the first such period is read from the file at the data step (§14 step 2) and recorded before the gate runs. Earlier periods use synthetic cash on both sides.
- A missing bar on an execution date: Study 001 §6.5 (next available close, logged).

#### 5.3.3 Checks and bounds

At the design point of the committed power bar (C2-bar MDE 2% a year, 80% power), the annualised standard error of the mean differential is 2% / (2.0 + 0.842) = 0.70% a year.

| Check | Statistic (monthly, 192 periods) | Bound | Derivation |
|---|---|---|---|
| **G1, bias** | \|mean(e_t)\| × 12 | **≤ 0.18% a year** | the series may move the C2 numerator by at most a quarter of a standard error at the design point (0.25 × 0.70%) |
| **G2, noise** | sd(g_t) / sd(x_t(ETF)) | **≤ 0.32** | added noise may inflate the C2 standard error by at most 5%: √(1 + 0.32²) = 1.05, if g is uncorrelated with the differential (assumption, stated) |

Both must pass. Bounds are compared at full precision; the reported figures are rounded once, after the comparison.

#### 5.3.4 Reported beside the gate, no decision weight

w_o and the number of switches of h on the overlap; mean(g_t) × 12 (the level gap, which cancels in e); corr(g_t, x_t(ETF)); G1 and G2 on 2003–2007 and on 2008–2018 separately (fidelity in the calmer and the more volatile part, the only evidence available on the assumption below); and e_t's mean for T2's and T3's signals (h from their own definitions), labelled descriptive, because the verdict rests on T1. The gate code never forms h_t · x_t on either series, and never T1, B3 or d.

#### 5.3.5 What the gate can and cannot show, and what the designer has seen

- **G2 is a weak test**: Study 002's daily ratios on the overlap (0.25, 0.29) sit under the bound; a pass is expected rather than informative. **G1 is the strong check, not a blind one**: from §2.4 the sign and rough size of mean(e) could be guessed (level gap by year, plus general knowledge of the 2006–07 inversion). If the guess is right, G1 passes because the gap was small in the cash months, which is what G1 measures; the gate stays valid where it is predictable.
- **Before 2003 there is no ETF to compare with.** Assumption, stated: the construction's error per unit of rate volatility is no worse in 1969–2002 than in 2003–2018. The 2003–2007 / 2008–2018 split is the only evidence on it and is reported, not gated.

#### 5.3.6 Halt rule

If G1 or G2 fails, the study halts permanently as **"inconclusive"** before the volatility check and before any rule return; every gate statistic is published; the construction, the bounds and the vendors are not changed and the gate is not re-run. A bug found later in the gate code is handled as Study 001 §8.2 handles one in shared code (amendment, both outputs kept); a bug fix may not change a bound.

### 5.4 Volatility check (once, after the gate passes, before any rule return)

σ = annualised standard deviation of x_t(synthetic) over the 593 holding periods 1969-08 to 2018-12 (signal dates July 1969 to November 2018), monthly standard deviation × √12. The code computes and writes σ only (no mean of x, no h), and the MDE it implies under the committed product form at w = 0.5: **MDE = 2% a year × σ / 10.18%**.

- **σ ≤ 10.18%**: the criteria stand as registered.
- **σ > 10.18%**: the study's title and first paragraph carry **"low-power check"**, and the "supported in history" row of §9.5 becomes **"consistent with an edge, not detectable at the 2% bar"**.
- Whatever σ is, the note says the study cannot see an edge of 1% a year or less (the 1% bar is σ ≤ 5.09%, below IEF's own 2003–2018 figure).

The power file also assumed that the ratio of the Newey–West to the i.i.d. standard error of the differential (0.972 in Study 003) carries over. It can only be observed from the rule's returns, so it is reported in the history results beside the assumed value; the criteria do not change if it differs.

### 5.5 Data availability

Dates only, from the manifests above (verified at §14 step 2, before the gate): FRED DGS10 from 1962-01-02, DGS7 from 1969-07-01, DTB3 from 1954; all to 2026-10-19. The test window needs DGS7 from the last FRED business day of July 1969, which exists by Study 001's §16 decision.

## 6. Exact rule specification

Unchanged (Study 001 §6): signal `DGS10/100 − bey(DTB3)` on the last FRED business day of the month on which both exist, threshold zero, duration leg if positive else cash, executed at the close of the first NYSE trading day strictly after the signal date, 100% of equity, monthly, no stops in the backtest. In the test window the legs are the synthetic series (§5.2); in the episode, IEF and BIL.

## 7. Registered trials (N = 3, carried over)

T1 (month-end sign of the spread), T2 (21-observation mean of the spread), T3 (carry including roll-down, `spread + D_mod(DGS10) × (DGS10 − DGS7)/3`), as defined in Study 001 §7. Logged in `trials.md` with their original registration date (2026-10-21, Study 001).

Why N stays at 3: a trial counts when its return is computed and seen. No return of T1, T2 or T3 has been computed, under any construction or study. The implicit search over instrument constructions (three across Studies 001 and 002) and over gates (two) is what the N = 10 sensitivity of Study 001 §9.4 covers; the note says so.

No other variants. Any addition is appended to `trials.md` with a date before it runs, and N increases.

## 8. Windows and the role of each

### 8.1 The test: 1969-08 to 2018-12, synthetic throughout

593 holding periods (first execution date the first NYSE trading day of August 1969; last period ends at the first execution date of January 2019). Criteria C1–C4 at base costs, as Study 001 §9.5. B3's weight w is the share of these 593 periods in which T1 holds the duration leg, computed from signals only, frozen, and used unchanged in the episode and the forward record. If T1 switches fewer than 8 times in the window, the first paragraph says "low-powered" (Study 003's rule; not expected over 1969–2018, by §2.4).

Sub-windows, descriptive, no decision weight, reported not selected from: 1969-08 to 2002-12 (401 periods, before any ETF) and 2003-01 to 2018-12 (192 periods, the gate's overlap); and Study 001's §9.6 sub-periods as amended (1969-08 to 1981-12, 1982-01 to 2008-12, 2009-01 to 2018-12).

### 8.2 2019-01 to 2026-09: an episode, not a test

93 holding periods (last period ends at the first execution date of October 2026). No term-spread rule return exists on it, but it is the programme's shared held-back window, the author's general knowledge covers it, and the 2022–24 inversion is common knowledge, so a result there would be predictable. **Run once**, with actual IEF and BIL from Alpaca (the synthetic series alongside), after the history note is committed. Reported under the heading "2019–2026 episode (no decision weight)", with the same statistics and B3 at the frozen w; never quoted in a verdict sentence.

### 8.3 The forward record: the only clean test

§11. Shadow only; scored once by a stopping rule.

## 9. Benchmarks, metrics and decision criteria

### 9.1–9.3 Benchmarks, costs, metrics

Unchanged (Study 001 §9.1–9.3): B0 cash, B1 duration leg, B2 50/50, B3 same exposure at the frozen w; 2 bp base and 4 bp stress per side; the twelve metrics, for T1, T2, T3 and B0–B3, base and stress costs, on the test window, each sub-window and the episode. Synthetic legs in the test window (B0 = synthetic cash, B1 = synthetic duration leg).

### 9.4 Deflated Sharpe ratio

As Study 001 §9.4: decision at N = 3, N = 10 beside it in every table, the variance floor if the trials are near-identical. **Added, descriptive, no decision weight:** the DSR at the programme-level family count, counted by the procedure of `tools/tsmom_family_dsr.py`: every trial of a term-spread or curve-slope duration rule whose return had been seen, in the programme's trial logs and the desk's trial registry, up to and including this study's run, with the registry rows listed. At registration that count is, as far as the logs show, the three trials of this study; the history step re-counts from the registry before reporting.

### 9.5 Verdict table (replaces Study 001 §9.5's table; criteria C1–C4 unchanged)

In the test window, at base costs, for T1:

- **C1**: Sharpe(T1) ≥ Sharpe(B1) + 0.10 and Sharpe(T1) ≥ Sharpe(B3) + 0.10 (annualised).
- **C2**: Newey–West t-statistic (Bartlett, 6 lags) of mean(T1 − B3) ≥ 2.0.
- **C3**: DSR(T1) at N = 3 ≥ 0.95.
- **C4**: the sign of mean(T1 − B3) is unchanged under stress costs.

| Verdict | Condition |
|---|---|
| **Inconclusive (gate)** | G1 or G2 fails (§5.3.6). No rule return is computed. |
| **Not supported** | Any of C1–C4 fails for T1. |
| **Inconclusive (fragile)** | C1–C4 hold for T1, but T2 or T3 fails any of C1–C4 on the same window (Study 001's fragility rule). |
| **Consistent with an edge, not detectable at the 2% bar** | C1–C4 hold for T1, T2 and T3 are not "not supported", and σ > 10.18% (§5.4). |
| **Supported in history; forward record pending** | C1–C4 hold for T1, T2 and T3 are not "not supported", and σ ≤ 10.18%. |

Precedence: not supported > inconclusive (either kind) > consistent > supported. No sentence may call the result "supported" without the words "in history; forward record pending" until the forward record is scored (§11.4). Whatever the verdict, the note's first paragraph carries "gate redesigned after Study 002's halt (cold read, point 7)" with the link to `COLD_READ.md`.

### 9.6 Pre-registered descriptive sub-analyses (no decision weight)

- The sub-windows of §8.1, metrics 1–7.
- Mechanism check (Study 001 §9.6): the number of periods with spread ≤ 0, the count and mean length of inverted episodes, and the duration leg's return over cash in those periods against the others.
- The observed Newey–West to i.i.d. ratio of the differential, beside the assumed 0.972 (§5.4).
- Charts to the house standard (`qune_research/style.py`): the spread with the holdings shaded; T1 against B1 and B3, growth and drawdown; the differential by decade.

### 9.7 What did not work

Study 001 §9.7, unchanged; an empty section is not acceptable.

## 10. Known pitfalls

Study 001's table applies. Rows that change or are added:

| Pitfall | Treatment |
|---|---|
| A new gate after the old one failed looks like moving the goalposts | Study 002's verdict stands; construction frozen at `a2b713b`; bounds from the committed power bar, not from any fidelity figure; one attempt; the label travels with the result (§0, §9.5). |
| The gate sees the rule's return | The gate module imports nothing from the backtest module and never forms h·x (§5.3.4, §13 test 1). |
| The designer can guess G1 and knows G2 will pass | Disclosed per check (§5.3.5). |
| Fidelity before 2003 is untestable | Assumption stated; the 2003–2007 / 2008–2018 split reported (§5.3.4–5.3.5). |
| The whole-history test has less power than it looks | Volatility bar checked before any rule return, with a fixed consequence (§5.4); 1% a year is out of reach and the note says so. |
| 2019–2026 is known history | Episode only, run once, no decision weight (§8.2). |
| Choosing when to score the forward record | Stopping rule fixed now (§11.3). |

## 11. Forward record (no paper order)

No paper order is placed under this study: the programme's paper sleeve belongs to Study 003's rule, and a rule whose clean test is still to come earns none. Promotion to any order would need an owner decision and Independent Risk clearance; none is asked for.

- **11.1 Start.** The first month-end after the history note (§14 step 8) is committed. Never backdated; a missed month is logged as missed and never filled later.
- **11.2 Decision record.** For each signal date t (Study 001 §6.3): fetch DGS10 and DTB3 from FRED (waiting up to three NYSE days for date t to appear, as Study 001 §6.3 allows; the wait is logged), compute the spread and T1's, T2's and T3's targets, and write `paper-log/decisions/<signal_date>.json` with every input, the file hashes and the UTC time written, before the close of the execution date. Never rewritten.
- **11.3 Monthly line and stopping rule.** After each execution date, `paper-log/shadow.csv` gets one line: the holding-period returns of IEF and BIL from Alpaca `adjustment='all'` closes, T1, T2, T3 and B1–B3 (frozen w) at base costs, and d_t = T1 − B3. Interim figures appear in the folder README under **"Not yet scored"** only. The record is **scored once, after 60 holding periods**; the scoring date is written in that month's decision record before any statistic is computed.
- **11.4 Forward verdict** (Newey–West t at 6 lags on d_t):

| Row | Condition |
|---|---|
| **Not testable** | T1 held the same leg in all 60 periods: no timing decision was made, so d_t = (1 − w)·x_t or −w·x_t is an exposure bet. Reported as such; the record continues to a second 60-period block, scored the same way. |
| **Supported (forward)** | mean(d) > 0 and t ≥ 2.0 |
| **Refuted (forward)** | t ≤ −2.0 |
| **Inconclusive (forward)** | anything else; the note records the effect size the 60 months could have detected |

Fewer than 8 switches in the 60 periods adds "low-powered" to whichever row applies. **Power, stated now:** scaling the committed power file to 60 periods gives a C2-bar MDE of about **3.0% a year** at Study 003's observed ETF-era dispersion (1.73% × √(185/60) = 3.04%; 0.96% × √(593/60) = 3.02%), and about **3.9% a year** under the conservative product form at IEF's 2003–2018 volatility (2% × 6.26/10.18 × √(593/60) = 3.87%). The forward record is weak; it is the only test in which the rule was fixed before the data existed. A forward verdict is reported beside the history verdict, not instead of it; a conflict between them is named in the first paragraph.

- **11.5 Published every month:** the decision record, the shadow line, the interim figures under their label, and `make dashboard` output once a shadow line exists.

## 12. Risk limits

None needed: no order is placed. Study 003's sleeve and the desk's limits are untouched.

## 13. Repository layout

`research/006-term-spread-switch-long-history/`:

- `src/`: Study 002's `src/` at `a2b713b`, copied with attribution in the commit and **unchanged** (synthetic legs, signal, calendar, engine, statistics); new modules `gate.py` (§5.3; imports only the signal, calendar, synthetic and data-reading modules), `volcheck.py` (§5.4; returns σ and the MDE only), `config.py` additions (windows, bounds, vendor rule) and `episode.py` (§8.2).
- `tests/`: Study 002's 131 tests, re-run unchanged, plus at least: (1) `gate.py` and `volcheck.py` import nothing from `backtest.py`, directly or through another module (checked on the import graph); (2) a constant g gives mean(e) = 0 to machine precision; (3) G1 and G2 on constructed series with known answers, including the BIL-absent branch; (4) the vendor rule of §5.3.2 on constructed calendars, including the December 2015 period; (5) `volcheck.py` output contains σ and the MDE and nothing else; (6) the look-ahead test of Study 001 §6.3 on the gate's h.
- `reproduce.sh` with `--gate`, `--volcheck`, `--history`, `--episode`; each refuses without `APPROVED` and refuses a second run when its output folder exists.
- `results/{gate,volcheck,history,episode}/`, `data/raw/`, `results/data_manifest.json`, `paper-log/`, `trials.md`, `README.md`, `REVIEW.md`, `review_recompute.py`.

## 14. Order of operations

1. Commit this document and `trials.md`; push (pre-push scan). No file read, no return.
2. Data step: hash-check and copy the files of §5.1, record dates only (first and last bars, the first BIL period of §5.3.2) in the manifest and `trials.md`; commit.
3. Implement `src/` and `tests/`; Study 002's 131 tests pass unchanged and the new tests pass; commit.
4. `APPROVED`; trial-log row for the gate written **before** the run; commit.
5. `reproduce.sh --gate`, **once**; commit the outputs whatever the outcome. Halt or proceed (§5.3.6).
6. Trial-log row, then `reproduce.sh --volcheck` once; commit σ and the MDE.
7. Run dates for T1–T3 appended to `trials.md` before the run; `reproduce.sh --history` once → `results/history/`; commit.
8. README.md: verdict per §9.5, the first-paragraph labels, "What did not work", the observed NW factor, the programme-level DSR; commit. This is the publication date.
9. `reproduce.sh --episode` once → `results/episode/`, under its label; commit.
10. Separate-session recomputation (`review_recompute.py`, `REVIEW.md`), as Studies 001–005.
11. Forward record from the first month-end after step 8 (§11).

No step may be reordered. Steps 5–7 are the only times the author sees any new quantity before the note; the gate and the volatility check show no rule return.

## 15. Things this study deliberately does not do

As Study 001 §15 and Study 002 §15, plus: it does not change the construction, the gate's bounds, its statistics or its vendors after this commit, and runs the gate once; it does not treat 2019–2026 as a test or run it twice; it places no paper order; it adds no trial (no other threshold, smoothing, maturity, trend overlay or vol targeting); it does not test the 12-month trend rule on the long history (a separate question on the agenda); it does not claim fidelity before 2003.

## 16. Amendments

(Append dated entries here; each must state what changed, why, which results had already been seen at the time, and the trial count N.)

- **2026-10-25 02:2x London, clarification before implementation (§14 step 3); results seen: the data step's dates only (`results/data_step.md`); N unchanged (3).** §0 and §13 name Study 002's code "at `a2b713b`". Study 002's `src/` has since changed in two commits, neither of which touches the construction: `25a69a4` (a hash-checked reuse of Study 001's FRED files in `reuse_bars.py`, made before Study 002's single validation run, so it is part of the code that ran) and `bddcf44` (mechanical lint: import order, the `datetime.UTC` alias, two f-strings without placeholders). **Decision: copy Study 002's `src/` and `tests/` as they stand at `edec076`**, so that the copy passes the repository's lint without new exceptions. Checked rather than promised by `src_provenance.py` (output `src_provenance.txt`): with import statements removed and the UTC alias normalised, 14 of the 16 modules have syntax trees identical to `a2b713b`, including `synthetic.py`, `bey.py`, `signal.py`, `calendar.py`, `backtest.py`, `stats.py` and `config.py`; the two that differ are `reuse_bars.py` (`25a69a4`) and `overlap_check.py` (one f-string prefix; not used by this study). The construction, the signal, the calendar and the engine are therefore the code of `a2b713b`. Nothing else changes.

- **2026-10-25 02:2x London, clarification during implementation; results seen: dates only; N unchanged (3).** (a) §13 and §14 step 3 say Study 002's "131 tests, re-run unchanged". At `edec076` Study 002 has 133 tests (131 plus two added by `25a69a4` before its validation run). Four of them test Study 002's own `reproduce.sh` modes (`--validate`, `--insample`, `--oos`), which this study does not have; they are not copied, and the same two gates (refusal without `APPROVED`, refusal of a second run) are tested for this study's four modes in `tests/test_gate.py`. The other 129 run unchanged. (b) §13 says "`config.py` additions"; the additions are in a separate `src/config006.py` instead, so that every copied module stays byte-identical to Study 002's (checked with `diff -r`; the only copied file that differs is `tests/test_data_io.py`, by the removal in (a) and its three then-unused imports). No rule, bound, window or criterion changes.

- **2026-10-25 03:3x London, clarification during implementation (§14 step 3, part 2); results seen: dates only; N unchanged (3).** (a) **Sub-period month convention.** Study 001's §16 decision and Study 002's `config.py` define the three §9.6 sub-periods "by the calendar month of the holding period's start", but Study 002's copied `report.subperiod_metrics` compares the schedule's index, which is the *signal* month, one month earlier; under it the first test period (signal July 1969, executed August 1969) falls outside the first sub-period and each boundary shifts by one period. Study 002 never ran it, so no result depends on it. The copied module stays unchanged; its output is kept under the key `subperiods` and labelled "by signal month". **Decision:** `src/history.py` computes both Study 001's sub-periods and this study's §8.1 sub-windows by the month of each period's execution date (`subperiods_by_execution_month`, `sub_windows`), which is the registered definition; the note quotes those. (b) **Programme-level family count (§9.4)**, counted now from the desk's trial registry (555 rows) and the public trial logs: no term-spread or curve-slope duration trial with a seen return exists (the registry's `term=` rows are VIX futures term-structure cells, a different signal; Studies 001 and 002 registered T1–T3 and never ran them), so the family is this study's three trials and the family DSR equals the N = 3 DSR. Recorded as a dated constant in `src/config006.py` and re-counted before the history run. (c) `src/history.py` and `src/episode.py` wrap Study 002's `report.run_window` unchanged; `history.strategy_results` repeats the engine's steps to expose the frames for the sub-windows and the Newey–West/i.i.d. ratio, and a test checks it equals the engine's monthly output period by period. No rule, bound, window or criterion changes.
