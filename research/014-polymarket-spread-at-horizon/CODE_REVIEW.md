# Study 014: separate-session code review of the engine, before `APPROVED` (§14 step 2 → step 4)

*2026-11-17, 12:18:54–12:27:51Z by the clock (the reviewer's own `date -u` lines). Reviewer: a separate Opus 5.5 session (the Tester agent), isolated and read-only, no network. It was briefed to check `src/reader.py`, `src/analysis.py`, `src/run.py`, `reproduce.sh`, `conftest.py` and `tests/*.py` at HEAD `78d7d17` against PREREGISTRATION.md in this priority: leak and scope paths (a field outside §5.3, a resolution file, a quote read before the gates, a per-market value in a committed output), the statistics of §9.1, §9.3 and §9.6 on hand-built examples, the refusal and once-only rules and the hash checks, the exclusion order and bins, test fidelity, and anything an outside reader would see as a defect. The hypothesis and the criteria were copied into its brief verbatim from this pre-registration (the lesson of Study 013's review, where a paraphrase stated H1 backwards). It opened nothing under `data/raw/` or `tools/data/` and no git-ignored row; its scratch scripts stayed under `/tmp/`; the tree was unchanged before and after (its report records `git status --short` empty at both ends and HEAD unchanged). The report was written to a file outside the repository and is reproduced below from there, unedited apart from this header and one redaction: the host's absolute repository path, which the leak scan's private denylist refuses, is written as `<repo>` wherever the reviewer quoted it (two lines in its Method section and its brief). Qune verified every must-fix against the source before taking it (the float subtraction 0.06 − 0.05 = 0.009999999999999995 < 0.01 reproduced on this host's Python 3.12.3; the stop-before-halt order, the per-day hash check and the absence of any write before the end read in `run.py` and `reader.py`; the union cluster count in `own_halts`) and recomputed the three-cluster sandwich (SE_cl = 4/√27, the engine's value to 1e-15, and Qune's own seven-row example to 5e-16 before the review). **Every must-fix and every should-fix was changed in the commit that carries this file**, each with a test that fails on `78d7d17` (checked in a scratch worktree at that commit with the new test files: 28 of 79 fail there, every must-fix's test among them; 79 pass on the fixed tree). Two departures from the reviewer's suggested fixes, both stated: the once-only marker is written after the sample file's hash check and after every snapshot has been verified, not before `read_sample`, so that every refusal still leaves nothing written (§5.1) while any death after the first quote is read leaves the marker; and a trial's half under ten markets publishes its counts and the sign of Δ̂ (what C4 reads), the reviewer's own suggestion for that case. The fourteen precisions the fixes needed are dated in PREREGISTRATION.md §16; no bin, bar, trial or criterion changed, and nothing of this study has been computed.*

---

# Study 014: separate-session code review of the analysis engine (HEAD 78d7d17)

Reviewer: Tester agent (Opus 5.5), separate session, read-only on the repository, no network. Files reviewed at HEAD 78d7d17: `src/reader.py`, `src/analysis.py`, `src/run.py`, `reproduce.sh`, `conftest.py`, `tests/*.py`, against `PREREGISTRATION.md` (§0, §5, §6, §9, §13, §14 read in full), `trials.md`, `DESIGN_REVIEW.md`, and Study 013's `src/data_step.py`, `src/score.py` (refusal lines), `collector.py` (field lines) and `PREREGISTRATION.md` §5.4 and §16. All the scratch scripts are in `/tmp/qr014-review-scratch/`. Paths below are relative to `research/014-polymarket-spread-at-horizon/` unless they say otherwise.

## Verdict

**Approve with changes.** The core statistics are correct, and I checked them by hand and against my own re-implementations. Δ̂ equals the difference of the bin means to 9e-16. The three-cluster sandwich matches my hand value 4/√27 to 0.0. The G/(G−1) factor is the only small-sample factor. The bootstrap matches an independent loop on the same generator exactly, and its 1 percent rule is right at the boundary. The power figures, C1–C4, the verdict precedence and the low-power label all match §9. The field lists match §5.3, and nothing in `src/` names or opens a resolution file. No quote is read before the APPROVED and data-step gates.

Seven defects must be fixed before `APPROVED`:

- The once-only rule can be dodged by a crash, or by a refusal that comes after every quote is read and every fit is computed.
- Snapshot hashes are not all checked before rows are read.
- The tick-floored share, which every verdict states, is wrong on one-tick quotes because of float subtraction. In a synthetic sample where every quote is exactly one tick wide, the run reports 0.568 longshot and 0.159 central where both should be 0.
- One-market and few-market cells (the high bin, the descriptive splits) put per-market values into the committed `summary.json`.
- When Study 013 both stops and halts on its price-field check, this study waits forever instead of halting.
- The §5.4 cluster floor is applied over both bins, where the document reads it per bin.
- The open-call test that §6.4 promises does not exist.

None of the seven needs a change to a rule. Each is a small code or test change, or, for must-fix 6, a dated §16 precision.

## Passed

- **Field scope (§5.1, §5.3).** `RECORD_FIELDS` (`src/reader.py:34`) is exactly the eight fields of §5.3. `END_FIELDS` is `id, endDate`. `SAMPLE_FIELDS` is the nine sample fields of §5.1, and `first_token` is not among them. Every snapshot row goes through `project` (`reader.py:60–65`), which refuses any other name before reading a value (`reader.py:183`, `:207`). In `run.py`, `classify_rows` reads only `eventIds`, `bestBid`, `bestAsk`, `orderPriceMinTickSize`, `liquidityNum`, `feesEnabled` and `endDate` from the projected row (`run.py:121–154`). Study 013's report is reduced to three keys (`reader.py:103–108`). Study 013's collector writes `eventIds` as a list of strings (`013/collector.py:181`). `decode_list` accepts that list as well as a JSON string.
- **No resolution file.** No module in `src/` names `status.jsonl`, `outcome.jsonl` or any forbidden field. I confirmed this with the test and by reading the three modules. There is no `open` of anything except the sample, the manifest, the data-step report, the snapshot log, `records.jsonl` files, `events.csv`, `trials.md` and the outputs. `src/` imports only its own `src` package, not Study 013's.
- **Gate order.** Nothing is read from Study 013's sample (which holds p) or from any snapshot before `APPROVED`, the `results/run` check, the data-step report, the manifest, the stop flag and the trials row (`run.py:272–278`). The refusal order in the docstring at `run.py:15–20` matches the code.
- **Committed outputs hold no market id.** `summary.json`, `deltas.csv`, `deciles.csv`, `verdict.md` and `input_manifest.json` carry counts, aggregates, event ids of followed events, and hashes. Market ids, clusters (which can be `market:<id>`) and per-market s go only to `results/rows.jsonl`. That file is git-ignored (`.gitignore:42`), and its SHA-256 is in the manifest (`run.py:363`). The per-market *values* that do leak are must-fix 4.
- **§6.2 variables.** The mid is `(bid + ask)/2` and equals Study 013's p bit for bit (013 `data_step.py:301`, same `as_float`, JSON round-trip). `row_as_recorded` checks bid and ask are in (0, 1), bid ≤ ask, and |mid − p| ≤ 1e-9 (`analysis.py:108–115`). A locked book (0.05/0.05, tick 0.01) gives s = 0.2. A null tick reads 0.001. A tick of 0.0001 is kept and counted. The alternative floor of 0.01 changes null ticks only (`run.py:340`). The half-spread is q/2 × 100, not floored.
- **§6.3 bins on the mid rounded to nine places** (`analysis.py:58–71`). (0.55+0.65)/2 = 0.6000000000000001 → central. (0.051+0.149)/2 = 0.09999999999999999 → rounded 0.1 → no bin. (0.89+0.91)/2 = 0.9 → no bin. (0.85+0.95)/2 = 0.8999999999999999 → no bin. (0.009+0.011)/2 = 0.009999999999999998 → rounded 0.01 → longshot. Every edge in the parametrised test agrees with the rule.
- **§6.3 exclusion by any event id** on the snapshot-of-record row (`run.py:121–129`). The fixed pair 1292829 and 770450 match `pm-view/events.csv`. Later-followed events are counted apart and their ids named (`run.py:157`, `:303`). The order is: missing row → fixed events → later events → not as recorded → bins.
- **§9.1 OLS.** Δ̂ − (mean_L − mean_C) = 8.9e-16 on an unbalanced example (37 against 11 rows, 7 clusters). α̂ = mean_C. The fit's n counts the two decision bins.
- **§9.3 sandwich, by hand, three clusters.** A: (L=1, y=1), (L=0, y=0); B: (1, 2), (1, 4); C: (0, 1), (0, 3).
  - Δ̂ = 7/3 − 4/3 = 1 and α̂ = 4/3.
  - The residuals are −4/3, −4/3 | −1/3, 5/3 | −1/3, 5/3.
  - The scores are s_A = (−8/3, −4/3), s_B = (4/3, 4/3), s_C = (4/3, 0).
  - (XᵀX)⁻¹ = [[1/3, −1/3], [−1/3, 2/3]]. Its second row r gives r·s_g = 0, 4/9, −4/9, so Σ = 32/81.
  - × 3/2 gives V = 16/27, so SE_cl = 4/√27 = 0.769800358919501.
  - The code's value is 0.769800358919501 (difference 0.0). t_cl = 1.29904, as by hand.
  - SE_ordinary = √(84/9/4 · 2/3) = 1.247219 (code 1.247219128924647).
  - A Stata-style extra (n−1)/(n−k) factor would give 0.8607. The code does not apply one, and the existing HC0 test catches that factor (mutation "extra (n-1)/(n-k) factor": caught).
  - On a 48-row, 7-cluster example, the relative difference from my own independent sandwich is 4e-16.
- **§9.3 bootstrap.** 4 longshot-only and 16 central-only clusters, 2,000 resamples: the code gives (1.7537820098338008, 2.660004380495343) with 18 dropped. My independent loop on `default_rng(14)` gives the identical interval and 18 dropped. At the boundary, 1 dropped of 100 is available (exactly 1 percent is not "more than"), and 2 dropped of 115 is not. The bootstrap runs only for the W fits (`run.py:316`). The halves and splits carry Wald ± 1.96 · SE_cl.
- **§9.3 no fit** on an empty bin, G < 2, or SE_cl exactly 0. The numerical-zero case is should-fix 1.
- **§9.6 power.** For SE = 0.2: 0.5684, 0.5940 and 0.4972, and ratio = 0.48169 = 2.842 · 0.2 / 1.18. SE = 0.59/2.842 gives ratio 0.5000. The constants check against the normal distribution: 2 + z₀.₈ = 2.8416, 2.128 + z₀.₈ = 2.9696, 1.645 + z₀.₈ = 2.4865, z(1 − 0.05/3) = 2.12805, z(1 − 0.05/13) = 2.66529. ln(1300/400)/2 = 0.5893, so the bar is 0.59.
- **§9.5 criteria and verdicts** (`analysis.py:248–279`).
  - Δ̂ = 0.59 with t = 2.128 exactly passes C1–C3.
  - C4 needs both halves fitted and Δ̂ > 0. Δ̂ = 0 on a half fails.
  - 0 < Δ̂ < 0.59 gives the "below half the published size" text with Δ̂ and t_cl.
  - Δ̂ ≥ 0.59 with C4 failing gives "not supported".
  - An M1a row that is "not supported (no fit)" gives "inconclusive (fragile: Sports)".
  - The precedence is halted > not supported > fragile > supported.
  - The low-power label is added to all three rows when the M1 ratio > 0.50 (`run.py:323–327`).
  - "supported" always carries "in one forward window" and the dates of W.
  - `verdict.md` states the horizon, Study 013's floor (10,000 USDC, spread ≤ 0.10, which matches 013 `data_step.py:79–80`), the tick-floored share by bin and the Sports share.
- **[WA26] figures.** |p − σ(1.112 · logit p)| gives 1.353 points at 0.05, 0.0 at 0.50 and 1.085 at 0.60, as the document's "about 1.4 at 0.05, 1.1 at 0.60". b = 1.112 is Study 013's `PUBLISHED_B_WA26` (013 `score.py:71`).
- **Hash checks.** The sample file is checked against `sample_jsonl_sha256` before any row is parsed (`reader.py:121–126`). A snapshot of record is refused when it is unlogged (`reader.py:175`), missing (`:149`) or off its hash (`:152`). Study 013's manifest key and the data-step key names match 013 `data_step.py:529–546` and `:587`.
- **Refusal and once-only basics.** No APPROVED, an existing `results/run`, a missing report or manifest, the stop flag, a missing or count-less trials row, and a sample off its hash all refuse with nothing written (the existing test). A second run after any completed run or halt is refused. `_write` creates `results/run/` first with `exist_ok=False` (`run.py:357`), so a crash inside `_write` still blocks a re-run.
- **reproduce.sh** refuses without a non-empty APPROVED, with an existing `results/run`, and without the trials row. It runs `python -m src.run` from the study folder, and the default paths in `main` resolve to Study 013's folder and `pm-view/events.csv` correctly (`run.py:399–402`).
- **Tooling.** `pytest`: 59 passed. `ruff check --no-cache src tests`: all checks passed. `mypy src` under the repository's settings (`check_untyped_defs`, `warn_unreachable`, …): no issues.
- **Test fidelity: what the existing tests do catch** (mutation pass on `/tmp` copies, 55 tests, `test_power_tool.py` excluded because it reads the repository's `tools/`):
  - dropping G/(G−1)
  - adding (n−1)/(n−k)
  - removing the nine-place rounding
  - reading null ticks as 0.01
  - ignoring the price-field halt
  - skipping the sample hash check
  - dropping the below-half text
  - removing the SE_cl = 0 rule
- No test patches a module path or a default argument bound at import. The forbidden-string test is not vacuous: it asserts at least three modules and scans the real `src/`, which is the intended target.

## Must-fix

1. **A crash, or a late refusal, between reading the quotes and writing the outputs leaves no trace, so the "once" rule can be dodged.** `src/run.py:270–347`: nothing is written until `_write` (`run.py:347`, `:357`).
   - **Reproduce:** `/tmp/qr014-review-scratch/check_run.py` case D. Patch `run.decile_table` to raise `MemoryError` after the fits. `results/` is absent afterwards, and an immediate second `run_analysis` completes with "supported in one forward window".
   - The same holds for a `KeyboardInterrupt`, an out-of-memory error during the moved-end scan (about 45 files of about 1.7 GB each), or the late refusal of must-fix 2.
   - **Violates:** §0 item 14, §13 ("`--run` runs once") and §14 step 6. Study 013 fixed the same hole at its code review: 013 `PREREGISTRATION.md` §16, 2026-11-03 item (9) creates `results/score/started.txt` before the protected read.
   - **Fix:** create a marker (for instance `results/run/started.txt`, created with `exist_ok=False`) after the gates and before `reader.read_sample`, and make `_write` tolerate the existing directory.
   - **Test:** make `decile_table` raise inside `run_analysis`, then assert that a second call raises `Refusal` matching "executed once".

2. **Not every snapshot is hash-checked before rows are read, and a refusal can fire after the whole analysis has run.**
   - **First path:** the moved-end scan verifies each earlier snapshot only at `src/run.py:342–344` (via `src/reader.py:202`). That is after every snapshot-of-record row has been read, every quote classified and all 14 fits and the verdict computed.
   - **Second path:** `read_record_rows` verifies one day, reads its rows, then verifies the next (`reader.py:174–183`). Rows of earlier days are read before a later day's mismatch is found. The refusal message then says "refused, nothing read", which is false.
   - **Reproduce:** `check_run.py` case C: one off-hash file on 2026-11-05, which is not a snapshot of record. The run refuses after 14 `fit_rows` calls. After the operator restores the bytes, a second run goes through. Case G: the rows of 2026-11-10 are read before 2026-11-20 is found off its hash.
   - **Violates:** §5.1 ("each hashed against its line … before any row is read; a mismatch or a missing file refuses with nothing written") and §6.5. Study 013's data step verifies every in-window snapshot before reading any row (013 `data_step.py:388–396`).
   - **Fix:** compute the full list of snapshots the run will read (the record days, plus every logged day in [S, max(record days)]). Verify all of them before `read_sample`'s rows are used, or at least before `read_record_rows`, and record the "missing" days at that point.
   - **Test:** in the end-to-end builder, corrupt a non-record day in the range. Assert a `SnapshotHashMismatch` is raised with `reader._iter_rows` never called (spy) and nothing written.

3. **The tick-floored flag is decided on a float difference, so a quote exactly one tick wide is often counted as "floored".** `src/analysis.py:102` (`floored = q < tick`, where `q = ask − bid` is a float).
   - **Reproduce:** 0.06 − 0.05 = 0.009999999999999995 < 0.01. Of the 98 one-tick quotes on the 0.01 grid, 18 are flagged floored: 4 of the 9 longshot pairs and 3 of the 20 central pairs. At tick 0.001, 27 of 980 are flagged. `check_stats.py` section 4.
   - End to end (`check_run.py` case I), with every quote exactly one tick wide, `verdict.md` would state a tick-floored share of 0.568 longshot and 0.159 central. Both should be 0, and the error is biased towards the longshot bin.
   - **Violates:** §6.2 ("any q below the tick … is floored at the tick and counted"). The figure is named in every verdict (§9.5), reported by bin and decile (§9.6), and read for pitfall 1 (§10). s itself is unaffected to about 1e-15.
   - **Fix:** compare on decimal-rounded values, e.g. `round(q, 9) < round(tick, 9)` (the same nine places as §6.3).
   - **Test:** assert not floored for (0.05, 0.06), (0.02, 0.03) and (0.07, 0.08) at tick 0.01, and for (0.050, 0.051) at tick 0.001. The current test uses only 0.02 wide at tick 0.01, and the `q <= tick` mutation survives it.

4. **Per-market values reach the committed `summary.json` through cells and splits under ten markets.**
   - **High bin:** `high_bin_difference` (`src/run.py:247–257`) publishes `mean_ln_s_high` and the difference for any n. With one high-bin market (`check_run.py` case A), `mean_ln_s_high` is exactly that market's ln s, −3.8607297110405945, and the value appears in `summary.json`.
   - **Splits:** the early, before-D/after-D and null-tick-0.01 splits go through `fit_rows` (`run.py:335–341`) with no ten-market rule. A four-market early split (case B) publishes α̂ = the mean ln s of two named-by-position central markets, Δ̂, and an sd from two markets.
   - **Violates:** §9.6 last bullet ("A decile cell or a split with fewer than ten markets reports its count only"), and §13 ("never a per-market row") in effect.
   - **Fix:** apply `MIN_CELL` to the high-bin block (n_high < 10 → counts only) and to every descriptive split (n < 10 → n and G only). Separately, decide in writing whether W1/W2 of a trial count as "splits". They carry C4, so I would publish their counts and the sign only when n < 10.
   - **Test:** end to end with one high-bin market and a four-market early split. Assert those entries hold only `n`/`G`. The current "no per-market row" check (`tests/test_run.py:232–234`) looks only for the strings "L17" and "C17" and passes on both leaks.

5. **When Study 013 both stops and halts on its price-field check, this study waits forever instead of halting.** `src/run.py:93` refuses on `stopped_for_amendment` before `run.py:289` tests `price_field_pass`.
   - Study 013 writes both flags when both fire ("a halt wins when both fire", 013 `data_step.py:30–31`). It never re-runs after a halt (013 `data_step.py:378–379`), so the stop flag is never cleared.
   - **Reproduce:** `check_run2.py` case J, with `{"stopped_for_amendment": true, "halted": true, "price_field_check": {"pass": false}}` → "refused: … this study waits (§5.4)".
   - **Violates:** §5.4 (a failed price-field check "halts permanently") and §9.5 precedence ("halted > …").
   - **Fix:** test `price_field_pass` before the stop flag, still after the manifest-exists check.
   - **Test:** the input above → `halted` true, verdict "inconclusive (halted: the quote fields do not mean what both documents say)".

6. **The §5.4 cluster floor is computed over both bins together, where the document reads it per bin.** `src/run.py:194–198` (`g` counts clusters over the union of the two bins).
   - §5.4: "fewer than **100 clusters or fewer than 200 markets in either decision bin**". The document's own reasons are per bin: "a bin median rest on fewer than a hundred independent events", and the one-bin crossings at "146 central clusters" and "277 longshot clusters". The design-review draft wording was "100 clusters in either decision bin" (`DESIGN_REVIEW.md` should-fix 1).
   - **Reproduce:** `check_run2.py` case K: 110 longshot clusters and 20 central clusters, G = 130 → no halt. The per-bin reading halts.
   - **Fix:** count G per decision bin and halt when either is below 100. If the author holds the union reading, write it as a dated §16 precision before `APPROVED`, because a permanent halt rule must not be read after the counts are known.
   - **Test:** case K, plus the 99/100 cluster boundary on each bin. The "clusters floor 50" mutation survives the current suite.

7. **The open-call test that §6.4 promises is missing.** `tests/test_no_outcome.py:8–19` checks the modules' text only.
   - §6.4: "nothing in `src/` opens `status.jsonl` or `outcome.jsonl` (a test asserts it on each module's text **and on its open calls**)". A name assembled from parts (`"status" + ".jsonl"`) would pass the text test.
   - **Fix (test only):** run the end-to-end `run_analysis` with `status.jsonl` and `outcome.jsonl` present in the synthetic Study 013 folder, and with `builtins.open`, `io.open` and `pathlib.Path.open` patched to raise on any path whose name is one of those two. Study 013 has the same guard for its data step (013 `data_step.py:4–7`).

## Should-fix

1. **SE_cl "0" is tested as an exact float zero** (`src/analysis.py:172`, `:178`). A sandwich that is zero in exact arithmetic comes out at 6.3e-16. The fit is then "fitted" with t_cl = −9.85e13: two clusters, each bin at one repeated ln s, k = 2 per bin (`check_stats.py` section 3). A positive degenerate case would pass C2 and C3. The existing test passes only because −1 and −3 have exact means. **Violates:** §9.3 "no fit". **Fix:** treat SE_cl ≤ 1e-12 · max(1, |Δ̂|) as 0. **Test:** the repeated-ln(0.001/0.05) case.
2. **A missing `events.csv` is silently read as "no later-followed events"** (`src/reader.py:217–218`; `check_run.py` case E ran and excluded nothing). The file is committed, so its absence means a wrong path. **Violates:** §6.3. **Fix:** refuse.
3. **An event with `followed_from` equal to the run date is not excluded** (`src/reader.py:229`, `since < before`; case H). The desk may read books on the morning of the run. **Violates:** §6.3 "before the analysis run". **Fix:** use `<=`, or record the reading.
4. **A Study 013 re-run under a dated amendment that still reports `stopped_for_amendment: true` makes this study refuse for good** (`src/run.py:93`; case F). Study 013's own scoring run proceeds in that case (013 `score.py:276`). §5.4 says the study refuses only when 013 "has not been re-run under a dated amendment", which the three keys of §0 item 15 cannot tell. A dated §16 precision is needed either way: read 013's `amendment` key as a fourth key, or state that 013's re-run must clear the flag.
5. **G per decision bin is not reported.** `src/analysis.py:118–131` and `src/run.py:59` carry only the total G. **Violates:** §9.6 first bullet ("n and G in each decision bin"). This goes together with must-fix 6.
6. **Boundary tests are missing.** These mutations all survive the suite (`mutate.py`):
   - the bootstrap threshold set anywhere up to 40 percent, or `<` for `<=`
   - the not-as-recorded share at 2 percent, or its base without missing rows
   - the market floor at 100, or the cluster floor at 50
   - the low-power ratio at 0.60, or no label on the companions
   - C4 with Δ̂ ≥ 0
   - K = 2.5 for 2.486
   - Wald z = 2.0
   - `MID_TOL` = 1e-6
   - `MIN_CELL` = 5
   - before-D with `<=`
   - the moved-end scan starting at S0 (2026-11-02)
   - the bootstrap run on the halves

   Add one boundary test each, for example 20 and 21 dropped of 2,000, 4 and 5 not-as-recorded rows of 440, ratio 0.50 and 0.5001, Δ̂ = 0 on a half, and a 2026-11-02 listing that must be ignored.
7. **Exclusion counts lose their §9.6 order.** `summary.json` is written with `sort_keys=True` (`src/run.py:365`), and `verdict.md` lists no exclusion count. "Not as recorded" is counted before "outside the decision bins" (`run.py:130–145`). That order is forced, because a bin needs a valid mid, but it is the reverse of §9.6's list. Write the counts in §9.6's order and state the forced swap.
8. **Decile labels read 0.0 and 1.0.** `src/analysis.py:52` and `src/run.py:223` label the first and last decile [0.0, 0.1) and [0.9, 1.0]. The document's labels are [0.01, 0.10) and [0.90, 0.99]. The content is the same, because 013's p is in [0.01, 0.99] (013 `data_step.py:81`).
9. **`input_manifest.json` does not hash every file the run read** (`src/run.py:279–285`). `events.csv` decides the later-followed exclusion, and `trials.md` and `APPROVED` gate the run. Add their SHA-256s.
10. **`conftest.py:1–2` is stale.** It says "so that ``import collector`` works (the convention of Studies 009-011)", but Study 014 has no collector.
11. **The document is inconsistent on the field count.** `PREREGISTRATION.md` §5.1 (line 75: "the seven fields of §5.3") and §6.5 (line 115: "the seven fields") disagree with §5.3 ("Eight fields", `id` included). The code follows §5.3. Correct the two lines in a dated precision.
12. **The shell's refusal order differs from `run.py`'s docstring.** `reproduce.sh:37–40` checks the trials row before Study 013's inputs are looked at. This is harmless, but the docstring and the shell should state one order.

## Open decisions

- **The `N_programme = <int>` requirement on the analysis-run row, with refusal without it** (`run.py:72–82`): consistent with §9.4 ("re-counted immediately before the analysis run and written to `trials.md`") and §14 step 5. The ≥ 3 check is a sensible sanity bar. Accepted.
- **The "row not as recorded" base = M1 rows after the followed-event exclusion plus rows whose record is missing** (`run.py:191`): consistent. A missing-record row cannot be tested for a followed event, so it stays in "the C1 rows after the followed-event exclusion". Counting it in both the base and the numerator is the faithful reading of §5.4. Accepted. Its tests are missing (should-fix 6).
- **The moved-end scan over every logged snapshot from S = 2026-11-03 to the latest snapshot of record, `id` and `endDate` only, a missing file named "missing" and skipped** (`reader.py:187–209`, `run.py:342–346`): consistent with §0 item 12 and §9.6. Keeping 2026-11-02 out is right. Skipping a missing file is acceptable for a descriptive count, but the result should state how many markets could have had their first listing on a missing day. Not acceptable as written: the hash check happens after the analysis (must-fix 2).
- **The decile table, secondary reading, high-bin difference, early and before-D/after-D splits and alternative-floor fit computed on the M1 rows**: consistent. §9.6 names M1 for the alternative floor and leaves the others unnamed. M1 is the headline trial, and Study 013 did the same for its descriptive splits. Accepted. Say so in the output.
- **A fit's n counts the two decision bins only**: consistent with §9.1 ("over the rows of the two bins only") and §9.6. Accepted. The per-bin G is missing (should-fix 5).
- **The author's three corrected test expectations:**
  - **(0.051 + 0.149)/2 → 0.100, outside the longshot bin:** correct. §6.3 introduces the rounding precisely because this float wrongly entered the bin (`DESIGN_REVIEW.md` should-fix 2). The true mid is 0.100, which `mid < 0.10` excludes.
  - **[WA26] compression near 0 at a central median mid near 0.50, with 1.1 the figure at 0.60:** correct. σ(1.112 · logit 0.5) = 0.5 exactly, so the compression is 0. The document's "1.1 at 0.60" is an example price, not the central bin's value. Evaluating at the bin's median mid is a defensible reading of "at that price". The note should say the central bin's figure is about 0 by the model's symmetry. It should also say that the [CR26] "clears" flag is judged at the lower end of its range (5.9) (`run.py:243`).
  - **The first listing may be the snapshot of record itself:** correct. §0 item 12 and §9.6 say "the first snapshot dated on or after S that lists them", and every sampled market is listed on its snapshot of record, so that day is a valid first listing and reads "unmoved".

## Method

All times are UTC, from `date -u`: start **Tue Nov 17 12:18:54 UTC 2026**, end **Tue Nov 17 12:27:51 UTC 2026**.

`git -C <repo> status --short` at the start: empty output (clean), exit 0. HEAD was `78d7d17c276360e4ad3b7d6cb7c46f60851b8e46`.
`git -C <repo> status --short` at the end: empty output (clean), exit 0. HEAD was still `78d7d17`.

I ran no writing git command. No file under the repository was created or changed: pytest ran with `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`, ruff with `--no-cache`, and mypy with its cache in `/tmp`. I did not open any of the following: `013/data/raw/`, `tools/data/`, any `sample.jsonl`, `rows.jsonl`, `records.jsonl`, `status.jsonl` or `outcome.jsonl`. Of `paper-log/snapshots.csv` I read only the header, the first two lines and the date column. I used no network.

Commands, each with its exit code:

| Command (cwd) | Exit |
|---|---|
| `date -u; git status --short; git rev-parse HEAD; mkdir -p /tmp/qr014-review-scratch; ls; wc -l …` (study dir) | 0 |
| `cat -n reproduce.sh conftest.py trials.md tests/*.py`; `Read` of `PREREGISTRATION.md`, `src/*.py` | 0 |
| `sed`/`grep` over 013 `src/data_step.py`, `src/score.py`, `PREREGISTRATION.md`, `collector.py`, `.gitignore`, `pyproject.toml`, `DESIGN_REVIEW.md`, `pm-view/events.csv`, `paper-log/snapshots.csv` (head and date column) | 0 |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` (study dir) → 59 passed | 0 |
| `.venv/bin/python -m ruff check --no-cache src tests` (study dir) → All checks passed | 0 |
| `.venv/bin/python -m mypy --cache-dir=/tmp/qr014-review-scratch/mypy_cache src` (study dir) → no issues in 4 files | 0 |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/qr014-review-scratch/check_stats.py` (hand sandwich, bin pairs, floored flag, bootstrap re-implementation and boundary, power, criteria) | 0 |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/qr014-review-scratch/check_run.py` (cases A–I on synthetic folders under `/tmp/qr014-review-scratch/runs/`, built with the tests' own builders) | 0 |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/qr014-review-scratch/check_run2.py` (cases J, K) | 0 |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/qr014-review-scratch/mutate.py` (29 single mutations on copies under `/tmp/qr014-review-scratch/mut/`, pytest per copy without `test_power_tool.py`) | 0 |
| `date -u; git status --short; git rev-parse --short HEAD` | 0 |

Not checked: performance at real scale (the moved-end scan hashes and parses about 45 snapshots of about 1.7 GB each); the chart step (not yet written, §6.5); `tools/power_pm014.py` beyond its existing tests passing.
