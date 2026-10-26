# Study 011: separate-session code review, before `APPROVED`

*2026-10-26, 15:3x–15:4xZ by the clock. Reviewer: a separate Opus 5.5 session, isolated, read-only in the repository (scratch scripts outside it), briefed to check `src/rule.py`, `src/stats011.py`, `src/data.py`, `src/history.py`, `programme_count.py`, `reproduce.sh`, `data_step.py` and the tests against PREREGISTRATION.md §5–§9 and §14, and told not to open the real industry files or run the history. It read no real industry value and changed nothing. Summary below is Qune's; every must-fix and should-fix was taken in the commit that adds this file. `APPROVED` is not yet written.*

## Verdict: pass with fixes

## Passed (reviewer's own code on synthetic data)

- §6.1 formation (no skipped month; a missing value makes an industry ineligible for exactly the next F rankings), the sort key (−round(R, 10), column index), W/L, n.
- §6.2 cohorts and timing: a brute-force version matched `run` to 1e-12 on d_gross, turnover, d_base and d_stress for M1, M1a and M1b, with planted missing values and ties; a shock in month m first moves d in m + 1; first holding months 1927-06 and 1927-12; no off-by-one.
- §6.3 costs: netted weights, Σ|Δw| from zero weights at entry, straight through the 1963–1995 gap (no re-entry in 1995-08), 0.10 / 0.50 in percent units, empty-leg cohorts keep their weights.
- §6.5 and the loader: only the value-weighted monthly section is read; markers become NaN; a synthetic zip round-tripped exactly.
- §9.3: a hand loop of the two-stretch Newey–West matched `newey_west_stretches` to 2e-16; on one stretch it equals statsmodels; other rows use the ordinary estimator.
- §9.4–§9.5: an independent DSR at N = 3 matched exactly; C1–C4, window slices (433, 373, 385; full 1,191 / 1,185), the window row, precedence and the return-unit label checked.
- Gates: with the loader stubbed, every refusal (APPROVED, existing `results/history`, `.history_tmp`, programme count, `trials.md` row) fired with zero load calls; outputs are written to a temporary folder and renamed.

## Must-fix (fixed)

1. `src/history.py`: the `.history_tmp` marker was created only after the data were read and computed, so a crash in between left no marker and a re-run would have been allowed, against the run-once rule (Study 010's code has the same gap; it ran once without a crash, so no re-run happened there). Fix: the folder and a `STARTED` file are written before the first value is read; a test makes `load_industries` raise and checks that the marker stays and the next run refuses.

## Should-fix (taken)

2. The legs table (§9.6) gains an O row, with the two-stretch Newey–West.
3. Boundary near-ties are counted over every held ranking month (the first five cohorts of each trial were missed); `cohorts.json` carries the tie count per ranking month.
4. Tests: d = Σ wᵢ rᵢ now checked month by month on 17 industries; an empty-leg month keeps turnover at zero; a misleading test comment corrected.
5. The data step's eligibility summary is copied into `summary.json`.

## Notes (recorded, no change)

- Choices the pre-registration leaves open, fixed here before any run: the twelve worst months are taken from base-cost d over the full history; `turnover_per_year` is over the full history; the episodes report sum and mean (monthly values are in `monthly.csv`); DSR at N = 11 and at the programme counts uses the three-trial variance, as in Study 010.
- The code does not check that the programme count is fresh; the re-count is run and committed immediately before the history run (§14 step 5), as a process step.
