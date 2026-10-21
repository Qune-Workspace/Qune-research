# Window-2 data decision (§5.3.4 steps 1-2)

Run at 2026-10-21T23:18:59Z (UTC). Data check only; no synthetic series, no rule, no return outside 2016-01-04 to 2018-12-31 was computed.

**Decision: window 2 accepted.** vendor series starts in time and both overlap checks pass.

| Item | Value |
|---|---|
| Vendor series (Tiingo IEF, adjClose) | 6099 rows, 2002-07-26 to 2026-10-21 |
| Alpaca series (Study 001 bars, adjustment='all') | 2716 rows, 2016-01-04 to 2026-10-21 |
| Common return days in window | 753 (2016-01-05 to 2018-12-31) |
| Days only in vendor / only in Alpaca | 1 / 0 |
| Correlation of daily returns | 0.999591 (threshold >= 0.999) -> pass |
| Annualised mean difference, vendor - Alpaca | +0.0494% p.a. (threshold within +/-0.05%) -> pass |
| Annualised tracking error (descriptive) | 0.1317% p.a. |
| Largest absolute daily difference (descriptive) | 13.67 bp |
| Days with absolute difference over 10 bp (descriptive) | 1 |
| Mean difference by year (descriptive, % p.a.) | 2016: +0.1423, 2017: +0.0028, 2018: +0.0031 |

Full statistics in `window2_data_decision.json`.

Days only in vendor: 2016-01-04.
Days only in Alpaca: none.
