"""A UTC stamp is parsed before it is ordered or sliced, never compared as text.

The defect class (predictions/POST_MORTEMS.md, 2026-11-09 06:15Z and 12:15Z):
pm-view writes every UTC stamp (``fetched_utc``, ``recorded_utc``,
``in_force_utc``, an admission time) in one format, ``pm_lib.UTC_STAMP_FORMAT``,
and for a while compared them as text: ``in_force_utc <= at_utc``,
``recorded < fetched``, ``str(fetched_utc)[:10]`` for the day.  Text order is
time order only while both sides carry that one format, which nothing held on
the paths that read the manifest's stamp.  Shown on 56572b1: a quote stamped
``2026-11-06 06:20:45 UTC`` (a space for the T) put a calibration line that
went into force at 05:00Z the same day *after* the quote, so the ledger gate
judged a call under the superseded line and lost its ``calibrated`` refusal;
the same stamp let a reading recorded before its quote pass
``recorded-after-quote``.

This check reads the pm-view modules and tools/check_due.py.  In each
function it marks as a *stamp* every parameter whose name ends in ``_utc``,
every expression that reads a ``..._utc`` key or name, and every variable
assigned from such an expression unless the assignment parses it with
``parse_utc_stamp``; ``str(x)``, ``x or ""`` and a subscript of a stamp are
stamps too.  It fails on any ordering comparison (``<``, ``<=``, ``>``,
``>=``), any slice, and any ``min``/``max``/``sorted`` with a stamp operand.
Equality (``==``, ``!=``) is allowed: a column copied from the quote is held
equal to its source as text on purpose.

Usage: python tools/check_stamp_compares.py [--root PATH] [--selftest]
Exit 1 on any text comparison.  ``--selftest`` writes a failing and a passing
module to a temporary folder and checks both verdicts.
"""
from __future__ import annotations

import argparse
import ast
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSERS = {"parse_utc_stamp", "strptime", "quote_day"}  # quote_day parses since 2026-11-09 12:15Z
PROPAGATE = {"str", "get", "strip", "lower", "upper", "join", "format", "replace"}  # text in, the same text out
ORDER_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
ORDER_CALLS = {"min", "max", "sorted"}


def _modules(root: Path) -> list[Path]:
    out = sorted(p for p in (root / "pm-view").glob("*.py") if p.name != "conftest.py")
    due = root / "tools" / "check_due.py"
    if due.exists():
        out.append(due)
    return out


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name):
            return f.id
        if isinstance(f, ast.Attribute):
            return f.attr
    return None


def _reads_stamp(node: ast.AST, tainted: set[str]) -> bool:
    """True when the expression's value is a stamp's text: a `_utc` name or key, or a tainted
    variable, reached through text-preserving steps only (`str()`, `.get()`, `or ""`, a subscript,
    a `.strip()`).  A call to a parser is not a stamp, and neither is the result of any other
    function (`spot_time_utc(d)` is a datetime, `earliest_scoring_day(...)` a date): a function
    that returns a stamp's text unparsed is checked where it is written, not where it is called."""
    if isinstance(node, ast.Name):
        return node.id.endswith("_utc") or node.id in tainted
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) and node.value.endswith("_utc")
    if isinstance(node, ast.Call):
        name = _call_name(node)
        if name in PARSERS or name not in PROPAGATE:
            return False
        inner = [node.func.value] if isinstance(node.func, ast.Attribute) else []
        return any(_reads_stamp(a, tainted) for a in [*inner, *node.args, *[k.value for k in node.keywords]])
    if isinstance(node, ast.Subscript):
        return _reads_stamp(node.value, tainted) or _reads_stamp(node.slice, tainted)
    if isinstance(node, ast.Attribute):
        return _reads_stamp(node.value, tainted)
    if isinstance(node, ast.IfExp):  # the value is one branch or the other; the test is not the value
        return _reads_stamp(node.body, tainted) or _reads_stamp(node.orelse, tainted)
    if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
        return _reads_stamp(node.elt, tainted)
    if isinstance(node, (ast.BoolOp, ast.BinOp, ast.Tuple, ast.List, ast.Set, ast.JoinedStr,
                         ast.FormattedValue, ast.Starred, ast.NamedExpr)):
        return any(_reads_stamp(c, tainted) for c in ast.iter_child_nodes(node) if isinstance(c, ast.expr))
    return False


class _Scope(ast.NodeVisitor):
    def __init__(self, path: Path, rel: str) -> None:
        self.path, self.rel = path, rel
        self.hits: list[str] = []
        self.tainted: set[str] = set()

    def _hit(self, node: ast.AST, what: str) -> None:
        self.hits.append(f"{self.rel}:{node.lineno}: {what}")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        saved = self.tainted
        self.tainted = {a.arg for a in node.args.args + node.args.kwonlyargs if a.arg.endswith("_utc")}
        for stmt in node.body:
            self.visit(stmt)
        self.tainted = saved

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        self.generic_visit(node)
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not names:
            return
        if _reads_stamp(node.value, self.tainted):
            self.tainted |= set(names)
        else:
            self.tainted -= set(names)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        self.generic_visit(node)
        if isinstance(node.target, ast.Name) and node.value is not None:
            if _reads_stamp(node.value, self.tainted):
                self.tainted.add(node.target.id)
            else:
                self.tainted.discard(node.target.id)

    def visit_Compare(self, node: ast.Compare) -> None:  # noqa: N802
        self.generic_visit(node)
        if any(isinstance(op, ORDER_OPS) for op in node.ops):
            for operand in [node.left, *node.comparators]:
                if _reads_stamp(operand, self.tainted):
                    self._hit(node, f"a UTC stamp ordered as text: {ast.unparse(node)}")
                    break

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        self.generic_visit(node)
        if isinstance(node.slice, ast.Slice) and _reads_stamp(node.value, self.tainted):
            self._hit(node, f"a UTC stamp sliced as text: {ast.unparse(node)}")

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        self.generic_visit(node)
        if _call_name(node) in ORDER_CALLS and isinstance(node.func, ast.Name):
            for arg in node.args:
                if _reads_stamp(arg, self.tainted):
                    self._hit(node, f"UTC stamps ordered as text: {ast.unparse(node)}")
                    break


def check_file(path: Path, root: Path) -> list[str]:
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = str(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    scope = _Scope(path, rel)
    scope.visit(tree)
    return scope.hits


def check_tree(root: Path) -> tuple[list[str], int]:
    hits: list[str] = []
    files = _modules(root)
    for p in files:
        hits.extend(check_file(p, root))
    return hits, len(files)


FAILING = '''
def in_force(history, at_utc):
    hit = None
    for h in history:
        if str(h.get("in_force_utc", "")) <= at_utc:
            hit = h
    return hit

def day(fetched_utc):
    return str(fetched_utc or "")[:10]

def after(row, quote):
    recorded = str(row.get("recorded_utc", ""))
    fetched = str(quote.get("fetched_utc", ""))
    return recorded < fetched

def latest(entries):
    return max(e["fetched_utc"] for e in entries)
'''

PASSING = '''
from datetime import datetime, UTC
FORMAT = "%Y-%m-%dT%H:%M:%SZ"

def parse_utc_stamp(stamp, what="stamp"):
    return datetime.strptime(str(stamp or ""), FORMAT).replace(tzinfo=UTC)

def in_force(history, at_utc):
    at = parse_utc_stamp(at_utc)
    hit = None
    for h in history:
        if parse_utc_stamp(h.get("in_force_utc")) <= at:
            hit = h
    return hit

def day(fetched_utc):
    return parse_utc_stamp(fetched_utc).date().isoformat()

def after(row, quote):
    recorded = parse_utc_stamp(row.get("recorded_utc"))
    fetched = parse_utc_stamp(quote.get("fetched_utc"))
    return recorded < fetched

def copied(row, quote):
    return str(row.get("quote_fetched_utc", "")) == str(quote.get("fetched_utc", ""))

def unrelated(a, b):
    return a[:10] < b

def spot_time_utc(d):
    return datetime(d.year, d.month, d.day, tzinfo=UTC)

def inside(d, start_utc, end):
    t = spot_time_utc(d)          # a datetime from a function, not a stamp's text
    at = parse_utc_stamp(start_utc)
    return at <= t < end

def through_a_function(row):
    day = earliest_day(row["recorded_utc"])   # a function's result is judged where it is written
    return day <= "2026-12-01"

def earliest_day(recorded_utc):
    return parse_utc_stamp(recorded_utc).date().isoformat()
'''


def selftest() -> int:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "pm-view").mkdir()
        (root / "pm-view" / "bad.py").write_text(FAILING, encoding="utf-8")
        bad = check_file(root / "pm-view" / "bad.py", root)
        (root / "pm-view" / "bad.py").write_text(PASSING, encoding="utf-8")
        good = check_file(root / "pm-view" / "bad.py", root)
    want = ("in_force_utc", "fetched_utc or", "recorded < fetched", "max(")
    ok = len(bad) == 4 and all(any(w in h for h in bad) for w in want) and good == []
    print(f"selftest: failing module {len(bad)} hit(s) (want 4), passing module {len(good)} (want 0): "
          f"{'pass' if ok else 'FAIL'}")
    if not ok:
        for h in bad + good:
            print("  " + h)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    hits, n = check_tree(a.root)
    for h in hits:
        print(h)
    print(f"stamp comparisons: {len(hits)} text comparison(s) of a UTC stamp over {n} module(s)"
          f"{'' if hits else ' (pass)'}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
