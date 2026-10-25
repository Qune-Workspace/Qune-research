"""Study 006 2019-2026 episode (PREREGISTRATION.md §8.2): once, after the
history note is committed (§14 step 9).  No decision weight.

Actual IEF and BIL from Alpaca (``adjustment='all'``), with the synthetic
series alongside, on the 93 periods from the first execution date of January
2019 to that of October 2026; B3 at the weight frozen by the history run.
The same engine as the history run (``report.run_window``, Study 002's code);
no criterion and no verdict are computed here.

    python -m src.episode    # writes results/episode/ once
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from . import backtest, report
from .calendar import build_schedule
from .config import CASH_LEG, DURATION_LEG, STUDY_DIR
from .config006 import EPISODE_DIR, EPISODE_FIRST_SIGNAL_MONTH, EPISODE_LAST_SIGNAL_MONTH, EPISODE_PERIODS, HISTORY_DIR
from .synthetic import synthetic_indices

HEADING = "2019–2026 episode (no decision weight)"


def note_committed(study_dir: Path = STUDY_DIR) -> bool:
    """§8.2: the episode runs only after the history note (README.md) is
    committed, unchanged since, and records a verdict."""
    readme = study_dir / "README.md"
    if not readme.exists() or "Verdict" not in readme.read_text(encoding="utf-8"):
        return False
    tracked = (
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", "README.md"], cwd=study_dir, capture_output=True
        ).returncode
        == 0
    )
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "README.md"], cwd=study_dir).returncode == 0
    return tracked and clean


def frozen_weight(history_dir: Path = HISTORY_DIR) -> float:
    return float(json.loads((history_dir / "summary.json").read_text(encoding="utf-8"))["weight_b3"])


def compute(
    fred: dict,
    actual: dict,
    weight_b3: float,
    first_month: str,
    last_month: str,
    out_dir: Path,
    expected_periods: int | None = None,
) -> dict:
    schedule = build_schedule(fred["DGS10"], fred["DTB3"], first_month, last_month)
    if expected_periods is not None and len(schedule) - 1 != expected_periods:
        raise ValueError(f"{len(schedule) - 1} episode periods, expected {expected_periods}")
    bar_dates = actual[DURATION_LEG].index.intersection(actual[CASH_LEG].index)
    resolved = backtest.resolve_execution_dates(schedule, bar_dates)
    synthetic = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    return {
        "study": "006",
        "section": "PREREGISTRATION.md §8.2",
        "heading": HEADING,
        "weight_b3_frozen_from_history": weight_b3,
        "actual": report.run_window(
            f"{HEADING}, actual ETFs",
            actual,
            fred,
            resolved,
            weight_b3,
            out_dir / "actual",
            with_subperiods=False,
            with_daily=True,
        ),
        "synthetic": report.run_window(
            f"{HEADING}, synthetic instruments",
            synthetic,
            fred,
            schedule,
            weight_b3,
            out_dir / "synthetic",
            with_subperiods=False,
            with_daily=False,
        ),
    }


def main(
    argv: list[str] | None = None,
    history_dir: Path = HISTORY_DIR,
    out_dir: Path = EPISODE_DIR,
    study_dir: Path = STUDY_DIR,
) -> int:
    argparse.ArgumentParser(description="Study 006 2019-2026 episode (§8.2), once.").parse_args(argv)
    if not (history_dir / "summary.json").exists():
        raise SystemExit("refused: results/history/summary.json is missing; the episode needs the frozen w (§8.2)")
    if not note_committed(study_dir):
        raise SystemExit("refused: README.md (the history note) is not committed with a verdict (§8.2, §14 step 8)")
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the episode runs once (§8.2)")
    summary = compute(
        report.load_fred(),
        report.actual_indices(),
        frozen_weight(history_dir),
        EPISODE_FIRST_SIGNAL_MONTH,
        EPISODE_LAST_SIGNAL_MONTH,
        out_dir,
        expected_periods=EPISODE_PERIODS,
    )
    summary["run_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary["provenance"] = report.provenance()
    report.write_json(out_dir / "summary.json", summary)
    print(f"episode written to {out_dir.relative_to(STUDY_DIR)} under '{HEADING}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
