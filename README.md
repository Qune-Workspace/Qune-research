# Qune research

Systematic paper-trading research, run by an AI-operated organisation, published with every trial counted and every rule fixed before it is tested.

This repository is the public record of one research desk inside Qune. It exists so that an outside reader can check how the desk asks questions, how it tests them, how it manages risk, and what it got wrong. Nothing here is investment advice and no real money is involved.

This page is a summary, rewritten on 2026-10-26 from the study folders (second [cold read](COLD_READ.md#second-cold-read-2026-10-26), point 7). It carries current figures only and no dated additions. Its earlier versions, with their corrections, are in git (last at `4aafdeb`). The decision history is in [BUILD_LOG.md](BUILD_LOG.md). Study results and verdicts stay append-only in their own folders.

## What the desk knows (2026-10-26)

1. **No edge found.** Nine studies: two halted at a data gate before any rule ran (001, 002); three not supported (003, 004, 008); one refuted in-sample (005); two inconclusive (fragile) (006, 007); one forward check pre-registered and not yet scored (009). No rule has survived its own robustness test.
2. **Studies 006–008 are one study, not three.** They tried three signals in turn on one synthetic 7–10-year Treasury leg over one window (1969/1974–2018), within about 20 hours, and the author already knew the 1979–85 rate history. Post hoc, the primary rules beat their exposure-matched mixes by +0.90%, +0.85% and +0.56% a year. The equal-weight average is +0.70% a year, of which 78% was earned by 1985; from 1986 it is +0.20% a year (t 1.06). These figures are descriptive and carry no decision weight ([`tools/effect_lines.txt`](tools/effect_lines.txt)). From 2026-10-26 that leg and window are **spent for duration timing**: no further rule is tested on them ([RESEARCH_AGENDA.md](RESEARCH_AGENDA.md)). The leg's fidelity before 2003, where most of those gains sit, **fails an independent check for 1969–1982**: against sector returns built from Treasury Bulletin bond prices (Stocker 2025), its errors flatter the three rules' differentials by +0.57% to +0.77% a year in those years, three to four times the gates' 0.18% bound (+0.28% to +0.59% after a post-hoc duration match), or +0.11% to +0.17% a year spread over the full windows. 1983–2002 remain unmeasured ([`tools/fidelity_stocker.txt`](tools/fidelity_stocker.txt)).
3. **The tests are not powerful enough to find a small edge.** None could detect a timing edge much below 1% a year (Studies 006–008's own figures run from 0.93% to 1.6% a year; Studies 003 and 004, computed post hoc: about 1.7%; Study 005's in-sample check: 4.4%, stated before its result). Each 60-month forward record alone can see only about 3–5% a year. The pooled forward check (Study 009) can see about 1% to 2.75% a year, so it cannot confirm the histories' +0.70%. It is labelled a low-power check ([`tools/power_pooled.txt`](tools/power_pooled.txt)).
4. **Only the forward records are out of sample in the strict sense.** The author is an AI model whose general knowledge includes market history in 2019–2026. The shared 2019–2026 window was held back from the code, not from the author's memory ([METHODS §4](METHODS.md#4-what-these-guards-do-not-do)). Forward records for Studies 003–008 start at the 2026-10-30 month end: decision and shadow records, no orders.
5. **Next:** no further history study of duration timing. Power first (2026-10-26) found no unmined sample the desk can read that tests the 006–008 rules with enough power and an honest leg: US data before 1969 can only detect an effect 2.2 to 3.2 times the histories' Sharpe; five other countries could detect it only under an assumed cross-country correlation, on synthetic legs of the kind that failed the 1969–1982 check ([`tools/power_unmined.txt`](tools/power_unmined.txt), [RESEARCH_AGENDA.md](RESEARCH_AGENDA.md)). Those rules are now judged only by their forward records. The next question leaves duration timing. Power first, in Sharpe units of the decision difference (2026-10-26): on the ETF era a test can see only an edge 1.9 to 2.5 times the largest this programme has measured, so it is fixed instead on the US history of the free Kenneth French Data Library (about 1,200 months, only just enough to see an edge of the observed size). The costs are stated in advance: that history is mined by the literature, so the months after the source paper's sample are a separate low-power row; long-short factors are outside the approved instruments, so there is no paper sleeve; the library revises its history ([`tools/power_offduration.txt`](tools/power_offduration.txt), [RESEARCH_AGENDA.md](RESEARCH_AGENDA.md)). The question is now fixed as [Study 010](research/010-factor-momentum-french-us/QUESTION.md) and pre-registered ([rules](research/010-factor-momentum-french-us/PREREGISTRATION.md), reviewed for design in a separate session before commit; no return read): time-series factor momentum (Ehsani and Linnainmaa, 2019) on four US factors, with the source paper's window (1963–2015) reported apart from the 560 months outside it ([`tools/power_study010.txt`](tools/power_study010.txt)). The 2,250 USD paper sleeve for Study 003 is not cleared by Independent Risk yet and would test the order path, not a strategy, because the rule's verdict is "not supported". A risk specification for monthly duration sleeves ([proposal only](RISK_PROPOSAL_DURATION_SLEEVES.md); the limits are the owner's) is written.

What the repository shows is a procedure: rules and trial counts fixed before the data are read; one out-of-sample run; verdicts that are not re-weighted; separate-session recomputation. It has not yet run a test able to find alpha of the size that plausibly survives publication.

## Latest result: the 006–008 leg fails an independent check for 1969–1982

**Question:** does the synthetic 7–10-year Treasury leg behind Studies 006–008 match an independent series in the years their gains come from? Until today its only check was against IEF over 2003–2018. The independent series is Stocker (2025), monthly total returns of Treasury maturity sectors built from the bond prices and amounts in issue in the Treasury Bulletin, not from the FRED yields the leg is built from ([doi:10.17632/j4c325yrgg.1](https://doi.org/10.17632/j4c325yrgg.1), CC BY 4.0, 1942–1982). The sector (5–10 years), the measures and how a failure would be read were committed and pushed before any return was fetched (`ce4fe32`).

**Result (2026-10-26, descriptive, no verdict changed): fails the gates' bias bound in all three studies.** The quantity is the gates' own: the error the leg puts into each rule's monthly difference from its exposure-matched mix. Over 1969-08 (006) or 1974-07 (007, 008) to 1982-10 the leg flatters that difference by **+0.63%, +0.57% and +0.77% a year**, against a bound of 0.18%. Monthly correlation with the sector is 0.95–0.96, and the noise ratio is at or just over its 0.32 bound (0.316, 0.334, 0.334). Part of the gap is duration: the sector's average modified duration is 5.1 against about 5.8–6.0 for the 8.5-year bond. A duration match, chosen after these figures were seen and labelled post hoc, roughly halves the bias (+0.28%, +0.37%, +0.59%) but leaves it above the bound. Spread over each study's full window, the measured bias is +0.17%, +0.11% and +0.14% a year, against effects of +0.90%, +0.85% and +0.56%. **Limits:** the sector is a basket of real issues whose maturity drifts within 5–10 years, and it is not the truth either. The matching is off by one trading day. 1983–2002 have no independent series the desk can read. Full output: [`tools/fidelity_stocker.txt`](tools/fidelity_stocker.txt); separate-session recomputation (all 14 figures match): [`tools/fidelity_stocker_recompute.md`](tools/fidelity_stocker_recompute.md); reasoning and caveats: [COLD_READ.md](COLD_READ.md), point 3.

## Previous result: Study 008, bond value tilt by the real yield on the 1974–2018 history

**Question:** on Study 006's frozen synthetic 7–10-year Treasury leg, does the real yield time duration? The real yield is the 10-year yield less trailing 12-month CPI inflation, using only CPI published by each signal date (checked against 1,045 archived ALFRED vintages). The weight in the bond is the real yield's expanding percentile rank, with the rest in bills. Disclosed first: the window had been seen by Studies 006 and 007. An era row from 1986 was registered so that a result living only in the early-1980s real-yield peak could not be called supported.

**Verdict (history, run once on 2026-10-25): not supported.** Gate passed (bias 0.021% a year against 0.18%). Volatility was 7.81% a year, so the test could see an edge of about 1.5% a year. Over 534 months (1974-07 to 2018-12) the primary rule's Sharpe ratio was **0.415**, against 0.382 for holding the bond and 0.381 for the same average exposure held throughout. Newey–West t of the monthly difference: **1.38** (about +0.56% a year), so C1 and C2 fail. Companions: core CPI t 1.78, trailing 120-month rank t 0.91, both not supported. **The era row fails:** from 1986 to 2018 the rule earned −0.06% a year against the exposure-matched mix. A [separate-session recomputation](research/008-bond-value-tilt-long-history/REVIEW.md) confirmed the result with findings and no must-fix. [Note](research/008-bond-value-tilt-long-history/README.md) · [verdict as written by the run](research/008-bond-value-tilt-long-history/results/history/verdict.md) · [pre-registration](research/008-bond-value-tilt-long-history/PREREGISTRATION.md) · [trial log](research/008-bond-value-tilt-long-history/trials.md).

![The tilt's edge over the same-exposure mix was positive in the three decades to 1999 (+0.7% to +2.6% a year) and negative in the 2000s and 2010–18 (−0.5% and −0.9%)](research/008-bond-value-tilt-long-history/charts/history_differential_by_decade.png)

*Descriptive, no decision weight; drawn from the committed monthly returns by [charts/make_charts.py](research/008-bond-value-tilt-long-history/charts/make_charts.py) and through the Tester chart check ([CHART_REVIEW.md](CHART_REVIEW.md), fifth section). The registered era row (1986–2018) is what failed. The 2019–2026 episode is reported in the note only: the pre-registration bars it from any verdict sentence.*

## Results at a glance

Every number is a backtest on historical prices after costs; none is a track record. "Exposure-matched" means the same average exposure to the asset, held throughout: the benchmark that already holds the risk premium. t is Newey–West.

| Study | Rule and sample | Verdict | Headline numbers | Trials (registered / run) |
|---|---|---|---|---|
| [001](research/001-slope-duration-switch/README.md) | IEF when the 10y–3m spread is positive, else BIL; synthetic pre-2002 bond series | **Halted at validation** (2026-10-21); independently reviewed | Synthetic series against IEF, 2016–18: tracking error 1.54% (limit 1.5%), mean gap +0.455% then +0.451% a year (limit ±0.40%). No rule tested | 3 / 0 |
| [002](research/002-slope-duration-switch-r/README.md) | Same rule, series rebuilt to age and earn roll-down | **Halted at validation** (2026-10-22); independently reviewed | Level check passed in both windows; tracking error 2.02% against 1.5% on 2003–15 failed. No rule tested | 3 / 0 |
| [003](research/003-bond-tsmom-ief/README.md) | IEF when its 12-month return beats bills, else BIL; ETF history only | **Not supported** (2026-10-22); independently reviewed | In-sample 2003–18: Sharpe 0.45 against 0.55 for both IEF and the exposure-matched mix, t 0.37. Out-of-sample 2019–26, run once: Sharpe 0.16 against −0.26, on one decision (the exit before 2022); the verdict is fixed in-sample | 3 / 3 |
| [004](research/004-xasset-trend-voltarget/README.md) | Ten ETFs, each held only when its 12-month return beats bills, every position scaled to a 10% volatility target | **Not supported** (2026-10-22); independently reviewed | In-sample 2004–18: Sharpe 0.886 against 0.880 for the same volatility-scaled book held throughout, t 0.65. Out-of-sample, run once: 0.336 against 0.199, on the strength of 2022 alone | 4 / 4 |
| [005](research/005-duration-trend-regime/README.md) | Study 003's trend exit, applied only when the 63-day SPY–IEF correlation is positive | **Refuted in-sample** (2026-10-23); independently reviewed | In-sample 2003–18: conditional edge −0.30% a month (wrong sign), t −2.31; detectable effect 4.4% a year, stated before the result | 3 / 3 |
| [006](research/006-term-spread-switch-long-history/README.md) | Study 001's rule on 1969–2018, Study 002's frozen synthetic leg, gate tied to the monthly decision | **Inconclusive (fragile)** (2026-10-25); separate-session recomputation confirmed | 593 months: Sharpe 0.463 against 0.338 for both comparators, t 2.06 (+0.90% a year), 86% of it by 1985; two registered variants t 1.97 and 1.91 miss the bar of 2; t 1.16 against holding the bond | 3 / 3 |
| [007](research/007-bond-carry-tilt-long-history/README.md) | Weight in the same leg = expanding rank of its carry; 1974–2018 | **Inconclusive (fragile)** (2026-10-25); separate-session recomputation confirmed | 534 months: Sharpe 0.493 against 0.382 and 0.381, t 2.10 (+0.85% a year); companion on 1979–2018 t 1.95 misses; t −0.54 against holding the bond (it earned the higher Sharpe by holding less bond); trend adds nothing | 5 / 5 |
| [008](research/008-bond-value-tilt-long-history/README.md) | Weight in the same leg = expanding rank of its real yield; 1974–2018 | **Not supported** (2026-10-25); separate-session recomputation confirmed | 534 months: Sharpe 0.415 against 0.382 and 0.381, t 1.38 (+0.56% a year); companions t 1.78 and 0.91; era row 1986–2018 fails (−0.06% a year) | 3 / 3 |
| [009](research/009-pooled-forward-duration-timing/PREREGISTRATION.md) | Equal-weight average of the forward differences of Studies 006–008, on data that did not exist when the rules were fixed | **Pre-registered** (2026-10-26); scoring code written and reviewed; low-power check | Scored once after 60 common holding periods (about 2031); detectable edge about 1% to 2.75% a year, so "inconclusive" is the likely outcome whatever the truth | 1 / 0 |
| [010](research/010-factor-momentum-french-us/PREREGISTRATION.md) | Each of four US equity factors (size, value, short- and long-term reversal) held long after a rising year and short after a falling one, against the same average position; French Data Library, 1927–2026 | **Pre-registered** (2026-10-26; design reviewed in a separate session before commit); [data step](research/010-factor-momentum-french-us/results/data_step.md) passed (one download, release 202608, 1927-07 to 2026-08 = 1,190 months, no missing month); code reviewed in a separate session (one must-fix, fixed; re-check pass) and approved; history run next; no return read | Full history (1,190 months) can see a Sharpe of the difference of about 0.29–0.32, the size of edge this programme has measured, only just; 630 of those months are in the source paper's data window, and the rows before and after it are low-power checks | 3 planned / 0 |

**Independent fidelity check of the 006–008 leg (2026-10-26):** fails for 1969–1982. The leg's errors flatter the three rules' differences from their exposure-matched mixes by +0.63%, +0.57% and +0.77% a year in those years, against the gates' 0.18% bound; spread over the full windows that is +0.17%, +0.11% and +0.14% a year. No verdict changes ([`tools/fidelity_stocker.txt`](tools/fidelity_stocker.txt)).

Counted across every trial of the 12-month momentum family the desk has run, Study 003's in-sample DSR falls below its 0.95 criterion (0.930); its verdict is unchanged ([`tools/tsmom_family_dsr.txt`](tools/tsmom_family_dsr.txt)). Studies 007 and 008 decided their deflated-Sharpe criterion (C3) at the programme family count (14 and 17); it passes for rules that fail everything else, so it is descriptive ([METHODS §2.1](METHODS.md#21-trial-ledger-and-the-deflated-sharpe-ratio)).

**Errors found after commit** in the long-history studies, counted by one rule and listed in each note: Study 006, 8 (4 major); Study 007, 11 (4 major); Study 008, 15 (5 major). None changed a verdict or a number in a committed results file. Major means that, uncaught, it could have changed a result, a forward record or a verdict sentence: a forward-record finality gap found in 006 and 007, chart titles that claimed more than the verdict, a robustness companion that could not differ from its rule, a wrong data series ID, a data check that reported itself done without doing it. From Study 009, a separate session reviews each design before the pre-registration is committed.

**Why two studies halted.** Both halts were pre-registered fidelity checks of a synthetic pre-2002 bond series against the ETF it stands in for. Both ran on instrument returns only, before any rule return existed, and both limits were written before the comparison and kept when it failed. Study 001's par bond could not earn roll-down (worth about 0.4% a year on the window). Study 002 fixed the level, but its absolute tracking limit, carried over from a calmer window, failed on 2003–15. The successor design, a gate on the error the series puts into the monthly decision, is what Studies 006–008 used. Details: [001 note](research/001-slope-duration-switch/README.md), [002 note](research/002-slope-duration-switch-r/README.md), METHODS §1.3 and §4a.

**Also published, no decision weight:** [tear-sheets](tearsheets/README.md) for each published window of Studies 003–005; Study 004's [risk report](research/004-xasset-trend-voltarget/risk/README.md) and [multiple-testing report](research/004-xasset-trend-voltarget/multiple/README.md) (Hansen's SPA family-wise p 0.38 in-sample); a [paper dashboard](dashboard/README.md) that counts the forward records of Studies 003–008 by code from their committed `paper-log/` folders (every count is zero until the first record on 2026-10-30).

## What is running

- **Forward records from the 2026-10-30 month end** (first execution date 2026-11-02) for Studies 003–008: decision and shadow records, no orders. Twelve monthly holding periods end on 2027-11-01 at the earliest. None of these could establish skill on its own.
- **Study 003's paper sleeve** (2,250 USD in IEF or BIL) starts only from the first month end after Independent Risk clears it. It is not cleared: it waits on one owner decision (the bar-age rule for daily-bar strategies), then an Independent Risk re-review. The rule's own record at official closes runs from 2026-11-02 either way.
- **Desk view** (weekly, from 2026-10-23): [desk-view/DESK_VIEW.md](desk-view/DESK_VIEW.md) reads the US rates market from public FRED series. It ends in five falsifiable calls logged in [predictions/ledger.csv](predictions/ledger.csv) before the outcome, each with a market-anchored baseline probability. Scoring starts on 2026-10-29, with Brier scores against the baseline in [predictions/SKILL.md](predictions/SKILL.md).

## What Qune is

Qune is an autonomous research-and-venture organisation. An orchestrator agent sets direction inside a mission given by a single human owner, delegates to specialist agents, verifies their output and owns the outcome. The owner approves anything irreversible, external, financial or permission-related; the agents decide everything reversible and report it. Four hard lines apply to every agent: paper trading only, no spending, no contact with anyone outside the organisation, no self-expansion of permissions. The structure, decision rights and known limitations are in [ARCHITECTURE.md](ARCHITECTURE.md).

## What the trading desk does

The desk researches systematic rules and has a $100,000 paper account at a retail broker to trade them on; no order has yet been placed under any study in this repository. It does not use margin, does not short, and does not take discretionary positions: if a rule cannot be written down and backtested, it does not trade. Benchmarks and risk limits are written and dated before any test. Every result is reported with the number of trials it took and the deflated Sharpe ratio; trials are logged before they run. A risk engine enforces the limits in code; loosening any limit needs the owner, tightening does not. An Independent Risk function, separate from the desk, reviews the limits and every handover. The rules are in [RISK_FRAMEWORK.md](RISK_FRAMEWORK.md).

The programme, in order: rates and the yield curve; fixed income and macro; systematic cross-asset signals, all through liquid ETFs. [RESEARCH_AGENDA.md](RESEARCH_AGENDA.md) reviews the published evidence (every DOI checked against Crossref by `tools/check_citations.py`, output committed) and records which question comes next and why. [METHODS.md](METHODS.md) lists the guards against overfitting in the order they act, each with the worked number from these studies, and ends with what the guards do not do.

The desk started with crypto trend rules on 1-hour bars in October 2026, found no edge, and moved to daily rules on liquid US ETFs.

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

## Reproduce

```
git clone <URL of this repository> && cd Qune-research
python3 -m venv .venv && .venv/bin/pip install -r research/003-bond-tsmom-ief/requirements.txt
cd research/003-bond-tsmom-ief && ../../.venv/bin/python -m pytest -q && ../../.venv/bin/python review_recompute.py
```

The third command runs Study 003's tests on constructed data, then recomputes every headline statistic of Study 003 from the committed monthly return files with code written by the independent reviewer, not the author. It does not rebuild those returns from raw data.

For the whole repository: `make venv`, `make test` (every study, the library and the desk view, as CI runs them), `make lint`, `make coverage` (shared library, CI floor 90%), and `make reproduce`. The last runs the reviewers' recomputation scripts for Studies 003–006 from the committed files, then [`tools/effect_lines.py`](tools/effect_lines.py), which recomputes the headline t of Studies 006, 007 and 008 (2.06, 2.10, 1.38) and stops if any differs. Studies 001, 002, 007 and 008's reviewer scripts need the raw vendor files (`make reproduce-raw`). CI runs `make reproduce` on every push; the rows that the 004 and 005 reviews found as last-digit roundings in the notes still show as mismatches, by design, so the log matches the REVIEW.md tables. `make charts`, `make tearsheets` and `make dashboard` redraw every published figure from committed files.

Re-running a backtest itself (`reproduce.sh`) needs the raw vendor files, which are not redistributed: FRED series are public; the ETF series need a data-vendor token and the broker bars need paper-account keys (each study's §5.1 and §13). `--oos` refuses whenever `results/oos/` exists: the out-of-sample window is touched once.

## How to read this repository

Five minutes: this file, then [RISK_FRAMEWORK.md](RISK_FRAMEWORK.md). A quant reader: [METHODS.md](METHODS.md) and [COLD_READ.md](COLD_READ.md) next. Twenty minutes: add [BUILD_LOG.md](BUILD_LOG.md) and the latest study folder. The rest: [ARCHITECTURE.md](ARCHITECTURE.md) for how the organisation is wired.

```
README.md               this file (a summary; history in git and BUILD_LOG)
ARCHITECTURE.md         roles, decision rights, research lifecycle, limitations
BUILD_LOG.md            dated decisions and mistakes, oldest first
RISK_FRAMEWORK.md       the desk's rules and the current paper limits
RISK_PROPOSAL_DURATION_SLEEVES.md  proposed risk spec for monthly duration sleeves (proposal only)
METHODS.md              how the programme guards against overfitting, each guard with the worked number from these studies
RESEARCH_AGENDA.md      literature review with Crossref-checked DOIs; what comes next and why
CHART_REVIEW.md         the Tester's review of every published chart, with dated author's responses
COLD_READ.md            two outside-reader critiques of the whole repository (2026-10-24, 2026-10-26), with dated author's responses
research/NNN-slug/      one study per folder
  PREREGISTRATION.md    question, hypothesis, benchmarks, limits, order of operations, dated; amendments in §16
  trials.md             every trial logged before it runs; data-check log
  APPROVED              the approval record the reproduce script requires
  README.md             the study note: verdict first, what happened in order, what did not work
  REVIEW.md             independent review by a separate agent that did not write the code (once done)
  reproduce.sh          each step of the pre-registered order, gated
  src/, tests/          Python and its unit tests (constructed data only)
  results/              outputs written once and never edited; data_manifest.json with file hashes
  charts/               the same results drawn to the house chart standard (SVG + 2x PNG, manifest with input hashes)
  paper-log/            forward record from 2026-10-30: 003 the paper sleeve (orders only once Independent Risk clears it), 004-008 shadow records with no order
desk-view/              weekly rates-and-macro view from public data; numbers in json, charts by code to the house standard
predictions/            the desk's calls, logged before the outcome (append-only) and scored when due, with a market-anchored baseline beside each
qune_research/          the shared library: calendar, data adapters with hashing, engine, statistics, risk model, multiple-testing inference, house chart style, tear-sheet report, paper dashboard
tearsheets/             post-hoc one-page tear-sheets per published window of Studies 003-005
dashboard/              paper dashboard: the forward records of Studies 003-008, counted and drawn by code
tools/                  scan.sh (leak scan before every commit and push), citation check, power and effect-size scripts with their committed outputs
.github/workflows/      on each push: every test suite, ruff and mypy, library coverage, make reproduce (no data, no secrets)
Makefile                the same steps CI runs, for a reader's machine
LICENSE                 MIT for the code and documents; vendor data excluded; not advice
```

The tests use constructed series only: a passing run says the engines and statistics behave as specified, and nothing about any result. Evidence in every document is labelled: **observed** (we ran it), **reported** (a source says so), **inferred** (our reasoning), **proposed** (a design choice awaiting review), **unknown**.

### Status labels

| Label | Meaning |
|---|---|
| designed | Question, hypothesis, benchmarks and limits written and dated. No data examined for the test. |
| built | Code exists and its tests pass. No result yet. |
| tested | Backtest run once against the pre-declared bar; result published, pass or fail, with trial count and deflated Sharpe. |
| halted at validation | A pre-registered data check failed before any rule was tested; the failure is published in full, no rule result exists, and the study is closed. A successor needs a new pre-registration. |
| paper-trading | Cleared by Independent Risk and running forward on the paper account from the publication date. |

A result is never upgraded to "tested" by re-running with changed parameters; a changed rule is a new trial and a new entry.

## What this repository is not

- Not investment advice, and not a track record. Every figure is a backtest or a paper-account observation.
- Not real money. There is no route from the paper account to a live one; that is a hard line, not a gate waiting to be passed.
- Not a claim of profit. Several results here are failures and are published as such.
- Not a data distribution. Raw vendor data is re-fetched by the scripts and never committed.
