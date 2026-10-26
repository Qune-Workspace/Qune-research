"""Study 010 history runner on synthetic factor series only."""
import json

import numpy as np
import pandas as pd
import pytest
from src import history

from tests.test_rule import H_END, synthetic

PROG = {"public_trials_md": 41, "with_desk_registry": 603, "method": "synthetic"}


@pytest.fixture(scope="module", autouse=True)
def few_resamples():
    """The registered run uses 10,000 resamples; 200 keep the tests fast and test the same code."""
    old = history.N_RESAMPLES
    history.N_RESAMPLES = 200
    yield
    history.N_RESAMPLES = old


@pytest.fixture(scope="module")
def computed(few_resamples):
    return history.compute(synthetic(21), H_END, PROG)


def test_structure_and_rows(computed):
    s, runs = computed
    b = s["cost_cases"]["base"]["trials"]
    assert set(b) == {"T1", "T1a", "T1b"}
    for k in b:
        assert b[k]["d"]["months"] == 1190
        assert {w: b[k]["windows"][w]["months"] for w in ("P1", "L", "P2", "P")} == {"P1": 432, "L": 630, "P2": 128, "P": 560}
        assert set(b[k]["dsr"]) == {"N3", "N10", "N41", "N603"}
    d = runs["base"]["T1"]["frame"]["d"]
    assert b["T1"]["d"]["mean_pct_a_year"] == pytest.approx(d.mean() * 12)
    assert s["window_row_T1"]["months"] == 560
    assert len(s["descriptive_T1"]["twelve_worst_months_d"]) == 12
    assert s["descriptive_T1"]["episodes_d"]["1929-09 to 1932-12"]["months"] == 40
    assert s["descriptive_T1"]["episodes_d"]["2008-09 to 2009-12"]["months"] == 16
    assert s["descriptive_T1"]["paper_comparison"]["paper_strategy_months"]["B1"]["months"] == 618
    assert list(s["descriptive_T1"]["d_by_decade"])[0] == "1920s" and list(s["descriptive_T1"]["d_by_decade"])[-1] == "2020s"


def test_per_factor_contributions_add_up_to_gross_d(computed):
    s, runs = computed
    fr = runs["base"]["T1"]["frame"]
    pf = s["cost_cases"]["base"]["trials"]["T1"]["per_factor"]
    gross = sum(v["contribution_to_mean_d_gross_pct_a_year"] for v in pf.values())
    assert gross == pytest.approx((fr["T_gross"] - fr["B3"]).mean() * 12, abs=1e-10)
    net = sum(v["contribution_to_mean_d_net_pct_a_year"] for v in pf.values())
    assert net == pytest.approx(fr["d"].mean() * 12, abs=1e-10)
    b = s["cost_cases"]["base"]["trials"]["T1"]
    assert b["hit_rate_pooled"] == pytest.approx(
        sum(v["hit_rate"] * v["months_held"] for v in pf.values()) / sum(v["months_held"] for v in pf.values()))
    assert b["T"]["excess_kurtosis"] == pytest.approx(b["T"]["kurtosis_non_excess"] - 3.0)
    pc = s["descriptive_T1"]["paper_comparison"]["paper_strategy_months"]["T1_gross"]
    assert {"nw_t", "iid_t"} <= set(pc)


def test_seed_makes_the_run_repeatable(computed):
    s2, _ = history.compute(synthetic(21), H_END, PROG)
    a = computed[0]["cost_cases"]["base"]["trials"]["T1"]["sharpe_test_vs_B1"]
    assert s2["cost_cases"]["base"]["trials"]["T1"]["sharpe_test_vs_B1"] == a


def _crit(sT, s1, s3, t, dsr, base_mean, stress_mean, b3_zero=False):
    m = {"T": {"sharpe_annual": sT}, "B1": {"sharpe_annual": s1}, "B3": {"sharpe_annual": s3},
         "B3_identically_zero": b3_zero, "d": {"nw_t": t, "mean_pct_a_year": base_mean}, "dsr": {"N3": {"dsr": dsr}}}
    return history.criteria(m, stress_mean)


def test_criteria_thresholds():
    assert _crit(0.6, 0.5, 0.5, 2.0, 0.95, 1.0, 0.5)["all"]
    assert not _crit(0.59, 0.5, 0.4, 2.5, 0.99, 1.0, 0.5)["C1"]
    assert not _crit(0.6, 0.4, 0.51, 2.5, 0.99, 1.0, 0.5)["C1"]
    assert not _crit(0.6, 0.4, 0.4, 1.99, 0.99, 1.0, 0.5)["C2"]
    assert not _crit(0.6, 0.4, 0.4, 2.5, 0.949, 1.0, 0.5)["C3"]
    assert not _crit(0.6, 0.4, 0.4, 2.5, 0.99, 1.0, -0.1)["C4"]
    z = _crit(0.10, 0.0, float("nan"), 2.5, 0.99, 1.0, 0.5, b3_zero=True)
    assert z["C1"] and z["C1_B3_leg"].startswith("Sharpe(T) >= 0.10")


def test_verdict_precedence_and_label():
    ok, bad = {"all": True}, {"all": False}
    v = history.verdict
    assert v({"T1": bad, "T1a": ok, "T1b": ok}, True, 1.0)["T1"] == "not supported"
    assert v({"T1": ok, "T1a": bad, "T1b": ok}, False, 1.0)["T1"] == "inconclusive (paper's window only)"
    assert v({"T1": ok, "T1a": bad, "T1b": ok}, True, 1.0)["T1"] == "inconclusive (fragile)"
    r = v({"T1": ok, "T1a": ok, "T1b": ok}, True, 1.0)
    assert r["T1"] == "supported in history; forward record pending" and r["T1a"] == "meets C1–C4"
    lab = v({"T1": ok, "T1a": ok, "T1b": bad}, True, 2.5)
    assert lab["T1"].endswith("(Sharpe units; the 2%-a-year bar not met)") and lab["T1b"] == "not supported"
    assert v({"T1": bad, "T1a": ok, "T1b": ok}, True, 2.5)["T1"] == "not supported"
    # §9.5 "any row that is not 'not supported'": a companion meeting C1–C4 is labelled whatever T1's row says
    r2 = v({"T1": bad, "T1a": ok, "T1b": bad}, True, 2.5)
    assert r2["T1a"] == "meets C1–C4 (Sharpe units; the 2%-a-year bar not met)" and r2["T1b"] == "not supported"
    assert r2["return_unit_bar_not_met"] is True
    assert v({"T1": bad, "T1a": ok, "T1b": ok}, True, 1.9)["T1a"] == "meets C1–C4"


def test_main_refusals(tmp_path):
    with pytest.raises(SystemExit, match="APPROVED"):
        history.main([], here=tmp_path)
    (tmp_path / "APPROVED").write_text("approved\n")
    (tmp_path / "results" / "history").mkdir(parents=True)
    with pytest.raises(SystemExit, match="exists"):
        history.main([], here=tmp_path)
    (tmp_path / "results" / "history").rmdir()
    with pytest.raises(SystemExit, match="programme_count"):
        history.main([], here=tmp_path)


def test_monthly_csv_full_precision(computed, tmp_path):
    _, runs = computed
    f = synthetic(21)
    frame = history.monthly_csv(f, runs["base"])
    p = tmp_path / "m.csv"
    frame.to_csv(p, float_format="%.17g")
    back = pd.read_csv(p, index_col="month", float_precision="round_trip")
    assert np.array_equal(back["T1_d"].to_numpy(), runs["base"]["T1"]["frame"]["d"].to_numpy())


def _text(frame: pd.DataFrame, cols: list[str]) -> str:
    lines = ["This file was created using the 209901 CRSP database.", "", "," + ",".join(cols)]
    for p, row in frame[cols].dropna().iterrows():
        lines.append(f"{p.year:04d}{p.month:02d}," + ",".join(f"{v:.2f}" for v in row))
    return "\n".join(lines + ["", "  Annual Factors: January-December", "," + ",".join(cols), "  1927, 1.00"]) + "\n"


def _study(tmp_path):
    """A synthetic study folder: zips, manifest, data step, count, trials row, APPROVED."""
    import hashlib
    import io
    import zipfile

    f = synthetic(21)
    f["Mkt-RF"], f["RF"] = 0.5, 0.1
    files = {
        "F-F_Research_Data_Factors_CSV.zip": ["Mkt-RF", "SMB", "HML", "RF"],
        "F-F_ST_Reversal_Factor_CSV.zip": ["ST_Rev"],
        "F-F_LT_Reversal_Factor_CSV.zip": ["LT_Rev"],
    }
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "results").mkdir()
    man = {"files": {}}
    for n, cols in files.items():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(n.replace("_CSV.zip", ".csv"), _text(f, cols))
        (tmp_path / "data" / "raw" / n).write_bytes(buf.getvalue())
        man["files"][n] = {"sha256": hashlib.sha256(buf.getvalue()).hexdigest()}
    (tmp_path / "results" / "data_manifest.json").write_text(json.dumps(man))
    (tmp_path / "results" / "data_step.json").write_text(json.dumps({"h_end": H_END}))
    (tmp_path / "results" / "programme_count.json").write_text(json.dumps(PROG))
    (tmp_path / "trials.md").write_text(history.HISTORY_ROW + " | synthetic |\n")
    (tmp_path / "APPROVED").write_text("approved (synthetic)\n")
    return tmp_path


def test_full_main_run_then_refuses(tmp_path, capsys):
    here = _study(tmp_path)
    history.main([], here=here)
    out = here / "results" / "history"
    assert {p.name for p in out.iterdir()} == {"monthly_base.csv", "monthly_stress.csv", "summary.json", "verdict.md"}
    assert not (here / "results" / ".history_tmp").exists()
    s = json.loads((out / "summary.json").read_text())
    assert s["h_end"] == H_END and "verdict" in s
    with pytest.raises(SystemExit, match="exists"):
        history.main([], here=here)


@pytest.mark.parametrize("bad", [{"public_trials_md": 1}, {"with_desk_registry": "603"}, {"method": " "}])
def test_bad_programme_count_refused_before_data(tmp_path, bad):
    here = _study(tmp_path)
    (here / "results" / "programme_count.json").write_text(json.dumps({**PROG, **bad}))
    (here / "data" / "raw" / "F-F_LT_Reversal_Factor_CSV.zip").write_bytes(b"not read")  # a read would stop on the hash
    with pytest.raises(SystemExit, match="programme_count"):
        history.main([], here=here)


def test_missing_history_row_and_leftover_tmp_refused(tmp_path):
    here = _study(tmp_path)
    (here / "trials.md").write_text("no row\n")
    with pytest.raises(SystemExit, match="history-run row"):
        history.main([], here=here)
    (here / "trials.md").write_text(history.HISTORY_ROW + "\n")
    (here / "results" / ".history_tmp").mkdir()
    with pytest.raises(SystemExit, match="history_tmp"):
        history.main([], here=here)
