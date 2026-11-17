"""§6.4 and §6.5: no module in src/ names a resolution file, an outcome or last-trade field, the resolution-time field,
the sample row's token field or the CLOB token list; and no module opens a resolution file, asserted on the open
calls themselves with the files present (code review 2026-11-17, must-fix 7). The names are spelt here, in the tests,
and nowhere in src/."""

import builtins
import io
from pathlib import Path

import pytest

from tests import test_run as e2e

SRC = Path(__file__).resolve().parents[1] / "src"
FORBIDDEN = ("outcome.jsonl", "status.jsonl", "outcomePrices", "umaResolutionStatus", "lastTradePrice",
             "closedTime", "first_token", "clobTokenIds")
RESOLUTION_FILES = ("status.jsonl", "outcome.jsonl")


def test_no_module_in_src_names_a_forbidden_field_or_file():
    modules = sorted(SRC.glob("*.py"))
    assert len(modules) >= 3
    for m in modules:
        text = m.read_text(encoding="utf-8")
        for word in FORBIDDEN:
            assert word not in text, f"{m.name} names {word!r}"


def test_no_module_in_src_opens_a_resolution_folder():
    for m in SRC.glob("*.py"):
        text = m.read_text(encoding="utf-8")
        assert '"resolution"' not in text and "'resolution'" not in text, f"{m.name} names the resolution folder"


class ResolutionFileOpened(AssertionError):
    pass


def _guard(real):
    def opened(file, *args, **kwargs):
        name = Path(str(file)).name if not isinstance(file, int) else ""
        if name in RESOLUTION_FILES:
            raise ResolutionFileOpened(f"src opened {name}")
        return real(file, *args, **kwargs)
    return opened


def test_the_run_never_opens_a_resolution_file_when_they_are_present(tmp_path: Path, monkeypatch):
    """The end-to-end run with Study 013's resolution files present in every folder the run touches, behind a guard on
    `builtins.open`, `io.open` and `pathlib.Path.open` (`Path.read_text` goes through `Path.open`)."""
    ms = e2e._markets()
    s13 = e2e._build_013(tmp_path, ms)
    s14 = e2e._build_014(tmp_path)
    for folder in (s13 / "results", s13 / "data" / "raw" / "resolution", s13 / "paper-log", s13 / "data" / "raw" / "snapshots" / e2e.SNAP):
        folder.mkdir(parents=True, exist_ok=True)
        for name in RESOLUTION_FILES:
            (folder / name).write_text('{"id": "L0", "outcome": "Yes"}\n', encoding="utf-8")
    real_builtin, real_io, real_path = builtins.open, io.open, Path.open
    monkeypatch.setattr(builtins, "open", _guard(real_builtin))
    monkeypatch.setattr(io, "open", _guard(real_io))
    monkeypatch.setattr(Path, "open", lambda self, *a, **k: _guard(lambda f, *aa, **kk: real_path(self, *aa, **kk))(self, *a, **k))
    # the guard itself fires on a direct open of one of the files
    with pytest.raises(ResolutionFileOpened):
        open(s13 / "results" / "status.jsonl", encoding="utf-8")
    with pytest.raises(ResolutionFileOpened):
        (s13 / "results" / "outcome.jsonl").read_text(encoding="utf-8")
    s = e2e._run(tmp_path, s14, s13)
    assert not s["halted"] and s["fits"]["M1"]["W"]["fitted"]
