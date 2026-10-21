# Study 001 — Term-spread duration switch (IEF vs BIL)

**Status: built.** The code in `src/` and `tests/` implements [PREREGISTRATION.md](PREREGISTRATION.md) and its tests pass. **No result exists.** No return of any rule or benchmark has been computed on real data; the owner's approval (§14 step 1) is pending and `reproduce.sh` refuses to run until it is recorded. This file will become the study note, including "What did not work" (§9.7), only after the runs in §14.

The question, hypothesis, data, exact rule, trials, sample split, benchmarks, metrics and decision criteria are all fixed in PREREGISTRATION.md and are not repeated here. The trial log is [trials.md](trials.md).

## What has been done so far (dates only, no returns)

- FRED series DGS10, DTB3 and DGS7 downloaded into `data/raw/` (git-ignored); provenance (URL, UTC timestamp, rows, SHA-256, first and last valid date) in `results/data_manifest.json`. Row and missing counts match §5.4.
- The signal-to-execution date mapping (§6.3) on the real FRED calendar gives 683 in-sample and 93 out-of-sample holding periods, as §8 anticipates, with no month lacking a signal. `python -m src.calendar` writes the mapping to `results/execution_calendar.csv`.

## How to run (after approval)

From this folder, with the repository's virtual environment (`pip install -r requirements.txt`):

```
python -m pytest -q          # unit tests on synthetic data; no network, no real returns
./reproduce.sh --validate    # §5.3 data check  -> results/validation/
./reproduce.sh --insample    # §8.1 in-sample   -> results/insample/   (freezes the B3 weight)
./reproduce.sh --oos         # §8.2 out-of-sample, exactly once -> results/oos/
```

`reproduce.sh` requires a file named `APPROVED` in this folder containing the owner's approval date, re-fetches the data on every run, and refuses `--oos` if `results/oos/` already exists. The main chart (`main_chart.png`: spread with the holding shaded, drawdown of T1 versus B1) is produced by `src/report.py` through `reproduce.sh`.

### Credentials

Alpaca market data (ETF bars, `adjustment='all'`, SIP feed) is fetched by `src/alpaca_bars.py`, which reads the API key pair from the environment variables `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` and from nowhere else. Export them in the shell that runs `reproduce.sh --validate` or `--oos`; `--insample` needs no credentials (FRED only). Bars are licensed and are never committed; only their row count and hash enter the manifest. FRED needs no key.

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
7. **Literature DOIs** (§3) have not yet been verified; they will be recorded here with the results.
