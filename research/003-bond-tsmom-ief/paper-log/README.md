# Forward record folder of Study 003 (paper sleeve; rules in `../paper/README.md`)

**Label: paper record of a not-supported rule.** This folder holds only what the forward code writes, once a month and never rewritten. The rules, the pieces and their status are in [`../paper/README.md`](../paper/README.md) (PREREGISTRATION.md §11–12); Independent Risk's decision is [`../RISK_CLEARANCE.md`](../RISK_CLEARANCE.md), **NOT CLEARED** as of 2026-10-22, so no order can follow a record until that changes. First signal date **2026-10-30**, first execution date **2026-11-02**. Not advice.

| Path | Written by | Content |
|---|---|---|
| `decisions/<signal_date>.json` | `paper/decide.py`, after 17:00 New York on the signal date (refused earlier, nothing on disk) | the month-end decision record: `mom_t`, the target holding, input hashes, UTC time; a missing bar or a non-month-end date is written as a `signal unavailable` record |
| `executions/<signal_date>.json` | the desk's monthly runner (private workspace, Tester-reviewed), on the execution date inside 15:30–16:00 ET | the order record and fill; check-mode runs add a `-check-<stamp>` suffix |
| `runs.jsonl` | the runner, one line per invocation (`check`, `execute`, `stop-check`) | what it decided and why; the single line so far is the first check run of 2026-10-22, refused at the gates as expected |
| `stops.jsonl`, `state.json` | `run-monthly stop-check` (designed to run daily; built and unit-tested, not yet scheduled as of 2026-10-24, see `../paper/README.md` row "Stop overlay") and the runner | the holding's close against the engine stop; the sleeve's state, written before every order is sent |
| `manifest.json`, `raw/` | `paper/decide.py --fetch` | row counts and SHA-256 of the fetched bars; `raw/` is git-ignored |
| `summary.csv` | not yet: the §11.5 monthly summary (equity, holding, return, cumulative slippage, same-dated B0/B1/B3) is **designed, not built** | |

`dashboard/README.md` at the repository root counts these files as committed and will draw the sleeve's equity once `summary.csv` exists. Nothing in this folder is a backtest, and nothing here changes the study's results or verdict. (Pointer file added 2026-10-24 11:18 London so that the dashboard's "each study's `paper-log/README.md`" resolves for all three studies.)
