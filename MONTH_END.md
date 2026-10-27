# Month-end runbook: the forward records due after Friday 2026-10-30

The first forward month end for Studies 003–008 is Friday 2026-10-30 (the last NYSE trading day of October). The second records for Studies 010 and 011 come from the French library's release 202610, which needs October's returns. Every step below is run by the hourly loop from 2026-10-30 21:15 UTC; each study's own code refuses an early run, a second record for the same month and a backdated one. Records are committed and pushed in the run that writes them. A `wait:` line (the source has not posted the final day yet) is expected for a while and is followed by a re-run.

| Study | Record for October 2026 | Command (from the study folder) | Earliest | Inputs |
|---|---|---|---|---|
| 003 | decision record `paper-log/decisions/2026-10-30.json` (no order: the sleeve is not cleared) | `python -m paper.decide --signal-date 2026-10-30 --holding BIL --fetch` | 17:00 New York on 2026-10-30 | Alpaca daily bars |
| 004 | decision record | `./reproduce.sh --forward decide --signal-date 2026-10-30 --fetch` | 21:15 UTC on 2026-10-30 | Alpaca daily bars |
| 005 | decision record | `./reproduce.sh --forward decide --signal-date 2026-10-30 --fetch` | 21:15 UTC on 2026-10-30 | Alpaca daily bars, FRED CPI |
| 006 | decision record (wait log until FRED posts the 30th) | `./reproduce.sh --forward decide --signal-month 2026-10 --fetch` | 21:15 UTC on 2026-10-30 | FRED H.15 series (Alpaca bars only at the shadow step) |
| 007 | decision record (wait log as for 006) | `./reproduce.sh --forward decide --signal-month 2026-10 --fetch` | 21:15 UTC on 2026-10-30 | FRED H.15 series, Alpaca daily bars |
| 008 | decision record (wait log as for 006) | `./reproduce.sh --forward decide --signal-month 2026-10 --fetch` | 21:15 UTC on 2026-10-30 | FRED H.15 and CPI series, Alpaca daily bars |
| 009 | none: it scores the 006–008 shadow records once, later | — | — | — |
| 010 | position record 2026-11 from release 202610 | `python -m src.forward010 fetch`, then `record --month 2026-11 ...` once the release is kept | the library's update after 2026-10-30 | French Data Library |
| 011 | cohort record 2026-11 from release 202610 | `python -m src.forward011 fetch`, then `record --month 2026-11 ...` once the release is kept | as for 010 | French Data Library |

No shadow line is due for October: each study's first shadow line follows its second decision record (the 2026-11 month end). Timing rules, wait logs and late tests are in each study's `paper-log/README.md`. Alpaca credentials come from the environment only (`APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`); a private wrapper on the desk's server loads the desk's paper market-data keys for the run. No key is in this repository.

## Pre-flight check, 2026-10-27 20:18–20:19 UTC (observed)

Run before the window so that a broken fetch does not surface on Friday night. Nothing was written to the repository (git status, including ignored files, was the same before and after), and no October value was read.

- Alpaca: one bars request for IEF over 2026-09-01 to 2026-09-30 with the run's credentials, into a temporary folder that was then deleted: 21 daily bars, 2026-09-01 to 2026-09-30.
- FRED: one request for DGS10 ending 2026-09-30, not kept: HTTP 200, last date 2026-09-30.
- Studies 004–008: `./reproduce.sh --forward decide ... --dry-run` for October on the real clock. Each refused as designed: 004 and 005 "before 21:15 UTC on the signal date", 006–008 "before 2026-10-30T21:15:00Z: the month's last H.15 release is not out".
- Studies 003, 010 and 011: the forward modules import in the project environment (003's decide needs fetched bars, so it has no dry run before the fetch).
- One error of the check itself, disclosed: the first attempt called the 004/005 modules outside `reproduce.sh` and failed on the import path that `reproduce.sh` sets; the check was changed to go through each study's `reproduce.sh`, the path the run uses, and passed.

What this does not show: that the decide steps work on October's data. That is first observed on Friday's run.
