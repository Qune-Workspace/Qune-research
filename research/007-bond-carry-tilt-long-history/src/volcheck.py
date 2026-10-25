"""Study 006 volatility check (PREREGISTRATION.md §5.4): once, after the gate
passes and before any rule return.

sigma = annualised standard deviation of the synthetic duration leg's monthly
return over synthetic cash on the 593 test periods, and the C2-bar MDE it
implies under the committed product form at w = 0.5.  Nothing else is written:
no mean of x, no signal (tests/test_gate.py checks the output's keys).

    python -m src.volcheck    # §14 step 6; writes results/volcheck/ once
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from .calendar import build_schedule, holding_periods
from .config006 import (
    DESIGN_MDE,
    GATE_DIR,
    TEST_FIRST_SIGNAL_MONTH,
    TEST_LAST_SIGNAL_MONTH,
    TEST_PERIODS,
    VOL_BAR,
    VOL_BAR_ONE_PERCENT,
    VOLCHECK_DIR,
)
from .fred import load_series
from .gate import _commit, period_returns
from .synthetic import synthetic_indices

OUTPUT_KEYS = ("sigma_annual", "mde_annual", "periods", "bar", "consequence", "run_at_utc", "code_commit")


def volatility(x: np.ndarray) -> dict:
    """sigma and the implied MDE = DESIGN_MDE * sigma / VOL_BAR (§5.4)."""
    sigma = float(np.std(np.asarray(x, dtype=float), ddof=1) * np.sqrt(12.0))
    above = sigma > VOL_BAR
    return {
        "sigma_annual": sigma,
        "mde_annual": DESIGN_MDE * sigma / VOL_BAR,
        "periods": int(len(x)),
        "bar": VOL_BAR,
        "consequence": (
            "sigma above the bar: title and first paragraph carry 'low-power check'; the 'supported in history' row "
            "becomes 'consistent with an edge, not detectable at the 2% bar' (§5.4)"
            if above
            else "sigma at or below the bar: the criteria stand as registered (§5.4)"
        )
        + f"; the study cannot see an edge of 1% a year or less (1% bar: sigma <= {VOL_BAR_ONE_PERCENT:.2%})",
    }


def compute() -> dict:
    dgs10, dtb3, dgs7 = load_series("DGS10"), load_series("DTB3"), load_series("DGS7")
    periods = holding_periods(build_schedule(dgs10, dtb3, TEST_FIRST_SIGNAL_MONTH, TEST_LAST_SIGNAL_MONTH))
    if len(periods) != TEST_PERIODS:
        raise ValueError(f"{len(periods)} test periods, expected {TEST_PERIODS}")
    synthetic = synthetic_indices(dgs10, dtb3, dgs7)
    starts, ends = periods["execution_date"], periods["period_end"]
    x = period_returns(synthetic["IEF"], starts, ends) - period_returns(synthetic["BIL"], starts, ends)
    return volatility(x)


def write(result: dict, out_dir: Path = VOLCHECK_DIR) -> None:
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the volatility check runs once (§5.4)")
    out_dir.mkdir(parents=True)
    result = {**result, "run_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "code_commit": _commit()}
    if tuple(result) != OUTPUT_KEYS:
        raise ValueError("volatility check output must hold exactly the registered keys")
    (out_dir / "volcheck.json").write_text(json.dumps(result, indent=2) + "\n")
    text = (
        f"# Study 006 volatility check (§5.4), run once\n\n"
        f"sigma {result['sigma_annual']:.2%} a year over {result['periods']} periods (bar {VOL_BAR:.2%}); "
        f"implied C2-bar MDE {result['mde_annual']:.2%} a year.\n\n{result['consequence']}.\n\n"
        f"Run {result['run_at_utc']}, code {result['code_commit'][:7]}. No mean return, no signal, no rule return.\n"
    )
    (out_dir / "volcheck.md").write_text(text)
    print(text)


def gate_passed(gate_dir: Path = GATE_DIR) -> bool:
    path = gate_dir / "gate.json"
    return path.exists() and json.loads(path.read_text()).get("outcome") == "PASS"


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Study 006 volatility check (§5.4), run once.").parse_args(argv)
    if not gate_passed():
        raise SystemExit("refused: results/gate/gate.json does not record a passed gate (§5.4, §14 step 6)")
    write(compute())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
