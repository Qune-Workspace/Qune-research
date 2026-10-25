"""Study 006 constants (PREREGISTRATION.md).  Kept apart from ``config.py``,
which is Study 002's file copied unchanged (§16, 2026-10-25), so that the
copied modules stay byte-identical.  Every number cites the section that
fixes it; nothing here is tunable.
"""

from __future__ import annotations

from .config import RESULTS_DIR

# --- Windows, as signal months (inclusive); the last month of each starts no
# holding period inside the window (as Study 002's config) ---
# §5.3.1: 192 overlap periods, execution 2003-01-02 to period end 2019-01-02.
OVERLAP_FIRST_SIGNAL_MONTH = "2002-12"
OVERLAP_LAST_SIGNAL_MONTH = "2018-12"
OVERLAP_PERIODS = 192
# §5.3.4: descriptive split of the overlap by the calendar year of the
# execution date that starts the period: 2003-2007 and 2008-2018.
OVERLAP_SPLIT_YEAR = 2008
# §5.4 and §8.1: the test window, 593 periods from the first execution date of
# August 1969 (signal July 1969) to the first execution date of January 2019.
TEST_FIRST_SIGNAL_MONTH = "1969-07"
TEST_LAST_SIGNAL_MONTH = "2018-12"
TEST_PERIODS = 593
# §8.2: the 2019-2026 episode, 93 periods.
EPISODE_FIRST_SIGNAL_MONTH = "2018-12"
EPISODE_LAST_SIGNAL_MONTH = "2026-09"
EPISODE_PERIODS = 93

# --- Gate bounds (§5.3.3), compared at full precision ---
DESIGN_MDE = 0.02  # C2-bar MDE at the design point, a year (power file, 21f850b)
Z_SUM = 2.0 + 0.842  # C2 bar plus the 80%-power quantile
G1_MAX = 0.0018  # |mean(e)| x 12: a quarter of DESIGN_MDE / Z_SUM, rounded as registered
G2_MAX = 0.32  # sd(g) / sd(x_ETF)

# --- Volatility check (§5.4) ---
VOL_BAR = 0.1018  # committed bar for a 2%-a-year C2-bar MDE at w = 0.5
VOL_BAR_ONE_PERCENT = 0.0509

# --- Sub-windows of the test window, descriptive (§8.1), by the month of the
# period's execution date; Study 001's §9.6 sub-periods come from config.py ---
SUB_WINDOWS = {
    "1969-08 to 2002-12 (before any ETF)": ("1969-08", "2002-12"),
    "2003-01 to 2018-12 (the gate's overlap)": ("2003-01", "2018-12"),
}
LOW_POWERED_SWITCHES = 8  # §8.1: fewer switches in the window -> "low-powered"
ASSUMED_NW_IID_RATIO = 0.972  # §5.4: Study 003's observed ratio, assumed by the power file

# --- Programme-level family count (§9.4), descriptive.  Trials of a term-spread
# or curve-slope duration rule whose return had been seen, in time order:
# (date, where, ids, count).  Counted 2026-10-25 03:1x London: the desk's
# private trial registry (555 rows) holds none (its "term=" rows are VIX
# futures term-structure cells, a different signal); in the public trial logs
# only Studies 001 and 002 registered T1-T3, and neither computed a return.
# Re-counted before the history run (§14 step 7); a change is a dated row here.
PROGRAMME_FAMILY = (("2026-10-25", "Study 006 T1-T3, the history run", "trials.md", 3),)

# --- Vendors (§5.3.2): preferred first ---
IEF_VENDORS = ("alpaca", "tiingo")
BIL_VENDORS = ("alpaca", "tiingo")

# --- Output folders, each written once (§13) ---
GATE_DIR = RESULTS_DIR / "gate"
VOLCHECK_DIR = RESULTS_DIR / "volcheck"
HISTORY_DIR = RESULTS_DIR / "history"
EPISODE_DIR = RESULTS_DIR / "episode"
