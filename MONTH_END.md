# Month-end runbook: the forward records due after Friday 2026-10-30

The first forward month end for Studies 003–008 is Friday 2026-10-30 (the last NYSE trading day of October). The second records for Studies 010 and 011 come from the French library's release 202610, which needs October's returns. Every step below is run by the hourly loop from 2026-10-30 21:15 UTC; each study's own code refuses an early run, a second record for the same month and a backdated one. Records are committed and pushed in the run that writes them. After every fetch attempt or record, `make dashboard` is run and its output committed with it; `make lint` and CI fail otherwise ([`tools/check_dashboard.py`](tools/check_dashboard.py), added 2026-10-28 after the dashboard was found a day stale). A `wait:` line (the source has not posted the final day yet) is expected for a while and is followed by a re-run.

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

## Pre-flight re-run, 2026-10-28 about 14:16–14:17 UTC (observed)

Same script, same checks, two days before the window, because about 30 commits had landed since the first check. None of them touched a study's `src/`, `paper/` or `reproduce.sh`, the shared library or the pinned requirements (`git diff --stat f54e0dd..387f245` on those paths: empty). Every step exited as on 2026-10-27: the Alpaca IEF 2026-09 bars request and the FRED DGS10 request to 2026-09-30 exit 0 (into a temporary folder that was deleted, not kept); 003, 010 and 011 import; 004–008 refuse on the real clock with the same messages as above (step times 14:17:02Z–14:17:13Z). Git status, including ignored files, was unchanged. The bar and row counts of the two fetches were not kept this time (the run's log buffer kept only the later lines), so only their exit codes are stated. No October value was read.

## What happened, 2026-10-30 to 2026-10-31 (observed)

No run fell between the gate (21:15 UTC on 30 October) and 00:15 UTC on 31 October. At about 16:50 UTC on 30 October the loop's cadence changed from hourly to four runs a day (00:15, 06:15, 12:15, 18:15 London) at the owner's instruction, to stop a slide into polishing; this runbook's "every step is run by the hourly loop" stopped being true at that moment and nothing re-pointed the steps at the new schedule. The 00:15 run worked a queue item and did not check what was due. The records were written by the 06:15 run on 31 October (`month-end.sh run 2026-10 2026-10-30 BIL`, step times 06:18:34Z to 06:19:06Z, commit `5b0a24f`): Studies 003, 004 and 005 decision records for signal date 2026-10-30 (the same daily bars as on Friday night: no bar exists after the signal date, and the execution date 2026-11-02 is unchanged, so the delay gained no information); Studies 006, 007 and 008 wait lines (FRED's DGS10 had no row for 30 October yet; re-run each run until the row appears, deadline 21:00 UTC on 2026-11-04); Studies 010 and 011 fetch checks (release 202609, nothing kept). The pre-flight on the real clock, run first at 06:18Z, found that 006 and 007 crash with a traceback instead of a clean refusal when `--dry-run` is used without fetched inputs (008 refuses cleanly); noted, not fixed this run.

The 12:15 run on 31 October re-checked 006, 007 and 008 at 12:19 UTC (the wrapper's `wait 2026-10` step, which runs only the studies whose month is `waiting` and the 010/011 fetch checks, never a written month twice): still waiting, FRED's DGS10 has no row for 30 October; 010 and 011 still on release 202609. The same run fixed the 006/007 crash: both now refuse with exit 1 and no write when a forward or frozen input is missing, with a test in each study ([research/POST_MORTEMS.md](research/POST_MORTEMS.md), "A refusal fixed in the newest copy only").

Change: [`tools/check_due.py`](tools/check_due.py) (in `make lint` and the CI lint job) computes what is due from the NYSE calendar and the committed files (the 003–008 monthly records with their deadlines, the weekly desk view, every call past its due date, the state of 010 and 011) and exits 1 once a record is past its deadline without a logged miss; every loop run starts with it and works a DUE or OVERDUE line before anything else. Post-mortem: [research/POST_MORTEMS.md](research/POST_MORTEMS.md), "The slip of 26–30 October".
