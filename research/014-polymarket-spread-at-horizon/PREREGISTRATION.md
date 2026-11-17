# Study 014: the longshot spread premium at the horizon, on Study 013's own rows

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-11-17 (the commit's time **D** is the record; London = UTC) |
| Status | pre-registered; **no bid, ask, spread or mid of any windowed market read by the author for this study; no row of Study 013's sample exists yet (its data step runs after 2027-01-20)** |
| Version | 1.0 (any change after this commit needs a dated amendment appended to §16 before any further step is run) |
| Study type | new family for the programme: first study of a microstructure quantity ([`QUESTION.md`](QUESTION.md), commit `b2dbeb8`, 2026-11-16 by git; [`RESEARCH_AGENDA.md`](../../RESEARCH_AGENDA.md), dated addition of 2026-11-16) |
| Data | Study 013's daily snapshots of Polymarket's open-market listing (Gamma API, taken by [`collector.py`](../013-polymarket-calibration-forward/collector.py) from S = 2026-11-03, git-ignored, hashed in [`paper-log/snapshots.csv`](../013-polymarket-calibration-forward/paper-log/snapshots.csv)) and Study 013's data-step sample file (`results/sample.jsonl`, git-ignored, hashed in its `results/data_manifest.json`). **No fetch of any kind by this study.** Verdict `derived` ([`tools/pm_data_terms.md`](../../tools/pm_data_terms.md): read 2026-11-01; re-read 2026-11-17 00:17:56Z before this commit: the effective date string unchanged, 11 August 2026, which is the whole of what the re-read checked (the page's bytes differ from the 2 November copy and were not diffed); the row in that file's "Re-reads" table, committed with this document). |
| Instruments | none: a measurement of quoted spreads, not a rule. **No paper order, no paper sleeve, no forward record of a position.** |
| Approval | approved by the orchestrator under the owner's delegation of 2026-10-21 (all decisions on this research programme) and inside the owner's scope of 2026-10-31 (prediction markets only), on the date of this commit. An `APPROVED` file is written at implementation time (§14 step 4), after this commit. |
| Total trial count registered | **3** (§7): M1 and its two companions M1a and M1b |
| Multiplicity decided at | **N = 3** (§9.4; a new family); the programme-wide count, re-counted before the analysis run, reported beside it with no decision weight |
| Design review | a separate session reviewed this document before its first commit ([`DESIGN_REVIEW.md`](DESIGN_REVIEW.md)): 6 must-fix and 14 should-fix points, all changed in the draft before this commit |
| Author | the orchestrator (Qune) |

Nothing in this document reports or implies the result of any test registered here. The question note fixed the question, the source, the test object (a difference in mean log relative spread between two price bins), the three trials, the decision row of the power table and the sample (Study 013's rows); this document writes them out as rules and fixes what the note left open (§0). Where the two differ, this document governs and says why.

---

## 0. Relationship to the question note, and what this document fixes

Everything in `QUESTION.md` §1–§4 stands. This document fixes, before any data:

1. **The pass bar:** C1 requires Δ ≥ 0.59, half of the smaller published premium ln(1300/400) = 1.18 (§9.5). The note offered Δ > 0 alone or half the published premium. Half is chosen because a premium at the horizon that is positive but small is a finding about the venue's tick, not a cost that changes what a trader does; Δ ≥ 0.59 says the longshot relative spread is at least 1.8 times the central one. A row with 0 < Δ̂ < 0.59, whatever its t_cl, reads "not supported (a premium below half the published size: Δ̂ = …, t_cl = …)" (§9.5).
2. **The rows this study reads, and a departure from the note stated with its reason (§5.1):** the note said the data step "reads 013's data-step output rows, never the snapshots directly". Study 013's sample file carries the market id, the snapshot of record's date, p, the cluster, the trial, the half, the Sports flag and the early flag, but not the bid, the ask, the tick or the liquidity figure, so this study's analysis run reads the sample file for the sample and then **the snapshot-of-record row of each sampled market, from the same snapshot file Study 013 read, hash-checked against its logged line**, for the eight fields of §5.3 and no other. Three of them (`orderPriceMinTickSize`, `liquidityNum`, `feesEnabled`) Study 013 never reads, and the moved-end count reads `id` and `endDate` of earlier snapshots, so the note's sentence "this one adds nothing to what 013 reads" is corrected here: this study reads three more fields of the same rows, none of them a price, an outcome or a status, and two fields of earlier rows. The sample is still Study 013's, fixed by its data step before any outcome is read; this study adds no market and removes only the followed events (§6.3).
3. **The treatment of a locked book:** bid = ask passes Study 013's eligibility (0 < bid ≤ ask < 1), so its quoted spread is 0 and ln 0 is undefined; the spread is floored at the market's tick and the market is counted (§6.2). Crossed books (bid > ask) never enter Study 013's sample.
4. **The tick floor:** the row's `orderPriceMinTickSize`; a null or unreadable value is read as 0.001, the smallest tick the venue uses, and counted (§6.2). The smaller tick is the conservative reading for H1: a locked or sub-tick longshot book floored at 0.01 would read ten times wider than at 0.001 and push Δ̂ towards H1. Δ̂ with null ticks read as 0.01 is reported beside (§9.6). A tick below 0.001 is counted and stated, because the sd bound behind the stated MDE assumes 0.001.
5. **The exclusion of the followed events, by any event id on the row** (§6.3), not by the cluster id alone: a market in several events is excluded if any of its event ids is 1292829 or 770450, and likewise for any event added to `pm-view/events.csv` with a `followed_from` date before the analysis run (counted apart), because the desk reads the books of every followed event by hand.
6. **The high-probability bin's report and the decile table** (§9.6): (0.90, 0.99] reported beside the two decision bins with no decision weight; the decile table uses ten bins of mid, [0.01, 0.10), [0.10, 0.20), …, [0.90, 0.99].
7. **The estimator and its standard error** (§9.3): Δ̂ is the difference of the two bin means of ln s, estimated as the slope of a regression of ln s on a longshot indicator over the rows of the two bins, with the standard error clustered by Study 013's cluster (parent event) and the usual G/(G − 1) factor; a clustered bootstrap interval reported beside it.
8. **Criteria C1–C4 in the programme's form, adapted to a difference of means** (§9.5), with C3 at N = 3 as a Bonferroni bar and a window row on Study 013's two four-week halves.
9. **The stop and halt rules inherited from Study 013, and this study's own** (§5.4).
10. **Timing:** nothing of this study is computed before Study 013's data step has run (after its scoring deadline, 2027-01-20 00:00Z), and the analysis run executes **before Study 013's scoring run** (between its §14 steps 6 and 9), so that no outcome of the sample is known to anyone when the spreads are read; this study reads no outcome in any case. Should the order not have been kept, the run still executes once and the note states the order as a limit, from `git log`.
11. **The secondary reading written out** (§9.6): the median half-spread in probability points by bin beside the compression figures of [WA26] and [CR26] as the note quotes them. The half-spread is q / 2 from the quoted spread, **not floored at the tick** (the note wrote s · mid / 2, which is floored): a locked book costs a taker no half-spread, and the secondary reading prices a cost, not a quote convention. Fees are not modelled and no fee rate is cited: this study fetches nothing and no fee schedule is on the repository's record; the share of markets with `feesEnabled` true is reported by bin.
12. **The moved-end count written out** (§9.6): the count of sampled markets whose `endDate` on the snapshot of record differs from the `endDate` on the first snapshot **dated on or after S** that lists them (the note said "the first snapshot that listed them"; S0 of 2026-11-02 is kept out as Study 013 keeps it out); the run reads `id` and `endDate` of earlier snapshots and nothing else.
13. **No historical slice and no open-market replication.** The note allowed a labelled replication; none is run, because a reading of open markets today would read the rows Study 013 holds unread until its window closes (`QUESTION.md` §4).
14. **The one-run rule:** the analysis run executes once, writes its outputs whatever they show, and refuses to run twice (§13, §14).
15. **Study 013's data-step report as an input** (§5.1, §5.4): the run reads three keys of Study 013's `results/data_step.json` (whether it stopped for a gap amendment, whether it halted, and whether its price-field check passed) and the SHA-256 of the sample file from its `results/data_manifest.json`, because the inherited stop and halt rules are decidable from nothing else.
16. **"No fit" written out** (§9.3, §9.5): a fit with an empty decision bin, fewer than two clusters or SE_cl = 0 has no Δ̂, and the verdict rows say what follows.
17. **The window's first days closed before this document** (§11): W opens 2026-11-04 and D is 2026-11-17, so the rows of markets closing in the window's first thirteen days already sit on disk, hashed, unread by the author; a before-D and after-D split of Δ̂ is reported (§9.6).

## 1. Question

> On the snapshot of record at 24 hours before resolution, over the binary Polymarket markets that enter Study 013's sample, is the relative quoted spread (best ask less best bid, divided by the mid) wider for longshots (mid below 0.10) than for markets priced near even (mid in [0.40, 0.60]), by the margin the venue's order-book literature reports for open markets, and what does that spread cost a trader who would fade the compression Study 013 tests for?

## 2. Hypothesis and grounding

H1: Δ = mean(ln s | longshot) − mean(ln s | central) over the decision sample (M1, §7) is greater than 0 by enough to meet C1–C4. The null of the t-test is Δ ≤ 0 (no relative spread premium for longshots at the horizon); the study's "not supported" verdict covers every failure of C1–C4, including a premium that is positive and below half the published size.

Grounding (`QUESTION.md` §1): [DU26] reports, on a pre-registered stratified panel of 600 open markets (a top-100 stratum by on-chain volume and a random stratum) over 28 days (2026-02-28 to 2026-03-27), a median quoted spread of about 400 bps of mid in [0.4, 0.6] and 1,300 to 1,800 bps below 0.10, and reads the magnitude as a maker's liquidity-provision constraint on a bounded-upside, asymmetric-downside contract.

Why it might not hold here: (a) the object differs: [DU26]'s figure is a market's time average while open, this study's is one quote at a fixed horizon before resolution; (b) at a day before resolution most longshots are settled in all but name and may be quoted at the tick on both sides, which compresses the relative spread of a longshot towards tick/mid and of a central market towards tick/0.5, so the premium could collapse or become a pure tick effect; (c) makers may withdraw before a known resolution, widening both bins; (d) Study 013's floor (spread ≤ 0.10, volume ≥ 10,000 USDC) caps s at 10 in the longshot bin and at 0.25 in the central bin, so the sample cannot show the widest longshot quotes; (e) Sports will hold a large part of the sample and [DU26] reports category-conditional spread differences, which is why M1a is registered.

### 2.4 Designer's prior knowledge (disclosed)

`QUESTION.md` §3 in full. The author has read no bid, ask, spread or mid of any windowed market for this study. The desk's weekly view has read, by hand and on quote days (3, 6 and 13 November), the books of ten markets of the two followed events, and the event listings of 13 November carried best bid and ask for 34 legs; every market of those two events is excluded (§6.3). The author's general knowledge covers Polymarket's order books and spreads to its training cutoff; no market resolving on or after 2026-11-04 is in that knowledge, and no parameter in this document was chosen on any spread of a windowed market. Study 013's data step, when it runs, reads p and the spread of every sampled row to apply its own floor; the author reads that step's counts, not its rows.

## 3. Literature

[DU26] arXiv:2604.24366v2 (abstract, introduction, §3.4, §4.3, §5.1–§5.2 read; Table 1's per-decile figures not in the HTML, not read); [CR26] and [WA26] as read for Study 013. All as cited in `QUESTION.md` §1 and the agenda's register. The three other arXiv abstracts the note lists are not added to the register until read.

## 4. Instruments

None. A result here does not imply any order on the desk; a rule that fades longshots net of the half-spread is scope question 5 and would be a later, separate pre-registration.

## 5. Data

### 5.1 Sources

- **Study 013's data-step sample**, `research/013-polymarket-calibration-forward/results/sample.jsonl` (git-ignored; SHA-256 in `results/data_manifest.json`, committed by Study 013's data step). One row per market and trial, in Study 013's own words: `trial`, `market`, `cluster`, `price` (p), `snapshot` (the snapshot-of-record date), `realised_horizon_hours`, `early`, `half`, `sports`, `first_label_yes`, `volume_at_horizon`, `tag_family`, `first_token`. This study reads `trial`, `market`, `cluster`, `price`, `snapshot`, `realised_horizon_hours`, `half`, `sports` and `early`, and never `first_token` (it names a token, not a price) or any file of Study 013's resolution fetch. `half`, `early`, `realised_horizon_hours` and membership itself derive from `closedTime` in Study 013's `status.jsonl`; this study reads them only as Study 013's derived flags, and `early` is correlated with the outcome for markets that can resolve early (Study 013 §10 row 15), so the early split of §9.6 is descriptive only.
- **Study 013's data-step report and manifest**, `results/data_step.json` (three keys only: whether the step stopped for a gap amendment, whether it halted, whether its §6.2 price-field check passed) and `results/data_manifest.json` (the sample file's SHA-256, `sample_jsonl_sha256`). The run refuses when the sample file's SHA-256 differs from the manifest's.
- **Study 013's snapshots**, `research/013-polymarket-calibration-forward/data/raw/snapshots/<UTC date>/records.jsonl` (git-ignored), each hashed against its line in `paper-log/snapshots.csv` before any row is read; a mismatch or a missing file refuses with nothing written. From the snapshot-of-record row of each sampled market the run reads the eight fields of §5.3 (this line said "seven" until the code review of 2026-11-17, §16; §5.3 has always listed eight, `id` among them).

Both files are Study 013's; this study fetches nothing. Polymarket's verdict is `derived`: no raw response or per-market row is committed; the published outputs are aggregates computed by the desk (§13), attributed to Polymarket with the snapshot dates.

### 5.2 Snapshot of record

Study 013's (its §5.2): for a market with resolution time T and horizon h, the snapshot dated on or after S with the latest start time t_s ≤ T − h, with the gap cap h + 48 hours. This study takes the snapshot named on the sample row and does not choose one.

### 5.3 What the analysis run may read from a snapshot row

Eight fields of the snapshot-of-record row of a sampled market, and no other: `id` (to find the row), `bestBid`, `bestAsk`, `orderPriceMinTickSize`, `liquidityNum`, `feesEnabled`, `endDate`, `eventIds`. From earlier snapshots (for the moved-end count of §9.6): `id` and `endDate` only. Never read by this study, and a test asserts the reader's field list: `outcomePrices`, `lastTradePrice`, `umaResolutionStatus`, `closedTime`, `outcomes`, `clobTokenIds`, `tagLabels` (the Sports flag comes from the sample row), and every file of Study 013's resolution fetch (`status.jsonl`, `outcome.jsonl`).

### 5.4 Stop and halt rules

Inherited, read from the three keys of Study 013's `results/data_step.json` (§5.1): if Study 013's data step **stopped for a gap amendment** (fewer than 42 of 56 C1 snapshot days, or a run of three gap days) and has not been re-run under a dated amendment, the run refuses and this study waits; if Study 013's **§6.2 price-field check failed** (the listing's mid and the quoted mid disagree by more than 0.02 on more than 1 percent of its C1 rows), this study **halts permanently** with the verdict "inconclusive (halted: the quote fields do not mean what both documents say)", because the bid and ask are the fields in question; Study 013's sample-size halt (fewer than 2,000 clusters or 5,000 markets) does not halt this study by itself, and the run proceeds whatever that key says, with this study's own floors deciding. Study 013 writes its manifest and sample file in every ending, so the presence of the manifest alone is never the signal to run.

This study's own permanent halt, with the verdict "inconclusive (halted at the analysis run)": the M1 decision sample (W, after the followed-event exclusion) holds fewer than **100 clusters or fewer than 200 markets in either decision bin**. Both are round floors with their own reasons, not derived crossings: below 100 clusters the G/(G − 1) factor, the clustered bootstrap and a bin median rest on fewer than a hundred independent events; below 200 markets the Sports split and the decile cell of a bin cannot each hold tens of markets. For the reader: the one-bin bound-based MDE in the cluster unit exceeds the 0.59 bar below 146 central clusters (2.842 · 2.505 / √146 = 0.589) and below 277 longshot clusters (2.842 · 3.454 / √277 = 0.590), and a bound above the bar says nothing about realised power, which §9.6 reports. The counts are published whatever they show.

A sampled market whose snapshot-of-record row cannot be found in the hashed snapshot file, or whose `bestBid` or `bestAsk` on that row is not a decimal number in (0, 1) with bid ≤ ask (which Study 013's eligibility should make impossible), is excluded and counted under "row not as Study 013 recorded it"; if that count exceeds 1 percent of the M1 sample (the C1 rows after the followed-event exclusion, before the bin assignment) the run halts permanently with the same verdict, because the two studies would not be reading one record. The same count over the M1a and M1b rows is reported and does not halt.

## 6. Exact rule specification

### 6.1 Horizon

h = 24 hours (M1, M1a: Study 013's C1 and C1a rows); h′ = 168 hours (M1b: Study 013's C1b rows). The realised horizon is Study 013's and is reported as it stands on the sample rows.

### 6.2 Spread, mid and the test variable

On the snapshot-of-record row: **mid** = (`bestBid` + `bestAsk`) / 2, equal to Study 013's p (the run asserts |mid − `price`| ≤ 1e-9 on every row and counts a disagreement under §5.4's "row not as recorded"); **tick** = `orderPriceMinTickSize` read as a decimal number, 0.001 when null or unreadable (counted; §0 item 4), a value below 0.001 kept and counted; **quoted spread** q = `bestAsk` − `bestBid`; **relative spread** s = max(q, tick) / mid, so that a locked book (q = 0) reads tick/mid and is counted, and any q below the tick (which the venue should not quote) is floored at the tick and counted. The test variable is **ln s**. The **half-spread in probability points** is q / 2 (not floored), for the secondary reading of §9.6.

### 6.3 Bins, sample and clusters

Bins are assigned on the mid rounded to nine decimal places (a float mid of (0.55 + 0.65) / 2 is 0.6000000000000001 and of (0.051 + 0.149) / 2 is 0.09999999999999999; a test holds both pairs and the 0.90 edge). The **longshot bin** is 0.01 ≤ mid < 0.10 and the **central bin** 0.40 ≤ mid ≤ 0.60; the **high-probability bin** 0.90 < mid ≤ 0.99 is reported (§9.6) with no decision weight; a market outside the two decision bins enters no trial's decision statistic and is counted. The **sample** of a trial is every row of Study 013's sample file for the matching Study 013 trial (M1 reads C1, M1a reads C1a, M1b reads C1b), **less every market whose snapshot-of-record row carries event id 1292829 or 770450** (the two events the desk's weekly view follows, [`pm-view/events.csv`](../../pm-view/events.csv) as of this commit; the count removed is reported), **and less every market carrying the event id of any row added to that file with a `followed_from` date before the analysis run** (the desk reads every followed event's books by hand; counted apart from the two, and the ids named in the results). **Cluster** = the sample row's `cluster` (Study 013's §6.4: the numerically smallest parent event id).

### 6.4 Outcome

None is read. This study's test variable is a quote at the horizon, not a resolution; nothing in `src/` opens `status.jsonl` or `outcome.jsonl` (a test asserts it on each module's text and on its open calls; the tests themselves name the files to assert it).

### 6.5 Engine

New code in `research/014-polymarket-spread-at-horizon/src/`: the reader (sample rows, hash-checked snapshot rows, the eight fields of §5.3; "seven" here until the code review of 2026-11-17, §16), the analysis run (bin assignment, Δ̂, clustered standard error, clustered bootstrap, the decile table, the secondary reading, the moved-end count, the realised power) and the chart step; the shared library's house-style charts (`qune_research/style.py`), unchanged. Tests written on synthetic rows before the run, including: the field list of the reader and its refusal on any other field; the hash check refusing a changed snapshot file; the tick floor on a locked book, on a null tick (0.001) and on a tick below 0.001 (kept, counted); the exclusion of the two events and of a later-followed event by any event id; bin assignment at each boundary (0.01, 0.10, 0.40, 0.60, 0.90, 0.99) and on the two float pairs of §6.3; the "no fit" rule on an empty bin, one cluster and a zero SE_cl; Δ̂ equal to the difference of the two bin means to 1e-12; the clustered standard error equal to the HC0 sandwich times n/(n − 1) when every cluster has one member; the bootstrap's seed and drop rule; the run refusing without `APPROVED`, refusing to run twice and refusing when Study 013's data step has not written its manifest; the §5.4 halts on synthetic counts; and that no module in `src/` names `outcome.jsonl`, `status.jsonl`, `outcomePrices`, `umaResolutionStatus`, `lastTradePrice`, `closedTime`, `first_token` or `clobTokenIds`.

## 7. Registered trials (N = 3)

| ID | Rule | Sample |
|---|---|---|
| M1 | Δ at h = 24 h over Study 013's C1 rows outside the two followed events | §6.3 |
| M1a | M1 with every market flagged Sports on its sample row set aside | Study 013's C1a rows, §6.3 |
| M1b | Δ at h′ = 168 h; otherwise M1 | Study 013's C1b rows, §6.3 |

M1a is the Sports companion ("supported" for M1 needs M1a not "not supported"); M1b is the horizon companion, reported. Each is judged on its own C1–C4 and the window row.

## 8. Window and the role of each part

Study 013's window: `closedTime` in **W = [2026-11-04, 2026-12-30)**, with halves W1 = [2026-11-04, 2026-12-02) and W2 = [2026-12-02, 2026-12-30) read from the sample row's `half`. There is no in-sample row. The power table's decision row (`QUESTION.md` §2; `tools/power_pm014.txt`: 8 w, distinct parent events, longshot share 0.10, central share 0.02, n₁ = 4,469, n₂ = 894, sd bounds 3.454 and 2.505, K = 2.842: **MDE 0.280, ratio 0.24 to 1.18**) is the stated power before data, an upper bound on the MDE. K = 2.842 is 80 percent power at t ≥ 2.0; the binding bar is C3, t ≥ 2.128, whose K is 2.970, and the MDE at 2.970 is reported beside the programme's figure (on the decision row 0.293, ratio 0.25). The analysis run recomputes both (§9.6) with the realised counts and the realised sd of ln s in each bin. If the recomputed ratio for M1 exceeds 0.50, that is, if the realised MDE at K = 2.842 exceeds the 0.59 pass bar, the study runs as a **labelled low-power check** and every verdict row carries the label.

## 9. Benchmarks, metrics and decision criteria

### 9.1 The test object

Over a trial's sample, with ℓ_i = ln s_i and L_i = 1 for the longshot bin and 0 for the central bin, over the rows of the two bins only,

  ℓ_i = α + Δ · L_i + ε_i,

fitted by ordinary least squares (so Δ̂ is exactly the difference of the two bin means), each market one observation with weight 1. The benchmark is **Δ = 0** (equal relative spread across the two bins). The decision quantity is **Δ̂**, its sign and its clustered t-statistic t_cl = Δ̂ / SE_cl.

### 9.2 Costs

None modelled. Fees are a reported field (`feesEnabled`, a flag, not a rate); the share of sampled markets with fees enabled is reported by bin; no fee rate is cited, because this study fetches nothing and no fee schedule is on the repository's record (§0 item 11).

### 9.3 Estimator and standard errors

With z_i = (1, L_i)ᵀ, X the n × 2 design, e_i the residual and s_g = Σ_{i∈g} e_i z_i the score of cluster g,

  V_cl = G/(G − 1) · (XᵀX)⁻¹ (Σ_g s_g s_gᵀ) (XᵀX)⁻¹,

and SE_cl is the square root of its (Δ, Δ) entry, G the number of clusters over the two bins' rows. Reported beside it, no decision weight: the ordinary standard error, and a clustered bootstrap percentile interval for Δ at 95 percent (2,000 resamples of clusters with replacement, `numpy.random.default_rng(14)`, fixed now; a resample in which either bin is empty is dropped and counted, and the interval is reported as not available if more than 1 percent are dropped). The bootstrap runs for the three trials' W rows only; the halves and the descriptive splits carry Wald intervals Δ̂ ± 1.96 · SE_cl. **No fit:** a fit (a trial on W, W1 or W2) whose decision bins include an empty one, whose rows hold fewer than two clusters, or whose SE_cl is 0 has no Δ̂ and no t_cl and is reported as "no fit" with its counts.

### 9.4 Multiplicity

C3 is a Bonferroni bar at **N = 3**: one-sided p ≤ 0.05 / 3, that is **t_cl ≥ 2.128** (standard normal). Beside it, no decision weight: the bar at N = 13 (one per study to date, this one included, Study 012 excluded: z ≥ 2.665) and at the programme-wide count of every trial registered in `research/*/trials.md` and the desk's private registry, re-counted immediately before the analysis run and written to `trials.md` with the method of the count.

### 9.5 Verdict table

For each trial k on W: **C1** Δ̂ ≥ 0.59 (half the smaller published premium, §0 item 1); **C2** t_cl ≥ 2.0; **C3** t_cl ≥ 2.128 (§9.4; C3 implies C2, both kept for form); **C4** Δ̂ > 0 on W1 and on W2 fitted separately (the window row; each half's t_cl reported, not tested); C4 fails unless both halves have a fit (§9.3).

| Verdict (M1, the headline) | Condition |
|---|---|
| **Not supported** | Any of C1–C4 fails for M1 on W, or M1 has no fit on W (the row reads "not supported (no fit)"). A row with 0 < Δ̂ < 0.59, whatever its t_cl, reads "not supported (a premium below half the published size: Δ̂ = …, t_cl = …)". |
| **Inconclusive (fragile: Sports)** | C1–C4 hold for M1, but M1a is "not supported" on its own C1–C4. |
| **Supported in one forward window** | C1–C4 hold for M1 and M1a is not "not supported". |
| **Inconclusive (halted …)** | A permanent halt of §5.4; no Δ is estimated. |

Precedence: halted > not supported > inconclusive (fragile) > supported. The companions' rows read "not supported", "not supported (no fit)" or "meets C1–C4" (an M1a with no fit is "not supported", so M1 reads "inconclusive (fragile: Sports)"); M1b's row adds whether Δ̂(h′) > Δ̂(h) as a descriptive line. **Low-power label:** if the recomputed ratio for M1 (§9.6) exceeds 0.50, every row adds "(low-power check: the minimum detectable effect exceeds the pass bar, half the published premium)". The sentence is exact: ratio 0.50 is where the realised MDE at K = 2.842 equals 0.59; the published premium itself would stay visible at 80 percent power up to a ratio of about 0.96 (SE_cl ≈ 0.397, where 1.18 / SE = 2.128 + 0.842), and the label does not claim otherwise. No sentence may call a result "supported" without "in one forward window" and the window's dates, and every verdict states the horizon, Study 013's floor, the tick-floored share of each bin and the share of the sample carrying the Sports flag. The note's first paragraph carries the §2.4 disclosure in one sentence.

### 9.6 Pre-registered descriptive sub-analyses (no decision weight)

- For every trial on W, W1 and W2: n and G in each decision bin, Δ̂, α̂, SE_cl, SE_ordinary, the bootstrap interval, t_cl; the share of rows in each bin whose s was floored at the tick (a bin where most quotes sit at the tick is a tick measurement, and the note says so).
- **Power, realised:** for each trial, n₁, n₂, G, the realised sd of ln s in each bin, SE = SE_cl of the §9.3 fit (the fitted model's clustered standard error, not a restricted one), MDE = 2.842 · SE, 2.970 · SE and 2.486 · SE, and **the ratio = 2.842 · SE / 1.18**, which the low-power label of §9.5 reads for M1.
- **The decile table:** ten bins of mid, each with n, G, median s, median q/2 in points, the tick-floored share, median `liquidityNum`, share `feesEnabled` true; against [DU26]'s Figure 1. The reference lines drawn on the chart of median s are [DU26]'s **full quoted spread** figures in units of mid, s = 0.04 (400 bps, central) and s = 0.13 and 0.18 (1,300 and 1,800 bps, below 0.10), not the half-spread the paper's introduction quotes at about 200 bps; the chart's subtitle says so. The **high-probability bin** (0.90, 0.99] with its mean ln s and the difference from the central bin, with its clustered interval (Wald, ± 1.96 · SE_cl).
- **The secondary reading (scope question 5's first number):** for the longshot, central and high-probability bins, the median half-spread q/2 in probability points beside the compression Study 013 tests for at that price under [WA26]'s slope (about 1.4 points at 0.05, 1.1 at 0.60) and [CR26]'s interior bins (5.9 to 7.3 points): the table says in which bins the published compression clears the half-spread and in which it is inside the quote. Nothing is sized or traded.
- **Early closes:** Δ̂ with its Wald interval for the rows flagged early and the others, with the early share; descriptive, and outcome-correlated by construction (§5.1).
- **Before and after this document:** Δ̂ with its Wald interval for the rows whose snapshot of record is dated before 2026-11-17 (read from the sample row's `snapshot`; these rows existed on disk at D) and for the others (§0 item 17).
- **Null ticks read as 0.01:** Δ̂ for M1 with null ticks floored at 0.01 instead of 0.001, beside the decision figure (§0 item 4).
- **The moved-end count:** sampled markets whose `endDate` on the snapshot of record differs from the `endDate` on the first snapshot dated on or after S that lists them, by bin; descriptive.
- Every exclusion count of §5.4 and §6.3 in order: rows removed for the two followed events, rows removed for later-followed events (ids named), rows outside the decision bins, rows not as recorded, null ticks, ticks below 0.001, locked books, the count of sampled markets in each bin by half.
- The comparison with [DU26]'s SF1 figures, descriptive only (a time average over open markets against one quote at a horizon).
- Charts to the house standard (`qune_research/style.py`): median s by decile with [DU26]'s two central figures drawn as reference lines; Δ̂ with intervals for M1, M1a, M1b and the early split.
- A decile cell or a split with fewer than ten markets reports its count only (Polymarket's `derived` verdict: a cell of one or two markets is a per-market row in effect).

### 9.7 What did not work

Study 001 §9.7, unchanged; an empty section is not acceptable.

## 10. Known pitfalls

| # | Pitfall | Handling |
|---|---|---|
| 1 | At a day before resolution a decided longshot sits at the tick on both sides, so s is tick/mid, a mechanical function of the price, not a maker's premium | the tick-floored share by bin is reported and named in every verdict; the decile table shows where the quotes sit (§9.6) |
| 2 | The sample's spread cap (0.10) truncates the longshot bin's s at 10 and the central bin's at 0.25 | inherited from Study 013; stated as a limit; Δ̂ is a lower bound on the uncapped premium only if truncation removes wide longshot quotes, which the count of Study 013's exclusion "spread above 0.10" by price bin cannot show (its count is not by bin); stated |
| 3 | The author chose the bins and the bar after reading [DU26]'s figures | the figures are the published effect the power is stated against; the bins are [DU26]'s own; nothing of the sample was read |
| 4 | The desk read ten books of the two followed events by hand | both events excluded by any event id (§6.3) |
| 5 | Study 013's sample file is written after its resolution fetch and sits beside its outcome file | this study's reader never opens the fetch's files (a test asserts the module's text); its field list is fixed here |
| 6 | The venue's `liquidityNum` is a figure of unknown construction | reported as a median by bin, never tested (`QUESTION.md` §4) |
| 7 | `feesEnabled` is a flag, not a rate | share reported by bin; no rate cited or applied |
| 8 | A market in several events is excluded if any id is a followed event's | §0 item 5; the count of such exclusions is reported |
| 9 | Study 013's realised horizon is 24–48 hours, longer across a gap | inherited; `realised_horizon_hours` read from the sample row and reported as it stands |
| 13 | The window's first thirteen days closed before this document, so their snapshot rows exist on disk at D | unread by the author (§2.4); the before-D and after-D split of §9.6 shows whether the two parts differ |
| 14 | The view keeps reading books by hand through the window | every event followed before the run is excluded by any event id and counted apart (§6.3) |
| 10 | Polymarket's verdict is `derived`: the snapshots and the sample file cannot be published | the separate-session recomputation (§14 step 8) runs on this host; the SHA-256 of every input is committed; the published tables are aggregates |
| 11 | The bound-based MDE is loose; the realised sd of ln s may be far smaller, so the realised power is better than stated, or a bin may be near-degenerate at the tick, so it is worse | the realised power is recomputed and reported (§9.6); the low-power label reads the realised figure |
| 12 | This study and Study 013 read the same rows; a defect in Study 013's data step would carry into this sample | the run checks mid against Study 013's p on every row and halts above 1 percent disagreement (§5.4) |

## 11. Forward record

This study is a forward test in the sense that nothing is computed before Study 013's window has closed and its data step has fixed the sample after 2027-01-20 00:00Z, and that the rules here are fixed before any spread is read. There is no position and no paper order. What the timeline holds: every snapshot's hash is committed within the day it is taken, and every snapshot-of-record row was taken before its market resolved. What it does not hold: W opened on 2026-11-04 and this document is dated 2026-11-17, so the rows of markets that closed in the window's first thirteen days (about 13 of W1's 28) already exist on disk at D, hashed; the guard for those rows is that no bid, ask, spread or mid of them has been read by the author (§2.4), not the timeline, and the before-D and after-D split of §9.6 is reported so that a reader can see whether the two parts differ.

## 12. Risk limits

Not applicable: no order of any kind.

## 13. Repository layout

`research/014-polymarket-spread-at-horizon/`: `QUESTION.md`, this file, `DESIGN_REVIEW.md`, `trials.md`, `src/`, `tests/`, `reproduce.sh` (refuses without `APPROVED`; `--run` runs once and refuses if `results/run/` exists), `results/` (the input manifest with the SHA-256 of Study 013's sample file, data manifest and every snapshot read; the Δ table, the decile table, the secondary reading, every count; never a per-market row), `charts/`, `README.md`. Git-ignored: `results/rows.jsonl` (the per-market rows the run computes from: id, mid, s, tick, bin, cluster; added to `.gitignore` with this commit), its SHA-256 in `results/input_manifest.json`.

## 14. Order of operations

1. This document and `trials.md`, reviewed for design by a separate session before commit; committed and pushed, with the `.gitignore` line of §13 and the terms re-read row. No row of this study's sample exists before Study 013's data step (after 2027-01-20), so the "before the first snapshot" rule of Study 013 has no analogue here; the record is this commit's time against Study 013's data-step date, and §11 states what the timeline does not hold.
2. Code and tests on synthetic rows (§6.5); a separate-session code review before step 4.
3. Study 013's data step runs (its §14 step 6), fixing the sample; this study waits for `results/data_manifest.json` in Study 013's folder.
4. `APPROVED` written and committed (it may be written at step 2's end; the analysis run still waits for step 3).
5. Programme-wide re-count (§9.4) and the analysis-run row in `trials.md`, committed and pushed before the run.
6. `./reproduce.sh --run`, once, after Study 013's data step and before Study 013's scoring run (§0 item 10); outputs committed whatever they show.
7. The note (README), §9.5 verdict, §2.4 disclosure first, §9.7.
8. Separate-session recomputation of every published figure from the withheld files on this host.
9. Charts, reviewed against the chart standard.

Time labels are written from `git log` or the machine clock, never estimated.

## 15. Things this study deliberately does not do

It does not change the bins, the bar, the trials or the criteria after this commit; read a spread at any time other than the snapshot of record; fetch anything; read any outcome, status or last-trade field (Study 013's derived flags `half`, `early` and `realised_horizon_hours` are read as flags, §5.1); weight markets by volume or by event; test depth, fees or resolution risk as trials; remove early closes or tick-floored quotes from the sample; run a historical slice or an open-market replication; size or trade anything; or claim to replicate [DU26].

## 16. Amendments

None to the bins, the bar, the trials or the criteria.

**Dated notes (precisions of the engine's reading, found at the separate-session code review of §14 step 2; no rule above is changed; nothing of this study has been computed and no bid, ask, spread or mid of a windowed market has been read):**

- **2026-11-17 (code review, [CODE_REVIEW.md](CODE_REVIEW.md); before `APPROVED`):** (1) §5.4's own halt, "fewer than 100 clusters or fewer than 200 markets in either decision bin", is read with both floors **per decision bin**, as the sentence's own reasons are (a bin median on fewer than a hundred independent events; the one-bin crossings at 146 and 277 clusters); the engine's first version counted the clusters over the union of the two bins, which would have let 110 longshot and 20 central clusters through. This reading is fixed here, before any count is known. (2) The run reads a **fourth, optional key** of Study 013's `results/data_step.json`, `amendment` (§0 item 15 names three): Study 013's data step, re-run under a dated §16 gap amendment, writes the amendment it ran under and recomputes its stop flag, so "has not been re-run under a dated amendment" in §5.4 means the stop flag set with no amendment named, which is also what Study 013's own scoring run reads; the three keys alone could not tell a stop from a re-run that still reports one. (3) A failed price-field check in Study 013 halts this study **before** the stop flag is read (§9.5 precedence, halted first): Study 013 writes both flags when both fire and never re-runs after a halt. (4) The tick-floored flag of §6.2 ("any q below the tick") is decided on q and the tick **rounded to the nine places of §6.3**, because 0.06 − 0.05 is below 0.01 in floating point and a quote exactly one tick wide is not below the tick; s itself is max(q, tick) / mid as written (the two differ by about 1e-15 on such a quote). (5) "SE_cl is 0" in §9.3 is read as at most 1e-12 · max(1, |Δ̂|): a sandwich that is zero in exact arithmetic comes out near 1e-16 in floats. (6) §9.6's last bullet (a cell or split under ten markets reports its count only) is applied to the high-probability bin's block and to every descriptive split; a trial's half under ten markets (W1 or W2) reports its counts and the sign of Δ̂, which is what C4 reads. (7) §6.3's "before the analysis run" for a later-followed event includes the run date itself (the desk may read books on the morning of the run). (8) The once-only rule (§13, §14 step 6): the run writes a marker `results/run/started.txt` after its last refusal and before the first snapshot-of-record row is read, so a run that dies after that line leaves the marker and the next attempt is refused; a refusal before the marker leaves nothing. (9) §5.1's "each hashed ... before any row is read" is implemented as every snapshot the run will touch, the record days and every logged day of the moved-end scan's range, verified before the first row of any of them; a logged earlier day with no file is named "missing" in the manifest and the moved-end count says how many sampled markets had no first listing. (10) The decile labels of §9.6 read [0.01, 0.10) first and [0.90, 0.99] last, the range Study 013's p can take. (11) The word "seven" at §5.1 and §6.5 is corrected to "eight" in place, with the date; §5.3 listed eight fields from the first commit. (12) The descriptive sub-analyses of §9.6 that name no trial are computed on the M1 rows (the headline trial; §9.6 names M1 for the alternative floor), and the output says so. (13) The exclusion counts are written in §9.6's order, as an ordered list beside the keyed table, with the one forced swap stated: a bin needs a valid mid, so "row not as recorded" is decided before "outside the decision bins". (14) `results/input_manifest.json` also records the SHA-256 of `APPROVED`, `trials.md` and `pm-view/events.csv` as read by the run.
- **2026-11-17 (chart step, [charts/make_charts.py](charts/make_charts.py); before any data):** §9.6's chart bullet says "[DU26]'s two central figures" and its decile bullet names three reference lines, s = 0.04, 0.13 and 0.18; the chart draws all three, labelled as full quoted spreads. The decile chart's title compares the lowest decile with a published median to the decile with a published median whose midpoint is nearest 0.50 and states the ratio; a decile or split under ten markets is drawn as its count (§9.6, last bullet). The Δ̂ chart's verdict phrase is the §9.5 sentence the run wrote, with the low-power label when it applies. No rule above is changed; nothing has been computed.
