"""Study 010 loader on synthetic zips only."""
import hashlib
import io
import json
import zipfile

import pytest
from src.data import load_factors, monthly_section

TEXT = """This file was created using the 209901 CRSP database.

,Mkt-RF,SMB,HML,RF
192607,    2.96,   -2.56,   -2.43,    0.22
192608,    2.64,   -1.17,    3.82,    0.25

  Annual Factors: January-December
,Mkt-RF,SMB,HML,RF
  1927,   29.47,   -2.04,   -4.54,    3.12
"""


def _zip(text: str, name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, text)
    return buf.getvalue()


def test_monthly_section_only():
    f = monthly_section(TEXT)
    assert list(f.columns) == ["Mkt-RF", "SMB", "HML", "RF"]
    assert [str(p) for p in f.index] == ["1926-07", "1926-08"]
    assert f.loc[f.index[0], "SMB"] == -2.56


@pytest.mark.parametrize("bad", ["-99.99", "-999", ""])
def test_marker_raises(bad):
    with pytest.raises(ValueError):
        monthly_section(TEXT.replace("   -1.17", f"   {bad}"))


def test_hash_checked_and_frames_joined(tmp_path):
    texts = {
        "F-F_Research_Data_Factors_CSV.zip": TEXT,
        "F-F_ST_Reversal_Factor_CSV.zip": "x\n\n,ST_Rev\n192607, 1.00\n192608, 2.00\n",
        "F-F_LT_Reversal_Factor_CSV.zip": "x\n\n,LT_Rev\n192608, 3.00\n",
    }
    man = {"files": {}}
    for n, t in texts.items():
        b = _zip(t, n.replace("_CSV.zip", ".csv"))
        (tmp_path / n).write_bytes(b)
        man["files"][n] = {"sha256": hashlib.sha256(b).hexdigest()}
    mp = tmp_path / "m.json"
    mp.write_text(json.dumps(man))
    f = load_factors(tmp_path, mp)
    assert list(f.columns) == ["SMB", "HML", "ST_Rev", "LT_Rev"] and len(f) == 2
    assert f["LT_Rev"].isna().iloc[0] and f.loc[f.index[1], "LT_Rev"] == 3.0
    man["files"]["F-F_LT_Reversal_Factor_CSV.zip"]["sha256"] = "0" * 64
    mp.write_text(json.dumps(man))
    with pytest.raises(SystemExit):
        load_factors(tmp_path, mp)
