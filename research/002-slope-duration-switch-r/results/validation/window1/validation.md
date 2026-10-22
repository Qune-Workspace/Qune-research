# Validation window 1 (§5.3.3)

Window 2016-01-04 to 2018-12-31; IEF and BIL from Alpaca. Instrument returns only; no rule applied.

| Check | Value | Threshold | Pass |
|---|---|---|---|
| A1 | 0.96975 | >= 0.95 | yes |
| A2 | 0.93985 | in [0.8, 1.05] | yes |
| A3 | 0.01159 | <= 0.015 | yes |
| A4 | 0.00100 (ex-ante central estimate +0.0005) | in [-0.0025, 0.0035] | yes |
| B1 | -0.00110 | within +/-0.003 | yes |
| B2 | 0.00288 | <= 0.005 | yes |

D1 (descriptive, no decision weight): IEF minus synthetic by calendar year, % p.a., against the roll-down the construction earns that year (§5.3.3):

| Year | Observed gap | Roll-down estimate |
|---|---|---|
| 2016 | -0.063% | 0.533% |
| 2017 | +0.146% | 0.438% |
| 2018 | +0.217% | 0.147% |

Duration/convexity cross-check, mean absolute daily error: 0.010 bp (acceptance 0.5 bp, §5.2).

Result: all window-1 thresholds met.
