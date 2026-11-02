# Study 013: calibration of Polymarket prices at a fixed horizon before resolution, on markets that resolve after this document's commit

**Pre-registration document**

| Field | Value |
|---|---|
| Date written | 2026-11-02 (the commit's time **D** is the record; London = UTC) |
| Status | pre-registered; **no price at any horizon read for any market; no outcome read; no snapshot row read by the author (the collector's log line and page counts only)** |
| Version | 1.0 (any change after this commit needs a dated amendment appended to §16 before any further step is run) |
| Study type | new family for the programme: first study on prediction-market data ([`QUESTION.md`](QUESTION.md), commit `4fb3776`, 2026-11-02 01:17:49Z by git; [`RESEARCH_AGENDA.md`](../../RESEARCH_AGENDA.md), status on 2026-11-01 and the dated additions of 2026-11-02) |
| Data | Polymarket's public Gamma API (open-market listing, daily snapshots taken by [`collector.py`](collector.py) from **S = 2026-11-03**; one resolution fetch per candidate market after the window) and the CLOB API (`tokens[].winner`, the second outcome source). Verdict `derived` ([`tools/pm_data_terms.md`](../../tools/pm_data_terms.md): read 2026-11-01; re-read 2026-11-02 12:24Z before this commit, effective date unchanged, the row in that file's "Re-reads" table). |
| Instruments | none: a calibration test, not a rule. **No paper order, no paper sleeve, no forward record of a position.** |
| Approval | approved by the orchestrator under the owner's delegation of 2026-10-21 (all decisions on this research programme) and inside the owner's scope of 2026-10-31 (prediction markets only), on the date of this commit. An `APPROVED` file is written at implementation time (§14 step 5), after this commit. |
| Total trial count registered | **3** (§7): C1 and its two companions C1a and C1b |
| Multiplicity decided at | **N = 3** (§9.4; a new family); the programme-wide count, re-counted before the scoring run, reported beside it with no decision weight |
| Design review | a separate session reviewed this document before its first commit ([`DESIGN_REVIEW.md`](DESIGN_REVIEW.md)): 8 must-fix and 14 should-fix points, all changed in the draft before this commit |
| Author | the orchestrator (Qune) |

Nothing in this document reports or implies the result of any test registered here. The question note fixed the question, the two sources, the test object (a logistic recalibration slope), the three trials, the decision row of the power table and the snapshot plan; this document writes them out as rules and fixes what the note left open (§0). Where the two differ, this document governs and says why.

---

## 0. Relationship to the question note, and what this document fixes

Everything in `QUESTION.md` §1–§4 stands. This document fixes, before any data:

1. **The horizon:** h = 24 hours for C1 and C1a; h′ = 168 hours (seven days) for C1b (§6.1). The note proposed "e.g. seven days" for C1b and called one day the conservative choice for finding the effect.
2. **The price field:** p is the midpoint of `bestBid` and `bestAsk` of the market's first listed outcome token in the snapshot of record (§6.2). The note said "the YES-token price" and left the field open.
3. **The outcome, redefined from "the YES token won" to "the first listed outcome token won"** (§6.2, §6.5), because the listing quotes its prices for the first token and many markets' outcomes are not labelled Yes and No (a team, a candidate). The slope b is unchanged by the choice; only the sign of the intercept a depends on it.
4. **The liquidity floor, measured at the horizon, not at resolution:** `volumeNum` ≥ 10,000 USDC in the snapshot of record, plus a spread cap of 0.10 (§6.3). The power table's "clean" count used volume at resolution; the floor here is stricter, so the table's n is an upper bound for this design, and the data step recomputes the row (§9.6).
5. **The other eligibility rules at the horizon** (§6.3), which the note did not have: exactly two outcome tokens; the order-book and status flags; no UMA resolution begun at the snapshot; the snapshot taken before the market's scheduled end; both quotes present with 0.01 ≤ p ≤ 0.99. Each exists so that p is a live pre-event quote on a binary market that can still trade.
6. **The window:** venue resolution time `closedTime` in **[2026-11-04 00:00:00Z, 2026-12-30 00:00:00Z)**, eight weeks of 56 days (§8). The note said the window starts "from the first snapshot date S"; it starts the day after, because a market closing on S cannot have a snapshot 24 hours earlier that is dated S. The first snapshot that can serve as a price source is the one dated S = 2026-11-03 (the daily job's first run, 04:40 UTC), after this commit. **The snapshot of 2026-11-02 (S0, taken at 06:21Z, before D) does not enter the sample for any trial**: its rows exist with their hashes, and the author has not read them, but the rule "pushed before the first snapshot that can enter the sample" is kept exactly rather than argued. If this document's push were to land after 2026-11-03 04:40Z, the snapshot of that day is excluded in the same way and S moves to the next day (§14 step 1).
7. **The snapshot-of-record rule and its gap cap** (§5.2): the latest snapshot dated on or after S whose start time is at least h before `closedTime`; a market whose realised horizon reaches h + 48 hours is out of the trial and counted. The note said "the last snapshot at least h before `closedTime`" without a cap.
8. **The cluster for a market in several parent events** (§6.4): the numerically smallest event id on its snapshot-of-record row.
9. **The outcome rule, written out** (§6.5): UMA status `resolved` in the resolution fetch, `outcomePrices` decoding to exactly 1 and 0, cross-checked against the CLOB's `tokens[].winner` for the first token; any other state excludes the market and is counted.
10. **The estimator and its standard error** (§9.3): maximum likelihood, standard errors clustered by parent event with the usual G/(G − 1) factor; a clustered bootstrap interval reported beside it with no decision weight.
11. **Criteria C1–C4 in the programme's form, adapted to a slope** (§9.5), with C3 at N = 3 as a Bonferroni bar (the deflated Sharpe ratio has no slope analogue), and a window row on the two four-week halves.
12. **The scoring deadline:** the resolution fetch runs on or after **2027-01-20 00:00Z** (three weeks after the window's end, for UMA finality); a market not `resolved` by then is counted, never filled (§11).
13. **Separation of the status and outcome fields in the resolution fetch** (§5.3), so that the data step can fix the sample and recompute power without any outcome being read; the fetched bodies are hashed, not kept.
14. **No historical slice.** The note allowed a labelled replication as a pipeline check; none is possible here, because the closed-market listing carries no price at a horizon before resolution and the programme holds no snapshots before S0. The pipeline is checked on synthetic data only (§6.6).
15. **A permanent halt** for two data-step stops that no amendment may remedy (§5.4), as [METHODS §1.3](../../METHODS.md#13-data-gates-that-can-halt-the-study) provides.

## 1. Question

> Over Polymarket binary markets that resolve after the pre-registration date, is the price at a fixed horizon before resolution compressed towards 0.50 relative to the outcome frequency (logistic recalibration slope b > 1: longshots overpriced, favourites underpriced), and does the compression hold once Sports markets are set aside?

## 2. Hypothesis and grounding

H1: the slope b of §9.1 over the decision sample (C1, §7) is greater than 1 by enough to meet C1–C4. H0: it is not (b ≤ 1, a calibrated or over-dispersed market).

Grounding (`QUESTION.md` §1): [WA26] reports b = 1.112 over 188,509 resolved binary markets and 1,875,570 daily observations to 2025-12 (abstract only; full text HTTP 401 on 2026-11-02, not read); [CR26], read in full, reports negative probability errors in every 5-cent bin from 4 to 45 cents and positive in every bin from 50 to 99 cents (equal child-market weights, to 2026-03-29), with the two-sided pattern "surprisingly absent in Sports".

Why it might not hold here: (a) one fixed horizon of 24 hours, where [WA26]'s abstract says the bias is weakest ("worsens at longer time horizons"), against a figure fitted on observations pooled across horizons; (b) markets resolving in November–December 2026, on a venue whose 2026 listing is larger and more liquid than the samples of either source (inferred, not measured); (c) the liquidity floor removes the thin markets where longshot demand may sit; (d) Sports, which [CR26] found without the pattern, will hold a large part of the sample (`tools/power_pm013.txt`: 38.8 percent of the clean parent events a month and 55.2 percent of the clean markets in the August–October rows carry a Sports tag), which is why C1a is registered.

### 2.4 Designer's prior knowledge (disclosed)

`QUESTION.md` §3.1 in full: the two sources' figures; the desk's 2026-11-01 field checks on 90 markets resolved before the note (which field is authoritative; none can enter the sample); the count probes of 2026-11-02 (no outcome, no wording, no price at a horizon). The author's general knowledge covers Polymarket markets and outcomes to its training cutoff, so no market resolved before D is out of sample for the author ([METHODS §4](../../METHODS.md#4-what-these-guards-do-not-do)); that is why the decision sample is markets resolving on or after 2026-11-04. The author has read no snapshot row: the collector's whitelist excludes the question text, description, slug and group title (the kept outcome labels can name a team or a candidate, so "no wording" means no question text), and the author has looked only at the log line (page count, row count, bytes, hashes) of S0. No parameter in this document was chosen on any price or outcome.

## 3. Literature

[CR26] arXiv:2609.12878 (read in full); [WA26] Princeton senior thesis, handle 88435/dsp01mw22v8973 (abstract only). Both as cited in `QUESTION.md` §1 and the agenda's register. The older favourite-longshot literature is known from the sources' citations and is not added to the register until read.

## 4. Instruments

None. A result here, whatever it is, does not imply any order on the desk; a rule that fades longshots is scope question 5 and would be a later, separate pre-registration.

## 5. Data

### 5.1 Sources

- **Daily snapshots** of the open-market listing, Gamma `GET /markets/keyset?closed=false&limit=100&include_tag=true`, every page, taken by [`collector.py`](collector.py) once a UTC day (scheduled 04:40 UTC; the venue caches the listing for up to five minutes, so a snapshot's prices may be up to five minutes older than its fetch time). Rows kept git-ignored under `data/raw/snapshots/<UTC date>/records.jsonl` with the whitelist of fields in the collector's docstring (no question text, description, slug, group title, image, resolution source or resolver address; every whitelisted key is written on every row, null when the venue omits it); one provenance line per complete snapshot in [`paper-log/snapshots.csv`](paper-log/snapshots.csv) with the SHA-256 of the rows and of the page manifest. **Snapshot time t_s** of a snapshot is its `started_utc` in that file. Nothing is backfilled: a day with no line is a gap, listed by the collector's `check` and by `tools/check_due.py`, never filled.
- **Resolution fetch** (§5.3), once, on or after the scoring deadline: for every candidate market (§6.4), Gamma `GET /markets/<id>` and CLOB `GET /markets/<conditionId>`. Each response body is hashed (SHA-256, byte count, fetch time) into a manifest and **not kept**; the two files of §5.3 are the only record.

Both APIs are public, read-only, called without a key, wallet or account, inside the documented rate limits, with the user agent the collector declares. Polymarket's verdict is `derived`: no raw response or per-market row is committed; the published outputs are aggregates computed by the desk (§13), attributed to Polymarket with the fetch dates.

### 5.2 Snapshot of record and vintage

For a market with resolution time T and horizon h, the **snapshot of record** is the snapshot dated on or after S with the latest t_s satisfying t_s ≤ T − h. If T − t_s ≥ h + 48 hours (a gap, or a market closing early in the day after a gap) the market is not in that trial's sample and is counted; otherwise the realised horizon lies in [h, h + 48 h). The snapshot's row for the market, as taken and hashed, is the only source of p and of the eligibility fields of §6.3. The venue may change a listing's metadata later; nothing is re-read at the horizon, and no price at any horizon is downloaded after the fact.

### 5.3 What the data step may read, and the two files of the resolution fetch

The resolution fetch writes, under `data/raw/resolution/` (git-ignored), two files that no single later step reads together until scoring:

- `status.jsonl`: id, conditionId, `closedTime`, `closed`, `umaResolutionStatus`, `endDate`, `volumeNum`, event ids, tag labels, the two outcome labels, fetch time, body hashes.
- `outcome.jsonl`: id, `outcomePrices`, the CLOB `tokens[]` with `winner`, fetch time, body hashes.

The fetch prints no outcome field. The **data step** (§14 step 6) reads the snapshots and `status.jsonl` only. From them it fixes the data-step sample of each trial by the rules of §6.3–§6.4 (every windowed, eligible market, whatever its UMA status at the fetch: unresolved markets leave the sample at scoring, not here), counts every exclusion, measures the price distribution at the horizon (Ê = the mean over the sample's markets of x² p(1 − p) with x = logit p, and the ten-bin histogram of p), the realised horizon distribution, the number of clusters G, and recomputes the power row of §9.6; it writes these to `results/data_step.{json,md}` (keys named in the study's own words, never a raw venue field name) and the sample's market ids with p, cluster id, early-close flag (§9.6) and trial membership to `results/sample.jsonl` (git-ignored; SHA-256 committed in `results/data_manifest.json`). **No outcome is read, written or printed by the data step**, and its code does not open `outcome.jsonl` (a test asserts it). Only the scoring run (§14 step 9) opens `outcome.jsonl`, and only after `APPROVED`.

### 5.4 Stop rules at the data step

Snapshot days that can serve C1 run from S to 2026-12-28 (56 days: a market closing before 2026-12-30 00:00Z needs t_s ≤ T − 24 h, before 2026-12-29 00:00Z, and the snapshot of 2026-12-29 starts at 04:40Z); those that can serve C1b run from S to 2026-12-22. A snapshot counts as a gap day when its line is missing, when its `distinct_markets` is below half the median of the window's snapshots (a listing cut short by a changed page cap looks complete to the collector), or when a field of §6.3 is null on every row of the snapshot (the venue renamed or dropped it; the collector writes every key).

The study **stops for a dated §16 amendment**, before any outcome is read, if fewer than 42 of the 56 C1 snapshot days exist, or any run of three or more consecutive gap days falls inside S to 2026-12-28 (C1, C1a) or S to 2026-12-22 (C1b). The amendment may only change how gaps are handled (for instance a wider cap, stated with its reason); it may not change h, h′, the floor, the window, the criteria or the trials.

The study **halts permanently, with the verdict "inconclusive (halted at the data step)"** and no amendment, if the check of §6.2 fails (more than 1 percent of the C1 data-step sample's rows have |p − the decoded `outcomePrices[0]`| > 0.02: the price field does not mean what this document says), or if the C1 data-step sample holds fewer than 2,000 clusters (below that, the recomputed ratio of §9.6 exceeds 1 under every E assumption of the power table: 1.22, 1.13, 1.05) or fewer than 5,000 markets (below that the reliability table of §9.6 averages fewer than 500 markets a bin and the Sports and horizon splits are not readable). The counts and the check's figure are published whatever they show.

## 6. Exact rule specification

### 6.1 Horizon

h = 24 hours (C1, C1a); h′ = 168 hours (C1b). The realised horizon T − t_s is reported for each trial (its minimum, median and maximum; the share above h + 24 hours), where T is `closedTime` from `status.jsonl`.

### 6.2 Price

p = (`bestBid` + `bestAsk`) / 2 of the snapshot-of-record row, read as decimal numbers; the venue's listing quotes these for the market's first listed outcome token (`outcomes[0]`, `clobTokenIds[0]`), whatever its label (general knowledge of the API, checked at the data step: on an open market the listing's `outcomePrices[0]` is the venue's own mid for the same token, so |p − `outcomePrices[0]`| ≤ 0.02 is required on at least 99 percent of the C1 data-step sample's rows, else §5.4 halts the study). The list fields `outcomes`, `clobTokenIds` and `outcomePrices` arrive as JSON-encoded strings in the listing (observed by the desk on 2026-11-01; confirmed at the data step): a string value is decoded with a JSON parser first, and a list value is used as it is. **y = 1 if the first listed outcome token won** (§6.5). Because the fit is a logistic regression with a free intercept, which token is "first" does not change b; it changes the sign of a, which is reported and carries no decision weight. The share of sampled markets whose first outcome label is "Yes" is reported.

### 6.3 Eligibility at the horizon (every field from the snapshot-of-record row)

A market is eligible for a trial when all of the following hold on its snapshot-of-record row: exactly two entries in the decoded `outcomes` and in the decoded `clobTokenIds`; `enableOrderBook` true; `active` true, `closed` false, `acceptingOrders` true; `umaResolutionStatus` not in {`proposed`, `disputed`, `resolved`} (the market's resolution had not begun at the snapshot); `endDate` present and t_s ≤ `endDate` (the snapshot precedes the scheduled end, so the price is not a post-event price on a market awaiting resolution); `bestBid` and `bestAsk` present with 0 < `bestBid` ≤ `bestAsk` < 1; spread `bestAsk` − `bestBid` ≤ 0.10; 0.01 ≤ p ≤ 0.99; `volumeNum` ≥ 10,000 (USDC, cumulative at the snapshot). Negative-risk children (`negRisk` true) are eligible, each as its own market. Each exclusion reason is counted in the order written here (a market is counted under the first reason that excludes it).

### 6.4 Candidate set, sample and clusters

The **candidate set** is every market id that appears in any snapshot dated from S to 2026-12-28 inclusive. All candidates are fetched at the resolution fetch. A candidate is in the **window** when its `closedTime` in `status.jsonl` lies in [2026-11-04 00:00:00Z, 2026-12-30 00:00:00Z). A windowed market is in a trial's **data-step sample** when a snapshot of record exists for the trial's horizon (§5.2, with the gap cap) and it is eligible on that row (§6.3). For C1a a market is also required to carry no tag whose label is `Sports` on its snapshot-of-record row (the match is exact, case-insensitive, on the label `Sports`; the labels present in the sample are listed by the data step, and no other label is used to exclude).

**Cluster** = the market's parent event: the numerically smallest entry of the row's event ids (ids parsed as integers; should any id fail to parse, the row's ids are ordered as strings and the data step reports the count); a market with no event id is its own cluster. Markets in different events that share an underlying (the same match, the same price series) are not clustered together, and the note says so (§10, row 6).

The **decision sample** for C1 is the data-step sample less the markets excluded at scoring by §6.5. The data step fixes the data-step sample before any outcome is read, so the counts of unresolved, disputed and 50/50 markets are reported as attrition, never as choices.

### 6.5 Outcome

At scoring, from `status.jsonl` and `outcome.jsonl`: a market **resolves first-token** when `umaResolutionStatus` is `resolved`, the decoded `outcomePrices` has two entries whose decimal values are exactly 1 and 0 in that order, and the CLOB record's token whose id equals `clobTokenIds[0]` has `winner` true while the other has `winner` false; **second-token** when the decimal values are exactly 0 and 1 with the winners reversed. y = 1 for first-token, 0 for second-token. Any other state excludes the market and is counted by kind, in this order: `umaResolutionStatus` not `resolved` at the fetch (unresolved or disputed by the deadline); `outcomePrices` not one of the two vectors (a 50/50 or fractional settlement); disagreement between `outcomePrices` and `winner`; a missing or failed fetch after three attempts. The authoritative-field rule follows the desk's 2026-11-01 checks (`QUESTION.md` §3.1): `outcomePrices` is set before UMA finality, so UMA `resolved` is required and the CLOB flag is the second source.

### 6.6 Engine

New code in `research/013-polymarket-calibration-forward/src/`: the resolution fetch (two output files, §5.3), the data step, the scoring run (logistic MLE; clustered sandwich covariance; clustered bootstrap; the reliability table), and the chart step; the shared library's house-style charts (`qune_research/style.py`), unchanged. Tests written on synthetic data before the data step, including: the snapshot-of-record choice (latest t_s ≤ T − h, the gap cap, the S bound, S0 never chosen); every eligibility rule and its counter; the cluster rule including a market in two events; the decoding of string-encoded lists; the outcome rule on each excluded state; the MLE against a closed-form check (a two-point design where b is known) and against an independent implementation on one synthetic sample to 1e-8; the clustered standard error equal to the ordinary one when every cluster has one member; the data step refusing to open `outcome.jsonl`; the scoring run refusing without `APPROVED` and refusing to run twice; and the gap-day rules of §5.4.

## 7. Registered trials (N = 3)

| ID | Rule | Sample |
|---|---|---|
| C1 | slope b at h = 24 h over all eligible markets resolving in the window | windowed, eligible, resolved (§6.3–§6.5) |
| C1a | C1 with every market tagged `Sports` set aside | as C1, without the Sports tag |
| C1b | slope b at h′ = 168 h; otherwise C1 | as C1 at the longer horizon (a windowed market needs a snapshot of record at least 168 h before T, so markets closing before t_s(S) + 168 h cannot enter; counted) |

C1a is the Sports companion (the note's fragility clause: "supported" for C1 needs C1a not "not supported"); C1b is the horizon companion, reported. Each is judged on its own C1–C4 and the window row.

## 8. Window and the role of each part

| Row | `closedTime` | Role |
|---|---|---|
| **W** | [2026-11-04, 2026-12-30) | **the decision row**: C1–C4 for each trial |
| W1 | [2026-11-04, 2026-12-02) | first half (28 days); the window row |
| W2 | [2026-12-02, 2026-12-30) | second half (28 days); the window row |

There is no in-sample row. The power table's decision row (`QUESTION.md` §2; `tools/power_pm013.txt`: 8 w, distinct parent events among clean markets, uniform E, K = 2.842, n = 44,694, MDE 0.0289 on b − 1, ratio 0.26 of [WA26]'s 0.112; C1a 0.33) is the stated power before data; the data step recomputes it (§9.6) with this design's floor and horizon, which remove markets, so the realised ratio may be higher (a measured Ê above the uniform 0.2159 lowers it). If the recomputed ratio for C1 exceeds 0.50 the study runs as a **labelled low-power check** and every verdict row carries the label.

## 9. Benchmarks, metrics and decision criteria

### 9.1 The test object

Over a trial's sample, with x_i = logit(p_i) and y_i the outcome,

  logit Pr(y_i = 1) = a + b · x_i,

fitted by maximum likelihood, each market one observation with weight 1. The benchmark is a calibrated market, **b = 1** (and a = 0, not tested). The decision quantity is **b̂ − 1**, its sign and its clustered t-statistic t_cl = (b̂ − 1) / SE_cl.

### 9.2 Costs

None: a calibration test. Fees, spread and the tick are not modelled; a reader who wants a return reading of b must compute it with the venue's fee schedule, and the note will say that no such reading is made here.

### 9.3 Estimator and standard errors

The fit is Newton–Raphson on the log-likelihood with step halving, started at (a, b) = (0, 1), stopped when the relative change in the log-likelihood is below 1e-10 or after 100 iterations (a fit that does not converge is reported as such and the trial's row reads "not supported (no fit)"). With π_i the fitted probability, z_i = (1, x_i)ᵀ, H = Σ_i π_i(1 − π_i) z_i z_iᵀ the observed information, and s_g = Σ_{i∈g} (y_i − π_i) z_i the score of cluster g,

  V_cl = G/(G − 1) · H⁻¹ (Σ_g s_g s_gᵀ) H⁻¹,

and SE_cl is the square root of its (b, b) entry. Reported beside it, no decision weight: the ordinary standard error from H⁻¹, and a clustered bootstrap percentile interval for b at 95 percent (the 2.5 and 97.5 percentiles over 2,000 resamples of clusters with replacement, `numpy.random.default_rng(13)`, fixed now; a resample whose fit fails to converge or holds one outcome only is dropped and counted, and the interval is reported as not available if more than 1 percent are dropped), the form [WA26]'s abstract describes.

### 9.4 Multiplicity

The programme's deflated Sharpe ratio has no slope analogue, so C3 is a Bonferroni bar at **N = 3**: one-sided p ≤ 0.05 / 3, that is **t_cl ≥ 2.128** (standard normal). Beside it, no decision weight: the bar at N = 12 (one per study to date, this one included and Study 012, closed unopened, excluded: z ≥ 2.638) and at the programme-wide count of every trial registered in `research/*/trials.md` and the desk's private registry, re-counted immediately before the scoring run and written to `trials.md` with the method of the count. The note says, before any result, that the question was chosen after eleven earlier studies and that only N = 3 decides.

### 9.5 Verdict table

For each trial k on W: **C1** b̂ − 1 ≥ 0.02 (a practical margin, the programme's analogue of the 0.10 Sharpe margin: at b = 1.02 a market priced 0.35 has an implied outcome frequency 0.28 points lower, below what any reader would act on; it stops a positive t on a negligible slope from counting); **C2** t_cl ≥ 2.0; **C3** t_cl ≥ 2.128 (§9.4; C3 implies C2 here, and both are kept for form, so that a reader of the earlier studies finds the same four rows); **C4** b̂ − 1 > 0 on W1 and on W2 fitted separately (the window row; each half's t_cl reported, not tested).

| Verdict (C1, the headline) | Condition |
|---|---|
| **Not supported** | Any of C1–C4 fails for C1 on W, or the C1 fit does not converge. |
| **Inconclusive (fragile: Sports)** | C1–C4 hold for C1, but C1a is "not supported" on its own C1–C4. |
| **Supported in one forward window** | C1–C4 hold for C1 and C1a is not "not supported". |
| **Inconclusive (halted at the data step)** | A permanent halt of §5.4; no slope is fitted. |

Precedence: halted > not supported > inconclusive (fragile) > supported. The companions' rows read "not supported" or "meets C1–C4"; C1b's row adds whether b̂(h′) > b̂(h), the direction [WA26]'s abstract reports, as a descriptive line. **Low-power label:** if the data step's recomputed ratio for C1 (§9.6) exceeds 0.50, every row adds "(low-power check: the published effect could not have been seen at 80 percent power)". No sentence may call a result "supported" without "in one forward window" and the window's dates, and every verdict states the horizon, the floor and the share of the sample carrying a Sports tag. The note's first paragraph carries the §2.4 disclosure in one sentence.

### 9.6 Pre-registered descriptive sub-analyses (no decision weight)

- For every trial on W, W1 and W2: n markets, G clusters, b̂, â, SE_cl, SE_ordinary, the bootstrap interval, t_cl, log-likelihood of the fit and of the calibrated model (a = 0, b = 1).
- **Power, realised (data step, before any outcome):** for each trial, n, G, the measured Ê over the data-step sample's p, SE(b̂) under H0 = 1 / √(G · Ê) (the cluster count as the independent unit, as the note's decision row), MDE = 2.842 · SE and 2.486 · SE, and **the ratio = 2.842 / √(G · Ê) / 0.112**, which is the figure the low-power label of §9.5 reads for C1.
- The **reliability table**: ten bins of p ([0.01, 0.10), [0.10, 0.20), …, [0.90, 0.99]), each with n, mean p, outcome share, the difference in percentage points and its clustered 95 percent interval; so that the result can be read against [CR26]'s Figure 1 and [WA26]'s diagrams.
- Brier score, log-loss, and the Brier skill score against the sample's own outcome base rate, for each trial.
- **Early closes.** `closedTime` depends on the outcome for markets that can resolve early (a "by date" market closes at the event when the event happens and at the scheduled end when it does not), and a venue proposal that lags the event by more than h would put a decided price into the snapshot of record even though §6.3 passes the row. The data step flags each market as **early** when `closedTime` is more than 24 hours before the `endDate` on its snapshot-of-record row (no outcome read), and the scoring run reports b̂ with its clustered interval for the early and the other markets separately, with the early share. Descriptive: the split is not a trial and does not move any verdict.
- b̂ by tag family (from the snapshot-of-record row's labels, with precedence `Sports` > `Politics` > `Crypto` > other for a market carrying several; a family with fewer than 500 markets pooled into "other"), by liquidity tercile of `volumeNum` at the horizon, and by realised-horizon half (below and above the median); descriptive, listed now so that the split is not chosen after.
- Every exclusion count of §6.3–§6.5 in order, the gap days inside the window by kind (§5.4) and the markets they removed, the candidate count, the windowed count, the count of markets in more than one event, and the share of markets whose first outcome label is "Yes".
- The comparison with [WA26]'s 1.112 and with [CR26]'s interior-bin errors, descriptive only (different samples, horizons and weights).
- Charts to the house standard (`qune_research/style.py`): the reliability diagram with the fitted curve and the diagonal; b̂ with intervals for C1, C1a, C1b, the tag families and the early split.

### 9.7 What did not work

Study 001 §9.7, unchanged; an empty section is not acceptable.

## 10. Known pitfalls

| # | Pitfall | Handling |
|---|---|---|
| 1 | The author's knowledge covers resolved markets to its cutoff | decision sample resolves on or after 2026-11-04, after D; no historical row (§0 item 14) |
| 2 | `outcomePrices` is set before UMA finality; some markets settle 50/50 or are disputed | UMA `resolved` required, CLOB `winner` as the second source, every other state excluded and counted (§6.5) |
| 3 | The listing is a daily snapshot, so the "24-hour" horizon is 24–48 hours in practice and longer across a gap | realised horizon reported; gap cap h + 48 h; stop rules on gaps (§5.4) |
| 4 | Snapshot S0 was taken before this commit | excluded from every trial by rule (§0 item 6) |
| 5 | A market still open after its scheduled end carries a post-event price | t_s ≤ `endDate` and no resolution status at the snapshot (§6.3) |
| 6 | Markets in different parent events share an underlying (the same match in several events, the same price series) | not clustered together; disclosed; the tag-family rows show where the sample sits |
| 7 | Negative-risk children are mutually exclusive within an event | clustered by event; each child one observation; the count of such markets reported |
| 8 | Sports will dominate the sample | C1a registered; the Sports share stated in every verdict |
| 9 | The venue's listing is cached up to five minutes | t_s is the fetch start; at a 24-hour horizon the staleness is negligible and stated |
| 10 | Polymarket's verdict is `derived`: the snapshots and the sample file cannot be published, so a reader cannot recompute the result from the tree | the separate-session recomputation (§14 step 11) runs on this host from the withheld files; their SHA-256 are committed; the published tables are aggregates; stated in the note as a limit on reproducibility |
| 11 | The resolution fetch is one call per candidate market (hundreds of thousands, most of them short-dated Sports) | detached, logged, retried; a market unfetched after three attempts is counted (§6.5); the fetch's batching is an implementation choice recorded in `trials.md`, not a rule |
| 12 | The venue could rename or drop a field under the collector, which writes every whitelisted key with null when absent | a snapshot with a §6.3 field null on every row is a gap day (§5.4) |
| 13 | The author chooses h, the floor and the window with the venue's listing counts in view | all fixed here from counts only, before any price at a horizon or any outcome; the data step may not move them |
| 14 | The outcome file sits on disk from the resolution fetch to the scoring run | the fetched bodies are not kept; the data step's code does not open `outcome.jsonl` (a test asserts it); only process stops anyone looking between the fetch and `APPROVED`; stated, not provable |
| 15 | `closedTime` depends on the outcome for markets that can resolve early, so the snapshot of record of an early close may hold a decided price when the venue's proposal lags the event by more than h | kept in the sample (removing them would select on the outcome); the early split of §9.6 shows the size; the same mechanism sits inside [WA26]'s horizon bands and is stated in the note |

## 11. Forward record

This study is itself a forward test: nothing is scored before the window closes and the deadline passes. There is no position and no paper order. The timeline that cannot be gamed: every snapshot's hash is committed within the day it is taken (the daily job commits its provenance line), and `closedTime` of every windowed market lies after this commit. **Scoring deadline 2027-01-20 00:00Z**: the resolution fetch runs on or after it, once; markets not `resolved` by the fetch are counted (§6.5). No interim fit is run on any part of the window.

## 12. Risk limits

Not applicable: no order of any kind.

## 13. Repository layout

`research/013-polymarket-calibration-forward/`: `QUESTION.md`, this file, `DESIGN_REVIEW.md`, `trials.md`, `collector.py` and its tests, `src/`, `tests/`, `reproduce.sh` (refuses without `APPROVED`; `--score` runs once and refuses if `results/score/` exists), `results/` (data manifest, data-step outputs, score outputs: the slope table, the reliability table, every count; never a per-market row), `charts/`, `README.md`. Git-ignored: `data/raw/` (snapshots, the resolution fetch's two files and its hash manifest) and `results/sample.jsonl` (added to `.gitignore` with this commit); their SHA-256 in `results/data_manifest.json`.

## 14. Order of operations

1. This document and `trials.md`, reviewed for design by a separate session before commit; committed and pushed before the snapshot of S = 2026-11-03 (04:40 UTC). Should the push land after that time, the snapshot of that day is excluded like S0 and S moves to the next day, recorded as a dated §16 note (an ID-only correction).
2. Collection: daily snapshots from S through at least 2026-12-28 (the last that can serve C1); the job keeps running after that for the prediction-market view.
3. Code and tests on synthetic data (§6.6); a separate-session code review before step 5. Due-register lines for the window's end and the scoring deadline are added with this step. The `.gitignore` entries of §13 are added with this commit.
4. Resolution fetch on or after 2027-01-20 00:00Z, logged in `trials.md` before it runs; two files and a hash manifest (§5.3).
5. `APPROVED` written and committed (it may be written at step 3's end; the scoring run still waits for steps 6–8).
6. Data step, logged in `trials.md` before it runs: sample, exclusion counts, price distribution, realised horizon, early flags, recomputed power (§9.6); stop and halt rules (§5.4). Outcome appended. No outcome read.
7. Programme-wide re-count (§9.4) and the scoring-run row in `trials.md`, committed and pushed.
8. (Reserved: a dated §16 amendment if step 6 stopped for gaps; a halt ends the study at step 6 with its verdict row.)
9. `./reproduce.sh --score`, once; outputs committed whatever they show.
10. The note (README), §9.5 verdict, §2.4 disclosure first, §9.7.
11. Separate-session recomputation of every published figure from the withheld files on this host.
12. Charts, reviewed against the chart standard.
13. The prediction-market desk view the agenda promised, scored the same way, as a separate piece of work.

Time labels are written from `git log` or the machine clock, never estimated.

## 15. Things this study deliberately does not do

It does not change h, h′, the floor, the window, the trials or the criteria after this commit; test a return-unit tail effect or a fade-the-longshots rule; weight markets by volume or by event; use any Kalshi data; read a price at a horizon other than from the snapshot of record; run any row on a second download of a price; run any historical slice; remove early closes from the sample; or claim to replicate [CR26] or [WA26].

## 16. Amendments

None.
