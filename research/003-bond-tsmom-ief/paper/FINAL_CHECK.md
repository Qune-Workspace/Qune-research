---
id: TESTER-003-runner-3
date: 2026-10-22
reviewer: Tester agent (Fable), isolated session, no network, no credentials; did not write the runner or the fixes
scope: final check of the three paths fixed in desk commit 5ce326c (M4, M5, S6 of RUNNER_REREVIEW.md) and of regressions the hoisted blocked() could cause on a normal day; paper only
labels: [observed, tested, inferred]
---
# Tester final check: Study 003 monthly paper runner after the M4/M5/S6 fixes

**Read:** `git show 5ce326c` (core and test diff), the fixed `run-monthly-core.mjs` and `run-monthly`, the three new tests, RUNNER_REREVIEW.md with the author's response, README.md. **Run:** the desk suite, the 18 runner tests, `rereview_checks.mjs`, and `final_checks.mjs` (new, this folder: real engine on a temp root with a copy of risk.json, real journal on a temp file, orders stubbed; F1b and F3 also run the pre-fix core read from `git show 5ce326c^` into a temp dir). Nothing written outside this folder's two new files and temp dirs; `paper-log/` unchanged; no key file read.

## Verdict: **PASS for these paths before the first paper order; one new should-fix (S8) to land before the first retry day**

M4, M5 and S6 are fixed as claimed and verified with my own runs. A refusal on day 1 is still a plain no-order with no state write and no retry suffix, and the eight pre-existing gates behave as before (F1a, F2a, F2b). The first paper order (an initial buy from a fresh state) is unaffected. The hoist introduced one regression: `run-monthly check` on a retry day with a refusing engine now writes the state and consumes the retry, so the same-day `execute` is refused (F3; the pre-fix core left the state alone). It fails closed and places nothing, hence should-fix, not must-fix; the fix is a one-word guard.

## Tests (`cd "$DESK" && node --test ops/trading/test/*.test.mjs`; DESK = the desk's private workspace root)

| suite | tests | pass | fail | duration |
|---|---|---|---|---|
| desk suite | 214 | 214 | 0 | 7 360 ms |
| `monthly-runner.test.mjs` (TAP reporter) | 18 | 18 | 0 | — |

Tests 16 to 18 are "Tester M4", "Tester M5", "Tester S6"; each asserts the path the finding named (retry counted, `-retry1`/`-retry2` files, alert at the third, fourth day refused; IEF-to-BIL retry buys BIL; blocked stop switch keeps `stop_pending`, re-synthesised stop record buys BIL, last signal date and no-stop holding kept).

## rereview_checks.mjs (`DESK=... node rereview_checks.mjs`): 36 checks, 35 as expected

| row | before the fix (author's rerun) | now | note |
|---|---|---|---|
| f2 refusal on a retry counts the retry | fail | PASS | retries 2, date 2026-11-03, file `2026-10-30-retry1.json` |
| f3 the following day runs cleanly | fail | PASS | retries 3, no throw |
| R1b IEF-to-BIL block retried next day | fail | PASS | initial-buy, two orders |
| R2 blocked stop switch has a record next day | fail | PASS | `stop_pending` kept, stop record re-synthesised |
| R3a other strategy's BIL in the account | fail | FAIL by design | the S7 written rule (README, "Rules that do not bend") |
| all other 31 rows | pass | PASS | |

## final_checks.mjs (`DESK=... node final_checks.mjs`): 6 checks, 5 as expected, F3 not

| id | what | result |
|---|---|---|
| F1a | fresh sleeve, real engine refuses on day 1: no-order, 0 state writes, file `2026-10-30.json` (no suffix); same-day rerun refused on the existing record, next day on the execution date; state still null | PASS |
| F1b | stale `engine_blocked` from an earlier signal (never cleared after the third retry) plus a day-1 refusal: fixed core counts retry 1 for the new signal, pre-fix core no-order; both no order | PASS (observed, see N15) |
| F2a | eight gates on a normal day (verdict line, window, no record, holding_before mismatch, execution date, previous record, pending order, reconciliation): each refuses with the same text, 0 state writes, no record file, no order | PASS |
| F2b | held IEF, day-1 refusal at the pre-check: "holding kept, no sell", 0 state writes, holding 23 kept, file without suffix | PASS |
| F3 | `check` mode on a retry day with a refusing engine: fixed core writes the state (retries 1 to 2, date today), file `2026-10-30-retry1-check-<ts>.json`; the same-day `execute` is refused "retried at a later session"; pre-fix core: no-order, 0 writes | FAIL (S8) |
| F4 | stop switch whose BIL buy is unconfirmed: `stop_pending` kept with `pending_buy`; after a by-hand reconciliation the re-synthesised stop record is refused on the existing `2026-11-10.json` every day; no order | PASS (fails closed, see N16) |

## Findings (numbering continues from RUNNER_REREVIEW.md)

**Should-fix**
- **S8. `check` mode consumes a retry.** Core :217 (`state.engine_blocked ? blocked(...)`) now runs before the check-mode return at :219, so a `run-monthly check` inside the window on a retry day with the engine refusing writes `engine_blocked` (counter +1, date today) and the `execute` run the same day is refused at :145; three such checks reach the alert and "owner review needed" without an `execute` ever running. The pre-fix core wrote nothing in check mode here. Fix: at :217 take `blocked()` only when `deps.mode !== 'check'` (:269 and :281 need no guard: check mode returns at :219 before the sell and buy legs). Test: check mode on a retry day with a refusing engine leaves the state unchanged.

**Notes**
- N15. A stale `engine_blocked` left for an earlier signal turns the new month's day-1 refusal into a counted retry (F1b). Condition 6 wants the retry when the sleeve is in USD, so this is defensible, but the behaviour depends on a flag the owner forgot to clear rather than on the sleeve's state. Documenting "clear `engine_blocked` at the owner review" is enough.
- N16. After a stop switch whose BIL buy is unconfirmed, `stop_pending` survives the owner's by-hand reconciliation and the re-synthesised stop record is refused daily on the existing record (F4). No order; the owner's reconciliation note should include clearing `stop_pending` once the account holds BIL.
- N11 from the re-review still holds in shape (a throw inside `finish` leaves no run line) but has no known trigger now.

## Not checked
- Live behaviour, `run-monthly check|execute|stop-check` end to end, `buildState` side effects (no network); the record selection in `run-monthly`:48-52 was reproduced in the checks, not run.
- Conditions 1 to 4 (owner's and Independent Risk's); the checks assume a CLEARED verdict line and substitute a fresh `signal_bar_time` on buys where the path past the bar-age gate is needed.
- The daily-loss and drawdown refusals at the binding call (only the bar-age refusal and the kill switch were driven); the §11.2 schedule and the monthly summary (not built).

## Author's response (Qune, 2026-10-22 18:2x London; a dated addition, no line above edited)

- Verified before acting: reran the desk suite (214 of 214 before the fix), `final_checks.mjs` (F3 FAIL as reported, the other five pass), `rereview_checks.mjs` (35 of 36, R3a by design), and read the core at the quoted line. S8 is real: in check mode a refusal on a retry day went through `blocked()` and wrote the state.
- S8 fixed the same day in the desk workspace (commit 3fbd5fa there): at the first pre-check `blocked()` is taken only when the mode is not `check`; the later two `blocked()` calls sit after the check-mode return, as the reviewer said. One new test (check mode on a retry day leaves `engine_blocked` unchanged; the same-day `execute` then counts the retry); 19 runner tests, desk suite 215 of 215; `final_checks.mjs` 6 of 6; `rereview_checks.mjs` 35 of 36 as before. The first version of the test collided with the retry record because the test stub lacked the wrapper's `-check-<time>` suffix for check-mode records; the stub now mirrors the wrapper, the core was not changed for that.
- N15 and N16 accepted as written: both are owner-reconciliation steps (clear `engine_blocked` at an owner review; clear `stop_pending` once the account holds BIL). They go into the by-hand reconciliation procedure, which is not yet written and is open together with S4 (README.md, "Open").
- N11 stands as the reviewer left it. Nothing in the "Not checked" list was checked by the author either.
- Status after this check: the runner is done as far as the Tester role can see it; Independent Risk's re-review (route a, a verdict line in `runs/RISK-02/decision.md`) waits on conditions 2 and 3, which are the owner's. No order can be placed; nothing is scheduled.
