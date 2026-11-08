"""The admission tool for a call, `ledger.py add` (2026-11-07 18:15Z,
predictions/POST_MORTEMS.md "A gate that only a test applied"): driven through
its command line against a manifest, a calibration history and a ledger built
in a tmp folder.  Each refusal is checked by its tag on stderr, with the ledger's
bytes unchanged; the admitted row is held to the committed-file test's gate,
pm_lib.ledger_file_violations.  Nothing touches the network or the real files."""
import csv
import hashlib
import io
import json
from pathlib import Path

import ledger as G
import pm_lib as L
import pytest
from score import read_csv

# the committed calibration files of the tmp folder (2026-11-08 06:15Z: ledger.py add holds the
# committed file to its method's latest line, so the fixture's lines carry the files' own hashes)
CAL = {"btc_touch": json.dumps({"rules": {"R2_method_is_a_basis_for_a_call": False}}).encode(),
       "fomc_bills": json.dumps({"rules": {"R2_basis_for_a_call": True}}).encode()}
CAL_FALSE = json.dumps({"rules": {"R2_basis_for_a_call": False}}).encode()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


HISTORY = (
    "method,in_force_utc,sha256,r2,source\n"
    f"btc_touch,2026-11-05T12:23:00Z,{sha(CAL['btc_touch'])},false,test\n"
    f"fomc_bills,2026-11-05T18:29:17Z,{sha(CAL['fomc_bills'])},true,test\n"
)
QUOTE = {"fetched_utc": "2026-11-06T06:16:37Z", "market_id": "3215008", "condition_id": "0x8a41",
         "yes_token_id": "1116", "gamma_sha256": "ab" * 32, "book_sha256": "cd" * 32, "description_sha256": "de" * 32,
         "market_mid": 0.45, "market_spread": 0.01, "volume_usdc": 250000.0, "end_date": "2026-12-09T23:59:00Z",
         "eligibility": "eligible", "question": "Will the Fed increase interest rates by 25 bps?"}
OLD = dict(QUOTE, fetched_utc="2026-11-03T18:23:14Z", book_sha256="c0" * 32, description_sha256=None)
SETTLED = dict(QUOTE, fetched_utc="2026-11-06T06:20:45Z", market_id="6507378", book_sha256=None, market_mid=None,
               eligibility="not open and accepting orders")
TOUCH = dict(QUOTE, fetched_utc="2026-11-06T06:16:38Z", market_id="6507380", book_sha256="e1" * 32, market_mid=0.60)
SETTLES = "the upper bound of the target range after the 9 December 2026 meeting is 25 bp higher"
BASIS = "the market prices 0.45; the bills price 0.99 after the November prints"


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "manifest.json").write_text(json.dumps([QUOTE, OLD, SETTLED, TOUCH]))
    (tmp_path / L.CALIBRATION_HISTORY).write_text(HISTORY)
    for method, body in CAL.items():
        (tmp_path / L.METHOD_CALIBRATION[method][0]).write_bytes(body)
    (tmp_path / "ledger.csv").write_text(",".join(L.LEDGER_COLUMNS) + "\n")
    return tmp_path


def run(folder: Path, **kw) -> int:
    a = dict(market_id="3215008", quote=QUOTE["fetched_utc"], desk_p="0.90", method="fomc_bills", method_p="0.99",
             range_lo="0.60", range_hi="1.00", proposition="Hike of 25 bp on 9 December", settles_on=SETTLES,
             basis=BASIS)
    a.update(kw)
    dry = a.pop("dry_run", False)
    argv = ["add", "--manifest", str(folder / "data" / "manifest.json"), "--ledger", str(folder / "ledger.csv")]
    for k, v in a.items():
        if v is not None:
            argv += [f"--{k.replace('_', '-')}", v]
    return G.main(argv + (["--dry-run"] if dry else []))


def rows(folder: Path) -> list[dict]:
    return read_csv(folder / "ledger.csv")


def file_gate(folder: Path) -> list[str]:
    manifest = json.loads((folder / "data" / "manifest.json").read_text())
    return L.ledger_file_violations(rows(folder), manifest, read_csv(folder / L.CALIBRATION_HISTORY))


def test_an_admitted_call_is_one_row_built_from_the_quote_that_passes_the_committed_file_gate(folder, capsys):
    assert run(folder) == 0
    assert "ADMITTED C-2026-11-06-fomc_bills-3215008" in capsys.readouterr().out
    [r] = rows(folder)
    assert r["made_on"] == "2026-11-06" and r["due_on"] == "2026-12-09" and r["venue"] == "polymarket"
    assert (r["market_mid"], r["market_spread"], r["volume_usdc"]) == ("0.45", "0.01", "250000.0")
    assert (r["condition_id"], r["yes_token_id"], r["quote_sha256"]) == ("0x8a41", "1116", "cd" * 32)
    assert (r["desk_p"], r["method_p"], r["range_lo"], r["range_hi"]) == ("0.90", "0.990", "0.600", "1.000")
    assert file_gate(folder) == []


def test_a_stated_call_carries_no_method_fields_and_passes(folder):
    assert run(folder, method="stated", method_p=None, range_lo=None, range_hi=None) == 0
    [r] = rows(folder)
    assert r["id"] == "C-2026-11-06-stated-3215008" and (r["method_p"], r["range_lo"], r["range_hi"]) == ("", "", "")
    assert file_gate(folder) == []


def test_dry_run_flag_admits_and_writes_nothing(folder, capsys):
    before = (folder / "ledger.csv").read_bytes()
    assert run(folder, dry_run=True) == 0
    assert "DRY RUN ADMITTED" in capsys.readouterr().out
    assert (folder / "ledger.csv").read_bytes() == before


@pytest.mark.parametrize(("kw", "tag"), [
    (dict(desk_p="0.9"), "probability"),
    (dict(desk_p="1.00"), "probability"),
    (dict(desk_p="0.50", method="stated", method_p=None, range_lo=None, range_hi=None), "departure"),
    (dict(basis="no mention of the venue's number"), "basis-names-market"),
    (dict(settles_on="Fed hikes"), "settles-on"),
    (dict(method="stated"), "stated-bare"),
    (dict(range_lo="0.40"), "range"),
    (dict(desk_p="0.30"), "desk-side"),
    (dict(market_id="6507380", quote=TOUCH["fetched_utc"], method="btc_touch", method_p="0.80", range_lo="0.75",
          range_hi="0.85", desk_p="0.80"), "calibrated"),
    (dict(quote="2026-11-06T09:00:00Z"), "written-quote"),            # a --dry-run quote leaves no entry
    (dict(market_id="6507378", quote=SETTLED["fetched_utc"]), "written-quote"),
    (dict(market_id="6507378", quote=SETTLED["fetched_utc"]), "eligible-at-quote"),
    (dict(quote=OLD["fetched_utc"]), "rules-on-record"),
])
def test_each_refusal_carries_its_tag_on_stderr_and_writes_nothing(folder, capsys, kw, tag):
    before = (folder / "ledger.csv").read_bytes()
    assert run(folder, **kw) == 1
    err = capsys.readouterr().err
    assert err.startswith("REFUSED ") and f"[gate:{tag}]" in err, err
    assert (folder / "ledger.csv").read_bytes() == before


def test_a_second_call_on_the_same_market_and_day_is_refused_whatever_its_method(folder, capsys):
    assert run(folder) == 0
    before = (folder / "ledger.csv").read_bytes()
    capsys.readouterr()
    for kw in (dict(), dict(method="stated", method_p=None, range_lo=None, range_hi=None)):
        assert run(folder, **kw) == 1
        assert "[gate:one-per-day]" in capsys.readouterr().err
    assert (folder / "ledger.csv").read_bytes() == before


def test_the_row_gate_refuses_a_retyped_mid_and_foreign_ids():
    row = G.build_row(QUOTE, "3215008", "0.90", "fomc_bills", 0.99, 0.60, 1.00, "x", SETTLES, BASIS)
    hist = read_csv_text(HISTORY)
    assert L.ledger_row_violations(row, QUOTE, hist) == []
    assert L.gate_tags(" ".join(L.ledger_row_violations(dict(row, market_mid="0.46"), QUOTE, hist))) == {
        "mid-from-quote"}
    assert L.gate_tags(" ".join(L.ledger_row_violations(dict(row, yes_token_id="999"), QUOTE, hist))) == {
        "written-quote"}
    # the timing rule still holds a hand-typed row that names another day
    assert "made-on-quote-day" in L.gate_tags(" ".join(L.ledger_row_violations(dict(row, made_on="2026-11-07"),
                                                                               QUOTE, hist)))


def test_r2_is_the_line_in_force_at_the_quote_not_the_latest():
    # a later line flipping the bills' R2 to false does not refuse a call on a quote fetched before it
    hist = read_csv_text(HISTORY + f"fomc_bills,2026-11-06T12:00:00Z,{'99' * 32},false,test\n")
    row = G.build_row(QUOTE, "3215008", "0.90", "fomc_bills", 0.99, 0.60, 1.00, "x", SETTLES, BASIS)
    assert L.ledger_row_violations(row, QUOTE, hist) == []
    later = dict(QUOTE, fetched_utc="2026-11-06T13:00:00Z")
    row_later = G.build_row(later, "3215008", "0.90", "fomc_bills", 0.99, 0.60, 1.00, "x", SETTLES, BASIS)
    assert L.gate_tags(" ".join(L.ledger_row_violations(row_later, later, hist))) == {"calibrated"}


# 2026-11-08 06:15Z, predictions/POST_MORTEMS.md "A call admitted under a calibration already superseded":
# before this date both calls below were admitted (rc 0, observed on a scratch worktree of 19a20ce)

def test_a_call_is_refused_when_a_calibration_went_into_force_after_its_quote(folder, capsys):
    # the bills re-run at 07:00Z the same day flips R2 to false and is on record; the 06:16Z quote's line said true
    (folder / L.METHOD_CALIBRATION["fomc_bills"][0]).write_bytes(CAL_FALSE)
    with (folder / L.CALIBRATION_HISTORY).open("a") as f:
        f.write(f"fomc_bills,2026-11-06T07:00:00Z,{sha(CAL_FALSE)},false,re-run\n")
    before = (folder / "ledger.csv").read_bytes()
    assert run(folder) == 1
    err = capsys.readouterr().err
    assert L.gate_tags(err) == {"calibration-since-quote"}, err
    assert "2026-11-06T07:00:00Z" in err and (folder / "ledger.csv").read_bytes() == before
    # the committed-file judgement, with no admission time, is unchanged: the line at the quote
    row = G.build_row(QUOTE, "3215008", "0.90", "fomc_bills", 0.99, 0.60, 1.00, "x", SETTLES, BASIS)
    assert L.ledger_row_violations(row, QUOTE, read_csv(folder / L.CALIBRATION_HISTORY)) == []


def test_a_call_is_refused_while_the_committed_calibration_is_not_on_record(folder, capsys):
    # the committed file was rewritten by a route that did not record it: the printer reads R2 false from it
    (folder / L.METHOD_CALIBRATION["fomc_bills"][0]).write_bytes(CAL_FALSE)
    before = (folder / "ledger.csv").read_bytes()
    assert run(folder) == 1
    err = capsys.readouterr().err
    assert L.gate_tags(err) == {"calibration-on-record"}, err
    assert (folder / "ledger.csv").read_bytes() == before
    (folder / L.METHOD_CALIBRATION["fomc_bills"][0]).unlink()
    assert run(folder) == 1
    assert "[gate:calibration-on-record]" in capsys.readouterr().err


def test_a_stated_call_needs_no_calibration_file(folder):
    for method in CAL:
        (folder / L.METHOD_CALIBRATION[method][0]).unlink()
    assert run(folder, method="stated", method_p=None, range_lo=None, range_hi=None) == 0


def read_csv_text(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))
