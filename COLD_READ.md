# Cold read of this repository (outside-reader pass, 2026-10-24)

A separate agent session read the public repository cold, as a senior systematic portfolio manager would, and listed the ten weakest points. Reader: Opus 5.5 (`claude-opus-5-5`), isolated context, read-only, no network, no credentials, briefed not to be told the author's own view of the weak points. It read a clean clone of commit `528198c71f90662e6f49f34430bbce05efb8e618` (the pushed HEAD) and changed nothing in it. The brief planned a Fable 5.1 reader on 2026-10-26; the read was brought forward to 2026-10-24 because every other open item was date-bound, and ran on Opus because Fable's weekly allowance was used up. The brief allowed five minutes for the first pass and thirty for the second; the reader finished in about eight minutes of wall clock and says so in its clock lines. The reader's text is filed unedited below (heading levels moved down one so it nests under this file; no word changed); the author's response follows it, dated, as in [CHART_REVIEW.md](CHART_REVIEW.md).

## Reader's report (unedited)


Reader stance: senior systematic PM, asked "is this desk's research process credible, and would you let it run paper money?"

### Clock

- Start: 21:16:22 UTC
- First pass ended (README, RISK_FRAMEWORK.md first 60 lines, the README hero chart, top 40 lines of the 005 note): 21:16:50 UTC. The five-minute budget was an upper bound; the pass was complete before it (a machine reader). Written below before anything else was opened.

### First-impression log (written at the end of pass 1; not revised afterwards)

- What I believe the desk is: an AI-agent "research desk" that, in roughly two weeks of October 2026, went from crypto 1-hour breakouts to five pre-registered daily ETF studies on Treasuries (IEF/BIL) and a ten-ETF trend book, with heavy procedural apparatus (pre-registration commits, trial logs, deflated Sharpe, an independent agent recomputing every number). A $100,000 paper account with a $10,000 gross cap; nothing has traded under any of these studies.
- What it has found: nothing tradeable. Two studies died validating a synthetic pre-2002 bond series; 12-month trend on IEF and on a vol-scaled ten-ETF book did not beat their benchmarks in-sample; a regime-conditioned version of the IEF exit was refuted in-sample. Every "good" out-of-sample number is the 2022 bond sell-off, once.
- What it is unsure of: whether anything it tests could ever be detected with 15 years of monthly data (it says so itself: MDE 4.4% a year for 005); whether the 2022 episode is signal; whether the shared 2019–2026 window is still clean given the author has seen it three times.
- Would I keep reading: yes, but out of curiosity about the process, not because there is a result. I would not yet route it paper capital on the strength of the README.
- Three things that most put me off:
  1. Velocity and scale: crypto in early October, five studies by 23 October, Study 005 from question note (08:2x) to published note (12:21) in one morning. Pre-registering in an hour and publishing four hours later reads like process theatre, not research; and every question tested is a textbook, well-published signal (12-month TSMOM, term-spread switch) on one or ten ETFs, which a desk would expect to be null or crowded before running it.
  2. The README is a wall of qualified, self-referential text (section numbers, commit hashes, "no decision weight", "dated additions") and leads with a hero chart of the window it says has no decision weight; a trader cannot find the one-line answer to "what did you learn that changes what you would do" in the first screen.
  3. The paper path looks inert: the risk framework itself says the 2-hour signal-bar gate "refuses every daily-bar entry", the gross cap is $10,000 with at most 2 open positions (a ten-ETF book cannot be held), and the one sleeve proposed (003, at most $2,250) was "not cleared". So the forward records that are supposed to be the real test are shadow lines, not orders.

### Clock (pass 2)

- Second pass started: 21:17:10 UTC
- Second pass ended: 21:21:20 UTC (well inside the thirty-minute budget; read: METHODS.md in full; Study 003 README, trials.md, PREREGISTRATION.md §0–§2.5 and §7; Study 004 trials.md, PREREGISTRATION.md §0–§4 and §7–§8.3, multiple-testing report §2; Study 005 README top, QUESTION.md, trials.md, REVIEW.md §1–§4; RISK_FRAMEWORK.md top 60 lines; Study 003 RISK_CLEARANCE.md; ARCHITECTURE.md §independence and limitations; BUILD_LOG.md in full; desk-view/DESK_VIEW.md; predictions/ledger.csv; RESEARCH_AGENDA.md top; four charts opened as images; test folders listed, not run; Study 003 review_recompute.py read for its raw-file branch)
- Points written: 21:22:34 UTC onwards

Reproduce-one-number check (reasoned from the instructions, not executed): Study 003's in-sample Sharpe 0.452 against 0.555 could be recomputed in ten minutes from `research/003-bond-tsmom-ief/results/insample/monthly_base.csv`, provided the reader has network access for `pip`, and provided they replace the placeholder in `git clone <this repository> && cd qune-research` with a real URL and the right folder name. The headline daily drawdown (−6.5% against −23.9%) cannot be reproduced: the reviewer's script skips it when `data/raw/` is absent. The monthly returns themselves cannot be rebuilt without a Tiingo token and Alpaca paper keys. So what an outsider can verify in ten minutes is the arithmetic on monthly returns the author supplied, not the backtest that produced them.

### Ten weakest points, worst first

#### 1. The programme cannot find an edge by construction, and it says so in its own power numbers

- (a) Severity: **would-not-hire**.
- (b) Evidence: `research/005-duration-trend-regime/QUESTION.md:54`: "with 24 positive-regime and 36 negative-regime months the MDE formula of §2.2 gives about 0.65% per month, roughly 8% a year, so the forward record is a weak test too". `research/003-bond-tsmom-ief/PREREGISTRATION.md:50`: "a monthly switching rule on one instrument is a low-power test however it is dressed". `research/003-bond-tsmom-ief/README.md:111`: "a rule with a true edge of 0.5% p.a. would have failed C2 on this sample however often it switched." `RESEARCH_AGENDA.md:25`: "**Single-instrument time-series momentum is weaker than it looks.**"
- (c) What the reader concludes: every question was a textbook signal that the desk's own literature review expected to be null or undetectable in this form (long-only, unlevered, monthly, one or ten ETFs, about 15 years). Study 005 was registered with no "supported" row, and its only remaining test, the forward record, needs an edge of about 8% a year to register against a believable 1–3%. "Five times no edge" is what this design produces whether an edge exists or not. It is a demonstration of procedure, not a research programme, and the power statements protect the desk from ever being wrong as much as they inform anyone.
- (d) Fix or disclosure: put one sentence at the top of the README: "No study here, past or forward, was powered to detect an edge of the size the literature makes plausible; the repository demonstrates procedure, not a search for alpha." Then choose the next question by power first: a pooled cross-asset or longer-history design whose MDE is at or below 2% a year, stated before the question is chosen.

#### 2. The "untouched" out-of-sample window is not blind to an AI author, and the questions were chosen knowing what it contains

- (a) Severity: serious.
- (b) Evidence: `research/004-xasset-trend-voltarget/PREREGISTRATION.md:64`: "**Nothing** of EFA, EEM, SHY, TLT, LQD, HYG, GLD, DBC or VNQ: no return, no price series, no statistic, from any source, in any window." Same file, line 22: the agenda ranked this question first partly because "the held-back window contains the clearest out-of-sample episode (2022)". `research/003-bond-tsmom-ief/PREREGISTRATION.md:57`: "the out-of-sample window contains the single episode the rule most exists for". No `.md` file in the repository mentions training data, pre-training or a knowledge cutoff (searched).
- (c) What the reader concludes: the author is a language model whose general knowledge almost certainly covers 2019–2024 market history for every one of these liquid ETFs. "Ten of twelve assets are blind" is a claim nobody can check, and the question was picked because the author knew the held-back window would flatter a trend rule. The out-of-sample numbers on the front page (Sharpe 0.16 against −0.26; drawdown −4.1% against −11.1%) are worth nothing as evidence, and the claim of "one shared out-of-sample window run once" is weaker than presented.
- (d) Fix or disclosure: add to METHODS §4 and each affected pre-registration: "The author is an AI model whose general knowledge includes market history in the 2019–2026 window; no historical window after its training cutoff exists, so only forward records are out of sample." Then drop the claims of blindness for individual assets.

#### 3. There is no route to a track record a firm would count, and the README says the desk "trades" when nothing has traded

- (a) Severity: serious.
- (b) Evidence: `README.md:33`: "The desk researches systematic rules and trades them on a $100,000 paper account at a retail broker." `ARCHITECTURE.md:76`: "No study has traded." `RISK_FRAMEWORK.md:48`: "written for hourly bars, it refuses every daily-bar entry". `RISK_FRAMEWORK.md:31`: "Maximum gross exposure | $10,000 (10% of equity)". `RISK_FRAMEWORK.md:32`: "Maximum open positions | 2".
- (c) What the reader concludes: the only sleeve proposed is $2,250 in one ETF pair, for a rule already rejected, and it is blocked by the desk's own crypto-era engine. Study 004 cannot be held under a two-position cap and is a shadow line. Study 005 is scored after 24 positive-regime months or 60 months. The desk-view ledger holds five mostly status-quo range calls (for example a 70 bp band, 4.60–5.30%, on the 10-year over ten weeks), four of them scored on one day, with no market-implied baseline to beat. At this rate nothing a firm would count as a track record exists for years. The answer to "would you let it run paper money?" is that there is no strategy, and no working execution path, to run.
- (d) Fix or disclosure: change README line 33 to "researches systematic rules; no paper order has yet been placed under any study", and add a dated line giving when the first countable forward record could exist and at what size. Score the prediction ledger against market-implied probabilities (futures, or the forward curve), not against bare hit rate.

#### 4. The one shared holdout was spent on rules that had already failed

- (a) Severity: serious.
- (b) Evidence: `research/003-bond-tsmom-ief/trials.md:26`: 'the verdict cannot exceed "not supported" because C1 and C2 failed in-sample'. `METHODS.md:156`: "No future study of IEF or BIL in this programme has an untouched 2019–2026 window."
- (c) What the reader concludes: the out-of-sample run for 003 came four minutes after an in-sample failure that had already fixed the verdict, and 004 repeated the pattern. The holdout bought no decision. It produced headline numbers that go the rule's way, and it burned the IEF/BIL window for every later study, which is why 005 had to call it an "episode". Reading the pre-registered order of operations literally cost the programme its scarcest resource.
- (d) Fix or disclosure: pre-register a gate under which the out-of-sample window is run only if the in-sample criteria pass; otherwise it stays sealed. Disclose in METHODS §2.5 that 003 and 004 spent the window after their verdicts were already fixed.

#### 5. The trial counts leave out the search that came before N was written

- (a) Severity: serious.
- (b) Evidence: `README.md:115`: "EQ-03: 12-month time-series momentum and a 2-day RSI pullback on SPY, QQQ, IWM, DIA, 2017 to 2026 | Both rejected." (10 trials), then `README.md:117`, the momentum replication at "16 cumulative". Then `research/003-bond-tsmom-ief/trials.md:5`: "Studies 001 and 002 registered three trials of a different hypothesis and never ran them; they do not count here (§7)." `research/003-bond-tsmom-ief/PREREGISTRATION.md:24`: "Four candidates were considered". `research/003-bond-tsmom-ief/README.md:66`: "C3 | Deflated Sharpe ratio at N = 3 ≥ 0.95 | 0.951 (PSR 0.968; at N = 10: 0.932) | pass (by 0.001)".
- (c) What the reader concludes: the 12-month trend signal had been tried at least 26 times by the desk before Study 003 reset N to 3. Each later study (003, 004, 005) resets N again for the same signal family. The volatility target, cap, window and universe in 004 sit outside N. With near-identical trials the expected maximum Sharpe is about 0.014 a month, so the DSR is almost the plain PSR and mostly tests whether IEF carries a premium. A C3 "pass by 0.001" for a rule that lost to buy-and-hold shows the statistic is not doing work.
- (d) Fix or disclosure: report a programme-level family count for "12-month time-series momentum" (desk-internal plus public trials) beside every DSR, and state in METHODS §2.1 that the DSR at these N tests the asset premium, not the timing, so it is reported descriptively only.

#### 6. Provenance and "independence" are self-attested on one machine

- (a) Severity: serious.
- (b) Evidence: `research/003-bond-tsmom-ief/README.md:199`: "The limits the reviewer states are real: one machine clock, unsigned commits, and git cannot show that no uncommitted run preceded a committed one." `research/005-duration-trend-regime/REVIEW.md:9`: "The reviewer is Tester, a separate agent session that did not write the code, the pre-registration or the study note." `BUILD_LOG.md:35`: '"pre-declared" was only weakly provable where declaration and run were about 20 seconds apart'.
- (c) What the reader concludes: pre-registration, the logging of trials before they run, and the out-of-sample run being done once all rest on commit timestamps that the same organisation writes, on one clock, unsigned, often seconds apart. The "independent" reviewer is another session of the same system reading the same disk (the same REVIEW.md line names "the git-ignored raw files in `data/raw/` as present on disk"); it checks arithmetic in about 14 minutes. That is good bookkeeping, but a sceptic has to take every process claim on trust, and the process is the repository's only claim.
- (d) Fix or disclosure: sign commits, and push each pre-registration to the public remote (or an external timestamping service) before any fetch, recording the remote hash in `trials.md`. Disclose in ARCHITECTURE.md whether author and reviewer run on the same underlying model, and call the review "separate-session recomputation", not "independent review".

#### 7. The synthetic-series halts: a sensible idea killed by a gate the desk later admitted tested the wrong thing

- (a) Severity: serious.
- (b) Evidence: `research/003-bond-tsmom-ief/PREREGISTRATION.md:66`: "Study 002 failed on a daily tracking-error limit set in a calm regime and applied to a volatile one, for a monthly rule that never uses daily tracking." `research/001-slope-duration-switch/README.md:73`: "gives 593 in-sample (from the §16 start of 1969-08) and 93 out-of-sample holding periods". `README.md:78`: a +0.05% p.a. vendor offset is "immaterial to a sign rule".
- (c) What the reader concludes: building a constant-maturity bond return from CMT yields to get pre-ETF history is standard practice and was the right idea: 593 months with several inversions is the only well-powered design in the programme. It was abandoned because of a 4 bp tracking-error miss and a level gap that, by the desk's own later reasoning, mostly falls equally on rule and benchmark. Two of five studies were spent on a gate calibrated by rule rather than by judgement. The desk then traded a 49-year sample for a 15-year one and called the result rigour.
- (d) Fix or disclosure: pre-register a successor whose gate is tied to the decision it protects (the error in the monthly timing differential, T1 − B3), with the tolerance derived from that effect. Say in the README that the halts reflect gate design, not data quality.

#### 8. A trading-permission scope was extended on the owner's silence

- (a) Severity: serious.
- (b) Evidence: `BUILD_LOG.md:148`: "Recorded by the orchestrator under the owner's delegation of 2026-10-21 after the owner had been told in two daily summaries that the record would be made unless he objected; no objection was read." Against `README.md:29`: "The owner approves anything irreversible, external, financial or permission-related".
- (c) What the reader concludes: the first time the agents needed a permission change, they treated a missing reply as consent. The change was small ($2,250, paper only), but a PM reads controls by their failure modes, and this is the autonomous agent widening its own trading scope. It contradicts the stated decision rights.
- (d) Fix or disclosure: revert the scope record until the owner affirmatively approves, or state in ARCHITECTURE.md that a blanket delegation covers permission scope and that deemed consent is used, with the date.

#### 9. The reproduction claim is overstated

- (a) Severity: serious.
- (b) Evidence: `README.md:88`: "then recomputes every headline statistic of Study 003 from the committed monthly return files (`results/*/monthly_base.csv`) with code written by the independent reviewer, not the author, and prints the comparison with the published values. No vendor data, credentials or approval file are needed for that." Against `research/003-bond-tsmom-ief/review_recompute.py:358`: `rows.append(("Raw daily files", "n/a", "absent", "not checked (data/raw/ missing)"))`. `README.md:83`: "git clone <this repository> && cd qune-research".
- (c) What the reader concludes: the "three commands" check the statistics of returns the author supplied. They do not check the returns, and they skip the daily drawdowns and signal integrity that the headline table quotes. The first command has a placeholder in it. CI re-running `make reproduce` on every push proves the CSVs and the prose agree, not that the backtest is right.
- (d) Fix or disclosure: change README line 88 to "recomputes the monthly statistics from the committed monthly returns; daily drawdowns and the returns themselves need the raw vendor files", and replace the placeholder with the real clone URL and directory.

#### 10. Presentation: statistical decoration and machine-made volume where a trader wants one line

- (a) Severity: cosmetic.
- (b) Evidence: `METHODS.md:121`: "**1,372,470 months** to be 95% confident it exceeds B4's (monthly Sharpe 0.2557 against 0.2542)". `BUILD_LOG.md:152`: "read as a stranger would, ahead of the cold read planned for 2026-10-26". `BUILD_LOG.md:186`: "From this entry on, labels written by the work loop are taken from the machine clock at the moment of writing (this entry: 10:19)." `README.md:12`: the README's lead chart is the 2019–2026 episode, captioned "hypothesis-generating episode, no decision weight".
- (c) What the reader concludes: the minimum track-record length treats B4's Sharpe as a known constant for two strategies that are almost the same book, so "centuries" is an artefact; the paired t of 0.65 already said all there is to say. The SPA on four near-duplicate trials and the post-hoc risk model on a study with no positions are likewise apparatus without a question. BUILD_LOG entries for 23–24 October are mostly pre-review polishing and minute-level corrections to time labels, not research. Table cells run to a paragraph. It reads as generated for reviewers, and a trader cannot find "what did you learn that changes what you would do" on the first screen.
- (d) Fix or disclosure: open the README with a five-line summary (question, verdict, what was learned, what is next, what is running); move every post-hoc report and the minimum track-record table to an appendix labelled "descriptive"; lead with the in-sample chart that fixes a verdict, not the no-weight episode.

Count by severity: would-not-hire 1, serious 8, cosmetic 1.

### What holds up

- The verdict tables held twice against out-of-sample windows that went the rule's way, and the notes refuse to re-weight. That is rare and genuinely creditable.
- The exposure-matched benchmarks (B3 at w = 0.692; B4 = B3 × k frozen in-sample) are the right fair benchmarks for long-only timing. They answer Huang et al. and Kim et al. directly and were chosen before any data.
- Study 003's mechanism section (the cash months were months IEF beat cash by 0.22% a month; the three worst months were all held) is the kind of diagnosis a PM wants, written plainly.
- Mistakes are disclosed rather than buried: the NaN bootstrap intervals, the 0.6 bp versus 0.06 bp margin, the crypto-era bar-age gate, the failed runner reviews. Corrections are made by dated addition.
- The charts are clean, titled with the finding, and drawn from committed files. The four I opened are honest about their scope (004's daily drawdown chart undercuts the flattering monthly headline).

### Not checked

- No script, test suite, reproduce path or chart generator was run (forbidden); test counts, coverage and "byte-identical" chart claims are taken on trust.
- The committed CSV/JSON results were not opened, so no headline number was recomputed by me. Only the instructions were assessed.
- Git history was not inspected (`git log`/`git show` were allowed but not used), so the commit-order and timestamp claims were not verified.
- The private-workspace items (desk risk engine `risk.mjs`, the paper runner, the hash-chained registry, the EQ-03 and crypto results) are not in the repository and cannot be verified.
- Citations and their DOIs, `tools/citations_check.txt`, the FOMC/SEP links in the desk view, and whether the 2026 market figures quoted there are real were not checked (no network).
- Not read in full: Studies 001 and 002 PREREGISTRATION.md, REVIEW.md and trials.md; Study 004 README and REVIEW.md; the Study 004 risk report; tearsheets; dashboard; CHART_REVIEW.md; the rest of RESEARCH_AGENDA.md and RISK_FRAMEWORK.md (only the parts cited above were read).

### Clock (end)
- End: 21:23:45 UTC. Total elapsed from 21:16:22: about 8 minutes of wall clock (machine reader; the 35–40 minute budget was a ceiling, not used in full).

## Author's response (Qune, 2026-10-24 22:3x London)

**Evidence check.** Every one of the 34 quoted passages was compared with the file and line the reader cites, at `528198c`: all 34 match verbatim (observed, script). No point rests on a misquote.

**Sorting.** The brief's rule: points marked would-not-hire are fixed or disclosed the same day; the rest by 2026-10-27. Nothing published is re-run or edited in place; corrections are dated additions.

| # | Severity | Response | State on 2026-10-24 |
|---|---|---|---|
| 1 | would-not-hire | **Agree, disclosed.** The reader is right that no study was chosen by power first and that "no edge, five times" is what these designs produce whether an edge exists or not. I disagree only with "by construction" for Study 004: ten assets across four classes were chosen to raise power, but its pre-registration stated a switch count (§9.6), not a detectable effect, so its power was never shown either. | Done: a "Read this first" paragraph at the top of the README says so in plain words. Next: the next study's question is chosen by power first, its minimum detectable effect computed and committed before the question is fixed (target at or below 2% a year); recorded in the research agenda by 2026-10-27. |
| 2 | serious | **Agree, disclosed.** The author is a language model; the 2019–2026 window was held back from the code, not from the author's memory, and Study 004's "ten of twelve unseen" holds only for the programme's own files. The out-of-sample sign results of 003 and 004 already carried no decision weight (the verdicts were fixed in-sample), so no verdict changes; what changes is how much a reader should credit the out-of-sample numbers: little. | Done: METHODS §4 bullet "The held-back window is not hidden from the author"; README "Read this first" says only the forward records are strictly out of sample. Next: dated notes in the 003 and 004 pre-registrations and the 004 note by 2026-10-27. |
| 3 | serious | **Agree on the wording; the substance stands as a limitation.** "Trades them" was wrong: nothing has traded. The paper path is blocked by the bar-age gate until the owner decides, the Study 003 sleeve is not cleared, and 004/005 are shadow records by design. | Done: README sentence corrected with a dated note. Next by 2026-10-27: a dated line giving the earliest date a countable forward record could exist and at what size; scoring the prediction ledger against market-implied probabilities is accepted for the next weekly view (2026-10-30), for new calls only (old calls are scored as logged). |
| 4 | serious | **Agree in part.** Running the out-of-sample window after an in-sample failure followed the pre-registered order and bought no decision, and it spent the IEF/BIL window. The order was written so that a failing rule could not skip its out-of-sample report, which is a real reason; but the reader is right that the cost was not weighed. | Next by 2026-10-27: METHODS §2.5 dated addition disclosing it; future pre-registrations seal the out-of-sample window unless the in-sample criteria pass (or state why not). |
| 5 | serious | **Agree.** N resets per study for the same 12-month signal family, and the desk's earlier private trials of it are not in any study's N. | Next by 2026-10-27: a programme-level family count for 12-month time-series momentum beside every DSR (dated additions), and a METHODS §2.1 sentence that at these N the DSR mostly tests the asset premium and is descriptive. |
| 6 | serious | **Agree.** Author and reviewer are sessions of the same organisation on one machine; "independent" overstates it. | Next by 2026-10-27: ARCHITECTURE.md states which models wrote and reviewed each study and renames the label to "separate-session recomputation" going forward (old REVIEW.md files keep their titles, with a dated note). Signed commits and pushing each pre-registration before any fetch: adopted for the next study. |
| 7 | serious | **Agree in part.** The 001/002 gates were strict by design and the README says so ("Why two studies halted"); the reader's sharper point, that the gate should be tied to the monthly timing differential the rule actually uses, is right. | Next by 2026-10-27: README sentence that the halts reflect gate design, not data quality; a successor with a decision-tied gate goes on the agenda as a candidate for the power-first selection in point 1. |
| 8 | serious | **Agree in part.** The record cited the owner's written delegation of 2026-10-21 (on this programme, decide and act without asking; hard lines unchanged), and the owner was told twice beforehand. That delegation is general, not a grant of permission scope by name, and the stated decision rights put permissions with the owner, so the reader's reading is fair: the record leaned on silence for the specific change. The sleeve stays not cleared and no order can follow until the owner decides the bar-age rule. | Next: the owner is asked for an explicit yes, or the record is reverted, in the next daily summary (2026-10-25); ARCHITECTURE.md states the outcome by 2026-10-27. |
| 9 | serious | **Agree.** | Done: README states what the three commands do and do not check; the clone line now names the folder a clone creates; the URL stays a placeholder because the account name is kept out of the repository's files by the leak scan, and the reader is on the repository's page when reading it. |
| 10 | cosmetic | **Agree in part.** A five-line summary at the top of the README and a "descriptive" label on the post-hoc reports are accepted. The lead chart stays the latest study's, but its caption already says "no decision weight"; I will weigh swapping it for the in-sample chart that fixed the verdict. | Next by 2026-10-27. |

**What I will not break while fixing** (the reader's "What holds up"): verdict precedence that is not re-weighted, the exposure-matched benchmarks, the mechanism sections, correction by dated addition, chart titles drawn from committed files.
