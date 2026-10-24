# Methods: how this programme guards against overfitting

*Written 2026-10-23 from the committed files at commit `7d38543`. Every number below was read from the file named beside it and rounded once from the stored value. Nothing was re-run for this document. A separate Tester agent that did not write this document checked 95 of its figures against the files on 2026-10-23: 94 matched and one section reference was wrong and is corrected (REVIEW.md §5, not §3). It describes the guards as they operated in Studies 001 to 005; it is not a claim that they are sufficient (see §3).*

A backtest can be made to look good by choosing, after the fact, which rule, parameter, universe, window, benchmark or statistic to report. Every guard here removes one of those choices from the author by fixing it before the result exists, counting it when it cannot be fixed, or handing it to someone who did not write the code. The guards are listed in the order in which they act on a study, each with the worked case from this repository.

## 1. Before any data

### 1.1 Pre-registration committed before the first fetch

Each study's `PREREGISTRATION.md` fixes the question, the one-sided hypothesis and its null, the trials, the benchmarks, the cost cases, the pass criteria, the verdict table with its precedence rule, the in-sample and out-of-sample windows, the data checks with their halt rule and the order of operations (§14 of each). The commit that holds it precedes every fetch, and the independent reviewer checks the order from git timestamps (REVIEW.md §5 in each study).

Worked case, Study 004: the pre-registration (`cf5ef34`, 2026-10-22 20:2x London) named twelve ETFs, the decisive benchmark B4 and four trials before a single price was fetched. The data checks then excluded SPY and DBC under a branch written in that document (§1.3 below), and the study ran on ten. The design was not changed to fit the data; the data check removed what the design had said it would remove.

Worked case, Study 005: the question came from Study 003's result on the shared 2019–2026 window, so that window was declared a hypothesis-generating episode with no decision weight, and the in-sample verdict table was given a "refuted" row with a magnitude and **no "supported" row**, because the power statement (§1.2) showed history could refute the hypothesis but could never support it ([PREREGISTRATION.md §9.5](research/005-duration-trend-regime/PREREGISTRATION.md)).

### 1.2 Power stated before the result

Each study says before the run how many signal changes or regime months it needs to mean anything, and what it will say if it does not get them.

| Study | Power quantity | Prior, written before the run | Observed | Source |
|---|---|---|---|---|
| 003 | switches of T1 in 185 months | 10 to 20 expected; 8 needed for full power | 18, 30.8% of months in cash: "as registered" | `results/insample/summary.json` → `power_statement` |
| 004 | switches across ten assets | 40 needed for full power | 167: "as registered" | `results/insample/summary.json` → `runs.ten…power_statement` |
| 005 | positive-regime months in 185; minimum detectable effect | σ_d assumed 1% a month at registration; positive share 10–30% | 26 positive months (14.1%); σ_d 0.69% a month; MDE **0.36% a month, 4.4% a year** at one-sided 5% and 80% power, written at 10:25 UTC on 2026-10-23 before any return | `results/checks/d3.json` |

Study 005's figure is the one that mattered: an edge of 4.4% a year is far above anything a conditional exit from IEF could plausibly earn, so the in-sample check was declared a sign-and-mechanism check in advance and the three verdict rows were refuted / sign consistent / inconclusive. The check then refuted the hypothesis (§2.4).

### 1.3 Data gates that can halt the study

A pre-registered data check with a limit written before the comparison, run on instrument returns only, before any rule return exists. Failure halts the study permanently; the limit is not moved after the fact.

- **Study 001** (synthetic 10-year par bond against IEF, 2016–2018, 753 days): tracking error 1.540% a year against a 1.5% limit and mean return gap +0.455% a year against ±0.40% failed. The one re-run the halt rule allowed, decided and committed before it ran, brought the tracking error to 1.145% and left the gap at +0.451%. Halted. ([note](research/001-slope-duration-switch/README.md), [review](research/001-slope-duration-switch/REVIEW.md))
- **Study 002** (series rebuilt to earn roll-down, bias estimated per component first): window 1 passed all six checks with the level gap at +0.10% against a +0.05% estimate; window 2 (2003–2015) passed the level check at −0.008% against −0.05% and failed the tracking-error limit, 2.02% against 1.5%. Halted; the limit, an absolute figure carried from a calmer window, was kept. The root README's "Why two studies halted" shows the decomposition. ([note](research/002-slope-duration-switch-r/README.md), [review](research/002-slope-duration-switch-r/REVIEW.md))
- **Study 003** (actual ETF history only): vendor BIL returns against the broker's over 753 common days 2016–2018, annualised mean difference −0.0001% a year against a ±0.05% gate; passed ([trials.md](research/003-bond-tsmom-ief/trials.md), data-check log).
- **Study 004**: the same gate at ±0.20% a year on twelve ETFs; SPY (+0.3146%) and DBC (−0.4648%) failed and were excluded under the pre-registered branch X before any return was computed; HYG (+0.14%) passed ([data_checks.md](research/004-xasset-trend-voltarget/results/checks/data_checks.md)).

Two halts in five studies is the gate doing its job, not the programme failing: in both cases the hypothesis is untested and the note says "inconclusive".

## 2. Around the test

### 2.1 Trial ledger and the deflated Sharpe ratio

Every rule, parameter or sub-sample choice is a row in the study's `trials.md`, dated before it runs. The number of rows N enters the deflated Sharpe ratio (Bailey and López de Prado, 2014, as implemented in `qune_research/stats.py`): the expected maximum Sharpe ratio of N trials of no skill is

SR\* = √V · [(1 − γ) Φ⁻¹(1 − 1/N) + γ Φ⁻¹(1 − 1/(N·e))],

with V the variance of the monthly Sharpe ratios across the registered trials and γ the Euler–Mascheroni constant, and DSR = PSR(SR > SR\*), the probabilistic Sharpe ratio adjusted for skewness and kurtosis. V is floored at (0.05/√12)² when the trials are nearly identical, so that N cannot be made harmless by registering near-duplicates; the files record whether the floor applied. Each study also reports the figure at N = 10, so a reader who distrusts the ledger can see what a larger family would do.

| Study | N registered, N run | Trials | T1 monthly Sharpe | SR\* at N | DSR at N | DSR at N = 10 | Floor applied |
|---|---|---|---|---|---|---|---|
| 003 in-sample | 3, 3 | 12-month sign; 12-1; 10-month SMA | 0.130 | 0.0137 | **0.951** | 0.932 | no |
| 004 in-sample, ten assets | 4, 4 | 12-, 6-, 3-month; blend | 0.256 | 0.0193 | **0.998** | 0.998 | no (V = 0.000337) |
| 004 in-sample, nine without IEF | same | same | 0.254 | 0.0152 | 0.998 | 0.998 | yes |
| 005 in-sample (no decision weight) | 3, 3 | 63-day; 252-day; CPI regime | 0.136 | 0.0123 | 0.959 | 0.945 | yes |

Sources: `results/insample/summary.json` → `deflated_sharpe` and `deflation_inputs` in each study.

What the DSR does and does not answer, from Study 004: a DSR of 0.998 says T1's Sharpe ratio is above zero after allowing for the best of four tries. It says nothing about whether T1 beats a benchmark that already holds the same risk premium, which was the study's question; §2.6 answers that, and the answer is no. The two figures sit side by side in the 004 note and do not conflict.

### 2.2 Benchmarks that already hold the premium

A long-only timing rule earns the asset's risk premium whenever it is invested, so "beats cash" or "beats buy-and-hold with lower volatility" is not evidence of timing skill. Each study's decisive benchmark is a constant-exposure book matched to the rule's own average exposure, with the weight frozen in-sample and carried unchanged out of sample.

- Study 003: B3 = constant mix at T1's in-sample IEF fraction w = 0.692. In-sample Sharpe: T1 0.452, B1 (hold IEF) 0.555, B3 0.554. The rule's lower volatility bought nothing per unit of risk.
- Study 004: B4 = the always-long volatility-scaled book B3 times the exposure ratio k = 0.8018 (ten assets; 0.7764 for nine). In-sample Sharpe: T1 0.886, B4 0.880, B3 0.880. Trend added nothing measurable on top of volatility scaling.
- Study 005: the quantity on trial is not a Sharpe ratio but the exit's value in positive-regime months minus its value in negative ones, which cannot be improved by holding more or less of the asset.

Sources: `results/insample/summary.json` → `weight_b3` (003), `k_exposure_ratio_frozen` (004), descriptive blocks.

### 2.3 Inference that respects autocorrelation and fat tails

Monthly return differences are tested with a Newey–West t-statistic (Bartlett kernel, 6 lags); Sharpe-ratio differences with the Ledoit and Wolf (2008) studentised circular-block bootstrap test; confidence intervals with a stationary bootstrap (Politis and Romano) of 10,000 resamples and expected block length 12 months, fixed seed. The pre-registered C2 criterion is the Newey–West t of mean(T1 − decisive benchmark) ≥ 2.0.

| Study, window | Quantity | Value | Criterion |
|---|---|---|---|
| 003 in-sample | NW t, T1 − B3 | 0.37 | C2 ≥ 2.0: **fail** |
| 003 in-sample | Ledoit–Wolf, Sharpe(T1) − Sharpe(B1), annual | −0.103, p 0.236, CI [−0.273, +0.068] | descriptive |
| 003 in-sample | bootstrap 95% CI of T1's annual Sharpe | [0.02, 0.83] | descriptive |
| 004 in-sample, ten | NW t, T1 − B4 | 0.65 | C2 ≥ 2.0: **fail** |
| 004 in-sample, ten | bootstrap 95% CI of T1's annual Sharpe | [0.44, 1.37] | descriptive |
| 005 in-sample | conditional edge Δ, NW t, bootstrap CI | −0.30% a month, t −2.31, CI [−0.52%, +0.03%] | U = +0.03% < 0.083%: **refuted** |

Sources: `results/insample/summary.json` → `inference` (003, 004), `edge` (005).

An honest failure of the method, disclosed rather than patched: in Study 003's out-of-sample window T1's excess return over cash is exactly zero in 50 of 93 months (the months it held BIL). Resamples drawn only from those months have an undefined Sharpe ratio, and the published bootstrap interval is NaN. The published file was left as written and a post-hoc note gives the values on finite resamples, [−0.70, 0.95] with one resample dropped ([posthoc_bootstrap_nan.md](research/003-bond-tsmom-ief/results/oos/posthoc_bootstrap_nan.md)). Later studies record `resamples_dropped_degenerate` in the file.

### 2.4 The verdict table and its precedence, fixed in advance

Each pre-registration ends in a table that maps the criteria to one of supported / not supported / inconclusive, with a precedence rule for the case in which the in-sample and out-of-sample windows disagree. In Studies 003 and 004 the rule is: any in-sample criterion failing fixes "not supported", whatever the held-back window does.

Both times the held-back window went the rule's way and the table held:

| Study | In-sample | Out of sample (run once) | Verdict |
|---|---|---|---|
| 003 | C1 fail (0.452 vs 0.555 and 0.554), C2 fail (t 0.37), C3 pass (0.951), C4 pass | O1 holds (mean T1 − B3 > 0, t 1.31), O2 holds (Sharpe 0.157 vs −0.259); monthly drawdown −5.5% vs −22.2% for B1, the benchmark the drawdown clause names | **not supported** |
| 004 | C1 fail (0.886 vs 0.880), C2 fail (t 0.65), C3 pass (0.998), C4 pass | O1 holds (t 0.35), O2 holds (Sharpe 0.336 vs 0.199); monthly drawdown −4.1% vs −11.1% | **not supported** |
| 005 | Δ −0.30% a month; upper bound of the interval +0.03% below the 0.083% a month believable minimum | episode 2019–2026 has no decision weight by design: Δ −0.23%, t −0.72, CI [−0.88%, +0.44%] | **refuted in-sample** |

Sources: `results/insample/summary.json` → `criteria`; `results/oos/summary.json` → `criteria`, `verdict_T1`; 005 `results/insample/summary.json` → `row_9_5_T1`, `results/episode/summary.json`.

The out-of-sample advantage in both studies came from one episode, sitting in bills through the 2022 Treasury sell-off; the notes say so in their first paragraph instead of re-weighting the criteria after seeing the window.

### 2.5 Out of sample once, on one shared window

The programme has one held-back window, 2019-01 to 2026-09, fixed on 2026-10-21 before any computation under any study. Each study's `reproduce.sh --oos` runs once and then refuses; the run's time is logged before and after in `trials.md` (003: 2026-10-22 08:37 London; 004: 2026-10-22 23:20–23:23 London). The window is spent for the hypothesis family that has seen it: Study 005, whose question arose from 003's result on that window, could not use it as a test and treated it as an episode (§1.1).

The cost is disclosed where it bites. Study 004's designer had seen every published number of Study 003 on IEF and BIL, two of its instruments, in both windows; §2.4 of its pre-registration says so, and a descriptive run without IEF was registered beside the main one for that reason (it gave the same outcomes).

### 2.6 Multiple testing across the family: reality check and SPA

The DSR treats trials as draws of no skill; White's (2000) reality check and Hansen's (2005) test for superior predictive ability take the actual family of trials against the decisive benchmark and ask whether the best of them beats it once the search is accounted for (`qune_research/multiple.py`; worked case in [Study 004's multiple-testing report](research/004-xasset-trend-voltarget/multiple/README.md), post hoc, no decision weight, 10,000 stationary-bootstrap resamples, expected block 12, seed fixed and the commit recorded before the run).

| Window, universe | Best trial, t | Individual p | SPA p (consistent / lower) | Reality-check p |
|---|---|---|---|---|
| in-sample, ten assets (180 months) | T1, 0.82 | 0.198 | 0.377 / 0.258 | 0.394 |
| in-sample, nine without IEF | T1, 0.96 | 0.165 | 0.308 / 0.247 | 0.331 |
| out of sample, ten (93 months) | — | — | 0.503 / 0.472 | 0.534 |
| out of sample, nine | — | — | 0.668 / 0.592 | 0.664 |

Minimum track-record length (Bailey and López de Prado, 2012) for T1 in-sample, ten assets: 49 months to be 95% confident its Sharpe ratio exceeds zero, and **1,372,470 months** to be 95% confident it exceeds B4's (monthly Sharpe 0.2557 against 0.2542). Source: `multiple/report.json`.

### 2.7 Everything that could be a choice is reported

Each note has a "what did not work" section and every variant that was registered is shown beside the headline: the stress cost case, the N = 10 deflation, the sub-periods, the per-asset attribution, the run without the instrument the designer was not blind to (004), the descriptive trials (005's T2 and T3). Study 005's T2 interval was built on 10,000 resamples of which 480 contained only one regime and were dropped; the count is in the file (`resamples_dropped_one_regime`).

## 3. After the result

### 3.1 Results written once; corrections by dated addition

`results/` files are written by the single run and never edited; `data_manifest.json` holds the SHA-256 of every raw file. When a reviewer or the author finds an error in prose, the correction is a dated addition beside the original text, so the record shows what was first written. Study 002's "pass by 0.6 bp" (0.06 bp) and the fourteen last-digit roundings in Study 004's note were corrected this way.

### 3.2 Independent recomputation by an agent that did not write the code

A separate agent (the Tester role) rebuilds the headline numbers from the committed results files with its own script, reruns the test suite, checks from git timestamps that each pre-registration and decision commit preceded the result it governs, and re-derives the verdict from the table. Its script and report are committed in the study folder.

| Study | Rows recomputed | Match | Outcome |
|---|---|---|---|
| 001 | 69 | 69 | confirmed |
| 002 | 157 | 156 | confirmed with findings (a prose margin) |
| 003 | 171 | 171 | confirmed with findings (stale sentences in the trial log, corrected by dated addition) |
| 004 | 1,951 | 1,937 | confirmed with findings (14 last-digit roundings in the note) |
| 005 | 1,341 | 1,337 | confirmed with findings (4 last-digit figures in the note) |

Sources: each study's `REVIEW.md` §4. No value in any `summary.json`, CSV or check file mismatched in any study.

### 3.3 Forward records that cannot be backdated

Where a study keeps a record after publication, the code refuses to write a decision before 21:15 UTC on the last NYSE trading day of the month, on any other date, or over an existing record; inputs and their hashes go into the record. Study 005's forward record is scored once, when either 24 positive-regime months or 60 holding periods have accumulated, by a table fixed in §11.4 before the first record exists; a "supported" forward result after a "refuted in-sample" check is reported as both, in that order. The first records fall on 2026-10-30 (`research/004-…/paper-log/`, `research/005-…/paper-log/`). The desk's market calls follow the same rule in [predictions/ledger.csv](predictions/ledger.csv): logged before the outcome, scored when due, append-only.

*Precision added 2026-10-24, after reading the three forward-record READMEs side by side.* The paragraph above describes Studies 004 and 005 exactly. Study 003's paper sleeve (`research/003-…/paper/`, record in `paper-log/`, first signal date also 2026-10-30) differs in three details: its clock gate is the pre-registered 17:00 New York time (§11.2; 21:00 UTC under EDT, 22:00 UTC under EST) and was enforced in code only from 2026-10-24, before the first record (until then the schedule alone kept a record out of the session); a date that is not the month's last NYSE trading day, or a missing month-end bar, is not refused but written as a `signal unavailable` record with no target, so the miss itself is on the record; and the input hashes sit in the paper log's `manifest.json` per fetch, not in the decision record. The never-overwrite rule is the same in all three.

## 4. What these guards do not do

- **They do not make a small family safe from the designer's priors.** Four lookbacks and a blend are near-duplicates; the SPA on such a family has little power to separate them, and the DSR floor exists because V across them is tiny. The real protection is that the rules are textbook choices fixed before the data, which is a weaker claim than "the search space was exhausted".
- **The shared window is spent.** No future study of IEF or BIL in this programme has an untouched 2019–2026 window. A new instrument gets one; the old ones do not.
- **The trial count is a rule of judgement.** Each ledger states which earlier trials do not count (a different hypothesis) and why. A reader who disagrees can use the N = 10 column.
- **No cross-validation.** Nothing here is tuned, so there is no purged or embargoed cross-validation and none is claimed. If a future study fits a parameter, that machinery must be pre-registered first.
- **Independent review checks arithmetic and order, not economics.** It can confirm that the verdict follows from the table; it cannot say the table asked the right question.
- **Backtests after costs are not a record.** The forward records start on 2026-10-30; none exists at the time of writing.

## 5. References

Checked against the Crossref registry by `tools/check_citations.py` (output in `tools/citations_check.txt`):

- Bailey and López de Prado (2014). The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality. *The Journal of Portfolio Management* 40(5). doi:10.3905/jpm.2014.40.5.094
- Hansen (2005). A Test for Superior Predictive Ability. *Journal of Business and Economic Statistics* 23(4). doi:10.1198/073500105000000063
- Ledoit and Wolf (2008). Robust performance hypothesis testing with the Sharpe ratio. *Journal of Empirical Finance* 15(5). doi:10.1016/j.jempfin.2008.03.002
- Politis and Romano (1994). The Stationary Bootstrap. *Journal of the American Statistical Association* 89(428). doi:10.1080/01621459.1994.10476870
- White (2000). A Reality Check for Data Snooping. *Econometrica* 68(5). doi:10.1111/1468-0262.00152

Cited from the library's docstrings, not Crossref-checked in this repository:

- Bailey and López de Prado (2012). The Sharpe ratio efficient frontier. *Journal of Risk*. (minimum track-record length, `qune_research/multiple.py`)
- Newey and West (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica*. (`qune_research/stats.py`)
