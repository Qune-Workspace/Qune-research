"""Study 007 constants (PREREGISTRATION.md).  Kept apart from ``config.py``
(Study 002's file) and ``config006.py`` (Study 006's), both copied unchanged,
so that every copied module stays byte-identical.  Every number cites the
section that fixes it; nothing here is tunable.
"""

from __future__ import annotations

from .config import RESULTS_DIR
from .config006 import G1_MAX, G2_MAX, VOL_BAR, VOL_BAR_ONE_PERCENT

# --- Carry history (§5.5, §6.2): month-end carries are counted from the first
# signal month with DGS7 (Study 001 §16), so that the m-th carry is the m-th
# calendar row. ---
CARRY_FIRST_SIGNAL_MONTH = "1969-07"

# --- Windows, as signal months (inclusive); the last month of each starts no
# holding period inside the window (Study 002's convention) ---
# §8.1: 534 periods, first execution date 1974-07-01, last period end 2019-01-02
# (results/data_step.json, 2026-10-25 11:25:57Z).
TEST_FIRST_SIGNAL_MONTH = "1974-06"
TEST_LAST_SIGNAL_MONTH = "2018-12"
TEST_PERIODS = 534
# §7: T1b's own window, 474 periods, first execution date 1979-07-02.
T1B_FIRST_SIGNAL_MONTH = "1979-06"
T1B_PERIODS = 474
# §8.2: the 2019-2026 episode, 93 periods (Study 006 §8.2).
EPISODE_FIRST_SIGNAL_MONTH = "2018-12"
EPISODE_LAST_SIGNAL_MONTH = "2026-09"
EPISODE_PERIODS = 93
# §5.3.1: the 192 overlap periods of the gate (Study 006 §5.3.1).
OVERLAP_FIRST_SIGNAL_MONTH = "2002-12"
OVERLAP_LAST_SIGNAL_MONTH = "2018-12"
OVERLAP_PERIODS = 192

# --- The rule (§6.2, §6.3, §7) ---
MIN_HISTORY = {"T1": 60, "T1a": 36, "T1b": 120}  # month-end carries before the first weight
TREND_LAG_ROWS = 12  # signal dates between the two index readings of the 12-month excess return
BLEND_CARRY_WEIGHT = 0.5  # T2 = 0.5 x T1's weight + 0.5 x trend signal
TRIAL_IDS = ("T1", "T1a", "T1b", "T2", "T3")
PRIMARY = "T1"
COMPANIONS = ("T1a", "T1b")
SECONDARY = ("T2", "T3")

# --- Gate and volatility bounds, inherited from Study 006 (§5.3.2, §5.4) ---
G1_MAX_007 = G1_MAX
G2_OBSERVED_006 = 0.131  # Study 006 results/gate/gate.json, inherited as observed; reproduced as a check
# The committed full-precision figure (Study 006 results/gate/gate.json, key gate_T1.G2_noise_ratio,
# commit 2026-10-25) that the copied files must reproduce, and the tolerance of that check (§5.3.2).
G2_OBSERVED_006_FULL = 0.13140878732605116
G2_REPRODUCTION_TOLERANCE = 1e-12
G2_MAX_007 = G2_MAX
VOL_BAR_007 = VOL_BAR
VOL_BAR_ONE_PERCENT_007 = VOL_BAR_ONE_PERCENT

# --- Turnover rule (§8.1): total one-way turnover below this -> "low-powered" ---
LOW_POWERED_TURNOVER = 8.0

# --- Programme-level family count (§9.4), decides C3.  (when, where, ids,
# count).  Counted at registration (2026-10-25); re-counted before the history
# run (§14 step 7); a change is a dated row here and in trials.md. ---
PROGRAMME_FAMILY = (
    ("2026-10-22", "Study 003 T1-T3, IEF 2003-2018", "trials.md", 3),
    ("2026-10-23", "Study 005 T1-T3, IEF 2003-08 to 2018-12", "trials.md", 3),
    ("2026-10-25", "Study 006 T1-T3, synthetic leg 1969-2018", "trials.md", 3),
    ("this study", "Study 007 T1, T1a, T1b, T2, T3", "trials.md", 5),
)
FAMILY_COUNT_AT_REGISTRATION = sum(row[3] for row in PROGRAMME_FAMILY)
assert FAMILY_COUNT_AT_REGISTRATION == 14

# --- Sub-windows of the test window, descriptive (§8.1), by execution month ---
SUB_WINDOWS = {
    "1974-07 to 2002-12 (before any ETF)": ("1974-07", "2002-12"),
    "2003-01 to 2018-12 (the gate's overlap)": ("2003-01", "2018-12"),
}
RATE_ERAS = {
    "1974-07 to 1981-12": ("1974-07", "1981-12"),
    "1982-01 to 2008-12": ("1982-01", "2008-12"),
    "2009-01 to 2018-12": ("2009-01", "2018-12"),
}

# --- Output folders, each written once (§13) ---
GATE_DIR = RESULTS_DIR / "gate"
VOLCHECK_DIR = RESULTS_DIR / "volcheck"
HISTORY_DIR = RESULTS_DIR / "history"
EPISODE_DIR = RESULTS_DIR / "episode"
