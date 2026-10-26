"""Paper dashboard: the forward records of the published studies, read as committed.

Each study that reached publication keeps a ``paper-log/`` folder (Study 003's
paper sleeve, Studies 004 to 008's shadow records with no order, Studies 010
and 011's monthly position records, added 2026-10-26).  Those
folders are written once a month by the studies' own forward code and are
never rewritten.  This module reads them exactly as they are on disk, counts
what exists, derives one equity path per series from the committed shadow
lines and draws it to the house chart standard.  It fetches nothing, runs no
strategy code, writes nothing into any study folder and carries no decision
weight: a record that is not on disk is reported as not on disk, never
estimated.  The output states the time it was generated and the commit it
read, so the dashboard cannot be mistaken for an earlier state (built
2026-10-24, before the first record of 2026-10-30).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from qune_research import nyse, style

__all__ = ["LogSpec", "Status", "build", "equity", "headline", "chart", "next_signal_date", "render",
           "read_json_dir", "read_jsonl", "read_csv", "status", "sha256", "monthly_records", "next_record_month",
           "due_text"]


@dataclass(frozen=True)
class LogSpec:
    """Where one study's forward record lives and how its series are read.

    ``book_columns`` maps a series id to the shadow column that carries its
    book value in USD (Study 004 writes ``T1_book`` and so on).  ``return_columns``
    maps a series id to the column with the period's net return, compounded
    from one unit (Study 005 writes ``T1``, ``B1``, ``B2``).  A study with neither
    is reported without a chart.  ``shadow_file`` names the per-period file in
    ``paper-log/`` (Study 003's §11.5 monthly summary is ``summary.csv``, added
    2026-10-24).  ``strategy`` is drawn in the accent colour; the rest in greys.

    A monthly position record (Studies 010 and 011, added 2026-10-26) sets
    ``records_file``: the CSV in ``paper-log/`` with one row per month and trial
    (and factor), read instead of ``decisions/*.json``.  ``record_format`` turns
    one row into text (``str.format`` on the row; ";" inside a value is shown as
    ", "), rows are joined per trial, and ``release_log`` names the fetch log
    whose last line is shown.  ``first_signal_date`` is then the first record
    month (YYYY-MM).  Such a record has no shadow line and no chart, because the
    study scores it once at the end (``scored_note`` says when and how).
    """

    study: str
    folder: str
    kind: str
    label: str
    first_signal_date: str
    strategy: str = ""
    benchmarks: tuple[str, ...] = ()
    book_columns: dict[str, str] = field(default_factory=dict)
    return_columns: dict[str, str] = field(default_factory=dict)
    book_usd: float = 1.0
    labels: dict[str, str] = field(default_factory=dict)
    data_source: str = ""
    chart_note: str = ""
    shadow_file: str = "shadow.csv"
    records_file: str = ""
    record_format: str = ""
    records_heading: str = "Record by trial"
    release_log: str = ""
    scored_note: str = ""

    @property
    def monthly(self) -> bool:
        return bool(self.records_file)

    @property
    def series(self) -> list[str]:
        return [self.strategy, *self.benchmarks] if self.strategy else []

    @property
    def unit(self) -> str:
        return "USD" if self.book_columns else "unit"


@dataclass
class Status:
    spec: LogSpec
    records: list[dict]
    shadow: pd.DataFrame
    executions: list[dict]
    runs: list[dict]
    stops: list[dict]
    equity: pd.DataFrame
    next_due: str
    inputs: dict[str, str]
    last_check: dict | None = None
    kept_releases: tuple[str, ...] = ()

    @property
    def last_record(self) -> dict | None:
        return self.records[-1] if self.records else None


# --- Reading: everything as committed, nothing computed by a strategy ------------------------

def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json_dir(directory: Path) -> list[dict]:
    """Every ``*.json`` in the folder, in file-name order (the files are dated)."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]


def read_jsonl(path: Path) -> list[dict]:
    path = Path(path)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path)


# --- Derived series --------------------------------------------------------------------------

def equity(shadow: pd.DataFrame, spec: LogSpec) -> pd.DataFrame:
    """One value per series at each period end, starting at the first period's start.

    Book columns are read as they are; return columns are compounded from
    one unit.  The first row is the start of the first period (every series
    at its starting value), so the chart begins where the record begins.
    """
    if not spec.series or shadow.empty:
        return pd.DataFrame(columns=spec.series)
    frame = shadow.sort_values("period_end").reset_index(drop=True)
    start = pd.Timestamp(frame["execution_date"].iloc[0])
    ends = pd.to_datetime(frame["period_end"]).tolist()
    data: dict[str, list[float]] = {}
    for name in spec.series:
        if name in spec.book_columns:
            data[name] = [spec.book_usd, *frame[spec.book_columns[name]].astype(float).tolist()]
        else:
            data[name] = [1.0, *(1.0 + frame[spec.return_columns[name]].astype(float)).cumprod().tolist()]
    return pd.DataFrame(data, index=pd.DatetimeIndex([start, *ends], name="date"), columns=spec.series)


def next_signal_date(last_signal_date: str | None, first_signal_date: str) -> str:
    """The signal date of the next record: the first one, or the last NYSE trading day of the following month."""
    if last_signal_date is None:
        return first_signal_date
    last = pd.Timestamp(last_signal_date)
    month_start = (last + pd.offsets.MonthBegin(1)).normalize()
    month_end = (month_start + pd.offsets.MonthEnd(0)).normalize()
    days = nyse.nyse_trading_days(month_start, month_end)
    return str(days[-1].date())


def _cell(text: str) -> str:
    """Text safe inside one markdown table cell."""
    return str(text).replace("|", "\\|")


def _row_text(fmt: str, row: dict) -> str:
    return _cell(fmt.format(**{k: v.replace(";", ", ") if isinstance(v, str) else v for k, v in row.items()}))


def monthly_records(frame: pd.DataFrame, spec: LogSpec) -> list[dict]:
    """One record per month of a monthly position file, trials in file order, nothing recomputed."""
    if frame.empty:
        return []
    frame = frame.astype({"month": str, "trial": str, "release": str})
    records = []
    for month in sorted(frame["month"].unique()):
        rows = frame[frame["month"] == month]
        parts = []
        for trial in dict.fromkeys(rows["trial"]):
            sub = rows[rows["trial"] == trial].to_dict("records")
            parts.append(f"{trial}: " + ", ".join(_row_text(spec.record_format, r) for r in sub))
        # No late flag is shown: the forward code writes ``late`` False and sets lateness at scoring
        # from the commit time (§11), so the file cannot say whether a row was on time.
        records.append({"signal_date": month, "release": ", ".join(sorted(rows["release"].unique())),
                        "rows": len(rows), "target": "<br>".join(parts)})
    return records


def next_record_month(last_month: str | None, first_month: str, kept: tuple[str, ...] = ()) -> str:
    """The next monthly record and the library release it needs (the first release that contains month t − 1)."""
    month = pd.Period(first_month, "M") if last_month is None else pd.Period(last_month, "M") + 1
    release = (month - 1).strftime("%Y%m")
    state = "archived, record not yet written" if release in kept else "not yet archived"
    return f"{month}, from release {release} ({state})"


def due_text(st: Status) -> str:
    return st.next_due if st.spec.monthly else _uk(st.next_due)


def _check_text(check: dict | None) -> str:
    if not check:
        return "none logged"
    at = pd.Timestamp(check.get("at_utc", ""))
    when = f"{at.strftime('%-d %b %Y %H:%M')}Z" if not pd.isna(at) else "?"
    kept = str(check.get("kept", "")).lower() == "true"
    reason = f" ({check['reason']})" if check.get("reason") else ""
    return _cell(f"{when}: release {check.get('release', '?')} kept" if kept
                 else f"{when}: release {check.get('release', '?')}, not kept{reason}")


def _uk(day: str | date | pd.Timestamp) -> str:
    return pd.Timestamp(day).strftime("%-d %b %Y")


def headline(status: Status) -> str:
    """The chart title: the finding so far, in words, from the equity frame alone."""
    spec, eq = status.spec, status.equity
    if eq.empty or len(eq) < 2:
        return (f"{spec.study}: no holding period has ended yet; the first record is due on "
                f"{_uk(status.next_due)} and the first shadow line after the following month-end")
    n = len(eq) - 1
    b0 = spec.benchmarks[0]
    s, b = float(eq[spec.strategy].iloc[-1]), float(eq[b0].iloc[-1])
    gap = (s / float(eq[spec.strategy].iloc[0]) - b / float(eq[b0].iloc[0])) * 100.0
    word = "ahead of" if gap > 0 else ("behind" if gap < 0 else "level with")
    periods = "period" if n == 1 else "periods"
    gap_text = f"{abs(gap):.1f} pp {word}" if gap != 0 else word
    return (f"{spec.study}: after {n} forward {periods}, {spec.labels.get(spec.strategy, spec.strategy)} is "
            f"{gap_text} {spec.labels.get(b0, b0)} (too few periods for any inference)")


# --- Status ------------------------------------------------------------------------------------

def status(root: Path, spec: LogSpec) -> Status:
    folder = Path(root) / spec.folder / "paper-log"
    if spec.monthly:
        records = monthly_records(read_csv(folder / spec.records_file), spec)
        shadow = pd.DataFrame()
    else:
        records = read_json_dir(folder / "decisions")
        shadow = read_csv(folder / spec.shadow_file)
    executions = read_json_dir(folder / "executions")
    runs = read_jsonl(folder / "runs.jsonl")
    stops = read_jsonl(folder / "stops.jsonl")
    last = records[-1]["signal_date"] if records else None
    inputs = {str(p.relative_to(root)): sha256(p) for p in sorted(folder.rglob("*"))
              if p.is_file() and "raw" not in p.relative_to(folder).parts and p.suffix in (".json", ".csv", ".jsonl")}
    log_path = folder / spec.release_log if spec.release_log else None
    log = (pd.read_csv(log_path, dtype=str, keep_default_na=False) if log_path and log_path.is_file()
           else pd.DataFrame(columns=["at_utc", "kept", "release", "reason"]))
    check = log.iloc[-1].to_dict() if not log.empty else None
    kept = tuple(log.loc[log["kept"].str.lower() == "true", "release"]) if not log.empty else ()
    due = (next_record_month(last, spec.first_signal_date, kept) if spec.monthly
           else next_signal_date(last, spec.first_signal_date))
    return Status(spec, records, shadow, executions, runs, stops, equity(shadow, spec), due, inputs, check, kept)


# --- Chart -------------------------------------------------------------------------------------

def chart(status: Status) -> Figure:
    """Equity of every series from the shadow lines, strategy in the accent; passes ``style.check``."""
    spec, eq = status.spec, status.equity
    fig, ax = style.figure(8.0, 4.6)
    assert isinstance(ax, Axes)
    plt.rcParams["svg.hashsalt"] = "qune-research"   # deterministic SVG ids: the same inputs give the same bytes
    unit = "book value, USD" if spec.unit == "USD" else "growth of one unit"
    period = f"{_uk(eq.index[0])} to {_uk(eq.index[-1])}" if len(eq) else "no period yet"
    style.title(fig, headline(status), f"Forward record from the committed shadow lines; {unit}, net of base costs; {period}")
    greys = list(style.CONTEXT)
    colours = {spec.strategy: style.ACCENT, **{b: greys[i % len(greys)] for i, b in enumerate(spec.benchmarks)}}
    for name in reversed(spec.series):
        ax.plot(eq.index, eq[name], color=colours[name], linewidth=1.8 if name == spec.strategy else 1.2)
    style.despine(ax)
    if spec.unit == "USD":
        style.thousands_axis(ax)
    ax.set_ylabel(unit.capitalize())
    ends = [style.EndLabel(spec.labels.get(n, n), float(eq[n].iloc[-1]), colours[n]) for n in spec.series]
    style.label_line_ends(ax, ends, min_gap=0.07, fontsize=9.0)
    style.source(fig, spec.data_source, period, spec.study, spec.chart_note or None)
    return fig


# --- Markdown ----------------------------------------------------------------------------------

def _record_row(record: dict) -> str:
    status_text = str(record.get("status", "?"))
    target = record.get("target")
    if isinstance(target, dict):
        target = ", ".join(f"{k} {v:.1%}" for k, v in sorted(target.items()) if isinstance(v, int | float) and v)
    execution = record.get("execution_date") or "n/a"
    return f"| {record.get('signal_date', '?')} | {execution} | {status_text} | {target if target else 'none'} |"


def _study_section(st: Status, chart_rel: str | None) -> list[str]:
    spec = st.spec
    lines = [f"## {spec.study} ({spec.kind})", "",
             f"**Label: {spec.label}.** Folder `{spec.folder}/paper-log/`.", ""]
    if spec.monthly:
        rec = st.last_record
        rows = [("Monthly records", f"{len(st.records)}"),
                ("Last record", f"{rec['signal_date']} from release {rec['release']}" if rec else "none yet"),
                ("Last release check", _check_text(st.last_check)),
                ("Next record due", st.next_due),
                ("Scoring", spec.scored_note or "not stated")]
        lines += ["| | |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows] + [""]
        if st.records:
            lines += [f"| Month | Release | {spec.records_heading} |", "|---|---|---|"]
            lines += [f"| {r['signal_date']} | {r['release']} | {r['target']} |" for r in st.records] + [""]
        lines += [spec.chart_note or "No equity line: this record is scored once at the end.", ""]
        return lines
    rows = [("Decision records", f"{len(st.records)}"),
            ("Last record", f"{st.last_record['signal_date']} ({st.last_record.get('status', '?')})" if st.last_record else "none yet"),
            ("Shadow lines (holding periods ended)", f"{len(st.shadow)}"),
            ("Next record due (signal date)", _uk(st.next_due))]
    if spec.kind == "paper sleeve":
        rows.append(("Execution records (orders)", f"{len(st.executions)}"))
        rows.append(("Runner lines in runs.jsonl", f"{len(st.runs)}"))
        rows.append(("Daily stop-check lines", f"{len(st.stops)}"))
    lines += ["| | |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows] + [""]
    if st.records:
        lines += ["| Signal date | Execution date | Status | Target |", "|---|---|---|---|"]
        lines += [_record_row(r) for r in st.records] + [""]
    if chart_rel:
        lines += [f"![{headline(st)}]({chart_rel})", ""]
        last = st.equity.iloc[-1]
        unit = "USD" if spec.unit == "USD" else "× start"
        lines += ["| Series | Value at the last period end |", "|---|---|"]
        lines += [f"| {spec.labels.get(n, n)} | {last[n]:,.2f} {unit} |" for n in spec.series] + [""]
    elif spec.series:
        lines += [f"No chart yet: the first shadow line follows the record after {_uk(st.next_due)}.", ""]
    else:
        lines += [spec.chart_note or "No equity series is defined for this record yet.", ""]
    return lines


def render(statuses: list[Status], generated_at_utc: str, commit: str, charts: dict[str, str]) -> str:
    """The dashboard page.  Every number is a count or a value read from the committed files."""
    lines = ["# Paper dashboard: the forward records, as committed", "",
             f"Generated {generated_at_utc} from the files at commit `{commit}` by `tools/make_paper_dashboard.py`. "
             "Each study's forward code writes its own record once a month and never rewrites it; this page only "
             "counts and draws what is on disk at generation time, so an empty row means no record exists yet, not "
             "that one was missed. Nothing here is a backtest: every value is a forward observation after the "
             "study's publication. No study has a supported verdict; no order has been placed. Not advice.", ""]
    lines += ["| Study | Kind | Records | Shadow lines | Next record due |", "|---|---|---|---|---|"]
    for st in statuses:
        shadow = "none (scored once at the end)" if st.spec.monthly else f"{len(st.shadow)}"
        lines.append(f"| {st.spec.study} | {st.spec.kind}, {st.spec.label} | {len(st.records)} | {shadow} | "
                     f"{due_text(st)} |")
    lines.append("")
    for st in statuses:
        lines += _study_section(st, charts.get(st.spec.study))
    lines += ["## How this page is made", "",
              "`make dashboard` runs `tools/make_paper_dashboard.py`, which reads each study's `paper-log/decisions/*.json`, "
              "`shadow.csv` (Study 003: its §11.5 `summary.csv`), `executions/*.json`, `runs.jsonl` and `stops.jsonl` as committed (Studies 010 and "
              "011: their monthly `positions.csv` or `cohorts.csv` and the last line of `releases/fetch_log.csv`), compounds the shadow "
              "lines' net returns (or reads the book values Study 004 writes) into one path per series, and draws it with "
              "`qune_research/style.py`. The SHA-256 of every input file and the generation time are in `manifest.json`. "
              "The page is regenerated by the work loop after each record; a run that finds nothing new changes only the "
              "time stamp. The forward records' own rules (no record before the close, never overwritten, misses "
              "logged as misses; Studies 010 and 011: only the first release that contains month t − 1, never replaced, late rows "
              "labelled at scoring from the commit time) are in each study's `paper-log/README.md`.", ""]
    return "\n".join(lines)


# --- Build -------------------------------------------------------------------------------------

def git_commit(root: Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build(root: Path, specs: list[LogSpec], out_dir: Path, generated_at_utc: str, commit: str | None = None) -> dict:
    """Write README.md, one chart per study with shadow lines, and manifest.json into ``out_dir``."""
    root, out_dir = Path(root), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    commit = commit or git_commit(root)
    statuses = [status(root, spec) for spec in specs]
    charts: dict[str, str] = {}
    outputs: dict[str, str] = {}
    for st in statuses:
        if len(st.equity) >= 2:
            stem = out_dir / f"{st.spec.folder.split('/')[-1][:3]}_forward"
            fig = chart(st)
            svg, png = style.save(fig, stem)
            plt.close(fig)
            charts[st.spec.study] = svg.name
            outputs[svg.name] = sha256(svg)
            outputs[png.name] = sha256(png)
    readme = render(statuses, generated_at_utc, commit, charts)
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    manifest = {
        "generated_at_utc": generated_at_utc, "commit": commit,
        "studies": [{"study": st.spec.study, "records": len(st.records), "shadow_lines": len(st.shadow),
                     "executions": len(st.executions), "next_record_due": st.next_due,
                     "inputs_sha256": st.inputs} for st in statuses],
        "outputs_sha256": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
