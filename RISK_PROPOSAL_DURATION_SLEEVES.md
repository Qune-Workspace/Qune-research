# Proposal: a risk specification for monthly ETF duration sleeves

**Status: proposal only, 2026-10-26. Nothing in [RISK_FRAMEWORK.md](RISK_FRAMEWORK.md) changes because of this file.** Changing the desk's limits is the owner's decision, and any change would go through Independent Risk first. Written in answer to the [second cold read](COLD_READ.md#second-cold-read-2026-10-26), point 8: the paper limits were written for hourly crypto and equity trading, so a monthly bond rule cannot be paper-traded under them as it was tested.

## The mismatch (observed in the files)

| Current limit ([RISK_FRAMEWORK.md](RISK_FRAMEWORK.md)) | What the monthly duration studies tested | Effect if traded today |
|---|---|---|
| Risk per trade = loss from entry to the stop; **orders without a stop are refused** | No intra-month stop in any backtest (Study 003 PREREGISTRATION §6, "no intra-month stops in the backtest"; Studies 006–008 hold for the month) | The paper sleeve would have to trade a rule with a stop that was never tested, and no code watches a stop after entry ([Study 003 RISK_CLEARANCE.md](research/003-bond-tsmom-ief/RISK_CLEARANCE.md)) |
| Signal-bar age at most 2 hours | Month-end signals from daily data | Every daily-bar entry is refused (known gap; the owner's item B) |
| At most 2 open positions | A sleeve is a pair (IEF and BIL, or a fraction of each) | One sleeve can use the whole position budget |
| No duration or DV01 limit | Interest-rate risk is the only risk these sleeves take | The limit that matters most is missing |

## Proposed specification (for monthly, long-only, unlevered ETF duration sleeves only)

1. **Size by interest-rate risk, not by a stop.** Each sleeve's DV01 (the dollar change for a 1 bp move in yields) is capped. The cap is chosen so that a 99th-percentile monthly move in the 10-year yield costs no more than the desk's existing risk-per-trade limit of $250.
2. **No stop.** Exits happen only at the monthly decision, as in the backtest. A stop is allowed only if the same stop was in the registered backtest. In place of a stop, a sleeve whose month-to-date loss passes its DV01 cap times the 1969–2018 99th-percentile move triggers a review and an owner notice, not a trade.
3. **Daily-bar age rule for these sleeves:** the signal is valid if it was computed from the last completed session's close and the order is placed before the end of the execution day (the owner's item B, which this file does not decide).
4. **A sleeve counts as one position**, IEF and BIL together. BIL counts towards gross exposure at full notional (conservative), but carries no DV01.
5. **Unchanged:** the account-level limits (cash basis, no margin, gross exposure $10,000, daily loss $500, drawdown halt 1.5%), journal-before-order, the price collar, spread and quote-age checks, and the per-order notional cap.

## The numbers behind item 1 (computed 2026-10-26 from the FRED DGS10 file already on disk for Study 006; no rule return involved)

Monthly change in the 10-year yield, month-end to month-end:

| Window | Months | Standard deviation | 99th percentile of the absolute change | Largest |
|---|---|---|---|---|
| 1969-08 to 2018-12 | 593 | 34.6 bp | 109.3 bp | 188.0 bp |
| 2003-08 to 2018-12 (the ETF era in-sample) | 185 | 24.0 bp | 67.2 bp | 108.0 bp |

Duration: an 8.5-year par bond (the synthetic leg Studies 006–008 used for IEF) at the 10-year yield on the latest desk view (5.13%) has a modified duration of about 6.8 years, so each $1,000 held has a DV01 of about $0.68. IEF's own published duration should replace this figure at implementation.

| | DV01 | Loss at the 1969–2018 99th percentile (109 bp) | Loss at the largest move (188 bp) |
|---|---|---|---|
| Today's proposed Study 003 sleeve, $2,250 in IEF | about $1.53 per bp | about $167 | about $288 |
| **Proposed cap: $2.25 per bp per sleeve** (about $3,300 of IEF) | $2.25 | about $246 | about $423 |
| Proposed aggregate cap across all duration sleeves: $5 per bp | $5 | about $547 | about $940 |

The aggregate cap keeps the loss from the largest monthly move of 1969–2018 inside the 1.5% drawdown halt ($1,500 on the $100,000 account). The 1969–2018 figures are used rather than the calmer ETF-era ones, because the calm window understates rate risk (the 2022 sell-off is outside both windows and is not used here).

## What this proposal does not do

- It does not clear any sleeve. Study 003's sleeve stays NOT CLEARED until the owner decides item B and Independent Risk re-reviews.
- It does not make any rule worth trading. The only sleeve proposed (Study 003) is a "not supported" rule; trading it would test the order path, not a strategy. Studies 004–008 stay shadow records.
- The numbers in item 1 are illustrations of how the cap would be set. The owner sets the values.

## Owner decisions this would need

1. Adopt DV01 caps for duration sleeves in place of stop-based risk per trade (values above, or others).
2. Allow no-stop orders for registered monthly sleeves whose backtest had no stop.
3. Item B (the daily-bar age rule), already open.
4. Count a sleeve as one position.
