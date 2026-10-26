"""Study 011 data step parser on synthetic text only (no library file)."""
from data_step import eligible_counts, parse_vw_monthly

HEAD = "This file was created using the 209901 CRSP database.\n\n"


def _file(rows: list[str], cols: str = ",A,B,C") -> str:
    return (
        HEAD
        + "  Average Value Weighted Returns -- Monthly\n"
        + cols + "\n"
        + "\n".join(rows)
        + "\n\n  Average Equal Weighted Returns -- Monthly\n" + cols + "\n192607,  -99.99,  -99.99,  -99.99\n"
    )


ROWS = ["192607,   1.00,   2.00,   3.00", "192608,  -99.99,   2.00,   3.00", "192609,   1.00,  -999,   3.00", "192610,   1.00,   2.00,   3.00"]


def test_vw_section_only_and_markers():
    p = parse_vw_monthly(_file(ROWS))
    assert p["column_header"] == ["A", "B", "C"]
    assert p["months"] == ["1926-07", "1926-08", "1926-09", "1926-10"]
    assert p["has_value"][1] == [False, True, True]
    assert p["has_value"][2] == [True, False, True]
    assert p["month_gaps"] == [] and p["duplicate_or_out_of_order"] == []
    assert "209901" in " ".join(p["preamble_lines"])


def test_no_number_is_returned():
    p = parse_vw_monthly(_file(ROWS))
    flat = repr({k: v for k, v in p.items()})
    assert "2.00" not in flat and "3.00" not in flat


def test_gap_duplicate_and_width():
    rows = [ROWS[0], ROWS[0], "192610,   1.00,   2.00", ROWS[3].replace("192610", "192612")]
    p = parse_vw_monthly(_file(rows))
    assert p["duplicate_or_out_of_order"] == ["1926-07->1926-07"]
    assert p["rows_with_wrong_field_count"] == ["1926-10"]
    assert p["month_gaps"] == ["1926-07..1926-10", "1926-10..1926-12"]


def test_missing_title_is_an_error():
    assert "error" in parse_vw_monthly(HEAD + ",A,B\n192607, 1.0, 2.0\n")


def test_eligibility_window():
    p = parse_vw_monthly(_file(ROWS))
    # values: 07 A,B,C; 08 B,C (A missing); 09 A,C (B missing); 10 A,B,C
    ec = eligible_counts(p, 2, "1926-08", "1926-10")
    assert ec == {"1926-08": 2, "1926-09": 1, "1926-10": 2}
    ec3 = eligible_counts(p, 3, "1926-08", "1926-10")
    assert ec3["1926-08"] == 0  # formation would need 1926-06, before the file
    assert ec3["1926-09"] == 1 and ec3["1926-10"] == 1
