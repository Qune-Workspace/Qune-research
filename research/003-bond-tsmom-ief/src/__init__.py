"""Study 003 source package (PREREGISTRATION.md §13).

Written in the §14 order.  Step 2 (BIL vendor decision) added
``tiingo_bars.py`` (from Study 002) and ``bil_overlap_check.py``.  Step 3
copied the engine from Study 002 at commit 2dfbdd5 unchanged (``backtest``,
``stats``, ``fred``, ``alpaca_bars``), copied ``bey`` (bill conversion only)
and the NYSE calendar rules, and added the modules this study's design
needs: ``config`` (constants), ``calendar`` (month-end signal dates from the
bar index), ``cash`` (§5.2 accrual), ``signal`` (T1-T3 from price indices),
``checks`` (D0, D2), ``reuse_bars`` (hash-checked reuse of earlier studies'
files) and ``report`` (runs, decoupled from any yield-spread input).

Modules are run from the study folder as ``python -m src.<module>`` so that
``src/calendar.py`` never shadows the standard-library ``calendar``.
"""
