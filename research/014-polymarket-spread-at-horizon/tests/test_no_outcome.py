"""§6.4 and §6.5: no module in src/ names a resolution file, an outcome or last-trade field, the resolution-time field,
the sample row's token field or the CLOB token list. The names are spelt here, in the test, and nowhere in src/."""

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
FORBIDDEN = ("outcome.jsonl", "status.jsonl", "outcomePrices", "umaResolutionStatus", "lastTradePrice",
             "closedTime", "first_token", "clobTokenIds")


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
