# Study 009: pooled forward check of the long-history duration-timing rules (low-power check)

Pre-registration, written 2026-10-26 before any forward record of Studies 006, 007 or 008 exists (the first signal date is 2026-10-30; the first holding period ends about 2026-12-01). Answers the [second cold read](../../COLD_READ.md#second-cold-read-2026-10-26), point 2: "pre-register, before 2026-10-30, a single pooled forward test ... with its combined MDE stated, or stop calling the forward records the test". The decision and its reasons are in [RESEARCH_AGENDA.md](../../RESEARCH_AGENDA.md) (dated addition of 2026-10-26, point 2); the agenda entry stands in for a question note.

## 1. Question

Studies 006, 007 and 008 found, on one synthetic 7–10-year Treasury leg over 1969/1974–2018, edges over their exposure-matched mixes of +0.90%, +0.85% and +0.56% a year; their equal-weight average was +0.70% a year, most of it before 1986 ([`tools/effect_lines.txt`](../../tools/effect_lines.txt)). That sample is spent. **Does the equal-weight average of the three rules' forward differences, on data that did not exist when the rules were fixed, beat zero?**

## 2. What is tested

- **Inputs.** Only the three studies' own forward files: `research/00{6,7,8}-*/paper-log/shadow.csv`, column `d` = T1 − B3 (each study's primary rule against its frozen exposure-matched mix, IEF and BIL, base costs), with `signal_date`, `execution_date` and `period_end`. This study fetches nothing, computes no signal, and writes nothing of its own before scoring except the scoring-date row in `trials.md` (§3). Nothing in Studies 006–008 changes.
- **Pooled series.** P_t = mean of the members' d_t for each holding period that has a row in every member's `shadow.csv` with the **same `signal_date`, `execution_date` and `period_end`**. Any other period is left out of P and listed with the reason; it is never filled. This matters because the members' codes write no row for a `signal unavailable` month and let the next row span two months, and a slipped execution date moves `execution_date` and `period_end` in one member only: keying on one date would pair holding periods of different lengths (found by the design review, [DESIGN_REVIEW.md](DESIGN_REVIEW.md), finding 1).
- **Members.** 006, 007 and 008. **One mechanical exclusion, fixed now:** a member whose own forward verdict for the block is "not testable" (Study 006 §11.4 and Study 007 §11.4: its T1 made no timing decision in the 60 periods, so its d is an exposure bet) is dropped from P for that block, and P is recomputed from the rest. The exclusion depends only on the member's holdings or weights, never on any return. In practice it can bite only Study 006: the rank weights of 007 and 008 move every month, so their weight's standard deviation is never zero. On the latest desk view the curve is upright ([desk-view/DESK_VIEW.md](../../desk-view/DESK_VIEW.md): 10-year 5.13%, 3-month bill 4.25%), so Study 006's T1 holds IEF while that lasts; if it does so at all 60 signal dates, P is the average of 007 and 008.
- **Not pooled.** Study 003: it is not one of the three long-history rules of §1 (12-month trend on IEF, verdict "not supported"), it writes no `shadow.csv` (its `paper-log/` holds a runner log, `runs.jsonl`, for a paper-order sleeve still awaiting Independent Risk clearance), and its record is scored under its own §11.5. `tools/power_pooled.py` computed two pools that include it (60-month MDE 1.15% and 1.27% a year at ETF-era dispersion); they were set aside on these grounds before any forward data exist. Study 004 (a twelve-ETF book against its own benchmark) and Study 005 (a regime-conditioned difference scored after 24 positive-regime months) score different objects. Their records continue under their own pre-registrations.

## 3. Scoring and verdict

Scored **once**, on the periods of P (§2) whose signal dates fall inside every remaining member's first 60-period block, so n ≤ 60 and n is reported; scoring follows the last member's block-1 scoring date, and P's scoring date is written in this folder's `trials.md` before any statistic of P is computed. This study computes and publishes no interim value of P; the members' own interim figures appear under their "Not yet scored" headings as their pre-registrations require, and anyone can average them, so the scoring rule, not secrecy, is what protects the block. Statistic: Newey–West t (Bartlett, 6 lags, as every C2 in the programme) of mean(P).

| Row | Condition |
|---|---|
| **Supported (pooled forward)** | mean(P) > 0 and t ≥ 2.0 |
| **Refuted (pooled forward)** | t ≤ −2.0 |
| **Inconclusive (pooled forward)** | anything else; the note states the effect size the block could have detected at its n, measured from P's own dispersion |
| **Not testable** | every member dropped under §2 |

"Low-power check" is part of every row's label (§4). The pooled verdict is reported beside the three members' own forward verdicts, never instead of them; a conflict is named in the first paragraph. Any scoring after the first block, or of a different pool, is a new pre-registration. A Newey–West t with 6 lags on 60 or fewer observations runs somewhat larger than a normal variable, so a t just above 2.0 overstates the evidence; this is said here because the members' pre-registrations do not say it.

## 4. Power, stated now ([`tools/power_pooled.py`](../../tools/power_pooled.py), output [`tools/power_pooled.txt`](../../tools/power_pooled.txt); committed `36eae76`, from committed history files only, after reproducing each member's published t)

60-month MDE at t ≥ 2.0 and 80% power (K = 2.842), with the dispersion of P measured two ways:

| Pool | At long-history dispersion (1974–2018, 534 months) | At ETF-era dispersion (2003–2018, 185 months) | Months to see +0.70% a year |
|---|---|---|---|
| 006 + 007 + 008 | 2.75% a year | 0.98% a year | 928 / 118 |
| 007 + 008 | 2.67% a year | 1.21% a year | 876 / 179 |

So: at the worst case the pool misses the agenda's 2% a year bar, which makes it a **low-power check** under the agenda's rule (2), not a test. The ETF-era figures flatter it for two reasons, disclosed here (design review, finding 3): (a) Study 006 barely times (B3 at w = 0.8702, so a held-bond month's d is 0.13 × the leg's excess return), which lowers P's dispersion and, if 006 contributes no edge, lowers P's expected mean by a third too, so 0.98% for three members is not more power than 1.21% for two; (b) in 2003–2018 Study 008's d is negatively correlated with 006's and 007's (−0.37, −0.40), against +0.31 and +0.19 over 1974–2018, and that sign flip may not persist: combining the two single-record ETF-era figures (2.54% and 2.39%) with the 1974–2018 correlation of 007 and 008 gives about 1.9% a year for their pool, against about 1.35% with the ETF-era correlation by the same rough formula (the script's measured figure is 1.21%). The "months to +0.70%" column assumes P's mean is +0.70% a year. **In 60 months the pool cannot reliably see the +0.70% a year the histories averaged:** at long-history dispersion that needs about 77 years and a "supported" row would need a forward edge about four times the historical one; at the most favourable ETF-era figure a true +0.70% would give an expected t of about 2.0, roughly even odds. "Inconclusive" is the likely outcome at the long-history dispersion, close to a coin flip at the ETF-era one.

## 5. Multiple testing

The forward family on these data is four tests: the three members' own forward verdicts and this pooled one. This study is the family's stated primary for the question in §1; the members' verdicts are reported as their own studies, with no adjustment for the four, and one member's "supported" alone is not read as an answer to §1. The history family count (17, Study 008 §9.4) is unchanged: no history trial is added.

## 6. Order of operations

1. Power computed and committed (`36eae76`, done).
2. Agenda decision committed; this pre-registration reviewed for design by a separate session before it is committed (rule from the second cold read, point 5): done 2026-10-26 01:19:40Z–01:22:59Z, approve with changes, two must-fix, both fixed before this commit ([DESIGN_REVIEW.md](DESIGN_REVIEW.md)).
3. This file and `trials.md` committed and pushed to the public remote **before 2026-10-30 21:15 UTC**; the remote commit hash and the host's push time are recorded in `trials.md` (ARCHITECTURE.md's promise for each new pre-registration).
4. Scoring code (one function reading the three `shadow.csv` files, with tests on constructed data) written and reviewed before the first holding period ends.
5. Scored once, as §3.

Approval: the orchestrator, under the owner's delegation of 2026-10-21; the owner has not seen this pre-registration.
