# Study 001 — Term-spread duration switch (IEF vs BIL)

**Status: halted at the data validation (§5.3), 2026-10-21. No rule has been tested.** The owner approved the pre-registration and the symbols IEF and BIL on 2026-10-21 (`APPROVED`, [trials.md](trials.md)). The first step after approval, `./reproduce.sh --validate`, failed two of the six pre-registered thresholds for the synthetic instrument series, so under §5.3 the study stopped before `--insample` or `--oos` was run. **No return of T1, T2, T3 or any benchmark has been computed.** `results/insample/` and `results/oos/` do not exist. A dated amendment proposal with a corrected construction is in §16 of [PREREGISTRATION.md](PREREGISTRATION.md) and waits for the owner's decision; nothing further runs until that decision is recorded there.

The question, hypothesis, data, exact rule, trials, sample split, benchmarks, metrics and decision criteria are all fixed in PREREGISTRATION.md and are not repeated here.

## Validation result (backtest data check, §5.3; not a performance test)

Window 2016-01-04 to 2018-12-31, 753 NYSE trading days, instrument returns only, no rule applied. Source: `results/validation/validation.json` and `validation.md`; plot `results/validation/validation.png` (a backtest data comparison, not a strategy).

| Check | Statistic | Value | Threshold | Result |
|---|---|---|---|---|
| A1 | Correlation of daily returns, IEF vs synthetic 10-year | 0.966 | ≥ 0.95 | pass |
| A2 | OLS slope of IEF on synthetic | 0.821 | in [0.80, 1.05] | pass (at the bottom of the band) |
| A3 | Annualised tracking error, IEF vs synthetic | 1.540% p.a. | ≤ 1.5% p.a. | **fail** |
| A4 | Annualised mean difference, IEF − synthetic | +0.455% p.a. | within ±0.40% p.a. | **fail** |
| B1 | Annualised mean difference, BIL − synthetic cash | −0.110% p.a. | within ±0.30% p.a. | pass |
| B2 | Annualised tracking error, BIL vs synthetic cash | 0.288% p.a. | ≤ 0.50% p.a. | pass |

The duration/convexity cross-check of the exact repricing (§5.2) agrees to 0.0000 bp per day on average (1.6 × 10⁻⁸ in return units; acceptance 0.5 bp), so the synthetic arithmetic is not the problem.

What the numbers say: the ETF's daily return moves about 0.82 for every 1.00 of a 10-year par bond repriced from DGS10. That is the ETF-versus-index mismatch §5.3 anticipated (a 7–10-year index has less duration than a 10-year bond), and it is larger than the thresholds allowed for. Yields rose over the window, so the longer synthetic lost more than the ETF; that shows up as the ETF beating the synthetic by 45 bp a year (A4) and as residual day-to-day variance (A3, 4 bp over the limit). The cash leg tracks well. Both failures are small in size and both point the same way: the synthetic duration leg is too long.

What this means for the study: the in-sample period (1962–2018) would have been scored on a synthetic series that is systematically more volatile than, and over rising-yield stretches lower-returning than, the instrument actually traded. §5.3 says that is not acceptable without a dated correction, so the correction is proposed in §16 (an equal-weight 7-year/10-year par-bond blend from DGS7 and DGS10, the example §5.3 itself gave) and the study waits. One correction only; if the re-run fails, the study halts for good.

## What did not work (so far)

- **A3 and A4 of the validation failed**, as above. The thresholds were set before any data were looked at, and the duration mismatch between a 7–10-year ETF and a 10-year par bond turned out larger than the ±0.40% p.a. and 1.5% p.a. allowances. A2 passed by 0.02.
- **Three tests failed after approval.** `test_reproduce_refuses_without_approval` asserted that no `APPROVED` file exists, so recording the approval broke it. It now runs on a copy of the script without that file (§16, first post-approval entry). 98 tests pass again.
- **`reproduce.sh` could not run as written.** It re-fetched the Alpaca bars on every run and required an API key pair that the run environment does not have; and on the day of the run the FRED site was in a maintenance window and returned an HTML page in place of the CSV for over twenty minutes. The script now reuses the files already in `data/raw/` in either case and says so; their provenance is in `results/data_manifest.json`. Both changes are recorded in §16. No return had been computed when they were made.
- **Cosmetic:** the date labels on the lower axes of `validation.png` overlap. Not fixed, since the figure is a committed result file.

## Paper trading

Not started. §8.4 and §11 start paper trading from the publication date of a study note with results; there is no such note. Nothing is backdated.

## Earlier preparation (dates only, no returns)

- FRED series DGS10, DTB3 and DGS7 downloaded into `data/raw/` (git-ignored); provenance (URL, UTC timestamp, rows, SHA-256, first and last valid date) in `results/data_manifest.json`. Row and missing counts match §5.4. Alpaca bars for IEF and BIL (`adjustment='all'`, 2016-01-04 to 2026-10-21) fetched the same day; only row counts and hashes are in the manifest.
- The signal-to-execution date mapping (§6.3) on the real FRED calendar gives 683 in-sample and 93 out-of-sample holding periods, as §8 anticipates, with no month lacking a signal. `python -m src.calendar` writes the mapping to `results/execution_calendar.csv`.

## How to run (after approval)

From this folder, with the repository's virtual environment (`pip install -r requirements.txt`):

```
python -m pytest -q          # unit tests on synthetic data; no network, no real returns
./reproduce.sh --validate    # §5.3 data check  -> results/validation/
./reproduce.sh --insample    # §8.1 in-sample   -> results/insample/   (freezes the B3 weight)
./reproduce.sh --oos         # §8.2 out-of-sample, exactly once -> results/oos/
```

`reproduce.sh` requires a file named `APPROVED` in this folder containing the owner's approval date, re-fetches the data on every run (falling back to the files already in `data/raw/` if FRED is unreachable or the Alpaca credentials are not set; §16), and refuses `--oos` if `results/oos/` already exists. The main chart (`main_chart.png`: spread with the holding shaded, drawdown of T1 versus B1) is produced by `src/report.py` through `reproduce.sh`.

### Credentials

Alpaca market data (ETF bars, `adjustment='all'`, SIP feed) is fetched by `src/alpaca_bars.py`, which reads the API key pair from the environment variables `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` and from nowhere else. Export them in the shell that runs `reproduce.sh --validate` or `--oos` to re-fetch; without them the script reuses bars already in `data/raw/`. `--insample` needs no credentials (FRED only). Bars are licensed and are never committed; only their row count and hash enter the manifest. FRED needs no key.

## Layout

The layout follows §13. Modules are run as `python -m src.<module>` from this folder so that `src/calendar.py` (the name fixed in §13) is imported as `src.calendar` and never shadows the standard-library `calendar` module. Two files are not in §13: `src/config.py`, which holds every pre-registered constant with its section reference, and `conftest.py`, which makes the folder importable for pytest.

| Module | Pre-registration section |
|---|---|
| `src/fred.py` | §5.1 download, parsing, manifest |
| `src/alpaca_bars.py` | §5.1 ETF bars, `adjustment='all'` |
| `src/bey.py` | §5.1 bond-equivalent yield; §5.2, §7 par-bond price, duration, convexity |
| `src/synthetic.py` | §5.2 synthetic 10-year and cash returns, duration/convexity cross-check |
| `src/validate.py` | §5.3 checks A1–A4, B1–B2 and plots |
| `src/calendar.py` | §6.3 signal dates (FRED calendar) and execution dates (NYSE calendar) |
| `src/signal.py` | §6.1 T1; §7 T2, T3 |
| `src/backtest.py` | §6.4–§6.6 monthly loop and costs; §9.1 benchmarks B0–B3 |
| `src/stats.py` | §9.3 metrics, Newey–West, Ledoit–Wolf, stationary bootstrap; §9.4 PSR/DSR |
| `src/report.py` | §8, §9.5, §9.6 runs, tables, criteria, figures |
| `src/paper_trade.py` | §11.2, §11.5 decision record and order plan (no order submission; see its docstring) |

Random seed for every bootstrap: 20261021 (§13).

## Implementation notes to be confirmed at review

These are readings of the pre-registration made while implementing; none changes a number or a rule. They are listed so that the reviewer can object before anything is run.

1. **T3 units.** `D_mod(DGS10_t) × (DGS10_t − DGS7_t)/3` is computed with both yields as decimals, consistent with `spread_t`, which §6.1 defines in decimals.
2. **Initial purchase.** No strategy or benchmark is charged for the position assumed to be in place at the first execution date; §6.6 starts with `holding = BIL` without a cost and §9.1 exempts B0 and B1 "after the initial purchase". The cost of switching is charged on both legs as `(1 − c)²` on equity (§6.6); a static mix pays `(1 − c·x)²` on the drifted fraction x (§9.1).
3. **Synthetic index on NYSE-only days.** When an execution date is an NYSE trading day but not a FRED business day, the synthetic index is taken as of the last FRED observation on or before it (the same as-of rule compounds the synthetic series onto NYSE intervals in §5.3).
4. **NYSE calendar.** No NYSE calendar source is named in §5; `src/calendar.py` is rule-based (regular holidays with their observance rules and the exchange's unscheduled closures since 1962). Out-of-sample execution dates are additionally resolved against the bars actually present (§6.5), so a calendar error there would appear as logged slippage. The closure list should be checked against the exchange's published history before the in-sample run.
5. **T2 start.** T2 needs 21 valid daily spreads; if that leaves the first signal date undefined, T2 simply starts at the first month where it is defined. T3 starts at the 1969-07 signal month (§7). Comparisons with B1 and B3 use the trial's own holding periods.
6. **Ledoit–Wolf standard errors** use a Bartlett kernel with 6 lags (the Newey–West bandwidth of §9.3) in the sample and in every resample; Sharpe ratios inside the test use population moments as in the paper.
7. **Literature DOIs** (§3) were checked against the Crossref API on 2026-10-21; see the table below. Nothing in §3 was changed: two citations carry a different year in the registry (online-first against print) and one could not be verified from an automated reader.

## Literature verification (2026-10-21)

Each §3 citation was looked up by title and authors in the Crossref registry. "Confirmed" means the registry entry matches the journal, volume, issue and pages in §3. Years are the print year used in §3; where the registry lists an earlier online-first year it is noted.

| §3 citation | DOI | Result |
|---|---|---|
| Fama and Bliss (1987), AER 77(4) | none registered | Not verified: the 1987 AER volume is not in Crossref and the JSTOR record cannot be read by an automated client. Left as cited. |
| Campbell and Shiller (1991), RES 58(3) | 10.2307/2298008 | Confirmed |
| Cochrane and Piazzesi (2005), AER 95(1) | 10.1257/0002828053828581 | Confirmed |
| Koijen, Moskowitz, Pedersen and Vrugt (2018), JFE 127(2) | 10.1016/j.jfineco.2017.11.002 | Confirmed |
| Moskowitz, Ooi and Pedersen (2012), JFE 104(2) | 10.1016/j.jfineco.2011.11.003 | Confirmed |
| Asness, Moskowitz and Pedersen (2013), JF 68(3) | 10.1111/jofi.12021 | Confirmed |
| Brooks and Moskowitz (2017), SSRN working paper | 10.2139/ssrn.2956411 | Confirmed (working paper, 2017) |
| Ilmanen (2011), *Expected Returns*, Wiley | book, no DOI checked | Not checked (book) |
| Bauer and Hamilton (2018), RFS 31(2) | 10.1093/rfs/hhx096 | Confirmed; registry year 2017 (online first), print 2018 |
| Stambaugh (1999), JFE 54(3) | 10.1016/s0304-405x(99)00041-0 | Confirmed |
| Welch and Goyal (2008), RFS 21(4) | 10.1093/rfs/hhm014 | Confirmed; registry year 2007 (online first), print 2008 |
| Estrella and Mishkin (1998), REStat 80(1) | 10.1162/003465398557320 | Confirmed |
| McLean and Pontiff (2016), JF 71(1) | 10.1111/jofi.12365 | Confirmed |
| Harvey, Liu and Zhu (2016), RFS 29(1) | 10.1093/rfs/hhv059 | Confirmed; registry year 2015 (online first), print 2016 |
| Bailey and López de Prado (2014), JPM 40(5) | 10.3905/jpm.2014.40.5.094 | Confirmed |
| Ledoit and Wolf (2008), JEF 15(5) | 10.1016/j.jempfin.2008.03.002 | Confirmed |
| Newey and West (1987), Econometrica 55(3) | 10.2307/1913610 | Confirmed (registry lists first page 703 only) |
| Politis and Romano (1994), JASA 89(428) | 10.1080/01621459.1994.10476870 | Confirmed |
| Henriksson and Merton (1981), JB 54(4) | 10.1086/296144 | Confirmed (registry lists first page 513 only) |
| Swinkels (2019), *Data* 4(3), 91 | 10.3390/data4030091 | Confirmed |
| Federal Reserve H.15 release notes | web page | Checked 2026-10-21 as stated in §3 |

Page numbers and journal details were not changed. The two "online first" years are registry conventions, not citation errors.
