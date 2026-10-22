"""Forward paper-trading path for Study 003 (PREREGISTRATION.md §11).

``decide`` computes the month-end decision record from Alpaca daily bars with
the study's own signal code; the order leg lives with the desk's paper client
and its risk engine (see paper/README.md).  Nothing here is ever backdated.
"""
