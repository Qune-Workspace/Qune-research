"""Pre-registered constants and repository paths (PREREGISTRATION.md).

Every number here is fixed by the pre-registration; the section that fixes it
is cited next to it.  Nothing in this module is tunable.  Constants that the
frozen Study 003 modules (``trend_signal``, ``cash``, ``bey``, ``switching``,
``schedule``) import are carried under the names those modules use, with the
values Study 003's ``config.py`` fixed (inherited by §0).
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
STUDY_003_DIR = STUDY_DIR.parent / "003-bond-tsmom-ief"
STUDY_004_DIR = STUDY_DIR.parent / "004-xasset-trend-voltarget"
STUDY_003_INSAMPLE_MONTHLY = STUDY_003_DIR / "results" / "insample" / "monthly_base.csv"   # §5.3.4, §5.3.5 (i)

# --- Instruments (§4) ---
DURATION_LEG = "IEF"
CASH_LEG = "BIL"
REGIME_SYMBOL = "SPY"            # regime input only; never held (§4)
SYMBOLS = (DURATION_LEG, CASH_LEG)

# --- Data files (§5.1): reused by SHA-256 check against the named study's manifest ---
REUSED_TIINGO = {DURATION_LEG: ("tiingo_IEF_daily.csv", STUDY_004_DIR),     # fetched under Study 002, reused by 003 and 004
                 REGIME_SYMBOL: ("tiingo_SPY_daily.csv", STUDY_004_DIR)}    # fetched under Study 004 §5.3.1
REUSED_FRED = {"DTB3": ("fred_DTB3.csv", STUDY_003_DIR)}
REUSED_ALPACA = {DURATION_LEG: ("alpaca_IEF_1Day_all.csv", STUDY_003_DIR),  # fetched under Study 001, reused by 003
                 CASH_LEG: ("alpaca_BIL_1Day_all.csv", STUDY_003_DIR)}
REUSED_ALPACA_OVERLAP = {REGIME_SYMBOL: ("alpaca_SPY_1Day_all.csv", STUDY_004_DIR)}   # 2016-2018 only, D1 (§5.3.2)
OVERLAP_SUBDIR = "overlap"       # the 2016-2018 broker SPY file lives apart from the episode fetch of the same name
ALPACA_FETCH = {REGIME_SYMBOL: ("2018-09-01", "2026-09-30")}                 # §5.3.3 step 1
CPI_SERIES = "CPIAUCNS"                                                       # §5.3.3 step 2, §6.1 T3
FETCH_ATTEMPTS_BEFORE_BRANCH = 2                                              # §5.3.3: two attempts on separate runs

# --- Expense ratios (§4; only BIL's enters the cash accrual, §5.2) ---
IEF_EXPENSE_RATIO = 0.0015
BIL_EXPENSE_RATIO = 0.001356

# --- Trend signal (§6.2; Study 003 §6.1 and §7, inherited; only T1's arithmetic is used here) ---
MOMENTUM_LOOKBACK_MONTHS = 12
T2_SKIP_MONTHS = 1               # Study 003's T2; present so the frozen module imports; not run (§15)
T3_SMA_MONTHS = 10               # Study 003's T3; present so the frozen module imports; not run (§15)

# --- Regime variables (§6.1, §7) ---
REGIME_WINDOWS = {"T1": 63, "T2": 252}   # common return days ending at the signal date; no dead band
CPI_THRESHOLD = 0.03                     # T3: twelve-month change of CPIAUCNS above 3.0%
CPI_LAG_MONTHS = 2                       # T3: the value for month m-2 at the signal date of month m
TRIAL_IDS = ("T1", "T2", "T3")
N_TRIALS_REGISTERED = 3
N_TRIALS_SENSITIVITY = 10

# --- Data checks (§5.3) ---
TIINGO_COVERAGE = ("2003-04-01", "2018-12-31")   # §5.3.1 D0, both Tiingo files
ALPACA_COVERAGE = ("2018-09-04", "2026-09-30")   # §5.3.1 D0, the three broker files
IEF_FIRST_BAR_ON_OR_BEFORE = "2002-07-31"        # Study 003's D0, already passed
MAX_CONSECUTIVE_MISSING = 3
OVERLAP_WINDOW = ("2016-01-04", "2018-12-31")    # §5.3.2 D1, descriptive, no gate
OVERLAP_LOW_AGREEMENT = 0.95                     # §5.3.2: below this the note must discuss it; T1 still runs
MIN_POSITIVE_MONTHS = 12                         # §5.3.4: fewer switches the in-sample rows off

# --- Sample split (§8): signal months, inclusive; the last signal month starts no period ---
INSAMPLE_FIRST_SIGNAL_MONTH = "2003-07"
INSAMPLE_LAST_SIGNAL_MONTH = "2018-12"
EPISODE_FIRST_SIGNAL_MONTH = "2018-12"           # §8.2: the hypothesis-generating episode, no decision weight
EPISODE_LAST_SIGNAL_MONTH = "2026-09"
SUBPERIODS = {"2003-08 to 2008-12": ("2003-08", "2008-12"),      # §9.7, by execution month, as Study 003 §9.6
              "2009-01 to 2015-12": ("2009-01", "2015-12"),
              "2016-01 to 2018-12": ("2016-01", "2018-12")}

# --- Costs, per trade per ETF, one side (Study 001 §9.2, inherited) ---
COST_CASES = {"base": 2e-4, "stress": 4e-4}

# --- Inference on the conditional edge (§9.3) ---
NEWEY_WEST_LAGS = 6
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_BLOCK_MONTHS = 12
SEED = 2005                                      # §9.3 item 2, fixed in the pre-registration
MIN_EDGE_PER_MONTH = 0.01 / 12                   # §9.5: the smallest believable edge, 1% a year = 0.083% a month
DSR_VARIANCE_FLOOR = (0.05 / 12 ** 0.5) ** 2     # Study 001 §9.4, inherited; DSR reported without decision weight

# --- Power statement (§9.6) ---
POWER_Z = 1.645 + 0.842                          # one-sided 5% level, 80% power
PRIOR_POSITIVE_SHARE = (0.10, 0.30)              # §2.4, §9.6
PRIOR_SIGMA_D_PER_MONTH = 0.010                  # §9.6 at registration; replaced by the exact figure under D3

# --- Forward record (§11) ---
FORWARD_STOP_POSITIVE_MONTHS = 24
FORWARD_STOP_TOTAL_MONTHS = 60
FORWARD_T_MIN = 2.0
FORWARD_FIRST_SIGNAL_DATE = "2026-10-30"         # §14 step 11: the first month-end after the note's publication (2026-10-23)
FORWARD_EARLIEST_UTC = (21, 15)                  # §16 (step 11): no record before 21:15 UTC on the signal date (after the
                                                 # 16:00 New York close under either EDT or EST; a daily bar fetched
                                                 # during the session would be the partial day)
FORWARD_BARS_START = "2024-01-02"                # §16 (step 11): bars fetched from here so that the 252-day window and the
                                                 # 12-month lookback always have more history than they need
FORWARD_LABEL = "refuted in-sample; forward record (section 11); no paper order"
FORWARD_RAW_DIR = PAPER_LOG_DIR / "raw"          # git-ignored; the study's data/raw/ and its manifest are never touched
FORWARD_MANIFEST = PAPER_LOG_DIR / "manifest.json"
FORWARD_DECISIONS_DIR = PAPER_LOG_DIR / "decisions"
FORWARD_SHADOW_CSV = PAPER_LOG_DIR / "shadow.csv"
FORWARD_INTERIM_JSON = PAPER_LOG_DIR / "interim.json"

# --- Engine conventions inherited by the frozen modules (Study 003 §6.5, §11.4) ---
MAX_MISSING_BARS = 3
STOP_DESCRIPTIVE_DRAWDOWN = -0.05
