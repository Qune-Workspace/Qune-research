# Risk framework

The desk's limits are set before the first test, reviewed by someone who did not write them, enforced in code, and loosened only by the owner.

This document states the rules the trading desk works under, the current numeric paper limits, the backtesting standards a result must meet, and the conditions under which trading stops. The numbers are current paper limits on a $100,000 paper account; they are not advice and they are not calibrated for anyone else's capital.

*Written 2026-10-21. Updated 2026-10-23 in three places, each marked with its date: the approved-instrument row (IEF and BIL are approved for two study sleeves), the table of reviewed restrictions (five of the seven have been enforced in the engine since 2026-10-11; two are still applied by the runner), and the known gaps (the 2-hour signal-bar age gate and the Study 003 sleeve's clearance status). No limit was loosened.*

## Mandate

1. **Paper only.** There is no route from the paper account to real money. The broker client refuses any host other than the paper and data endpoints. No task may propose, design or prepare a live route.
2. **No margin, no shorting, no leverage.** Gross exposure after any order must not exceed settled cash, never the broker's margin buying power, and the tighter limits below apply beneath that.
3. **Systematic only.** Every strategy is a written set of rules: universe, entry, exit, position size, and the conditions under which it is switched off. The backtest and the paper runner call the same strategy module. There are no discretionary orders; an order that cites no written, backtested strategy is refused by the risk engine.
4. **Benchmarks and limits before any test.** Buy-and-hold of each traded asset, an equal-weight portfolio where there is more than one, and cash, are fixed and dated before the first test. Every result is reported against them after costs, with maximum drawdown and a risk-adjusted return. Underperforming the benchmark is a valid finding and is reported as such.
5. **Independent review.** The desk proposes limits; Independent Risk reviews them. Every strategy that passes its pre-declared bar goes to Independent Risk before it can trade. The reviewer never wrote the thing reviewed.
6. **Loosening needs the owner; tightening does not.** Any role may tighten a limit through a risk task. A looser value is a written proposal with backtest evidence and Independent Risk's opinion, decided by the owner. The limits file and the risk engine are protected: a research task cannot write to them, and an attempted change is restored and held for approval.

## Current paper limits

Interim values were set on 2026-10-10 and reviewed by Independent Risk the same day; the only change on review was the drawdown halt, tightened from 2% to 1.5%. Nothing has been loosened since.

| Limit | Current paper value | Note |
|---|---|---|
| Account | $100,000 paper, cash basis | Exposure is capped by settled cash, never by buying power |
| Margin, shorting, leverage | Not allowed | Enforced in code; the broker's paper account would allow them, so the refusal is ours |
| Approved instruments | BTC/USD, ETH/USD (spot); SPY, QQQ, IWM, DIA; IEF, BIL (study sleeves only) | Any other symbol needs a recorded approval. *Updated 2026-10-23:* IEF and BIL were approved by the owner on 2026-10-21 for the Study 001 sleeve and the scope was extended in writing on 2026-10-23 to the Study 003 paper sleeve (at most $2,250, same limits, no numeric change), each inside the limits above and each still needing Independent Risk's clearance before the first paper order ([RISK_CLEARANCE.md](research/003-bond-tsmom-ief/RISK_CLEARANCE.md)). Currency ETFs are not approved. |
| Maximum risk per trade | $250 (0.25% of equity) | Loss from entry to the strategy's stop, including estimated fees and half-spread. Orders without a stop are refused. |
| Maximum notional per order | $2,500 | |
| Maximum position per asset | $5,000 | |
| Maximum concentration in one asset | 5% of equity | BTC and ETH count as one bucket against gross exposure because they are highly correlated |
| Maximum gross exposure | $10,000 (10% of equity) | |
| Maximum open positions | 2 | |
| Maximum orders per night | 6 | A cap against runaway loops |
| Daily loss limit | $500 (0.5% of equity) | Realised plus unrealised since 00:00 UTC. On breach, new entries stop until the next UTC day; exits stay allowed. |
| Drawdown halt | 1.5% from the recorded high-water mark | On breach the engine writes the kill switch; all new entries halt until the orchestrator reviews and the owner is told |
| Order types | Market, limit | Time in force: good-till-cancelled, immediate-or-cancel |
| Journal entry before order | Required | The order's identifier must match a journal entry written before it |
| Written strategy and recorded backtest | Required | The entry must cite a strategy identifier with a specification and a backtest |
| Exit plan with time limit | Required | |

Reviewed restrictions added after the limits above. *Updated 2026-10-23:* when this document was written the table said none of them was enforced in code; in fact the first five have been checked by the risk engine's market-data gates since 2026-10-11 (an order that fails one is refused and the reasons go into the run's decision record as a no-trade decision), and the last two are still applied by the runner, not the engine.

| Restriction | Value | Where it is enforced |
|---|---|---|
| Price collar | Reject if the limit price is more than 1% from mid | engine, since 2026-10-11 |
| Maximum quoted spread | 25 basis points | engine, since 2026-10-11 |
| Maximum quote age | 5 minutes | engine, since 2026-10-11 |
| Maximum signal-bar age | 2 hours | engine, since 2026-10-11 (see the known gaps: written for hourly bars, it refuses every daily-bar entry) |
| Duplicate-order window | 60 seconds | engine, since 2026-10-11 |
| Order size against hourly volume | Warn at 1x, reject at 10x | runner only (designed, not tested) |
| Consecutive-loss switch-off | 5 losses | runner only (designed, not tested) |

These are new restrictions, so adding them is a tightening and needs no approval. Relaxing any of them, including making the signal-bar age depend on the bar's timeframe, is a loosening and follows the section "What loosening requires".

## Backtesting standards

A result is accepted only if the following were in place before the run.

- **Pre-declaration in its own commit.** Rules, parameters, split, costs, benchmarks, pass bar and trial count are committed before the backtest, so the history shows they existed first. The trial-registry row records the hash of the declaration file, and the run verifies it before starting.
- **Trials logged before they run.** Every variant (parameter set, symbol set, timeframe) is a row in an append-only, hash-chained registry. A corrected row is a new row and still counts. A family groups variants of one idea and sets the trial count for deflation. A rule kept for further study after failing once carries its earlier trials with it. (2026-10-24: the hash-chained registry is the trading desk's internal one and is not published. The five studies in this repository log their trials in each study's `trials.md`, a plain table whose chain is the git history; the commit order is the public proof and each `REVIEW.md` checked it. See the dated precision under "Research lifecycle" in `ARCHITECTURE.md`.)
- **Trial count and deflated Sharpe with every result.** A Sharpe ratio without a trial count is not a result. The deflated Sharpe is reported at the family count and, as a sensitivity, at the full registry count. When fewer than two in-sample Sharpes are logged the cross-trial variance falls back to the null, which makes the deflated figure optimistic; the report says so.
- **Pass bar.** A positive verdict needs, on the portfolio at base cost: Sharpe above the benchmark over the same dates, maximum drawdown below the benchmark, deflated Sharpe at or above 0.95, positive net return at the raised cost level, and a minimum number of closed trades (30, or a declared lower number with the reason) on at least 15 distinct entry days. A lower drawdown with a lower Sharpe is reported as a risk-reduction finding, not a pass.
- **Look-ahead.** A signal computed at the close of day t fills at the close or open of t+1 or later. A shifting test checks that past signals do not change when later data is added.
- **Held-back out-of-sample period.** The split is chronological and fixed before any tuning. The out-of-sample window is touched once per strategy version. If it is used to choose anything, it is burned and the report says so. Where no parameter is chosen in-sample, both halves are reported unchanged and the second half measures stability, not fit.
- **Costs.** Reported at zero, base and raised cost. For liquid ETFs the base is 2 basis points per side (half-spread plus slippage, no commission) with 0 and 5 basis points shown. For crypto spot the base was the broker's taker fee plus 5 basis points of slippage plus half the quoted spread, with a +50% sensitivity. Paper fills are an assumption, not measured fill costs, and are labelled as such. A rule that loses at zero cost is dead before costs are discussed.
- **Independent bets, not trades.** Trade counts are reported next to distinct entry days. Correlated instruments are counted as fewer bets than their number.
- **Cash rate.** Idle cash earns 0% by default; verdicts are also checked against a historical T-bill rate, and a verdict that flips with the cash rate is reported as unstable.
- **Robustness.** Results by sub-period; a bootstrap interval for the mean return; where a parameter is chosen, its neighbourhood must also work.
- **Reproducibility.** Each result records the data hashes, the code version, the parameters and the seed. A re-run gives the same numbers. The run stops if a data hash differs from the declaration.
- **Verdict wording.** "No edge shown", "insufficient evidence", "not replicated" and "underperforms buy-and-hold" are valid verdicts and are written plainly. The original run's numbers are the headline; a re-grade or a widened bar is reported beneath them.

## Paper trading forward

- Paper trading begins on the publication date of the cleared rule and is never backdated.
- Orders exist only when the no-model runner executes a strategy that Independent Risk has cleared. Uncleared strategies record a no-trade decision. Nobody places an order by hand.
- The journal is written by code before the order, and the exit record requires fills, the exit reason, slippage against the backtest assumption, an attribution into market move, rule timing and costs, and one lesson.
- Reconciliation joins the journal to broker orders, fills and positions and flags any mismatch, untracked position or unjournalled order.
- A flat book that "beats" buy-and-hold over a short window has mostly avoided costs; reviews decompose any benchmark gap and report a gap smaller than one round-trip cost as no information.

## Stop conditions

Any of these stops new entries. Exits remain allowed in every case.

| Trigger | Effect | Reset |
|---|---|---|
| Kill switch | No new entries | Removed only after the orchestrator's review |
| Drawdown halt (1.5% from high-water mark) | Engine writes the kill switch | Orchestrator reviews; owner is told |
| Daily loss limit ($500) | No new entries until the next UTC day | Automatic at 00:00 UTC |
| Strategy switch-off rule (for example 5 consecutive losses) | That strategy stops for its declared period | Per the strategy's specification |
| Stale quote or stale signal bar | Order refused | Fresh data |
| Missing journal entry, stop, exit plan or strategy reference | Order refused | Fix the entry |
| Unapproved symbol | Order refused | Recorded approval |
| Reconciliation mismatch or account not flat when it should be | Flagged; reviewed before the next cycle | Review |
| Organisation-level pause (change guard or usage guard) | Research lanes pause; nothing is loosened | Guard clears |

## What loosening requires

A proposal in writing with the backtest evidence that motivates it, Independent Risk's written opinion, and the owner's decision. The orchestrator and the desk cannot grant it. The limits file records who set each value, who reviewed it and when, so a loosened value is visible in the history with its approval.

## Known gaps

- Two reviewed restrictions (order size against hourly volume, consecutive-loss switch-off) are applied by the runner, not the engine (table above).
- *Added 2026-10-23:* the engine's 2-hour signal-bar age gate was written for hourly crypto bars and refuses every entry whose signal comes from a daily bar, which is every entry of the Study 003 rule. A timeframe-aware rule is a loosening in form, so it is the owner's decision; Independent Risk's opinion that the rule is sound is on record, and the decision is pending. Until it is taken, the Study 003 paper sleeve is **not cleared** (Independent Risk, 2026-10-22: nine conditions, of which the sleeve size, the symbol scope and the built execution path are met or recorded and this one is open; [RISK_CLEARANCE.md](research/003-bond-tsmom-ief/RISK_CLEARANCE.md), [paper/README.md](research/003-bond-tsmom-ief/paper/README.md)). Its decision records are written regardless, labelled as the paper record of a not-supported rule, and no order is placed.
- The engine caps gross exposure but does not yet count correlated positions as one bet beyond the crypto bucket.
- The paper runner wakes on a schedule and has no resting broker stop, so a paper loss can exceed the backtested stop by the movement between wakes.
- Options work is observation and scoring only; options orders are not permitted.
