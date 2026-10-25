"""Study 008 §13 tests (1) and (6) for the volatility check: import graph; the
output's keys, the reproduction of Study 007's committed figure to 1e-12 (and
the refusals when it does not reproduce or the window differs), write-once,
and the refusal without a passed gate.  Constructed returns only; no file in
data/raw/ is read."""

import json

import numpy as np
import pytest
from src import gate008, volcheck008
from src.config008 import STUDY007_VOLCHECK, VOL_BAR_008

from tests.test_carry_rank import _reachable


def test_volcheck008_never_reaches_the_engines():
    reached = _reachable("volcheck008")
    assert not {"backtest", "tilt", "report", "stats", "real_yield"} & reached, reached


def _committed(tmp_path, sigma: float, periods: int = 534):
    path = tmp_path / "volcheck007.json"
    path.write_text(json.dumps({"sigma_annual": sigma, "periods": periods, "code_commit": "abc1234"}))
    return path


def test_reproduction_to_the_tolerance_and_refusals(tmp_path):
    v = volcheck008.volatility(np.tile([0.02, -0.015], 300)[:534])
    ok = volcheck008.check_reproduced(v, _committed(tmp_path, v["sigma_annual"] + 1e-13))
    assert ok["abs_difference"] < 1e-12 and ok["tolerance"] == 1e-12 and len(ok["committed_007"]["sha256"]) == 64
    with pytest.raises(ValueError, match="data step is wrong"):
        volcheck008.check_reproduced(v, _committed(tmp_path, v["sigma_annual"] + 1e-9))
    with pytest.raises(ValueError, match="differs"):
        volcheck008.check_reproduced(v, _committed(tmp_path, v["sigma_annual"], periods=533))
    short = volcheck008.volatility(np.tile([0.02, -0.015], 300)[:533])
    with pytest.raises(ValueError, match="differs"):
        volcheck008.check_reproduced(short, _committed(tmp_path, short["sigma_annual"], periods=533))


def test_study007_committed_figure_is_full_precision():
    committed = json.loads(STUDY007_VOLCHECK.read_text())
    assert committed["periods"] == 534 and isinstance(committed["sigma_annual"], float)
    assert len(repr(committed["sigma_annual"]).split(".")[1]) >= 12  # enough digits for a 1e-12 check


def test_output_keys_label_and_write_once(tmp_path):
    v = volcheck008.volatility(np.tile([0.02, -0.02], 300)[:534])
    rep = volcheck008.check_reproduced(v, _committed(tmp_path, v["sigma_annual"]))
    out = tmp_path / "volcheck"
    volcheck008.write(v, rep, out)
    written = json.loads((out / "volcheck.json").read_text())
    assert tuple(written) == volcheck008.OUTPUT_KEYS
    assert v["mde_annual"] == pytest.approx(0.02 * v["sigma_annual"] / VOL_BAR_008)
    assert json.loads((out / "reproduction.json").read_text())["abs_difference"] == 0.0
    text = (out / "volcheck.md").read_text()
    assert "Study 008" in text and "reproduction of Study 007" in text
    with pytest.raises(SystemExit):
        volcheck008.write(v, rep, out)


def test_refuses_without_a_passed_gate(tmp_path):
    with pytest.raises(SystemExit, match="passed gate"):
        volcheck008.main([], gate_dir=tmp_path / "gate", out_dir=tmp_path / "volcheck")
    (tmp_path / "gate").mkdir()
    halted = gate008.decide({"T1": {"G1_pass": False}, "T1a": {"G1_pass": True}, "T1b": {"G1_pass": True}})
    (tmp_path / "gate" / "gate.json").write_text(json.dumps(halted))
    with pytest.raises(SystemExit, match="passed gate"):
        volcheck008.main([], gate_dir=tmp_path / "gate", out_dir=tmp_path / "volcheck")
    assert not (tmp_path / "volcheck").exists()
