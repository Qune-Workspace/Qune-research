"""Pre-registered constants and repository paths (PREREGISTRATION.md).

Every number here is fixed by the pre-registration; the section that fixes it
is cited next to it.  Nothing in this module is tunable.
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

# --- FRED series (§5.1) ---
FRED_SERIES = ("DGS10", "DTB3", "DGS7")

# --- Expense ratios, p.a., deducted inside the synthetic series (§4, §5.2) ---
IEF_EXPENSE_RATIO = 0.0015
BIL_EXPENSE_RATIO = 0.001356

# --- Synthetic-series cross-check tolerance (§5.2): 0.5 bp per day on average ---
DC_CROSSCHECK_TOLERANCE = 0.5e-4

# --- Alpaca bar history available for the ETFs (§5.4) ---
ETF_BARS_START = "2016-01-04"

# --- Validation window (§5.3) ---
VALIDATION_START = "2016-01-04"
VALIDATION_END = "2018-12-31"
VALIDATION_THRESHOLDS = {
    "A1_corr_min": 0.95,
    "A2_slope_min": 0.80,
    "A2_slope_max": 1.05,
    "A3_tracking_error_max": 0.015,
    "A4_mean_diff_abs_max": 0.0040,
    "B1_mean_diff_abs_max": 0.0030,
    "B2_tracking_error_max": 0.0050,
}

# --- Sample split (§8): signal months, inclusive.  The holding period that
# starts at a month's execution date ends at the next month's execution date,
# so the last signal month of each window produces no holding period inside it.
INSAMPLE_FIRST_SIGNAL_MONTH = "1962-01"
INSAMPLE_LAST_SIGNAL_MONTH = "2018-12"
OOS_FIRST_SIGNAL_MONTH = "2018-12"
OOS_LAST_SIGNAL_MONTH = "2026-09"
T3_FIRST_SIGNAL_MONTH = "1969-07"  # DGS7 starts 1969-07-01 (§7)

# --- Sub-periods (§9.6), by the calendar month of the holding period's start ---
SUBPERIODS = {
    "1962-02 to 1981-12 (rising rates)": ("1962-02", "1981-12"),
    "1982-01 to 2008-12 (disinflation)": ("1982-01", "2008-12"),
    "2009-01 to 2018-12 (zero lower bound and QE)": ("2009-01", "2018-12"),
}

# --- Costs, per trade per ETF, one side, fraction of traded notional (§9.2) ---
COST_CASES = {"base": 2e-4, "stress": 4e-4}

# --- Trials (§7) and deflation (§9.4) ---
TRIAL_IDS = ("T1", "T2", "T3")
N_TRIALS_REGISTERED = 3
N_TRIALS_SENSITIVITY = 10
T2_WINDOW = 21
DSR_VARIANCE_FLOOR = (0.05 / 12 ** 0.5) ** 2  # a 0.05 annualised Sharpe spread

# --- Inference (§9.3) ---
NEWEY_WEST_LAGS = 6
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_BLOCK_MONTHS = 12
SEED = 20261021

# --- Decision thresholds (§9.5) ---
C1_SHARPE_MARGIN = 0.10
C2_T_MIN = 2.0
C3_DSR_MIN = 0.95
NOT_SUPPORTED_T_MAX = -1.0

# --- Supervisory stop descriptive (§11.4): IEF 5% below its entry close ---
STOP_DESCRIPTIVE_DRAWDOWN = -0.05

# --- Missing ETF bars tolerated on an execution date (§6.5) ---
MAX_MISSING_BARS = 3
