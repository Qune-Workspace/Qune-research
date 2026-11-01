"""A patched path must never be reached through a default bound at import.

The defect class (research/POST_MORTEMS.md, 2026-11-01): a forward module
defines its paper-log paths as module constants and its helpers take them as
default arguments, ``def write_record(record, directory=DECISIONS_DIR)``.  A
default is evaluated once, when the module is imported.  A test that does
``monkeypatch.setattr(forward, "DECISIONS_DIR", tmp_path)`` and then calls the
entry point has changed the module attribute, not the default: every call
inside the module that omits the argument still reads or writes the real
folder.  The test then passes for the wrong reason (Study 006, 2026-10-31,
printed a wait line from the real ``paper-log/raw/`` where the test expected a
refusal; Study 004's twin test, reviewed the same day, had three such call
sites in ``main`` that its dry-run-only assertions never exercised).

This check reads every forward or paper module and its tests.  For each
constant that a test patches on the module, it finds the module's functions
whose default arguments are built from that constant and every call inside
the module that omits the argument.  Any such call is a failure: the entry
point passes the path by name (``write_record(record, DECISIONS_DIR)``, which
resolves the attribute at call time), or the helper takes no default.

Usage: python tools/check_bound_defaults.py [--root PATH] [--selftest]
Exit 1 on any reached default.  ``--selftest`` builds a passing and a failing
module with a test in a temporary folder and checks both verdicts.
"""
from __future__ import annotations

import argparse
import ast
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_GLOBS = ("forward*.py", "paper_trade.py")


def _is_const_name(name: str) -> bool:
    return name.isupper() and len(name) > 1


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _string_list(node: ast.AST | None) -> list[str] | None:
    """The strings of a literal list or tuple of upper-case names, else None."""
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts and all(
            isinstance(e, ast.Constant) and isinstance(e.value, str) and _is_const_name(e.value) for e in node.elts):
        return [e.value for e in node.elts]
    return None


def module_aliases(test_tree: ast.AST, module_name: str) -> set[str]:
    """Names under which the test imports the module (``from src import forward``, ``import src.forward as fw``)."""
    aliases: set[str] = set()
    for node in ast.walk(test_tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[-1] == module_name:
                    aliases.add(a.asname or a.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == module_name:
                    aliases.add(a.asname or a.name)
    return aliases


def patched_constants(test_file: Path, module_name: str) -> dict[str, list[str]]:
    """``{CONST: ["test_x.py:12", ...]}`` for every ``monkeypatch.setattr(<module>, "CONST", ...)``, written
    with a literal name, inside a loop over a literal list or tuple of names, or inside a loop over a
    module-level list or tuple of names."""
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
    except SyntaxError:
        return {}
    aliases = module_aliases(tree, module_name)
    if not aliases:
        return {}
    lists: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            vals = _string_list(node.value)
            if vals:
                lists[node.targets[0].id] = vals
    out: dict[str, list[str]] = {}

    def setattr_calls(scope: ast.AST):
        for inner in ast.walk(scope):
            if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) and inner.func.attr == "setattr"
                    and len(inner.args) >= 2 and isinstance(inner.args[0], ast.Name) and inner.args[0].id in aliases):
                yield inner

    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            vals = _string_list(node.iter)
            if vals is None and isinstance(node.iter, ast.Name):
                vals = lists.get(node.iter.id)
            if vals is None:
                continue
            for call in setattr_calls(node):
                if isinstance(call.args[1], ast.Name) and call.args[1].id == node.target.id:
                    for v in vals:
                        out.setdefault(v, []).append(f"{test_file.name}:{call.lineno}")
    for call in setattr_calls(tree):
        if isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str) and _is_const_name(call.args[1].value):
            out.setdefault(call.args[1].value, []).append(f"{test_file.name}:{call.lineno}")
    return out


def reached_defaults(src: Path, patched: dict[str, list[str]]) -> list[str]:
    """One line per call inside ``src`` that omits an argument whose default is built from a patched constant."""
    tree = ast.parse(src.read_text(encoding="utf-8"))
    funcs: dict[str, ast.FunctionDef] = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    bound: dict[str, dict[str, set[str]]] = {}
    for name, fn in funcs.items():
        pos = fn.args.posonlyargs + fn.args.args
        defaults = [None] * (len(pos) - len(fn.args.defaults)) + list(fn.args.defaults)
        pairs = list(zip(pos, defaults, strict=True)) + list(zip(fn.args.kwonlyargs, fn.args.kw_defaults, strict=True))
        for arg, default in pairs:
            if default is None:
                continue
            consts = {n for n in _names_in(default) if _is_const_name(n)} & set(patched)
            if consts:
                bound.setdefault(name, {})[arg.arg] = consts
    lines: list[str] = []
    for caller, fn in funcs.items():
        for call in ast.walk(fn):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in bound):
                continue
            if any(k.arg is None for k in call.keywords):
                continue  # **kwargs: cannot tell statically
            callee = funcs[call.func.id]
            pos_names = [a.arg for a in callee.args.posonlyargs + callee.args.args]
            passed = set(pos_names[:len(call.args)]) | {k.arg for k in call.keywords if k.arg}
            for param, consts in bound[call.func.id].items():
                if param not in passed:
                    where = "; ".join(sorted({p for c in consts for p in patched[c]}))
                    lines.append(f"{src.name}:{call.lineno} {caller}() calls {call.func.id}() without {param}= "
                                 f"(default bound to {', '.join(sorted(consts))}, patched by {where})")
    return lines


def targets(root: Path) -> list[tuple[Path, Path]]:
    found: list[tuple[Path, Path]] = []
    for study in sorted((root / "research").glob("[0-9][0-9][0-9]-*")):
        for pattern in MODULE_GLOBS:
            for src in sorted((study / "src").glob(pattern)):
                found.append((src, study / "tests"))
    desk = root / "desk-view"
    if desk.exists():
        for src in sorted(desk.glob("*.py")):
            if src.name != "conftest.py":
                found.append((src, desk / "tests"))
    return found


def check(root: Path, verbose: bool = True) -> int:
    failures = 0
    modules = 0
    patched_total = 0
    for src, tests_dir in targets(root):
        modules += 1
        patched: dict[str, list[str]] = {}
        for test_file in sorted(tests_dir.glob("test_*.py")) if tests_dir.exists() else []:
            for const, where in patched_constants(test_file, src.stem).items():
                patched.setdefault(const, []).extend(where)
        if not patched:
            continue
        patched_total += len(patched)
        hits = reached_defaults(src, patched)
        if verbose:
            rel = src.relative_to(root)
            print(f"{rel}: tests patch {', '.join(sorted(patched))}: {'pass' if not hits else f'{len(hits)} reached'}")
            for h in hits:
                print(f"  FAIL {h}")
        failures += len(hits)
    if verbose:
        print(f"bound defaults: {'pass' if not failures else 'FAIL'} ({modules} modules, {patched_total} patched "
              f"constants, {failures} reached through a default)")
    return 1 if failures else 0


# --- self-test over a built fixture -------------------------------------------------------------

_PASSING = '''
from pathlib import Path
RAW_DIR = Path("paper-log/raw")
DECISIONS_DIR = Path("paper-log/decisions")
def load_inputs(raw_dir: Path = RAW_DIR): return raw_dir
def write_record(record, directory: Path = DECISIONS_DIR): return directory
def main(argv=None):
    load_inputs(RAW_DIR)
    return write_record({}, directory=DECISIONS_DIR)
'''

_FAILING = '''
from pathlib import Path
RAW_DIR = Path("paper-log/raw")
DECISIONS_DIR = Path("paper-log/decisions")
def load_inputs(raw_dir: Path = RAW_DIR): return raw_dir
def write_record(record, directory: Path = DECISIONS_DIR): return directory
def main(argv=None):
    load_inputs()
    return write_record({})
'''

_TEST = '''
from src import forward
PATH_NAMES = ["DECISIONS_DIR"]
def test_x(tmp_path, monkeypatch):
    monkeypatch.setattr(forward, "RAW_DIR", tmp_path)
    for name in PATH_NAMES:
        monkeypatch.setattr(forward, name, tmp_path / name)
    forward.main([])
'''


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for study, body in (("001-pass", _PASSING), ("002-fail", _FAILING)):
            (root / "research" / study / "src").mkdir(parents=True)
            (root / "research" / study / "tests").mkdir(parents=True)
            (root / "research" / study / "src" / "forward.py").write_text(body, encoding="utf-8")
            (root / "research" / study / "tests" / "test_forward.py").write_text(_TEST, encoding="utf-8")
        passing = targets(root)[0]
        failing = targets(root)[1]
        patched = patched_constants(passing[1] / "test_forward.py", "forward")
        if sorted(patched) != ["DECISIONS_DIR", "RAW_DIR"]:
            print(f"selftest: patched constants not detected: {patched}")
            return 1
        if reached_defaults(passing[0], patched):
            print("selftest: the passing module was flagged")
            return 1
        hits = reached_defaults(failing[0], patched)
        if len(hits) != 2 or "load_inputs() without raw_dir=" not in hits[0] or "write_record() without directory=" not in hits[1]:
            print(f"selftest: the failing module gave {hits}")
            return 1
        if check(root, verbose=False) != 1:
            print("selftest: check() did not fail on the fixture")
            return 1
    print("bound defaults self-test: pass")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    return check(args.root)


if __name__ == "__main__":
    sys.exit(main())
