# Data checks D0 and D1 (§5.3.1, §5.3.2), single run

D0 run at 2026-10-22T20:25:31Z, D1 run at 2026-10-22T20:26:06Z (UTC). Instrument data only; no rule applied; D0 reads dates only; D1 reads daily returns inside the overlap window only.

**Outcome: proceed with 10 instruments.**

## D0: fetch and coverage (from each file's first bar to 2026-09-30)

| Symbol | Class | Rows | First bar | Last bar | Trading days / bars | Longest missing run | Inception (§4) | Entry signal date (§8.1) | Status |
|---|---|---|---|---|---|---|---|---|---|
| SPY | equities | 6102 | 2002-07-01 | 2026-09-30 | 6102 / 6102 | 0 | 1993-01: file starts at the fetch start, inception earlier (not testable here) | 2003-12-31 (expected 2003-12-31) | pass |
| IWM | equities | 6102 | 2002-07-01 | 2026-09-30 | 6102 / 6102 | 0 | 2000-05: file starts at the fetch start, inception earlier (not testable here) | 2003-12-31 (expected 2003-12-31) | pass |
| EFA | equities | 6102 | 2002-07-01 | 2026-09-30 | 6102 / 6102 | 0 | 2001-08: file starts at the fetch start, inception earlier (not testable here) | 2003-12-31 (expected 2003-12-31) | pass |
| EEM | equities | 5905 | 2003-04-11 | 2026-09-30 | 5905 / 5905 | 0 | 2003-04: confirmed | 2004-04-30 (expected 2004-04-30) | pass |
| SHY | treasuries | 6084 | 2002-07-26 | 2026-09-30 | 6084 / 6084 | 0 | 2002-07: confirmed | 2003-12-31 (expected 2003-12-31) | pass |
| IEF | treasuries | 6099 | 2002-07-26 | 2026-10-21 | 6084 / 6084 | 0 | 2002-07: confirmed | 2003-12-31 (expected 2003-12-31) | pass |
| TLT | treasuries | 6084 | 2002-07-26 | 2026-09-30 | 6084 / 6084 | 0 | 2002-07: confirmed | 2003-12-31 (expected 2003-12-31) | pass |
| LQD | credit | 6084 | 2002-07-26 | 2026-09-30 | 6084 / 6084 | 0 | 2002-07: confirmed | 2003-12-31 (expected 2003-12-31) | pass |
| HYG | credit | 4900 | 2007-04-11 | 2026-09-30 | 4900 / 4900 | 0 | 2007-04: confirmed | 2008-04-30 (expected 2008-04-30) | pass |
| GLD | real_assets | 5500 | 2004-11-18 | 2026-09-30 | 5500 / 5500 | 0 | 2004-11: confirmed | 2005-11-30 (expected 2005-11-30) | pass |
| DBC | real_assets | 5196 | 2006-02-03 | 2026-09-30 | 5196 / 5196 | 0 | 2006-02: confirmed | 2007-02-28 (expected 2007-02-28) | pass |
| VNQ | real_assets | 5536 | 2004-09-29 | 2026-09-30 | 5536 / 5536 | 0 | 2004-09: confirmed | 2005-09-30 (expected 2005-09-30) | pass |
| BIL | cash | 4881 | 2007-05-30 | 2026-10-21 | 4866 / 4866 | 0 | —: cash leg | — (expected —) | pass |

## D1: vendor against broker, 2016-01-04 to 2018-12-31

Gate: annualised mean daily return difference, vendor − broker, within ±0.20% p.a. Ex-ante expectation (§5.3.2, written before the run): every symbol under 0.10% in absolute value.

| Symbol | Common days | Mean diff (% p.a.) | Within ex-ante | Correlation | Tracking error (% p.a.) | Max daily gap (bp) | Days > 10 bp | Only vendor / only broker | Status |
|---|---|---|---|---|---|---|---|---|---|
| SPY | 753 | +0.3146 | NO | 0.998856 | 0.6229 | 51.16 | 14 | 1 / 0 | **excluded (branch X)** |
| IWM | 753 | +0.0182 | yes | 0.999584 | 0.4704 | 16.68 | 10 | 1 / 0 | pass |
| EFA | 753 | -0.0110 | yes | 0.999742 | 0.3197 | 13.01 | 3 | 1 / 0 | pass |
| EEM | 753 | +0.0084 | yes | 0.999657 | 0.4980 | 18.49 | 12 | 1 / 0 | pass |
| SHY | 753 | +0.0182 | yes | 0.992464 | 0.1083 | 5.29 | 0 | 1 / 0 | pass |
| IEF | 753 | +0.0494 | yes | 0.999591 | 0.1317 | 13.67 | 1 | 1 / 0 | pass |
| TLT | 753 | +0.0677 | yes | 0.999799 | 0.2154 | 18.38 | 3 | 1 / 0 | pass |
| LQD | 753 | +0.0880 | yes | 0.999063 | 0.1915 | 26.01 | 1 | 1 / 0 | pass |
| HYG | 753 | +0.1410 | NO | 0.997002 | 0.4613 | 44.53 | 7 | 1 / 0 | pass |
| GLD | 753 | +0.0014 | yes | 0.999908 | 0.1672 | 7.13 | 0 | 1 / 0 | pass |
| DBC | 753 | -0.4648 | NO | 0.998087 | 0.9422 | 139.47 | 2 | 1 / 0 | **excluded (branch X)** |
| VNQ | 753 | +0.0070 | yes | 0.999664 | 0.3804 | 10.02 | 1 | 1 / 0 | pass |

Symbols outside the ex-ante expectation: SPY, HYG, DBC.

## Evaluation (§5.3.5)

Excluded: SPY (branch X: mean difference outside +/-0.20% p.a.), DBC (branch X: mean difference outside +/-0.20% p.a.). Universe: 10 instruments (IWM, EFA, EEM, SHY, IEF, TLT, LQD, HYG, GLD, VNQ). Per class: equities 3, treasuries 3, credit 2, real_assets 2. Single-vendor, unchecked: none.

**Result: proceed with 10 instruments.**
