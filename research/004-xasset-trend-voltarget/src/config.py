"""Pre-registered constants and repository paths (PREREGISTRATION.md).

Every number here is fixed by the pre-registration; the section that fixes it
is cited next to it.  Nothing in this module is tunable.  Layout follows
Study 003's ``config.py``.
"""
from __future__ import annotations

from pathlib import Path

# --- Paths (relative to the study folder; nothing outside the repository) ---
STUDY_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = STUDY_DIR.parent.parent
RAW_DIR = STUDY_DIR / "data" / "raw"
RESULTS_DIR = STUDY_DIR / "results"
CHECKS_DIR = RESULTS_DIR / "checks"
MANIFEST_PATH = RESULTS_DIR / "data_manifest.json"
PAPER_LOG_DIR = STUDY_DIR / "paper-log"
STUDY_001_DIR = STUDY_DIR.parent / "001-slope-duration-switch"
STUDY_002_DIR = STUDY_DIR.parent / "002-slope-duration-switch-r"
STUDY_003_DIR = STUDY_DIR.parent / "003-bond-tsmom-ief"

# --- Instruments (§4): four classes, twelve ETFs; inception as known to the
# author, confirmed or corrected from the first vendor bar at §5.3.1 ---
UNIVERSE = {
    "equities": ("SPY", "IWM", "EFA", "EEM"),
    "treasuries": ("SHY", "IEF", "TLT"),
    "credit": ("LQD", "HYG"),
    "real_assets": ("GLD", "DBC", "VNQ"),
}
SYMBOLS = tuple(s for group in UNIVERSE.values() for s in group)
CLASS_OF = {s: c for c, group in UNIVERSE.items() for s in group}
CASH_ETF = "BIL"
EXPECTED_INCEPTION = {"SPY": "1993-01", "IWM": "2000-05", "EFA": "2001-08", "EEM": "2003-04",
                      "SHY": "2002-07", "IEF": "2002-07", "TLT": "2002-07", "LQD": "2002-07",
                      "HYG": "2007-04", "GLD": "2004-11", "DBC": "2006-02", "VNQ": "2004-09"}
EXPECTED_ENTRY_SIGNAL_DATE = {"SPY": "2003-12-31", "IWM": "2003-12-31", "EFA": "2003-12-31", "EEM": "2004-04-30",
                              "SHY": "2003-12-31", "IEF": "2003-12-31", "TLT": "2003-12-31", "LQD": "2003-12-31",
                              "HYG": "2008-04-30", "GLD": "2005-11-30", "DBC": "2007-02-28", "VNQ": "2005-09-30"}

# --- Data (§5.1): one vendor for every return; files reused from earlier
# studies after a SHA-256 check against that study's manifest ---
VENDOR_FETCH_START = "2002-07-01"          # §5.3.1: from 2002-07-01 or the fund's first bar
VENDOR_FETCH_END = "2026-09-30"
REUSED_VENDOR_FILES = {"IEF": ("tiingo_IEF_daily.csv", STUDY_002_DIR),   # fetched under Study 002
                       CASH_ETF: ("tiingo_BIL_daily.csv", STUDY_003_DIR)}  # fetched under Study 003
REUSED_BROKER_FILES = {"IEF": ("alpaca_IEF_1Day_all.csv", STUDY_001_DIR),
                       CASH_ETF: ("alpaca_BIL_1Day_all.csv", STUDY_001_DIR)}
REUSED_FRED_FILE = ("fred_DTB3.csv", STUDY_003_DIR)
FRED_SERIES = "DTB3"
BIL_EXPENSE_RATIO = 0.001356    # Study 001 §4, inherited through Study 003 §5.2 (cash accrual only)

# --- Data checks (§5.3) ---
COVERAGE_END = "2026-09-30"                # §5.3.1: from each file's first bar to this date
MAX_CONSECUTIVE_MISSING = 3                # §5.3.1
FETCH_ATTEMPTS = 2                         # §5.3.1: a failing fetch or coverage is retried once
OVERLAP_START = "2016-01-04"               # §5.3.2
OVERLAP_END = "2018-12-31"
OVERLAP_MEAN_DIFF_ABS_MAX = 0.0020         # §5.3.2: ±0.20% p.a., the only gate
OVERLAP_EXANTE_ABS_MAX = 0.0010            # §5.3.2: ex-ante expectation, under 0.10% p.a. for every symbol
BROKER_FETCH_START = OVERLAP_START         # the broker's bars serve the overlap check only (§5.1)
BROKER_FETCH_END = OVERLAP_END
HALT_MAX_EXCLUSIONS = 3                    # §5.3.2 / §5.3.5: more than three exclusions halts
HALT_MIN_PER_CLASS = 2                     # §5.3.2 / §5.3.5: any class below two halts

# --- Rule (§6, §7): no parameter is tunable; these are the canonical values ---
LOOKBACKS_MONTHS = {"T1": (12,), "T2": (6,), "T3": (3,), "T4": (12, 6, 3)}
SIGMA_TARGET = 0.10                        # §6.2 σ_a
WEIGHT_CAP = 0.25                          # §6.2 w_cap
VOL_WINDOW_DAYS = 63                       # §6.2
MIN_RETURN_DAYS_FOR_ENTRY = 63             # §8.1: 63 trading days of returns to t (64 bars)

# --- Sample split (§8) ---
INSAMPLE_FIRST_SIGNAL_DATE = "2003-12-31"
INSAMPLE_LAST_SIGNAL_MONTH = "2018-12"
OOS_FIRST_SIGNAL_MONTH = "2018-12"
OOS_LAST_SIGNAL_MONTH = "2026-09"

# --- Costs, bp of traded notional, one side (§9.2); stress = 2× base ---
COST_BP_BASE = {"SPY": 2.0, "IWM": 2.0, "EFA": 2.5, "EEM": 3.0, "SHY": 2.0, "IEF": 2.0, "TLT": 2.0,
                "LQD": 2.5, "HYG": 3.0, "GLD": 2.0, "DBC": 3.5, "VNQ": 2.5}
COST_STRESS_MULTIPLE = 2.0

# --- Trials (§7) ---
TRIAL_IDS = ("T1", "T2", "T3", "T4")
N_TRIALS_REGISTERED = 4

# --- Decision criteria (§9.5) and the §9.6 descriptives ---
C1_SHARPE_MARGIN = 0.10                    # §9.5 C1: against B4 and B3
C2_T_MIN = 2.0                             # §9.5 C2: Newey–West t of mean(T1 − B4)
C3_DSR_MIN = 0.95                          # §9.5 C3 at N = 4
NOT_SUPPORTED_T_MAX = -1.0                 # §9.5: O1 fails with t ≤ −1.0 → not supported
N_TRIALS_SENSITIVITY = 10                  # §7, §9.4
POWER_MIN_SWITCHES = 40                    # §9.6: fewer on/off switches in-sample → "low-powered"
COST_MULTIPLES_BREAKEVEN = (0.0, 0.5, 1.0, 2.0, 3.0, 5.0)   # §9.6 breakeven cost curve
SUBPERIODS = {"2004-01..2008-12": ("2004-01", "2008-12"),    # §9.6, by holding-period start month
              "2009-01..2015-12": ("2009-01", "2015-12"),
              "2016-01..2018-12": ("2016-01", "2018-12")}
CRISIS_WINDOWS = {"GFC 2008-09-01..2009-02-28": ("2008-09-01", "2009-02-28", "insample"),      # §9.6 [HRvH16]
                  "COVID 2020-02-19..2020-03-23": ("2020-02-19", "2020-03-23", "oos"),
                  "COVID 2020-02-19..2020-08-31": ("2020-02-19", "2020-08-31", "oos"),
                  "2022 2022-01-01..2022-10-31": ("2022-01-01", "2022-10-31", "oos")}
B2_WEIGHTS = {"SPY": 0.60, "IEF": 0.40}    # §9.1 B2 (SPY = the pre-registered vendor series, §16 2026-10-22 consequence 2)
REFERENCE_SYMBOLS = ("SPY", "IEF")         # §9.6 crisis table and correlations
VOL_REALISED_WINDOW_MONTHS = 12            # §9.6 forecast vs realised
VOL_EXCEEDANCE_FACTOR = 1.5                # §9.6: "realised exceeded forecast by more than half"
# The pre-registration fixes no bootstrap seed; Study 003's (20261021) is inherited so that
# every resample is reproducible.  Recorded in §16 at the in-sample run.
SEED = 20261021

# --- Forward record (§11; code added at §14 step 11 on 2026-10-23, before the first forward month-end;
# §16 entry of that date).  No paper order. ---
FORWARD_FIRST_SIGNAL_DATE = "2026-10-30"         # the first month-end after the note's publication (2026-10-23)
FORWARD_EARLIEST_UTC = (21, 15)                  # no record before 21:15 UTC on the signal date (after the New York close)
FORWARD_BARS_START = "2025-06-02"                # bars fetched from here: covers t_12 and the 63 return days of every record
FORWARD_BOOK_USD = 10_000.0                      # §11.1: notional book, marked at the closes, starts all cash
FORWARD_LABEL = "not supported; forward shadow record (section 11); no paper order"
FORWARD_RAW_DIR = PAPER_LOG_DIR / "raw"          # git-ignored; data/raw/ and results/data_manifest.json are never touched
FORWARD_MANIFEST = PAPER_LOG_DIR / "manifest.json"
FORWARD_DECISIONS_DIR = PAPER_LOG_DIR / "decisions"
FORWARD_SHADOW_CSV = PAPER_LOG_DIR / "shadow.csv"
FORWARD_BOOKS_DIR = PAPER_LOG_DIR / "books"      # the three books' values and drifted weights at each period end
