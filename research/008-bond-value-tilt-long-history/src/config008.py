"""Study 008 constants (PREREGISTRATION.md).  Kept apart from ``config.py``
(Study 002's file), ``config006.py`` and ``config007.py``, all copied
unchanged, so that every copied module stays byte-identical.  Every number
cites the section that fixes it; nothing here is tunable.
"""

from __future__ import annotations

from .config import RESULTS_DIR, STUDY_DIR
from .config006 import G1_MAX, G2_MAX, VOL_BAR, VOL_BAR_ONE_PERCENT
from .config007 import (
    G2_OBSERVED_006,
    G2_OBSERVED_006_FULL,
    G2_REPRODUCTION_TOLERANCE,
    LOW_POWERED_TURNOVER,
    OVERLAP_FIRST_SIGNAL_MONTH,
    OVERLAP_LAST_SIGNAL_MONTH,
    OVERLAP_PERIODS,
    RATE_ERAS,
)

# --- Real-yield history (§5.5, §6.1): the first real yield is that of signal
# month 1969-07, the first month of Study 001's execution calendar. ---
REAL_YIELD_FIRST_SIGNAL_MONTH = "1969-07"
CPI_AVAILABILITY_PATH = RESULTS_DIR / "cpi_availability.csv"  # data step, §16 (a) and (b)

# --- Windows, as signal months (inclusive); the last month of each starts no
# holding period inside the window (Study 002's convention) ---
# §8.1: 534 periods, first execution date 1974-07-01, last period end 2019-01-02
# (results/data_step.json, 2026-10-25 17:25:07Z).
TEST_FIRST_SIGNAL_MONTH = "1974-06"
TEST_LAST_SIGNAL_MONTH = "2018-12"
TEST_PERIODS = 534
# §7: T1b's own window, 474 periods, first execution date 1979-07-02.
T1B_FIRST_SIGNAL_MONTH = "1979-06"
T1B_PERIODS = 474
# §8.1: the era window (decision weight only through the era row), by execution
# month 1986-01 to 2018-12, 396 periods, first execution date 1986-01-02.
ERA_FIRST_EXECUTION_MONTH = "1986-01"
ERA_LAST_EXECUTION_MONTH = "2018-12"
ERA_PERIODS = 396
# §8.2: the 2019-2026 episode, 93 periods (Study 006 §8.2).
EPISODE_FIRST_SIGNAL_MONTH = "2018-12"
EPISODE_LAST_SIGNAL_MONTH = "2026-09"
EPISODE_PERIODS = 93
# §5.3: the gate's 192 overlap periods, Study 006 §5.3.1 (imported above).
assert OVERLAP_PERIODS == 192 and (OVERLAP_FIRST_SIGNAL_MONTH, OVERLAP_LAST_SIGNAL_MONTH) == ("2002-12", "2018-12")

# --- The rule (§6.1, §6.2, §7) ---
TRIAL_IDS = ("T1", "T1a", "T1b")
PRIMARY = "T1"
COMPANIONS = ("T1a", "T1b")
CPI_SERIES = {"T1": "CPIAUCNS", "T1a": "CPILFENS", "T1b": "CPIAUCNS"}  # §16, 17:2x GMT: CPIAUCNS, not CPIAUCNSA
RANK_KIND = {"T1": "expanding", "T1a": "expanding", "T1b": "trailing"}
RANK_N = {"T1": 60, "T1a": 60, "T1b": 120}  # minimum history (expanding) or window (trailing), in defined real yields
WINDOW_OF = {"T1": "test", "T1a": "test", "T1b": "t1b"}
# The first signal month with a weight, fixed by the data step (results/data_step.json); the code checks it.
FIRST_WEIGHT_MONTH = {"T1": "1974-06", "T1a": "1974-06", "T1b": "1979-06"}

# --- Gate and volatility bounds, inherited (§5.3, §5.4) ---
G1_MAX_008 = G1_MAX
G2_MAX_008 = G2_MAX
G2_INHERITED = (G2_OBSERVED_006, G2_OBSERVED_006_FULL, G2_REPRODUCTION_TOLERANCE)
VOL_BAR_008 = VOL_BAR
VOL_BAR_ONE_PERCENT_008 = VOL_BAR_ONE_PERCENT
# §5.4: Study 007's committed 534-period figure that the copied files must reproduce.
# Filled from Study 007 results/volcheck/volcheck.json by volcheck008.py at run time
# (read, not retyped), to this tolerance.
VOL_REPRODUCTION_TOLERANCE = 1e-12
STUDY007_DIR = STUDY_DIR.parent / "007-bond-carry-tilt-long-history"
STUDY006_DIR = STUDY_DIR.parent / "006-term-spread-switch-long-history"
STUDY007_VOLCHECK = STUDY007_DIR / "results" / "volcheck" / "volcheck.json"

# --- Overlap with Studies 006 and 007 (§5.6): only these columns are read ---
OVERLAP_SOURCES = {
    "007": (STUDY007_DIR / "results" / "history" / "monthly_base.csv", "w_T1"),
    "006": (STUDY006_DIR / "results" / "history" / "monthly_base.csv", "T1_holding"),
}
OVERLAP_LEG_LABEL_006 = "IEF"  # 1[h_t = leg]: the value of 006's T1_holding meaning "in the duration leg"
OVERLAP_FLAG = 0.8  # §5.6: above this for T1 the headline states non-independence

# --- Turnover rule (§8.1) ---
LOW_POWERED_TURNOVER_008 = LOW_POWERED_TURNOVER

# --- Programme-level family count (§9.4), decides C3.  (when, where, ids,
# count).  Counted at registration (2026-10-25); re-counted before the history
# run (§14 step 7); a change is a dated row here and in trials.md. ---
PROGRAMME_FAMILY = (
    ("2026-10-22", "Study 003 T1-T3, IEF 2003-2018", "trials.md", 3),
    ("2026-10-23", "Study 005 T1-T3, IEF 2003-08 to 2018-12", "trials.md", 3),
    ("2026-10-25", "Study 006 T1-T3, synthetic leg 1969-2018", "trials.md", 3),
    ("2026-10-25", "Study 007 T1, T1a, T1b, T2, T3, synthetic leg 1974-2018", "trials.md", 5),
    ("this study", "Study 008 T1, T1a, T1b", "trials.md", 3),
)
FAMILY_COUNT_AT_REGISTRATION = sum(row[3] for row in PROGRAMME_FAMILY)
assert FAMILY_COUNT_AT_REGISTRATION == 17
DSR_ALSO_AT = (3, 10)

# --- Sub-windows of the test window, descriptive (§8.1), by execution month ---
SUB_WINDOWS = {
    "1974-07 to 2002-12 (before any ETF)": ("1974-07", "2002-12"),
    "2003-01 to 2018-12 (the gate's overlap)": ("2003-01", "2018-12"),
    "1974-07 to 1985-12 (complement of the era window)": ("1974-07", "1985-12"),
}
RATE_ERAS_008 = RATE_ERAS

# --- Output folders, each written once (§13) ---
GATE_DIR = RESULTS_DIR / "gate"
VOLCHECK_DIR = RESULTS_DIR / "volcheck"
HISTORY_DIR = RESULTS_DIR / "history"
EPISODE_DIR = RESULTS_DIR / "episode"
