"""Tests for the paper dashboard module on constructed forward records in a temporary folder."""

from __future__ import annotations

import json

import pandas as pd
import pytest
from matplotlib import pyplot as plt

from qune_research import paperlog, style

BOOK_SPEC = paperlog.LogSpec(
    study="Study 004", folder="research/004-test", kind="shadow record", label="not supported",
    first_signal_date="2026-10-30", strategy="T1", benchmarks=("B3", "B4"),
    book_columns={"T1": "T1_book", "B3": "B3_book", "B4": "B4_book"}, book_usd=10_000.0,
    labels={"T1": "Trend T1", "B3": "Equal weight B3", "B4": "Vol-scaled B4"}, data_source="constructed",
)
RETURN_SPEC = paperlog.LogSpec(
    study="Study 005", folder="research/005-test", kind="shadow record", label="refuted in-sample",
    first_signal_date="2026-10-30", strategy="T1", benchmarks=("B1", "B2"),
    return_columns={"T1": "T1", "B1": "B1", "B2": "B2"},
    labels={"T1": "Conditional T1", "B1": "Hold IEF B1", "B2": "Trend B2"}, data_source="constructed",
)
SLEEVE_SPEC = paperlog.LogSpec(
    study="Study 003", folder="research/003-test", kind="paper sleeve", label="not supported",
    first_signal_date="2026-10-30", chart_note="Equity follows the monthly summary (designed, not built).",
)


def _write_record(folder, signal_date, status="ok", execution_date=None, target=None):
    (folder / "decisions").mkdir(parents=True, exist_ok=True)
    record = {"signal_date": signal_date, "status": status, "execution_date": execution_date, "target": target}
    (folder / "decisions" / f"{signal_date}.json").write_text(json.dumps(record))


def _book_shadow(folder, n):
    rows = []
    value = {"T1": 10_000.0, "B3": 10_000.0, "B4": 10_000.0}
    dates = pd.date_range("2026-11-01", periods=n + 1, freq="MS")
    for i in range(n):
        for k, r in (("T1", 0.01), ("B3", 0.005), ("B4", -0.002)):
            value[k] *= 1.0 + r
        rows.append({"signal_date": str((dates[i] - pd.Timedelta(days=3)).date()), "execution_date": str(dates[i].date()),
                     "period_end": str(dates[i + 1].date()), "T1_book": value["T1"], "B3_book": value["B3"],
                     "B4_book": value["B4"]})
    pd.DataFrame(rows).to_csv(folder / "shadow.csv", index=False)
    return rows


def _return_shadow(folder, n):
    dates = pd.date_range("2026-11-01", periods=n + 1, freq="MS")
    rows = [{"signal_date": str((dates[i] - pd.Timedelta(days=3)).date()), "execution_date": str(dates[i].date()),
             "period_end": str(dates[i + 1].date()), "T1": -0.01, "B1": 0.004, "B2": 0.004} for i in range(n)]
    pd.DataFrame(rows).to_csv(folder / "shadow.csv", index=False)
    return rows


@pytest.fixture
def root(tmp_path):
    for spec in (BOOK_SPEC, RETURN_SPEC, SLEEVE_SPEC):
        (tmp_path / spec.folder / "paper-log").mkdir(parents=True)
    return tmp_path


def test_empty_folders_report_nothing_and_the_first_due_date(root):
    st = paperlog.status(root, BOOK_SPEC)
    assert st.records == [] and st.shadow.empty and st.equity.empty and st.executions == []
    assert st.next_due == "2026-10-30"
    assert "no holding period has ended yet" in paperlog.headline(st)
    assert "30 Oct 2026" in paperlog.headline(st)


def test_missing_paper_log_folder_is_empty_not_an_error(tmp_path):
    st = paperlog.status(tmp_path, BOOK_SPEC)
    assert st.records == [] and st.equity.empty and st.inputs == {}


def test_next_signal_date_is_the_last_nyse_trading_day_of_the_following_month():
    assert paperlog.next_signal_date(None, "2026-10-30") == "2026-10-30"
    assert paperlog.next_signal_date("2026-10-30", "2026-10-30") == "2026-11-30"
    assert paperlog.next_signal_date("2026-11-30", "2026-10-30") == "2026-12-31"
    # December 2027: the 31st is a Friday and a trading day.
    assert paperlog.next_signal_date("2027-11-30", "2026-10-30") == "2027-12-31"


def test_book_columns_are_read_as_written_with_the_start_row_prepended(root):
    folder = root / BOOK_SPEC.folder / "paper-log"
    rows = _book_shadow(folder, 3)
    _write_record(folder, "2026-10-30", execution_date="2026-11-02", target={"SPY": 0.2, "IEF": 0.0})
    st = paperlog.status(root, BOOK_SPEC)
    eq = st.equity
    assert list(eq.columns) == ["T1", "B3", "B4"]
    assert len(eq) == 4 and eq.index[0] == pd.Timestamp("2026-11-01")
    assert eq.iloc[0].tolist() == [10_000.0, 10_000.0, 10_000.0]
    assert eq["T1"].iloc[-1] == pytest.approx(rows[-1]["T1_book"])
    assert eq["B4"].iloc[-1] == pytest.approx(rows[-1]["B4_book"])
    assert st.next_due == "2026-11-30"
    assert set(st.inputs) == {f"{BOOK_SPEC.folder}/paper-log/shadow.csv",
                              f"{BOOK_SPEC.folder}/paper-log/decisions/2026-10-30.json"}


def test_return_columns_compound_from_one_unit(root):
    folder = root / RETURN_SPEC.folder / "paper-log"
    _return_shadow(folder, 2)
    eq = paperlog.status(root, RETURN_SPEC).equity
    assert eq["T1"].iloc[0] == 1.0
    assert eq["T1"].iloc[-1] == pytest.approx(0.99 ** 2)
    assert eq["B1"].iloc[-1] == pytest.approx(1.004 ** 2)


def test_shadow_rows_are_sorted_by_period_end_before_compounding(root):
    folder = root / RETURN_SPEC.folder / "paper-log"
    rows = _return_shadow(folder, 3)
    pd.DataFrame(rows[::-1]).to_csv(folder / "shadow.csv", index=False)
    eq = paperlog.status(root, RETURN_SPEC).equity
    assert eq.index.is_monotonic_increasing
    assert eq["B2"].iloc[1] == pytest.approx(1.004)


def test_headline_states_the_gap_in_words_and_warns_about_inference(root):
    folder = root / BOOK_SPEC.folder / "paper-log"
    _book_shadow(folder, 2)
    st = paperlog.status(root, BOOK_SPEC)
    text = paperlog.headline(st)
    assert text.startswith("Study 004: after 2 forward periods, Trend T1 is 1.0 pp ahead of Equal weight B3")
    assert "too few periods" in text
    folder5 = root / RETURN_SPEC.folder / "paper-log"
    _return_shadow(folder5, 1)
    text5 = paperlog.headline(paperlog.status(root, RETURN_SPEC))
    assert "after 1 forward period, Conditional T1 is 1.4 pp behind Hold IEF B1" in text5


def test_chart_passes_the_house_style_check(root):
    folder = root / BOOK_SPEC.folder / "paper-log"
    _book_shadow(folder, 4)
    st = paperlog.status(root, BOOK_SPEC)
    fig = paperlog.chart(st)
    try:
        assert style.check(fig) == []
        texts = [t.get_text() for t in fig.texts]
        assert any(t.startswith("Study 004: after 4 forward periods") for t in texts)
        assert any("Qune Research, Study 004" in t for t in texts)
        colours = {line.get_color() for line in fig.axes[0].get_lines()}
        assert style.ACCENT in colours
    finally:
        plt.close(fig)


def test_render_lists_every_study_and_each_record(root):
    folder = root / BOOK_SPEC.folder / "paper-log"
    _write_record(folder, "2026-10-30", execution_date="2026-11-02", target={"SPY": 0.25, "GLD": 0.1, "IEF": 0.0})
    folder3 = root / SLEEVE_SPEC.folder / "paper-log"
    _write_record(folder3, "2026-10-30", status="signal unavailable")
    (folder3 / "runs.jsonl").write_text('{"mode": "check", "decision": "no-order"}\n\n{"mode": "check"}\n')
    statuses = [paperlog.status(root, s) for s in (BOOK_SPEC, RETURN_SPEC, SLEEVE_SPEC)]
    page = paperlog.render(statuses, "2026-10-24T08:00:00Z", "abc1234", {})
    assert "| Study 004 | shadow record, not supported | 1 | 0 | 30 Nov 2026 |" in page
    assert "| Study 005 | shadow record, refuted in-sample | 0 | 0 | 30 Oct 2026 |" in page
    assert "| 2026-10-30 | 2026-11-02 | ok | GLD 10.0%, SPY 25.0% |" in page
    assert "| 2026-10-30 | n/a | signal unavailable | none |" in page
    assert "| Runner lines in runs.jsonl | 2 |" in page
    assert "Equity follows the monthly summary (designed, not built)." in page
    assert "No chart yet: the first shadow line follows the record after 30 Oct 2026." in page
    assert "commit `abc1234`" in page and "2026-10-24T08:00:00Z" in page


def test_build_writes_page_chart_and_manifest_only_for_studies_with_lines(root):
    folder = root / BOOK_SPEC.folder / "paper-log"
    _book_shadow(folder, 2)
    _write_record(folder, "2026-10-30", execution_date="2026-11-02")
    out = root / "dashboard"
    manifest = paperlog.build(root, [BOOK_SPEC, RETURN_SPEC, SLEEVE_SPEC], out, "2026-10-24T08:00:00Z", commit="deadbee")
    assert (out / "README.md").is_file() and (out / "manifest.json").is_file()
    assert (out / "004_forward.svg").is_file() and (out / "004_forward.png").is_file()
    assert not (out / "005_forward.svg").exists() and not (out / "003_forward.svg").exists()
    assert manifest["commit"] == "deadbee"
    assert [s["records"] for s in manifest["studies"]] == [1, 0, 0]
    assert [s["shadow_lines"] for s in manifest["studies"]] == [2, 0, 0]
    assert set(manifest["outputs_sha256"]) == {"004_forward.svg", "004_forward.png"}
    page = (out / "README.md").read_text()
    assert "![Study 004: after 2 forward periods" in page and "](004_forward.svg)" in page
    assert "| Trend T1 | 10,201.00 USD |" in page
    written = json.loads((out / "manifest.json").read_text())
    assert written["studies"][0]["inputs_sha256"] == paperlog.status(root, BOOK_SPEC).inputs


def test_build_is_byte_identical_for_the_same_inputs_and_stamp(root):
    folder = root / BOOK_SPEC.folder / "paper-log"
    _book_shadow(folder, 2)
    out = root / "dashboard"
    paperlog.build(root, [BOOK_SPEC], out, "2026-10-24T08:00:00Z", commit="deadbee")
    first = {p.name: p.read_bytes() for p in out.iterdir()}
    paperlog.build(root, [BOOK_SPEC], out, "2026-10-24T08:00:00Z", commit="deadbee")
    second = {p.name: p.read_bytes() for p in out.iterdir()}
    assert first == second


def test_shadow_file_is_configurable_for_the_sleeve_summary(root):
    """Study 003 writes its periods to summary.csv (§11.5); the dashboard reads that file, not shadow.csv."""
    spec = paperlog.LogSpec(
        study="Study 003", folder=SLEEVE_SPEC.folder, kind="paper sleeve", label="not supported",
        first_signal_date="2026-10-30", strategy="T1", benchmarks=("B3", "B1"),
        return_columns={"T1": "rule_return", "B3": "B3", "B1": "B1"}, shadow_file="summary.csv")
    folder = root / spec.folder / "paper-log"
    dates = pd.date_range("2026-11-01", periods=3, freq="MS")
    pd.DataFrame([{"signal_date": "2026-10-30", "execution_date": str(dates[i].date()), "period_end": str(dates[i + 1].date()),
                   "rule_return": 0.01, "B3": 0.002, "B1": -0.003} for i in range(2)]).to_csv(folder / "summary.csv", index=False)
    st = paperlog.status(root, spec)
    assert len(st.shadow) == 2 and st.equity["T1"].iloc[-1] == pytest.approx(1.01 ** 2)
    assert f"{spec.folder}/paper-log/summary.csv" in st.inputs
    assert paperlog.status(root, SLEEVE_SPEC).shadow.empty      # the default still reads shadow.csv


# --- Monthly position records (Studies 010 and 011, added 2026-10-26) --------------------------

MONTHLY_SPEC = paperlog.LogSpec(
    study="Study 010", folder="research/010-test", kind="monthly position record", label="not supported",
    first_signal_date="2026-09", records_file="positions.csv", record_format="{factor} {h:+g}",
    release_log="releases/fetch_log.csv", scored_note="once after 60 months", chart_note="No equity line here.",
)
COHORT_SPEC = paperlog.LogSpec(
    study="Study 011", folder="research/011-test", kind="monthly cohort record", label="not supported",
    first_signal_date="2026-09", records_file="cohorts.csv", record_format="long {winners} / short {losers}",
)


def _positions(folder, rows):
    cols = ["month", "trial", "factor", "h", "release", "late"]
    pd.DataFrame(rows, columns=cols).to_csv(folder / "positions.csv", index=False)


def test_monthly_records_group_by_month_and_trial_in_file_order(root):
    folder = root / MONTHLY_SPEC.folder / "paper-log"
    folder.mkdir(parents=True)
    _positions(folder, [("2026-10", "T1", "SMB", -1, "202609", False),
                        ("2026-09", "T1b", "HML", 1, "202608", False),
                        ("2026-09", "T1", "SMB", 1, "202608", False), ("2026-09", "T1", "ST_Rev", -1, "202608", False),
                        ("2026-09", "T1a", "HML", 1, "202608", False)])
    st = paperlog.status(root, MONTHLY_SPEC)
    assert [r["signal_date"] for r in st.records] == ["2026-09", "2026-10"]
    assert st.records[0]["target"] == "T1b: HML +1<br>T1: SMB +1, ST_Rev -1<br>T1a: HML +1"   # file order, not sorted
    assert st.records[0]["release"] == "202608" and st.records[0]["rows"] == 4
    assert st.next_due == "2026-11, from release 202610 (not yet archived)"
    assert st.shadow.empty and st.equity.empty
    assert f"{MONTHLY_SPEC.folder}/paper-log/positions.csv" in st.inputs


def test_monthly_record_with_no_file_is_due_at_its_first_month(tmp_path):
    st = paperlog.status(tmp_path, MONTHLY_SPEC)
    assert st.records == [] and st.last_check is None
    assert st.next_due == "2026-09, from release 202608 (not yet archived)"
    page = paperlog.render([st], "2026-10-26T22:00:00Z", "abc1234", {})
    assert ("| Study 010 | monthly position record, not supported | 0 | none (scored once at the end) | "
            "2026-09, from release 202608 (not yet archived) |") in page
    assert "| Last release check | none logged |" in page and "| Last record | none yet |" in page


def test_a_month_with_two_releases_names_both(root):
    folder = root / MONTHLY_SPEC.folder / "paper-log"
    folder.mkdir(parents=True)
    _positions(folder, [("2026-09", "T1", "SMB", 1, "202608", False), ("2026-09", "T1a", "HML", 1, "202607", False)])
    assert paperlog.status(root, MONTHLY_SPEC).records[0]["release"] == "202607, 202608"


def test_float_positions_pipes_and_blank_reasons_do_not_break_the_page(root):
    folder = root / MONTHLY_SPEC.folder / "paper-log"
    (folder / "releases").mkdir(parents=True)
    _positions(folder, [("2026-09", "T1", "SMB", 1, "202608", False), ("2026-09", "T1", "HML", None, "202608", False)])
    (folder / "releases" / "fetch_log.csv").write_text("at_utc,kept,release,reason\n2026-10-26T22:16:42Z,False,202608,bad | header\n"
                                                        "2026-10-26T23:16:42Z,False,202608,\n")
    st = paperlog.status(root, MONTHLY_SPEC)
    assert st.records[0]["target"] == "T1: SMB +1, HML +nan"
    assert paperlog._check_text(st.last_check) == "26 Oct 2026 23:16Z: release 202608, not kept"
    assert paperlog._check_text({"at_utc": "2026-10-26T22:16:42Z", "kept": "False", "release": "202608",
                                 "reason": "bad | header"}).endswith("(bad \\| header)")


def test_monthly_section_shows_the_record_the_last_check_and_no_chart(root):
    folder = root / MONTHLY_SPEC.folder / "paper-log"
    (folder / "releases").mkdir(parents=True)
    _positions(folder, [("2026-09", "T1", "SMB", 1, "202608", False)])
    (folder / "releases" / "fetch_log.csv").write_text(
        "at_utc,kept,release,reason\n2026-10-26T20:16:05Z,False,202608,not newer\n2026-10-26T22:16:42Z,False,202608,not newer\n")
    out = root / "dashboard"
    manifest = paperlog.build(root, [MONTHLY_SPEC], out, "2026-10-26T22:30:00Z", commit="deadbee")
    page = (out / "README.md").read_text()
    assert "| Last record | 2026-09 from release 202608 |" in page
    assert "| Last release check | 26 Oct 2026 22:16Z: release 202608, not kept (not newer) |" in page
    assert "| Next record due | 2026-10, from release 202609 (not yet archived) |" in page
    assert "| Scoring | once after 60 months |" in page
    assert "| Month | Release | Record by trial |" in page
    assert "| 2026-09 | 202608 | T1: SMB +1 |" in page
    assert "No equity line here." in page
    assert manifest["outputs_sha256"] == {} and not list(out.glob("*.svg"))
    assert manifest["studies"][0]["records"] == 1
    assert manifest["studies"][0]["next_record_due"] == "2026-10, from release 202609 (not yet archived)"
    assert f"{MONTHLY_SPEC.folder}/paper-log/releases/fetch_log.csv" in manifest["studies"][0]["inputs_sha256"]


def test_kept_release_check_is_reported_as_kept(root):
    folder = root / MONTHLY_SPEC.folder / "paper-log"
    (folder / "releases").mkdir(parents=True)
    _positions(folder, [("2026-09", "T1", "SMB", 1, "202608", False)])
    (folder / "releases" / "fetch_log.csv").write_text("at_utc,kept,release,reason\n2026-11-03T15:15:00Z,True,202609,\n")
    st = paperlog.status(root, MONTHLY_SPEC)
    assert paperlog._check_text(st.last_check) == "3 Nov 2026 15:15Z: release 202609 kept"
    assert st.next_due == "2026-10, from release 202609 (archived, record not yet written)"


def test_cohort_lists_are_shown_with_commas_not_semicolons(root):
    folder = root / COHORT_SPEC.folder / "paper-log"
    folder.mkdir(parents=True)
    pd.DataFrame([{"month": "2026-09", "trial": "M1", "winners": "Machn;Oil;Finan", "losers": "Steel;Cnstr;Clths",
                   "release": "202608", "late": False}]).to_csv(folder / "cohorts.csv", index=False)
    st = paperlog.status(root, COHORT_SPEC)
    assert st.records[0]["target"] == "M1: long Machn, Oil, Finan / short Steel, Cnstr, Clths"
    assert "| " not in st.records[0]["target"]


def test_existing_specs_are_unchanged_by_the_monthly_path(root):
    assert not BOOK_SPEC.monthly and paperlog.status(root, BOOK_SPEC).next_due == "2026-10-30"


def test_the_real_010_and_011_specs_read_the_committed_records():
    """The tool's SPECS against the repository's own paper-log files: a typo in a file name or format fails here."""
    import importlib.util
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    spec_ = importlib.util.spec_from_file_location("make_paper_dashboard", repo / "tools" / "make_paper_dashboard.py")
    assert spec_ is not None and spec_.loader is not None
    tool = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(tool)
    monthly = {s.study: s for s in tool.SPECS if s.monthly}
    assert set(monthly) == {"Study 010", "Study 011"}
    st10 = paperlog.status(repo, monthly["Study 010"])
    st11 = paperlog.status(repo, monthly["Study 011"])
    assert st10.records[0]["signal_date"] == "2026-09" and st10.records[0]["release"] == "202608"
    assert st10.records[0]["target"].startswith("T1: SMB +1, HML +1, ST_Rev -1, LT_Rev +1<br>T1a: SMB +1, HML +1<br>T1b: ")
    assert st11.records[0]["target"].startswith("M1: long Machn, Oil, Finan / short Steel, Cnstr, Clths<br>M1a: ")
    assert st10.last_check is not None and st11.last_check is not None
