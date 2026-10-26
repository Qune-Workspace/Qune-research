# Separate-session recomputation: tools/power_offduration.txt

Run 2026-10-26 06:2xZ, Opus 5.5, isolated session. Brief: recompute every figure from the committed monthly CSVs with its own script, outside the repository, before opening the published `.txt`; read only the docstring of `tools/power_offduration.py`, never run it; read-only on the repository; no network.

Timing note: the reviewer started before commit `9707d55` and reported the two files as untracked. The files it checked are byte-identical to `9707d55`. The should-fix changes below were made after its report and changed labels and added columns only. No figure it checked changed.

## Report (verbatim, one scratch path replaced by a placeholder)

All 74 figures in `tools/power_offduration.txt` match my independent recomputation, so there are no numeric mismatches. I computed everything from the committed CSVs before opening the .txt, using a scratch script at `<scratch>/check.py`. I read only the docstring of `tools/power_offduration.py`, never ran it, and changed nothing in the repo. As a cross-check, a Bartlett-6 NW I coded by hand gives the same ratios as the house `newey_west_mean` to 4 decimal places.

| figure | mine | published | match? |
|---|---|---|---|
| 003: n / t / Sharpe(d) / sd a yr / nw | 185 / 0.374 / 0.0924 / 2.46% / 0.9689 | 185 / 0.37 / 0.092 / 2.46% / 0.969 | yes |
| 004 | 180 / 0.647 / 0.1852 / 2.15% / 1.1080 | 180 / 0.65 / 0.185 / 2.15% / 1.108 | yes |
| 006 | 593 / 2.060 / 0.2822 / 3.20% / 0.9631 | 593 / 2.06 / 0.282 / 3.20% / 0.963 | yes |
| 007 | 534 / 2.102 / 0.3093 / 2.73% / 0.9815 | 534 / 2.10 / 0.309 / 2.73% / 0.981 | yes |
| 008 | 534 / 1.381 / 0.2267 / 2.49% / 1.0949 | 534 / 1.38 / 0.227 / 2.49% / 1.095 | yes |
| pool (006-008 inner join) | 534 / 2.169 / 0.3214 / 2.19% / 0.9885 | 534 / 2.17 / 0.321 / 2.19% / 0.989 | yes |
| largest nw ratio | 1.1080 (004) | 1.108 | yes |
| E1, N=180: S_MDE at nw 1.00 / nw high / x 0.321 / sd(d) for 2% bar / return MDE at sd 5/10/15% | 0.7338 / 0.8130 / 2.29 / 2.73% / 3.67 / 7.34 / 11.01% | 0.734 / 0.813 / 2.3x / 2.73% / same | yes |
| E2, N=273 | 0.5958 / 0.6602 / 1.86 / 3.36% / 2.98 / 5.96 / 8.94% | 0.596 / 0.660 / 1.9x / 3.36% / same | yes |
| F1, N=434 | 0.4726 / 0.5236 / 1.47 / 4.23% / 2.36 / 4.73 / 7.09% | 0.473 / 0.524 / 1.5x / 4.23% / same | yes |
| F2, N=1196 | 0.2847 / 0.3154 / 0.887 / 7.03% / 1.42 / 2.85 / 4.27% | 0.285 / 0.315 / 0.9x / 7.03% / same | yes |
| F3, N=1202 | 0.2840 / 0.3146 / 0.885 / 7.04% / 1.42 / 2.84 / 4.26% | 0.284 / 0.315 / 0.9x / 7.04% / same | yes |
| months to see Sharpe 0.20 / 0.321 / 0.50 / 0.75, nw 1.00 | 2423.1 / 940.6 / 387.7 / 172.3 | 2423 / 941 / 388 / 172 | yes |
| same, nw high | 2974.6 / 1154.7 / 475.9 / 211.53 | 2975 / 1155 / 476 / 212 | yes |

The month counts for the five samples (180, 273, 434, 1196, 1202) are correct inclusive counts.

**Method notes**

- **Must-fix:** none.
- **Should-fix:** the "x pool 0.321" and "2% bar needs sd(d) <=" columns are computed at nw 1.00 only, and only the return-MDE column says so. Label them. At nw high the sd(d) limits are 2.46%, 3.03%, 3.82%, 6.34% and 6.36%.
- **Should-fix:** "0.9x" for F2 and F3 overstates the margin. It is 0.887 at nw 1.00 but 0.98 at nw high, so the French US samples only just reach the pool edge. Show both values.
- **Should-fix:** calling 1.108 the "high case" implies a bound. It is the largest of six observed values, four of them below 1. A not-yet-fixed question with a slower or overlapping signal could have a larger ratio. Call it "largest observed".
- **Should-fix:** the 0.321 benchmark is a point estimate chosen in-sample, with a standard error of about 0.15 over 44.5 years. It is an anchor, not a target edge. A short caveat would help.
- **Fine:** S_MDE = K·nw/√(N/12) is correct in annual Sharpe units. t = SR_annual·√(N/12)/nw, so t ≥ K gives this formula.
- **Fine:** K = 2.0 + 0.842 is the standard normal-approximation power constant, and the t-distribution correction is negligible at N ≥ 180.
- **Fine:** months needed = 12(K·nw/S)² is consistent with the formula above.
- **Fine:** the published t values (0.37, 0.65, 2.06, 2.10, 1.38) and pool Sharpe 0.321 reproduce. Each d is the plain column difference, with no NaNs or duplicate months.

`tools/power_offduration.py` and `tools/power_offduration.txt` are both still untracked in git, not committed.

## Responses (all four should-fix taken before the agenda text was committed)

| Point | Response |
|---|---|
| Columns computed at nw 1.00 only | Both columns now show nw 1.00 / largest observed nw (script and `.txt`; agenda table). |
| "0.9x" overstates the margin | Shown as 0.88–0.89× / 0.98×. The agenda and front page say the US history reaches an edge of the observed size "only just". |
| "High case" implies a bound | Renamed "largest observed", with the note that it is not a bound. |
| 0.321 is an in-sample anchor | Caveat added in the `.txt` and the agenda: a point estimate with a standard error of about 0.15, an anchor rather than a target. |
