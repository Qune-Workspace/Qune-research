# Study 010 shadow forward record (PREREGISTRATION.md §11)

Shadow only: the four factors are long-short portfolios outside the approved instruments, so there is no paper order and no paper sleeve.

- `positions.csv`: one row per forward month, trial and factor, appended by `python -m src.forward010 record --month YYYY-MM` from **the first release of the Kenneth French Data Library that contains month t − 1** (the code refuses any other release), never replaced. Each row carries the formation return at full precision, the position h (+1 / −1), the release, the three zips' SHA-256, the manifest's hash and download times, and the record time. The commit time in git is the evidence of when the row existed; rows committed after the first release that contains month t will be labelled "late" at scoring and still scored.
- `frozen_hbar.json`: B3's average positions per trial and factor, frozen from the history run (`results/history/summary.json`), never re-estimated.
- Scoring after 60 holding months, from one release named at scoring, with a vintage row (§11). Over 60 months the record can detect only a Sharpe of d of about 1.27 at 80% power, so its verdict will be worded as a low-power check. The scoring code (part 2) is not built yet.

First record: 2026-09 from release 202608 (the history snapshot, downloaded 2026-10-26 09:17:57Z), recorded 2026-10-26 before release 202609 was available to the desk.
