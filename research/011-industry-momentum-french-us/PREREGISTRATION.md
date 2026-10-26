# Study 011: industry momentum on US industries outside Moskowitz and Grinblatt's sample, 1927–1963 and 1995–2026

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-10-26 (the commit's time is the record) |
| Status | pre-registered; **no industry file of the Kenneth French Data Library downloaded or read for this study; no industry return, formation return, rank, position or rule return computed on any window** |
| Version | 1.0 (any change after this commit needs a dated amendment appended to §16 before any further step is run) |
| Study type | new family for the programme: first study that ranks industries ([`QUESTION.md`](QUESTION.md), commit `7c0c156`; [`QUESTION_REVIEW.md`](QUESTION_REVIEW.md); [`RESEARCH_AGENDA.md`](../../RESEARCH_AGENDA.md), dated additions of 2026-10-26) |
| Data | Kenneth French Data Library, US 17 and 30 industry portfolios, value-weighted, monthly; one snapshot (§5) |
| Instruments | none tradable: a long-short of US industries is outside the approved instruments. **No paper order and no paper sleeve**; a shadow forward record only (§11). |
| Approval | approved by the orchestrator under the owner's delegation of 2026-10-21 (all decisions on this research programme), on the date of this commit. An `APPROVED` file is written at implementation time (§14 step 4), after this commit, so that `reproduce.sh` keeps its refusal gate. |
| Total trial count registered | **3** (§7): M1 and its two fragility companions M1a and M1b |
| Deflated Sharpe ratio decided at | **N = 3** (§9.4; a new family); the programme-wide count, re-counted before the history run, reported beside it with no decision weight |
| Design review | a separate session reviewed this document before its first commit ([`DESIGN_REVIEW.md`](DESIGN_REVIEW.md)) |
| Author | the orchestrator (Qune) |

Nothing in this document reports or implies the performance of any rule registered here. The question note fixed the question, the source paper, the industry sets, the trials, the windows, the window rule and the vintage plan; this document writes them out as rules. Where the two differ, this document governs and says why (§0).

---

## 0. Relationship to the question note, and what changes

Everything in `QUESTION.md` §1–§3 stands. This document adds what the note left open, each fixed now, before any data:

1. The benchmark and the decision difference on every row (§9.1): d is the zero-investment rule return itself, against zero.
2. A cost model for the cohort trades, base and stress (§6.3). The note had none.
3. Criteria C1–C4 in the programme's form (Study 001 §9.5), adapted to a zero-investment rule, with C3 at N = 3 (§9.4–§9.5).
4. The verdict table with the note's window rule and fragility clause, and its precedence (§9.5).
5. The Newey–West estimator on the two-stretch decision row O (§9.3).
6. Ranking ties and an empty leg (§6.1, §6.5).
7. **Change to the note's §3.2 ("commits them with a manifest"):** the downloaded files are **not** committed, as in every study since 001 (`.gitignore`: `**/data/raw/`); the manifest with SHA-256, byte size, download time and the release line of each file's header is committed, and the full-precision monthly series the history run writes are committed, so every published figure can be recomputed from them. Once the library publishes its next rebuild, a later reader cannot download this snapshot again (§10, row 1).
8. The forward record's timing and scoring (§11), as Study 010's.
9. **Two departures from the note's §1 eligibility sentence:** the stop of §5.4 covers every ranking month whose cohort is held in any row, not only decision-window months (stricter); and the remedy after a stop is a dated §16 amendment limited as §5.4 says, where the note left it to "the pre-registration".
10. The programme-wide count also reads the desk's private registry `ops/trading/research/trials.jsonl`, as Studies 007, 008 and 010 did; it is reported as a separate figure beside the count from the public logs alone. Neither has decision weight.

## 1. Question

> Does holding the three US industries with the highest past six-month return long and the three with the lowest short, each cohort held for six months, earn a positive return over the months outside Moskowitz and Grinblatt's 1963–1995 sample (1927–1963 and 1995–2026)?

## 2. Hypothesis and grounding

H1: the mean of d^{M1} (§9.1) over the decision row O is positive and large enough to meet C1–C4. H0: it is not.

Grounding: Moskowitz and Grinblatt (1999) [MG99], quoted in `QUESTION.md` §1: the same rule on 20 value-weighted two-digit SIC industries earns 0.43 percent a month over July 1963 to July 1995 (its t-statistic unread here).

Why it might not survive here: (a) the library's industries are four-digit SIC groups reassigned once a year, not the paper's 20 groups formed monthly, so this is a variant (`QUESTION.md` §1, check (c)); (b) O excludes the paper's months, and the months after it are the period in which the rule was public from 1999; (c) before 1963 the universe is narrower (NYSE only until AMEX joins CRSP in 1962: general knowledge, not read from the library) and industries are thinner and costlier to trade; (d) the paper reports industry momentum dissipating after 12 months and reversing at long horizons, a reversal it calls economically small; a six-month hold lies inside the horizons it reports as profitable, so this is not a reason the rule should fail, only a reminder that the effect has a horizon.

### 2.4 Designer's prior knowledge (disclosed)

`QUESTION.md` §3.1 in full: [MG99]'s result on 1963–1995; later uses of the library's pre-1963 industry months for related rules (check (a), search summaries only, including a ranking study on 10 industries from 1926); momentum's crashes in 1932 and 2009 [DM16]; the 1929–32 fall; lower post-publication returns for published anomalies in general. The author has not seen any industry's six- or twelve-month return over 1926–1963 or 1995–2026, nor any ranking on them. No episode was used to choose anything. The note's first paragraph repeats this disclosure in one sentence, whatever the verdict.

## 3. Literature

[MG99] source of the rule; [DM16] (momentum crashes, prior knowledge). Both in the agenda's register, Crossref-checked (`tools/citations_check.txt`). The sources of check (a) are known from abstracts or search summaries only and are not added to the register until read.

## 4. Instruments

None. The rule is a paper long-short of industry portfolios. A result here, whatever it is, does not imply any order on the desk.

## 5. Data

### 5.1 Sources

Two monthly files from the Kenneth French Data Library, each downloaded **once** in the data step (§14 step 2): the 17 industry portfolios and the 30 industry portfolios. The download links are read from the library's page at the data step and recorded in the manifest; the file names expected are `17_Industry_Portfolios_CSV.zip` and `30_Industry_Portfolios_CSV.zip` (general knowledge of the library; confirmed or corrected at the data step, an ID-only correction needing a dated §16 note, nothing else). Only the section of average value-weighted returns, monthly, is used; no other section (equal-weighted returns, annual returns, firm counts, sizes, book-to-market) is parsed. Values are percent a month.

### 5.2 Snapshot and vintage

As `QUESTION.md` §3.2, with item 7 of §0: one snapshot; the manifest records URL, SHA-256, byte size, download time (UTC) and the header line naming the CRSP release each file was built from; every history row uses that snapshot only; no second download before the history run. If the two files name different releases, the data step records it and the study proceeds; the note states it.

### 5.3 What the data step may read

Dates, column names and missing-value markers only (each field compared as a stripped string with "-99.99", "-999" and "", so no value is parsed as a number): for each file, the industry column names in order, the first and last month of the value-weighted monthly section, month gaps, the row count, and per month the number of industries whose field is not a missing-value marker (the library's codes −99.99 and −999, or empty). The parser records only whether each field matched a marker; **no return value is written, printed or summarised.** From these it fixes and writes to `trials.md`: the last month common to the two files (O's and the full history's end), the exact month counts of I1, I2, O, M and the full history for each trial, the industry counts and names, and each month's eligible count where it is below the full set.

### 5.4 Stop rules at the data step

The study stops for a dated §16 amendment, before any code is run on returns, if: either file's value-weighted monthly section starts in any month other than 1926-07, earlier or later; the 17-industry file has other than 17 industry columns, or the 30-industry file other than 30; the last common month is before 2026-06; there is a month gap, a duplicated month or a month out of order from 1926-07 to that month; the value-weighted monthly section's header is missing or renamed beyond a whitespace difference; or, at any ranking month m whose cohort is held in any row (M1 and M1a from 1926-12, M1b from 1927-06, to the month before the last common month), fewer than 12 of the 17 (fewer than 20 of the 30) industries are eligible under §6.1, counted from the marker flags alone for F = 6 and F = 12. Fewer missing markers than that do not stop the study; they are handled by §6.5 and reported, with the per-month count of industries that have a value. The amendment may only change how missing months are handled; it may not change the industry sets, the share, the formation or holding lengths, or the windows of §8.

## 6. Exact rule specification

### 6.1 Signal and cohorts

For industry i, end of month m and formation length F (6 for M1 and M1a, 12 for M1b): R_i,m = Π_{j=0..F−1} (1 + r_i,m−j / 100) − 1, the compounded return over months m − F + 1 to m, that is formation t − F to t − 1 for a first holding month t = m + 1; no skipped month. R_i,m is defined only when all F months have a value for i; an industry with R_i,m defined is **eligible** at m. The eligible industries are sorted on the key (−round(R_i,m, 10), column index in the file), so that returns equal to ten decimals are ordered by column, earlier first; adjacent pairs within 10⁻¹² at the boundaries between the n-th and (n + 1)-th place from either end are counted and reported. W(m) is the first n and L(m) the last n of that order, n = 3 for M1 and M1b (17 industries) and n = 5 for M1a (30 industries). The library's "Other" group is ranked like any industry. Computed in double precision from the snapshot's values as printed.

### 6.2 Rule return

Cohort m is held in months m + 1 to m + 6. In month t the six cohorts m = t − 1, …, t − 6 are held, each with weight 1/6. Cohort m's return in t is c_m,t = mean of r_i,t over W(m) minus mean of r_i,t over L(m), each mean over the members with a value in t (§6.5). The rule return before costs is

  d_t = (1/6) Σ_{j=1..6} c_{t−j},t   (percent a month; zero investment, no cash return).

A month t is a holding month of a trial only when all six cohorts exist: from 1927-06 for M1 and M1a (first cohort ranked at the end of 1926-12) and from 1927-12 for M1b (first cohort ranked at the end of 1927-06).

### 6.3 Costs

Each month the book is reset to its target weights: w_i,t = (1/6) Σ_{j=1..6} [ (1/n) 1{i ∈ W(t−j)} − (1/n) 1{i ∈ L(t−j)} ], so an industry in several cohorts or in both legs of different cohorts nets. Cost in month t = c × Σ_i |w_i,t − w_i,t−1| (one-way notional traded per dollar on each side), deducted from d_t; the first holding month is charged from zero weights. w_i,t follows this nominal formula whatever values are missing in month t, and a cohort with an empty leg (§6.5) keeps its weights for costs. **Base c = 10 bp, stress c = 50 bp** one way; d_t is in percent a month, so c enters as 0.10 and 0.50. A holding month in O after the gap (1995-08) is charged against the weights of 1995-07, as if the rule ran straight through (it does: costs are computed on the full history and then sliced).

Not charged, and why: the drift of weights within a month and the reset to equal weights within each leg; the industries' own rebalancing (value-weighted, low turnover). Both flatter d slightly (§10, row 5). The costs are a convention of this study, not an estimate of what a fund would pay in any decade; [MG99] puts its break-even one-way cost near 75 basis points for the six-month rule (reported, not used).

### 6.4 Engine

New code in `research/011-industry-momentum-french-us/src/` (signal, cohorts, rule, costs, metrics including the two-stretch Newey–West of §9.3); the shared library's deflated Sharpe, bootstrap and house-style chart functions (`qune_research/`), unchanged. Tests written with synthetic industry series before the history run, including: formation without a skipped month; the ranking order and the tie rule; six overlapping cohorts and the first holding month of each trial; the netting of weights across cohorts; the cost arithmetic (replacing one member of one leg of one cohort adds 2/(6n) to Σ|Δw|; entry from zero); the empty-leg rule; and that the two-stretch Newey–West equals the ordinary one when the series has one stretch.

### 6.5 Missing data

A missing value in a formation month makes the industry ineligible at that ranking (§6.1). A held industry with no value in a holding month drops out of its leg's mean for that month; if a leg has no member with a value, cohort m contributes zero in t and the event is counted and reported. Below the stop thresholds of §5.4 nothing else changes.

## 7. Registered trials (N = 3)

| ID | Rule | Holding months in O |
|---|---|---|
| M1 | 17 industries, top 3 / bottom 3, formation t − 6 to t − 1, six overlapping six-month cohorts | I1 1927-06 to 1963-06 and I2 1995-08 to the end |
| M1a | 30 industries, top 5 / bottom 5; otherwise M1 | as M1 |
| M1b | 17 industries, top 3 / bottom 3, formation t − 12 to t − 1; otherwise M1 | I1 1927-12 to 1963-06 and I2 |

M1a and M1b are fragility companions (`QUESTION.md` §2.1). Each is judged on its own C1–C4 on O.

## 8. Windows and the role of each

All windows are holding months.

| Row | Months | Role |
|---|---|---|
| I1 | 1927-06 (M1b: 1927-12) to 1963-06 | before the paper's sample; used by later work for related rules; reported, no weight alone; part of the window rule |
| I2 | 1995-08 to the last common month of the snapshot (expected 2026-08) | after the paper's sample; reported, no weight alone; part of the window rule |
| **O** | I1 and I2 together | **the decision row**: C1–C4 for each trial |
| M | 1963-07 to 1995-07 | the paper's sample; reported, no weight |
| full | 1927-06 (M1b: 1927-12) to the end | reported, no weight (mined in part) |

Power, from `QUESTION.md` §2.3 (`tools/power_industry.txt`): detectable Sharpe of d on O 0.347 (nw 1.00) to 0.384 (nw 1.108) (M1b 0.348 / 0.386 on 800 months); I1 0.473 / 0.524; I2 0.510 / 0.565; M 0.502 / 0.556. These are the edges detectable at 80% power, not hard floors. Six overlapping cohorts may carry a Newey–West ratio above 1.108; the realised ratio is reported (§9.6). There is no untouched out-of-sample window: every month to the snapshot was published before this study. The forward record (§11) is the only clean test, and a weak one.

## 9. Benchmarks, metrics and decision criteria

### 9.1 Benchmark and the decision difference

- **B0**: zero. The rule is a zero-investment long-short, as [MG99] reports its profits, so the decision difference is the rule return itself: **d_t^k = rule return of trial k after costs**, at base and at stress costs.
- Reported beside it, no decision weight: the winners' leg and the losers' leg each minus EW_t, the equal-weight mean over the industries of the trial's set with a value in month t, and EW_t itself.

### 9.2 Costs

§6.3.

### 9.3 Metrics

Study 001 §9.3, adapted: turnover is reported as Σ|Δw| per year; hit rate is the fraction of months with d > 0. Sharpe ratios are annualised (monthly mean / monthly sd × √12). **Newey–West** with a Bartlett kernel and 6 lags, as every earlier study, with one adaptation for O: the series is demeaned by O's overall mean, and the autocovariance at lag j sums only over pairs of months that are both in the same stretch (I1 or I2), divided by O's total month count; on a single stretch this is the ordinary estimator. The I1, I2, M and full rows use the ordinary estimator.

### 9.4 Deflated Sharpe ratio

Study 001 §9.4's formula and variance floor, on each trial's d^k over O, **at N = 3**: a new family (no earlier study ranked industries; related to Study 010, which timed factors on the same library, disclosed). Beside it, with no decision weight: the DSR at N = 11 (one per study to date, this one included), and at the programme-wide count of every trial registered in `research/*/trials.md` and in the desk registry `ops/trading/research/trials.jsonl`, re-counted immediately before the history run and written to `trials.md` with the method of the count. The note says, before any result, that the question was chosen after ten earlier studies and that only N = 3 decides.

### 9.5 Verdict table

For each trial k on O, at base costs: **C1** annualised Sharpe of d^k ≥ 0.10 (the programme's margin over the benchmark; here weaker than C2, which on 806 months needs about 0.24 at nw 1.00 (0.27 at 1.108), and kept for form); **C2** Newey–West t of mean(d^k) ≥ 2.0; **C3** DSR(d^k) at N = 3 ≥ 0.95; **C4** the sign of mean(d^k) unchanged at stress costs.

**Window row (M1 only):** mean(d^{M1}) > 0 over I1 and > 0 over I2, at base costs. Pass or fail on the signs; each Newey–West t is reported, not tested.

| Verdict (M1, the headline) | Condition |
|---|---|
| **Not supported** | Any of C1–C4 fails for M1 on O. |
| **Inconclusive (one side of the paper's sample only)** | C1–C4 hold for M1, but the window row fails (mean of d ≤ 0 over I1 or over I2). |
| **Inconclusive (fragile)** | C1–C4 and the window row hold, but M1a or M1b is "not supported" on its own C1–C4. |
| **Supported in history; forward record pending** | C1–C4, the window row and the companion clause hold. |

Precedence: not supported > inconclusive (one side of the paper's sample only) > inconclusive (fragile) > supported. The companions' rows read "not supported" or "meets C1–C4". **Return-unit label:** if the minimum detectable mean of d^{M1} at 80% power on O (2.842 × the Newey–West standard error of mean monthly d × 12, at base costs) exceeds 2% a year, any row that is not "not supported" adds "(Sharpe units; the 2%-a-year bar not met)", as `QUESTION.md` §2.3 expects. No sentence may call a result "supported" without "in history; forward record pending", and every verdict says the rule is a variant of [MG99]'s on the library's industries. The note's first paragraph carries the §2.4 disclosure in one sentence.

### 9.6 Pre-registered descriptive sub-analyses (no decision weight)

- I1, I2, O, M and full for every trial: mean(d), Newey–West t, Sharpe of d, months.
- d by decade (calendar decades, the first and last partial), for M1.
- The legs: winners minus EW_t and losers minus EW_t, over the same rows, for M1.
- Per industry: the share of months in W and in L, for M1; no industry is dropped or reweighted after it is seen.
- **The paper's comparison:** mean(d^{M1}) before costs over M (1963-07 to 1995-07) beside the paper's 0.43 percent a month; a different industry set and classification, so descriptive only.
- The twelve worst months of d^{M1} with their dates, and d^{M1} in 1929-09 to 1932-12 and 2008-09 to 2009-12 (the episodes of §2.4, listed before any result so that the choice is not made after).
- Eligibility: months with fewer than the full set eligible, ties, empty legs.
- Power, realised: observed NW/iid ratio of d on O, annualised sd(d), MDE at t = 2 and at 80% power, in % a year and in Sharpe of d.
- Charts to the house standard (`qune_research/style.py`): cumulative d^{M1} with I1/M/I2 marked; d by decade; the three trials on I1/I2/O.

### 9.7 What did not work

Study 001 §9.7, unchanged; an empty section is not acceptable.

## 10. Known pitfalls

| # | Pitfall | Handling |
|---|---|---|
| 1 | The library rebuilds its whole history monthly; numbers change with the release | one snapshot, hashes and release line in the manifest; raw files not committed (§0 item 7), full-precision outputs committed; the forward scoring reports a vintage row (§11) |
| 2 | M is the paper's sample, and I1 has been used by later work for related rules | decision on O; window row on I1 and I2 separately; M reported with no weight; I1's label stated in every row |
| 3 | The author knows the famous episodes (§2.4) | listed before any data; episode rows fixed now (§9.6) |
| 4 | Thin industries early in the sample may dominate the ranks | eligibility counts reported; stop thresholds (§5.4); M1a on a finer set and M1 on a coarser one; the legs reported |
| 5 | Within-month drift, leg resets and the industries' own rebalancing are not charged | disclosed; stress costs fivefold; d at stress costs reported |
| 6 | Pre-1962 universe NYSE only, thinner and costlier markets | I1 reported separately; the note says so (general knowledge) |
| 7 | The library's industries are not the paper's | a variant, stated in every verdict (§9.5) |
| 8 | O joins two stretches 385 months apart | Newey–West within stretches (§9.3); costs computed straight through (§6.3) |
| 9 | I2's first cohorts are ranked on formation months inside the paper's window | only return months count as outside (`QUESTION.md` §2.3); disclosed |
| 10 | Ranking ties | column order, fixed in §6.1; counted |
| 11 | A real-time investor would need the industry returns at each month end | built from CRSP data that exist at month end; the library's publication lag affects only the forward record (§11) |
| 12 | The raw files sit on disk from the data step to the history run | only process stops anyone looking: the data step's parser writes dates, counts and marker flags only, and no other script reads the files until `--history`; stated, not provable |

## 11. Forward record (shadow only; no paper order)

Trials recorded: M1, M1a and M1b. For each forward holding month t (the first is the month after the snapshot's last month), the cohort ranked at the end of t − 1 is computed from the first release that contains month t − 1 and committed with that release's hash and the commit time; the five earlier cohorts held in t are those already recorded (or, for the first forward months, those of the history run). Because the library publishes with a lag, the commit will often come weeks into month t or later. That cannot be gamed: the cohort is a mechanical function of returns to t − 1, so the timing of the commit selects nothing. **Every forward month is scored, whatever the commit time;** rows committed after the first release that contains month t (the first holding month's return) are labelled "late" and counted, not dropped. The first forward month's cost is measured from the weights of the history's last month, as if the rule ran straight through (Study 010's dated addition 4). The cohorts scored are the committed ones; those recomputed from the scoring release are shown beside them as part of the vintage row.

Scoring after 60 holding months, from one release named at scoring, with the rules of §9.1 and §9.5 (C2 and C4 decide; C1 and C3 are reported), and a vintage row comparing that release with the snapshot over the history's months. **Power, stated now:** over 60 months the detectable Sharpe of d at 80% power is 2.842 / √5 = 1.27 (1.41 at nw 1.108), about 3.7 times O's detectable 0.347–0.384; the forward record can catch only a very large edge or a clear sign reversal, and its verdict is worded as a low-power check. Code (`forward011.py`) is written after the note, with tests and a separate code review, before the first forward month is due; Study 010's dated code decisions (its §16) are the template.

## 12. Risk limits

Not applicable: no order of any kind.

## 13. Repository layout

`research/011-industry-momentum-french-us/`: `QUESTION.md`, `QUESTION_REVIEW.md`, this file, `DESIGN_REVIEW.md`, `trials.md`, `data_step.py`, `src/`, `tests/`, `reproduce.sh` (refuses without `APPROVED`; `--history` runs once and refuses if `results/history/` exists), `results/` (manifest and data-step outputs; history outputs), `charts/`, `README.md`; `data/raw/` git-ignored.

## 14. Order of operations

1. This document and `trials.md`, reviewed for design by a separate session before commit; committed and pushed before step 2.
2. Data step, logged in `trials.md` before it runs: download once, manifest, dates, column names, counts and missing markers only (§5.3); outcome appended; stop rules (§5.4).
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

It does not change the industry sets, the share, the formation or holding lengths after the data step; test a skipped month, the one-month rule or equal-weighted industries; use the 10, 12, 38, 48 or 49 industry sets; use firm counts or any other section of the files; or run any row on a second download. It does not claim to replicate [MG99]'s result.

## 16. Amendments

None.
