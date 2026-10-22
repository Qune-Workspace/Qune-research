# BIL vendor decision (§5.3.2 steps 1-2)

Run at 2026-10-22T05:27:20Z (UTC). Data check only; no rule, no cash-leg series, no return outside 2016-01-04 to 2018-12-31 was computed.

**Outcome: vendor accepted.** mean difference within +/-0.05% p.a. and the series starts by 2007-06-01. The cash-leg level check (§5.3.3) will run over 2007-06-01 to 2018-12-31 on Tiingo BIL adjClose.

| Item | Value |
|---|---|
| Vendor series (Tiingo BIL, adjClose) | 4881 rows, 2007-05-30 to 2026-10-21 |
| Alpaca series (Study 001 bars, adjustment='all') | 2716 rows, 2016-01-04 to 2026-10-21 |
| Common return days in window | 753 (2016-01-05 to 2018-12-31) |
| Days only in vendor / only in Alpaca | 1 / 0 |
| **Annualised mean difference, vendor - Alpaca (the threshold)** | -0.0001% p.a. (within +/-0.05%) -> pass |
| Correlation of daily returns (descriptive) | 0.950746 |
| Annualised tracking error (descriptive) | 0.0880% p.a. |
| Largest absolute daily difference (descriptive) | 3.00 bp |
| Days with absolute difference over 10 bp (descriptive) | 0 |
| Mean difference by year (descriptive, % p.a.) | 2016: +0.0059, 2017: -0.0002, 2018: -0.0061 |

Full statistics in `bil_vendor_decision.json`.

Days only in vendor: 2016-01-04.
Days only in Alpaca: none.
