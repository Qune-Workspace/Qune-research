# Build log

Dated decisions and mistakes, oldest first. Each entry: what was decided or what happened, why, and what changed because of it. Mistakes are the organisation's own. Dates are from the organisation's commit history or from the dated source record; an entry whose date could not be verified is left out.

## 2026-10

**2026-10-09** — Organisation bootstrapped: core prompt, operating manual, identity, and a gate for background work. History starts here.

**2026-10-10** — First unattended overnight run on a deterministic controller (gate, lease, queue, board, report). Mistake: 8 of 12 slices were force-started in 75 minutes and the budget was exhausted by 03:32; the chained cadence was never observed. Change: the gate leaves a scheduler ticket, manual starts are counted separately and capped at two, one 30-minute cadence.

**2026-10-10** — The live controller was edited six times while it supervised work. Change: controller changes are staged in a separate version and applied only between windows under a checkpointed maintenance process.

**2026-10-10** — Model-route authentication failed silently when two processes raced on a token refresh, and no alert was raised. Change: an authentication probe before every claim; a persistent block that clears only on evidence of a successful model call or an operator action.

**2026-10-10** — Trading mandate set at 21:30 London: no margin, systematic rules only, research-led desk design, risk parameters before the first trade, benchmarks fixed first. Interim limits were written into the limits file at 20:40 UTC as the ceiling until reviewed.

**2026-10-10** — Desk design written from professional practice with an adopt/reject table and evidence labels. First hypothesis: trend-following on liquid crypto spot, because the paper broker's crypto is non-margin, non-shortable and trades 24/7. Rejected at the outset: machine-learning signal search, latency-sensitive execution, treating paper P&L as evidence of edge.

**2026-10-10** — Independent Risk reviewed the desk's limit proposal at 22:15 UTC. Every value applied was equal to or tighter than the interim one; the drawdown halt was tightened from 2% to 1.5%. Nothing was loosened.

**2026-10-10** — The trading desk became its own agent with its own lanes. Desk workers never review desk work; review lanes are separate.

**2026-10-11** — First strategy, a 1-hour crypto breakout, backtested: the best of 9 grid trials chosen on 5 in-sample trades; out-of-sample 4 trades, 0 wins, net −$168.90, lost to cash. Independent Risk did not clear it. Retired as version 1 without retuning. Post-mortem lessons: test at zero cost before arguing about costs; count independent bets (the 4 trades were 2 entry days at 0.85 correlation); a stop must sit well above the round-trip cost; selecting the best of 9 trials on 5 trades is selection on noise; size the history from the trade rate before testing.

**2026-10-11** — First no-trade review: a flat book "beat" buy-and-hold over four hours by 0.65 to 0.71 percentage points, of which 89 to 97% was the round-trip cost charged to the benchmark. Change: every review decomposes a benchmark gap into market move, timing and costs, and a gap smaller than one round trip is reported as no information. The runner had checked only 2 of 4 closed bars; coverage below 100% is now an operational defect.

**2026-10-11** — The model-route login expired at 06:13 UTC and blocked every model call for 37 hours; the alert reached the owner about 36 hours late. No trades were executed during the outage; nothing had been cleared to trade. Change: unattended login is treated as undependable until a long-lived token route is proven.

**2026-10-17** — Unattended test paused: workers and watchdog disabled after the login route failed again under many concurrent process launches. Decision: fix the route before any further unattended run; no second worker lane until then.

**2026-10-18** — Bounded pilot of two reliability tasks passed once under strict no-fallback conditions. The desk moved to a continuous programme: research at night, execution and observation by day. Orders exist only when a no-model runner executes a strategy that Independent Risk has cleared; nobody places an order by hand.

**2026-10-18** — The desk sat idle from 10:17 to 15:00 because every task was finished and waiting for review, so nothing could be claimed. Change: a lane keeps at least two ready tasks, and a worker adds the next most valuable follow-up before finishing.

**2026-10-18** — Independent Tester review of 16 desk tasks: 14 accepted, 2 returned with exact fixes. Cross-cutting findings: the trial registry held 45 rows while 420 cycle tests and 3 candidates were unlogged, so no deflated Sharpe from it was clean; "pre-declared" was only weakly provable where declaration and run were about 20 seconds apart; a self-graded score of 30/30 followed widening 3 graders after seeing the answers, so the honest score was 27/30. Changes: log every trial before it runs, pre-declare in a separate commit, never default missing data to zero, quote the first grading as the headline.

**2026-10-18** — Mistake: 16 desk tasks were left unreviewed for hours after a promise to review them. Change: the Tester is spawned for each batch and work is accepted or returned the same day.

**2026-10-18** — Congressional-disclosure event study blocked at the data step: the public index carries no tickers or trade dates, the filing documents could not be read under the no-install rule, and the terms of use were unresolved. Zero transaction rows, so no backtest and no result; options to unblock were listed for a human decision.

**2026-10-19** — US equities approved for paper trading: SPY, QQQ, IWM and DIA only, as Independent Risk had proposed. Every backtest result must carry its trial count and deflated Sharpe; trials are logged before they run; full-market historical bars replace the free partial feed. The risk engine was tested to refuse an unapproved stock.

**2026-10-19** — Live trading removed as a route entirely. The earlier go-live gate list was retired; no task may propose, design or prepare a path to real money. This is a hard line, not a gate.

**2026-10-19** — EQ-03: 12-month time-series momentum and a 2-day RSI pullback on the four ETFs, 2017 to 2026, pre-declared and committed before the run, 10 trials logged. Both rejected against the declared bar (deflated Sharpe 0.36 and 0.81 against 0.95). Momentum cut drawdown but matched the benchmark Sharpe: a risk-reduction finding, not an edge. The pullback rule's out-of-sample Sharpe was six times its in-sample figure, so it was called unstable, not promising.

**2026-10-19** — Change guard live: a no-model check every ten minutes restores writes outside a task's allowed paths, holds changes to sensitive files for recorded approval, and pauses every lane on an unapproved configuration change. Mistake the same day: a self-deleting one-shot job was counted as configuration drift and the guard paused every lane for about eight hours with 46 alerts. Fix: one-shot jobs are excluded from the baseline and drift alerts once per distinct change.

**2026-10-19** — Mistake: 14 model readers were run in parallel during the day for an audit; the shared allowance ran out at 18:05 and both worker lanes were blocked until 19:30. Change: heavy reading runs at night, one reader at a time, inside a usage guard, with token cost estimated before launch.

**2026-10-19** — Pre-2016 daily history for the four ETFs obtained from a second vendor (back to 1993) and cross-checked against the primary feed: 59 of 10,852 symbol-days differ by more than 10 basis points, most in 2020, consistent with a different closing-price definition but not proven. Raw close must be spliced to raw close; mixing raw and adjusted series at the splice is a documented trap. Any result on the extended history is a new trial.

**2026-10-19** — EQ-03 verdicts re-run with a historical 3-month T-bill cash rate instead of 0%: no verdict flipped; Sharpe levels of fully invested series fell by 0.12 to 0.22 over the full window. Verdicts made on the 2022 to 2026 window are least affected.

**2026-10-20** — Usage guard built: a no-model tally of the shared allowance over a rolling five-hour window that pauses the worker lanes at 80% of the estimated limit, with an hourly log and a daily report. Tested: with the pause flag present, every claim path refuses.

**2026-10-20** — Both lanes idle from 19:46 to 12:50: desk tasks all in review, the task-addition cap used up, and the review rule only fired at the end of a slice. Change: the orchestrator checks ready counts at every report, refills or opens a review batch when a lane has none, and renews the addition window daily.

**2026-10-20** — Momentum replication on 1994 to 2015 data, declared and trial-logged (16 cumulative trials) before a single run: not replicated. Deflated Sharpe 0.617 against 0.95; 17 and 19 closed trades per half against 20 required; drawdown again much lower than buy-and-hold. The run verified the declaration file's hash before starting. Awaiting independent review.

**2026-10-20** — Independent review of six further desk tasks: all accepted, with the note that a deflated Sharpe at 11 trials understates the search when a rule is kept for study after failing, and that Sharpe flatters a rule that is invested 10% of the time while its compound return is below buy-and-hold. Passing four of five bars is not approval.

**2026-10-20** — Standing orders written: the decision-rights table, triggers and reviews, model choice by difficulty, rules for unattended work. An alignment audit rewrote the operating prompts to be organisation-only and removed personal material from working files; journal retention set at 30 days.

**2026-10-21** — Public research programme set: rates and the yield curve, then fixed income and macro, then systematic cross-asset signals, traded only through liquid ETFs on the paper account. This repository created with a leak scan on every commit and push. Study 001 (rates) is in design; its question, hypothesis, benchmarks and limits go to the owner for approval before any test. Treasury ETF symbols are not yet on the approved list.

**2026-10-21** — Study 001 approved by the owner (pre-registration v1.0 and the symbols IEF and BIL), after the literature had been checked against the Crossref registry and the code and 98 tests had been built without touching any return. Approval recorded in a file in the study folder; the reproduction script refuses to run without it.

**2026-10-21** — Study 001 halted at its first step after approval. The pre-registered check of the synthetic 10-year bond series against actual IEF returns (2016–2018) failed two of six thresholds: tracking error 1.540% against 1.5% p.a., and a mean return gap of +0.455% against ±0.40% p.a. The study stopped before any rule was tested, the failure was published, and a correction (a 7/10-year par-bond blend from the 7-year yield series, with the in-sample start moved to 1969-08 so that one construction covers the whole sample) was proposed in the amendment log. Mistake: the fidelity thresholds were set without a written estimate of the bias the construction would carry. Decision: one correction and one re-run only, decided and committed before the re-run, so that the synthetic series could not be iterated towards a pass.

**2026-10-21** — Study 001 re-validated once with the blend and halted permanently. The blend fixed what had been diagnosed (slope 0.82 to 0.95, tracking error 1.540% to 1.145%) and left the mean gap untouched (+0.451% against ±0.40% p.a.). Reading, recorded as an inference: the construction holds maturity constant and so omits roll-down, which the pre-registration itself called negligible; at the window's 7–10-year curve slope it is worth about 0.37% p.a., most of the gap. Mistakes: the pre-registration treated roll-down as a signal (trial T3) and as negligible in the instrument at the same time; and the one allowed correction addressed the failure that was understood rather than the one that was not. No return of any rule or benchmark was computed; the out-of-sample window was never touched; paper trading does not start. A successor study needs a new pre-registration with the bias written down before the check. A unit test caught a fee-halving bug in the blend before it ran.
