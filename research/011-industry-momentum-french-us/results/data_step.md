# Study 011 data step (§14 step 2): dates, column names, counts and missing-value markers only

Run 2026-10-26T15:31:24Z. Library page read 2026-10-26T15:31:22Z; each file downloaded once (`data_manifest.json`: URL, time, SHA-256, bytes, header lines). Only the value-weighted monthly section was read, for dates and column names; each value field was compared as a stripped string with "-99.99", "-999" and empty, recording only whether it matched. No field was parsed as a number; no return value was written, printed or summarised; no other section was read.

| File | Downloaded (UTC) | Industries | Rows | First month | Last month | Gaps | Duplicate / out of order |
|---|---|---|---|---|---|---|---|
| `17_Industry_Portfolios_CSV.zip` | 2026-10-26T15:31:23Z | 17: Food, Mines, Oil, Clths, Durbl, Chems, Cnsum, Cnstr, Steel, FabPr, Machn, Cars, Trans, Utils, Rtail, Finan, Other | 1,202 | 1926-07 | 2026-08 | 0 | 0 |
| `30_Industry_Portfolios_CSV.zip` | 2026-10-26T15:31:23Z | 30: Food, Beer, Smoke, Games, Books, Hshld, Clths, Hlth, Chems, Txtls, Cnstr, Steel, FabPr, ElcEq, Autos, Carry, Mines, Coal, Oil, Util, Telcm, Servs, BusEq, Paper, Trans, Whlsl, Rtail, Meals, Fin, Other | 1,202 | 1926-07 | 2026-08 | 0 | 0 |

Release lines (file headers, verbatim):

- `17_Industry_Portfolios_CSV.zip`: This file was created using the 202608 CRSP database.
- `30_Industry_Portfolios_CSV.zip`: This file was created by CMPT_IND_RETS using the 202608 CRSP database.

**Last common month: 2026-08.**

| Trial | I1 | I2 | O | M | full |
|---|---|---|---|---|---|
| M1 | 1927-06 to 1963-06 (433) | 1995-08 to 2026-08 (373) | 806 | 385 | 1,191 |
| M1a | 1927-06 to 1963-06 (433) | 1995-08 to 2026-08 (373) | 806 | 385 | 1,191 |
| M1b | 1927-12 to 1963-06 (427) | 1995-08 to 2026-08 (373) | 800 | 385 | 1,185 |

Eligibility at ranking months whose cohort is held (§5.4; marker flags only):

- `17_Industry_Portfolios_CSV.zip F=6`: 1,196 ranking months (1926-12 to 2026-07); minimum eligible 17; months below the full set 0; below the floor 0
- `17_Industry_Portfolios_CSV.zip F=12`: 1,190 ranking months (1927-06 to 2026-07); minimum eligible 17; months below the full set 0; below the floor 0
- `30_Industry_Portfolios_CSV.zip F=6`: 1,196 ranking months (1926-12 to 2026-07); minimum eligible 30; months below the full set 0; below the floor 0

Months with fewer industries holding a value than the set (to the last common month):

- `17_Industry_Portfolios_CSV.zip`: 0 months
- `30_Industry_Portfolios_CSV.zip`: 0 months

**Outcome: pass: no §5.4 stop rule met.**
