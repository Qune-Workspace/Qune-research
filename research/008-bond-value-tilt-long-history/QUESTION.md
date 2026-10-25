# Study 008: question choice and design constraints (step 0, before the pre-registration)

*Qune, 2026-10-25 (the commit's time is the record; London = UTC). Committed before `PREREGISTRATION.md` exists, before any CPI value or real yield is computed on any window, and before any file is read for this study. This is candidate V of the agenda refresh ([`RESEARCH_AGENDA.md`](../../RESEARCH_AGENDA.md), dated addition and precision of 2026-10-25, commits `75f6a70` and `7ea34ac`; [`tools/power_refresh.txt`](../../tools/power_refresh.txt)). The note fixes the rule, the trials, the windows, the family count and the order of operations, so that the pre-registration can be written from it without a second look at any data. Where this note and the later pre-registration differ, the pre-registration governs and must say why.*

## 1. The question, and why this form

Studies 006 and 007 have run three of the signals the fixed-income style literature times duration with on Study 006's frozen synthetic 7–10-year leg over 1969–2018: the sign of the term spread, the sign and level of carry, and the 12-month trend. The style papers name value beside carry and momentum [AMP13, BPR18]; it is the one not yet run on this leg, and power does not separate it from the other refresh candidates (all inside the 2% bar, `power_refresh.txt`).

**Decision: a tilt by the level of the real yield.** The question:

> **Does scaling a long-only intermediate-duration position by the level of its real yield (the 10-year yield less trailing 12-month CPI inflation) improve risk-adjusted return over the same average exposure held throughout, after realistic costs, on 1974–2018?**

Primary rule **T1, real-yield tilt by rank.** At each month end m, the real yield is r_m = DGS10 at the month end (the same month-end convention and FRED file Study 007 used for its carry) less π_m = CPI(m−1)/CPI(m−13) − 1, where CPI is the all-items CPI for urban consumers, **not seasonally adjusted** (FRED `CPIAUCNSA`). The index for month m−1 is published in the middle of month m, so it is known at the month end; the index for month m is not, and is never used. The weight in the duration leg over the next holding period is the percentile rank of r_m among all month-end real yields observed so far (expanding window, at least 60 observations; average-rank percentile as 007), w ∈ [0, 1]; the rest is in Study 001's cash leg. A higher real yield means more duration. No threshold, scale or smoothing.

What the sources say, and what this form departs from (read 2026-10-25; agenda precision): [AMP13]'s main bond value measure is the 5-year change in 10-year yields; its Table I, Panel C reports the real bond yield (10-year yield less a 5-year inflation **forecast**) as an alternative, 1983–2011, high-minus-low 2.0% a year, t 3.78 (reported). [BPR18] measures government-bond value as a real yield against survey inflation expectations (reported from a search summary only; the publisher PDF was not found). Three departures, disclosed now: (1) both papers rank bonds **across countries**; this is a time-series rule on one US leg against bills, which neither reports, so a negative result would not contradict them; (2) trailing 12-month inflation is a **proxy** for a forecast, because no public monthly inflation-forecast series back to 1969 has been checked; (3) [AMP13]'s sample lies inside the window, so the window is in-sample for the literature as well as for the family.

Not chosen: [AMP13]'s main measure, the 5-year yield change, because it is close to the negative of the 5-year return ([AMP13]'s own words), a long-horizon reversal of the trend signal 007 already ran; it would be its own question with its own power line, not a companion here.

## 2. Trials, family count and the fragility rule

### 2.1 Registered trials (N = 3)

Study 007's companions moved its minimum history, and an expanding rank does not depend on its minimum history once it is reached: 007's T1a had the same weights as T1 on the test window and T1b differed only by starting later (007 README, disclosed at its gate). **That design miss is not repeated.** Each companion here moves a choice that changes the weight path on the test window:

| ID | Rule | Why registered |
|---|---|---|
| T1 | real-yield tilt, headline CPI, expanding rank, minimum 60 months (primary) | the question |
| T1a | the same with core CPI (all items less food and energy, not seasonally adjusted, FRED `CPILFENS`) for π | fragility companion: the inflation proxy, the one judgement in r |
| T1b | the same as T1 with a **trailing 120-month** rank instead of an expanding one (first weight 1979-07; scored against T1 on 1979-07 to 2018-12) | fragility companion: the rank window, and the check on persistence (§3.1) |

"Supported in history" for T1 needs T1a and T1b not "not supported" on the same criteria (006's fragility rule, kept). Both series are fetched once at the data step; whether either is revised in FRED's current vintage is checked there against ALFRED vintages for a sample of dates and stated, before any real yield is computed.

### 2.2 Family count

Criterion C3 (deflated Sharpe ratio ≥ 0.95) is decided at the **programme-level family count**, as in 007 §2.2: every trial of a duration-timing rule on the 7–10-year Treasury leg (IEF or the synthetic leg) over a window overlapping 1974–2018 whose return had been seen when this study's history step runs. 14 before this study (007's pre-registration §9.4: 003, 005 and 006 three each, 007 five), **17 with this study's three**, re-counted from the desk's registry and the public trial logs immediately before the history run (any addition raises it). N = 3 and N = 10 are reported beside it.

### 2.3 Power, restated (the agenda's rule, step 2)

From `tools/power_refresh.txt` (committed before this note; nothing new read): window July 1974 to the first execution date of January 2019, about **534 periods** (sixty month-end real yields from 1969-07; the exact count fixed by the data step). The C2 test can see **1.60% a year (0.207 Sharpe)** at sd(w − w̄) = 0.5, the conservative figure that binds, and 0.93% (0.119) at a uniform rank weight; an edge of 1% a year or less at the conservative dispersion cannot be seen, and the note's first paragraph says so. The forward record alone: about 4.8% a year at 60 months. The volatility check of 006 §2.3 is repeated once on the 534 periods before any rule return (bar 10.18% a year); above it the study is a low-power check.

## 3. Design problems, and the decisions that resolve them

### 3.1 What the author has seen, and the persistence risk

The leg and the window are those of Studies 006 and 007, whose results the author has read: both primary rules met all four criteria with t near 2 (006 t 2.06, 007 t 2.10) and both verdicts are "inconclusive (fragile)". The author also knows, from general knowledge and not from this repository, the broad path of US real yields: negative or low in the mid-1970s, highest in the early 1980s, falling for most of the following decades. So the sign of what an expanding rank does in 1974–1990 is partly foreseeable: low weight in the high-inflation 1970s and high weight in the early 1980s, when long bonds rallied. An expanding rank of a level with a secular decline can therefore act as a time trend that is right once. Decisions, fixed now:

- **T1b's trailing 120-month rank** adapts to the drift; if T1 passes and T1b is "not supported", the verdict is "inconclusive (fragile)".
- **An era row in the verdict table:** if T1 passes C1–C4 but mean(T1 − B3) is ≤ 0 over 1986-01 to 2018-12 (after the real-yield peak; 396 months, chosen now as the first January after the 1981–85 peak years), the verdict is **"inconclusive (one era)"**. No other sub-window has decision weight; 006's three rate eras and the two halves (1974-07 to 2002-12, 2003-01 to 2018-12) are reported, not selected from.
- **Overlap with 006 and 007, measured from signal paths only** at the data step: the correlation of T1's weight with 007's T1 weight and with 006's T1 holding over the window, reported before any return. If either exceeds 0.8, the note's headline says the result is not independent of that study's, whatever the verdict.

### 3.2 Gate, costs and turnover

Unchanged from 007 §3.2 and §3.3, which apply as written to a fractional weight: G1 ≤ 0.18% a year computed once for each of the three weight paths on 2003–2018 from signal paths and instrument returns only; G2 inherited as observed (0.131); a trial failing G1 is dropped before any return; if T1's fails, the study halts as "inconclusive (gate)". Costs 2 bp a side (stress 4 bp) on |w_t − w_{t−1}|; "low-powered" below 8 units of one-way turnover; each trial's B3 holds its own mean weight, from signals only.

### 3.3 Windows and verdict table

- **1974-07 to 2018-12, synthetic throughout: the test**, criteria C1–C4 of Study 001 §9.5 at base costs, C3 at the family count.
- **2019-01 to 2026-09: an episode, not a test**, run once after the note with no decision weight, actual IEF and BIL with the synthetic series alongside, as 006 §8.2 and 007.
- **The forward record: the only clean test.** Shadow only, no paper order, 006 §11 and 007's forward code: the weight to four decimals with r, π, the CPI month used, the rank and the months behind it; scored once after 60 periods.

**Verdict table (for the pre-registration's §9.5).** For T1: "supported in history; forward record pending" needs C1–C4 at base costs, C3 at the family count, the volatility bar met, T1a and T1b not "not supported", and the era row passed; "not supported" if any of C1–C4 fails; "inconclusive (fragile)" if a companion fails; "inconclusive (one era)" if the era row fails; "inconclusive (gate)" if the gate fails. Precedence: not supported > inconclusive (gate) > inconclusive (one era) > inconclusive (fragile) > supported.

## 4. Why not the alternatives

- **The 5-year yield change [AMP13 main measure].** §1: a long-horizon reversal of trend; its own question.
- **Survey inflation forecasts** (as both papers use). Not checked for a public monthly series covering 1969–2018; if one is found before the pre-registration, the pre-registration says why it is or is not used, and a change of T1's proxy after this note would be an amendment with a reason, before any data step.
- **A z-score or fixed scale of the real yield.** A scale would be set with the author's knowledge of the 1980s peak; the rank has none.
- **Cross-country value.** Outside the approved and delegated universe.
- **Combining value with carry and trend.** Three seen signals plus a new one; the combination is a later question once V's own verdict exists.

## 5. What this note does not do

No file was read for this study, no CPI value, real yield, rank or weight was computed on any window, and no parameter was chosen on any study's data. Every figure above is from `tools/power_refresh.txt` and the published notes of Studies 006 and 007. Order of operations after this note: pre-registration and `trials.md` (three rows), pushed before the data step; data step (hash-check and copy 006's frozen files; fetch `CPIAUCNSA` and `CPILFENS` once with a manifest; vintage check; dates and values only); real-yield, rank and weight modules with tests (007's rank code reused where it applies); `APPROVED`; overlap correlations and gate once; volatility check once; family re-count; history run once; note; episode once; separate-session recomputation; forward record. Time labels are written from `git log`, not estimated.

Literature: [AMP13] and [BPR18] from the agenda's register, Crossref-checked on 2026-10-22 (`tools/citations_check.txt`); [AMP13]'s definitions were read from the authors' PDF on 2026-10-25, [BPR18]'s from a search summary only. No new references.
