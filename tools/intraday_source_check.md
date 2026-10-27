# Intraday source check: SPY minute bars on the desk's paper market-data feed

Written 2026-10-27 from 22:1xZ by the clock, for the reopener in RESEARCH_AGENDA's pre-FOMC drift
addition ("a free intraday S&P 500 (or SPY) source covering 2011–2026 for the 2pm-to-2pm form").

**What was run.** A private probe script (it loads the paper-account market-data keys from a file
outside this repository; it is not published) asked Alpaca's market-data API (`/v2/stocks/SPY/bars`,
`adjustment=raw`) for SPY bars. It printed **bar counts and first/last timestamps only; no price was
printed, read or kept**. Nothing was written to this repository by the probe. Run 2026-10-27
22:16Z (output observed by Qune and copied below by hand).

**Minute bars, 13:30–21:00 UTC on the date shown** (count, first, last):

| feed | 2011-03-15 | 2013-06-19 | 2015-12-16 | 2015-12-30 | 2015-12-31 | 2016-01-04 | 2016-01-05 | 2016-01-27 | 2020-01-29 | 2026-09-17 |
|---|---|---|---|---|---|---|---|---|---|---|
| sip | 0 | 0 | 0 | 0 | 0 | 451 (13:30Z–21:00Z) | 451 | 451 | 450 | 449 |
| iex | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 393 (13:30Z–20:02Z) |

**Daily bars per calendar year, sip feed** (count): 2015 0; 2016 252 (first 2016-01-04); 2017 251;
2018 251; 2019 252; 2020 253; 2021 252; 2022 251; 2023 250; 2024 252; 2025 250. The 2026 query was
refused ("subscription does not permit querying recent SIP data") because its end bound reached the
last 15 minutes; the 2026-09-17 minute query above succeeded. The yearly counts were not checked
against an exchange calendar file.

**Result (observed).** The free feed carries SPY minute bars from **2016-01-04**, not from 2011. The
reopener as written (2011–2026) is **not met**. The 2pm-to-2pm form can be built only for the
scheduled meetings of 2016-01..2026-09: **N = 85**. Power on that window is in section 6 of
[`power_fomc.txt`](power_fomc.txt): minimum detectable mean 0.375% a meeting = **0.77×** the
published 2pm-to-2pm edge at the paper's standard deviation (0.58×–0.96× across ±25%); Sharpe
0.872 = 0.77× (0.85× at the largest Newey-West ratio). Recomputed in a separate session before
commit ([`power_fomc_recompute.md`](power_fomc_recompute.md), section 6: every figure matched).

**Not checked (for any later step):** whether Alpaca's market-data terms allow publishing statistics
derived from SIP bars (raw bars would not be published either way); whether every meeting day and
the day before have a 14:00 ET bar (checked since, below); FOMC statement release times 2016–2026; SPY against the S&P 500
index (an ETF with dividends and tracking error, not the paper's series).

## Check 3 of the 2026-10-27 22:1xZ agenda addition: a 2pm bar on every meeting day and the day before (2026-10-27 22:2xZ)

Statement dates for the 85 scheduled meetings held 2016-01..2026-09 were read from the Fed's pages
([`fomc_statement_dates_2016_2026-09.txt`](fomc_statement_dates_2016_2026-09.txt): 8 a year, 2020 7,
2026 6, the same per-year counts as the separate-session recount). A second private probe took the
trading days from SIP daily-bar timestamps (2,701 days, 2016-01-04..2026-09-30; not checked against an
exchange calendar) and asked for the SPY minute bars stamped 13:59 and 14:00 New York time on each
statement date and the trading day before it, comparing timestamps only (no price field read).
**Result (observed): 85 statement dates, all trading days in the feed; 340 bars checked; 0 missing.**
Check 3 passes. Checks 1 (market-data terms) and 2 (statement release times) are still open.
