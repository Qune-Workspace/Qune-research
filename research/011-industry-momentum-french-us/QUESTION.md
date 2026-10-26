# Study 011: question choice and design constraints (step 0, before the pre-registration)

*Qune, 2026-10-26 (the commit's time is the record; London = UTC). Committed before `PREREGISTRATION.md` exists, before any industry file of the Kenneth French Data Library is downloaded for this study, and before any industry return is read on any window. This is the question the agenda's dated additions of 2026-10-26 14:2xZ named as the next question note ([`RESEARCH_AGENDA.md`](../../RESEARCH_AGENDA.md); [`tools/power_industry.txt`](../../tools/power_industry.txt), commit `c765787`; check (a), commit `0d9d6f4`). Those additions asked this note to answer four checks before it fixes anything: (a) re-run the check for later work on the library's pre-1963 industry months; (b) choose the industry set and the long/short share in advance, with the reason; (c) state that a test on the library is a variant of [MG99], not a replication; (d) keep Study 010's window rule. §1–§5 below do that, plus the family count, the power of each row and the vintage plan. Where this note and the later pre-registration differ, the pre-registration governs and must say why.*

## 1. The question, the source paper and its rule

**Decision: cross-sectional industry momentum, [MG99]'s headline rule, on the library's 17 value-weighted US industries, decided on the months outside [MG99]'s sample.** The question:

> **Does holding the three US industries with the highest past six-month return long and the three with the lowest short, each cohort held for six months, earn a positive return over the months outside Moskowitz and Grinblatt's 1963–1995 sample (1927–1963 and 1995–2026)?**

**Source paper.** Moskowitz and Grinblatt, "Do Industries Explain Momentum?", Journal of Finance 54(4):1249–1290 (1999), doi:10.1111/0022-1082.00146; read 2026-10-26 from the published article's text layer (course copy archived by the Internet Archive, SHA-256 `df0570fc…8721d9`, the copy named in `tools/power_industry.py`; text extracted locally, not committed). What it says (reported, quoted from that copy):

- The industries: "20 value-weighted industry portfolios are formed for every month from July 1963 to July 1995. Two-digit Standard Industrial Classification (SIC) codes are used to form industry portfolios".
- The rule: industries "sorted on their past six-month raw returns and a zero investment strategy is formed that is long the three highest past return industries and short the three lowest, holding the positions constant for six months, and recomputing the strategy monthly" (Table II caption); average 0.43 percent a month. Its t-statistic sits in a table image with no text layer in this copy: unread.
- No skipped month in the headline rule: "the 0.43 percent per month average return for industry momentum reported in Table III, Panel A (which does not skip a month)"; skipping one month gives 0.40 percent ("negligibly differs").
- Other horizons: Table III "reports the L = 1-, 6-, 12-month and H = 1-, 6-, 12-, 24-, 36-month strategies", and the paper calls its results "consistent with the findings of Jegadeesh and Titman (1993) for individual stock returns" (whose profits are strong at 3 to 12 months and diminish beyond a year; that description is of the individual-stock results, not of Table III itself).
- The industries are "formed monthly ... using CRSP SIC codes, which allow for time-variation in industrial classification" (Table I caption); its list of 20 ends with "20. Other".
- The sample: "The raw return profits correspond to the July 1963 to July 1995 time period".

**Primary rule M1.** Industries: the library's 17 industry portfolios, value-weighted, monthly. At the end of each month c − 1 every eligible industry is ranked on its compounded return over months c − 6 to c − 1 (no skipped month, as the paper's Panel A); cohort c is long the top three and short the bottom three, equal weight within each leg, and is held for months c to c + 5. Write W(m) and L(m) for the top three and bottom three ranked at the end of month m. In month t six cohorts are held (ranked at the ends of t − 1 to t − 6); the decision difference is

  d_t = (1/6) Σ_{j=1..6} [ (1/3) Σ_{i ∈ W(t−j)} r_i,t − (1/3) Σ_{i ∈ L(t−j)} r_i,t ],

a zero-investment return, tested against zero, as the paper reports its profits. The winners' and losers' legs and their difference from the equal-weight average of all 17 industries are reported beside d, with no decision weight. Eligibility (fixed now, before any file is read): an industry is ranked at the end of month c − 1 only if it has a return in each of the six formation months; if a held industry has no return in a holding month, its leg averages over the members that have one. The data step counts, per month, how many of the 17 (and 30) industries have a return (a count of missing codes, not a return) and reports it; if any decision-window month has fewer than 12 of the 17 (or, for M1a, fewer than 20 of the 30) eligible, the data step stops and says so before any signal is computed, and the pre-registration decides the remedy before anything else is read. The library's "Other" group is ranked like any industry, as [MG99]'s list includes "20. Other". First return month with all six cohorts held: 1927-06 (library from 1926-07; first formation 1926-07 to 1926-12; first holding month 1927-01).

**Check (b), the industry set and the share.** The paper uses 20 industries and three a side: 15% of the cross-section long, 15% short, 30% in all. Of the library's sets (10, 12, 17, 30, 38, 48, 49), 17 is the nearest in count to 20, and three a side keeps the paper's stated rule word for word at 35% of the cross-section (17.6% a side). The alternative that keeps the share instead is 30 industries with five a side (33%, 16.7% a side); it is registered as a companion (M1a). The primary keeps the count of three because the paper states the rule in those words and the share only follows from its 20 industries. Not chosen: 10 and 12 (three a side is 60% and 50% of the set, a different object); 38, 48 and 49 (further from 20, and finer sets carry thinner industries in the 1920s and 1930s: inferred, not checked, since that would need the firm counts). Chosen now, before any file is downloaded.

**Check (c), a variant, not a replication.** The library assigns firms by four-digit SIC at the end of June (Compustat codes for fiscal year t − 1, else CRSP codes), into 17 or 30 groups; [MG99] used two-digit SIC codes into 20 groups, formed monthly from CRSP codes that "allow for time-variation" (Table I caption), not reassigned once a year. The groups and their updating differ, so a test on the library tests a variant of [MG99]'s rule, not the rule on [MG99]'s data, and its result on the paper's own months is not a replication either. The README and the verdict say so.

## 2. Trials, family count and power

### 2.1 Registered trials (N = 3)

Trial ids are M1, M1a, M1b; the window ids I1, I2 are those of `tools/power_industry.txt`.

| ID | Rule | Why registered |
|---|---|---|
| M1 | 17 industries, top 3 / bottom 3, formation t − 6 to t − 1, six-month overlapping holding | the question, as the paper's headline rule on the nearest library set |
| M1a | 30 industries, top 5 / bottom 5, otherwise as M1 | fragility companion: the industry set and the share (33%, near the paper's 30%) |
| M1b | 17 industries, top 3 / bottom 3, formation t − 12 to t − 1, six-month holding | fragility companion: the formation window, the paper's main free parameter (its Table III reports L = 12 beside L = 6) |

"Supported" for M1 needs M1a and M1b not "not supported" on the same criteria (Study 006's fragility rule, kept). M1b's first month with all six cohorts held is 1927-12 (first formation 1926-07 to 1927-06), so its I1 window has 427 months; M1 and M1a use 1927-06.

Not registered: the skip-month form (the paper reports 0.40 against 0.43 percent a month, "negligibly" different, so it would move little), the one-month/one-month rule (§4), equal-weighted industries (§4).

### 2.2 Family count

This is a new family for the programme: no earlier study ranked industries. It is related to Study 010 (momentum, the same library, overlapping months) but times different assets in a different way (cross-sectional ranks of industries, not the sign of each factor's own past return), so it is counted as its own family: **N = 3**, used for criterion C3 (deflated Sharpe ratio ≥ 0.95). The relationship is disclosed; the programme-wide trial count, re-counted from every `research/*/trials.md` immediately before the history run, is reported beside the result with the deflated Sharpe ratio at that count, with no decision weight, as in Study 010.

### 2.3 Power of each row ([`tools/power_industry.txt`](../../tools/power_industry.txt); M1b's rows by the same formula)

Arithmetic on month counts only (K = 2.842 for a Newey–West t ≥ 2.0 at 80% power; nw = 1.00 and 1.108, the largest ratio observed in the programme, not a bound; six overlapping six-month cohorts may carry a larger nw than any series seen so far).

| Row | Months | N | Detectable Sharpe(d) | vs the 006–008 pool's 0.321 | Status |
|---|---|---|---|---|---|
| I1, before the paper's sample | 1927-06 to 1963-06 | 433 | 0.473 / 0.524 | 1.47× / 1.63× | low-power check; used by later work for related rules (check (a)) |
| I2, after the paper's sample | 1995-08 to 2026-08 | 373 | 0.510 / 0.565 | 1.59× / 1.76× | low-power check; after the sample's end (the paper was published in 1999, so its first four years precede publication) |
| **O = I1 + I2, outside the paper's sample** | both | **806** | **0.347 / 0.384** | 1.08× / 1.20× | **the decision row** |
| M, the paper's window | 1963-07 to 1995-07 | 385 | 0.502 / 0.556 | | in-sample for the literature; reported apart, no decision weight |
| full history | 1927-06 to 2026-08 | 1,191 | 0.285 / 0.316 | | reported, no decision weight (mined in part) |
| M1b on O | 1927-12 to 1963-06 and I2 | 800 | 0.348 / 0.386 | | its own months |

In return units, the 2%-a-year bar holds on O if sd(d) ≤ 5.77% a year (5.21% at nw 1.108). A long-short of three industries against three will very likely have a larger sd (inferred, not read), so O is a test in Sharpe units and its title will say so; at an assumed sd of 15% a year (an assumption, not a measurement) the detectable mean would be about 5.2–5.8% a year, about the size of the paper's headline 0.43% a month (5.2% a year, simple × 12). So O can see an edge of the paper's reported size, not a smaller, decayed one.

**Window rule, check (d) (fixed now).** The decision is taken on O only, in the words of check (d) ("paper's window reported apart, decision on the months outside it"). This is stricter than Study 010's actual rule, which decided on the full history H and used the months outside its paper's window only as a condition: 010's outside months (560) could see only 0.416 / 0.461, while O's 806 can see 0.347 / 0.384, so here the clean months can carry the decision themselves. M (the paper's months) and the full history are reported apart, with no decision weight. I1 and I2 are each reported; neither decides alone. If M1 meets the criteria on O but the mean of d is ≤ 0 on I1 or on I2, the verdict is **"inconclusive (one side of the paper's sample only)"**, the counterpart of Study 010's "inconclusive (paper's window only)": an edge carried by one stretch alone is not this study's evidence.

O is two stretches joined at a gap of 385 months: Newey–West lags do not bridge 1963-06 to 1995-08 (autocovariances are taken within each stretch; the pre-registration fixes the estimator). Return months only count as outside the sample: the cohorts held in I2's first months are ranked on formation months that include the paper's window (for longer under M1b's twelve-month formation), as `tools/power_industry.py` states.

## 3. What the author knows before choosing, and the vintage plan

### 3.1 Known before any data

- [MG99]'s positive result on 1963–1995 (§1), and its Table III statements on horizons.
- **Check (a), re-run today (15:1xZ, search summaries only, nothing below read in full; queries: "industry momentum 1926-1963 Fama French industry portfolios six-month formation pre-1963 out-of-sample Moskowitz Grinblatt" and "\"industry momentum\" out-of-sample \"1927\" OR \"1926\" Kenneth French 30 industry portfolios replication"):** one summary reports that Faber (2010) used the library's 10 industries from 1926 to 2010 (that his paper studies relative-strength, that is ranking, rules is the author's general knowledge, not read); a paper titled "A Century of Profitable Industry Trends" and an arXiv paper refining it (2412.14361) are reported to run a long-only trend rule on the library's 48 industries from 1926 to 2024; an Aalto thesis extends a 2007 industry lead-lag predictability study backwards and forwards and reports the effect specific to the original sample. Together with the uses found at 14:2xZ (agenda, check (a)), this confirms the label: **I1 is used by later work for related rules**, including at least one ranking rule on the library's pre-1963 months (Faber, by summary; his exact rule and windows not read). No source found uses [MG99]'s six-month/six-month top-three rule on the 17- or 30-industry sets before 1963; the search was short and is not proof that none exists. Whatever results the abstracts and summaries state are known to the author.
- General knowledge (no source read here): momentum strategies crashed in 1932 and in 2009 [DM16]; US markets fell in 1929–32; post-publication returns of published anomalies are on average lower than in-sample (a general finding, not checked for this rule).

The author has not seen any industry's six- or twelve-month return computed over 1926–1963 or 1995–2026, nor any ranking on them, and does not know which industries led or lagged in any month. No episode above was used to choose anything: the set and the share follow from the paper's 20 industries and its stated three-a-side rule (§1, check (b)); the windows follow from the paper's stated sample and the library's start.

### 3.2 Vintage

The library rebuilds its whole history each month and says historical returns can change (Study 010's note, §3.2, read 2026-10-26 06:1xZ; the same library). Decisions, as in Study 010:

- **One snapshot.** The data step downloads the 17- and 30-industry monthly files once; records SHA-256, byte size, the download time and the release in each file's header; commits them with a manifest. Every history row uses that snapshot only. No second download before the history run.
- **The vintage is part of the sample.** The note names the release; a later release may give other numbers, a property of the source, stated in the README.
- **Forward record.** Shadow only: a long-short of US industries cannot be held with the approved instruments, so there is no paper sleeve. At each later month end the three trials' cohorts for the next month are recorded from the latest release, with its hash; scoring after 60 holding months, from one named release, with a vintage row against the snapshot, as in Study 010.

## 4. Why not the alternatives

- **The one-month/one-month rule (IM(1,1)).** The paper calls it "remarkably strong", but it also reports that skipping a month "eliminates the profitability" of it and discusses lead-lag and microstructure effects; it turns over the whole book monthly. Not the paper's headline rule; not registered.
- **Equal-weighted industries.** The paper's industries are value-weighted; its equal-weighted variant in the text is a different portfolio (`tools/power_industry.py`). Not registered.
- **The 48 or 49 industries, or the 10 and 12.** §1, check (b).
- **The pre-1926 Cowles data.** Not a fresh sample: Szakmary and Zhou (2015) used them for this question (agenda, check (a)).
- **Volatility-managed factors and dynamic momentum.** Ruled out by power first on the French US history (agenda, dated addition 13:2xZ).

## 5. What this note does not do

No industry file was downloaded or read for this study; no industry return, rank, formation return or position was computed on any window; no parameter was chosen on any data. Every figure is from `tools/power_industry.txt`, the same formula on the month counts in §2.3, or the source paper as quoted. Order of operations after this note: pre-registration and `trials.md` (three rows), reviewed for design by a separate session before commit, pushed before the data step; data step (one snapshot, hashes, manifest; dates and counts only, including the eligibility count of §1); signal and scoring code with tests; `APPROVED`; history run once; note; separate-session recomputation; forward record. Time labels are written from `git log`, not estimated.

Literature: [MG99] and [DM16] are in the agenda's register. The sources named in check (a) are known from abstracts or search summaries only and are not added to the register until read.
