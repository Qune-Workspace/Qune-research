# Architecture

Qune is a small organisation of AI agents with one human owner, built so that no single agent can approve its own work, loosen its own limits or spend anything.

This document covers who does what, who may decide what, how a research idea becomes a paper trade, how independence is enforced, the one shared resource that shapes the whole operation, and what the structure cannot guarantee.

## Roles

| Role | Owns | Does not do |
|---|---|---|
| Owner (human) | The mission, the hard lines, every irreversible or external decision, every loosening of a limit | Day-to-day direction; the owner is not required to reply between tasks |
| Orchestrator (Qune) | Direction within the mission, the task queue, delegation, verification of every handover, the outcome | Accept its own work as a desk result; write to protected files without a recorded approval |
| Strategy | The ranked list of what would move the organisation most; the weekly strategy review | Operate the desk |
| Tech Lead | Tooling, reliability, the controller that runs unattended work | Review desk output |
| Tester | Independent review of desk output: re-computes claims from the result files, runs the test suite, accepts or returns each task with a named defect | Place orders; read credentials; re-run research scripts that overwrite their own outputs |
| Trading desk | Hypotheses, pre-declarations, backtests, the written strategy specifications, the post-trade reviews | Accept its own work; change limits; place an order by hand |
| Independent Risk | Review of risk parameters, review of every strategy that reaches the bar, clearance before anything trades | Write the strategy or the risk proposal it reviews |

The orchestrator, Strategy, Tech Lead and Tester are separate agents with separate instructions. The desk runs as its own agent with its own memory. Independent Risk runs as a separate lane; the reviewer of a proposal is never its author.

```
                 Owner (human)
                 mission, hard lines, irreversible decisions, loosening
                        |
                        v
                 Orchestrator (Qune)
                 queue, delegation, verification, outcomes
          ______________|_______________________
         |              |              |        |
     Strategy       Tech Lead       Tester   Trading desk  <---- reviewed by ---- Independent Risk
     direction      tooling,        reviews  research,                            limits, clearance
                    controller      desk     backtests,
                                    output   paper runner

     Hard lines on every box: paper only, no spending, no external contact, no self-expansion of permissions.
```

## Decision rights

The default rule: reversible, within budget and inside the hard lines means the orchestrator decides. Money, credentials, permissions, anything external and anything irreversible means ask the owner first. "Reversible" means the undo command can be named before acting and works without the owner.

| Decide and act (log only) | Decide, act and inform | Ask the owner first |
|---|---|---|
| Create, reorder, merge or kill tasks | Reversible configuration changes that are backed up and are not a permission, billing, model or credential change | Any purchase or subscription |
| Accept or return reviewed work on the Tester's findings | Lifting a guard hold whose cause is documented and the orchestrator's own | New keys, tokens, logins, sign-ups |
| Pre-declare and run research within the mandate; log trials | Starting or stopping a lane | Widening what any agent can do |
| Tighten a research or risk rule | A new Tester, Strategy or Security slice | Messages or posts in the organisation's name; off-host copies; contacting anyone |
| Fix bugs in own tooling | | Looser trading limits, live trading, new instruments, options orders |

Why it is drawn this way: the expensive failures of an autonomous organisation are the ones that cannot be undone. Everything that can be undone is cheaper to do and report than to queue for a human. Everything that cannot be undone, or that changes who may do what, is cheap to wait for. The tie-breaker is explicit: if the undo cannot be named, it is ask-first.

## Research lifecycle

Every study passes the same gates in order. A gate is a check that produces a dated artefact; the artefact is committed before the next gate opens.

1. **Question.** One question and a plain-English hypothesis with an economic reason, written before any data is examined for the test.
2. **Pre-registration.** Universe, entry, exit, sizing, switch-off conditions, benchmarks (buy-and-hold of each traded asset, and cash), the out-of-sample split, the cost assumptions, the pass bar and the trial count. Committed in its own commit so the history shows the parameters existed before the result. Trials are logged in an append-only, hash-chained registry before they run; the registry row records the hash of the pre-registration file.
3. **Approval to test.** The owner sees the pre-registration before any test runs. New symbols need an approval recorded before they can paper trade.
4. **Build.** Backtest code with tests that pass. The backtest and the paper runner call the same strategy module, so what was tested is what trades. The tests run on every push to the public repository (GitHub Actions, constructed data only), with lint, type checking and a coverage floor on the shared library; `make test` runs the same suites on a reader's machine.
5. **Test, once.** The backtest runs one time against the declared bar. The out-of-sample period is touched once; if it is used to choose anything, it is burned and the report says so. Reports show zero, base and raised costs. Failure is reported with its numbers. An ambiguous result is reported as ambiguous; the original numbers are the headline.
6. **Independent review.** The Tester re-computes the claims from the result files and checks that the pre-registration preceded the run. The reviewer's recomputation script is committed beside the study and re-run by CI on every push (`make reproduce`), so a later edit to a published number would show as a mismatch. A pass goes to Independent Risk as a review task; a pass is not an approval.
7. **Clearance.** Independent Risk clears the strategy for the paper account under the limits in force, or returns it.
8. **Paper trading forward.** The runner executes the cleared rule with the risk engine and journal enforced. Paper trading starts at publication and is never backdated. Fills, slippage against the backtest assumption and no-trade decisions are logged.
9. **Post-trade review.** Every exit record carries the rule's behaviour, the exit reason, slippage, the attribution (market move, rule timing, costs) and one lesson.

A rule that fails at gate 5 is retired as that version. Retuning on the out-of-sample window is a new trial, logged as such, and counts against the deflated Sharpe of every later result in the same family.

**What the five study folders actually show for each gate (precision added 2026-10-24, after reading the list above against `research/`).** The list describes the process as designed; where the published studies differ, the folder is the record.

- *Gate 1.* The question is §1 of each `PREREGISTRATION.md` (Studies 003 and 004 also carry a §0 on why the question was chosen). Only Study 005 has a separate `QUESTION.md`, committed before its pre-registration. *Precision added 2026-10-24 10:21 London:* Studies 002 and 005 also open with a §0, on what they inherit from the study before them (002 from 001; 005 from 003 and its own `QUESTION.md`), not on why the question was chosen; only Study 001 has no §0. Every path this document names was checked on the same date against a clone of `3eda924`: each exists in the study folders it is attributed to. (*Note 10:19:* the label "10:21" above was an estimate; the commit that carries it, `1dcc812`, is stamped 10:18:14 London.)
- *Gate 2.* The public trial log of each study is its `trials.md`: a plain table (date logged, description, date run, code commit) whose chain is the git history, with no hash of the pre-registration file in the rows. The append-only, hash-chained registry named above is the trading desk's internal one; it is not published, and none of the five studies here has rows in it. The public proof that a declaration preceded its result is the commit order, which each study's `REVIEW.md` checked from the timestamps.
- *Gate 3.* The owner saw and approved Study 001's pre-registration and symbols on 2026-10-21. Studies 002 to 005 were approved by the orchestrator under the owner's delegation of the same day, as each `APPROVED` file says; the owner did not see those four pre-registrations before their runs.
- *Gate 4.* Holds for Study 003: `paper/decide.py` imports the signal, calendar and data modules from the study's `src/`. Studies 004 and 005 keep shadow records from the same modules (`src/forward.py`); they place no order.
- *Gate 5.* The notes show the base cost case and a stress case at double the base; a zero-cost figure appears only in Study 004's breakeven cost curve.
- *Gate 6.* CI re-runs the recomputation scripts of Studies 003, 004 and 005 (`make reproduce`); those of 001 and 002 need the raw FRED files, which are not redistributed (`make reproduce-raw`). No study has passed its bar yet. Study 003 went to Independent Risk because its pre-registration paper-trades the rule whatever the verdict (`RISK_CLEARANCE.md`: not cleared, conditions listed); 004 and 005 sought no clearance because they place no order.
- *Gates 7 to 9.* No study has traded. Study 003's first decision record is due on the first month-end after its publication, 2026-10-30, and an order can follow only once the sleeve is cleared; 004 and 005 keep shadow records from the same date (`paper-log/`). No fill and no exit record exists yet.

## How independence is enforced

- **Different agents, different lanes.** The desk and its reviewers are separate agents with separate instructions and separate task lanes. A desk worker cannot claim a review task.
- **The desk never accepts its own work.** Every desk handover waits in review until the Tester accepts it or returns it with a named defect. When more than five tasks are waiting in review, the next review batch is created before any new research task.
- **Independent Risk did not write what it reviews.** The risk-limit file records who set each value, who reviewed it and when; the review note states that the reviewer wrote neither the proposal nor the strategy.
- **Protected files.** The mandate, the limits file, the risk engine, the broker client, the journal library and the runner cannot be changed by a research task. A change guard, which makes no model call, checks every commit within about ten minutes: writes outside a task's allowed paths are restored, a change to a sensitive file is held as a patch for the orchestrator's recorded approval, and a failing test suite or leak scan restores the code. Changes to the organisation's automations or configuration without a recorded approval pause every lane.
- **Code enforces the limits.** The risk engine refuses any order that breaches a limit, cites no written strategy, has no journal entry, or has no stop. No strategy can override it.
- **Tightening is free, loosening is not.** Any role may propose a tighter limit through a risk task. A looser value is written as a proposal with backtest evidence and Independent Risk's opinion, and goes to the owner.

## The shared-allowance constraint

Every agent in the organisation, and every interactive session, draws on a single model-usage allowance measured over a rolling five-hour window. This is the binding resource, more than compute or data.

- A usage guard, which makes no model call, tallies the allowance hourly and pauses the research lanes at 80% of the estimated limit. Its pause has been tested to actually block new work.
- Heavy reading runs at night, one reader at a time. Running fourteen readers in parallel during the day once exhausted the allowance and blocked both worker lanes for about ninety minutes (see BUILD_LOG.md, 2026-10-19).
- The day path (data, signals, risk checks, orders, journal) is built to run with zero model calls, so paper trading does not stop when research pauses.
- Reviews and plans are sized to the allowance: a lite version runs when the window is above a stated threshold, and a second concurrent model-backed worker is not started until the guard has run clean for a week.

## Evidence labels

Every claim in a desk document carries one of five labels. **Observed**: the author opened or ran it in that session. **Reported**: a source says so and the author did not verify it against the full text. **Inferred**: the author's reasoning from observed or reported facts. **Proposed**: a design choice awaiting review. **Unknown**: stated as not known. A number without a label is treated as unverified.

## Chart standard

Every chart the desk publishes is drawn by a script from committed results files through one house style module, `qune_research/style.py`: the title states the finding and a subtitle carries the units and the period; one series in the accent colour and the rest in greys; no top or right spines, faint horizontal gridlines only, no border, lines labelled at their ends instead of a legend, bars sorted by value; one sans-serif family at fixed sizes; a source line bottom left with the data source, the sample period, "Qune Research" and the study id; SVG and a 2x PNG. The module's `check` refuses to save a figure that breaks the mechanical part of the list, and the Tester review applies the whole list (`style.CHECKLIST`) and returns each failure with the exact fix. A study's `results/` charts are the run's own output and are never replaced; the restyled versions live in `charts/` beside a manifest with the input hashes and every number that appears in a title.

## Limitations

- **One human owner.** Every irreversible decision waits for one person. If the owner is unavailable the organisation keeps doing reversible work and stops at the first ask-first boundary.
- **AI agents can be wrong, and confidently so.** The structure assumes it: every desk result is re-computed by a different agent, every limit is enforced by code rather than by instruction, and every automated check that matters makes no model call. None of this makes a wrong conclusion impossible; it makes an unreviewed one unlikely to be published.
- **Pre-declaration is only as strong as the gap it proves.** A hash chain proves that the declaration preceded the run; it does not prove that the parameters were chosen blind. Where the declaration and the run happened seconds apart, the review says so.
- **Deflated Sharpe depends on an honest trial count.** The registry was incomplete for the first week; results from that period are marked, and the organisation reports the deflated Sharpe at the family count and at the full registry count. (2026-10-24: that week's results are the trading desk's internal ones and are not in this repository; none of the five studies here predates the fix. Each study's note and `METHODS.md` report the deflated Sharpe at the registered count and at N = 10 as the sensitivity, from its own `trials.md`.)
- **Small samples.** Most results so far rest on one out-of-sample split and on four highly correlated ETFs, which are far fewer than four independent bets. The desk says this in each report; readers should keep it. (2026-10-24: the "four ETFs" were the desk's internal equity work. As published here, Studies 003 and 005 rest on one instrument pair, IEF against BIL; Study 004 on ten ETFs across equities, Treasuries, credit and real assets; and every study's out-of-sample window is the same single split, 2019 to 2026, touched once per study.)
- **Paper fills are not real fills.** The paper broker ignores market impact, queue position and some fees. Paper performance is treated as evidence that the rule executed as specified, never as evidence of edge.
- **Reliability is young.** The organisation's history begins on 2026-10-09. Unattended operation has failed in ways listed in BUILD_LOG.md: budget exhaustion, a 37-hour login outage, lanes stalled by an empty queue, a guard that paused everything over a self-deleting job. Each has a fix; none has yet run clean for long.
