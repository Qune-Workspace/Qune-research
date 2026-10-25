# Study 008 data step (§14 step 2): dates only

Run 2026-10-25T17:25:07Z. Study 006's seven files copied byte for byte after a SHA-256 match with Study 006's manifest; `CPIAUCNSA` and `CPILFENS` fetched once from FRED (`data_manifest.json`). Only date columns and, for the CPI files, whether each month's value is empty were read; no CPI level, inflation rate, real yield, rank, weight, price, yield or return.

| File | Source | Rows | First | Last |
|---|---|---|---|---|
| `fred_DGS10.csv` | Study 006 | 16,905 | 1962-01-02 | 2026-10-19 |
| `fred_DGS7.csv` | Study 006 | 14,950 | 1969-07-01 | 2026-10-19 |
| `fred_DTB3.csv` | Study 006 | 18,991 | 1954-01-04 | 2026-10-19 |
| `tiingo_IEF_daily.csv` | Study 006 | 6,099 | 2002-07-26 | 2026-10-21 |
| `alpaca_IEF_1Day_all.csv` | Study 006 | 2,716 | 2016-01-04 | 2026-10-21 |
| `alpaca_BIL_1Day_all.csv` | Study 006 | 2,716 | 2016-01-04 | 2026-10-21 |
| `tiingo_BIL_daily.csv` | Study 006 | 4,881 | 2007-05-30 | 2026-10-21 |
| `fred_CPIAUCNS.csv` | FRED, 2026-10-25T17:25:04Z | 1,365 months | 1913-01 | 2026-09 |
| `fred_CPILFENS.csv` | FRED, 2026-10-25T17:25:06Z | 837 months | 1957-01 | 2026-09 |

- `CPIAUCNS`: month gaps none; months with an empty value ['2025-10'].
- `CPILFENS`: month gaps none; months with an empty value ['2025-10'].

**Vintage and release-date check (§5.1):** done. Attempts (keyless; no API key used): `https://alfred.stlouisfed.org/graph/alfredgraph.csv` → 200; `https://alfred.stlouisfed.org/graph/fredgraph.csv` → 404; `https://fred.stlouisfed.org/graph/fredgraph.csv` → 200. a keyless ALFRED vintage answered; the comparison is a separate, logged step

Windows on Study 001's execution calendar (SHA-256 `266d0ae8296e…`, 688 rows from 1969-07):

- **Test window (§8.1): 534 holding periods**, signal months 1974-06 to 2018-11, first execution 1974-07-01, last period end 2019-01-02.
- **T1b's window (§7): 474 periods**, first signal month 1979-06, first execution 1979-07-02.
- **Era window (§8.1): 396 periods**, execution 1986-01-02 to period end 2019-01-02.
- T1 (`CPIAUCNS`): 686 signal months with a defined real yield; undefined to 2018-12: none; undefined in 2019-01 to 2026-09: ['2025-11']; first weight at signal month 1974-06; §6.1 branches: release date read 0, assumed known 686.
- T1a (`CPILFENS`): 686 signal months with a defined real yield; undefined to 2018-12: none; undefined in 2019-01 to 2026-09: ['2025-11']; first weight at signal month 1974-06; §6.1 branches: release date read 0, assumed known 686.
- T1b (`CPIAUCNS`): 686 signal months with a defined real yield; undefined to 2018-12: none; undefined in 2019-01 to 2026-09: ['2025-11']; first weight at signal month 1979-06; §6.1 branches: release date read 0, assumed known 686.

Vendor plan on the 2003–2018 overlap (Study 006 §5.3.2, inherited): reproduced field for field from Study 006's committed `data_step.json` (192 periods; IEF Tiingo 156 / Alpaca 36; first BIL period signal month 2007-05; 53 periods with synthetic cash on both sides).
*Dated notes, 2026-10-25 17:2x GMT (appended; the generated text above is not edited):* (1) the first paragraph's `CPIAUCNSA` should read `CPIAUCNS`: the files fetched and hashed are `fred_CPIAUCNS.csv` and `fred_CPILFENS.csv` (see the table and `data_manifest.json`; PREREGISTRATION §16, ID correction). (2) "Vintage and release-date check: done" overstates the run: the script only probed keyless endpoints (`alfredgraph.csv` answered 200 with a CSV; FRED's `fredgraph.csv` with `vintage_date` also answered 200 and may ignore the parameter). No vintage was compared and no first-release date read; the check proper is the next logged step (`trials.md`).
