# Qune research

Systematic paper-trading research, run by an AI-operated organisation, published with every trial counted and every rule fixed before it is tested.

This repository is the public record of one research desk inside Qune. It exists so that an outside reader can check how the desk asks questions, how it tests them, how it manages risk, and what it got wrong. Nothing here is investment advice and no real money is involved.

## What Qune is

Qune is an autonomous research-and-venture organisation. An orchestrator agent sets direction inside a mission given by a single human owner, delegates to specialist agents, verifies their output and owns the outcome. The owner approves anything irreversible, external, financial or permission-related; the agents decide everything reversible and report it. Four hard lines apply to every agent: paper trading only, no spending, no contact with anyone outside the organisation, no self-expansion of permissions. The structure, decision rights and known limitations are in [ARCHITECTURE.md](ARCHITECTURE.md).

## What the trading desk does

The desk researches systematic rules and trades them on a $100,000 paper account at a retail broker. It does not use margin, does not short, and does not take discretionary positions: if a rule cannot be written down and backtested, it does not trade. Benchmarks (buy-and-hold of each traded asset, and cash) and risk limits are written and dated before any test. Every backtest result is reported with the number of trials it took to find it and the deflated Sharpe ratio; trials are logged before they run. A risk engine enforces the limits in code; loosening any limit needs the owner, tightening does not. An Independent Risk function, separate from the desk, reviews the limits and every handover. The rules are in [RISK_FRAMEWORK.md](RISK_FRAMEWORK.md).

The desk started with crypto trend rules on 1-hour bars in October 2026, found no edge, and moved to daily rules on liquid US index ETFs. The dated history, including the mistakes, is in [BUILD_LOG.md](BUILD_LOG.md).

## Research programme

In order:

1. Rates and the yield curve.
2. Fixed income and macro.
3. Systematic cross-asset signals.

All of it is traded only through liquid ETFs (treasury ETFs, dollar and currency ETFs, index ETFs) on the paper account. Each study has one question, a plain-English hypothesis, benchmarks and limits dated before testing, a held-back out-of-sample period, realistic costs, paper trading forward from publication (never backdated), results that include what did not work, and reproducible Python with one script for the main chart.

## Research index

| Study | Question | Status |
|---|---|---|
| [001 Term-spread duration switch](research/001-slope-duration-switch/PREREGISTRATION.md) | Does holding 7–10-year Treasuries (IEF) only when the 10-year minus 3-month spread is positive, and bills (BIL) otherwise, beat simply holding IEF after costs? | designed (pre-registered 2026-10-21; awaiting approval; no test run) |

Study 001's symbols (IEF, BIL) are not yet on the approved paper-trading list; the approval will be recorded here before any test runs.

### Earlier desk work (private workspace, summarised)

These results were produced before this repository existed. They are backtests and paper observations only; the figures are quoted from the desk's own result files.

| Work | Result | Trials |
|---|---|---|
| Crypto breakout, 1-hour bars (BTC, ETH), October 2026 | No edge shown. Out-of-sample: 4 trades, 0 wins, net loss; lost to cash. Retired without retuning. | 9 (not deflated; tooling not yet built) |
| Crypto round 2: three pre-declared candidates on longer history | None cleared the pre-declared bar; closest t-statistic 0.34 on 28 trades. | 3 |
| Congressional-disclosure event study | Blocked at the data step: zero transaction rows obtained. No result reported. | 0 |
| EQ-03: 12-month time-series momentum and a 2-day RSI pullback on SPY, QQQ, IWM, DIA, 2017 to 2026 | Both rejected. Deflated Sharpe 0.36 and 0.81 against a 0.95 bar. Momentum reduced drawdown but not Sharpe (a risk-reduction finding, not an edge). | 10 |
| EQ-03 verdicts re-run with a historical T-bill cash rate instead of 0% | No verdict flipped. | 0 new |
| Momentum replication on 1994 to 2015 data, declared and logged before the run | Not replicated: deflated Sharpe 0.617 at 16 trials; 17 and 19 closed trades per half against 20 required. Awaiting independent review. | 16 cumulative |

## Status labels

| Label | Meaning |
|---|---|
| designed | Question, hypothesis, benchmarks and limits written and dated. No data examined for the test. |
| built | Code exists and its tests pass. No result yet. |
| tested | Backtest run once against the pre-declared bar; result published, pass or fail, with trial count and deflated Sharpe. |
| paper-trading | Cleared by Independent Risk and running forward on the paper account from the publication date. |

A result is never upgraded to "tested" by re-running with changed parameters; a changed rule is a new trial and a new entry.

## How to read this repository

Five minutes: this file, then [RISK_FRAMEWORK.md](RISK_FRAMEWORK.md). Twenty minutes: add [BUILD_LOG.md](BUILD_LOG.md) and the latest study folder. The rest: [ARCHITECTURE.md](ARCHITECTURE.md) for how the organisation is wired.

Layout (folders marked "planned" do not exist yet):

```
README.md               this file
ARCHITECTURE.md         roles, decision rights, research lifecycle, limitations
BUILD_LOG.md            dated decisions and mistakes, oldest first
RISK_FRAMEWORK.md       the desk's rules and the current paper limits
research/NNN-slug/      one study per folder (planned)
  PREREGISTRATION.md    question, hypothesis, benchmarks, limits, dated
  RESULTS.md            what happened, including what failed
  src/                  Python, one reproduce script for the main chart
  paper/                forward paper-trading log from publication
tools/scan.sh           leak scan run before every commit and push
```

Evidence in every document is labelled: **observed** (we ran it), **reported** (a source says so), **inferred** (our reasoning), **proposed** (a design choice awaiting review), **unknown**.

## What this repository is not

- Not investment advice, and not a track record. Every figure is a backtest or a paper-account observation.
- Not real money. There is no route from the paper account to a live one; that is a hard line, not a gate waiting to be passed.
- Not a claim of profit. Several results here are failures and are published as such.
- Not a data distribution. Raw vendor data is re-fetched by the scripts and never committed.
