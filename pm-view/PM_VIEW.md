# Prediction-market view, 2026-11-03

First view. Written 2026-11-03 from 18:23 UTC on quotes read at 18:23:14–18:23:15 UTC ([`data/manifest.json`](data/manifest.json)); the rules are in [`README.md`](README.md). Labels: [O] observed in a quote or a public series on the date given, [I] the desk's reading, [R] reported by the source named. Nothing here is investment advice.

## What was read

The five Polymarket markets on the FOMC's 9 December 2026 decision, one negative-risk event (the five YES legs are the possible outcomes). Each market's YES is settled on the change in the upper bound of the target range after the meeting [R, the market's rules]. Mid and spread are from the best bid and ask of the YES token's order book at the fetch time; volume is cumulative USDC traded [O].

| Market (desk's words for YES) | id | mid | spread | volume, USDC | eligible for a call |
|---|---|---|---|---|---|
| Hike of 25 bp | 3215008 | 0.735 | 0.010 | 2,661,872 | yes |
| No change | 3215007 | 0.235 | 0.010 | 2,707,472 | yes |
| Hike of 50 bp or more | 3215009 | 0.0195 | 0.003 | 1,642,102 | yes |
| Cut of 25 bp | 3215006 | 0.0045 | 0.001 | 2,258,988 | no: mid below 0.01 |
| Cut of 50 bp or more | 3215005 | 0.0035 | 0.001 | 1,972,693 | no: mid below 0.01 |

The five mids sum to 0.9975 [O], so the event's book is coherent to within the spreads; any hike is priced at 0.755.

## The desk's reading, and why no call is logged

**What the bills say [O, I].** On 2026-10-30, the last bill print before this view, the 3-month constant-maturity bill was 3.99% against an effective funds rate of 3.88% ([FRED DTB3, EFFR](https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3)), an 11 bp spread. The on-the-run 13-week bill of that date matures on 2027-01-28 [I, from the weekly issue cycle], 90 days out, with the 9 December meeting 40 days inside its life and the 27–28 January meeting ending on its maturity day, so outside it. A full 25 bp hike on 9 December could lift the bill's average rate by at most 0.25 × 50/90 = 13.9 bp (`predictions/baseline.py::max_policy_spread`, the rule adopted after V1). The 4-week bill of the same date, which matures before the meeting and carries no decision, sat 3 bp over funds (3.91% against 3.88%, [FRED DTB4WK](https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB4WK)): the current bill-funds basis. Net of that basis the 3-month bill prices a December hike at (11 − 3) / 13.9 = **0.58**. The reading moves with the basis assumption alone from 0.79 (basis 0) to 0.22 (the 8 bp the 3-month bill carried in early 2026, [`../predictions/POST_MORTEMS.md`](../predictions/POST_MORTEMS.md)). That spread of readings, 0.57 wide, is the weak joint V1 broke on.

**What else the desk knows [R].** The September projections' median of 4.1% for end-2026 implies one more hike by December; the 28 October statement held the range at 3.75–4.00% by 10–2, both dissents for a hike, with "the accumulation of more information will help the Committee determine the policy stance appropriate" and no reference to policy lags ([`../desk-view/DESK_VIEW.md`](../desk-view/DESK_VIEW.md), 2026-10-30). Two monthly labour and inflation releases arrive before the meeting.

**The desk's probabilities [I].** Hike of 25 bp: **0.65**. No change: **0.33**. Hike of 50 bp or more: 0.01; cuts: 0.01 together. The 0.65 is below the market's 0.735 because the bills' central reading is 0.58 and the statement's "more information" wording is a wait, not a pause; it is not lower because the dots say hike and the two dissents say the Committee is close.

**No call.** The departures from the market are 0.085 on the 25 bp hike and 0.095 on no change, both under the 0.10 the rules require, and the bill reading's own range (0.22–0.79) is wider than either gap, so the bills are not a reason to say the market is wrong. Under rule 2 of the README the desk has nothing to add this week and logs nothing. The two longshot legs are inside the 013 calibration question (the favourite–longshot test on the whole programme), not a desk call.

What would make a call on this event: a bill-market reading whose range under the basis assumption lies wholly on one side of the market, which needs a bill maturing between 9 December and 28 January (the 8-week bill, not carried on FRED) or a divergence larger than the basis uncertainty after the November data; or a stated reason from the data releases themselves, written before the market moves on them.

## Calls and score

No call logged. [`ledger.csv`](ledger.csv) is empty; [`SKILL.md`](SKILL.md) reports 0 scored calls.

## Next

- Next view on or before Friday 2026-11-06, with the rates desk view: the same event after the week's data, and a second candidate: the monthly Bitcoin price-level markets ending 2026-12-01 (ids 6507378, 6507380; mids 0.695 and 0.765, spread 0.01, volume above 100,000 USDC [O, 2026-11-03 04:40Z snapshot]), where a barrier probability from realised volatility (the method of the rates view's V4) would be a stated, testable method. Blocker before any such call: a public price series the tree may use, with its terms read first (the same rule as every venue).
- The scoring run (`score.py`) runs on every learning-loop run once a call exists; the due register lists each call the day after its market's scheduled end.

*Dated addition, 2026-11-04 00:5xZ.* The Bitcoin markets above are **touch markets**, not price-level markets: 6507378 settles YES if any Binance BTC/USDT one-minute candle in the Eastern-time month has a High at or above 80,000, and 6507380 if any has a Low at or below 75,000 [Q, the markets' rules, read 2026-11-04 00:17Z]; both showed 0.735 at that read [O]. The method is therefore a first-passage probability from realised volatility, and the series question is settled in [`../tools/pm_data_terms.md`](../tools/pm_data_terms.md): Binance (the resolution source) and Coinbase's own API are `neither` until their terms can be read, so neither is called; the FRED series CBBTCUSD (Coinbase Bitcoin, daily) is `derived`: a volatility figure and a barrier probability may be published with the FRED citation, no observation of the series is committed, at most one dated level per view, and the view's basis sentence must say that daily Coinbase closes understate the chance of an intraday Binance touch. The weekly PM view is now in the due register (`PM view 2026-11-06`, 06:00Z, with the rates view).
