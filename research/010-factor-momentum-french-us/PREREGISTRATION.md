# Study 010: time-series factor momentum on four US equity factors, 1927–2026

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-10-26 (the commit's time is the record) |
| Status | pre-registered; **no file of the Kenneth French Data Library downloaded or read for this study; no factor return, formation return, position or rule return computed on any window** |
| Version | 1.0 (any change after this commit needs a dated amendment appended to §16 before any further step is run) |
| Study type | new family for the programme: first study that times an equity factor or uses this library ([`QUESTION.md`](QUESTION.md), commits `e699ac3` and `9cfd47f`; [`RESEARCH_AGENDA.md`](../../RESEARCH_AGENDA.md), dated additions of 2026-10-26) |
| Data | Kenneth French Data Library, US research factors (monthly): the 3-factor file (SMB, HML), the short-term reversal file (ST_Rev) and the long-term reversal file (LT_Rev); one snapshot (§5) |
| Instruments | none tradable: the factors are long-short portfolios outside the approved instruments. **No paper order and no paper sleeve**; a shadow forward record only (§11). |
| Approval | approved by the orchestrator under the owner's delegation of 2026-10-21 (all decisions on this research programme), on the date of this commit. An `APPROVED` file is written at implementation time (§14 step 4), after this commit, so that `reproduce.sh` keeps its refusal gate. |
| Total trial count registered | **3** (§7): T1 and its two fragility companions T1a and T1b |
| Deflated Sharpe ratio decided at | **N = 3** (§9.4; a new family); the programme-wide count, re-counted before the history run, reported beside it with no decision weight |
| Design review | a separate session reviewed this document before its first commit ([`DESIGN_REVIEW.md`](DESIGN_REVIEW.md)), the rule adopted after the second cold read |
| Author | the orchestrator (Qune) |

Nothing in this document reports or implies the performance of any rule registered here. The question note fixed the question, the source paper, the factor set, the trials, the windows, the window rule and the vintage plan; this document writes them out as rules. Where the two differ, this document governs and says why (§0).

---

## 0. Relationship to the question note, and what changes

Everything in `QUESTION.md` §1–§3 stands. This document adds what the note left open, each fixed now, before any data:

1. Benchmarks B0, B1, B3 and the decision difference d on every row (§9.1).
2. A cost model for the timing trades, base and stress (§6.3). The note had none.
3. Criteria C1–C4 in the programme's form (Study 001 §9.5), with C3 at N = 3 (§9.4–§9.5).
4. The verdict table with the note's window rule and fragility clause, and its precedence (§9.5).
5. Each trial's own window and factor entry dates (§7–§8): all three trials share the holding months of the decision row H.
6. The missing-value rule and the data step's checks (§5.3, §6.5).
7. **Change to the note's §3.2 ("commits them with a manifest"):** the downloaded files are **not** committed. The repository's rule since Study 001 keeps raw downloads out of git (`.gitignore`: `**/data/raw/`); the manifest with SHA-256, byte size, download time and the release line of each file's header is committed. Consequence, stated now: once the library publishes its next monthly rebuild, a later reader cannot download this snapshot again and may get other numbers (§10, row 1). The full-precision monthly series the history run writes (`results/history/`) are committed, so every published figure can be recomputed from them.
8. The forward record's timing, given that the library publishes with a lag, which trials it records and how it is scored (§11).
9. **Addition to the note's §2.2 programme-wide count:** besides `research/*/trials.md`, the count also reads the desk's private registry `ops/trading/research/trials.jsonl`, as Studies 007 and 008 did. That file is not public, so this part of the count cannot be checked by a reader (the second cold read said so); it is reported as a separate figure, and the count from the public logs alone is given beside it. Neither has decision weight.

## 1. Question

> Does holding each US equity factor long after a year in which it rose, and short after a year in which it fell, earn more than holding the same average position in each factor throughout, on 1927–2026?

## 2. Hypothesis and grounding

H1: the mean of d (T1 minus its exposure-matched benchmark B3, §9.1) over the decision row H is positive and large enough to meet C1–C4. H0: it is not.

Grounding: Ehsani and Linnainmaa (NBER WP 25551, 2019) [EL19], quoted in `QUESTION.md` §1: time-series factor momentum on up to 20 non-momentum factors earns 4.2% a year (t 7.04) over 1964-07 to 2015-12, beside 4.21% (t 7.60) for the equal-weight portfolio of the same factors. That figure is a long-short return, not a timing difference against an exposure-matched benchmark, so it is not the effect this study tests; its size says nothing about d.

Why it might not survive here: (a) four factors, not twenty, so d averages fewer bets; (b) 560 of H's months lie outside the paper's data window, and the paper's own months are mined by the literature that followed it; (c) before 1963 the library's universe is narrower (NYSE stocks only until AMEX joins CRSP in 1962: general knowledge, not read from the library for this note) and trading costs were higher; (d) the paper's own text says losers "earn premiums that are close to zero", so most of its gain may come from holding winners long, which B3 partly holds too.

### 2.4 Designer's prior knowledge (disclosed)

`QUESTION.md` §3.1 in full: the paper's positive result on 1964–2015; momentum's crashes in 1932 and 2009 [DM16]; value's long drawdown to 2020; size weak after the early 1980s; short-term reversal reported to weaken in recent decades; the 1929–32 fall. The author has not seen any of these factors' 12-month signs over 1928–1963 or 2016–2026. No episode was used to choose anything. The note's first paragraph repeats this disclosure in one sentence, whatever the verdict.

## 3. Literature

[EL19] source of the rule; [HOP17] (a century of trend on markets, the reason Mkt-RF is left out, `QUESTION.md` §1); [DM16] (momentum crashes, prior knowledge); [MM17] (the alternative not taken, `QUESTION.md` §4). All in the agenda's register, Crossref-checked (`tools/citations_check.txt`).

## 4. Instruments

None. The four factors are paper long-short portfolios. A result here, whatever it is, does not imply any order on the desk.

## 5. Data

### 5.1 Sources

Three monthly files from the Kenneth French Data Library, each downloaded **once** in the data step (§14 step 2): US Fama/French 3 factors (SMB and HML used; Mkt-RF and RF read only for their dates), short-term reversal factor (ST_Rev), long-term reversal factor (LT_Rev). The download links are read from the library's page at the data step and recorded in the manifest; the file names expected are `F-F_Research_Data_Factors_CSV.zip`, `F-F_ST_Reversal_Factor_CSV.zip` and `F-F_LT_Reversal_Factor_CSV.zip` (from general knowledge of the library; confirmed or corrected at the data step, an ID-only correction like Study 008's needing a dated §16 note, nothing else). Only the monthly section of each file is used; the annual section is not parsed. Values are percent a month.

### 5.2 Snapshot and vintage

As `QUESTION.md` §3.2, with item 7 of §0: one snapshot; the manifest records URL, SHA-256, byte size, download time (UTC) and the header line naming the CRSP release each file was built from; every history row uses that snapshot only; no second download before the history run. If the three files name different releases, the data step records it and the study proceeds (the library builds its files on its own schedule); the note states it.

### 5.3 What the data step may read

Dates and missing-value markers only: for each file, the first and last month of the monthly section, month gaps, the count and dates of missing-value markers (the library's codes −99.99 and −999), and the row count. To find the markers the parser compares each value field with −99.99 and −999 and records only whether it matched; **no factor value is written, printed or summarised.** From these it fixes and writes to `trials.md`: the last month common to the three files (H's end), the exact month counts of H, P1, L, P2 and P, each trial's first holding month per factor, and any missing month inside H.

### 5.4 Stop rules at the data step

The study stops for a dated §16 amendment, before any code is run on returns, if: a file's monthly section starts in any month other than the one `QUESTION.md` §1 states (SMB, HML 1926-07; ST_Rev 1926-02; LT_Rev 1931-01), earlier or later; H's end is before 2026-06; or any missing-value marker **or month gap** falls in the months a trial uses, that is from 1926-07 to H's end for SMB, HML and ST_Rev (the 12-month formation of H's first month starts in 1926-07) and from 1931-01 to H's end for LT_Rev. The entry dates of §6.2 are fixed by this document, not derived from the files. The amendment may only change how missing months are handled; it may not change the factor set, the formation windows or the windows of §8.

## 6. Exact rule specification

### 6.1 Signal

For factor k, month t and formation length L (12 for T1 and T1a, 6 for T1b): R_k,t = Π_{j=1..L} (1 + f_k,t−j / 100) − 1, the compounded return over months t − L to t − 1, no skipped month. Defined only when all L months exist for k. Position h_k,t = +1 if R_k,t > 10⁻¹², −1 otherwise (a formation return within floating-point error of zero, |R| ≤ 10⁻¹², is a tie and takes −1; ties are counted and reported). Computed in double precision from the snapshot's values as printed (two decimals in percent).

### 6.2 Rule return and the factors held

A factor is held in month t if R_k,t is defined and t is inside the trial's window. K_t = number of factors held in t. Rule return T_t = (1/K_t) Σ_k h_k,t f_k,t (percent a month; self-financing, no cash return added: each factor is a zero-investment long-short return). Factor entry in H (from the start dates of `QUESTION.md` §1, confirmed at the data step): T1 holds SMB, HML and ST_Rev from 1927-07 and LT_Rev from 1932-01 (K_t 3, then 4); T1a holds SMB and HML from 1927-07 (K_t 2); T1b (6-month formation) holds SMB, HML and ST_Rev from 1927-07 (their formation exists earlier, but H starts there) and LT_Rev from 1931-07 (K_t 3, then 4).

### 6.3 Costs (on the timing trades only)

A factor position of size |h| = 1 is one dollar long and one dollar short. Changing h_k from −1 to +1 or back trades 2 dollars on each leg, 4 dollars of notional per dollar of factor position. The cost charged in month t is c × (1/K_t) Σ_k 2 |h_k,t − h_k,t−1| (so 4c per flip, averaged over the factors held), deducted from T_t. A factor's first month in the window is charged as entering from zero (|h| traded on each leg, 2c). **Base c = 10 bp, stress c = 50 bp** of notional per dollar traded, one way; since T_t is in percent a month, c enters as 0.10 and 0.50. B1 and B3 hold constant positions and pay no timing cost. The reweighting when K_t changes (1932-01 in T1; 1931-07 in T1b) is not charged to T, B1 or B3.

Not charged, and why: the factors' own monthly rebalancing. It is paid by the rule on |h| = 1 in every factor every month and by B3 only on |h̄_k| ≤ 1, so leaving it out flatters d (§10, row 5). It is not modelled because the library publishes no turnover for these factors and any figure would be a guess; the stress row's fivefold timing cost is the only allowance. The costs are a convention of this study, not an estimate of what a fund would pay in any decade.

### 6.4 Engine

New code in `research/010-factor-momentum-french-us/src/` (signal, rule, benchmarks, costs, metrics); the shared library's Newey–West, deflated Sharpe, bootstrap and house-style chart functions (`qune_research/`), unchanged. Tests written with synthetic factor series before the history run, including: the ±1 versus {0, 1} identity of `QUESTION.md` §1, gross of costs (d exactly doubles; t and Sharpe unchanged; with costs the identity does not hold, since entry and flip costs do not halve in the same way); entry dates and K_t; formation without a skipped month; cost arithmetic per flip; h̄ frozen from H on every row.

### 6.5 Missing data

In any month a trial uses, including the formation months before H (from 1926-07; LT_Rev from 1931-01): the study stops (§5.4). Before those months: not used.

## 7. Registered trials (N = 3)

| ID | Rule | Window |
|---|---|---|
| T1 | SMB, HML, ST_Rev, LT_Rev; 12-month formation; monthly; equal weight over the factors held | H |
| T1a | SMB and HML only; otherwise T1 | H |
| T1b | the four factors; 6-month formation (t − 6 to t − 1); otherwise T1 | H |

T1a and T1b are fragility companions (`QUESTION.md` §2.1). Each is judged on its own C1–C4 on H against its own B3.

## 8. Windows and the role of each

All windows are holding months. h̄_k for B3 is computed once, per trial and per factor, over that factor's months in H, and is used unchanged on every row.

| Row | Months | Role |
|---|---|---|
| **H** | 1927-07 to the last common month of the snapshot (expected 2026-08) | **the decision row**: C1–C4 for each trial |
| P1 | 1927-07 to 1963-06 | before the paper's data; reported, no weight alone |
| L | 1963-07 to 2015-12 | the paper's US data window (its strategy months are 1964-07 to 2015-12); reported, no weight |
| P2 | 2016-01 to H's end | after the paper's sample; reported, no weight alone |
| **P** | P1 and P2 together | **the window rule** (§9.5): sign of mean(d^{T1}) only |

Power, from `QUESTION.md` §2.3 (`tools/power_study010.txt`): detectable Sharpe of d on H 0.285 (nw 1.00) to 0.316 (nw 1.108); P 0.416 / 0.461; P1 0.474 / 0.525; L 0.392 / 0.435; P2 0.870 / 0.964. The history cannot see an edge below about 0.29 Sharpe of d. These are the edges detectable at 80% power, not hard floors: a smaller edge can pass by chance and a larger one can fail. There is no out-of-sample window and no episode: the whole published history to the snapshot is in H. The forward record (§11) is the only clean test, and a weak one (§11).

## 9. Benchmarks, metrics and decision criteria

### 9.1 Benchmarks and the decision difference

- **B0**: zero (cash; the factors are excess returns).
- **B1**: every factor held long, h = +1, equal weight over the same factors held in each month as the trial (the paper's comparison).
- **B3^k**: each factor at the trial's own average position h̄ over H: B3_t = (1/K_t) Σ h̄_k f_k,t. h̄_k is the unweighted mean of h_k,t over factor k's months in H. h̄ uses the whole of H, a look-ahead in the benchmark only (Study 007's convention), disclosed. Because the weights are 1/K_t while h̄ is unweighted, d keeps a small static exposure to a factor when K_t varies over H (T1's first 54 months at K_t = 3; none in T1a, where K_t = 2 throughout); its size, Σ over H of (h_k,t − h̄_k)/K_t divided by H's month count, is reported per factor. If every h̄_k is exactly zero, B3 is identically zero and C1's B3 leg reads Sharpe(T) ≥ 0.10.
- **d_t^k = T_t^k − B3_t^k**, at base and at stress costs (only T pays costs).

### 9.2 Costs

§6.3.

### 9.3 Metrics

Study 001 §9.3, adapted: B0 is zero, so "excess return" is the series itself; turnover is reported as flips per factor per year and in total; hit rate (a) is the fraction of factor-months in which the sign held matched the sign of the factor's return (a month with f = 0 counts as a miss). Sharpe ratios are annualised (monthly mean / monthly sd × √12), Newey–West with a Bartlett kernel and 6 lags, as every earlier study.

### 9.4 Deflated Sharpe ratio

Study 001 §9.4's formula and variance floor, on each trial's monthly rule return T^k over H (the programme's convention; T includes the premium of the static position h̄, so C3 can pass partly on that premium, which is why C1 and C2 also test against B3), **at N = 3**: a new family (no earlier study timed an equity factor or used this library). Beside it, with no decision weight: the DSR at N = 10, and at the programme-wide count of every trial registered in `research/*/trials.md` and in the desk registry `ops/trading/research/trials.jsonl`, re-counted immediately before the history run and written to `trials.md` with the method of the count. The note says, before any result, that the sample was chosen after ten earlier studies on other questions and that only N = 3 decides.

### 9.5 Verdict table

For each trial k on H, at base costs: **C1** Sharpe(T^k) ≥ Sharpe(B1^k) + 0.10 and ≥ Sharpe(B3^k) + 0.10; **C2** Newey–West t of mean(d^k) ≥ 2.0; **C3** DSR(T^k) at N = 3 ≥ 0.95; **C4** the sign of mean(d^k) unchanged at stress costs.

**Window row (T1 only):** mean(d^{T1}) over P > 0 at base costs, with h̄ from H. Pass or fail on the sign; its Newey–West t is reported, not tested.

| Verdict (T1, the headline) | Condition |
|---|---|
| **Not supported** | Any of C1–C4 fails for T1 on H. |
| **Inconclusive (paper's window only)** | C1–C4 hold for T1, but the window row fails (mean of d over P ≤ 0). |
| **Inconclusive (fragile)** | C1–C4 and the window row hold, but T1a or T1b is "not supported" on its own C1–C4. |
| **Supported in history; forward record pending** | C1–C4, the window row and the companion clause hold. |

Precedence: not supported > inconclusive (paper's window only) > inconclusive (fragile) > supported. The companions' rows read "not supported" or "meets C1–C4". **Return-unit label:** if the minimum detectable mean of d^{T1} at 80% power on H (2.842 × the Newey–West standard error of mean monthly d × 12, at base costs) exceeds 2% a year, any row that is not "not supported" adds "(Sharpe units; the 2%-a-year bar not met)", as `QUESTION.md` §2.3 fixed. No sentence may call a result "supported" without "in history; forward record pending". The note's first paragraph carries the §2.4 disclosure in one sentence.

### 9.6 Pre-registered descriptive sub-analyses (no decision weight)

- P1, L, P2 and P for every trial: mean(d), Newey–West t, Sharpe of d, months.
- d by decade (calendar decades, the first and last partial), for T1.
- Per factor: mean of h_k (h̄_k), flips, the factor's own contribution to mean(d^{T1}) ((1/K_t)-weighted), with its t; no factor is dropped or reweighted after it is seen.
- **The paper's comparison:** T1's own return and B1's over the paper's strategy months 1964-07 to 2015-12 and over H, beside the paper's 4.2% (t 7.04) and 4.21% (t 7.60); a different factor set and construction, so descriptive only.
- The twelve worst months of d^{T1} with their dates, and d^{T1} in 1929-09 to 1932-12 and 2008-09 to 2009-12 (the episodes of §2.4, listed before any result so that the choice is not made after).
- Power, realised: observed NW/iid ratio of d, annualised sd(d), MDE at t = 2 and at 80% power, in % a year and in Sharpe of d.
- Charts to the house standard (`qune_research/style.py`): cumulative d^{T1} with P1/L/P2 marked; d by decade; per-factor contributions; the three trials on P1/L/P2.

### 9.7 What did not work

Study 001 §9.7, unchanged; an empty section is not acceptable.

## 10. Known pitfalls

| # | Pitfall | Handling |
|---|---|---|
| 1 | The library rebuilds its whole history monthly; numbers change with the release | one snapshot, hashes and release line in the manifest; raw files not committed (§0 item 7), full-precision outputs committed; the forward scoring reports a vintage row (§11) |
| 2 | L is the paper's sample and was mined by the literature after it | the window row on P (§9.5); L reported with no weight |
| 3 | The author knows the famous episodes (§2.4) | listed before any data; episode rows fixed now (§9.6) |
| 4 | The reversal factors are built from past stock returns, as momentum is | T1a without them (fragility clause) |
| 5 | Factor rebalancing costs not charged; they are larger for the rule (|h| = 1) than for B3 | disclosed in the note's limitations; stress costs fivefold on timing trades only; d at stress costs reported |
| 6 | Pre-1962 universe NYSE only, thinner and costlier markets | P1 reported separately; the note says the early factors are built on a narrower universe (general knowledge) |
| 7 | B3 uses h̄ over all of H (look-ahead in the benchmark) | disclosed; it is the same convention as Studies 007 and 008 |
| 8 | Formation "t − 12 to t − 1, no skip" is inferred from the paper's equation (1) example | `QUESTION.md` §1 labels it inferred; T1b moves the formation length; the skip is not tested |
| 9 | The reversal factors may be built differently from the paper's | `QUESTION.md` §1, disclosed, not adjusted |
| 10 | Ties (R = 0 exactly) | −1, fixed in §6.1; their count reported |
| 11 | A real-time investor would need the factor returns at each month end | the factors are built from CRSP data that exist at month end; the library's own publication lag affects only the forward record (§11) |
| 12 | The raw files sit on disk from the data step to the history run | only process stops anyone looking: the data step's parser writes dates and marker flags only, and no other script reads the files until `--history`; stated, not provable |

## 11. Forward record (shadow only; no paper order)

Trials recorded: T1, T1a and T1b; B1 as defined; B3 at h̄ frozen from H (as Study 008's frozen w̄), never re-estimated on forward months.

For each forward holding month t (the first is the month after the snapshot's last month), positions h_k,t are computed from the first release that contains month t − 1, and committed with that release's hash and the commit time. Because the library publishes with a lag, the commit will often come weeks into month t or later. That cannot be gamed: h_k,t is a mechanical function of returns to t − 1, so the timing of the commit selects nothing. **Every forward month is scored, whatever the commit time;** rows committed after the first release that contains month t are labelled "late" and counted, not dropped. The h scored is the committed h; the h recomputed from the scoring release is shown beside it as part of the vintage row.

Scoring after 60 holding months, from one release named at scoring, with the rules of §9.1 and §9.5 (C2 and C4 decide; C1 and C3 are reported), and a vintage row comparing that release with the snapshot over H's months. **Power, stated now:** over 60 months the detectable Sharpe of d at 80% power is 2.842 / √5 = 1.27 (1.41 at nw 1.108), about 4.5 times the history's detectable 0.285–0.316 and about four times the largest edge the programme has measured (the 006–008 pool's 0.321); the forward record can catch only a very large edge or a clear sign reversal, and its verdict is worded as a low-power check. Code (`forward010.py`) is written after the note, with tests, before the first forward month is due.

## 12. Risk limits

Not applicable: no order of any kind.

## 13. Repository layout

`research/010-factor-momentum-french-us/`: `QUESTION.md`, `QUESTION_REVIEW.md`, this file, `DESIGN_REVIEW.md`, `trials.md`, `data_step.py`, `src/`, `tests/`, `reproduce.sh` (refuses without `APPROVED`; `--history` runs once and refuses if `results/history/` exists), `results/` (manifest and data-step outputs; history outputs), `charts/`, `README.md`; `data/raw/` git-ignored.

## 14. Order of operations

1. This document and `trials.md`, reviewed for design by a separate session before commit; committed and pushed before step 2.
2. Data step, logged in `trials.md` before it runs: download once, manifest, dates and missing markers only (§5.3); outcome appended; stop rules (§5.4).
3. Code and tests on synthetic series; a separate-session code review before `APPROVED`.
4. `APPROVED` written and committed.
5. Programme-wide re-count (§9.4) and the history-run row in `trials.md`, committed and pushed.
6. `./reproduce.sh --history`, once; outputs committed whatever they show.
7. The note (README), §9.5 verdict, §2.4 disclosure first, §9.7.
8. Separate-session recomputation of every published figure from the committed outputs.
9. Charts, reviewed against the chart standard.
10. Forward record code and tests (§11).

Time labels are written from `git log` or the machine clock, never estimated.

## 15. Things this study deliberately does not do

It does not add factors after the data step, change the formation windows, drop a factor, test a skipped month, use the momentum factor or the market, use the global or developed-market files, or run any row on a second download. It does not claim anything for the paper's twenty-factor result.

## 16. Amendments

None.
