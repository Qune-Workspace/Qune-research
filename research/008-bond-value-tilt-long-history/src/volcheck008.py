"""Study 008 volatility check (PREREGISTRATION.md §5.4): once, after the gate
passes and before any rule return.

The 534-period figure for this leg, window and calendar is already published
by Study 007 (``results/volcheck/volcheck.json`` there).  It is not re-run as
if new: sigma of x_t(synthetic) over T1's test window is recomputed from the
copied files with Study 006's ``volcheck.volatility`` (copied unchanged) as a
consistency check, and must reproduce Study 007's committed full-precision
figure to 1e-12, or the data step is wrong and nothing is written.

``volcheck.json`` holds exactly Study 006's registered keys (sigma, the count,
the MDE at w = 0.5, the bar, the consequence, time and commit) and nothing
else; the reproduction is recorded beside it in ``reproduction.json`` (Study
007's figure, its file hash, the difference and the tolerance).

    python -m src.volcheck008     # §14 step 6; writes results/volcheck/ once
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .calendar import build_schedule, holding_periods
from .config008 import (
    GATE_DIR,
    STUDY007_VOLCHECK,
    TEST_FIRST_SIGNAL_MONTH,
    TEST_LAST_SIGNAL_MONTH,
    TEST_PERIODS,
    VOL_BAR_008,
    VOL_REPRODUCTION_TOLERANCE,
    VOLCHECK_DIR,
)
from .fred import load_series
from .gate import _commit, period_returns
from .synthetic import synthetic_indices
from .volcheck import OUTPUT_KEYS, gate_passed, volatility

__all__ = ["OUTPUT_KEYS", "check_reproduced", "compute", "gate_passed", "main", "volatility", "write"]


def check_reproduced(result: dict, committed_path: Path = STUDY007_VOLCHECK) -> dict:
    """§5.4: same leg, window and calendar as Study 007, so the figure must be
    Study 007's to 1e-12 and the count the same; otherwise stop."""
    raw = committed_path.read_bytes()
    committed = json.loads(raw)
    if committed["periods"] != result["periods"] or result["periods"] != TEST_PERIODS:
        raise ValueError(
            f"T1's window ({result['periods']} periods) differs from Study 007's ({committed['periods']}): "
            "§5.4 asks for a fresh, labelled figure, which this code does not compute"
        )
    diff = abs(float(result["sigma_annual"]) - float(committed["sigma_annual"]))
    if diff > VOL_REPRODUCTION_TOLERANCE:
        raise ValueError(
            f"sigma {result['sigma_annual']!r} does not reproduce Study 007's committed {committed['sigma_annual']!r} "
            f"(|diff| {diff:.3g} > {VOL_REPRODUCTION_TOLERANCE:g}): the data step is wrong (§5.4)"
        )
    return {
        "committed_007": {"file": "research/007-bond-carry-tilt-long-history/results/volcheck/volcheck.json",
                          "sha256": hashlib.sha256(raw).hexdigest(), "sigma_annual": committed["sigma_annual"],
                          "periods": committed["periods"], "code_commit": committed.get("code_commit")},
        "reproduced_here": float(result["sigma_annual"]),
        "abs_difference": diff,
        "tolerance": VOL_REPRODUCTION_TOLERANCE,
    }


def write(result: dict, reproduction: dict, out_dir: Path = VOLCHECK_DIR) -> None:
    """Study 007's ``volcheck007.write`` with this study's label and the
    reproduction file beside it; the folder is written once."""
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the volatility check runs once (§5.4)")
    result = {**result, "run_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "code_commit": _commit()}
    if tuple(result) != OUTPUT_KEYS:
        raise ValueError("volatility check output must hold exactly the registered keys")
    out_dir.mkdir(parents=True)
    (out_dir / "volcheck.json").write_text(json.dumps(result, indent=2) + "\n")
    (out_dir / "reproduction.json").write_text(json.dumps(reproduction, indent=2) + "\n")
    text = (
        f"# Study 008 volatility check (§5.4), run once: a reproduction of Study 007's figure, not a new one\n\n"
        f"sigma {result['sigma_annual']:.2%} a year over {result['periods']} periods (bar {VOL_BAR_008:.2%}); "
        f"implied C2-bar MDE at w = 0.5 {result['mde_annual']:.2%} a year.\n\n{result['consequence']}.\n\n"
        f"Reproduces Study 007's committed figure: |diff| {reproduction['abs_difference']:.1e} "
        f"≤ {reproduction['tolerance']:g}.\n\n"
        f"Run {result['run_at_utc']}, code {result['code_commit'][:7]}. No mean return, no signal, no rule return.\n"
    )
    (out_dir / "volcheck.md").write_text(text)
    print(text)


def compute() -> dict:
    dgs10, dtb3, dgs7 = load_series("DGS10"), load_series("DTB3"), load_series("DGS7")
    periods = holding_periods(build_schedule(dgs10, dtb3, TEST_FIRST_SIGNAL_MONTH, TEST_LAST_SIGNAL_MONTH))
    if len(periods) != TEST_PERIODS:
        raise ValueError(f"{len(periods)} test periods, expected {TEST_PERIODS}")
    synthetic = synthetic_indices(dgs10, dtb3, dgs7)
    starts, ends = periods["execution_date"], periods["period_end"]
    x = period_returns(synthetic["IEF"], starts, ends) - period_returns(synthetic["BIL"], starts, ends)
    return volatility(x)


def main(argv: list[str] | None = None, gate_dir: Path = GATE_DIR, out_dir: Path = VOLCHECK_DIR) -> int:
    argparse.ArgumentParser(description="Study 008 volatility check (§5.4), run once.").parse_args(argv)
    if not gate_passed(gate_dir):
        raise SystemExit("refused: results/gate/gate.json does not record a passed gate (§5.4, §14 step 6)")
    result = compute()
    write(result, check_reproduced(result), out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
