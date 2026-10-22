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
"""

__version__ = "0.1.0"
