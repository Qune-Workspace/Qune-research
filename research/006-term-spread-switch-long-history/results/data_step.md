# Study 006 data step (§14 step 2): dates only

Run 2026-10-25T02:21:01Z. Files copied byte for byte after a SHA-256 match with the source study's manifest (`data_manifest.json`). Only date columns were read; no price, yield, return or signal value.

| File | Source | Rows | First date | Last date |
|---|---|---|---|---|
| `fred_DGS10.csv` | Study 002 | 16,905 | 1962-01-02 | 2026-10-19 |
| `fred_DGS7.csv` | Study 002 | 14,950 | 1969-07-01 | 2026-10-19 |
| `fred_DTB3.csv` | Study 002 | 18,991 | 1954-01-04 | 2026-10-19 |
| `tiingo_IEF_daily.csv` | Study 002 | 6,099 | 2002-07-26 | 2026-10-21 |
| `alpaca_IEF_1Day_all.csv` | Study 002 | 2,716 | 2016-01-04 | 2026-10-21 |
| `alpaca_BIL_1Day_all.csv` | Study 002 | 2,716 | 2016-01-04 | 2026-10-21 |
| `tiingo_BIL_daily.csv` | Study 004 | 4,881 | 2007-05-30 | 2026-10-21 |

Vendor plan on Study 001's execution calendar (SHA-256 `266d0ae8296e…`), §5.3.2:

- Overlap periods: 192 (execution 2003-01-02 to period end 2019-01-02).
- IEF: Tiingo 156, Alpaca 36 (first Alpaca period: execution 2016-01-04); missing: none.
- BIL: first period with BIL at both ends: signal month 2007-05, execution 2007-06-01 to 2007-07-02 (tiingo). Synthetic cash on both sides before it: 53 periods. From it: Tiingo 103, Alpaca 36; missing afterwards: none.
