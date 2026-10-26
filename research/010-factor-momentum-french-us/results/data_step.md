# Study 010 data step (§14 step 2): dates and missing-value markers only

Run 2026-10-26T09:17:58Z. Library page read 2026-10-26T09:17:56Z; each file downloaded once (`data_manifest.json`: URL, time, SHA-256, bytes, header lines). Only dates were read from the monthly sections, and each value field was compared with −99.99, −999 and empty, recording only whether it matched. No factor value was written, printed or summarised; the annual sections were not parsed.

| File | Downloaded (UTC) | Columns | Rows | First month | Last month | Gaps | Marker months (all columns) |
|---|---|---|---|---|---|---|---|
| `F-F_Research_Data_Factors_CSV.zip` | 2026-10-26T09:17:57Z | Mkt-RF, SMB, HML, RF | 1,202 | 1926-07 | 2026-08 | 0 | 0 |
| `F-F_ST_Reversal_Factor_CSV.zip` | 2026-10-26T09:17:57Z | ST_Rev | 1,207 | 1926-02 | 2026-08 | 0 | 0 |
| `F-F_LT_Reversal_Factor_CSV.zip` | 2026-10-26T09:17:57Z | LT_Rev | 1,148 | 1931-01 | 2026-08 | 0 | 0 |

Release lines (file headers, verbatim):

- `F-F_Research_Data_Factors_CSV.zip`: This file was created using the 202608 CRSP database.
- `F-F_Research_Data_Factors_CSV.zip`: The 1-month TBill rate data until 202405 are from Ibbotson Associates. Starting from 202406, the 1-month TBill rate is from ICE BofA US 1-Month Treasury Bill Index.
- `F-F_ST_Reversal_Factor_CSV.zip`: This file was created using the 202608 CRSP database.  It
- `F-F_LT_Reversal_Factor_CSV.zip`: This file was created using the 202608 CRSP database.  It

**H's end (last month common to the three files): 2026-08.**

| Row | Months | Count |
|---|---|---|
| H | 1927-07 to 2026-08 | 1,190 |
| P1 | 1927-07 to 1963-06 | 432 |
| L | 1963-07 to 2015-12 | 630 |
| P2 | 2016-01 to 2026-08 | 128 |
| P | P1 and P2 | 560 |

| Trial | Factor | First formation month | First holding month | Holding months in H |
|---|---|---|---|---|
| T1 | SMB | 1926-07 | 1927-07 | 1,190 |
| T1 | HML | 1926-07 | 1927-07 | 1,190 |
| T1 | ST_Rev | 1926-07 | 1927-07 | 1,190 |
| T1 | LT_Rev | 1931-01 | 1932-01 | 1,136 |
| T1a | SMB | 1926-07 | 1927-07 | 1,190 |
| T1a | HML | 1926-07 | 1927-07 | 1,190 |
| T1b | SMB | 1927-01 | 1927-07 | 1,190 |
| T1b | HML | 1927-01 | 1927-07 | 1,190 |
| T1b | ST_Rev | 1927-01 | 1927-07 | 1,190 |
| T1b | LT_Rev | 1931-01 | 1931-07 | 1,142 |

Columns used, months the trials use: markers and gaps

- SMB (1926-07 to 2026-08): markers none; gaps none
- HML (1926-07 to 2026-08): markers none; gaps none
- ST_Rev (1926-07 to 2026-08): markers none; gaps none
- LT_Rev (1931-01 to 2026-08): markers none; gaps none

**Outcome: pass: no §5.4 stop rule met.**
