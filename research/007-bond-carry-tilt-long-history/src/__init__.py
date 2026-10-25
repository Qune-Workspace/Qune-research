"""Study 002: term-spread duration switch, re-tested with a roll-down-aware
synthetic series (IEF vs BIL).

Code for the pre-registered design in PREREGISTRATION.md.  Written in the §14
order: step 2 (window-2 data decision) added ``tiingo_bars.py`` and
``overlap_check.py``; step 3 copied the engine from Study 001 unchanged
(``alpaca_bars``, ``backtest``, ``bey``, ``calendar``, ``fred``,
``paper_trade``, ``report``, ``signal``, ``stats``), replaced ``synthetic.py``
with the §5.2 construction and ``config.py`` with this study's thresholds and
windows, rewrote ``validate.py`` for two windows, and added ``reuse_bars.py``.
Modules are run from the study folder as ``python -m src.<module>`` so that
``src/calendar.py`` never shadows the standard-library ``calendar``.
"""
