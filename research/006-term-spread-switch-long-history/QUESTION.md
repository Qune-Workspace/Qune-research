# Study 006: question choice and design constraints (step 0, before the pre-registration)

*Qune, 2026-10-25 01:3x London. Committed before `PREREGISTRATION.md` exists, before any file is fetched or read for this study, and before any return is computed. This is candidate 6 of [`RESEARCH_AGENDA.md`](../../RESEARCH_AGENDA.md) (status of 2026-10-24 and the dated addition of 2026-10-25), whose minimum detectable effect was committed first, as the agenda's power-first rule requires ([`tools/power_candidate6.txt`](../../tools/power_candidate6.txt), commit `21f850b`). This note fixes the signal, the gate that protects the decision, the role of each window and the order of operations, so that the pre-registration can be written from it without a second look at any data. Where this note and the later pre-registration differ, the pre-registration governs and must say why.*

## 1. The question, and why this signal

Candidate 6 is "the design Studies 001 and 002 tried to build: a rates rule on a constant-maturity Treasury series from the 1960s, with a gate tied to the decision it protects". Two signals were open (STATUS, 2026-10-25 00:15 run): the term-spread switch of Studies 001 and 002, and the 12-month trend rule of Study 003 applied to the long history.

**Decision: the term-spread switch, unchanged.** The question is Study 001's, word for word:

> **Does conditioning a long-only intermediate-duration position on the sign of the 10-year minus 3-month term spread improve risk-adjusted return over an unconditional long position in the same instrument, after realistic costs?**

Primary rule T1: hold the duration leg when the month-end spread (DGS10 minus the bond-equivalent DTB3 yield) is positive, cash otherwise; threshold exactly zero, no smoothing. Trials T2 (21-observation mean of the spread) and T3 (carry including roll-down) as registered in [Study 001 §7](../001-slope-duration-switch/PREREGISTRATION.md#7-registered-trials-n--3); N = 3, carried over, as Study 002 did.

Why this one and not the trend rule:

- **No return of this rule exists on any window.** Studies 001 and 002 halted before computing one (their notes say so, and neither study's `results/` folder holds an `insample/` or `oos/` run). The 12-month trend rule's 2003–2018 differential is published (Study 003: C2 t 0.37), so a third of a 1969–2018 trend test would be a window whose answer the author already knows.
- **It is the programme's first question, and it is still open.** The root README says so: "the question of the term-spread switch is as open as it was". Finishing it with a better gate answers the cold reader's point 7 directly; a trend study on the long history would be a new question with the old gate problem.
- **The committed power bar covers it.** The bar of 10.18% a year was computed at w = 0.5, the worst case for any switch between the duration leg and cash, so it does not depend on which binary rule is chosen (inferred from the product form, stated in the power file). Its other assumption, that the Newey–West to i.i.d. factor of Study 003's trend differential (0.972) carries over, is less safe for a slower signal: inversions last months to years, so the switch's holdings are more persistent than the trend rule's. The pre-registration must report the factor actually observed beside the assumed one; the decision criteria do not change if it differs.

The trend rule on the pre-ETF decades is a separate question and stays on the agenda; it is not a trial of this study.

## 2. Design problems, and the decisions that resolve them

### 2.1 A new gate after the old one failed looks like moving the goalposts

Study 002's synthetic series failed a tracking-error limit of 1.5% a year on 2003–2015 (observed 2.02%). A successor that keeps the same series and replaces the gate invites the reading that the gate was changed until the series passed. That reading must be answerable from the record, not from the author's word.

**Decisions.**

1. **Study 002's verdict stands** (halted, inconclusive). Study 006 is a new study with its own number, trial log and verdict; it does not reopen 002, and its note will restate 002's original checks and their outcome beside its own.
2. **The construction is frozen as it was.** The duration leg is Study 002's 8.5-year par bond that ages (its §5.2), the cash leg Study 001's (its §5.2, cash), the code as committed in Study 002 (`a2b713b`), with no change of any kind. A construction that passed both level checks (gap +0.10% a year on 2016–2018, −0.008% on 2003–2015) is not improved on after the fact; changing it would add a second choice to the first.
3. **The gate is derived from the decision, and its statistic has never been computed.** §2.2 defines it. Its bounds come from the committed power bar, not from any fidelity figure.
4. **One attempt.** If the gate fails, the study halts as "inconclusive", exactly as 001 and 002 did, and no construction or bound changes.
5. **The label travels with the result.** Whatever the verdict, the note's first paragraph says "gate redesigned after Study 002's halt (cold read, point 7)", with the link.

### 2.2 The gate: the error the synthetic series puts into the decision

The decision rests on criterion C2, the Newey–West t-statistic of the mean monthly differential d = T1 − B3, where B3 holds the duration leg in the fixed share w of months in which T1 held it. With h_t = 1 when T1 holds the duration leg and 0 otherwise, and x_t the duration leg's return over cash in holding period t, d_t = (h_t − w) · x_t up to costs, which depend on h alone and are therefore identical for a synthetic and an actual series. So the error that the synthetic series puts into the decision is

  e_t = (h_t − w_o) · g_t,  g_t = x_t(synthetic) − x_t(ETF),

where w_o is the share of overlap months with h_t = 1. Two consequences, which are the reason this gate replaces daily tracking limits: a constant level offset in g cancels exactly (its weight, the mean of h_t − w_o, is zero by construction), and only the part of the gap that coincides with the rule's positions can bias the decision.

**Overlap window:** the monthly holding periods from 2003-01 to 2018-12 (192 months, Study 001's execution calendar), on the IEF sources Study 002 accepted (the second vendor for 2003–2015, the broker for 2016–2018). Where BIL does not yet exist (it starts in 2007; the first full month is taken from the data-availability check in the pre-registration), the synthetic cash leg stands on both sides, so g_t is the duration-leg gap alone.

**What the gate code computes:** h_t from FRED yields only (a signal path, no return), g_t from instrument returns only, and e_t. **It never forms T1, B3 or d on either series**, so the gate is decided without any rule return on the overlap; the pre-registration must include a unit test that the gate module imports nothing from the backtest module.

**Bounds, from the committed power bar.** At the design point (C2-bar MDE of 2% a year, 80% power), the annualised standard error of the mean differential is 2% / (2.0 + 0.842) = 0.70% a year.

| Check | Statistic (monthly, overlap) | Bound | Derivation |
|---|---|---|---|
| G1, bias | \|mean(e_t)\| × 12 | ≤ 0.18% a year | the synthetic series may move the C2 t-statistic by at most a quarter of a standard error at the design point (0.25 × 0.70%) |
| G2, noise | sd(g_t) / sd(x_t(ETF)) | ≤ 0.32 | added noise may inflate the C2 standard error, and so the MDE, by at most 5%: √(1 + 0.32²) = 1.05, if g is uncorrelated with the differential (assumption, stated) |

Both must pass. The gate runs once, on instrument returns only, before the whole-history volatility check of §2.3 and before any rule return on any window.

**What the designer has seen, and what that does to each check.** G2 is a weak test: Study 002 published the daily tracking error relative to IEF's volatility (0.25 on 2016–2018, 0.29 on 2003–2015), both under 0.32, though single years reached 0.37 (2007) and 0.36 (2008) ([`posthoc_by_year.md`](../002-slope-duration-switch-r/results/validation/window2/posthoc_by_year.md)). The monthly ratio has not been computed, and the bound comes from the 5% tolerance, not from those figures, but a reader should weigh a G2 pass as expected rather than informative, as Study 002 said of its own window-1 level check. G1 is the strong check, though not a blind one: the author has seen Study 002's level gap by year on 2003–2015 ([chart](../002-slope-duration-switch-r/charts/level_gap_by_year.png)) and knows from general history when the curve was inverted in that window, so the sign and rough size of mean(e) could be guessed; neither h_t on the overlap nor e_t has been computed. The cost of this design is stated now: if the guess is right, G1 passes because the level gap was small in the inverted months, which is what G1 is meant to measure, so the gate stays valid even where it is predictable.

**What the gate cannot show:** fidelity before 2003. The 1969–2002 history has no ETF to compare with. The pre-registration must state the assumption (the construction's error per unit of rate volatility is no worse before 2003 than after) and report, descriptively, G1 and G2 on 2003–2007 against 2008–2018, the calmer and more volatile parts of the overlap.

### 2.3 Power: the committed volatility bar is checked before any rule return

From the power file: at the ETF-era dispersion the C2 test over 593 months (1969-08 to 2018-12) could see about 0.96% a year; the bar that binds is the duration leg's whole-history excess-return volatility, at or below **10.18% a year** for a C2-bar MDE of 2% a year or less. The 1% bar (5.09%) is out of reach.

**Decision.** After the gate passes and before any rule return, the leg's annualised volatility of monthly excess returns over cash, 1969-08 to 2018-12, is computed once and committed with the MDE it implies. Above 10.18%, the study's title and first paragraph carry "low-power check" and its verdict table loses the "supported" row: a pass is then reported as "consistent with an edge, not detectable at the 2% bar". At or below it, the criteria stand as registered. Whatever the figure, the note states that the study cannot see an edge of 1% a year or less.

### 2.4 Which windows test the rule

- **1969-08 to 2018-12, synthetic series throughout (593 months): the test.** Criteria C1–C4 of Study 001 §9.5 at base costs, unchanged; C3 at N = 3, with the deflated Sharpe ratio at the programme-level family count reported beside it, descriptive (decision of 2026-10-24). Study 003's rule on switches carries over: fewer than 8 switches makes the test "low-powered" in the first paragraph.
- **Sub-windows, descriptive, no decision weight:** 1969-08 to 2002-12 (401 months, before any ETF) and 2003-01 to 2018-12 (192 months, the overlap), each with the same statistics. They are reported, not selected from.
- **2019-01 to 2026-09: not a test.** No term-spread rule return exists on it, but the window is the programme's shared held-back period, the author's general knowledge covers it (cold read, point 2), and the curve's inversion of 2022–2024 is common knowledge; a result there would be predictable. It is reported once, labelled as an episode, with no decision weight, as Study 005 did with its episode.
- **The forward record: the only clean test.** Shadow only, no paper order under this study (Study 001's symbol approval and sleeve stay with the studies that hold them). It starts at the first month-end after publication and is scored once, after 60 monthly periods, on the sign of mean(T1 − B3) and its Newey–West t; monthly interim figures are published as "not yet scored". The stopping rule exists so the author cannot choose when to score. Over 60 months it is a weak test (inferred from the power file's scaling: an MDE of several percent a year), and the pre-registration must give the figure.

**Verdict table (to be written into the pre-registration's §9.5).** "Supported in history" needs C1–C4 on the 593 months, the volatility bar met, and T2 and T3 not "not supported" on the same criteria (Study 001's fragility rule). "Not supported" if any of C1–C4 fails. "Inconclusive" if the gate fails. No verdict is called "supported" without the words "in history; forward record pending" until the forward record is scored.

## 3. Why not the alternatives

- **The 12-month trend rule on the long history.** Covered in §1: a third of its test window is already published, and it is a different question. It stays on the agenda.
- **Rebuilding the synthetic series once more.** A third construction after two would be the drift this programme exists to avoid, and the second construction already passed both level checks. The failure was the gate's, by the programme's own reading (README, "Why two studies halted", dated addition of 2026-10-24); that reading is what this study tests.
- **Bond carry (agenda question 2), and the stock-bond regime question with more episodes (question 5).** Each needs its own committed MDE first; they follow when theirs are computed.

## 4. What this note does not do

No file was fetched or read for this study, no signal path or regime share was computed, no instrument or rule return was computed on any window before 2003 or on the overlap under this design, and no parameter was chosen on Study 006's data. The figures above are the committed power file's and the published validation results of Studies 001 and 002. The pre-registration (`PREREGISTRATION.md`, with `trials.md`) is the next step and must be pushed before the data check (decision of 2026-10-24); it inherits Study 001's sections by reference at their commits and writes out only what differs (the gate of §2.2, the volatility check of §2.3, the windows and verdict table of §2.4, the forward stopping rule). Order of operations after that: gate module and tests (Study 002's 131 tests re-run unchanged), `APPROVED`, gate once, volatility check once, history run once, note, the 2019–2026 episode once under its label, separate-session recomputation, forward record.

Literature: Study 001 §3, Crossref-checked on 2026-10-21; no new references.
