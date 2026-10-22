# Data checks D0 and D2 (§5.3.1, §5.3.3), single run

Run at 2026-10-22T07:30:55Z (UTC). Instrument and cash-accrual returns only; no rule applied; no IEF return read (D0 uses dates only).

## D0: coverage of the in-sample IEF series

Vendor IEF bars against the rule-based NYSE calendar, 2002-07-31 to 2018-12-31: 4134 of 4134 trading days present; first bar 2002-07-26 (required on or before 2002-07-31); longest run of missing trading days 0 (allowed <= 3). **Pass.**

## D2: cash-leg level check

Window 2007-06-01 to 2018-12-31 on Tiingo BIL adjClose (selected by the committed §5.3.2 decision: vendor_accepted). 2916 common return days, 2007-06-04 to 2018-12-31.

| Check | Value | Threshold | Pass |
|---|---|---|---|
| B1 annualised mean difference, BIL minus accrual | +0.0366% p.a. (ex-ante +0.00 +/- 0.20) | within +/-0.003 | yes |
| B2 annualised tracking error (descriptive) | 0.5857% p.a. | reference 0.50%; 2016-2018 reading 0.288% | descriptive (above the reference) |

Observed gap inside the ex-ante component ranges. Correlation of daily returns 0.0930 (descriptive); largest absolute daily difference 43.3 bp.

Ex-ante component estimate (§5.3.3, written before the run):

| Component | Ex-ante estimate (% p.a.) | Range (+/-) |
|---|---|---|
| 1-3 month bills against the 3-month rate | -0.02 | 0.05 |
| portfolio yield lags the spot rate by about a month | +0.04 | 0.04 |
| expense ratio | +0.00 | 0.02 |
| securities lending and other income | +0.01 | 0.03 |
| price versus NAV at the window ends | +0.00 | 0.01 |
| daily reset and day-count conventions | +0.00 | 0.03 |
| **Central estimate / sum of ranges** | **+0.00** | **0.20** |

By calendar year (descriptive): mean gap and tracking error, % p.a.

| Year | Mean gap | Tracking error |
|---|---|---|
| 2007 | +0.287 | 0.896 |
| 2008 | +0.320 | 1.561 |
| 2009 | +0.256 | 0.678 |
| 2010 | -0.046 | 0.292 |
| 2011 | +0.043 | 0.258 |
| 2012 | +0.005 | 0.220 |
| 2013 | -0.009 | 0.236 |
| 2014 | +0.038 | 0.242 |
| 2015 | -0.046 | 0.261 |
| 2016 | -0.071 | 0.292 |
| 2017 | -0.119 | 0.312 |
| 2018 | -0.117 | 0.209 |

**Result: D0 and D2 pass; the study proceeds to the registered trials.**
