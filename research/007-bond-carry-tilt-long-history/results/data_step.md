# Study 007 data step (§14 step 2): dates only

Run 2026-10-25T11:25:57Z. Study 006's seven files copied byte for byte after a SHA-256 match with Study 006's manifest (`data_manifest.json`). Only date columns were read; no price, yield, return, carry, rank or signal value.

| File | Source | Rows | First date | Last date |
|---|---|---|---|---|
| `fred_DGS10.csv` | Study 006 | 16,905 | 1962-01-02 | 2026-10-19 |
| `fred_DGS7.csv` | Study 006 | 14,950 | 1969-07-01 | 2026-10-19 |
| `fred_DTB3.csv` | Study 006 | 18,991 | 1954-01-04 | 2026-10-19 |
| `tiingo_IEF_daily.csv` | Study 006 | 6,099 | 2002-07-26 | 2026-10-21 |
| `alpaca_IEF_1Day_all.csv` | Study 006 | 2,716 | 2016-01-04 | 2026-10-21 |
| `alpaca_BIL_1Day_all.csv` | Study 006 | 2,716 | 2016-01-04 | 2026-10-21 |
| `tiingo_BIL_daily.csv` | Study 006 | 4,881 | 2007-05-30 | 2026-10-21 |

Windows on Study 001's execution calendar (SHA-256 `266d0ae8296e…`, 688 rows from 1969-07; month gaps: [('2018-12', '2018-12')]):

- **Test window (§8.1): 534 holding periods**, signal months 1974-06 to 2018-11, first execution date 1974-07-01, last period end 2019-01-02.
- **T1b's window (§7): 474 periods**, first signal month 1979-06, first execution date 1979-07-02.
- First signal month by minimum history (§5.5, §6.2): T1 (60) 1974-06, T1a (36) 1972-06, T1b (120) 1979-06; the trend signal (twelve earlier rows, §6.3) from 1970-07.
- Counted from the calendar's rows: the m-th month-end carry is the m-th calendar row from 1969-07. Whether DGS7 is present on every signal date (a carry undefined on a date is handled at the code step, Study 006 section 16 (c)) is not read here.

Vendor plan on the 2003–2018 overlap (Study 006 §5.3.2, inherited): reproduced field for field from Study 006's committed `data_step.json` (192 periods; IEF Tiingo 156 / Alpaca 36; first BIL period signal month 2007-05; 53 periods with synthetic cash on both sides).
