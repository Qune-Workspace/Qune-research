# Study 010 shadow forward record (PREREGISTRATION.md §11)

Shadow only: the four factors are long-short portfolios outside the approved instruments, so there is no paper order and no paper sleeve.

- `positions.csv`: one row per forward month, trial and factor, appended by `python -m src.forward010 record --month YYYY-MM` from **the first release of the Kenneth French Data Library that contains month t − 1** (the code refuses any other release), never replaced. Each row carries the formation return at full precision, the position h (+1 / −1), the release, the three zips' SHA-256, the manifest's hash and download times, and the record time. The commit time in git is the evidence of when the row existed; rows committed after the first release that contains month t will be labelled "late" at scoring and still scored.
- `frozen_hbar.json`: B3's average positions per trial and factor, frozen from the history run (`results/history/summary.json`), never re-estimated.
- `releases/<YYYYMM>.json` and `releases/fetch_log.csv`: each later library release, downloaded once by `python -m src.forward010 fetch` and kept only if the three files name one new release; the zips go to `raw/<YYYYMM>/` (git-ignored), their URL, download time, SHA-256 and header lines to the json (committed). Every attempt, kept or refused, is a line in `fetch_log.csv`.
- `interim.json` (`python -m src.forward010 interim`): months recorded, months with a return, cumulative T and B3, mean d; no t-statistic and no verdict before the 60th month.
- Scoring (`python -m src.forward010 score --release YYYYMM`) after 60 holding months (2026-09 to 2031-08), once, from the first archived release that contains 2031-08, on each row as first committed and re-checked against its own release, with a vintage row; output `results/forward/score.json`. Over 60 months the record can detect only a Sharpe of d of about 1.27 at 80% power, so its verdict is worded as a low-power check. Code decisions: PREREGISTRATION.md §16 (2026-10-26).

First record: 2026-09 from release 202608 (the history snapshot, downloaded 2026-10-26 09:17:57Z), recorded 2026-10-26 before release 202609 was available to the desk.
