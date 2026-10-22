---
id: RISK-003-paper
date: 2026-10-22
author_role: "Independent Risk (did not write the study, the limits or the engine)"
labels: [observed, inferred, tested]
scope: paper only; Study 003 sleeve; IEF and BIL; no real money anywhere
---
# RISK-003-paper decision: Study 003 paper-trading sleeve

## Strategy: study003-tsmom-ief-bil v1 -> **NOT CLEARED** for paper trading today; re-evaluate against the numbered conditions below (paper only, sleeve at most 2 250 USD at first clearance, symbols IEF and BIL only, no real money anywhere).

This is a decision on the paper sleeve's gate, not on the research. The study's verdict is "not supported" (README first paragraph, observed) and §11 says the forward record proceeds as the paper record of a not-supported rule; nothing here contradicts that. The sleeve cannot be cleared today because (i) the engine, as written, refuses every entry the §11 schedule would send (bar-age gate), (ii) the symbol approval on record is scoped to Study 001, (iii) the pre-registered 4 500 USD single buy exceeds the per-order cap, and (iv) the execution path does not exist. None of these is a finding against the rule; all are checkable. First signal date 2026-10-30, first execution 2026-11-02, starting position BIL (README "Paper trading", observed): a re-clearance before 2026-10-30 is feasible if conditions 1 to 4 are met, and conditions 5 to 9 are met before the first order.

Evidence labels: observed = read in the named file; inferred = reasoned from the code or arithmetic; tested = run in this session with the quoted command.

## Standard | Finding | Verdict

| Standard | Finding | Verdict |
|---|---|---|
| §12.1 instruments IEF and BIL only | Both are in `allowed_symbols.us_equity` of risk.json (observed). The approval record `study001_symbols_approved` reads "Research Study 001 (term-spread duration switch) only; $4,500 sleeve inside existing limits" (observed). The engine checks the symbol list, not the scope note (inferred from `risk.mjs` lines 137–138), so the engine would accept; the written approval would not. Study 001 is halted and never traded. | **fail: recorded scope extension needed (condition 2)** |
| §12.2 sleeve 4 500 USD, never more than 5 000 USD in one position | Per-position cap 5 000 USD and concentration 5% of equity (5 000 USD at 100 000 USD equity) are met by 4 500 USD, with 500 USD headroom (inferred). But `max_notional_per_order_usd` is 2 500 USD and a 4 500 USD buy is a single entry: engine rejection reproduced (tested, below). A sell is an exit and is not notional-capped (inferred, `risk.mjs` line 197 is inside the entry branch). | **conflict: 4 500 > 2 500 per order; resolved by condition 1** |
| §12.2 gross exposure ≤ 100% of sleeve; no margin | Engine caps gross at min(cash, 10 000 USD) and refuses notional > cash (observed). The 10 000 USD gross cap and the 2 open-position cap are shared with every other desk strategy on the same paper account (inferred). | pass, with condition 6 |
| §12.3 100% in one Treasury ETF | Concentration check is per asset, 5% of equity; a 4 500 USD or 2 250 USD position passes at any equity above 90 000 USD / 45 000 USD (inferred). | pass |
| §12.4 20% drawdown halt | Sleeve halt in dollars: 900 USD on 4 500 USD; 450 USD on 2 250 USD. Account halt: 1.5% of the 100 000 USD high-water mark = 1 500 USD (state file observed, mark 100 000). The sleeve's halt bites first in dollars; the account halt can still be tripped by other strategies and then blocks the sleeve's buy leg (kill switch; exits stay allowed). Sleeve halt is not enforced by the engine; it needs the study's own monitor. | tighter than desk; enforcement is the study's (condition 8) |
| §12.5 3% one-day loss review | 135 USD on 4 500 USD; 67.50 USD on 2 250 USD; desk daily limit 500 USD. Sleeve rule bites first. Desk rule stops entries only; the sleeve rule is a written review, no trade (observed). | tighter than desk; study-side |
| §12.6 one switch per month; §11.3 one sell and one buy | `max_orders_per_night` 6 is not binding (2 orders, or 3 if the buy were split). The duplicate-order window (60 s, same symbol and side) is enforced in code (observed, `marketGates`), so a split buy would need more than 60 s between legs. Condition 1 keeps the buy to one order. | pass |
| §12.7 order notional within ±2% of target | Not enforced by the engine; runner-side. With whole shares (§6.2) and IEF near 95 USD, one share is about 2.1% of 4 500 USD and 4.2% of 2 250 USD, so the target must be defined as the whole-share quantity times the expected price, or the rule is unmeetable (inferred). The desk runner sends notional (fractional) orders, which contradicts whole shares (observed, `run-strategy-core.mjs` line 139). | partial; condition 5 |
| §12.8 orders only 15:30–16:00 ET; no order if last log record missing | Neither enforced by the engine; the desk runner is hourly and has no time-of-day window (observed, `desk-start` line 39). | not enforceable today; condition 5 |
| Stop requirement (risk.json: orders without a stop refused) | Risk as the engine computes it: qty × (entry − stop) + 2 × 0.25% × notional (crypto taker fee rate, overstates ETF fees) + qty × half-spread. IEF entry 95.01, half-spread 0.01: 4 500 USD at a 5% stop = 247.97 USD (passes by 2 USD; 5.05% is the limit); 2 500 USD at 5% = 137.76 USD; 2 250 USD at 5% = 123.99 USD; at 2 500 USD the widest stop is just under 9.5% (9.5% rejected at 250.37 USD). BIL: any stop below entry with the same arithmetic is accepted, for example 1% below (tested). No code monitors the stop after entry (RISK_FRAMEWORK "Known gaps", observed). | pass at ≤ 2 500 USD; marginal at 4 500 USD |
| Max open positions 2 | Mid-switch: after the BIL sell fills, the IEF buy opens position 1 of 2. If other desk strategies hold two positions, the buy is refused after the sell has gone, stranding the sleeve in USD cash rather than BIL (inferred, `risk.mjs` lines 215–216). | pass only with condition 6 |
| Bar age ≤ 2 h, quote age ≤ 5 min, spread ≤ 25 bp, collar 1% | risk.json says no code reads `pending_enforcement`; that is stale: `marketGates` enforces collar, spread, quote age, bar age and the duplicate window on every entry (observed). The signal bar for a monthly rule is the daily bar of date t; at 15:50 ET on the next NYSE day it is 23 h old on an ordinary day and 78 h over the first weekend: rejected (tested). The volume ratios and 5-loss switch-off are the only unenforced items. | **fail: every IEF and BIL entry is refused as written (condition 3)** |
| §11.4 data failure and price sanity | Study: missing month-end bar → re-check 3 days, then hold and alert; fill more than 0.5% from last mid → next order held for review. Engine: collar applies to limit orders only; market orders are unpriced against mid (observed). The study's 0.5% is tighter but post-fill and runner-side. | study-side; condition 5 |
| Verdict line read by the runner | The runner reads only `runs/RISK-02/decision.md` (observed, `run-strategy` line 43) and treats any verdict starting with "CLEARED" as cleared, including "CLEARED WITH CONDITIONS" (observed, regex `/^CLEARED\b/`). This file is not read by any code. | informational; conditional wording is unsafe in that file |
| Desk pass bar (RISK_FRAMEWORK) | The desk bar needs 30 closed trades on 15 entry days and Sharpe above benchmark; the study has 18 in-sample and 10 out-of-sample switches and fails C1 and C2. The desk's own route for a rule below its bar is forward-test mode, which needs `forward_test.enabled` in risk.json (absent, observed) and an owner decision. | not met; see condition 4 |
| Runner integration | Needs a strategy module exporting ID, VERSION, signal and size in the hourly-bar interface, a spec and `<id>-backtest.json` under `ops/trading/strategies/`, a baseline (exists, but records crypto prices only), a journal entry per order, and equity quotes and bars from the ops client (none: `alpaca.mjs` has crypto quote and bar functions only; `buildState` fetches crypto quotes only, so an IEF market order "cannot be priced"). The runner places buys only; sells are "TRD-06", not built. | **fail: nothing exists yet (condition 5)** |

### Tested in this session

Command (no network, no credentials; default engine, equity equal to the high-water mark so no state file changed; verified afterwards that `state/high-water-mark.json` was unchanged and no `KILL` file appeared):

```
cd <agent workspace root, the directory containing ops/> && node -e 'import("./ops/trading/lib/risk.mjs").then(({preTradeCheck}) => { ... preTradeCheck(order, state) ... })'
```

with `state.now` 2026-11-02T20:50Z, hosts paper and data only, equity and cash 100 000, no positions, IEF quote 94.99/95.01 and BIL 91.49/91.51 timestamped 30 s earlier, `signal_bar_time` 2026-10-30T13:30Z. Results:

| Hypothetical order | Rejections (besides the expected "no journal entry" and "no written spec") |
|---|---|
| buy IEF 4 500 USD, stop 5% below | notional 4 500 exceeds 2 500; signal bar age 78.33 h exceeds 2 h |
| buy IEF 2 500 USD, stop 5% | bar age only |
| buy IEF 2 500 USD, stop 9.5% | risk to stop 250.37 exceeds 250; bar age |
| buy IEF 2 500 USD, no stop | "orders without a stop are refused"; bar age |
| buy BIL 2 500 USD, stop 1% | bar age only |
| buy BIL 2 500 USD, bar 1 h old | journal and spec only |

## Conditions before the first order (each checkable by a third party)

1. **Sleeve tightened to 2 250 USD** (a tightening; no owner needed), recorded as a dated §16 amendment with the reason: one buy fits under the 2 500 USD per-order cap with 11% headroom for drift, the 5% IEF stop risks 124 USD against 250, and §11.3's one sell and one buy per month stays intact. Rejected alternatives: splitting the buy (breaks §11.3 and depends on the 60 s duplicate window); raising `max_notional_per_order_usd` (a loosening; owner only; not recommended for a not-supported rule). RISK-02's "minimum size, about 250 USD" is not applied: at 250 USD one IEF share is 38% of the sleeve, so whole-share rounding would swamp the slippage and ±2% records that are the point of the forward test. Check: amendment present; `paper-log/` config states 2 250.
2. **Symbol scope extended in writing** to Study 003 (same symbols, same sleeve rule, same limits), by the owner or by the orchestrator citing the owner's delegation of 2026-10-21, recorded in risk.json beside `study001_symbols_approved` through a risk task (research tasks cannot write that file). This is not a loosening of any numeric limit. Check: risk.json names Study 003; the git history shows who wrote it.
3. **Bar-age gate resolved for daily-bar strategies.** The 2 h limit was designed for hourly crypto bars; a monthly rule on daily bars can never pass it. Independent Risk's opinion: a timeframe-aware rule ("signal bar is the last closed bar of the strategy's own timeframe, at most one bar-length plus 24 h old") is sound and not weaker in substance. In form it loosens a reviewed restriction for this strategy, so it needs a written proposal and the owner's decision, then an engine change with a test. Check: risk.json or the engine records the rule; `node --test` for the engine passes with a daily-bar case; this file's test above re-run shows no bar-age rejection.
4. **Clearance route chosen and recorded.** Either (a) this sleeve is cleared as a RISK-cleared strategy with a verdict line in `runs/RISK-02/decision.md` written by Independent Risk after conditions 1 to 3 and 5 to 9 are met (never "CLEARED WITH CONDITIONS" in that file: the runner reads it as cleared), or (b) the desk's forward-test mode is enabled by the owner with Independent Risk's review, and the sleeve runs under its caps. Check: one of the two records exists and names this strategy id.
5. **Execution path built and reviewed by Tester before use:** a monthly runner (not the hourly one) that (i) runs only on the §11.2 dates and inside 15:30–16:00 ET, (ii) fetches daily IEF and BIL bars and fresh equity quotes through the paper client, (iii) writes the decision record, then the journal entry, then the order, (iv) can sell (the desk runner cannot), (v) sends whole-share quantities and checks ±2% against the whole-share target, (vi) refuses if the previous session's log record is missing, (vii) applies the 0.5% fill-versus-mid review hold. The strategy spec and `study003-tsmom-ief-bil-backtest.json` exist under `ops/trading/strategies/`. Check: files exist; Tester's review record; a dry run against the engine with `placeOrder` stubbed shows approve.
6. **Sell only if the buy would pass:** the runner pre-checks the buy with the engine (position count, kill switch, daily loss, gross cap) before sending the sell, and if the buy is refused after the sell, logs "engine-blocked, sleeve in USD" and re-tries the buy next session up to three times, then alerts. Check: code path and a unit test.
7. **Stops logged as a supervisory overlay (§11.4):** the decision record holds the stop price; a daily check (the §11.2 re-check slot or the desk monitor, which has no stop logic today) logs IEF's close against the stop; a trigger moves the sleeve to BIL and is logged; the no-stop record is the holding implied by the signal alone, computed from the same records. Check: records show `stop_price`, `stop_checked_at`, `stop_triggered`; the summary shows two equity columns.
8. **Sleeve halt and daily review enforced by the study's monitor** with the dollar values at the chosen size (450 USD halt; 67.50 USD one-day review on 2 250 USD) written in the first `paper-log/` record. Check: first record present before 2026-11-02.
9. **Labelling:** every `paper-log/` record and the summary carry "paper record of a not-supported rule". Check: grep.

What would clear it: conditions 1, 2, 4 and 9 are paperwork and could be done this week; 3 needs the owner; 5 to 8 need code and a Tester review. A re-review takes an hour once they exist.

## Not checked

- Current IEF and BIL prices and spreads (no network); the arithmetic uses 95.01 and 91.51 with a 2-cent spread, labelled inferred.
- The desk runner's and engine's test suites (not run here).
- The journal library's required fields, `lib/journal.mjs`.
- Whether the paper account can place equity orders at all (the ops client has never sent one).
- The NYSE calendar for 2026-10-30 and 2026-11-02 (taken from the task brief).
- The owner's delegation record of 2026-10-21 (cited by the pre-registration, not read).
