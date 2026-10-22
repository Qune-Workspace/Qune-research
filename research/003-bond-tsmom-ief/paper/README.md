# Paper-trading path for Study 003 (PREREGISTRATION.md §11, §12)

This is the forward record of a rule whose verdict was **not supported** (README.md). It is run anyway because §11 was pre-registered before any result and the forward record is the only test nobody has seen. Every line of it is labelled as the paper record of a not-supported rule. Paper only; there is no real money anywhere in this organisation's trading.

First signal date: **2026-10-30** (last NYSE trading day of October). First execution date: **2026-11-02**. Starting position: BIL. Sleeve: **2 250 USD** (tightened from the pre-registered 4 500 USD on 2026-10-22; §16 amendment). Nothing can be placed before `RISK_CLEARANCE.md` records Independent Risk's clearance and every condition in it is met.

## Pieces and their status

| Piece | What it does | Status (2026-10-22) |
|---|---|---|
| `paper/decide.py` | After the close on the signal date: computes `mom_t` and the target from Alpaca `adjustment='all'` daily bars with the study's own `src.signal.excess_momentum` (the function the backtest called); writes one JSON record per signal date to `paper-log/decisions/`; refuses a date that is not the last NYSE trading day of its month, a missing month-end bar, or a lookback the bars do not cover (`status: signal unavailable`); never overwrites a record | **built, tested** (8 tests on synthetic bars in `tests/test_paper_decide.py`; in CI). Not yet run on real bars: the first signal date is 2026-10-30 |
| Bar fetch | `src.alpaca_bars.fetch_bars` into `paper-log/raw/` (git-ignored) with its own `paper-log/manifest.json` (row counts and SHA-256 only). The study's `data/raw/` and `results/data_manifest.json` are never touched, so the published hashes stay frozen | **built** (parameters of the existing fetcher), not yet run |
| Order leg | On the execution date, 15:45–15:55 ET: reads the decision record, writes the desk journal entry first, then sells the holding, waits for the fill, buys the target with the proceeds in whole shares; appends the fills, the official close and the slippage in basis points to the record. Orders go only through the desk's paper broker client and its risk engine (private workspace, `ops/trading/lib/alpaca.mjs` and `risk.mjs`), which refuse any host but the paper endpoints, any order without a stop, and any breach of the desk limits | **designed**, not built |
| Schedule | Two unattended jobs: the decision after 17:00 ET on the last NYSE trading day of each month; the orders on the next NYSE trading day. A missing bar re-checks each NYSE day at 15:30 ET for up to three days, then holds and alerts the owner (§11.2) | **designed**, not built |
| Monthly summary | `paper-log/summary.csv` (equity, holding, return, cumulative slippage) and the same-dated B0/B1/B3 benchmarks from the same bars (§11.5) | **designed**, not built |
| Clearance | `RISK_CLEARANCE.md`: Independent Risk's decision and its conditions | **NOT CLEARED on 2026-10-22**, nine checkable conditions; see below |

## Independent Risk's decision of 2026-10-22 and what follows from it

Verdict: **not cleared today**, re-evaluate against nine conditions (`RISK_CLEARANCE.md`). None is a finding against the rule; all are checkable. The reviewer reproduced the engine's refusals with hypothetical orders and no network. What the orchestrator decided the same day, under the owner's delegation of 2026-10-21:

| Condition | Owner of the fix | Status |
|---|---|---|
| 1. Sleeve tightened to **2 250 USD** (one buy under the 2 500 USD per-order cap; 5% IEF stop risks 124 USD against the 250 USD limit; one sell and one buy per month intact) | Qune: a tightening, recorded as a §16 amendment | **done 2026-10-22** |
| 2. Symbol approval scope extended in writing from Study 001 to Study 003 (same symbols, same limits; no numeric limit changes) | Qune records it citing the owner's delegation, after the owner has been told in the daily summary; the limits file is written only through a risk task | pending (daily summary 2026-10-22) |
| 3. The engine's 2-hour signal-bar age gate, designed for hourly crypto bars, refuses every daily-bar entry. A timeframe-aware rule is a loosening in form | **Owner's decision** (ask-first), with Independent Risk's opinion that the rule is sound | pending (daily summary 2026-10-22) |
| 4. Clearance route: (a) a verdict line in the desk's clearance record written by Independent Risk once 1–3 and 5–9 hold, never with conditional wording | Qune chose route (a) | recorded |
| 5. Monthly runner (dates and 15:30–16:00 ET window, daily bars and equity quotes through the paper client, decision then journal then order, sells, whole shares with the ±2% check against the whole-share target, refuses without the previous record, 0.5% fill review), spec and backtest file in the desk's strategies folder, Tester review | Qune builds; Tester reviews | not built |
| 6. Sell only if the buy would pass the engine; "engine-blocked, sleeve in USD" path with three retries | Qune builds | not built |
| 7. Stop as a logged overlay: stop price in the record, daily check, no-stop record alongside | Qune builds | not built |
| 8. Sleeve halt (450 USD) and one-day review (67.50 USD) in the first record | Qune builds | not built |
| 9. Every record labelled "paper record of a not-supported rule" | Qune builds | not built |

**Dates.** If the conditions are not all met by the close of 2026-10-30, the decision record for that date is still written (it costs nothing and is never backdated) but no order follows; the first paper order then waits for the first month-end after clearance. A record without an order is labelled as such. Nothing is ever backdated to make the record look longer.

## Rules that do not bend

- **Never backdated.** Every record carries `run_at_utc` and is committed on the day it is written; the commit timestamp is the second clock. A record for a signal date is written after that date's close, never before.
- **Never rewritten.** `write_record` refuses to overwrite. A correction is a new file with a note pointing at the old one.
- **Same code as the backtest.** The decision uses `src/signal.py`, `src/calendar.py` and `src/alpaca_bars.py` unchanged. A change to `src/` after publication is a dated amendment (§11.4) and the record before and after it is kept apart.
- **Desk limits win where tighter.** The sleeve's §12 limits sit under the desk's `RISK_FRAMEWORK.md`; where the two differ, the tighter one applies and the clearance note says which.
- **The engine stop is an overlay.** If the desk's required stop is triggered, the trigger is logged and the no-stop rule's record is computed alongside (§11.4).

## Running the decision (from the study folder)

```
python -m paper.decide --signal-date 2026-10-30 --holding BIL --fetch
```

Credentials come only from the environment variables `src/alpaca_bars.py` reads; nothing is read from a file in this repository. `--dry-run` prints the record without writing it.
