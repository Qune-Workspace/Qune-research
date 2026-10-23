"""qune_research: the shared research library (Study 004 PREREGISTRATION.md §13).

Built after the Study 004 pre-registration was committed and before any of
its data were fetched.  Studies 001–003 keep their own frozen code and do
not import this package.

Modules
-------
dates     month-end signal dates and next-bar execution dates from a bar index
sizing    time-series trend signals, close-to-close volatility, capped
          inverse-volatility weights with a no-leverage scale-down (§6.1–§6.2)
engine    multi-asset monthly backtest with drift and per-asset costs (§6.3–§6.4)
stats     metrics and inference (§9.3–§9.4), ported from Study 003 by attribution,
          with the degenerate-resample rule for the bootstrap interval (§2.5)
nyse      rule-based NYSE trading calendar (ported from Study 003 by attribution)
data      vendor adapters with provenance hashing (Tiingo, Alpaca, FRED) and the
          hash-checked reuse of an earlier study's file; every path a parameter
datacheck coverage against the NYSE calendar and two-vendor overlap statistics,
          with no threshold of any study (§5.3.1–§5.3.2)
risk      ex-ante risk model: EWMA and Ledoit-Wolf-shrunk covariance forecasts,
          portfolio volatility, Euler risk contributions, VaR/ES (normal and
          historical), historical stress windows, a drawdown-control multiplier
          and forecast-accuracy statistics (built 2026-10-23, after Study 004's
          results; describes a weight vector, never sizes one)
"""

__version__ = "0.1.0"
