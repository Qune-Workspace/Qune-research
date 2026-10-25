# Separate-session recomputation: Study 006

## 1. Headline

**Confirmed with findings.** The verdict "inconclusive (fragile)" for T1 follows from §9.5 as written: at base costs over the 593 holding periods 1969-08 to 2018-12, T1's Sharpe 0.4633 clears B1 (0.3384) and B3 (0.3382) by 0.125 (C1), the Newey–West t of mean(T1 − B3) is 2.0599 (C2), the DSR at N = 3 is 0.9987 (C3) and the sign holds at stress costs (C4); T2 and T3 pass C1, C3 and C4 but fail C2 at t 1.9713 and 1.9118, so the fragility row applies and the precedence (not supported > inconclusive > consistent > supported) is not reached further. The gate (G1 0.0076%/yr against 0.18%, G2 0.1314 against 0.32) and the volatility check (σ 7.754% against 10.18%) recompute from the raw files and pass. Every number in `gate.json`, `periods.csv`, `volcheck.json`, both `summary.json` files, the eight monthly and eight metrics CSVs, the chart manifest and the four chart titles recomputes; the whole monthly table (schedule, spread, holdings, B0–B3, T1–T3, both cost cases, history and both episode variants) rebuilds from the raw FRED, Tiingo and Alpaca files with the reviewer's own legs, calendar and engine to 1e-13 or better; the commit chain is in the pre-registered order. The findings are time labels entered as estimates and not corrected, a third chart render not mentioned in the note, and one trial-log edit that the pre-registration calls an append. None changes a number or the verdict.

## 2. Independence statement

The reviewer is Tester, a separate agent session that did not write the code, the pre-registration or the note. Date of review: 2026-10-25. The reviewer had read access to the repository at commit `df477ba`, its git history, Studies 001 and 002's pre-registrations, `tools/power_candidate6.txt`, `CHART_REVIEW.md` and the git-ignored raw files in `data/raw/` as present on disk (SHA-256 of all 7 files matches `results/data_manifest.json`). No network access, no vendor credentials, no secret file read; `reproduce.sh` and `charts/make_charts.py` were not run; nothing under `results/`, `src/`, `tests/`, `charts/`, `paper-log/` or the notes was modified. Every statistic in §4 was re-derived in `review_recompute.py` with numpy, pandas and scipy only, importing nothing from `src/` or `qune_research/`; the synthetic legs, the NYSE calendar, the Newey–West t, both block bootstraps, the Ledoit–Wolf test and the DSR are hand-coded there. The reviewer wrote only this file and `review_recompute.py`.

*Dated note, 2026-10-25, as in Study 005 §2 after the [cold read](../../COLD_READ.md) (point 6):* "independent" in this file means a separate agent session that did not write the study, on the same underlying model as the author (Fable 5.1) and on the same machine; it recomputes the published figures from the committed files and checks the commit order, and is not a replication by an outside party. See [ARCHITECTURE.md](../../ARCHITECTURE.md#how-independence-is-enforced).

## 3. Tests

Run from the study folder and from `qune_research/`, as `.github/workflows/tests.yml` does (`python -m pytest -q`), with the repository's virtual environment, at 07:2x GMT on 2026-10-25:

| Suite | Result |
|---|---|
| Study (`tests/`) | 179 passed in 38.9 s (60 warnings: `invalid value encountered in sqrt` in `stats.py:140`, the Ledoit–Wolf standard error of a degenerate resample) |
| Library (`qune_research/tests/`) | 134 passed in 12.5 s |

`git diff 2f1884f 94be69f -- src tests reproduce.sh conftest.py` is empty: the code that ran the gate, the volatility check, the history and the episode is the tree committed before `APPROVED`. After the runs only `src/forward.py`, `tests/test_forward.py` and `reproduce.sh --forward` were added (`016fa69`); `git diff 94be69f HEAD -- results` is empty. The 163 tests at the run (8 + 11 + 13 + 14 + 9 + 8 + 6 + 11 + 17 top-level functions at `2f1884f`, some parametrised) became 179 with the 16 forward tests.

## 4. Recomputation

`review_recompute.py` prints 1,854 rows: 1,842 match, 0 mismatch, 12 informational. It runs in about a minute (two block bootstraps of 10,000 resamples for each of six trial–cost pairs in each window) and exits 0. Selected rows:

| Claim | Published | Recomputed | Match |
|---|---|---|---|
| SHA-256 of the 7 raw files = manifest; chart manifest's two input hashes = committed `monthly_base.csv`, `metrics_base.csv` | — | equal | yes |
| Synthetic 8.5-year leg (Study 002 §5.2) and cash leg (Study 001 §5.2) rebuilt from FRED; schedule from the reviewer's rule-based NYSE calendar; spread at every signal date | — | 593 periods, dates identical, spread max diff 1e-16 | yes |
| B0–B3, T1–T3 monthly returns rebuilt from raw data with the reviewer's engine, history, both cost cases | — | max abs diff ≤ 1e-13 (14 series) | yes |
| T1–T3 rebuilt from B1, B0 and the holdings with the (1 − c)² switch cost; B2, B3 from B1 and B0 with the drift cost; T2/T3 holdings recovered from their returns | — | 0 | yes |
| B3 weight = T1's IEF share of the 593 periods | 0.8701517707 | same | yes |
| Gate: h, vendor per period, g, e rebuilt from FRED, Tiingo `adjClose` and Alpaca `close`; 192 periods, 2003-01-02 to 2019-01-02 | `periods.csv` | g max diff 1e-15, h and vendors identical | yes |
| G1 \|mean(e)\| × 12; G2 sd(g)/sd(x_ETF); w_o; switches; corr(g, x_ETF); level gap; both splits; T2/T3 G1 | 7.6273e-5; 0.131409; 0.9375; 6; 0.2231; 2.2e-5; … | same (1e-14) | yes |
| Cash periods 2003–2007 / T1 in the leg every 2008–2018 period | 12 / yes | 12 / yes | yes |
| σ over 593 periods from the rebuilt legs; MDE = 2% σ / 10.18% | 7.7542%; 1.5234% | same | yes |
| Twelve metrics, all seven books, both cost cases, history and both episode variants (from the committed files) | `metrics_*.csv`, `summary.json` | same (1e-10 or better) | yes |
| NW mean, se, t vs B1 and B3 for T1–T3 (hand-coded Bartlett 6 lags); stress t | 2.0599 / 1.9713 / 1.9118; 1.1631 …; 2.0123 … | same (1e-8) | yes |
| Sharpe bootstrap 95% intervals (seed 20261021, stationary, block 12, 10,000); Ledoit–Wolf t and p vs B1/B3 (studentised circular block) | [0.2096, 0.7108]; p 0.0971 … | same; p within 1/10,000 (four episode p-values vs B1 differ by one resample) | yes |
| DSR N = 3 / 10 / family 3; SR*; PSR; floor applied (raw variance 4.3e-7 < 2.08e-4) | 0.99872 / 0.99708; true | same | yes |
| §9.5 criteria for T1, T2, T3 and the verdict row by the reviewer's precedence; labels | as published | same | yes |
| Sub-windows and sub-periods by execution month (all metrics, all books); copied `subperiods` key by signal month (2009 sub-period 119 periods) | as published | same | yes |
| Mechanism check: 77 inverted month ends, 14 episodes, 5.5; 0.380% / 0.755%; 54.5% | as published | same | yes |
| NW/i.i.d. ratio T1 − B3 | 0.96309 | same | yes |
| Episode: Alpaca schedule (no slip), spread, B0–B3, T1–T3 actual and synthetic, both cost cases | — | max abs diff ≤ 1e-13 | yes |
| Episode daily max drawdown T1 / T2 / T3 / B1 from the reviewer's daily path | −22.64% / −22.64% / −20.33% / −23.92% | same | yes |
| README and trial-log typed numbers (about 110: tables, gate, sub-windows, mechanism, episode, "by 0.06 / 0.03 / 0.09", "+0.9% a year") | — | all at printed rounding | yes |
| Chart titles (four SVGs) against the recomputed numbers and the manifest; manifest numbers (77, 54, dates, growth, drawdowns, decade means, shares) | as published | same | yes |

## 5. Commit chain

Committer times from `git log --format=%cI` (2026-10-25; the first two in +01:00, the rest UTC = London after 02:00); run times from `run_at_utc` and file modification times under `results/`; `code_commit` / `provenance.git_commit` in each output.

| Step | Commit | Time | Governs | Precedes the governed result |
|---|---|---|---|---|
| Power bar (`tools/power_candidate6.txt`) | `21f850b` | 00:17:15+01 | bounds 0.18%, 0.32, 10.18% | yes |
| Question note | `07962f7` | 01:20:12+01 | everything | yes |
| Pre-registration, trial log (step 1) | `a67ef8d` | 02:19:51 | everything | yes: first file read 02:21:01Z |
| Data step (step 2) | `edec076` | 02:21:36 | — | after its run 02:21:01Z (pre-run row committed with the outcome; disclosed) |
| §16 copy decision; code part 1; code part 2 (step 3) | `e505e28` `a693069` `2f1884f` | 02:22:49, 02:28:17, 03:21:42 | every run | yes |
| `APPROVED` + gate row (step 4) | `392b7e1` | 03:22:11 | --gate | yes: gate run 03:22:29Z, `code_commit` 392b7e1 |
| Gate outputs (step 5) | `8286e25` | 03:22:43 | — | after the run |
| Volcheck row; run 03:23:04Z; outputs (step 6) | `ff50d9f` `9e9d9b5` | 03:22:58, 03:23:11 | --volcheck | yes; `code_commit` ff50d9f |
| History row, T1–T3 run dates, family re-count (step 7) | `abb7023` | 03:23:42 | --history | yes: files 03:24:29–57Z, `run_at_utc` 03:24:57Z, provenance abb7023 |
| History outputs | `662630c` | 03:25:23 | — | after the run; `results/history/` has this one commit |
| Note (step 8) | `3663b77` | 03:27:16 | --episode | yes |
| Episode row; run 03:29:13Z; outputs (step 9) | `d1ffbbd` `94be69f` | 03:28:32, 03:29:42 | — | yes; provenance d1ffbbd; `results/episode/` has one commit |
| Forward code, §16 entry | `016fa69` `034ea89` | 04:21:52, 04:21:58 | forward record only | — |
| Charts; charts after the chart check; CHART_REVIEW | `b868f5d` `2d0889a` `6d32efb` | 04:26:08, 05:22:32, 05:22:38 | — | inputs unchanged (hashes) |
| SVG id-salt re-render (manifest `made_at` 06:21:38Z, commit at run `adf97de`) | `df477ba` | 06:22:05 | — | PNGs byte-identical to `2d0889a` (checked) |

`PREREGISTRATION.md` differs from `a67ef8d` only by four appended §16 entries (8 lines, none removed). Limits as in Study 005: one machine clock, unsigned commits; git cannot show the absence of an uncommitted earlier run.

## 6. Criteria and verdict

Applied by the reviewer from the recomputed numbers. Gate PASS (G1 at 4.2% of its bound, G2 at 41%), so the gate row does not apply. T1: C1 margins +0.1250 and +0.1251; C2 t 2.0599 ≥ 2.0; C3 0.99872 ≥ 0.95; C4 mean +0.000753 base, +0.000736 stress. T2: C2 t 1.9713 < 2.0; T3: C2 t 1.9118 < 2.0; both pass C1, C3, C4. Hence **inconclusive (fragile)**; σ 7.754% ≤ 10.18% so neither the "consistent" row nor the "low-power check" label applies; 27 switches ≥ 8 so no "low-powered" label; the only label is the gate-redesign label, which the note's first paragraph carries. `verdict_T1`, `verdict.md`, the README, the root README and the trial log agree. The episode summary holds no criteria or verdict key and the README gives it no row.

## 7. Disclosures

Present: G1 rests on 12 cash periods in 2003–2007 and T1 held the leg in every 2008–2018 period (README gate section, trials.md); fidelity before 2003 assumed; G2 expected to pass; the result comes from 1969–1981 and the author knew the inversion dates (README second paragraph, "What did not work"); fragility rule applied without re-weighting; t vs B1 1.16; effect +0.9%/yr below the 1.52%/yr MDE; the copied engine's `subperiods` key is by signal month and the note quotes the execution-month table; the episode has no decision weight and the 2022–24 inversion was known; no paper order; the chart check's three must-fix items and the author-only check of the re-rendered charts (`CHART_REVIEW.md` third section; the README says "titles below are the corrected ones" and links to it).

## 8. Findings, ranked

**Must fix:** none.

**Should fix**

1. Time labels entered as estimates and not corrected. `PREREGISTRATION.md` §16 third entry "03:3x London, clarification during implementation (§14 step 3, part 2)" was committed at 03:21:42 (`2f1884f`); the README quotes it as "03:3x" twice. README "Added … 03:3x London, after the episode was run once at 03:29": the commit is `94be69f` at 03:29:42. README step 1 and `trials.md` "question note 01:1x–01:4x": both commits are 01:20 (+01:00). Append one dated correction; the order of events is unaffected (§5).
2. `trials.md` rewrote the three T1–T3 rows ("registered, not run" → run date, code commit, outputs) in `abb7023`/`662630c` and replaced the closing sentence; §7 says additions are "appended … with a date". The content is correct and the pre-run version is in git, but a reader of the file alone cannot see that the rows changed. A one-line note under the table would close this.

**Notes**

3. The charts were rendered three times: `b868f5d`, `2d0889a` (after the chart check) and `df477ba` (SVG id salt, PNGs byte-identical, manifest `made_at` 06:21:38Z). The README's chart section mentions the first two only; the third is in the commit message and the BUILD_LOG.
4. Four episode Ledoit–Wolf p-values vs B1 (T2 actual, T3 synthetic, both cost cases) differ from the reviewer's by exactly one resample in 10,000 (e.g. 0.9323 vs 0.9322): a resample in which the trial and B1 nearly coincide puts |t*| on the comparison boundary. No decision weight; the history p-values match to 1e-12.
5. `metrics_*.csv` writes `hit_rate_held_vs_other` for B2 and B3 as empty and `sharpe_annual` for B0 as empty (NaN); the summary carries `NaN` literals, which strict JSON parsers reject. Harmless here.
6. The first-period convention (Study 001 §6.6, inherited): the book starts in cash, so a first target of IEF pays the switch cost. In the history T1 starts in cash (July 1969 spread −0.63%), so nothing is charged; in the episode T1–T3 start in IEF and pay 4 bp against B1 in January 2019.
7. The gate's descriptive splits use their own w per subset; the 2008–2018 G1 is exactly 0 because h is constant there, which is the disclosed limit rather than evidence of fidelity.
8. `README.md` step 7 says the publication commit "carries this line"; the publication commit is `3663b77` (03:27:16) and later commits (`94be69f`, `034ea89`, `b868f5d`, `6d32efb`) edited the README with dated notes, each stating that nothing above changed. Verified: the diff `3663b77`→HEAD removes only the "charts not drawn" bullet and the three "Next" placeholders.

## 9. Not checked (and why)

- The NYSE calendar's special closures were taken from the reviewer's own list, which agrees with the committed execution dates on all 593 + 192 + 93 periods; the list itself was not verified against an exchange source.
- `reproduce.sh` in any mode, `make_charts.py`, the forward-record code (`src/forward.py`, refuses before 2026-10-30), the engine's diagnostic `main_chart.png` files, the PNG rendering of the four charts (titles were read from the SVG text), the root README's at-a-glance rows, the BUILD_LOG, literature citations.
- Whether each run was executed once: git shows each output folder committed once, in order, with matching provenance commits and file times inside the logged-to-committed interval; it cannot show the absence of an uncommitted earlier run.
- Data-step hash matches against Studies 002 and 004's manifests were not repeated; this study's manifest hashes match the files on disk.

## 10. How to rerun the reviewer's checks

From the study folder, with the raw files present in `data/raw/`:

```
../../.venv/bin/python review_recompute.py && ../../.venv/bin/python -m pytest -q
```

The script takes about a minute, prints the 1,854-row comparison table and exits 0; without the raw files it reports the raw-data rows as not checked and still recomputes everything from the committed files.
