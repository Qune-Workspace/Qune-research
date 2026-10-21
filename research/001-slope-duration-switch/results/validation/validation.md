# Validation of the synthetic series (§5.3)

Window 2016-01-04 to 2018-12-31. Instrument returns only; no rule applied.

| Check | Value | Threshold | Pass |
|---|---|---|---|
| A1 | 0.97010 | >= 0.95 | yes |
| A2 | 0.94610 | in [0.8, 1.05] | yes |
| A3 | 0.01145 | <= 0.015 | yes |
| A4 | 0.00451 | within +/-0.004 | NO |
| B1 | -0.00110 | within +/-0.003 | yes |
| B2 | 0.00288 | <= 0.005 | yes |

Duration/convexity cross-check, mean absolute daily error: 0.000 bp (acceptance 0.5 bp, §5.2).

Result: FAILED; the study halts (§5.3).
