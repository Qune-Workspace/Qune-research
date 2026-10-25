# Separate-session recomputation: Study 008

## 1. Headline

**Confirmed with findings.** The verdict "not supported" for T1 follows from §9.5 as written. At base costs over the 534 periods 1974-07 to 2018-12, T1's Sharpe ratio is 0.4146 against B1 0.3818 and its B3 0.3812 (w̄ 0.46618). It misses the C1 margin by 0.067 against both. The Newey–West t of mean(T1 − B3) (+0.56% a year) is 1.3813, so C2 fails. C3 passes (DSR 0.98842 at the family count 17; 0.99552 at N = 3, 0.99086 at N = 10) and so does C4 (stress t 1.3327). Two failed criteria put T1 in the first row of the precedence. The era row (396 periods, mean(T1 − B3) −0.0554% a year, t −0.18) and the companion clause are never reached, though the era row fails as well. Both companions are "not supported" on their own criteria: T1a (t 1.7789, C1 short by 0.033) and T1b (474 periods, t 0.9147, C1 short by 0.118).

The following recompute from the raw files: the real yield, the CPI month k, the three weight paths, both legs, every monthly return at both costs, the gate (G1 0.021% / 0.024% / 0.062% a year; G2 0.13140878732605116), the overlap correlations, the volatility check (σ 7.8124%) and the episode. k is rebuilt from the ALFRED cache itself, not taken from `cpi_availability.csv`. All §9.6 descriptives recompute, and so do 287 of the 288 numbers typed in README.md and in trials.md's gate, volatility, history and episode rows. The commit chain is in the registered order.

There are seven findings and none changes the verdict. Two should-fix points are about what the note shows: the episode table's mean weights mix two bases, and a registered descriptive (T1 on T1b's 474 periods) is missing. Should-fix 3: a limitation the pre-registration says the note states (no forecast-based real yield) is absent. The four notes cover a stale CSV column, an amendment committed after the run it governed (disclosed), an inherited label and the DSR variance.

## 2. Independence statement

The reviewer is Tester, a separate agent session that did not write the code, the pre-registration or the note. Date of review: 2026-10-25, from 21:28 to 21:4x GMT. The reviewer had read access to the repository at `b13efd2` and its git history, and to Study 006's and 007's committed files. Study 007's review script was read and adapted. The git-ignored raw files in `data/raw/` and the ALFRED cache `data/raw/alfred/` were read as present on disk. All 9 SHA-256 values match `results/data_manifest.json`, and all 1,374 cache files match `results/alfred_cache_manifest.csv`. No network access, no credentials, no secret file read. `reproduce.sh` was not run, and nothing under `results/`, `src/`, `tests/`, `paper-log/`, `data/raw/` or the notes was modified.

`review_recompute.py` uses numpy, pandas and scipy only and imports nothing from `src/` or `qune_research/`. The reviewer read `src/real_yield.py` and `src/history008.py` for the conventions the pre-registration leaves to the code, then reproduced them without choosing new ones:
- the RNG draw order;
- quintiles by `rank(method="first")`;
- ddof 0 for sd(w);
- B3 for the sub-windows and eras taken at the full-window w̄;
- T1b's B1–B3 restarted on its own window;
- the hold target set to the drifted weight.

The reviewer wrote only this file and `review_recompute.py`.

*Dated note, 2026-10-25, as in Study 005 §2 after the [cold read](../../COLD_READ.md) (point 6):* "independent" in this file means a separate agent session on the same model family as the author, on the same machine. It recomputes the published figures from the committed and raw files and checks the commit order. It is not a replication by an outside party. See [ARCHITECTURE.md](../../ARCHITECTURE.md#how-independence-is-enforced).

## 3. Tests

Both suites were run with the repository's virtual environment and `python -m pytest -q` at 21:29 GMT on 2026-10-25:

| Suite | Result |
|---|---|
| Study (`tests/`) | 319 passed, 2 skipped in 83.4 s (64 warnings, `RuntimeWarning` in `src/stats.py` on degenerate resamples) |
| Library (`qune_research/tests/`) | 134 passed in 14.3 s |

The skips are the two copied `forward007` tests, skipped by name in `tests/conftest.py`, as disclosed. Between the reviewed code (`7d7dc03`) and the history output (`ef7f4bd`), the only change in `src/`, `tests/` or `reproduce.sh` is four comment lines in `config008.py` (the family re-count). Between the history and episode outputs nothing changes. So the code that ran the gate, the volatility check, the history and the episode is the tree tested here. The README's "319 tests pass, 2 skipped" is correct.

## 4. Recomputation

`review_recompute.py` prints 953 rows: 940 match, 1 mismatch (should-fix 1), 12 informational. It runs in about 90 s and exits 1 because of the mismatch. Selected rows:

| Claim | Published | Recomputed | Match |
|---|---|---|---|
| SHA-256: 9 raw files = data manifest = history provenance; 1,374 ALFRED cache files = cache manifest (1,045 HTTP 200, 329 HTTP 404); 006/007 overlap sources = gate.json | — | equal | yes |
| Signal dates (last date in the month with DGS10, DGS7, DTB3), 687 months; = `cpi_availability.csv` dates | — | equal | yes |
| k rebuilt from the vintage dated on each signal date (m − 1 if present, else the latest month); CPILFENS without a vintage follows the headline (§16 (a)) | `cpi_availability.csv` | CPIAUCNS identical; CPILFENS differs only at 1996-01 (note 4) | yes |
| m − 1 unpublished at t: CPIAUCNS 1996-01, 2025-11; CPILFENS 2025-11; no core vintage before 1996-12 (329 months); December vintages equal the current files (27,192 and 14,053 months) | `vintage_check.json` | same | yes |
| π, r at signal dates; undefined only at 2025-11 (§16 (b)) | `signals.csv`, `monthly_base.csv` | ≤ 1e-16 | yes |
| Expanding (min 60) and trailing-120 average-rank weights over defined values; first months 1974-06 / 1974-06 / 1979-06 | `signals.csv` (594), history, gate, episode | ≤ 1.2e-16 | yes |
| B1, B0 rebuilt from FRED on the committed execution dates (= Study 007's history, 534 months) | `monthly_*.csv` | ≤ 1.7e-15 | yes |
| T1, T1a, T1b, B2, B3 at both costs (engine from cash, drift, (1 − c·\|Δw\|)²); no hold period 1974–2018 | `monthly_*.csv` | ≤ 3.2e-16 | yes |
| Twelve metrics; turnover 23.83 / 21.89 / 32.70; bootstrap CI [0.1354, 0.6795]; Ledoit–Wolf p vs B3 0.7004 / 0.43 / 0.87 (seed order reproduced) | `metrics_*.csv`, `summary.json` | ≤ 1e-10; p exact | yes |
| DSR at N = 17 / 3 / 10 and SR*, both costs; floor applied (raw variance below 2.08e-4) | as published | same | yes |
| Era row (396 periods; −0.0554% a year; t −0.1838); §9.5 C1–C4 for the three trials; the reviewer's precedence; no turnover label; σ ≤ bar | as published | same | yes |
| Sub-windows and rate eras (Sharpe of T, B1, B3; mean and t of T − B3; mean weight) for all three trials | `summary.json` | same | yes |
| Quintiles (107/107/106/107/107, ranges, excess, hit rate); r ≤ 0 76 / r > 0 458; NW/iid 1.0949; sd(w − w̄) 0.2701; MDE 0.817% / 1.161%; corr(d, 007 d) 0.1925; T1 on T1b's window (Sharpe 0.4338, t 1.3311) | `summary.json` | same | yes |
| Gate: g from the rebuilt legs and ETF closes per vendor columns; G1, w_o, turnover, splits, mean g, corr(g, x_ETF) 0.2231; G2; overlap correlations 0.1146 / −0.0143 / 0.0854 and 0.1613 / 0.1148 / 0.0880; no flag | `periods.csv`, `gate.json` | g ≤ 1.6e-15; statistics ≤ 1e-12 | yes |
| Volatility check: σ 7.81237%, = Study 007's committed figure; MDE 1.5348% | `volcheck.json` | same | yes |
| Episode: actual B1/B0 = broker closes; synthetic legs; weights with the rank still expanding (T1b trailing), 2025-11 held at the drifted weight; all trials and B3 at both costs, both sides; NW t 0.8505 / 0.7734 / 0.4010; forward weights 0.5241 / 0.654 / 0.9916 | `results/episode/` | ≤ 3.2e-16 | yes |
| Typed numbers: README verdict, gate, results, sub-window, mechanism, power and episode tables and text; the weight by execution year (0.19 … 0.39; 2022 max 0.033); trials.md gate, volcheck, history and episode rows | — | 287 of 288 at printed rounding | 1 NO |

## 5. Commit chain

Committer times come from `git show -s --format=%cI` (all on 2026-10-25, UTC = London). Run times come from `run_at_utc` (or `started_utc`) in each output.

| Step | Commit | Time | Run (UTC) | Precedes the governed result |
|---|---|---|---|---|
| Question; pre-registration and trial log | `1d1daeb` `ca2432a` | 16:24:09, 17:20:07 | — | yes |
| Data step outputs, with the §16 ID amendment and the pre-run row | `be162c1` | 17:25:51 | 17:25:07 | after its run (note 5) |
| Vintage check: script and first attempt; row; outputs | `d76c22a` `ac42f2d` `245613c` | 17:45:13, 18:18:12, 18:27:09 | 18:18:33–18:25:33 | yes |
| §16 (a)/(b) clarifications | `dcf5cd1` | 18:27:45 | — | yes, before any code (`0dec256` 18:34:18) |
| Code; fixes after the code review | `0dec256` … `cf5b64f`, `7d7dc03` | 18:34:18–20:24:11, 20:36:24 | — | yes |
| `APPROVED` + gate row; gate outputs | `e9169dd` `172c456` | 20:43:36, 20:44:12 | 20:43:56 (code `e9169dd`) | yes |
| Volcheck row; outputs | `fe94ff7` `2902e22` | 20:44:40, 20:45:09 | 20:44:55 (code `fe94ff7`) | yes |
| Re-count and history row; outputs; outcome row | `031c134` `ef7f4bd` `b111b0e` | 21:18:23, 21:19:50, 21:21:02 | 21:19:39 (code `031c134`) | yes |
| Root README; note | `798d487` `a90f048` | 21:22:14, 21:24:19 | — | yes, before the episode row |
| Episode row; outputs; section; correction | `ebc80e1` `eb39f49` `cea7187` `b13efd2` | 21:24:53, 21:25:49, 21:26:26, 21:27:04 | 21:25:29 (code `ebc80e1`) | yes |

The 27 listed commits are strictly increasing in time. Each `results/` folder and `cpi_availability.csv` has exactly one commit. Since `ca2432a`, no line has been removed from `PREREGISTRATION.md`, `trials.md` or `QUESTION.md`: every amendment, precision and outcome is appended. The limits are as before: one machine clock, unsigned commits, and git cannot show that no uncommitted earlier run took place.

## 6. Criteria and verdict

The reviewer applied the criteria to the recomputed numbers. G1 passes for all three trials and none is dropped. σ 7.812% ≤ 10.18%, and every turnover is ≥ 8, so no label applies.

| Trial | C1 (margin vs B1 / B3) | C2 | C3 (N = 17) | C4 | Row |
|---|---|---|---|---|---|
| T1 | **fail** (−0.067 / −0.067) | **fail**, t 1.3813 | pass, 0.988 | pass | **not supported** |
| T1a | **fail** (−0.033 / −0.033) | **fail**, t 1.7789 | pass, 0.994 | pass | not supported |
| T1b | **fail** (−0.118 / −0.117) | **fail**, t 0.9147 | pass, 0.976 | pass | not supported |

Precedence: not supported > gate > one era > fragile > consistent > supported. T1 is "not supported" on C1 and C2 alone, so the era row and the companion clause do not decide it. `summary.json`, `verdict.md`, README.md and trials.md agree. The verdict is not knife-edge: T1 is 0.62 short of t = 2 and 0.067 short on Sharpe. The one decision-relevant choice made after registration, §16 (a), moves T1a's 1996-01 real yield from 0.025601 to 0.025659 and cannot change T1a's row.

## 7. Disclosures

These disclosures are present:
- The §2.4 disclosure (the window was seen by Studies 006 and 007; the drift of real yields is general knowledge) is the note's first paragraph and is repeated in "What did not work".
- The gain sits before 1986 (era row) and before 2003, where fidelity is an assumption.
- No overlap flag, so no sentence is required; the correlations are reported.
- The episode is a known window with no decision weight, and its one hold month is disclosed.
- The process slips are listed: the series ID, the data-step script that over-labelled its probe, the code-review must-fix, and time labels written ahead of the clock, each corrected by an appended precision.

These are not in the note: should-fix 2 and 3 below, and the fact that core-CPI release dates before 1996-12 are inferred from the headline release, because ALFRED holds no core vintage (329 months; in trials.md and §16 only).

## 8. Findings, ranked

**Must fix:** none.

**Should fix**

1. README episode table, row "Mean weight in IEF": the three trials are on different bases. T1 0.218 and T1a 0.167 are the mean of the monthly `w_` column, which includes the 2025-11 hold month's drifted weight (`metrics_base.csv` `mean_weight`). T1b 0.446 is the mean over signal months only (`mean_signal_weight_in_episode` 0.4457). On T1's basis T1b is 0.450; on T1b's basis T1 is 0.217 and T1a 0.165. Pick one basis and name it. trials.md's 0.218 for T1 is the first basis.
2. README results: §2.5, §7 and §9.6 register "T1 on T1b's 474 periods with its t" beside T1b. The note does not report it. The figures are Sharpe 0.434, +0.61% a year, t 1.33, from `verdict.md`. They support the note's sentence that the trailing rank "did worse, not better": on the same periods T1 has t 1.33 against T1b's 0.91, so the gap is a rule effect and not a window effect.
3. README: §5.5 says that the absence of a monthly inflation-forecast series covering 1969–2018 (so T1's trailing-CPI proxy stands, with no forecast-based trial) is "stated as a limitation in the note". The note does not state it. Add one sentence, for example in "What did not work".

**Notes**

4. `results/cpi_availability.csv` (`245613c`, written before §16 (a)) still gives CPILFENS k = 1995-12 and branch `assumed_known` for signal month 1996-01. The code applies §16 (a) (k = 1995-11, reproduced here from the cache), but `summary.json`'s CPILFENS branch counts (assumed_known 270 / read 264 on the test window) repeat the CSV's labels. §16 (a) promised the counts "both ways", and only `k_not_m_minus_1 = 1` shows the change. A reader using the CSV's k column directly would get T1a's 1996-01 wrong.
5. The §16 series-ID amendment (labelled "17:2x GMT") and the data step's second-attempt pre-run row were committed in `be162c1` at 17:25:51, after that run at 17:25:07Z. The §0 header asks for an amendment before any further step. The row says "in the same commit", and the change is an identifier with no discretion, so nothing turns on it, but strictly the amendment post-dates the run it governed. The vintage check's first-attempt rows were likewise committed with their outcome (`d76c22a`, disclosed; that attempt wrote nothing).
6. `gate.json` labels the first split "2002-2007". It holds the 60 periods executed 2003–2007. The label is inherited from Study 007's code (that review's note 3).
7. The DSR variance is taken over this study's three trial Sharpe ratios (floored), not the family's 17 (Study 007 review note 4). It is not decision-relevant here because T1 fails C1 and C2. trials.md's episode row says "687 months of history"; that is 687 signal months, of which 686 have a defined real yield (n = 686 in `summary.json`).

## 9. Not checked (and why)

- The NYSE execution calendar: execution dates were taken from the committed files, are identical to Study 007's committed history on all 534 months, and fall 1–7 days after the rebuilt signal date. The episode calendar was not rebuilt.
- ALFRED's endpoint semantics (that a vintage dated t holds what was published by t) were taken from the logged hand check; no network.
- Not run or read: `reproduce.sh`, `data_step.py`, `vintage_check.py`, the root README, BUILD_LOG, the code-review record, the charts (not yet drawn; out of scope), the citations.
- Episode Ledoit–Wolf p-values and bootstrap intervals: no decision weight, not quoted.
- The desk registry count (562 rows) behind the family re-count: outside this repository.

## 10. How to rerun the reviewer's checks

From the study folder, with the raw files and the ALFRED cache present in `data/raw/`:

```
../../.venv/bin/python review_recompute.py; ../../.venv/bin/python -m pytest -q
```

The script takes about 90 s, prints the 953-row table and exits 1 while should-fix 1 stands. Without the raw files it checks hashes only and says so.
