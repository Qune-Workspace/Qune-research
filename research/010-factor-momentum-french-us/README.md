# Study 010 — Time-series factor momentum on four US equity factors (1927–2026)

**Verdict: not supported** (pre-registered row, §9.5; history run once on 2026-10-26 at 10:19:49Z). **Read the disclosure first:** the author knew before choosing this question that the source paper reports a positive result on 1964–2015, and knew the general history of these factors (momentum's crashes in 1932 and 2009, value's long drawdown to 2020, size weak after the early 1980s, short-term reversal reported to weaken), but had not seen any factor's 12-month signs over 1928–1963 or 2016–2026 (§2.4 of the pre-registration). The sample and the question were chosen after ten earlier studies on other questions; only N = 3, this study's own three trials, decides the deflated Sharpe criterion.

*Dated addition, 2026-10-26, after the separate-session recomputation (should-fix 1; the paragraph above is unchanged):* the disclosure above omits two items of §2.4, given here in full: the author also knew of the 1929–32 market fall, and **no episode was used to choose anything** (the two episodes reported below were listed in the pre-registration before any result).

The rule holds each of four factors from the Kenneth French Data Library (size SMB, value HML, short-term reversal ST_Rev, long-term reversal LT_Rev) long after its return over the previous twelve months was positive and short after it was negative, equal weight, rebalanced monthly (Ehsani and Linnainmaa, NBER WP 25551, 2019). The decision difference d is the rule's return minus B3, the same factors held throughout at the rule's own average position. Costs are charged on every change of sign: 10 bp per unit traded in the base case, 50 bp under stress; the factors' own rebalancing costs are not charged, which flatters every figure on this page.

**What it does and does not show.** The timing earns a clear premium over its own average position: d is **+2.57% a year, Newey–West t 3.78**, over 1,190 months. But the rule does not beat simply holding the four factors long: **−0.36% a year against B1 (t −0.43), Sharpe 0.575 against 0.554**. Both are true because the rule's average positions are small (h̄ from 0.06 for SMB to 0.51 for ST_Rev), so B3 is a low-volatility portfolio (1.96% a year) with a high Sharpe ratio (0.697), while the rule takes full ±1 positions (6.84% a year). The timing gains about as much as it gives up by not holding the factors' premia steadily. The edge also sits in the past: by decade, d is positive from the 1920s to the 1990s and **−0.87% a year in the 2000s, −0.22% in the 2010s and +0.49% in 2020–2026** (descriptive); the 128 months after the paper's data (2016-01 to 2026-08) give **+0.36% a year, t 0.18**, a row that can only see a very large edge. At 50 bp stress costs d falls to +0.74% a year (t 1.03).

Everything on this page is a backtest on the library's factor returns (release 202608), after the timing costs above. Nothing here is a track record, a forecast or investment advice. The question, the trials, the benchmarks, the criteria and the order of operations were fixed in [`PREREGISTRATION.md`](PREREGISTRATION.md) before any library file was downloaded (`d9648af`); the trial log is [`trials.md`](trials.md).

What happened, in order (commit times read back from git, UTC; London is UTC on this date):

1. 07:25: question note (`e699ac3`), with power stated from month counts only ([`tools/power_study010.txt`](../../tools/power_study010.txt)).
2. 08:22: pre-registration and trial log, design-reviewed in a separate session before the commit ([DESIGN_REVIEW.md](DESIGN_REVIEW.md); 4 must-fix, 8 should-fix, all fixed first).
3. 09:17–09:18: data step logged before it ran (`cb8866c`), one download, **pass** (`a2e97b3`): H = 1927-07 to 2026-08, 1,190 months, no gap, no missing-value marker; only dates and markers read.
4. 09:21–09:40: code and 27 tests on synthetic series (`e98c874`, `1839e5a`); a separate code review failed it on one must-fix (a companion row's label depended on T1's verdict), fixed (`55aa9e3`) and re-checked (pass); `APPROVED` (`2f29086`) ([CODE_REVIEW.md](CODE_REVIEW.md)).
5. 10:17: programme-wide re-count (31 registered rows in the public trial logs, 595 with the desk's private registry, no weight) and the history-run row, pushed before the run (`eef348e`).
6. **The history run, once** (10:19:49Z), outputs committed as written (`1748602`); outcome row (`d9ac7da`).
7. This note.

## Results: the decision row H, 1927-07 to 2026-08 (1,190 months, base costs)

| Trial | Sharpe T | Sharpe B1 | Sharpe B3 | mean d (% a year) | NW t of d | T − B1 (% a year) | DSR N = 3 | C1 | C2 | C3 | C4 | Row |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **T1** four factors, 12 months | 0.575 | 0.554 | 0.697 | **+2.57** | **3.78** | −0.36 | 1.000 | fail | pass | pass | pass | **not supported** |
| T1a SMB and HML only | 0.330 | 0.355 | 0.361 | +2.48 | 2.82 | −0.10 | 0.984 | fail | pass | pass | pass | not supported |
| T1b four factors, 6 months | 0.249 | 0.551 | 0.699 | +0.59 | 0.84 | −2.60 | 0.895 | fail | fail | fail | fail | not supported |

C1 asks for a Sharpe ratio 0.10 above both B1 and B3. T1 misses it on both legs; the bootstrap test of the Sharpe difference gives +0.02 against B1 (p 0.87) and −0.12 against B3 (p 0.31). The verdict follows from C1 alone, before the window row or the companions are read. The deflated Sharpe ratio at the programme-wide counts, with no weight: 0.9999 at N = 10, 0.9989 at 31, 0.9403 at 595 (the desk's private registry, which a reader cannot check). T1's costs: 0.46% a year at base (4.50 sign changes a year across the four factors), 2.28% under stress.

**Window row (T1, §9.5):** over P, the 560 months outside the paper's data window (1927-07 to 1963-06 and 2016-01 to 2026-08), mean d is +3.18% a year (t 2.76): **pass**. It would have mattered only if C1–C4 had held.

### Sub-windows (descriptive, no decision weight; mean d in % a year, NW t)

| Window | Months | T1 | T1a | T1b |
|---|---|---|---|---|
| P1, 1927-07 to 1963-06 (before the paper's data) | 432 | +4.01 (2.97) | +3.30 (1.91) | −0.53 (−0.36) |
| L, 1963-07 to 2015-12 (the paper's data window) | 630 | +2.03 (2.64) | +2.31 (2.25) | +1.19 (1.55) |
| P2, 2016-01 to 2026-08 (after it) | 128 | +0.36 (0.18) | +0.57 (0.22) | +1.43 (0.76) |

P2 can detect only a Sharpe of d of about 0.87–0.96 at 80% power (§8), about 2.4 to 2.6 times T1's full-history 0.37; its flat figure is a weak test, not a refutation.

**T1's d by decade:** 1927–29 +10.56 (t 1.92, 30 months); 1930s +5.34 (1.36); 1940s +4.95 (2.46); 1950s +1.09 (0.98); 1960s +2.80 (2.38); 1970s +5.13 (3.30); 1980s +1.55 (1.05); 1990s +2.76 (1.37); 2000s −0.87 (−0.44); 2010s −0.22 (−0.15); 2020-01 to 2026-08 +0.49 (0.18, 80 months).

**Per factor (T1, base):** contribution to mean d after costs SMB +0.69% a year (t 2.41), HML +0.61 (1.95), ST_Rev +0.37 (1.24), LT_Rev +0.91 (2.96); before costs +0.81, +0.72, +0.49, +1.01. Average position h̄ 0.059, 0.224, 0.511, 0.120; 103 to 123 sign changes each over the 99 years; hit rate 53–57% (pooled 55.3%). The static exposure left in d by the varying factor count is at most 0.0035 in absolute value.

**Episodes registered before the run (§9.6):** 1929-09 to 1932-12, d summed to +11.0% (40 months); 2008-09 to 2009-12, −5.9% (16 months). The twelve worst months of d range from −13.8% (1939-09) to −5.4% (2022-07); five fall in 2000–2001 and 2008, three in 2020–2023.

**The paper's comparison (descriptive; a different factor set and construction):** the paper reports 4.2% a year (t 7.04) for time-series factor momentum on up to 20 factors and 4.21% (t 7.60) for holding them equally weighted over 1964-07 to 2015-12. On the same 618 months, T1 earns 3.57% a year before costs (t 4.56) and 3.08% after base costs (t 3.88), against 3.97% (t 4.40) for holding the four factors long. The paper's own pattern, the timed portfolio close to the held one, is reproduced; the timing does not add to holding.

### Power, after the fact (§9.6)

T1: sd(d) 6.94% a year, Newey–West to iid standard-error ratio 0.975; minimum detectable mean of d 1.36% a year at t = 2 and **1.93% a year at 80% power** (Sharpe of d 0.20 and 0.28). The 2%-a-year bar of `QUESTION.md` §2.3 is met, so no "Sharpe units" label applies.

## What did not work

- **The headline rule did not beat holding the factors.** Its significant d is real in this sample but is a gain over a benchmark that holds small positions; against holding all four factors long, the rule is flat (−0.36% a year) and its Sharpe ratio is not distinguishable (+0.02, p 0.87).
- **The edge does not reach the recent decades.** 2000–2026 is negative or flat in each decade, and the post-paper row is +0.36% a year (t 0.18).
- **Costs bite.** At 50 bp per unit traded, d falls from +2.57% to +0.74% a year (t 1.03), and T1 trails B1 by 2.18% a year (t −2.54). Rebalancing costs inside each factor are not charged at all.
- **The six-month formation (T1b) fails everything**: d +0.59% a year (t 0.84), and −2.33% a year under stress.
- The pre-registration's C1 compares Sharpe ratios with a benchmark of very different volatility (B3 1.96% a year against T1's 6.84%). That was fixed before the data and is applied as written; it is noted here because it makes C1 hard for any rule whose average position is small.

## Separate-session recomputation (§14 step 8)

In progress at the time of this note; its result is added below as a dated section, with REVIEW.md.

*Dated addition, 2026-10-26 10:4x GMT.* **Confirmed with findings, no must-fix** ([REVIEW.md](REVIEW.md); separate Opus 5.5 session that did not write the study, same model family, same machine). From the raw zips (hashes match the manifest) with its own numpy/pandas/scipy, importing nothing from `src/`: every position, cost, T, B1, B3 and d of the three trials at both costs matches the monthly CSVs exactly; every figure in `summary.json` recomputes, bootstrap and Ledoit–Wolf included; all 48 numbers typed in `trials.md` and 129 of the 130 in this note match; the commit chain is in order and the data-step and history-run rows were pushed before their runs. Tests: 31 study, 134 library, all pass. `review_recompute.py` prints 1,393 rows: 1,387 match, 2 mismatch, 4 informational; both mismatches are in this note and are answered here, nothing above is rewritten:

- **Mismatch 1 (note 4):** "about 2.4 to 2.6 times T1's full-history 0.37" should read **2.3 to 2.6** (0.870 / 0.370 = 2.35).
- **Mismatch 2 (should-fix 1):** the §2.4 items missing from the first paragraph; answered by the dated addition under it.
- **Should-fix 2 (§10 row 6):** before 1962 the library's universe is NYSE stocks only (AMEX joins CRSP in 1962; general knowledge, not read from the library), so P1's factors are built from fewer, larger firms, and trading costs then were higher than the 10 bp charged here. The files' own headers describe the universe as NYSE, AMEX and NASDAQ ([data step](results/data_step.md)).
- **Should-fix 3 (§9.1, §10 row 7):** B3's average positions h̄ are taken from the whole of H, a look-ahead in the benchmark only; every sub-window row (P1, L, P2, P and the decades) uses the same full-H h̄.
- **Notes:** no formation return was a tie (|R| ≤ 1e-12, in any factor, trial or cost case), so the tie rule (ties take −1) never acted; formation runs from t − 12 to t − 1 with no skipped month, which is this study's reading of the paper (§6), not a quoted rule; the raw zips are git-ignored and the library is rebuilt monthly, so a reader cannot download this snapshot again (the manifest's hashes identify it); the DSR at N = 10, 31 and 595 reuses the variance of Sharpe ratios across the three trials (the programme's convention; no weight); `summary.json` records no commit hash, so "code `eef348e`" is read from the commit order (the run's code is the HEAD the run started from; nothing in `src/` changed after `55aa9e3`).
- **Not checked by the reviewer:** the 564 private desk rows behind the 595 count; whether the zips are byte-for-byte what the library served (no network).

## Next

1. The separate-session recomputation of every figure on this page.
2. Charts to the house standard, through the Tester chart check (§9.6).
3. The forward record code (`forward010.py`, shadow only; §11), before the first forward month is due. Over 60 months it can see only a Sharpe of d of about 1.27, so its verdict will be worded as a low-power check.
