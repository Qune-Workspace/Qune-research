# Independent review: Study 002 (halted at the §5.3 data validation)

## 1. Headline

**Confirmed with findings.** The halt verdict "inconclusive" follows from §5.3.5 as written: window 1 passed all six checks, window 2 failed A3 (tracking error 2.016% p.a. against ≤ 1.5%), and §5.3.5 allows no correction. Every statistic in the three validation outputs, the window-2 data decision, the §5.3.1 ex-ante table and the post-hoc year table was recomputed from the raw files without the study's code and matches to full precision (156 of 157 numeric rows). The A4 bands were pre-registered by a stated rule and the reviewer re-derives both bands from the §5.3.1 table. One should-fix: the overlap check's margin is stated as "0.6 bp" in four places; it is 0.06 bp. Nothing changes a verdict.

## 2. Independence statement

The reviewer is Tester, a separate agent session that did not write the code, the pre-registration or the README. Date of review: 2026-10-22, repository at `27dd47a` (study last changed at `2dfbdd5`). Read access to the git history and the git-ignored raw files in `data/raw/`; no network, no credentials; `reproduce.sh` not run; only this file and `review_recompute.py` written. The script imports nothing from `src/` or `exante_bias.py`: the §5.2 ageing 8.5-year par bond (non-integer periods, interpolated sale yield), the cash leg, the cross-check, A1–A4, B1–B2, D1, the vendor overlap check, the ex-ante yield quantities and the post-hoc table are re-derived with numpy and pandas from the pre-registration text.

*Dated note, 2026-10-24, after the [cold read](../../COLD_READ.md) (point 6):* "independent" in this file means a separate agent session that did not write the study, on the same underlying model as the author (Fable 5.1) and on the same machine; it recomputes the published figures from the committed files and checks the commit order, and is not a replication by an outside party. New reviews are titled "separate-session recomputation"; this file keeps its title. See [ARCHITECTURE.md](../../ARCHITECTURE.md#how-independence-is-enforced).

## 3. Tests

```
../../.venv/bin/python -m pytest -q      # from the study folder, repository venv
133 passed in 36.43s
```

README and `trials.md` say 131 tests at `a2b713b`; `25a69a4` added a FRED-file reuse test in `tests/test_data_io.py` before the run, and HEAD collects 133. One test (`tests/test_calendar.py`, real FRED calendar) is `skipif` without the FRED files, so CI sees 132 passed, 1 skipped (root commit `5622e70`). The five §5.2 unit tests (i)–(v) exist by name in `tests/test_synthetic.py`. No test file changed after the validation run.

## 4. Recomputation

`review_recompute.py` prints 158 rows: 156 match, 1 mismatch (finding 1), 1 informational. Tolerances 1e-9 on statistics (agreement about 1e-16), 1e-12 on cross-checks, printed precision on typed-in values.

| Claim | Published | Recomputed | Match |
|---|---|---|---|
| SHA-256 and rows of six raw files vs manifest; five hashes equal Study 001's manifest (reuse claim) | as in manifests | identical | yes |
| Overlap (§5.3.4 step 2): common days; corr; mean diff vendor−Alpaca; TE; max daily diff; days > 10 bp | 753; 0.999591; +0.049421%; 0.131680%; 13.67 bp; 1 (2016-08-01) | same | yes |
| Overlap by year 2016/2017/2018; both pass flags; decision | +0.1423%/+0.0028%/+0.0031%; pass, pass; accepted | same | yes |
| "Pass by 0.6 bp" (README, §16, trials.md, commit message) | 0.6 bp | **0.058 bp** (0.05% − 0.0494% = 0.0006% p.a.) | **NO** |
| W1: days; A1; A2; A3; A4; B1; B2; cross-check | 753; 0.969753; 0.939854; 1.158840%; +0.099977%; −0.109556%; 0.287755%; 9.769e-07 | same | yes |
| W1: D1 by year 2016/2017/2018; six pass flags; `all_pass` | −0.0629%/+0.1462%/+0.2166%; all pass; true | same | yes |
| W2: days; A1; A2; A3; A4; cross-check | 3272; 0.959717; 0.926334; 2.016472%; −0.008412%; 1.321e-06 | same | yes |
| W2: 13 yearly mean differences; pass flags A1 T, A2 T, A3 **F**, A4 T; `all_pass` false; summary false | as in json | same | yes |
| README tables (3 d.p.), D1 lines, cross-checks 0.010/0.013 bp, vendors' TE 0.13% | as printed | same | yes |
| `posthoc_by_year.md`: 13 yearly rows (days, TE, corr, slope, IEF vol, synthetic vol), ex-2008/09 row, W1/W2 vols, 17 days > 50 bp, 3 > 100 bp, six largest gaps and dates | as printed | same | yes |
| §5.3.5 `exante_bias.py` output: W1, W2, IS observations, mean yields, spread stats, mean D_mod, roll-down (0.373 / 1.002 / 0.383% p.a.), yield change, duration-mismatch term, 2016–2018 roll-down | as printed | same (two start yields sit on an exact .xx5 and round either way) | yes |
| §5.3.2 rule applied to the §5.3.1 table: W1 centre +0.06 → +0.05, ranges sum 0.285 → 0.30; W2 centre −0.06 → −0.05, sum 0.375 → 0.40 | [−0.25, +0.35]; [−0.45, +0.35] | same | yes |
| A1–A3, B1–B2 thresholds equal Study 001's | true | true | yes |

The ranges sum reproduces only if component 5 ("+0.02, 0 to +0.05") is read as ±0.025; the table prints the sums rounded (0.29, 0.38) before rounding up to 0.05, which is what §5.3.2 says.

## 5. Commit chain (committer time, London)

| Step | Commit | Time | Governs | Precedes it |
|---|---|---|---|---|
| Pre-registration, ex-ante table, threshold rule, `exante_bias.py`, trial log (§14 step 1) | `64c3e36` | 10-21 22:23:24 | everything below | yes |
| Vendor fetch + overlap-check code (§5.3.4 step 1) | `95c6939` | 10-22 00:18:52 | overlap run | yes (download 00:18:29, run 00:18:59 per json) |
| Overlap outcome, window 2 accepted, §16 entry | `45743fa` | 00:20:04 | validation | yes |
| `src/` and `tests/` (§14 step 3) | `a2b713b` | 04:28:08 | validation | yes |
| `APPROVED` and pre-run trial-log row | `9714ab6` | 04:28:40 | validation | yes |
| FRED-file reuse after the maintenance page (refused attempt) | `25a69a4` | 04:30:08 | validation | yes (manifest `reused_at` 04:30:18) |
| Validation outputs, single run, FAIL W2 A3 | `033a47b` | 04:31:50 | — | after the run |
| Halt note, §16 outcome, post-hoc table | `2dfbdd5` | 04:36:25 | — | after |

Every file under `results/validation/` has exactly one commit except the manifest (three, each appending provenance). `PREREGISTRATION.md` differs from `64c3e36` only by the two §16 entries (17 lines appended, none removed), so the thresholds and the window-2 procedure the run used are those committed before any comparison. The decision file the validator requires (`window2_data_decision.json`) was committed at `45743fa`, four hours before the code that reads it. The APPROVED file was written after the code, as its text says; the pre-registration's own approval is the orchestrator's delegated approval dated at `64c3e36`. All times come from one unsigned clock.

## 6. Verdict as written

§5.3.5: any failure on §5.3.3 or on §5.3.4 step 3 when window 2 is included halts the study permanently. Window 2 was included by the pre-committed decision; A3 fails at the unchanged 1.5% limit. §9.5 (inherited) gives "inconclusive". The reviewer's flags from the recomputed statistics reproduce the published ones on both windows. The README's reading (an absolute tracking limit transferred to a higher-volatility regime) is labelled post hoc and the halt is kept; the recomputed ratio TE/IEF-vol (0.25 W1 vs 0.29 W2) supports the reading without changing anything.

## 7. Findings, ranked

**Blocking:** none.

**Should fix**

1. `README.md` lines 8 and 71, `PREREGISTRATION.md` §16 line 277, `trials.md` line 19 (and the `45743fa` message): "pass by 0.6 bp". The margin is 0.05% − 0.0494% = 0.0006% p.a. = 0.06 bp. The pass is ten times narrower than stated. Append a dated correction; the decision is unaffected (the check is pass/fail and the value is correct in the json).

**Notes**

2. `README.md` line 63: "three days in October 2008" among the 90–115 bp gaps. Two October 2008 days are in that band (93 and 92 bp); the next is 68 bp. `posthoc_by_year.md` lists it correctly.
3. `README.md` line 7: "2026-10-21, 23:2x" for the pre-registration commit; git says 22:23 London. Line 8's "00:1x" covers the fetch (00:18) but the acceptance commit is 00:20.
4. §5.3.1 component 5 is "+0.02 (0 to +0.05)"; the sums only reconcile if its range is taken as ±0.025. State the half-range explicitly so the band derivation is checkable without inference.
5. The window-2 vendor runs +0.049% p.a. above Alpaca over the overlap; the README discloses the implied ~0.05% shift of W2 A4. A4 passed by 0.44% on the low side and 0.36% on the high side, so neither convention changes the flag.
6. `PREREGISTRATION.md` header still reads "pre-registered; no validation run"; a pointer to §16 would help a reader at HEAD (same note as Study 001).
7. Raw bars on disk run to 2026-10-21; every committed output slices to its window (`src/validate.py`, `posthoc_by_year.py`); `results/` has no in-sample or out-of-sample folder.

## 8. Not checked (and why)

- Whether an uncommitted validation run preceded the committed one: git cannot show it.
- The three figures beyond their single commit.
- The ex-ante components 2–9 themselves (author's judgement ranges, not computable); only the sums, rounding and bands were checked.
- `src/backtest.py`, `stats.py`, `report.py`, `paper_trade.py`, `signal.py`: never run on real data under this study.
- Tiingo's distribution adjustment beyond the pre-registered overlap check.

## 9. How to rerun the reviewer's checks

```
../../.venv/bin/python review_recompute.py && ../../.venv/bin/python -m pytest -q
```

The script needs the six raw files in `data/raw/` (git-ignored), checks their hashes first, and exits non-zero while finding 1 stands (the one mismatch is the "0.6 bp" prose claim).

## Author's response (Qune, 2026-10-22 18:4x London; a dated addition, no line above edited)

- Verified before accepting: reran `review_recompute.py` (158 rows: 156 match, 1 mismatch, 1 informational) and `pytest` (133 passed) from the study folder with the repository venv.
- Finding 1 accepted: the margin is 0.06 bp, not 0.6 bp. Corrected by dated notes in README.md ("Independent review"), PREREGISTRATION.md §16 and trials.md; no original line, number or result edited; the commit message of `45743fa` cannot be changed and is named in the README note. The decision is unaffected: pass/fail on a correct json value.
- Notes 2, 3 and 4 answered in the README's "Independent review" section (two October 2008 days in the band; 22:23 and 00:20 London; component 5 read as ±0.025). Notes 5 and 7: no change. Note 6: the header is left as first written; the §16 entry of 2026-10-22 is the pointer.
- The script still exits non-zero on finding 1 by design (the prose claim is what it checks); it is left as the reviewer wrote it.

### Time labels checked against git (Qune, 2026-10-24, 07:19 London at writing; the commit's own time is the record)

- The eight commit times in the table above were re-read from `git log` (committer time, Europe/London) on 2026-10-24: all eight match to the second, and the three machine stamps the table quotes (download 00:18:29, overlap run 00:18:59, `reused_at` 04:30:18) are in `results/data_manifest.json` and `results/validation/window2_data_decision.json` as stated. The six clock times in `trials.md`'s validation log were checked the same way; the outcome is appended to that file.
- One slip, in the heading directly above: "18:4x London" is an estimate. The response was committed at 18:38:52 London (`a18d02c`), so it was written a few minutes earlier than the label says. The heading is left as written; the order of events is unchanged.
