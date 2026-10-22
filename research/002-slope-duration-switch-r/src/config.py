"""Pre-registered constants and repository paths (PREREGISTRATION.md).

Every number here is fixed by the pre-registration; the section that fixes it
is cited next to it.  Nothing in this module is tunable.  Sections not
restated in Study 002's document are inherited from Study 001's (§0), and
the values below that carry a Study 001 citation are copied from there
unchanged.
"""
from __future__ import annotations

from pathlib import Path

# --- Paths (relative to the study folder; nothing outside the repository) ---
STUDY_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = STUDY_DIR / "data" / "raw"
RESULTS_DIR = STUDY_DIR / "results"
MANIFEST_PATH = RESULTS_DIR / "data_manifest.json"
PAPER_LOG_DIR = STUDY_DIR / "paper-log"

# --- Instruments (§4) ---
DURATION_LEG = "IEF"
CASH_LEG = "BIL"
SYMBOLS = (DURATION_LEG, CASH_LEG)

# --- FRED series (§5.1; DGS7 is core in this study) ---
FRED_SERIES = ("DGS10", "DTB3", "DGS7")

# --- Expense ratios, p.a., deducted inside the synthetic series (§4, §5.2) ---
IEF_EXPENSE_RATIO = 0.0015      # verified 2026-10-21 (§4)
BIL_EXPENSE_RATIO = 0.001356    # Study 001 §4, not re-verified (§4)

# --- Synthetic duration leg (§5.2): a single par bond with BOND_YEARS to
# maturity at purchase, bought at the par yield interpolated linearly between
# the CURVE_SHORT_YEARS and CURVE_LONG_YEARS constant-maturity yields, held
# for one observation, and repriced with its maturity shortened by the
# elapsed time at the interpolated par yield for that shortened maturity.
# The maturity is the midpoint of the index's 7-10-year range, not fitted.
BOND_YEARS = 8.5
BOND_PERIODS = 17               # 2 * BOND_YEARS semi-annual periods at purchase
CURVE_SHORT_YEARS = 7.0         # DGS7
CURVE_LONG_YEARS = 10.0         # DGS10
CURVE_SHORT_SERIES = "DGS7"
CURVE_LONG_SERIES = "DGS10"

# --- Synthetic-series cross-check tolerance (§5.2): 0.5 bp per day on average ---
DC_CROSSCHECK_TOLERANCE = 0.5e-4

# --- Alpaca bar history available for the ETFs (§5.4) ---
ETF_BARS_START = "2016-01-04"

# --- Validation (§5.3): two windows, instrument returns only, one run. ---
# Window 1 (§5.3.3, required): Alpaca IEF and BIL, adjustment='all'.
VALIDATION_START = "2016-01-04"
VALIDATION_END = "2018-12-31"
# Window 2 (§5.3.4, conditional; decision recorded in
# results/validation/window2_data_decision.json before any validation run):
# second-vendor IEF, split- and distribution-adjusted close; no cash check.
WINDOW2_START = "2003-01-02"
WINDOW2_END = "2015-12-31"
WINDOW2_DECISION_PATH = RESULTS_DIR / "validation" / "window2_data_decision.json"

# A1-A3 and B1-B2 unchanged from Study 001 (§5.3.2); A4 is the central
# estimate +/- the sum of the absolute component ranges of §5.3.1, so it is a
# band rather than a symmetric limit: [-0.25%, +0.35%] p.a. on window 1
# (centre +0.05, half-width 0.30) and [-0.45%, +0.35%] p.a. on window 2
# (centre -0.05, half-width 0.40).  IEF minus synthetic, annualised.
VALIDATION_THRESHOLDS = {
    "A1_corr_min": 0.95,
    "A2_slope_min": 0.80,
    "A2_slope_max": 1.05,
    "A3_tracking_error_max": 0.015,
    "A4_mean_diff_min_window1": -0.0025,
    "A4_mean_diff_max_window1": 0.0035,
    "A4_mean_diff_min_window2": -0.0045,
    "A4_mean_diff_max_window2": 0.0035,
    "B1_mean_diff_abs_max": 0.0030,
    "B2_tracking_error_max": 0.0050,
}
# Ex-ante central estimate of IEF minus synthetic, % p.a. (§5.3.1), printed
# next to the observed value whatever the outcome (§5.3.5).
A4_CENTRAL_ESTIMATE = {"window1": 0.0005, "window2": -0.0005}
# D1 (§5.3.3, descriptive, no decision weight): the roll-down the construction
# earns in each calendar year of window 1, from exante_bias.py (§5.3.5).
ROLLDOWN_ESTIMATE_BY_YEAR = {"2016": 0.00533, "2017": 0.00438, "2018": 0.00147}

# --- Sample split (§8): signal months, inclusive.  The holding period that
# starts at a month's execution date ends at the next month's execution date,
# so the last signal month of each window produces no holding period inside it.
# In-sample from the first execution date of August 1969 (first signal date
# the last FRED business day of July 1969, the first month with DGS7; §8.1).
INSAMPLE_FIRST_SIGNAL_MONTH = "1969-07"
INSAMPLE_LAST_SIGNAL_MONTH = "2018-12"
OOS_FIRST_SIGNAL_MONTH = "2018-12"
OOS_LAST_SIGNAL_MONTH = "2026-09"
T3_FIRST_SIGNAL_MONTH = "1969-07"  # DGS7 starts 1969-07-01 (§7)

# --- Sub-periods (§8.1, fixed by Study 001's §16 decision), by the calendar
# month of the holding period's start ---
SUBPERIODS = {
    "1969-08 to 1981-12 (rising rates)": ("1969-08", "1981-12"),
    "1982-01 to 2008-12 (disinflation)": ("1982-01", "2008-12"),
    "2009-01 to 2018-12 (zero lower bound and QE)": ("2009-01", "2018-12"),
}

# --- Costs, per trade per ETF, one side, fraction of traded notional (Study 001 §9.2) ---
COST_CASES = {"base": 2e-4, "stress": 4e-4}

# --- Trials (§7) and deflation (Study 001 §9.4) ---
TRIAL_IDS = ("T1", "T2", "T3")
N_TRIALS_REGISTERED = 3
N_TRIALS_SENSITIVITY = 10
T2_WINDOW = 21
DSR_VARIANCE_FLOOR = (0.05 / 12 ** 0.5) ** 2  # a 0.05 annualised Sharpe spread

# --- Inference (Study 001 §9.3) ---
NEWEY_WEST_LAGS = 6
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_BLOCK_MONTHS = 12
SEED = 20261021

# --- Decision thresholds (Study 001 §9.5) ---
C1_SHARPE_MARGIN = 0.10
C2_T_MIN = 2.0
C3_DSR_MIN = 0.95
NOT_SUPPORTED_T_MAX = -1.0

# --- Supervisory stop descriptive (Study 001 §11.4): IEF 5% below its entry close ---
STOP_DESCRIPTIVE_DRAWDOWN = -0.05

# --- Missing ETF bars tolerated on an execution date (Study 001 §6.5) ---
MAX_MISSING_BARS = 3
