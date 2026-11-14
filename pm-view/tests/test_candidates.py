"""The printer's candidate record (2026-11-14 12:15Z, predictions/POST_MORTEMS.md "A figure
the gate took on the desk's word"): barrier.py and fomc_calibrate.py --live write what they
read as one line of data/candidates.jsonl, readings.py add copies the four figures from it
by id, and the row gate holds the row to the record (`figures-from-tool`).  Until this date
the figures were typed from the printer's line and held to nothing but [0, 1]."""
import csv
import json
from datetime import UTC, date, datetime
from pathlib import Path

import barrier as B
import fomc_calibrate as F
import pm_lib as L
import readings as R
from test_barrier import NOW as BARRIER_NOW
from test_barrier import calibration, csv_text, series
from test_fomc_calibrate import synthetic_history
from test_readings import QUOTE, history, ns, write_manifest

NOW = datetime(2026, 11, 14, 12, 30, tzinfo=UTC)
LATE_QUOTE = dict(QUOTE, fetched_utc="2026-11-20T06:17:00Z", gamma_sha256="ba" * 32, rules_window="month")
LATE_NOW = datetime(2026, 11, 20, 6, 30, tzinfo=UTC)


def candidate(**kw) -> dict:
    base = dict(method="btc_touch", key="75000:down", method_p=0.876, range_lo=0.876, range_hi=0.886, climatology_p=0.690,
                market_mid=0.925, computed_at=datetime(2026, 11, 6, 6, 20, tzinfo=UTC), inputs={"series": "CBBTCUSD"})
    base.update(kw)
    return L.candidate_record(**base)


# --- the record ------------------------------------------------------------------------------

def test_candidate_record_carries_the_figures_at_three_decimals_and_refuses_what_is_not_a_reading(tmp_path):
    c = candidate()
    assert c["id"] == "K-btc_touch-75000:down-20261106T062000Z" and c["computed_utc"] == "2026-11-06T06:20:00Z"
    assert (c["method_p"], c["range_lo"], c["range_hi"], c["climatology_p"]) == ("0.876", "0.876", "0.886", "0.690")
    assert candidate(range_lo=0.886, range_hi=0.876)["range_lo"] == "0.876"  # the range is ordered
    assert candidate(climatology_p=None)["climatology_p"] is None
    for bad in (dict(method="stated"), dict(range_lo=0.9), dict(method_p=1.2, range_hi=1.2), dict(climatology_p=1.5),
                dict(key="75 000")):
        try:
            candidate(**bad)
        except ValueError:
            continue
        raise AssertionError(f"admitted {bad}")
    path = tmp_path / "data" / "candidates.jsonl"
    assert L.read_candidates(path) == []
    L.append_candidate(path, c)
    L.append_candidate(path, candidate(key="65000:down", method_p=0.3, range_lo=0.3, range_hi=0.35))
    assert [x["id"] for x in L.read_candidates(path)] == [c["id"], "K-btc_touch-65000:down-20261106T062000Z"]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


# --- the printers write it -------------------------------------------------------------------

def test_barrier_writes_a_candidate_per_mid_on_a_fetched_run_and_none_on_a_dry_run_or_a_kept_file(tmp_path, capsys):
    obs = series(120)
    body = csv_text(obs).encode()
    cal = tmp_path / "cal.json"
    cal.write_text(json.dumps(calibration(False)))
    cands = tmp_path / "data" / "candidates.jsonl"
    rc = B.run("2026-11", [(80_000.0, "up"), (75_000.0, "down")], {75_000.0: 0.925}, lambda url: body, None,
               tmp_path / "raw", tmp_path / "m.json", dry_run=False, show_level=False, now=lambda: BARRIER_NOW,
               calibration=cal, candidates=cands)
    out = capsys.readouterr().out
    assert rc == 0
    got = L.read_candidates(cands)
    assert len(got) == 1 and got[0]["key"] == "75000:down" and got[0]["market_mid"] == 0.925, got
    assert f"candidate {got[0]['id']} written" in out and "--candidate " + got[0]["id"] in out
    # the figures are the report's own, at the report's decimals
    line = next(ln for ln in out.splitlines() if "barrier 75,000 down" in ln)
    assert f"primary {got[0]['method_p']}, sensitivity {got[0]['range_hi']}" in line or \
        f"primary {got[0]['method_p']}, sensitivity {got[0]['range_lo']}" in line
    assert f"touch rate {got[0]['climatology_p']}" in line
    entry = json.loads((tmp_path / "m.json").read_text())[0]
    assert got[0]["inputs"]["series_sha256"] == entry["sha256"] and got[0]["inputs"]["series_fetched_utc"] == entry["fetched_utc"]
    assert got[0]["window_from_utc"] == ""
    text = cands.read_text(encoding="utf-8")
    for _d, v in obs[-5:]:  # no value of the series is written
        assert f"{v:.2f}" not in text
    # a dry run and a kept file write none, and say so
    rc = B.run("2026-11", [(75_000.0, "down")], {75_000.0: 0.925}, lambda url: body, None, tmp_path / "raw",
               tmp_path / "m.json", dry_run=True, show_level=False, now=lambda: BARRIER_NOW, candidates=cands)
    assert rc == 0 and "no candidate written (dry run)" in capsys.readouterr().out
    (tmp_path / "kept.csv").write_bytes(body)
    rc = B.run("2026-11", [(75_000.0, "down")], {75_000.0: 0.925}, None, tmp_path / "kept.csv", tmp_path / "raw",
               tmp_path / "m.json", dry_run=False, show_level=False, now=lambda: BARRIER_NOW, candidates=cands)
    assert rc == 0 and "no candidate written (series read from a file)" in capsys.readouterr().out
    assert len(L.read_candidates(cands)) == 1


def test_barrier_candidate_carries_the_legs_window(tmp_path):
    obs = series(120)
    body = csv_text(obs).encode()
    cands = tmp_path / "data" / "candidates.jsonl"
    opens = datetime(2026, 11, 5, 17, 17, tzinfo=UTC)
    rc = B.run("2026-11", [(75_000.0, "down")], {75_000.0: 0.5}, lambda url: body, None, tmp_path / "raw",
               tmp_path / "m.json", dry_run=False, show_level=False, now=lambda: BARRIER_NOW,
               window_from={75_000.0: opens}, candidates=cands)
    assert rc == 0
    got = L.read_candidates(cands)
    assert got[0]["window_from_utc"] == "2026-11-05T17:17:00Z" and got[0]["climatology_p"] is None


def test_fomc_live_writes_a_candidate_per_class_with_the_hull_range_and_the_classes_share(tmp_path):
    meetings, raw_dir, _ = synthetic_history(tmp_path)
    out = tmp_path / "cal.json"
    assert F.run(raw_dir, tmp_path / "manifest.json", out, fetch=False) == 0
    cal = F.load_calibration(out)
    s = F.load_dir(raw_dir)
    mids = {"hike": 0.635, "none": 0.325}
    got = F.live_candidates(s, meetings, date(2026, 12, 9), date(2026, 11, 4), cal, mids, raw_dir, NOW)
    lines = F.live_lines(s, meetings, date(2026, 12, 9), date(2026, 11, 4), cal, mids)
    assert [c["key"] for c in got] == ["hike", "none"]
    for c in got:
        line = next(ln for ln in lines if ln.startswith(f"  p_{c['key']}:"))
        p = float(c["method_p"])
        assert f"{cal['rules']['R1_primary']} {p:.3f}" in line
        lo, hi = float(c["range_lo"]), float(c["range_hi"])
        a, b = (float(x) for x in line.split("range under the basis [")[1].split("]")[0].split(", "))
        assert (f"{lo:.3f}", f"{hi:.3f}") == (f"{min(a, p):.3f}", f"{max(b, p):.3f}"), "the hull of the reading and its range"
        share = cal["sample"]["outcomes"].get(c["key"], 0) / cal["sample"]["scored_meetings"]
        assert c["climatology_p"] == f"{share:.3f}" and c["market_mid"] == mids[c["key"]]
        assert set(c["inputs"]["input_sha256"]) == set(F.SERIES) and c["inputs"]["as_of"] == "2026-11-04"
    # the reading that stops early writes nothing
    assert F.live_candidates(s, meetings, date(2026, 12, 9), date(2026, 12, 10), cal, mids, raw_dir, NOW) == []


# --- the row names it and is held to it ------------------------------------------------------

def gate(row_kw: dict, quote: dict = QUOTE, cands: tuple = (), recorded: str = "2026-11-06T18:30:00Z") -> set[str]:
    row = dict(id="R-2026-11-06-btc_touch-6507380", made_on="2026-11-06", recorded_utc=recorded, venue="polymarket",
               market_id="6507380", condition_id=quote["condition_id"], yes_token_id=quote["yes_token_id"], proposition="p",
               method="btc_touch", method_p="0.876", range_lo="0.876", range_hi="0.886", market_mid="0.925",
               climatology_p="0.690", due_on="2026-12-01", gate="calibrated;method-departure;touch-below",
               quote_fetched_utc=quote["fetched_utc"], quote_sha256=quote["gamma_sha256"], source="s", window_from_utc="",
               candidate_id="")
    row.update(row_kw)
    v = L.reading_row_violations(row, quote, (dict(method="btc_touch", in_force_utc="2026-11-05T12:23:00Z",
                                                   sha256="f2" * 32, r2="false", source="s"),), (), None, candidates=cands)
    return L.reading_tags(" ".join(v)), v


def test_the_gate_holds_the_row_to_its_candidate():
    c = candidate()
    assert gate({}, cands=(c,))[0] == set(), "a row before the held-from date with no candidate passes"
    assert gate({"candidate_id": c["id"]}, cands=(c,))[0] == set(), "the row copied from its candidate passes"
    tags, v = gate({"candidate_id": c["id"]}, cands=())
    assert tags == {"figures-from-tool"} and "not on" in v[0]
    tags, v = gate({"candidate_id": c["id"]}, cands=(c, c))
    assert tags == {"figures-from-tool"} and "more than once" in v[0]
    for col, bad in (("method_p", "0.123"), ("range_lo", "0.100"), ("range_hi", "0.900"), ("climatology_p", "0.5")):
        tags, v = gate({"candidate_id": c["id"], col: bad}, cands=(c,))
        assert "figures-from-tool" in tags and any(f"{col} {bad!r} is not the candidate's" in x for x in v), (col, v)
    # the candidate was read against another mid, or on another window, or outside [quote, row]
    other = candidate(market_mid=0.9)
    assert "the quote's is 0.925" in gate({"candidate_id": other["id"]}, cands=(other,))[1][0]
    windowed = candidate(window_from_utc="2026-11-05T17:17:00Z")
    assert "window_from_utc" in gate({"candidate_id": windowed["id"]}, cands=(windowed,))[1][0]
    early = candidate(computed_at=datetime(2026, 11, 6, 6, 0, tzinfo=UTC))
    assert "before the quote's fetch" in gate({"candidate_id": early["id"]}, cands=(early,))[1][0]
    late = candidate(computed_at=datetime(2026, 11, 6, 19, 0, tzinfo=UTC))
    assert "after the row was recorded" in gate({"candidate_id": late["id"]}, cands=(late,))[1][0]
    wrong_method = dict(c, method="fomc_bills")
    assert "is a fomc_bills reading" in gate({"candidate_id": c["id"]}, cands=(wrong_method,))[1][0]
    unparsed = dict(c, computed_utc="2026-11-06 06:20:00")
    assert "computed_utc" in gate({"candidate_id": c["id"]}, cands=(unparsed,))[1][0]


def test_a_reading_on_a_quote_fetched_from_the_held_from_date_needs_a_candidate():
    late_c = candidate(computed_at=datetime(2026, 11, 20, 6, 20, tzinfo=UTC))
    row = dict(id="R-2026-11-20-btc_touch-6507380", made_on="2026-11-20", quote_fetched_utc=LATE_QUOTE["fetched_utc"],
               quote_sha256=LATE_QUOTE["gamma_sha256"])
    tags, v = gate(row, quote=LATE_QUOTE, cands=(late_c,), recorded="2026-11-20T06:30:00Z")
    assert tags == {"figures-from-tool"} and "no candidate_id" in v[0]
    assert gate(dict(row, candidate_id=late_c["id"]), quote=LATE_QUOTE, cands=(late_c,), recorded="2026-11-20T06:30:00Z")[0] == set()


def test_add_copies_the_figures_from_the_candidate_and_names_it_on_the_row(tmp_path, capsys):
    manifest = write_manifest(tmp_path, [QUOTE, LATE_QUOTE])
    cands = tmp_path / "data" / "candidates.jsonl"
    c = candidate(computed_at=datetime(2026, 11, 20, 6, 20, tzinfo=UTC))
    L.append_candidate(cands, c)
    readings = tmp_path / "readings.csv"
    args = ns(quote=LATE_QUOTE["fetched_utc"], method_p=None, range_lo=None, range_hi=None, climatology_p=None, candidate=c["id"])
    assert R.add(args, manifest, readings, LATE_NOW, candidates=cands) == 0
    out = capsys.readouterr().out
    assert "ADMITTED R-2026-11-20-btc_touch-6507380: method_p=0.876 range=[0.876, 0.886]" in out
    with readings.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert tuple(rows[0]) == L.READING_COLUMNS and rows[0]["candidate_id"] == c["id"]
    assert (rows[0]["method_p"], rows[0]["range_lo"], rows[0]["range_hi"], rows[0]["climatology_p"]) == ("0.876", "0.876", "0.886", "0.690")
    assert L.reading_file_violations(rows, [QUOTE, LATE_QUOTE], history(tmp_path), L.read_candidates(cands)) == []
    # a figure typed beside the candidate is held to it, not preferred
    args = ns(market_id="6507380", quote=LATE_QUOTE["fetched_utc"], method_p=0.123, range_lo=None, range_hi=None,
              climatology_p=None, candidate=c["id"], proposition="p2")
    assert R.add(args, manifest, tmp_path / "r2.csv", LATE_NOW, candidates=cands) == 1
    out = capsys.readouterr().out
    assert "[reading:figures-from-tool]" in out and "method_p '0.123' is not the candidate's '0.876'" in out
    # no candidate on a late quote: refused by the gate; a typed set of figures on a late quote: refused by the gate
    args = ns(quote=LATE_QUOTE["fetched_utc"], method_p=0.876, range_lo=0.876, range_hi=0.886, climatology_p=0.690)
    assert R.add(args, manifest, tmp_path / "r3.csv", LATE_NOW, candidates=cands) == 1
    assert "no candidate_id" in capsys.readouterr().out
    # neither a candidate nor the figures: refused before the gate
    args = ns(quote=LATE_QUOTE["fetched_utc"], method_p=None, range_lo=None, range_hi=None, climatology_p=None)
    assert R.add(args, manifest, tmp_path / "r4.csv", LATE_NOW, candidates=cands) == 1
    assert "give --candidate" in capsys.readouterr().out
    # an id no printer wrote
    args = ns(quote=LATE_QUOTE["fetched_utc"], method_p=None, range_lo=None, range_hi=None, climatology_p=None, candidate="K-x")
    assert R.add(args, manifest, tmp_path / "r5.csv", LATE_NOW, candidates=cands) == 1
    assert "candidate K-x is not on" in capsys.readouterr().out
    assert not (tmp_path / "r2.csv").exists() and not (tmp_path / "r5.csv").exists()


def test_the_committed_candidates_file_if_any_holds_well_formed_records_written_after_their_quotes():
    here = Path(__file__).resolve().parent.parent
    for c in L.read_candidates(here / L.CANDIDATES):
        assert c["method"] in L.READING_METHODS and c["id"] == L.candidate_id(c["method"], c["key"], L.parse_utc_stamp(c["computed_utc"]))
        assert 0.0 <= float(c["range_lo"]) <= float(c["method_p"]) <= float(c["range_hi"]) <= 1.0
        assert isinstance(c["inputs"], dict) and c["inputs"]
