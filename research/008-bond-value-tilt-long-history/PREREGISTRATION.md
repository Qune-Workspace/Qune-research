# Study 008 — Bond value tilt by the real yield on the long history (1974–2018): does the level of the real yield time duration?

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-10-25 (the commit's time is the record) |
| Status | pre-registered; **no CPI file fetched or read for this study, no inflation rate, real yield, rank or weight computed on any window, no instrument return or rule return computed under this design** |
| Version | 1.0 (any change after this commit requires a dated amendment appended to §16 before any further step is run) |
| Study type | new study on candidate V of the agenda refresh in its long-history form ([`QUESTION.md`](QUESTION.md), commit `1d1daeb`; [`RESEARCH_AGENDA.md`](../../RESEARCH_AGENDA.md), dated addition and precision of 2026-10-25, commits `75f6a70` and `7ea34ac`); **third study on Study 006's leg and window after Studies 006 and 007 were published** (§0, §2.4, §9.4) |
| Instruments | Study 006's synthetic constant-maturity leg and synthetic cash from FRED for the test; IEF and BIL (approved under Study 001 on 2026-10-21) only in the gate, the 2019–2026 episode and the forward shadow record. **No paper order** (§11). |
| Approval | approved by the orchestrator under the delegation of 2026-10-21 (all decisions on this research programme), on the date of this commit. An `APPROVED` file is written at implementation time (§14 step 4), after this commit, so that `reproduce.sh` keeps its refusal gate. |
| Total trial count registered | **3** (§7): T1 and its two fragility companions T1a and T1b |
| Deflated Sharpe ratio decided at | the **programme-level family count, 17 at registration** (§9.4), re-counted before the history run; N = 3 and N = 10 reported beside it |
| Author | the orchestrator (Qune) |

Nothing in this document reports or implies the performance of any rule registered here. No return of T1, T1a or T1b exists on any window, and no CPI value, inflation rate or real yield has been computed by this programme on any date. The question note (`QUESTION.md`) fixed the rule, the trials, the windows, the family-count criterion and the order of operations; this document writes them out as rules. Where the two differ, this document governs and says why (§0, item 10).

---

## 0. Relationship to Studies 001, 002, 006 and 007, and what changes

**Inherited unchanged from Study 001's pre-registration at commit `b6db436`**: the literature of §3 there, the FRED sources and the bill conversion (§5.1), the synthetic cash leg (§5.2, cash), the execution calendar and timing convention (§6.3: signal on the last FRED business day of the month on which every input exists, execution at the close of the first NYSE trading day strictly after it), the missing-data handling (§6.5), costs (§9.2: 2 bp a side base, 4 bp stress), the twelve metrics (§9.3), the deflated Sharpe ratio's method and variance floor (§9.4), criteria C1–C4 (§9.5), the "What did not work" requirement (§9.7) and the pitfalls table (§10).

**Inherited unchanged from Study 002 at commit `a2b713b`**, through Study 006's copy: the duration leg (one 8.5-year par bond that ages and is repriced on a curve interpolated between DGS7 and DGS10) and the code that builds it.

**Inherited unchanged from Study 006's pre-registration at commit `a67ef8d` with its §16 amendments**: the seven data files and the hash-check rule (§5.1 there), the vendor rule per holding period (§5.3.2), the gate's two statistics, their bounds and their derivation (§5.3.1, §5.3.3), the import-graph rule (§5.3.4, §13 test 1), the volatility check's bar and consequence (§5.4), the treatment of 2019–2026 as an episode run once (§8.2), the forward record's clock, execution-date, missed-month and wait rules (§11 and the §16 entry of 2026-10-25 04:2x), the no-paper-order rule (§11–§12) and the order-of-operations pattern (§13–§14).

**Inherited unchanged from Study 007's pre-registration at commit `e4c21e5` with its §16 amendments as committed at `187038f`**: the average-rank percentile and its tie rule (§6.2 there), the fractional-weight engine `tilt.py` and its drift and cost convention (§6.4–§6.5), the gate for a fractional weight path (G1 per trial, G2 inherited as observed, §5.3), costs on the traded fraction, the turnover rule (§8.1), the per-trial B3 at the trial's frozen mean weight (§9.1), the family-count rule for C3 (§9.4), the mechanism check's equal-count quintiles (§16 entry of 2026-10-25 12:3x), and the forward record's code decisions of its §16 entries of 2026-10-25 14:21 and 14:32 GMT where they apply to a fractional weight (when t is final, rounding, holds, starting weights, the shadow line).

The reader should open those documents for the inherited sections; they are not paraphrased so that nothing drifts. **What changes, and nothing else:**

1. **The signal** (§6.1): the real yield, DGS10 at the signal date less trailing 12-month CPI inflation to the previous month, in place of carry. Two new FRED files (§5.1).
2. **The trials** (§7): N = 3; each companion moves a choice that changes the weight path on the test window (the inflation measure; the rank window), not the minimum history, which Study 007's gate showed changes nothing once reached (007 §16, entry of 2026-10-25 12:3x).
3. **A trailing-window rank** (§6.2) for T1b, new code beside 007's expanding rank.
4. **Criterion C3 at the programme-level family count, 17 at registration** (§9.4).
5. **An era row** in the verdict table (§9.5): "inconclusive (one era)".
6. **Overlap with Studies 006 and 007** (§5.6), measured from signal paths before any return; a headline flag above 0.8.
7. **A CPI availability rule** (§6.1, §6.5): the index for month m−1 is used at month m's signal date only if it had been published by then where the publication date can be read; a missing CPI month leaves the real yield undefined and the trial holds.
8. **The mechanism check** (§9.6) groups by the real yield's sign in place of carry's.
9. **The forward record** (§11) writes the real yield, the CPI months used, the rank and the months behind it.
10. **Where this document differs from or is more specific than `QUESTION.md`**: (a) the note placed the overlap correlations "at the data step"; the data step reads dates only (as in Studies 006 and 007), and the weight paths first exist in the gate code, so the overlap is computed **in the same single run as the gate, before any rule return** (§5.6, §14 step 5); (b) the note's §4 asked for a check for a public monthly inflation-forecast series covering 1969–2018 before this document: done, none found (§5.5), so T1's proxy is unchanged; (c) the CPI availability rule (§6.1), the trailing rank's exact form (§6.2), T1b's verdict window and its descriptive pairing with T1 (§7), the episode's handling of the missing October 2025 index (§6.5, §8.2) and the sub-analyses (§9.6) were not fixed in the note; they are fixed here. Nothing in the note is reversed.

## 1. Question

**Does scaling a long-only intermediate-duration position by the level of its real yield (the 10-year yield less trailing 12-month CPI inflation) improve risk-adjusted return over the same average exposure held throughout, after realistic costs, on 1974–2018?**

The instrument is Study 006's synthetic 8.5-year leg against its synthetic cash over 1974-07 to 2018-12. T1's verdict is the headline.

## 2. Hypothesis

- **H1 (T1):** the level of the real yield, measured against the yield's own history, predicts the leg's excess return over cash over the next month, so that a weight rising with the real yield's rank earns a higher Sharpe ratio than the same average weight held throughout, after costs (C1–C4 of Study 001 §9.5, with C3 at the family count).
- **H0 (T1):** the leg's excess return is not predictable from the real yield's level; the tilt's return equals the exposure-matched constant mix minus trading costs, and any Sharpe difference is within noise.

### 2.1–2.3 Grounding, and why the edge might not survive

The grounding is the agenda's value candidate and its sources ([AMP13]: value in government bonds across countries, main measure the 5-year yield change, the real yield an alternative in Table I Panel C, 1983–2011, high-minus-low 2.0% a year, t 3.78, reported; [BPR18]: real yield against survey expectations, from a search summary only), and `QUESTION.md` §1. Reasons the edge might not survive, stated now: (1) both sources rank bonds **across countries**; a time-series rule on one leg against bills is a different bet, and its premium may be the term premium's variation already timed by carry (Study 007); (2) trailing inflation is a poor forecast in the 1970s, when inflation was rising, so r_m overstates the real yield then; (3) an expanding rank of a level with a secular drift acts partly as a time trend (§2.4, §3 of the note); (4) the weight changes every month, so costs are paid continuously.

### 2.4 Designer's prior knowledge (disclosed; extends Study 007 §2.4)

The test window has been seen twice, and the form was chosen after seeing it (`QUESTION.md` §3.1). The author has read, and the reader should assume the author remembers:

- **Study 006's published results on this leg** (σ 7.75% a year over 593 periods; T1 spread sign Sharpe 0.463 vs 0.338, t 2.06; the decade differentials and three rate eras; the 2019–2026 episode).
- **Study 007's published results on this leg** (T1 carry tilt Sharpe 0.493 vs B3 0.381, t 2.10, verdict "inconclusive (fragile)" because T1b failed C2 at t 1.95 on its 474 periods; the mechanism quintiles, with the top quintile of carry carrying the result; σ 7.81% over the same 534 periods; the episode's T1 weight averaging 0.256).
- **General rate and inflation history, from general knowledge and not from this repository:** inflation high and rising in the 1970s, peaking around 1980; nominal and real yields highest in the early 1980s; real yields falling for most of the following decades, negative on this measure in parts of the 1970s and after 2008 at times; core and headline inflation diverging in oil-price episodes. **So the sign of what an expanding rank does in 1974–1990 is partly foreseeable** (low weight in the 1970s, high weight in the early 1980s when long bonds rallied).
- **Not seen, by anyone in this programme**: any CPI value read from the study's files, any inflation rate or real yield on any date, any rank or weight path, G1 for these paths, the overlap correlations, and any return of T1, T1a, T1b or of any benchmark at their mean weights.

Mitigations, all checkable: no parameter of T1 is a scale or threshold (the rank has none; 60 months is Study 007's minimum, inherited, not chosen on these data); T1b's trailing rank removes the secular drift and T1a moves the one judgement in r; the era row (§9.5) withholds "supported" if the result lives only before 1986; each trial's B3 removes the leg's premium at the trial's own exposure; C3 is decided at the family count; the overlap flag (§5.6) says when the result is a restatement of 006's or 007's; the episode is run once with no decision weight; the forward record is the only clean test.

### 2.5 What Studies 006 and 007 taught, applied here

- A companion that moves only the minimum history of an expanding rank is the primary under another name (007's gate disclosure); here both companions change the weight path.
- A companion on a shorter window can fail C2 for want of periods while the primary on the same periods looks the same (007: T1b t 1.95; T1 on T1b's 474 periods Sharpe 0.516). The fragility clause is kept as registered in 007 (stricter, not loosened after seeing it bite), and T1 on T1b's 474 periods is reported beside T1b, with its t, so that a reader can tell a window miss from a rule miss; the verdict does not use that row.
- Power is stated against the realised weight dispersion as well as the design figure (007 dated correction of 13:4x): §9.6.
- Time labels come from `git log`, never estimated; trial-log rows appended and never rewritten.

## 3. Literature

The agenda's [AMP13] and [BPR18], Crossref-checked on 2026-10-22 (`tools/citations_check.txt`); [AMP13]'s definitions read from the authors' PDF on 2026-10-25, [BPR18]'s from a search summary only; Study 001 §3 and Study 007 §3 for the term-premium and carry literature. No new references.

## 4. Instruments

No symbol is traded. IEF and BIL (approved 2026-10-21 under Study 001) appear only as data: in the gate (§5.3), the 2019–2026 episode (§8.2) and the forward shadow record (§11).

## 5. Data

### 5.1 Sources

- **Study 006's seven files, reused byte for byte and hash-checked**: `fred_DGS10.csv`, `fred_DGS7.csv`, `fred_DTB3.csv`, `tiingo_IEF_daily.csv`, `alpaca_IEF_1Day_all.csv`, `alpaca_BIL_1Day_all.csv`, `tiingo_BIL_daily.csv`, each copied into this study's `data/raw/` only after its SHA-256 matches Study 006's `results/data_manifest.json`. A mismatch stops the study before the gate.
- **Two new FRED files, fetched once** at the data step through the copied `fred.py` (Study 006's endpoint, `fredgraph.csv?id=<SERIES>`): `CPIAUCNSA` (CPI for all urban consumers, all items, not seasonally adjusted, index 1982–84 = 100, monthly) and `CPILFENS` (the same, all items less food and energy). Raw bytes stored, SHA-256, URL and UTC time written to the manifest. Not seasonally adjusted because the seasonally adjusted series are revised every year for five years back, and a 12-month change of an unadjusted index carries no seasonal pattern.
- **Vintage and release check, once, at the data step, before any inflation rate is computed**: through ALFRED's public download (the vintage form of the same endpoint), (a) for one vintage date in each year 1995–2018 where ALFRED holds one, compare that vintage's values for the CPI months it covers with the current file, and report the count and size of differences (expected: none beyond rounding, because the unadjusted index is not revised; any difference is reported in full and the current file is used, as Study 001 §5.1 uses current FRED files); (b) read each CPI month's first-release date where ALFRED holds it, for §6.1's availability rule. If ALFRED cannot be read without a key, the check is reported as not done, the no-revision property is stated as BLS's published policy, unverified here, and the release dates fall back to the assumption of §6.1. This step reads values only to compare vintages; it computes no inflation rate and no real yield.

The vendor rule per holding period is Study 006 §5.3.2 as applied there. The forward record (§11) fetches new FRED (including the two CPI series) and Alpaca data each month; nothing else is fetched.

### 5.2 Instruments

Duration leg: Study 002 §5.2, code at `a2b713b` as copied by Study 006, unchanged. Cash leg: Study 001 §5.2 (cash), unchanged.

### 5.3 The gate (signal paths and instrument returns only; no rule return)

Study 007 §5.3 applied to the three weight paths of §7: on Study 006's 192 overlap periods (2003–2018), G1^k = |mean((w_t^k − w̄_o^k) · g_t)| × 12 ≤ **0.18% a year**, each trial computed once, at full precision; **G2 inherited as observed (0.131)** and reproduced from the copied files against Study 006's committed full-precision figure 0.13140878732605116 to 1e-12, or the run stops. A trial whose G1 fails is dropped before any return as "inconclusive (gate)"; **if T1's fails, the study halts permanently**. Reported beside it, no decision weight: w̄_o^k, one-way turnover on the overlap, mean(g) × 12, corr(g, x_ETF), G1^k on 2003–2007 and 2008–2018. The gate code never forms w·x and never a rule or benchmark return. Fidelity before 2003 is an assumption (Study 006 §5.3.5).

### 5.4 Volatility check (once, after the gate, before any rule return)

σ of x_t(synthetic) over the test window's holding periods (§8.1); bar **10.18% a year** (Study 006 §5.4). The 534-period figure is already published by Study 007 (7.81%, `results/volcheck/volcheck.json` there) for the same leg, window and calendar. **It is not re-run as if new**: the script recomputes it from the copied files as a consistency check and must reproduce Study 007's committed full-precision figure to 1e-12, or the data step is wrong; it writes σ, the count and the MDE at w = 0.5 (2% × σ / 10.18%) and nothing else. If T1's window differs from 007's by even one period (§5.5), the figure is computed afresh on T1's window and labelled as such.

### 5.5 Data availability, and the inflation-forecast check of `QUESTION.md` §4

Dates only, from Study 006's manifest and the new files' first and last rows (verified at §14 step 2): DGS10 from 1962-01-02, DGS7 from 1969-07-01, DTB3 from 1954, all to 2026-10-19; CPIAUCNSA and CPILFENS monthly from before 1960 (exact first months written by the data step). Study 001's execution calendar starts at signal month 1969-07, so the first real yield is that of 1969-07 (π uses CPI 1969-06 over 1968-06); the sixtieth is 1974-06, so **T1's and T1a's first weight is for the period executed on the first NYSE trading day of July 1974** and **T1b's (the 120th real yield) for July 1979**. The exact period counts are fixed by the data step.

**Inflation-forecast check, done before this document (2026-10-25, 17:1x GMT, machine clock read at 17:19:42Z after it; sources read, no forecast value used):** no public monthly inflation-forecast series covers 1969–2018. The University of Michigan's expected-inflation series on FRED (`MICH`, median expected price change over the next 12 months, consumers) is monthly and contiguous from **1978-01** (first and last dates read from FRED's download, 585 rows to 2026-09; no value looked at); the Livingston Survey (Federal Reserve Bank of Philadelphia) is semiannual (June and December) from 1946; the Survey of Professional Forecasters' CPI forecasts are quarterly from 1981 Q3 and its 10-year CPI forecast from 1991 Q4 (the Livingston and SPF facts are from the Philadelphia Fed's survey pages, a Philadelphia Fed working paper and search summaries, not from the data files; only `MICH`'s dates were read from data). A forecast-based real yield would therefore start ranking in 1983 at the earliest (60 months of MICH) and would cover only the post-peak era that §9.5's era row tests on its own; or it would mix frequencies and surveys, a construction choice made with knowledge of the window. **Decision: T1's proxy stands (trailing 12-month CPI); no forecast-based trial is added** (it would raise N and the family count for a rule that cannot see the 1970s). Stated as a limitation in the note.

### 5.6 Overlap with Studies 006 and 007 (signal paths only, in the gate run)

In the same single run as the gate, before any rule return: over T1's test-window periods, corr(w_t^{T1}, w_t^{007 T1}) and corr(w_t^{T1}, 1[h_t^{006 T1} = leg]), with 007's T1 weights and 006's T1 holdings read from their committed `results/history/monthly_base.csv` (files hash-recorded; only the weight and holding columns are read, no return column). Also reported: the same correlations for T1a and T1b. **If either correlation for T1 exceeds 0.8, the note's headline states that the result is not independent of that study's, whatever the verdict.** No decision weight beyond that sentence.

## 6. Exact rule specification

### 6.1 Real yield, and when the CPI is known

Signal dates are Study 001's execution calendar (§6.3 there: the last FRED business day of the month on which DGS10, DGS7 and DTB3 all exist), unchanged, so that every leg, benchmark and period is that of Studies 006 and 007. On the signal date t of month m:

- y_t = DGS10_t / 100, read from the copied file.
- π_m = CPI(k) / CPI(k − 12) − 1, where **k = m − 1** (the index for the previous month), with CPI = CPIAUCNSA for T1 and T1b, CPILFENS for T1a. The index for month m is never used.
- **Availability rule.** Where the data step has read CPI(m − 1)'s first-release date (§5.1 (b)) and it is **after t**, k is the latest month whose first release is on or before t (normally m − 2), and the month is counted and listed. Where no release date can be read (expected for most or all of 1969–1990s), k = m − 1 is assumed known at t: BLS has published each month's index in the following month, before its last business day, as far as the author knows (stated, not checked month by month). The count of months by each branch is reported by the data step before any inflation rate is computed.
- r_m = y_t − π_m. No smoothing, no annualisation beyond the 12-month change.

If CPI(k) or CPI(k − 12) is missing (for example the October 2025 index, not published by BLS; checked at the data step from the file's dates), r_m is **undefined**: the month is left out of the rank history (n counts defined real yields) and every trial **holds** its position over that period (traded fraction zero, weight drifting with the two legs), as Study 007's forward rule (§16, 14:32 GMT, point (e)). The data step lists every such month before any rate is computed; none is expected in 1968–2018.

### 6.2 Weight: average-rank percentile, expanding or trailing

For T1 and T1a, with r_1, …, r_n the defined real yields observed up to and including month m (n = n_m), for n ≥ 60:

w_m = ( #{s ≤ m : r_s < r_m} + ½ · #{s < m : r_s = r_m} ) / (n − 1),

Study 007 §6.2 with r in place of c, computed by the copied `carry_rank` rank function. For **T1b**, the same formula over the **last 120 defined real yields including r_m** (n fixed at 120, denominator 119), from the month in which the 120th real yield exists. Before that no weight exists and no holding period is formed for that trial. w ∈ [0, 1]; higher real yield, more duration. No threshold, scale, smoothing or volatility scaling.

### 6.3 Execution, sizing and costs

Study 007 §6.4: weights set at the close of the execution date following the signal date, 100% of equity between the two legs, monthly, no stops; costs (2 bp base, 4 bp stress, a side) on the traded fraction |w_t − w̃_{t−1}| with the previous weight drifted; the first period starts from cash.

### 6.4 Engine

Study 007's `tilt.py`, copied unchanged with its equality tests (a 0/1 path reproduces `run_switching`; a constant path reproduces `run_static` from the second period). One addition, tested before any run: a **hold** period (§6.1) passes the drifted weight through with zero traded fraction.

### 6.5 Missing data

Study 001 §6.5 for the yields and ETF bars; §6.1 above for the CPI. Nothing is interpolated.

## 7. Registered trials (N = 3)

| ID | Rule (§6) | Window | Role |
|---|---|---|---|
| T1 | real-yield tilt, headline CPI (`CPIAUCNSA`), expanding rank, minimum 60 | 1974-07 to 2018-12 (the test window, §8.1) | **primary; the headline** |
| T1a | the same with core CPI (`CPILFENS`) | the test window | fragility companion: the inflation measure |
| T1b | the same as T1 with a trailing 120-month rank | **1979-07 to 2018-12** (about 474 periods); T1 reported on the same periods beside it, with its t, descriptive | fragility companion: the rank window and the secular drift |

**Fragility rule, for T1** (Study 006 §9.5 as carried by Study 007 §7): "supported in history; forward record pending" for T1 needs T1a and T1b each not "not supported" on their own criteria (T1b on its own window, against its own B3).

No other variants: no other inflation measure or horizon, no forecast-based real yield (§5.5), no other minimum history or rank window, no z-score, scale or dead band, no blend with carry or trend, no volatility targeting, no other maturity. Any addition is appended to `trials.md` with a date before it runs, and N and the family count increase.

## 8. Windows and the role of each

### 8.1 The test: 1974-07 to 2018-12, synthetic throughout

Holding periods from the first execution date of July 1974 (signal month 1974-06) to the period ending at the first execution date of January 2019 (signal month 2018-12): **about 534 periods, the exact count fixed by the data step (§14 step 2)**. Criteria C1–C4 at base costs (§9.5). Each trial's B3 weight w̄ is its mean weight over its window, from signals only, frozen, and used unchanged in the episode and the forward record. Turnover rule: total one-way turnover below 8 → "low-powered" (Study 007 §8.1).

**Era window, with decision weight only through the era row (§9.5): 1986-01 to 2018-12 by execution month, 396 periods.** Sub-windows, descriptive, reported not selected from: 1974-07 to 2002-12 and 2003-01 to 2018-12; Study 006's three rate eras by execution month (1974-07 to 1981-12, 1982-01 to 2008-12, 2009-01 to 2018-12); 1974-07 to 1985-12 (the complement of the era window).

### 8.2 2019-01 to 2026-09: an episode, not a test

93 holding periods, as Study 007 §8.2, **run once** after the history note is committed, with actual IEF and BIL from Alpaca and the synthetic series alongside; the rank history continues to expand (T1b's to trail) through the episode, with no re-estimation; B3 at each trial's frozen w̄; the October 2025 CPI gap handled by §6.1 (months whose r is undefined hold). Reported under "2019–2026 episode (no decision weight)"; never quoted in a verdict sentence.

### 8.3 The forward record: the only clean test

§11. Shadow only; scored once by a stopping rule.

## 9. Benchmarks, metrics and decision criteria

### 9.1–9.3 Benchmarks, costs and metrics

Study 007 §9.1–9.3 unchanged: B0 synthetic cash, B1 the synthetic leg, B2 50/50 rebalanced monthly; **B3^k per trial** at its frozen w̄^k; every differential d_t^k = T_k − B3^k; base and stress costs; the twelve metrics for the three trials and B0–B3 on each trial's window, each sub-window and the episode.

### 9.4 Deflated Sharpe ratio, decided at the programme-level family count

C3 is decided at the programme-level family count (Study 007 §9.4's rule): every trial of a duration-timing rule on the 7–10-year Treasury leg (IEF or the synthetic leg) over a window overlapping 1974–2018 whose return had been seen when this study's history step runs. **At registration, 17**:

| When | Where | Trials | Count |
|---|---|---|---|
| 2026-10-22 | Study 003 T1–T3, IEF 2003–2018 | 12-month trend, 12-1, 10-month moving average | 3 |
| 2026-10-23 | Study 005 T1–T3, IEF 2003-08 to 2018-12 | Study 003's exit conditioned on three regime variables | 3 |
| 2026-10-25 | Study 006 T1–T3, synthetic leg 1969–2018 | spread sign, 21-day mean, carry sign | 3 |
| 2026-10-25 | Study 007 T1, T1a, T1b, T2, T3, synthetic leg 1974–2018 | carry tilt (three minimum histories), carry + trend, trend | 5 |
| this study | T1, T1a, T1b | §7 | 3 |

Not counted, and why: as Study 007 §9.4 (Study 004's portfolio trials; the desk registry's equity and crypto rows; Studies 001 and 002 never ran). Study 007's T1a counts as a trial although its path equalled T1's: it was registered and run, and the count does not shrink after the fact. Re-counted immediately before the history run from the desk's registry and the public trial logs and written to `trials.md` and `config008.py`; any addition raises it. DSR at N = 3 and N = 10 reported beside it. Variance floor as Study 001 §9.4.

### 9.5 Verdict table (criteria C1–C4 of Study 001 §9.5, C3 at the family count)

For each trial k on its window, at base costs: **C1** Sharpe(T_k) ≥ Sharpe(B1) + 0.10 and ≥ Sharpe(B3^k) + 0.10; **C2** Newey–West t (Bartlett, 6 lags) of mean(d^k) ≥ 2.0; **C3** DSR(T_k) at the family count ≥ 0.95; **C4** the sign of mean(d^k) unchanged under stress costs.

**Era row (T1 only):** mean(T1 − B3^{T1}) over the era window 1986-01 to 2018-12 (§8.1) > 0 at base costs, with B3^{T1} at T1's full-window w̄. Pass/fail on the sign only; its t is reported, not tested.

| Verdict (T1, the headline) | Condition |
|---|---|
| **Inconclusive (gate)** | G1 for T1 fails (§5.3). No rule return is computed. |
| **Not supported** | Any of C1–C4 fails for T1. |
| **Inconclusive (one era)** | C1–C4 hold for T1, but the era row fails. |
| **Inconclusive (fragile)** | C1–C4 and the era row hold for T1, but T1a or T1b is "not supported" on its own criteria. |
| **Consistent with an edge, not detectable at the 2% bar** | All of the above hold and σ > 10.18% (§5.4). |
| **Supported in history; forward record pending** | C1–C4, the era row and the companion clause hold, and σ ≤ 10.18%. |

Precedence: not supported > inconclusive (gate) > inconclusive (one era) > inconclusive (fragile) > consistent > supported. The companions' own rows read "not supported", "inconclusive (gate)" or "meets C1–C4" (no era row and no companion clause for them). "Low-powered" is added to any row whose trial fails the turnover rule. No sentence may call a result "supported" without "in history; forward record pending" until the forward record is scored. Whatever the verdict, the note's first paragraph carries in one sentence the disclosure of §2.4 (the window was seen by Studies 006 and 007, and the drift of real yields is general knowledge) and, if §5.6's flag is raised, the overlap sentence.

### 9.6 Pre-registered descriptive sub-analyses (no decision weight)

- The sub-windows of §8.1, metrics 1–7, for every trial; T1 on T1b's 474 periods with its t (§2.5).
- **Mechanism check:** the leg's mean excess return over cash a year by equal-count quintile of T1's weight (ties by order, Study 007's rule; five rows, in full), and separately in the periods with r_m ≤ 0 against the others.
- **Overlap after the fact:** the correlation of T1's and Study 007 T1's monthly differentials d (both against their own B3) over the common 534 periods, beside §5.6's weight correlations.
- **Power, realised:** the observed Newey–West to i.i.d. ratio of d beside the assumed 0.972; sd(w − w̄) beside the design 0.5 and the uniform 1/√12; the minimum detectable mean difference at t = 2 and at 80% power (K = 2.842) from the observed Newey–West standard error of d, in % a year (the form of Study 007's dated correction, not its first sentence).
- Counts by §6.1's availability branch, and the months whose r is undefined, in every window.
- Charts to the house standard (`qune_research/style.py`): the real yield with T1's weight path; T1 against B1 and B3, growth and drawdown; the differential by decade; the three trials by sub-window.

### 9.7 What did not work

Study 001 §9.7, unchanged; an empty section is not acceptable.

## 10. Known pitfalls

Study 001's, Study 006's and Study 007's tables apply. Rows that change or are added:

| Pitfall | Treatment |
|---|---|
| The window has been seen twice, and real yields' secular drift is common knowledge | Disclosed (§2.4) in the note's first paragraph; no scale or threshold; T1b's trailing rank; the era row; C3 at the family count of 17; only the forward record is clean. |
| Using a CPI index before it was published | k = m − 1 only where it is known or assumed known at t; release dates read where ALFRED has them; counts reported (§6.1). |
| CPI revisions | Unadjusted series, not revised by policy; vintage comparison at the data step (§5.1). |
| A third study on the same leg restates the first two | Overlap correlations before any return and a headline flag above 0.8 (§5.6); the differential correlation after (§9.6). |
| A companion that changes nothing | Each companion changes the weight path on the test window by construction (inflation measure; rank window); the gate's weight-path output shows whether they differ, and if any pair is identical on every overlap period, §16 says so before any return. |
| A missing CPI month | r undefined, left out of the rank, trial holds (§6.1); listed. |
| The volatility check re-run as if new | Reproduced to 1e-12 against 007's committed figure, or computed afresh only if the window differs (§5.4). |

## 11. Forward record (no paper order)

No paper order is placed under this study. Study 007 §11 and its §16 code decisions apply with these changes only:

- **11.1 Start.** The first signal date after the history note (§14 step 8) is committed, per Study 001's calendar: 2026-10-30 if the note is committed before 21:15 UTC that day, otherwise the November 2026 signal date (the last FRED business day of November, expected 2026-11-30). Never backdated; a missed month is logged as missed and never filled.
- **11.2 Decision record.** For each signal date: DGS10 (and DGS7, DTB3 for the calendar's rule) from FRED, the CPIAUCNSA and CPILFENS rows fetched that month, the CPI months k and k − 12 used for each measure and their first-release status (§6.1: on a forward date the index is used only if its row is in the fetched file on t), π and r at full precision, n_m, the rank, w_m for T1, T1a and T1b to four decimals, every input hash and the UTC time. Starting weights are the three trials' weights at the 2026-09 signal date from the episode.
- **11.3 Monthly line and stopping rule.** `paper-log/shadow.csv`: IEF and BIL holding-period returns from Alpaca `adjustment='all'` closes, T1, T1a, T1b and B1–B3 at base costs, d_t = T1 − B3^{T1}. Interim figures under **"Not yet scored"** only. **Scored once, after 60 holding periods**; the scoring date is written in that month's decision record before any statistic is computed.
- **11.4 Forward verdict**, rows as Study 007 §11.4. **Power, stated now** from committed figures (`tools/power_refresh.txt`; Study 007 §11.4: K = 2.842, Newey–West factor 0.972, σ 7.75–7.81%): over 60 periods the C2-bar MDE is about **4.8% a year (0.62 Sharpe) at sd(w − w̄) = 0.5**, and about 2.8% a year at the uniform-rank dispersion. The forward record is weak and is the only test in which the rule was fixed before the data existed.
- **11.5 Published every month:** the decision record, the shadow line, the interim figures under their label, and `make dashboard` output once a shadow line exists.

## 12. Risk limits

None needed: no order is placed.

## 13. Repository layout

`research/008-bond-value-tilt-long-history/`:

- `src/`: Study 007's `src/` as committed at `187038f`, copied with attribution and **unchanged** (it contains Study 006's and Study 002's code), plus new modules `config008.py` (windows, trials, family table of §9.4, bounds imported from `config006`/`config007`), `real_yield.py` (§6.1–6.2: CPI reading, the availability rule, π and r at signal dates, the trailing rank beside the copied expanding rank; imports only the signal-calendar, FRED-reading and rank modules), `gate008.py` (§5.3 and §5.6; imports nothing from `backtest.py` or `tilt.py`), `volcheck008.py`, `history008.py`, `episode008.py`, `forward008.py`.
- `tests/`: Study 007's tests re-run unchanged where the code is copied, plus at least: (1) the import graph of `real_yield.py`, `gate008.py` and `volcheck008.py` (nothing from `backtest.py` or `tilt.py`); (2) π and r on constructed CPI series: k = m − 1, never m; the availability rule switching to the latest published month; a missing index making r undefined; (3) the trailing rank: window of 120 including today, denominator 119, the tie rule, no weight before 120 defined values, no look-ahead (changing r_{m+1} does not change w_m); (4) the hold period in the engine; (5) the overlap correlations read only weight and holding columns; (6) the volatility output's keys and the 1e-12 reproduction; (7) the look-ahead test of Study 001 §6.3 on every weight path; (8) the era row and the verdict precedence on constructed differentials.
- `reproduce.sh` with `--gate`, `--volcheck`, `--history`, `--episode`, `--forward`; each refuses without `APPROVED` and refuses a second run when its output folder exists.
- `results/{gate,volcheck,history,episode}/`, `data/raw/`, `results/data_manifest.json`, `paper-log/`, `trials.md`, `README.md`, `REVIEW.md`, `review_recompute.py`.

## 14. Order of operations

1. Commit this document and `trials.md`; push (pre-push scan). No CPI file fetched; nothing computed.
2. Data step: hash-check and copy the seven files; fetch `CPIAUCNSA` and `CPILFENS` once with a manifest; vintage and release-date check (§5.1); record dates only (first and last rows; missing CPI months; counts by §6.1's availability branch; the first signal month of each trial; the exact period counts of §8.1) in the manifest and `trials.md`; commit. No inflation rate or real yield computed.
3. Implement `src/` and `tests/`; the copied tests pass unchanged and the new tests pass; commit. No real-data run. (`forward008.py` may follow the note, as Study 007 §16 recorded.)
4. `APPROVED`; trial-log row for the gate written **before** the run; commit.
5. `reproduce.sh --gate`, **once** (three G1 figures, G2 reproduced, the overlap correlations of §5.6); commit the outputs whatever the outcome. Halt or proceed (§5.3).
6. Trial-log row, then `reproduce.sh --volcheck` once (reproduction of 007's σ, §5.4); commit.
7. Family re-count written to `trials.md` and `config008.py`; run rows for T1, T1a, T1b appended before the run; `reproduce.sh --history` once → `results/history/`; commit.
8. `README.md`: verdict per §9.5, the first-paragraph disclosure (and the overlap sentence if flagged), the mechanism and power rows, "What did not work", the DSR at 17, 3 and 10; commit. This is the publication date.
9. `reproduce.sh --episode` once → `results/episode/`, under its label; commit.
10. Separate-session recomputation (`review_recompute.py`, `REVIEW.md`), as Studies 001–007.
11. Forward record from the first signal date after step 8 (§11).

No step may be reordered. Steps 5–7 are the only times the author sees any new quantity before the note; the gate, the overlap and the volatility check show no rule return. Outcome rows in `trials.md` are appended, never written into an existing row.

## 15. Things this study deliberately does not do

As Study 007 §15, plus: it does not change the inflation measure, the lag rule, the rank windows, the minimum history, the era window, the gate's bounds or the family rule after this commit; it does not run the gate, the volatility check, the history or the episode twice; it adds no trial (in particular no forecast-based real yield, §5.5, and no 5-year yield change, `QUESTION.md` §1); it does not combine value with carry or trend; it places no paper order; it does not claim fidelity before 2003.

## 16. Amendments

(Append dated entries here; each must state what changed, why, which results had already been seen at the time, and the trial count N.)

- **2026-10-25 17:2x GMT, correction of a series ID before the data step's first CPI fetch (§14 step 2); results seen: none (the first data-step attempt stopped at an HTTP 404 before any CPI data was received; `trials.md`, data-step rows); N unchanged (3); family count unchanged (17).** Everywhere this document and `QUESTION.md` write `CPIAUCNSA`, read **`CPIAUCNS`**: FRED's ID for the consumer price index for all urban consumers, all items in U.S. city average, not seasonally adjusted, index 1982–84 = 100 (series page read 2026-10-25 17:24 GMT). The series meant was described in words in both documents and is unchanged; only the identifier was wrong (the author's error, not checked against FRED before the commit). `CPILFENS` was checked the same way and is correct. Original wording left as written; the code uses `CPIAUCNS`.

- **2026-10-25 18:3x GMT, two clarifications of §6.1 after the vintage and release-date check and before any inflation rate, real yield, rank or weight is computed (§14 step 2 done, code step not started); results seen: dates and flags only (`results/vintage_check.md`, `results/cpi_availability.csv`), no CPI level, inflation rate or return; N unchanged (3); family count unchanged (17).** (a) **Core CPI release dates where ALFRED holds no core vintage.** BLS publishes the all-items index and the index less food and energy in the same monthly release, so where `CPILFENS` has no ALFRED vintage (signal months 1969-07 to 1996-11) its availability follows the `CPIAUCNS` release read for the same signal date, instead of §6.1's "assumed known" branch. This changes one month: signal month **1996-01**, where the December 1995 index was not yet published at t (the release came after the signal date), so T1a uses k = 1995-11 there, as T1 and T1b do. Why: the registered fallback would let T1a use an index that the headline vintage shows was not yet public; the change can only remove look-ahead. The branch counts are reported both ways by the code step. (b) **Precedence for an index that was never published.** §6.1's missing-index rule (r undefined, the position held) applies whenever CPI(m − 1) is missing from the current file, i.e. was never published; the availability rule (k moves back to the latest month published by t) applies only when CPI(m − 1) exists in the current file but was published after t. This is the reading §6.1's own example already gives (the October 2025 index; episode signal month 2025-11 holds, as the data step listed), and it is written here because the availability rule read alone would have set k = 2025-09 for that month. In 1969–2018 the only late month is 1996-01, whose index exists, so the test window is governed by the availability rule alone; the episode's 2025-11 and the forward record's 2026-11 hold, unchanged.
