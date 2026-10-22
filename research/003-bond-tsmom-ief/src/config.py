"""Pre-registered constants and repository paths (PREREGISTRATION.md).

Every number here is fixed by the pre-registration; the section that fixes it
is cited next to it.  Nothing in this module is tunable.  Values that carry a
Study 001 citation are inherited unchanged through §0 of this study's
document; the layout follows Study 002's ``config.py`` (commit 2dfbdd5).
"""
from __future__ import annotations

from pathlib import Path

# --- Paths (relative to the study folder; nothing outside the repository) ---
STUDY_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = STUDY_DIR / "data" / "raw"
RESULTS_DIR = STUDY_DIR / "results"
MANIFEST_PATH = RESULTS_DIR / "data_manifest.json"
PAPER_LOG_DIR = STUDY_DIR / "paper-log"
STUDY_001_DIR = STUDY_DIR.parent / "001-slope-duration-switch"
STUDY_002_DIR = STUDY_DIR.parent / "002-slope-duration-switch-r"

# --- Instruments (§4) ---
DURATION_LEG = "IEF"
CASH_LEG = "BIL"
SYMBOLS = (DURATION_LEG, CASH_LEG)

# --- Data files (§5.1) ---
FRED_SERIES = ("DTB3",)                       # the only FRED series this study uses
TIINGO_IEF_FILE = "tiingo_IEF_daily.csv"      # fetched under Study 002, reused by hash
TIINGO_BIL_FILE = "tiingo_BIL_daily.csv"      # fetched under §5.3.2 step 1 of this study
VENDOR_DECISION_PATH = RESULTS_DIR / "checks" / "bil_vendor_decision.json"   # §5.3.2 step 2 outcome

# --- Expense ratios, p.a. (§4); only BIL's enters a modelled series (§5.2) ---
IEF_EXPENSE_RATIO = 0.0015      # verified 2026-10-21 (§4); informational, the ETF series is actual
BIL_EXPENSE_RATIO = 0.001356    # Study 001 §4, not re-verified; deducted inside the cash accrual

# --- Alpaca bar history available for the ETFs (§5.4) ---
ETF_BARS_START = "2016-01-04"

# --- Signal (§6.1, §7): no parameter is tunable; these are the canonical values ---
MOMENTUM_LOOKBACK_MONTHS = 12   # T1, T2: trailing 12-month excess return
T2_SKIP_MONTHS = 1              # T2: 12-1, excess return measured to the end of month m - 1
T3_SMA_MONTHS = 10              # T3: Faber (2007) 10-month moving average of month-end closes

# --- Data checks (§5.3) ---
# D0 (§5.3.1): the vendor IEF series must cover every NYSE trading day of the
# in-sample period with at most MAX_MISSING_BARS consecutive gaps, and its
# first bar must be on or before the first lookback date.
COVERAGE_START = "2002-07-31"
COVERAGE_END = "2018-12-31"
FIRST_BAR_REQUIRED_ON_OR_BEFORE = "2002-07-31"
# D2 (§5.3.3): annualised mean daily difference BIL - TRI_cash on common
# trading days; B1 is the only gate, B2 is descriptive against its historical
# reference (Study 001's threshold) and its 2016-2018 reading (Study 002).
CASH_CHECK_THRESHOLDS = {"B1_mean_diff_abs_max": 0.0030}
B2_REFERENCE_TRACKING_ERROR = 0.0050
B2_READING_2016_2018 = 0.00288
# Ex-ante component estimate of BIL - TRI_cash, decimal p.a., written in
# §5.3.3 before any check ran; printed next to the observed value whatever the
# outcome (§5.3.5).
CASH_GAP_EXANTE = {
    "central_estimate": 0.0000,
    "sum_of_absolute_ranges": 0.0020,
    "components": {
        "1-3 month bills against the 3-month rate": {"estimate": -0.0002, "range": 0.0005},
        "portfolio yield lags the spot rate by about a month": {"estimate": 0.0004, "range": 0.0004},
        "expense ratio": {"estimate": 0.0, "range": 0.0002},
        "securities lending and other income": {"estimate": 0.0001, "range": 0.0003},
        "price versus NAV at the window ends": {"estimate": 0.0, "range": 0.0001},
        "daily reset and day-count conventions": {"estimate": 0.0, "range": 0.0003},
    },
}
# Window of D2 when the vendor is accepted (§5.3.2); branch F uses the overlap window.
CASH_CHECK_START_FULL = "2007-06-01"
CASH_CHECK_END = "2018-12-31"
OVERLAP_START = "2016-01-04"
OVERLAP_END = "2018-12-31"

# --- Sample split (§8): signal months, inclusive.  The holding period that
# starts at a month's execution date ends at the next month's execution date,
# so the last signal month of each window produces no holding period inside it.
INSAMPLE_FIRST_SIGNAL_MONTH = "2003-07"   # lookback reaches 2002-07-31 (§8.1)
INSAMPLE_LAST_SIGNAL_MONTH = "2018-12"
OOS_FIRST_SIGNAL_MONTH = "2018-12"        # inherited from Studies 001 and 002 (§8.2)
OOS_LAST_SIGNAL_MONTH = "2026-09"

# --- Sub-periods (§9.6), by the calendar month of the holding period's start
# (the execution month) ---
SUBPERIODS = {
    "2003-08 to 2008-12 (hiking cycle and crisis)": ("2003-08", "2008-12"),
    "2009-01 to 2015-12 (zero lower bound and QE)": ("2009-01", "2015-12"),
    "2016-01 to 2018-12 (normalisation)": ("2016-01", "2018-12"),
}

# --- Power statement (§9.6): the author's prior, disclosed in §2.4, and the
# switch count below which the in-sample test is labelled low-powered ---
PRIOR_CASH_SHARE = (0.20, 0.35)
PRIOR_SWITCHES = (10, 20)
POWER_MIN_SWITCHES = 8

# --- Costs, per trade per ETF, one side, fraction of traded notional (Study 001 §9.2) ---
COST_CASES = {"base": 2e-4, "stress": 4e-4}

# --- Trials (§7) and deflation (Study 001 §9.4) ---
TRIAL_IDS = ("T1", "T2", "T3")
N_TRIALS_REGISTERED = 3
N_TRIALS_SENSITIVITY = 10
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

# --- Missing ETF bars tolerated on an execution date, and consecutive missing
# bars tolerated anywhere in the in-sample series (Study 001 §6.5, §5.3.1) ---
MAX_MISSING_BARS = 3
