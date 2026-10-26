# Separate-session recomputation: Study 010

## 1. Headline

**Confirmed with findings.** The verdict "not supported" for T1 follows from §9.5 as written. Over H (1927-07 to 2026-08, 1,190 months) at base costs, T1's Sharpe ratio is 0.5749 against B1 0.5545 and B3 0.6966. It misses the C1 bar by 0.080 against B1 and by 0.222 against B3, so C1 fails on both legs. C2 passes (mean d +2.57% a year, Newey–West t 3.7835), C3 passes (DSR 1.0000 at N = 3) and C4 passes (stress mean d +0.74% a year). One failed criterion puts T1 in the first row of the precedence, so the window row (P, 560 months, +3.18% a year, t 2.76, pass) and the companion clause do not decide it. Both companions are "not supported" on their own C1–C4: T1a fails C1 only, and T1b fails all four.

From the three raw zips, the reviewer's own code rebuilds the following. Every factor value, signal, position, K_t, cost, T, B1, B3 and d of the three trials at both costs matches `results/history/monthly_*.csv` with zero difference. Every figure in `summary.json` recomputes, including the bootstrap Sharpe intervals and the Ledoit–Wolf p-values (draw order reproduced). All typed numbers in trials.md's data-step, re-count and history-outcome rows match. Of the numbers typed in README.md, all but one match. The commit chain is in the registered order, and the push reflog shows that the data-step and history-run rows were pushed before their runs.

There are eight findings and none changes the verdict. Three are should-fix points on the note's disclosures: the §2.4 sentence is incomplete, the pre-1962 universe point is missing, and B3's look-ahead is not named. Five are notes.

## 2. Independence statement

The reviewer is Tester, a separate agent session that did not write the question note, the pre-registration, the code or the note. Date of review: 2026-10-26, from 10:22 to 10:3x GMT. The reviewer had read access to the repository at `d9ac7da` and then `4c3127b`, and to its git history. README.md was read at 10:23, untracked; it was committed unchanged in `4c3127b` at 10:24:28 (SHA-256 `3373f4c5…` both times, printed by the script). Study 008's review files were read and their structure adapted. The git-ignored zips in `data/raw/` were read as present on disk; all three match `results/data_manifest.json` (zip and CSV SHA-256 and bytes). No network access, no credentials, no secret file read. `reproduce.sh`, `data_step.py` and `programme_count.py` were not run, and nothing under `results/`, `src/`, `tests/`, `data/raw/` or the notes was modified.

`review_recompute.py` uses numpy, pandas and scipy only, and imports nothing from `src/` or `qune_research/`. It parses the monthly sections with its own parser. The reviewer read `src/rule.py`, `src/history.py`, `src/data.py` and `qune_research/stats.py` for the conventions the pre-registration leaves to the code, then reproduced them without choosing new ones:
- **Cost convention:** cost_t = c × (1/K_t) Σ_k 2 |h_k,t − h_k,t−1|, with h = 0 before a factor's first held month. So a flip costs 4c/K_t and an entry 2c/K_t of the month's return (4c or 2c on that factor's 1/K_t share), as §6.3's formula states. The 1927-07 entry of three factors costs 0.20% (2c), and LT_Rev's entry in 1932-01 costs 0.05% (2c/4). Reweighting is not charged.
- The formation product runs in date order, and |R| ≤ 1e-12 is a tie that takes −1 (there are no ties).
- h̄ is the unweighted mean over a factor's held months in H.
- Newey–West uses a Bartlett kernel with 6 lags and no small-sample correction.
- The DSR variance is the population variance (ddof 0) of the three trials' monthly Sharpe ratios of T within each cost case, floored at (0.05/√12)². The floor is not binding: base 0.0015985, stress 0.0033935.
- The bootstrap order per cost case is a fresh `default_rng(20261021)`, then for each trial: the T, B1 and B3 intervals, then Ledoit–Wolf against B1, then against B3.

The reviewer wrote only this file and `review_recompute.py`.

*Dated note, 2026-10-26, as in Study 005 §2 after the [cold read](../../COLD_READ.md) (point 6):* "independent" in this file means a separate agent session on the same model family as the author, on the same machine. It recomputes the published figures from the committed and raw files and checks the commit order. It is not a replication by an outside party. See [ARCHITECTURE.md](../../ARCHITECTURE.md#how-independence-is-enforced).

## 3. Tests

Both suites were run with the repository's virtual environment and `python -m pytest -q` at 10:24 GMT on 2026-10-26:

| Suite | Result |
|---|---|
| Study (`tests/`, from the study folder) | 31 passed in 13.1 s |
| Library (`qune_research/tests/`, from the repository root) | 134 passed in 18.0 s |

`git diff 55aa9e3 HEAD` shows no change in `src/` or `reproduce.sh`. So the code that ran at 10:19:49Z is the code the separate code review re-checked, and the tree tested here. The run's code is `eef348e` because the run falls between the commits `eef348e` and `1748602`. `summary.json` itself records no commit hash.

## 4. Recomputation

`review_recompute.py` prints 1,393 rows: 1,387 match, 2 mismatch (should-fix 1 and note 4, both in README.md), 4 informational. It runs in about 110 s and exits 1 while those two stand. Selected rows:

| Claim | Published | Recomputed | Match |
|---|---|---|---|
| (e) SHA-256 and bytes of the 3 zips and their CSV members; one member each; header names the 202608 release | manifest | equal | yes |
| (a) Monthly sections: 1926-07 to 2026-08 (1,202), ST_Rev 1926-02 (1,207), LT_Rev 1931-01 (1,148); no gap, no −99.99/−999 | `data_step.json` | same | yes |
| Factor columns of both monthly CSVs, 1,190 months, read at round-trip precision | `f_*` | 0 difference | yes |
| (b) h, K_t, T_gross, cost, T, B1, B3, d for T1, T1a, T1b at 10 and 50 bp | `monthly_*.csv` | 0 difference | yes |
| (c) Eleven metrics of T, T_gross, B1, B3; d and T − B1 rows (mean, NW t and se, iid t, Sharpe); cost a year | `summary.json` | ≤ 1e-9 relative | yes |
| Bootstrap Sharpe CIs (18) and Ledoit–Wolf diff and p (12): T1 vs B1 +0.0205 (p 0.8686), vs B3 −0.1217 (p 0.3063) | `summary.json` | same; p exact | yes |
| DSR, PSR and SR* at N = 3/10/31/595, both costs; T1 base 1.0000 / 0.99994 / 0.99894 / 0.94031 | `summary.json` | same | yes |
| C1–C4 for the three trials; window row; reviewer's precedence; no return-unit label (MDE 1.9307% ≤ 2%) | `criteria`, `verdict` | same | yes |
| (d) P1/L/P2/P rows for every trial and cost; per factor h̄, flips, ties (all 0), long share, hit rate, gross and net contributions with t (net sum = mean d), static exposure; pooled hit rate; flips a year | `summary.json` | same | yes |
| Decades (11), twelve worst months (dates and values), the two episodes (+11.03%, −5.94%), paper comparison (618 months and H) | `descriptive_T1` | same | yes |
| Realised power: NW/iid 0.9747, sd(d) 6.941%, MDE 1.359% / 1.931% a year (Sharpe of d 0.196 / 0.278) | `power_realised` | same | yes |
| Public count 31 by study (own parse of the `\| ID \|` tables at `eef348e`) | `programme_count.json` | same | yes |
| (f) trials.md: data-step, re-count and history-outcome numbers (48 rows) | — | all at printed rounding | yes |
| (f) README.md: verdict, tables, decades, per factor, episodes, paper, power, costs, "What did not work" (≈ 130 numbers) | — | all but one at printed rounding | 1 NO (note 4) |

## 5. Commit chain

Committer times are from `git show -s --format=%cI`, push times from the local `origin/main` reflog, and run times from the outputs. All are on 2026-10-26, where UTC equals London.

| Step | Commit | Committed | Pushed | Run (UTC) | Precedes the governed result |
|---|---|---|---|---|---|
| Question | `e699ac3` `9cfd47f` | 07:25:24, 07:25:55 | 07:26:11 | — | yes |
| Pre-registration + trials.md | `d9648af` | 08:22:51 | 08:23:22 (with `9dbaa96`) | — | yes |
| Data-step row; outcome | `cb8866c` `a2e97b3` | 09:17:32, 09:18:51 | 09:17:52, 09:19:00 | page 09:17:56, step 09:17:58 | yes |
| Code; fixes after review | `e98c874` `1839e5a` `55aa9e3` | 09:21:21, 09:28:15, 09:37:13 | 09:28:34, 09:37:30 | — | yes |
| `APPROVED` | `2f29086` | 09:40:45 | 09:41:02 | — | yes |
| Re-count + history-run row | `eef348e` | 10:17:34 | 10:17:51 | count 10:17:18 | yes |
| History outputs; outcome row | `1748602` `d9ac7da` | 10:20:08, 10:21:24 | 10:21:40 | history 10:19:49 | yes |
| Note | `4c3127b` | 10:24:28 | not checked | — | yes, after the outcome row |

The first 12 commits form one ancestry line (checked by the script; `4c3127b` is the child of `d9ac7da`) and are strictly increasing in time. `APPROVED` is added only in `2f29086`. The data-step row is absent at `9dbaa96` and present at `cb8866c`. The history-run row is absent at `2f29086` and present at `eef348e`. `results/history/` has exactly one commit (`1748602`) and is unchanged in the working tree. No line has been removed from `PREREGISTRATION.md` or `trials.md` since `d9648af`, or from `QUESTION.md` since `e699ac3`. The limits are as before: one machine clock, unsigned commits, and a reflog that is local and editable. Git cannot show that no uncommitted earlier run took place.

## 6. Criteria and verdict

The reviewer applied §9.5 to the recomputed numbers:

| Trial | C1 (margin vs B1 / B3) | C2 (NW t of d) | C3 (DSR N = 3) | C4 (stress mean d) | Row |
|---|---|---|---|---|---|
| T1 | **fail** (−0.080 / −0.222) | pass, 3.78 | pass, 1.000 | pass, +0.74 | **not supported** |
| T1a | **fail** (−0.125 / −0.130) | pass, 2.82 | pass, 0.984 | pass, +0.63 | not supported |
| T1b | **fail** (−0.402 / −0.550) | **fail**, 0.84 | **fail**, 0.895 | **fail**, −2.33 | not supported |

Precedence: not supported > inconclusive (paper's window only) > inconclusive (fragile) > supported. T1 is "not supported" on C1 alone. The verdict is not knife-edge: T1 would need +0.08 of Sharpe ratio to clear even the B1 leg, and B3's leg is 0.22 away. `summary.json`, `verdict.md`, trials.md and README.md agree. No B3 is identically zero, so C1's B3 leg is the ordinary one. The README's own remark, that C1 compares T with a benchmark of much lower volatility (1.96% against 6.84%), is accurate and was fixed before the data.

## 7. Disclosures

The note is README.md as committed in `4c3127b` (§2). Its first paragraph carries a §2.4 sentence and, before any result, the sentence that the sample was chosen after ten earlier studies and that "only N = 3, this study's own three trials, decides" (§9.4). Also present:
- the factors' own rebalancing costs are not charged (§10 row 5);
- the paper comparison is labelled descriptive, with a different factor set and construction (§9.6, §10 row 9);
- P2 is described as a weak test;
- the registered episodes and decades are given;
- the desk part of the count is labelled uncheckable;
- the "What did not work" section is present (§9.7).

The following are missing: should-fix 1–3 and notes 5–6 below.

## 8. Findings, ranked

**Must fix:** none.

**Should fix** (all in README.md)

1. The §2.4 sentence in the first paragraph leaves out two items. §2.4 lists "the 1929–32 fall" (the note names only momentum's 1932 crash, a different item) and ends with "No episode was used to choose anything". §2.4 asks the first paragraph to repeat this disclosure. Add both, so the sentence matches `QUESTION.md` §3.1.
2. §10 row 6 says "the note says the early factors are built on a narrower universe (general knowledge)", meaning NYSE only before 1962. The note does not say it, yet P1 carries the largest d (+4.01% a year). Add one sentence, labelled general knowledge, beside the data-step finding that the headers describe NYSE, AMEX and NASDAQ.
3. §9.1 and §10 row 7 say that B3's h̄ uses the whole of H, "a look-ahead in the benchmark only, disclosed". The note defines B3 as "the rule's own average position" without naming the look-ahead, and does not say that the window row and the sub-windows use h̄ from H.

**Notes**

4. README, P2 paragraph: "about 2.4 to 2.6 times T1's full-history 0.37". The ratio is 0.870 / 0.370 = 2.35, so the range should read "2.3 to 2.6". This is the script's one numeric mismatch.
5. §6.1 says ties "are counted and reported". There are none in any factor, trial or cost case (`summary.json`), but the note does not say "no ties".
6. Two smaller disclosures are not in the note. §0 item 7 and §10 row 1: the raw snapshot is not committed, and a later download may give other numbers. §10 row 8: the no-skip formation is inferred from the paper's example. The full-precision CSVs are committed, which limits the first.
7. The DSR at N = 10, 31 and 595 reuses the three-trial variance of monthly Sharpe ratios (the code's convention, as in Study 008 review note 7). The convention is not decision-relevant here: C3 passes at N = 3 with 1.000, and T1 fails on C1.
8. trials.md's "code `eef348e`" is inferred from the commit order. `summary.json` records the run time but no commit hash. A `git rev-parse HEAD` field in later runners would make the claim checkable from the output alone.

## 9. Not checked (and why)

- The desk registry part of the programme count (595 − 31 = 564 rows, and the keyword search for an equity-factor trial): the registry is private and outside this repository. Only the public 31 was recounted.
- Whether the raw zips equal what the library served at 09:17:57Z: there was no network access. The check covers the zips against the manifest only.
- Not run: `reproduce.sh`, `data_step.py`, `programme_count.py`. Not read: the root README, BUILD_LOG, the design and code review records (beyond their headings), `tools/power_study010.txt` (the pre-registration's 0.870 / 0.964 were taken as typed), and the citations. The charts are not drawn yet and are out of scope.
- README.md was written in parallel; the version reviewed is the one committed in `4c3127b`. Any later edit needs the script rerun; the script prints the SHA-256 it read. The push of `4c3127b` was not checked.

## 10. How to rerun the reviewer's checks

From the study folder, with the three zips present in `data/raw/`:

```
../../.venv/bin/python review_recompute.py; ../../.venv/bin/python -m pytest -q
```

The script takes about 110 s, prints the 1,393-row table and exits 1 while should-fix 1 and note 4 stand. If a raw zip is missing, it says so and exits 2.
