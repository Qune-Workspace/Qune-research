# Study 007 — Bond carry tilt by level on the long history (1974–2018): does the level of carry time duration beyond its sign, and does the 12-month trend add anything to it?

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-10-25 (the commit's time is the record) |
| Status | pre-registered; **no file read for this study, no carry, rank, trend or weight value computed on any window, no instrument return or rule return computed under this design** |
| Version | 1.0 (any change after this commit requires a dated amendment appended to §16 before any further step is run) |
| Study type | new study on the agenda's question 2 in its long-history form ([`QUESTION.md`](QUESTION.md), commit `7692356`; [`RESEARCH_AGENDA.md`](../../RESEARCH_AGENDA.md), dated additions of 2026-10-25); **second study on Study 006's leg and window after Study 006's results were published** (§0, §2.4, §9.4) |
| Instruments | Study 006's synthetic constant-maturity leg and synthetic cash from FRED for the test; IEF and BIL (approved under Study 001 on 2026-10-21) only in the gate, the 2019–2026 episode and the forward shadow record. **No paper order** (§11). |
| Approval | approved by the orchestrator under the delegation of 2026-10-21 (all decisions on this research programme), on the date of this commit. An `APPROVED` file is written at implementation time (§14 step 4), after this commit, so that `reproduce.sh` keeps its refusal gate. |
| Total trial count registered | **5** (§7): T1, its two fragility companions T1a and T1b, T2 and T3 |
| Deflated Sharpe ratio decided at | the **programme-level family count, 14 at registration** (§9.4), re-counted before the history run; N = 5 and N = 10 reported beside it |
| Author | the orchestrator (Qune) |

Nothing in this document reports or implies the performance of any rule registered here. No return of T1, T1a, T1b or T2 exists on any window. T3 is Study 003's rule word for word, and its path on IEF over 2003–2026 is published (§2.4); on the synthetic leg before 2003 it has never been computed. The question note (`QUESTION.md`) fixed the rule, the trials, the windows, the family-count criterion and the order of operations; this document writes them out as rules. Where the two differ, this document governs and says why (§0, item 11).

---

## 0. Relationship to Studies 001, 002, 003 and 006, and what changes

**Inherited unchanged from Study 001's pre-registration at commit `b6db436`**: the literature of §3 there, the FRED sources and the bill conversion (§5.1), the synthetic cash leg (§5.2, cash), the execution calendar and timing convention (§6.3: signal on the last FRED business day of the month on which every input exists, execution at the close of the first NYSE trading day strictly after it), the missing-data handling (§6.5), the carry definition of its trial T3 (§7), costs (§9.2: 2 bp a side base, 4 bp stress), the twelve metrics (§9.3), the deflated Sharpe ratio's method and variance floor (§9.4), criteria C1–C4 (§9.5), the "What did not work" requirement (§9.7) and the pitfalls table (§10).

**Inherited unchanged from Study 002 at commit `a2b713b`**, through Study 006's copy (006 §16, entries of 2026-10-25 02:2x): the duration leg (one 8.5-year par bond that ages and is repriced on a curve interpolated between DGS7 and DGS10) and the code that builds it.

**Inherited unchanged from Study 006's pre-registration at commit `a67ef8d` with its §16 amendments as committed at `7692356`**: the seven data files and the hash-check rule (§5.1 there), the vendor rule per holding period (§5.3.2), the gate's two statistics, their bounds and their derivation (§5.3.1, §5.3.3), the import-graph rule (§5.3.4, §13 test 1), the volatility check's bar and consequence (§5.4), the treatment of 2019–2026 as an episode run once (§8.2), the forward record (§11, including the five code decisions of the §16 entry of 2026-10-25 04:2x: when t is final, the execution date, a missed month, starting holdings, the shadow line), the no-paper-order rule (§11–§12), the repository layout and the order of operations pattern (§13–§14), and the lesson of its review: time labels from `git log`, trial-log rows appended and never rewritten.

The reader should open those documents for the inherited sections; they are not paraphrased so that nothing drifts. **What changes, and nothing else:**

1. **The rule** (§6): a fractional weight in the duration leg, the expanding percentile rank of the leg's carry, in place of a 0/1 switch on a sign.
2. **The trials** (§7): N = 5; Study 006's fragility rule applies to T1 through its two companions T1a and T1b only; T2 and T3 are secondary hypotheses with their own verdict rows, never promoted to the headline.
3. **Criterion C3 is decided at the programme-level family count** (§9.4), not at this study's N; 14 at registration.
4. **The gate** (§5.3) is Study 006's G1 with the trial's weight path w_t in place of h_t, computed once for each of the five weight paths; G2 is inherited as observed (0.131 on the same 192 periods) and not re-run as if new.
5. **Costs** (§6.4) are charged on the traded fraction of equity, which for a 0/1 path is Study 006's full switch and for a constant weight is Study 001's rebalancing drift; the switch-count rule becomes a turnover rule (§8.1).
6. **Benchmark B3 is per trial** (§9.1), at that trial's mean weight; B0, B1 and B2 are common.
7. **The test window** (§8.1) is 1974-07 to 2018-12, about 534 holding periods, shared by all five trials; the first 59 holding periods of Study 006's window fall outside it for every trial.
8. **The verdict table** (§9.5) carries the companion clause for T1, the turnover label and the volatility row.
9. **The forward record** (§11) writes the fractional weight, the carry, its rank and the number of months behind the rank, to four decimals.
10. **A fractional-weight engine** (§6.5, §13) is new code; it must reproduce Study 006's switching engine on a 0/1 path and Study 001's static benchmark on a constant path, period by period, before anything runs.
11. **Where this document differs from or is more specific than `QUESTION.md`**: (a) the **family count is 14, not 11**: the note counted Studies 006 (3) and 003 (3) and this study (5), and omitted Study 005's three trials, which are duration-timing rules on IEF over 2003-08 to 2018-12 (Study 003's exit conditioned on a regime variable) and fall inside the note's own definition; they are counted here (§9.4). (b) The rank's tie rule and denominator (§6.2), the trend signal's exact form on the synthetic indices (§6.3), the drift convention of the traded fraction (§6.4), T1b's window (§7), the first-period cost convention (§6.5) and the sub-analyses (§9.6) were not fixed in the note; they are fixed here. Nothing in the note is reversed.

## 1. Question

**Does scaling a long-only intermediate-duration position by the level of its carry (yield over bills plus roll-down, as defined by Koijen, Moskowitz, Pedersen and Vrugt [KMPV18]) improve risk-adjusted return over the same average exposure held throughout, after realistic costs, on 1974–2018; and does adding the 12-month trend rule to it add anything the carry level does not already give?**

The instrument is Study 006's synthetic 8.5-year leg against its synthetic cash over 1974-07 to 2018-12. The first half of the question is T1's verdict, the headline. The second is read from T2 against T1 and T3 (§9.6, attribution), each with its own secondary verdict row.

## 2. Hypothesis

- **H1 (T1):** the level of carry predicts the leg's excess return over cash over the next month, so that a weight rising with the carry's rank earns a higher Sharpe ratio than the same average weight held throughout, after costs (C1–C4 of Study 001 §9.5, with C3 at the family count).
- **H0 (T1):** the leg's excess return is not predictable from the carry's level beyond what its sign gives; the tilt's return equals the exposure-matched constant mix minus trading costs, and any Sharpe difference is within noise.
- **H1 (T2), secondary:** the equal blend of the carry weight and the 12-month trend signal earns a higher Sharpe ratio than its own exposure-matched mix, after costs. **H0 (T2):** it does not.
- **H1 (T3), secondary:** Study 003's 12-month trend rule, on the synthetic leg over the long history, meets C1–C4 against its own exposure-matched mix. **H0 (T3):** it does not.

### 2.1–2.3 Grounding, and why the edge might not survive

The grounding is the agenda's section on carry and bond-return predictability ([`RESEARCH_AGENDA.md`](../../RESEARCH_AGENDA.md); [CS91], [CP05], [KMPV18], [BPR18], [TV12]) and `QUESTION.md` §1: the predictive-regression reading says a steeper curve means more and a flatter curve less, which a sign switch cannot express. Reasons the edge might not survive, stated now: (1) [TV12]'s reading, that the predictability is concentrated in the inversions of the 1970s and early 1980s, in which case the level adds nothing to the sign and T1 fails where Study 006's T1 passed; (2) the rank rests on five to ten years of history in 1974–1979 and is noisy there; (3) a fractional weight trades every month, so costs are paid continuously rather than at switches; (4) after 2008 the carry's rank may sit near one for long stretches, in which case T1 is close to B1 and the differential is close to zero for a decade.

### 2.4 Designer's prior knowledge (disclosed; extends Study 006 §2.4)

The test window has been seen, and the form was chosen after seeing it (`QUESTION.md` §3.1). The author has read, and the reader should assume the author remembers:

- **Study 006's published results on this leg over 1969–2018** (`README.md`, `results/history/`, `results/episode/`, charts): the sign of carry (its T3: Sharpe 0.468, Newey–West t 1.91 against B3, C2 fail), the sign of the spread (T1: Sharpe 0.463 vs 0.338, t 2.06, 27 switches, w 0.8702), the 77 inverted month ends and their dates, the decade differentials, the three rate eras, the mechanism check, σ = 7.75% a year, and the 2019–2026 episode (T1 t −0.61 on actual IEF/BIL). **So the sign component of the carry tilt is known, and only the level component is open.**
- **Study 003's rule on IEF**: in-sample 2003–2018 (Sharpe 0.45 against 0.55, t 0.37), out of sample 2019–2026 (t 1.31, one exit in 2021–22), and its per-asset attribution inside Study 004 (the signal hurt IEF in 2004–2018 and helped in 2019–2026); Study 006's gate shows the synthetic leg tracks IEF closely over 2003–2018 (G1 0.008% a year, G2 0.131). **So the 2003–2026 part of T3's path is effectively known and only 1974-07 to 2002-12 (about 342 periods) is open.** T2 inherits both disclosures.
- **Study 005**: the trend exit's cost by stock–bond correlation regime over 2003–2018, which bears on T3's 2003–2018 path only.
- **General rate history**: that carry was larger in absolute terms before 1990 than after, and the inversion dates of Study 006 §2.4.
- **Not seen, by anyone**: any carry level or rank on any date, any weight path, G1 for a fractional weight, the leg's volatility over the 534 periods, T3's path before 2003, and any return of T1, T1a, T1b, T2 or of any benchmark at a fractional w̄.

Mitigations, all checkable: no parameter of T1 is a scale or threshold (the rank has none; the 60-month minimum is the smallest round figure covering one rate cycle and is moved both ways by the companions); T3 is Study 003's rule unchanged; T2's weights are one half each; each trial's B3 removes what Study 006 already showed about the leg's premium by era; C3 is decided at the family count; the episode is run once with no decision weight; the forward record is the only clean test.

### 2.5 What Study 006 taught, applied here

- A near miss on a sign switch (t 2.06 against t 1.97 and 1.91 for its variants) is the case the fragility rule was written for; here the companions move the rule's only free choice, not its signal.
- A gate that cannot see the rule's return stays a gate; the import-graph test is kept and extended to the new engine (§13).
- Trial-log rows are appended with a date and never rewritten in place; time labels come from `git log` (006 `REVIEW.md`, should-fix 1 and 2).

## 3. Literature

The agenda's [KMPV18], [BPR18], [BGHLS15], [CS91], [CP05], [TV12] and [ACM13], Crossref-checked on 2026-10-22 (`tools/citations_check.txt`); Study 001 §3 for the term-spread literature. No new references.

## 4. Instruments

No symbol is traded. IEF and BIL (approved 2026-10-21 under Study 001) appear only as data: in the gate (§5.3), the 2019–2026 episode (§8.2) and the forward shadow record (§11).

## 5. Data

### 5.1 Sources: no fetch; Study 006's seven files, reused byte for byte and hash-checked

`fred_DGS10.csv`, `fred_DGS7.csv`, `fred_DTB3.csv`, `tiingo_IEF_daily.csv`, `alpaca_IEF_1Day_all.csv`, `alpaca_BIL_1Day_all.csv`, `tiingo_BIL_daily.csv`, taken from Study 006's `data/raw/`, each copied into this study's `data/raw/` only after its SHA-256 matches Study 006's `results/data_manifest.json`; the match, the source and the time are written to this study's manifest. A mismatch stops the study before the gate. The vendor rule per holding period is Study 006 §5.3.2 as applied there (IEF: Alpaca from 2016-01-04, Tiingo before; BIL from the 2007-05 signal month, synthetic cash on both sides before). The forward record (§11) fetches new FRED and Alpaca data each month; nothing else is fetched.

### 5.2 Instruments

Duration leg: Study 002 §5.2, code at `a2b713b` as copied by Study 006, unchanged. Cash leg: Study 001 §5.2 (cash), unchanged. Both include today's expense ratios, as there.

### 5.3 The gate (signal paths and instrument returns only; no rule return)

#### 5.3.1 Quantities

Holding periods: Study 006's 192 overlap periods (execution dates from the first NYSE trading day of January 2003 to that of January 2019). For each period t and each trial k: w_t^k is the trial's weight in the duration leg for period t (§6; 0 or 1 for T3, fractional for the others), from FRED yields and the synthetic indices only; g_t = x_t(synthetic) − x_t(ETF) exactly as Study 006 §5.3.1, with its BIL-absent branch; w̄_o^k = mean of w_t^k over the 192 periods; e_t^k = (w_t^k − w̄_o^k) · g_t.

#### 5.3.2 Checks and bounds

| Check | Statistic | Bound | Status |
|---|---|---|---|
| **G1^k, bias**, each of the five trials | \|mean(e_t^k)\| × 12 | **≤ 0.18% a year** (Study 006 §5.3.3, unchanged) | computed once per trial |
| **G2, noise** | sd(g_t) / sd(x_t(ETF)) | ≤ 0.32 | **inherited as observed: 0.131 on the same 192 periods** (Study 006 `results/gate/gate.json`); it does not depend on the rule and is not re-run as if new. The gate script recomputes it from the copied files as a consistency check and must reproduce 0.131 to the committed precision, or the data step is wrong. |

Bounds compared at full precision; figures rounded once, after the comparison.

#### 5.3.3 Consequence

A trial whose G1 fails is dropped before any return is formed and its verdict row reads **"inconclusive (gate)"**; the others proceed. **If T1's G1 fails, the study halts permanently as inconclusive** before the volatility check and before any rule return. Nothing is re-run; no bound, vendor or construction changes.

#### 5.3.4 Reported beside the gate, no decision weight

w̄_o^k and the one-way turnover of each weight path on the overlap; mean(g_t) × 12; corr(g_t, x_t(ETF)); G1^k on 2003–2007 and 2008–2018 separately. The gate code never forms w·x on either series and never a rule or benchmark return.

#### 5.3.5 What the gate can and cannot show, and what the designer has seen

For T3 the gate is Study 006's G1 for a different h; its 2003–2018 holdings are effectively known (§2.4). For T1 the weight varies over 2008–2018, so G1 rests on more than Study 006's twelve cash months, but on the same single ETF; a pass says the construction's error is small where the rank moves, nothing more. Fidelity before 2003 is an assumption (Study 006 §5.3.5), stated here again.

### 5.4 Volatility check (once, after the gate, before any rule return)

σ = annualised standard deviation of x_t(synthetic) over the test window's holding periods (§8.1). Bar **10.18% a year**, consequence and the 1% statement as Study 006 §5.4; the code writes σ, the period count and the implied MDE at w = 0.5 (2% × σ / 10.18%) and nothing else. Expected from the committed 593-period figure (7.75%): below the bar; if the 534-period figure is above it, the "low-power check" label applies as registered.

### 5.5 Data availability

Dates only, from Study 006's manifest (verified at §14 step 2): DGS10 from 1962-01-02, DGS7 from 1969-07-01, DTB3 from 1954, all to 2026-10-19. The first carry is the signal date of 1969-07; the sixtieth is 1974-06, so T1's first weight is for the period executed on the first NYSE trading day of July 1974. T1a's first weight exists from 1972-06 and T1b's from 1979-06; T2's and T3's trend signal needs twelve prior signal dates and exists from 1970-07.

## 6. Exact rule specification

### 6.1 Carry

On each signal date t (Study 001 §6.3, requiring DGS10, DGS7 and DTB3 all present), c_t = (DGS10_t/100 − bey(DTB3_t)) + D_mod(DGS10_t) × (DGS10_t − DGS7_t)/300, exactly Study 001 §7's T3 signal as implemented in the copied `signal.carry` (Study 006 `src/signal.py`), read from the FRED files of §5.1. No smoothing.

### 6.2 Weight: expanding percentile rank, minimum history m

Let c_1, …, c_t be the month-end carries observed up to and including t, n_t = t. For n_t ≥ m,

w_t = ( #{s ≤ t : c_s < c_t} + ½ · #{s < t : c_s = c_t} ) / (n_t − 1),

the average-rank percentile of today's carry among all carries seen so far, in [0, 1]; before n_t = m no weight exists and no holding period is formed for that trial (its window starts at the first period for which it does). **m = 60 for T1, 36 for T1a, 120 for T1b.** No threshold, no scale, no smoothing, no volatility scaling. Why the rank and why expanding: `QUESTION.md` §1.

### 6.3 Trend signal (T2, T3)

On signal date t, with the synthetic duration-leg and cash total-return indices of §5.2 (daily, as built by the copied `synthetic.synthetic_indices`), the 12-month excess return is D(t)/D(t₋₁₂) − C(t)/C(t₋₁₂), where t₋₁₂ is the signal date twelve rows earlier in the execution calendar. h_t = 1 if it is positive, else 0. This is Study 003 §6.1 word for word with the synthetic indices in place of IEF's and BIL's adjusted closes and the calendar's signal dates in place of month-end closes; in the episode and the forward record the ETF closes are used, as Study 003 did. T3's weight is h_t; T2's is ½ w_t(T1) + ½ h_t.

### 6.4 Execution, sizing and costs

Weights are set at the close of the execution date following the signal date (Study 001 §6.3), 100% of equity between the two legs, monthly, no stops. The traded fraction at execution is |w_t − w̃_{t−1}|, where w̃_{t−1} is the previous weight after drifting with the two legs' returns over the period just ended (the convention of Study 001's static benchmarks, `backtest.run_static`); both sides pay the cost of Study 001 §9.2 on that fraction (base 2 bp, stress 4 bp). A full switch therefore costs what it cost in Studies 003 and 006, and a constant weight costs what B3 costs.

### 6.5 Engine

A new module `tilt.py` runs the monthly loop for a fractional weight path with the drift convention of §6.4, starting from the cash leg (weight 0) as the copied switching engine does, so the first period pays the cost of the first purchase. Before any run, tests prove (1) that a 0/1 weight path reproduces the copied `backtest.run_switching` period by period (holding, cost, return) and (2) that a constant weight path reproduces the copied `backtest.run_static` from the second period onward (the first-period purchase cost is the known difference between the switching engine and the static benchmarks, Study 006 §16 (e)). Benchmarks are computed by the copied `backtest.benchmarks`, unchanged.

## 7. Registered trials (N = 5)

| ID | Rule (§6) | Window | Role |
|---|---|---|---|
| T1 | carry tilt by expanding rank, m = 60 | 1974-07 to 2018-12 (the test window, §8.1) | **primary; the headline** |
| T1a | the same, m = 36 | the test window (its earlier weights, from 1972-07, are not used) | fragility companion of T1 |
| T1b | the same, m = 120 | **1979-07 to 2018-12** (about 474 periods: its first weight is 1979-06); T1 is reported on the same 474 periods beside it, descriptive | fragility companion of T1 |
| T2 | ½ T1's weight + ½ h_t (12-month trend) | the test window | secondary: carry plus trend |
| T3 | h_t, Study 003's rule unchanged | the test window | secondary: trend alone, the attribution T2 needs |

**Fragility rule, for T1 only** (Study 006 §9.5 as amended here): "supported in history; forward record pending" for T1 needs T1a and T1b each not "not supported" on their own criteria (T1b on its own window). T2 and T3 are separate hypotheses: each gets its own verdict row labelled secondary, no cross-trial rule applies between them and T1, and neither is promoted to the headline whatever it shows.

No other variants: no other minimum history, no trailing window, no scale, z-score or dead band, no other trend lookback, no other blend weight, no volatility targeting, no other maturity. Any addition is appended to `trials.md` with a date before it runs, and N increases.

## 8. Windows and the role of each

### 8.1 The test: 1974-07 to 2018-12, synthetic throughout

Holding periods from the first execution date of July 1974 (signal month 1974-06) to the period ending at the first execution date of January 2019 (signal month 2018-12): **about 534 periods, the exact count fixed by the data step (§14 step 2) before any weight is computed.** Criteria C1–C4 at base costs (§9.5). Each trial's B3 weight w̄ is its mean weight over its window, computed from signals only, frozen, and used unchanged in the episode and the forward record.

**Turnover rule** (replaces Study 003's switch count): a trial whose total one-way turnover Σ|w_t − w̃_{t−1}| over its window is below 8 (eight full switches) carries "low-powered" in its row.

Sub-windows, descriptive, no decision weight, reported not selected from: 1974-07 to 2002-12 and 2003-01 to 2018-12 (the gate's overlap); Study 006's three rate eras by execution month, 1974-07 to 1981-12, 1982-01 to 2008-12, 2009-01 to 2018-12.

### 8.2 2019-01 to 2026-09: an episode, not a test

93 holding periods, as Study 006 §8.2, **run once** after the history note is committed, with actual IEF and BIL from Alpaca and the synthetic series alongside; the rank history continues to expand through the episode (no re-estimation); B3 at each trial's frozen w̄. Reported under "2019–2026 episode (no decision weight)"; never quoted in a verdict sentence. Disclosed now: for T2 and T3 the trend part of this window is published (Study 003's out-of-sample run, Study 004's attribution), so for them the episode is a recomputation on a known window and is labelled as such.

### 8.3 The forward record: the only clean test

§11. Shadow only; scored once by a stopping rule.

## 9. Benchmarks, metrics and decision criteria

### 9.1 Benchmarks

B0 synthetic cash and B1 the synthetic duration leg (common); B2 50/50 rebalanced monthly (common); **B3^k per trial** at that trial's frozen w̄^k (§8.1), rebalanced monthly with costs by `backtest.run_static`. Every differential d_t^k = T_k − B3^k is against the trial's own B3.

### 9.2–9.3 Costs and metrics

Study 001 §9.2 and §9.3, unchanged: 2 bp base and 4 bp stress a side on the traded fraction (§6.4); the twelve metrics for the five trials and B0–B3, base and stress costs, on each trial's window, each sub-window and the episode; the stationary-bootstrap Sharpe interval and the Ledoit–Wolf test, descriptive.

### 9.4 Deflated Sharpe ratio, decided at the programme-level family count

**C3 is decided at the programme-level family count** (decision of `QUESTION.md` §2.2, stricter than the standing rule of 2026-10-24 under which the family figure is descriptive), because the test window is in-sample for the family (§2.4). The family: every trial of a duration-timing rule on the 7–10-year Treasury leg (IEF or the synthetic leg) over a window overlapping 1974–2018 whose return had been seen when this study's history step runs. **At registration, 14**:

| When | Where | Trials | Count |
|---|---|---|---|
| 2026-10-22 | Study 003 T1–T3, IEF 2003–2018 (`trials.md`) | 12-month trend, 12-1, 10-month moving average | 3 |
| 2026-10-23 | Study 005 T1–T3, IEF 2003-08 to 2018-12 (`trials.md`) | Study 003's exit conditioned on three regime variables | 3 |
| 2026-10-25 | Study 006 T1–T3, synthetic leg 1969–2018 (`trials.md`) | spread sign, 21-day mean, carry sign | 3 |
| this study | T1, T1a, T1b, T2, T3 | §7 | 5 |

Not counted, and why: Study 004's four portfolio trials hold IEF as one of ten assets and are not duration-timing rules on the leg; the desk's private registry's trend rows are on equities and crypto (`tools/tsmom_family_dsr.py`, re-checked before the run); Studies 001 and 002 registered trials and never ran them. The count is **re-counted immediately before the history run** from the desk's registry and the public trial logs and written to `trials.md`; any addition raises it. The DSR at N = 5 and N = 10 is reported beside it in every table. At about 534 months the DSR is barely sensitive to N (Study 006's at N = 10 was 0.997); this is stated for the principle, not as a safeguard that would bite. Variance floor as Study 001 §9.4.

### 9.5 Verdict table (criteria C1–C4 of Study 001 §9.5, C3 at the family count)

For each trial k on its window, at base costs: **C1** Sharpe(T_k) ≥ Sharpe(B1) + 0.10 and ≥ Sharpe(B3^k) + 0.10; **C2** Newey–West t (Bartlett, 6 lags) of mean(d^k) ≥ 2.0; **C3** DSR(T_k) at the family count ≥ 0.95; **C4** the sign of mean(d^k) unchanged under stress costs.

| Verdict (T1, the headline) | Condition |
|---|---|
| **Inconclusive (gate)** | G1 for T1 fails (§5.3.3). No rule return is computed. |
| **Not supported** | Any of C1–C4 fails for T1. |
| **Inconclusive (fragile)** | C1–C4 hold for T1, but T1a or T1b is "not supported" on its own criteria. |
| **Consistent with an edge, not detectable at the 2% bar** | C1–C4 hold for T1, neither companion is "not supported", and σ > 10.18% (§5.4). |
| **Supported in history; forward record pending** | C1–C4 hold for T1, neither companion is "not supported", and σ ≤ 10.18%. |

T2 and T3, each in its own row labelled **secondary**: "inconclusive (gate)", "not supported", "consistent with an edge, not detectable at the 2% bar" or "supported in history; forward record pending" by the same conditions without the companion clause. Precedence: not supported > inconclusive (either kind) > consistent > supported. "Low-powered" is added to any row whose trial fails the turnover rule. No sentence may call a result "supported" without "in history; forward record pending" until the forward record is scored. Whatever the verdict, the note's first paragraph carries the disclosure of §2.4 in one sentence: the window had been seen by Study 006 and the trend's 2003–2026 path by Studies 003 and 004.

### 9.6 Pre-registered descriptive sub-analyses (no decision weight)

- The sub-windows of §8.1, metrics 1–7, for every trial.
- **Attribution:** mean(d) and its t for T2 beside T1 and T3 on the common window, and the correlation of T1's and T3's weight paths; the note answers the question's second half from these three rows and nothing else.
- **Mechanism check (the level, not the sign):** the leg's mean excess return over cash in the periods grouped by the quintile of T1's weight (five rows, reported in full, not selected from), and separately in the periods with c_t ≤ 0 against the others (Study 006's mechanism check for carry).
- The observed Newey–West to i.i.d. ratio of d beside the assumed 0.972; the realised sd(w_t − w̄) beside the 0.5 and 1/√12 figures of §11.4.
- Charts to the house standard (`qune_research/style.py`): the carry with T1's weight path; T1 against B1 and B3, growth and drawdown; the differential by decade; T1, T2 and T3 by sub-window.

### 9.7 What did not work

Study 001 §9.7, unchanged; an empty section is not acceptable.

## 10. Known pitfalls

Study 001's and Study 006's tables apply. Rows that change or are added:

| Pitfall | Treatment |
|---|---|
| The window has been seen and the form was chosen after seeing it | Disclosed in §2.4 and the note's first paragraph; no scale or threshold in T1; C3 at the family count (§9.4); only the forward record is clean (§11). |
| A second study on the same leg does not pay for the first | Family count of 14 at registration, re-counted before the run, decides C3. |
| The rank's minimum history is a free choice | It is the only one, and T1a and T1b move it both ways under the fragility rule (§7). |
| A fractional rule hides its costs in small monthly trades | Costs on the traded fraction with drift (§6.4); turnover reported and the low-powered label tied to it (§8.1). |
| The new engine differs from the frozen one | Two equality tests before any run (§6.5, §13). |
| The gate is re-run until it passes | One attempt per trial; G2 inherited; T1's failure halts the study (§5.3.3). |
| T3's 2003–2018 path is known | Disclosed; only its pre-2003 path is open (§2.4); secondary row only. |
| 2019–2026 is known history | Episode only, run once, no decision weight (§8.2). |
| Choosing when to score the forward record | Stopping rule fixed now (§11.3). |

## 11. Forward record (no paper order)

No paper order is placed under this study (Study 006 §11, unchanged). Study 006 §11.1–11.5 and the five code decisions of its §16 entry of 2026-10-25 04:2x apply with these changes only:

- **11.1 Start.** The first signal date after the history note (§14 step 8) is committed: 2026-10-30 if the note is committed before 21:15 UTC that day, otherwise 2026-11-28. Never backdated; a missed month is logged as missed and never filled.
- **11.2 Decision record.** For each signal date: DGS10, DGS7 and DTB3 from FRED (the wait rule of Study 006), c_t, the rank's history length n_t, w_t for T1, T1a and T1b, h_t and T2's weight, all to four decimals, every input hash and the UTC time written. Starting weights before the first record are the five trials' weights at the 2026-09 signal date computed from the study's frozen files at the episode step; they are written in the first record.
- **11.3 Monthly line and stopping rule.** `paper-log/shadow.csv`: IEF and BIL holding-period returns from Alpaca `adjustment='all'` closes, the five trials and B1–B3 (each trial's frozen w̄) at base costs, and d_t = T1 − B3^T1. Interim figures under **"Not yet scored"** only. **Scored once, after 60 holding periods**; the scoring date is written in that month's decision record before any statistic is computed.
- **11.4 Forward verdict**, Newey–West t at 6 lags on d_t, rows as Study 006 §11.4 ("not testable" if sd(w_t) over the 60 periods is zero; "supported (forward)" mean(d) > 0 and t ≥ 2.0; "refuted (forward)" t ≤ −2.0; "inconclusive (forward)" otherwise, with the detectable effect size), and "low-powered" if the 60-period turnover is below 8. **Power, stated now** from the committed figures (K = 2.842, Newey–West factor 0.972, σ = 7.75%): over 60 periods the C2-bar MDE is **0.62 Sharpe or 4.8% a year at sd(w − w̄) = 0.5**, and **0.36 Sharpe or 2.8% a year at the uniform-rank dispersion 1/√12**; the forward record is weak and is the only test in which the rule was fixed before the data existed. A forward verdict is reported beside the history verdict, never instead of it.
- **11.5 Published every month:** the decision record, the shadow line, the interim figures under their label, and `make dashboard` output once a shadow line exists.

## 12. Risk limits

None needed: no order is placed. Study 003's sleeve and the desk's limits are untouched.

## 13. Repository layout

`research/007-bond-carry-tilt-long-history/`:

- `src/`: Study 006's `src/` as committed at `7692356`, copied with attribution and **unchanged** (Study 002's construction, signal, calendar, engine and statistics; Study 006's `config006.py`, `gate.py`, `volcheck.py`, `history.py`, `episode.py`, `forward.py`); new modules `config007.py` (windows, m for each trial, the family table of §9.4, bounds inherited by import from `config006`), `carry_rank.py` (§6.1–6.3: carry at signal dates, expanding rank, trend signal; imports only the signal, calendar, synthetic and data-reading modules), `tilt.py` (§6.5), `gate007.py` (§5.3: wraps Study 006's `gate.gate_statistics` with w in place of h; imports nothing from `backtest.py` or `tilt.py`), `volcheck007.py`, `history007.py`, `episode007.py`, `forward007.py`.
- `tests/`: Study 006's tests re-run unchanged where the code is copied (its four `reproduce.sh` mode tests are replaced by the same two gates for this study's modes), plus at least: (1) `gate007.py`, `carry_rank.py` and `volcheck007.py` import nothing from `backtest.py` or `tilt.py`, directly or through another module; (2) the rank on constructed carries: monotone in c_t, in [0, 1], the tie rule, no weight before n_t = m, and no look-ahead (changing c_{t+1} does not change w_t); (3) the trend signal on constructed indices reproduces Study 003's rule, incl. the twelve-row lag; (4) `tilt.py` equals `run_switching` on a 0/1 path and `run_static` from the second period on a constant path, to machine precision, with and without costs; (5) the turnover statistic on constructed paths; (6) G1 for a fractional w on constructed series, incl. mean(e) = 0 for a constant g; (7) the volatility output contains σ, the count and the MDE and nothing else; (8) the look-ahead test of Study 001 §6.3 on every weight path.
- `reproduce.sh` with `--gate`, `--volcheck`, `--history`, `--episode`; each refuses without `APPROVED` and refuses a second run when its output folder exists.
- `results/{gate,volcheck,history,episode}/`, `data/raw/`, `results/data_manifest.json`, `paper-log/`, `trials.md`, `README.md`, `REVIEW.md`, `review_recompute.py`.

## 14. Order of operations

1. Commit this document and `trials.md`; push (pre-push scan). No file read, no value computed.
2. Data step: hash-check and copy the seven files (§5.1), record dates only (first and last bars; the first signal date of each trial by §5.5; the exact period count of §8.1) in the manifest and `trials.md`; commit.
3. Implement `src/` and `tests/`; the copied tests pass unchanged and the new tests pass; commit. No real-data run.
4. `APPROVED`; trial-log row for the gate written **before** the run; commit.
5. `reproduce.sh --gate`, **once** (five G1 figures, G2 reproduced); commit the outputs whatever the outcome. Halt or proceed (§5.3.3).
6. Trial-log row, then `reproduce.sh --volcheck` once; commit σ, the count and the MDE.
7. Family re-count written to `trials.md` and `config007.py`; run rows for T1, T1a, T1b, T2, T3 appended before the run; `reproduce.sh --history` once → `results/history/`; commit.
8. `README.md`: verdict per §9.5 for T1 and the secondary rows, the first-paragraph disclosure, the attribution and mechanism rows, "What did not work", the observed NW factor and sd(w − w̄), the DSR at 14, 5 and 10; commit. This is the publication date.
9. `reproduce.sh --episode` once → `results/episode/`, under its label; commit.
10. Separate-session recomputation (`review_recompute.py`, `REVIEW.md`), as Studies 001–006.
11. Forward record from the first signal date after step 8 (§11).

No step may be reordered. Steps 5–7 are the only times the author sees any new quantity before the note; the gate and the volatility check show no rule return. Outcome rows in `trials.md` are appended, never written into an existing row.

## 15. Things this study deliberately does not do

As Study 006 §15, plus: it does not change the rank's definition, the minimum histories, the blend weight, the gate's bounds or the family rule after this commit; it does not run the gate, the volatility check, the history or the episode twice; it adds no trial; it does not test carry across maturities, a carry-sign switch, a dead band, a z-score or the affine term-premium control [ACM13] (`QUESTION.md` §4); it places no paper order; it does not claim fidelity before 2003; it does not promote T2 or T3 to the headline.

## 16. Amendments

(Append dated entries here; each must state what changed, why, which results had already been seen at the time, and the trial count N.)

- **2026-10-25 12:3x London, sequencing of §14 step 3 (implementation); results seen: none (no gate, volatility, history or episode figure exists; no carry, rank or weight computed on any date); N unchanged (5).** `src/forward007.py` (§11, the forward record) is implemented after the history note and before its first use at step 11, not within step 3. Reason: it needs no result of steps 5–9 except the frozen weights and the starting holdings that the episode writes, and its specification (§11, with Study 006's five code decisions) is complete; building it last keeps step 3 to the modules that steps 5–9 run. Nothing in §11 changes; the start date rule of §11.1 stands. Also recorded: the mechanism check's quintiles (§9.6) are five equal-count groups by the rank of T1's weight with ties broken by order, so that long runs of w = 1 still split; the gate's G2 reproduction (§5.3.2) compares to Study 006's committed full-precision figure 0.13140878732605116 with a tolerance of 1e-12; the episode's trend on the actual side reads the ETF index at the last bar on or before each signal date, with the twelve earlier signal dates taken from the schedule (§6.3). These are code decisions inside the registered rules, written down before any run.

- **2026-10-25 12:3x London, disclosure after the gate (§14 step 5); results seen: the gate outputs only (`results/gate/`, code `96af276`): five G1 figures, G2, the weight paths on the 2003–2018 overlap; no return of any rule or benchmark; N unchanged (5).** The gate's `periods.csv` shows T1, T1a and T1b with identical weights on every overlap period. This is an identity of the registered rule, not a data fact: §6.2's expanding rank at month t depends on all carries up to t and not on the minimum history m once n_t ≥ m, so m fixes only the first month a weight exists. On the test window (§8.1, from 1974-07, where n_t ≥ 60 > 36) **T1a's weight path equals T1's at every period, and T1b's equals T1's on T1b's own window from 1979-07**; the companions differ from T1 only by window, not by weight. The author did not see this at registration (§7 presents m as "the rule's only free choice" and expects the companions to "move it both ways"). **Nothing is changed**: no trial is added, removed or redefined, N stays 5, the family count stays 14, and the verdict table of §9.5 is applied as written. What this means for the reader, stated now: the fragility clause for T1 rests on T1b alone (the same rule on 474 of the 534 periods), T1a's row will reproduce T1's figures exactly and carries no information, and a "supported in history" verdict for T1 is therefore weaker than the registered text implies. This is recorded here before the volatility check and before any rule return exists.

- **2026-10-25 14:21 GMT, clarification before the first forward record (§14 step 11); results seen: the history and episode outputs as published; no forward data exist and no forward-month carry, rank or weight has been computed; N unchanged (5).** `src/forward007.py` implements §11 on top of Study 006's copied `src/forward.py` (unchanged; its clock gates, execution-date rule, missed-month rule, wait log and record writer are reused as fixed by Study 006 §16 of 2026-10-25 04:2x, points (a)–(c)) and fixes six points §11 leaves to the code, decided now, before any forward input is fetched. (a) **When t is final.** Study 006's rule applied to all three FRED series (DGS10, DTB3 and DGS7, one H.15 release), and both ETFs must have a bar on or after t (the trend reads the close of t). (b) **Rank history.** The carries of 1969-07 to 2026-09 are the frozen files' (the episode's 687, so the history the rank expands is the one already published, never re-estimated from a later fetch); each forward month adds the carry on its own signal date from the fetched files, observations dated on or before t only; a test proves that a fetch disagreeing with the frozen files before 2026-10 changes nothing. (c) **Trend.** h_t from the IEF and BIL `adjustment='all'` closes read at the last bar on or before each of the signal dates t−12 … t (§6.3); bars fetched from 2025-01-02; signal dates to 2026-09 are the frozen schedule's. (d) **Rounding.** Weights are written to four decimals (§11.2) and the shadow line uses the written values; c_t is written at full precision. (e) **Holds.** A trial whose weight is undefined on t (carry: DGS7 missing on a forward signal date, T1, T1a, T1b and T2; trend: an ETF index undefined, T2 and T3) holds its position: no trade, the weight drifts with the two legs (traded fraction zero). (f) **Starting weights and the shadow line.** The starting weights are `results/episode/summary.json`'s 2026-09 weights (T1, T1a, T1b 0.4111; T2 0.2055; T3 0), written in the first record and used as each trial's weight before its first execution, without drift over 2026-10-01 to the first execution date (that period belongs to no record, Study 006 §16 (d)). Each line is the last row of `tilt.run_tilt` (base cost 0.02% a side) and `backtest.benchmarks` (each trial's B3 at its frozen w̄ from `results/history/summary.json`) run on every forward period so far, with earlier periods' IEF and BIL returns read from the lines already written; d = T1 − B3^T1. §11.4's "not testable" is sd(w_T1) = 0 over the block and "low-powered" a block turnover of T1 (sum of traded fractions) below 8. No rule, bound, window or criterion changes. 14 tests in `tests/test_forward007.py` (256 in the study's suite).

- **2026-10-25 14:32 GMT, after a separate code review of `src/forward007.py` and before any forward input is fetched; results seen: none new; N unchanged (5).** A Tester agent that did not write the code (Opus 5.5, isolated, constructed data only) returned FAIL with one must-fix; report and response in `paper-log/CODE_REVIEW.md`. Changes to the entry above: (a) is tightened: t is final only when every FRED series has a row on t itself (empty or not), as well as on every later weekday; without this, a 2026-10-30 t with DGS7 not yet posted would have written a record holding T1, T1a, T1b and T2 for good. (e) is narrowed: a carry trial holds only when the carry on t is undefined; a forward month whose carry is undefined is left out of the rank history (n counts defined carries) and named in the record, instead of holding every later month. §11.4's "not testable" is read from T1's targets in the records of the block (holds left out), not from the drifted weights. Every record also hashes the frozen `data/raw/fred_*` files and `results/episode/summary.json`, and lists the carry of every forward month it ranked on. No rule, bound, window or criterion changes. 17 tests in `tests/test_forward007.py` (259 in the study's suite).

- **2026-10-25 17:2x GMT, precision found while writing Study 008's pre-registration; results seen: none new; N unchanged (5).** §11.1's fallback date "2026-11-28" (also in `QUESTION.md` §3.3) is a Saturday; the November 2026 signal date under Study 001's calendar is the last FRED business day of the month, expected 2026-11-30. The branch does not apply: the history note was committed on 2026-10-25, before 2026-10-30 21:15 UTC, so the forward record starts with the 2026-10-30 signal date. The code takes signal dates from the calendar rule, not from this text, so nothing in the code changes. Original wording left as written.
