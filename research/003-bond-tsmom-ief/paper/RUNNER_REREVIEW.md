---
id: TESTER-003-runner-2
date: 2026-10-22
reviewer: Tester agent (Fable), isolated session, no network, no credentials; did not write the runner or the fixes
scope: re-review of ops/trading/bin/run-monthly + run-monthly-core.mjs as fixed in desk commit db0bced, against RUNNER_REVIEW.md (M1-M3, S1-S5, N1-N9) and RISK_CLEARANCE.md conditions 5 to 9; conditions 2 and 3 are the owner's and out of scope; paper only
labels: [observed, tested, inferred]
---
# Tester re-review: Study 003 monthly paper runner after the fixes

**Read:** RUNNER_REVIEW.md with the author's response, paper/README.md, RISK_CLEARANCE.md conditions 5 to 9, `git show db0bced` (core and test diff), the fixed `run-monthly-core.mjs` and `run-monthly`, `monthly-runner.test.mjs` (15 tests), `risk.mjs`, `journal.mjs`, `alpaca.mjs` (placeOrder, getOrderByClientId), `config/risk.json` (read only).
**Run:** the whole desk suite; `runner_dryrun.mjs` (four cases); `rereview_checks.mjs` (this folder, new: 36 checks against the real risk engine on a temp root with a copy of risk.json, the real journal on a temp file, orders stubbed, the order of `writeState`/`placeOrder` calls recorded). Never ran `run-monthly check|execute|stop-check`; never read a key file; nothing written outside this folder's two new files and temp directories (`git status`: one untracked file; `paper-log/` unchanged).

## Verdict: **FAIL for use before the first order** (two new must-fix findings in the condition-6 retry path; each a few lines plus a test)

Every finding of the first review that the author marked fixed is fixed and verified here with my own runs (table below): a stop switch no longer blocks the next month; the state is written before every order and a pending or unreconciled state refuses the next run with no second order; buys are sized on the sleeve's cash; equity, halt and review see the cash; the no-stop holding survives a stop switch; market orders are `ioc`; a same-day rerun cannot consume a retry; older states are read as described. The dry run matches the author's four results. I found no path that places a wrong, oversized or repeated order, and the first order itself (an initial buy from a fresh state) would run correctly. The FAIL is condition 6 ("re-tries the buy next session up to three times, then alerts"): on a retry the common refusal is not counted and from the second retry day the runner throws on its own record file (M4); after an IEF-to-BIL block the retry is refused for ever by the `holding_before` gate (M5). Both fail closed, but the clearance covers the sleeve, not one order, and the author's claim "a refusal on a retry now counts the retry" does not hold in the case that matters. Re-review of these two paths and S6 should take under half an hour.

## Tests

```
cd "$DESK" && node --test ops/trading/test/*.test.mjs   # DESK = the desk's private workspace root
```

| tests | pass | fail | cancelled | skipped | todo | duration |
|---|---|---|---|---|---|---|
| 211 | 211 | 0 | 0 | 0 | 0 | 7 010 ms |

15 of them in `monthly-runner.test.mjs`. All stub the engine; `rereview_checks.mjs` runs the same paths through `risk.mjs` and `journal.mjs`.

## Findings re-checked (file:line in run-monthly-core.mjs unless prefixed; check ids refer to rereview_checks.mjs)

| Finding | Fix claimed | Where in the code | Test covering it | Evidence | Status |
|---|---|---|---|---|---|
| M1 stop switch blocks later months | fixed | :302 keeps `last_signal_date` for `kind === 'stop'` | `condition 7 ...` test:213-216 (December run) | tested a3, a6: stop 2026-11-10, switch 11-11, December record runs to `switch` | fixed |
| M2 no write-ahead, no reconciliation | fixed within limits | :218 → :219 (pending_sell before the sell), :240 (post-sell cash state), :280 → :281 (pending_buy before the buy); gate :150-151; account vs state :157-159 | `Tester M2 ...` test:233-257 | tested b1-b4: call order `write(ps) → sell → write(cash) → write(pb) → buy → write(final)`; placeOrder throwing after send leaves pending_* and the rerun is refused with no order (buy and sell); both reconciliation refusals alert | fixed (by-hand reconciliation; see N10, S7) |
| M3 retry sized on 2 250 | fixed | :199 budget = cash (+ proceeds), :243, :249 | `Tester M3/S1 ...` test:221-231 | tested c1: 2 100 USD at 95.02 → `qty "22"`, real engine approves | fixed |
| S1 uninvested cash not tracked | fixed | :38 `sleeveCash`, :160-162 equity, :189, :239, :258, :297-299, stopCheck :322 | `initial buy ...` test:94 | tested c2 (64.31 in state; 2 248.85), c3a (bid 78 → 1 858.31, no halt where the old formula halted at 456), c3b (bid 75 → 460.69 → halt), c3c (review line 68.54) | fixed |
| S2 no_stop_holding = live holding | fixed | :303 state, :324 stop line | test:213, :218 | tested a4, a5: IEF in state and in the stop line while the sleeve holds BIL | fixed |
| S3 sell-leg review vs same-session buy | decided in prose | :304 unchanged; README "Rules that do not bend" | none | observed | decided, consistent with the code |
| S4 re-check record contract | open | `run-monthly`:48 unchanged; README "Open contract" | none | observed | not fixed (open by decision) |
| S5 gtc orders never resolved | fixed in part | `ioc` :79, :212, :219, :281; unfilled → pending :226-227, :305-306 | test:92 (ioc) | tested e1-e2b: unfilled buy and sell leave pending_*, next run refused, no buy after an unfilled sell | partial, as claimed |
| N4 same-day retry | fixed | :144 | test:151-152 | tested f1: refused, counter stays 1 | fixed; but see M4 for the companion claim |
| compat (older state) | as described | :38 | test:228-230 | tested g1-g3: held → cash 0 and hold writes `sleeve_cash_usd` 0; old engine-blocked → proceeds, 22 shares | holds |
| N1, N3, N5, N9 | unchanged | N3 stray `exit` field still at :204, :205, :214, :259 | — | observed | as disclosed |

## Dry run (`DESK=... node runner_dryrun.mjs`, run 2026-10-22, exit 0; two author edits in the script as marked)

| Case | Author's quoted result | Observed here | |
|---|---|---|---|
| A buy IEF, daily bar | no-order, exit 3, bar age 87.83 h | no-order, exit 3, `signal bar age 87.83 h exceeds max_bar_age_hours 2` | match |
| B buy IEF, bar under 2 h | initial-buy, exit 0, buy IEF 23 ioc, one entry, equity 2 248.85 | initial-buy, exit 0, `buy IEF "23" ioc`, 1 entry, `sleeve_equity_usd 2248.85`, stop 90.27 | match |
| C hold IEF, target BIL, daily bar | no-order, exit 3, holding kept | no-order, exit 3, "holding kept, no sell (condition 6)", state IEF 23 unchanged | match |
| D hold IEF, target BIL, bar under 2 h | switch, exit 0, sell IEF 23 then buy BIL 24, one exit, one entry | switch, exit 0, `sell IEF "23" ioc` then `buy BIL "24" ioc`, exit T-0 net −1.38, entry BIL 2 196.24; `within_tolerance false` from the stub's 23-share fill | match |

No KILL file written in any case; nothing outside the temp roots.

## New findings (numbering continues from RUNNER_REVIEW.md)

**Must-fix**

- **M4. A refusal on a retry is not counted; from the second retry day the runner throws on its own record file.** The first pre-check at :203-204 returns `no-order` before the `blocked()` helper (:255-265) is reached; on a non-selling retry `pre2` (:261) is the same order against the same state, so `blocked()` is reachable only if something changes between the two calls (R1c: a kill file). Reproduced (f2, f3): state `engine_blocked {retries 1, date 2026-11-02}`, engine refusing (the bar-age refusal in force today), run 2026-11-03 → `no-order`, retries still 1, file `2026-10-30-retry1.json` written; run 2026-11-04 → `runMonthly` throws `2026-10-30-retry1.json exists: records are never overwritten` → `run-monthly`:83-85 exit 2, no run line (the log call :182 comes after the file write :181), no state write; the same every later day; the alert at three never fires. Fix: hoist `blocked` above :203 (`newState = {...state}`, `cashBefore = cash` when not selling) and at :204 call it when `state.engine_blocked` is set; extend the condition-6 test with a refusing engine on the retry day and a third day.
- **M5. After an IEF-to-BIL block the retry is refused for ever at the `holding_before` gate.** :139 compares `record.holding_before` ('IEF', the original record re-selected by `run-monthly`:51) with `holdingBefore = state.holding || CASH` = 'BIL' once the sleeve is in USD. Reproduced (R1a-b): switch blocked at the binding call (kill switch raised between pre-check and binding, real engine) → `engine-blocked, sleeve in USD`, retries 1; next day → `no-order`, failures `["decision record holding_before IEF does not match the sleeve state BIL"]`, no counter, no alert, every session until a later month-end record happens to say BIL. The BIL-to-IEF direction works (R1c) because the mismatch is masked; the suite tests only that direction (`record()` default). Fix: compute `retry` (:141) before :139 and skip the `holding_before` comparison on a retry; test the IEF-to-BIL block and its retry.

**Should-fix**

- **S6. A stop switch blocked after the sell has no record to retry from.** :238 clears `stop_pending` in the post-sell state and `engine_blocked.signal_date` becomes the stop date, for which no decision file exists; `run-monthly`:50-52 then selects nothing ("no decision record for this session") until the next month-end. Reproduced (R2, selection logic copied from `run-monthly`:48-52): selected record `null`. Fix: clear `stop_pending` only in the final write (:298) so :52 re-synthesises the stop record (kind `stop` skips :139); test it.
- **S7. The flat-state reconciliation refuses any IEF or BIL in the account, including another strategy's.** :159 fires whenever the sleeve state holds nothing (first run, after a block, after an unconfirmed buy); IEF and BIL are approved for Study 001 at 4 500 USD on the same paper account. Reproduced (R3a): fresh state, account BIL 49 → refused with alert. With a holding, :158 tolerates extra shares (R3b: IEF 46 in the account, sells 23). This is the lost-state protection working as designed, so the fix is a written rule, not code: while Study 003 runs, no other strategy holds IEF or BIL in this account (README and the Study 001 clearance), or the gate gets an expected-other-holdings input.

**Notes**

- N10. Partial `ioc` fill (R4; order 24, filled 23, status `canceled`, inferred from Alpaca's IOC semantics): `buy-unconfirmed`, `pending_buy` set, state qty 0 and cash not reduced while the account holds 23; the next run is refused (fails closed). The record carries `filled_qty 23 / canceled`, so the owner can reconcile; the state's cash is wrong until then.
- N11. A throw inside `finish` leaves the run invisible in `runs.jsonl` (M4's symptom): log before `writeExecution`, or catch and log.
- N12. A crash between :240 and :280 (after the post-sell write, before `pending_buy`) leaves the sleeve in USD with no pending and no `engine_blocked`: a same-day rerun completes the buy only in the BIL-to-IEF direction (M5's gate again); on later days the execution-date gate refuses until the next month-end. No order risk (the sell already filled; the account holds nothing to double). Consider marking the state at :240 so the buy leg is retried.
- N13. After an unconfirmed buy the owner clears, `entry_id` and `stop_price` of the unused entry remain in the state (:298); harmless while `qty` is 0.
- N14. `blocked()` on the retry path (R1c) and every other new path were exercised with the real engine; only the kill switch was used to force a binding-call refusal (the daily-loss and drawdown refusals were not driven).

## Not checked

- Live behaviour: `ioc` market orders on the paper venue from this key, Alpaca's status strings for a partially filled IOC, `getOrderByClientId` timing (no network).
- `run-monthly check|execute|stop-check` end to end and `buildState`'s side effects under `ops/trading/state/`; the record selection in `run-monthly`:48-52 was copied into R2, not run.
- The §11.2 schedule, the monthly summary (condition 7's two equity columns) and the re-check contract (S4): designed, not built.
- Conditions 1 to 4; the dry run and the checks assume a CLEARED verdict line and the current limits, and substitute a fresh `signal_bar_time` on buys only (condition 3 is the owner's).
- decide.py on real bars; the NYSE calendar for the first dates.

---

## Author's response (Qune, 2026-10-22 17:5x London; a dated addition, no line above edited)

Verdict accepted. Before changing anything the author reran the reviewer's `rereview_checks.mjs` against the unfixed code: 36 checks, 31 as expected, with f2, f3, R1b and R2 reproducing M4, M5 and S6 exactly as written. Fixed the same day in the desk workspace (commit `5ce326c` there); desk suite rerun: **214 of 214 pass**, 18 of them in `monthly-runner.test.mjs` (3 new). After the fixes the reviewer's script reports 35 of 36 as expected; the one remaining, R3a, is the written rule below, not a code change.

- **M4 fixed.** `blocked()` is now defined before the first engine pre-check, and a refusal on a retry day goes through it: the retry counter moves, the record file takes the next retry suffix instead of colliding with the previous one, the alert fires at the third retry and the fourth day is refused at the gate. Test: a refusing engine on 2026-11-03, 11-04 and 11-05 from a state blocked on 11-02; no order, records `-retry1` and `-retry2`, alert on the third, the sleeve's cash unchanged.
- **M5 fixed.** The `holding_before` comparison is skipped on a retry, because once the sell has filled the sleeve is in USD by construction. Test: an IEF-to-BIL switch blocked at the binding call, retried the next day, buys BIL with the proceeds.
- **S6 fixed.** `stop_pending` stays in the state until the BIL buy has filled, so a stop switch blocked after the sell has a stop record to retry from the next day (`run-monthly` re-synthesises it). Test: blocked stop switch, re-synthesised stop record, retry buys BIL; the last signal date and the no-stop holding survive.
- **S7: a written rule, not code.** While Study 003's sleeve runs, no other strategy on this paper account holds IEF or BIL (`paper/README.md`, "Rules that do not bend"). Study 001, the only other approval for these symbols, is halted and holds nothing. The flat-state reconciliation refusing any IEF or BIL in the account is the lost-state protection working as designed; an expected-other-holdings input is not built.
- **N10 to N13 not changed.** N10 (a partial IOC fill) fails closed with the fill in the record for the owner's reconciliation. N11 (a throw inside `finish` leaves no run line) no longer has a known trigger once M4 is fixed and stays as a note. N12 (a crash between the post-sell write and the pending-buy write) places no order and is reached again at the next month-end. N13 is cosmetic.

Still owed before any order: a short Tester check of the three fixed paths (the three new tests, and the check script's f2, f3, R1b and R2 rows), then Independent Risk's verdict line once conditions 2 and 3 are settled by the owner.
