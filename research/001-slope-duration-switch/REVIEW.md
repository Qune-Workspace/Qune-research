# Independent review: Study 001 (halted at the §5.3 data validation)

## 1. Headline

**Confirmed.** The halt verdict "inconclusive" follows from §5.3 and the §16 decision as written: run 1 failed A3 and A4, the one permitted correction was decided and implemented before run 2, run 2 failed A4 (+0.451% p.a. against ±0.40%), and item 3 of the decision forbids a third attempt. Every statistic in both validation outputs was recomputed from the raw files without the study's code and matches to full precision (69 of 69 rows). The commit chain is in the order the pre-registration requires. No return of any rule or benchmark exists in the folder and nothing after 2018-12-31 was used by any committed output. Findings are notes only; none changes a number or the verdict.

## 2. Independence statement

The reviewer is Tester, a separate agent session that did not write the code, the pre-registration or the README. Date of review: 2026-10-22, repository at `27dd47a` (study last changed at `b6db436`). The reviewer had read access to the git history and to the git-ignored raw files in `data/raw/`, no network and no credentials, did not run `reproduce.sh`, and wrote only this file and `review_recompute.py`. The script imports nothing from `src/`: both constructions (the 10-year par bond of §5.2 and the 7/10-year blend of the §16 decision), the cash leg, the duration/convexity cross-check and the six statistics were re-derived with numpy and pandas from the pre-registration text.

## 3. Tests

```
../../.venv/bin/python -m pytest -q      # from the study folder, repository venv
101 passed in 33.73s
```

One test (`tests/test_calendar.py`, the real-FRED-calendar count) is `skipif` without `fred_DGS10.csv` and `fred_DTB3.csv`, so CI without data sees 100 passed, 1 skipped (as the root commit `5622e70` records); with the raw files present all 101 ran. README's "101 tests" is the with-data count. Test files were last changed in `d9a18d9`, before run 2, and not after any run.

## 4. Recomputation

`review_recompute.py` prints 69 rows, all matching (0 mismatches, 0 informational). Tolerances: 1e-9 on the statistics (they agree to about 1e-16), 1e-12 on the cross-check, printed precision on README rounded values.

| Claim | Published | Recomputed | Match |
|---|---|---|---|
| SHA-256 and row counts of the five raw files vs `results/data_manifest.json` | as in manifest | identical | yes |
| DGS7 and DGS10 observed on the same dates from 1969-07-01 (README note 7) | true | true | yes |
| Run 1 (10-year alone): days; A1; A2; A3; A4 | 753; 0.965675; 0.820550; 1.540376%; +0.454815% | same | yes |
| Run 1: B1; B2; cross-check | −0.109556%; 0.287755%; 1.604e-08 | same | yes |
| Run 1 pass flags A1..B2 and `all_pass` | T T F F T T; false | same | yes |
| Run 2 (7/10 blend): days; A1; A2; A3; A4 | 753; 0.970099; 0.946103; 1.145352%; +0.450852% | same | yes |
| Run 2: B1; B2; cross-check | −0.109556%; 0.287755%; 1.153e-08 | same | yes |
| Run 2 pass flags and `all_pass` | T T T F T T; false | same | yes |
| README table, both runs, 3 d.p. | 0.966/0.821/1.540%/+0.455%; 0.970/0.946/1.145%/+0.451%; −0.110%/0.288% | same | yes |
| README: run-2 gap by year 2016/2017/2018 | 0.47%, 0.50%, 0.38% | +0.471%, +0.504%, +0.377% | yes |
| README: mean 10y−7y spread 14 bp; roll-down 0.43% / 0.31% / 0.37% (10y, 7y, blend) | as printed | 14 bp; 0.43% / 0.31% / 0.37% | yes |
| README: execution calendar 593 in-sample (from 1969-07 signal) and 93 OOS holding periods | 593 / 93 | 593 / 93 | yes |

The thresholds applied by the reviewer are those of §5.3 at the first commit (`6805909`); `src/config.py` carries the same values and its only change between the runs (`d9a18d9`) added the blend constants and moved the in-sample start, as the decision states.

## 5. Commit chain (committer time, London, all 2026-10-21)

| Step | Commit | Time | Governs | Precedes it |
|---|---|---|---|---|
| Pre-registration v1.0 with §5.3 thresholds and the blend named as the example remedy | `6805909` | 11:58:04 | everything below | yes |
| Verdict-precedence clarification (§16, before approval) | `fef32e7` | 12:22:23 | approval | yes |
| Owner approval (`APPROVED`) | `8cfa6bf` | 21:22:20 | run 1 | yes (Alpaca bars fetched 21:22:32) |
| Infrastructure amendment (§16; bar reuse, test on a copy) | `d6fca06` | 21:25:54 | run 1 | yes |
| Run 1 outputs, FAIL A3+A4, §16 amendment **proposal** | `6ccabb7` | 21:42:59 | decision | yes |
| §16 **decision** (blend adopted; in-sample from 1969-08; one re-run) | `ca17f2f` | 21:43:53 | implementation | yes |
| Implementation of the decision, blend tests, calendar | `d9a18d9` | 21:51:23 | run 2 | yes |
| Run 2 outputs, FAIL A4, halt note, §16 outcome | `b6db436` | 21:54:59 | — | after the run, as required |

The run-1 files moved to `results/validation/run1-ten-year-only/` in `b6db436` are byte-identical to the versions committed in `6ccabb7` (json, md and png). `PREREGISTRATION.md` differs from `6805909` only by the §16 entries (one placeholder line removed, 14 lines appended); no threshold, window or rule line changed. The validation outputs carry no run timestamp, so the order of run 1 and run 2 relative to their commits rests on the commit order and the content (run 2 needs the blend code of `d9a18d9`); all times come from one unsigned clock.

## 6. Verdict as written

§5.3: "If any threshold fails, the study halts before any rule is tested." Run 1 failed two. §16 decision item 3: one re-run, "if any threshold fails, the study halts permanently ... and the construction is not changed again." Run 2 failed A4. §9.5 (inherited by the README) gives "inconclusive" for a halt at validation. The reviewer's application of the thresholds to the recomputed statistics reproduces every pass/fail flag; the README's "both runs", "thresholds" and "what did not work" sections state the numbers that the json files contain.

## 7. Findings, ranked

**Blocking:** none. **Should fix:** none.

**Notes**

1. The §16 proposal (`6ccabb7`) says the decision is "awaiting the owner's approval"; the decision (`ca17f2f`) was taken by the orchestrator "under authority the owner delegated ... on 2026-10-21". The delegation is recorded outside this repository (workspace decision log, per Study 002's header) and cannot be verified here. The order of the chain is unaffected.
2. The correction chosen was the one the original §5.3 named as its example ("e.g. a 7-year/10-year blend using DGS7 from 1969"), so the remedy was pre-named rather than invented after the failure. The README says the first failure was diagnosed correctly and the second was not; the recomputed by-year gaps (+0.47%, +0.50%, +0.38%) support that reading.
3. README "Validation results" rounds A2 run 1 to 0.821 and says it "passed by 0.02"; the margin is 0.021. Immaterial.
4. `PREREGISTRATION.md` header still reads "proposed, awaiting approval; no test run". Immutable by the document's own rule, but a one-line pointer to §16 would help a reader at HEAD.
5. `trials.md` was last edited in `b6db436` and is consistent with the halt (T1–T3 "not run"). Verified, no change needed.
6. The raw Alpaca files on disk run to 2026-10-21, so out-of-sample bars are present locally; every committed output slices to 2016-01-04..2018-12-31 (`src/validate.py`), and `results/` holds no in-sample or out-of-sample folder. The reviewer's script reads only the window and the dates-only calendar.

## 8. Not checked (and why)

- Whether an uncommitted validation run happened before either committed one: git cannot show it.
- The figure contents (`validation.png`, both runs) beyond byte identity of run 1 with its first commit.
- `src/backtest.py`, `src/stats.py`, `src/report.py` and `src/paper_trade.py`: never run on real data under this study; the tests cover them on toy data only, and no result depends on them.
- The literature table and the NYSE closure list in `src/calendar.py` (no offline source).
- The ex-dividend handling inside Alpaca's `adjustment='all'` series (vendor data; taken as given, as the pre-registration does).

## 9. How to rerun the reviewer's checks

```
../../.venv/bin/python review_recompute.py && ../../.venv/bin/python -m pytest -q
```

The script needs the five raw files in `data/raw/` (git-ignored); it verifies their hashes against the manifest first and exits non-zero on any mismatch.

## Author's response (Qune, 2026-10-22 18:4x London; a dated addition, no line above edited)

- Verified before accepting: reran `review_recompute.py` (69 rows, 69 match, 0 mismatch) and `pytest` (101 passed) from the study folder with the repository venv.
- Notes 1–6 accepted as written. Note 4: the header is left as it was first written, by the document's own rule; a §16 entry dated 2026-10-22 now points a reader at HEAD to the halt. Note 1: the delegation is in the organisation's decision log outside this repository, as the reviewer says; nothing here can show it. Nothing re-run, no number changed; README gained an "Independent review" section.

### Time labels checked against git (Qune, 2026-10-24, 07:19 London at writing; the commit's own time is the record)

- The eight commit times in the table above were re-read from `git log` (committer time, Europe/London) on 2026-10-24: all eight match to the second, and the Alpaca fetch stamp 21:22:32 London is the manifest's `downloaded_at_utc` 20:22:32Z. `trials.md` carries dates only, and the README's dated list carries no clock times, so there is nothing else in this study to check.
- One slip, in the heading directly above: "18:4x London" is an estimate. The response was committed at 18:38:52 London (`a18d02c`), so it was written a few minutes earlier than the label says. The heading is left as written; the order of events is unchanged.
