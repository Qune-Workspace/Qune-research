"""Study 007 volatility check (PREREGISTRATION.md §5.4): once, after the gate
passes and before any rule return.

sigma = annualised standard deviation of the synthetic duration leg's monthly
return over synthetic cash on the 534 test periods (§8.1), and the C2-bar MDE
it implies at w = 0.5 (2% x sigma / 10.18%).  The statistic, the bar and the
consequence are Study 006's ``volcheck.volatility``, copied unchanged and
called on this study's window; the output holds exactly Study 006's registered
keys and nothing else (tests/test_gate007.py).

    python -m src.volcheck007     # §14 step 6; writes results/volcheck/ once
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .calendar import build_schedule, holding_periods
from .config007 import (
    GATE_DIR,
    TEST_FIRST_SIGNAL_MONTH,
    TEST_LAST_SIGNAL_MONTH,
    TEST_PERIODS,
    VOL_BAR_007,
    VOLCHECK_DIR,
)
from .fred import load_series
from .gate import _commit, period_returns
from .synthetic import synthetic_indices
from .volcheck import OUTPUT_KEYS, gate_passed, volatility

__all__ = ["OUTPUT_KEYS", "compute", "gate_passed", "main", "volatility", "write"]


def write(result: dict, out_dir: Path = VOLCHECK_DIR) -> None:
    """Study 006's ``volcheck.write`` with this study's label: the JSON holds
    exactly the registered keys, the note states sigma, the count, the bar
    and the MDE, and the folder is written once."""
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the volatility check runs once (§5.4)")
    out_dir.mkdir(parents=True)
    result = {**result, "run_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "code_commit": _commit()}
    if tuple(result) != OUTPUT_KEYS:
        raise ValueError("volatility check output must hold exactly the registered keys")
    (out_dir / "volcheck.json").write_text(json.dumps(result, indent=2) + "\n")
    text = (
        f"# Study 007 volatility check (§5.4), run once\n\n"
        f"sigma {result['sigma_annual']:.2%} a year over {result['periods']} periods (bar {VOL_BAR_007:.2%}); "
        f"implied C2-bar MDE at w = 0.5 {result['mde_annual']:.2%} a year.\n\n{result['consequence']}.\n\n"
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
    argparse.ArgumentParser(description="Study 007 volatility check (§5.4), run once.").parse_args(argv)
    if not gate_passed(gate_dir):
        raise SystemExit("refused: results/gate/gate.json does not record a passed gate (§5.4, §14 step 6)")
    write(compute(), out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
