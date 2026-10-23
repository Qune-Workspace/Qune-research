"""One-page tear-sheet from a table of monthly returns (shared library).

A tear-sheet is a *description* of a return series beside its benchmarks:
growth of one unit, drawdown from the running high, the standard metrics,
calendar-year returns and the strategy-minus-benchmark differences with a
Newey-West t-statistic.  It computes nothing a study's pre-registration did
not already define (the metric functions are those of ``stats``), it carries
no decision weight and it never decides a verdict: the verdict rules live in
each study's PREREGISTRATION.md and were applied once, by the study's own code.

The chart follows the house standard (``style``): the title states the
finding and every number in it is computed here from the same table the
panels are drawn from, never typed.  ``style.save`` refuses a figure that
fails the mechanical part of the standard.

Input: a ``pandas.DataFrame`` of simple monthly returns (fractions, not per
cent) with a sorted ``DatetimeIndex`` of period-end dates, one column per
series.  Sharpe ratios are of the excess return over the ``cash`` column when
one is given and of the raw return otherwise.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from . import stats, style

METRIC_ORDER = [
    "months", "ann_return", "ann_volatility", "sharpe", "max_drawdown", "worst_month",
    "best_month", "hit_rate", "mean_monthly", "skewness", "kurtosis", "final_growth",
]
METRIC_LABELS = {
    "months": "Months",
    "ann_return": "Return, % a year",
    "ann_volatility": "Volatility, % a year",
    "sharpe": "Sharpe ratio",
    "max_drawdown": "Maximum drawdown, %",
    "worst_month": "Worst month, %",
    "best_month": "Best month, %",
    "hit_rate": "Months up, %",
    "mean_monthly": "Mean month, %",
    "skewness": "Skewness",
    "kurtosis": "Kurtosis",
    "final_growth": "Growth of 1",
}
PERCENT_METRICS = {"ann_return", "ann_volatility", "max_drawdown", "worst_month", "best_month",
                   "hit_rate", "mean_monthly"}


# ----------------------------------------------------------------------------
# Tables.
# ----------------------------------------------------------------------------

def _f(frame: pd.DataFrame, row: Any, col: Any) -> float:
    """One cell of a table as a float (pandas types a .loc scalar as a wide union)."""
    v: Any = frame.loc[row, col]
    return float(v)


def _validate(monthly: pd.DataFrame, columns: list[str]) -> None:
    if not isinstance(monthly.index, pd.DatetimeIndex):
        raise TypeError("monthly returns need a DatetimeIndex of period-end dates")
    if not monthly.index.is_monotonic_increasing or monthly.index.has_duplicates:
        raise ValueError("the index must be sorted and without duplicates")
    missing = [c for c in columns if c not in monthly.columns]
    if missing:
        raise KeyError(f"columns not in the table: {missing}")
    if len(monthly) < 2:
        raise ValueError("at least two months are needed")
    bad = [c for c in columns if monthly[c].isna().any()]
    if bad:
        raise ValueError(f"missing monthly returns in {bad}; the tear-sheet does not fill gaps")


def metrics_table(monthly: pd.DataFrame, columns: list[str], cash: str | None = None) -> pd.DataFrame:
    """One column per series, one row per metric (``METRIC_ORDER``).

    ``ann_return`` is geometric, ``ann_volatility`` is the monthly standard
    deviation times the square root of twelve, ``sharpe`` is annualised from
    the excess over ``cash`` (raw when ``cash`` is None) and NaN when the
    series has no variance, ``max_drawdown`` is the most negative decline of
    the total-return index from its running high, ``hit_rate`` is the share
    of months with a return above zero.  Fractions, not per cent.
    """
    _validate(monthly, columns + ([cash] if cash else []))
    out: dict[str, dict[str, float]] = {}
    for c in columns:
        r = monthly[c].astype(float)
        excess = r - monthly[cash].astype(float) if cash else r
        index = stats.total_return_index(r)
        # A constant excess (a cash leg against itself) has a standard deviation
        # of rounding noise, not zero; no Sharpe ratio is reported for it.
        sd = float(excess.std(ddof=1))
        sharpe = stats.sharpe_annual(excess) if sd > 1e-12 else float("nan")
        out[c] = {
            "months": float(len(r)),
            "ann_return": stats.annualised_geometric_return(r),
            "ann_volatility": stats.annualised_volatility(r),
            "sharpe": sharpe,
            "max_drawdown": stats.max_drawdown(index),
            "worst_month": float(r.min()),
            "best_month": float(r.max()),
            "hit_rate": float((r > 0).mean()),
            "mean_monthly": float(r.mean()),
            "skewness": stats.skewness(r) if r.std(ddof=0) > 0 else float("nan"),
            "kurtosis": stats.kurtosis(r) if r.std(ddof=0) > 0 else float("nan"),
            "final_growth": float(index.iloc[-1]),
        }
    return pd.DataFrame(out).reindex(METRIC_ORDER)


def calendar_year_returns(monthly: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Compounded return per calendar year, with the number of months in each.

    A year with fewer than twelve months is a partial year; the ``months``
    column says so and the caller is expected to print it.
    """
    _validate(monthly, columns)
    years = pd.DatetimeIndex(monthly.index).year
    rows = {}
    for y in sorted(set(years)):
        part = monthly.loc[years == y, columns].astype(float)
        row = {c: float(np.prod(1.0 + part[c]) - 1.0) for c in columns}
        row["months"] = float(len(part))
        rows[int(y)] = row
    table = pd.DataFrame(rows).T
    table.index.name = "year"
    return table[["months"] + columns]


def difference_table(monthly: pd.DataFrame, strategy: str, benchmarks: list[str],
                     cash: str | None = None, lags: int = stats.NEWEY_WEST_LAGS) -> pd.DataFrame:
    """Strategy minus each benchmark: mean monthly difference, its Newey-West
    t-statistic (``stats.newey_west_mean``), the annualised return gap and the
    Sharpe-ratio gap.  One row per benchmark."""
    _validate(monthly, [strategy] + benchmarks + ([cash] if cash else []))
    met = metrics_table(monthly, [strategy] + benchmarks, cash)
    rows = {}
    for b in benchmarks:
        nw = stats.newey_west_mean(monthly[strategy].astype(float) - monthly[b].astype(float), lags=lags)
        rows[b] = {
            "mean_monthly_diff": nw["mean"],
            "se": nw["se"],
            "t_newey_west": nw["t"],
            "lags": float(nw["lags"]),
            "n": float(nw["n"]),
            "ann_return_gap": _f(met, "ann_return", strategy) - _f(met, "ann_return", b),
            "sharpe_gap": _f(met, "sharpe", strategy) - _f(met, "sharpe", b),
            "max_drawdown_gap": _f(met, "max_drawdown", strategy) - _f(met, "max_drawdown", b),
        }
    table = pd.DataFrame(rows).T
    table.index.name = "benchmark"
    return table


# ----------------------------------------------------------------------------
# The sheet.
# ----------------------------------------------------------------------------

@dataclass
class TearSheet:
    strategy: str
    benchmarks: list[str]
    cash: str | None
    labels: dict[str, str]
    period: str
    metrics: pd.DataFrame
    calendar: pd.DataFrame
    differences: pd.DataFrame
    index: pd.DataFrame
    drawdown: pd.DataFrame
    headline: str = ""
    inputs: dict[str, str] = field(default_factory=dict)

    @property
    def series(self) -> list[str]:
        return [self.strategy] + self.benchmarks

    def to_dict(self) -> dict[str, Any]:
        """Every number on the sheet, JSON-ready (NaN becomes null)."""
        def clean(frame: pd.DataFrame) -> dict[str, Any]:
            d = frame.to_dict(orient="index")
            return {str(k): {str(kk): (None if isinstance(vv, float) and math.isnan(vv) else vv)
                             for kk, vv in v.items()} for k, v in d.items()}
        return {
            "strategy": self.strategy,
            "benchmarks": self.benchmarks,
            "cash": self.cash,
            "labels": self.labels,
            "period": self.period,
            "months": int(_f(self.metrics, "months", self.strategy)),
            "headline": self.headline,
            "metrics": clean(self.metrics),
            "calendar_year_returns": clean(self.calendar),
            "differences": clean(self.differences),
            "final_index": {c: float(self.index[c].iloc[-1]) for c in self.index.columns},
            "inputs": self.inputs,
        }


def _period_label(idx: pd.Index) -> str:
    return f"{pd.Timestamp(idx[0]):%Y-%m} to {pd.Timestamp(idx[-1]):%Y-%m}"


MATCHED_SHARPE_GAP = 0.05
"""Below this absolute Sharpe-ratio gap the headline says "matched" rather than
"beat" or "lagged": a gap of a few hundredths over a decade is inside the noise
of any such comparison (Study 004's in-sample gap of 0.005 came with a
Newey-West t of 0.65), and a verb of victory would overstate it."""


def _minus(text: str) -> str:
    """Hyphen-minus to the typographic minus the tick labels use (``style.pct`` does the same)."""
    return text.replace("-", "−")


def headline(metrics: pd.DataFrame, strategy: str, benchmark: str, labels: dict[str, str] | None = None,
             t_stat: float | None = None) -> str:
    """A title that states what the numbers say, built from the metrics table.

    The verb follows the Sharpe gap ("beat" or "lagged" beyond
    ``MATCHED_SHARPE_GAP``, "matched" inside it); the Newey-West t of the
    monthly gap is quoted when given, so the reader can weigh the verb; every
    figure is read from the table, so the sentence cannot overstate the panels
    below it.
    """
    labels = labels or {}
    s_name = labels.get(strategy, strategy)
    b_name = labels.get(benchmark, benchmark)
    s_ret = _f(metrics, "ann_return", strategy) * 100.0
    b_ret = _f(metrics, "ann_return", benchmark) * 100.0
    s_sr = _f(metrics, "sharpe", strategy)
    b_sr = _f(metrics, "sharpe", benchmark)
    s_dd = _f(metrics, "max_drawdown", strategy) * 100.0
    b_dd = _f(metrics, "max_drawdown", benchmark) * 100.0
    if math.isnan(s_sr) or math.isnan(b_sr):
        verb = "returned"
    elif abs(s_sr - b_sr) < MATCHED_SHARPE_GAP:
        verb = "matched"
    elif s_sr > b_sr:
        verb = "beat"
    else:
        verb = "lagged"
    # Only the numbers get the typographic minus: labels such as "Newey-West" keep their hyphen.
    n = _minus
    t_text = "" if t_stat is None or math.isnan(t_stat) else f" (Newey-West t {n(f'{t_stat:.2f}')})"
    if verb == "returned":
        head = f"{s_name} returned {n(f'{s_ret:+.1f}')}% a year to {b_name}'s {n(f'{b_ret:+.1f}')}%{t_text}"
    else:
        head = (f"{s_name} {verb} {b_name} on Sharpe ratio, {n(f'{s_sr:.2f}')} to {n(f'{b_sr:.2f}')}{t_text}, "
                f"returning {n(f'{s_ret:+.1f}')}% a year to its {n(f'{b_ret:+.1f}')}%")
    return head + f"; maximum drawdown {n(f'{s_dd:.1f}')}% against {n(f'{b_dd:.1f}')}%"


def build(monthly: pd.DataFrame, strategy: str, benchmarks: list[str], cash: str | None = None,
          labels: dict[str, str] | None = None, lags: int = stats.NEWEY_WEST_LAGS,
          inputs: dict[str, str] | None = None) -> TearSheet:
    """Compute every table of the sheet from the monthly returns."""
    _validate(monthly, [strategy] + benchmarks + ([cash] if cash else []))
    cols = [strategy] + benchmarks
    labels = dict(labels or {})
    met = metrics_table(monthly, cols, cash)
    index = pd.DataFrame({c: stats.total_return_index(monthly[c].astype(float)) for c in cols})
    first: pd.Timestamp = pd.DatetimeIndex(monthly.index)[0]
    before = first - pd.offsets.MonthEnd(1)
    start = pd.DataFrame({c: [1.0] for c in cols}, index=pd.DatetimeIndex([before]))
    index = pd.concat([start, index])
    drawdown = index / index.cummax() - 1.0
    sheet = TearSheet(
        strategy=strategy, benchmarks=list(benchmarks), cash=cash, labels=labels,
        period=_period_label(monthly.index), metrics=met,
        calendar=calendar_year_returns(monthly, cols),
        differences=difference_table(monthly, strategy, benchmarks, cash, lags),
        index=index, drawdown=drawdown, inputs=dict(inputs or {}),
    )
    sheet.headline = headline(met, strategy, benchmarks[0], labels,
                              t_stat=_f(sheet.differences, benchmarks[0], "t_newey_west"))
    return sheet


# ----------------------------------------------------------------------------
# Drawing.
# ----------------------------------------------------------------------------

def _fmt(metric: str, value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    if metric == "months":
        return f"{int(value):,d}"
    if metric in PERCENT_METRICS:
        text = f"{value * 100.0:+.1f}" if metric in {"ann_return", "worst_month", "best_month", "mean_monthly",
                                                      "max_drawdown"} else f"{value * 100.0:.1f}"
        return _minus(text)
    return _minus(f"{value:.2f}")


def _colours(sheet: TearSheet) -> dict[str, str]:
    palette = [style.ACCENT] + list(style.CONTEXT)
    return {c: palette[min(i, len(palette) - 1)] for i, c in enumerate(sheet.series)}


def draw(sheet: TearSheet, data_source: str, study: str, subtitle: str | None = None,
         note: str | None = None) -> Figure:
    """The one-page figure: growth of one unit, drawdown, metrics and calendar years.

    Passes ``style.check``; the title is ``sheet.headline``.  Line ends carry
    the labels (keep them short); the tables use the series ids as headers.
    """
    style.apply()
    fig = plt.figure(figsize=(8.5, 10.5))
    sub = subtitle or (f"Monthly returns, {sheet.period}; Sharpe ratio of the excess over "
                       f"{sheet.labels.get(sheet.cash, sheet.cash) if sheet.cash else 'zero'}, annualised; "
                       f"drawdown from the running high of the total-return index")
    top = style.title(fig, sheet.headline, sub)          # placed first so the axes start below it
    grid = fig.add_gridspec(nrows=3, ncols=1, height_ratios=[3.0, 1.3, 3.2], hspace=0.38,
                            left=0.08, right=0.80, top=top, bottom=0.07)
    ax_growth = fig.add_subplot(grid[0])
    ax_dd = fig.add_subplot(grid[1], sharex=ax_growth)
    bottom = grid[2].subgridspec(1, 2, width_ratios=[1.25, 1.0], wspace=0.08)
    ax_met = fig.add_subplot(bottom[0])
    ax_cal = fig.add_subplot(bottom[1])
    colours = _colours(sheet)

    # Growth of one unit: the strategy in the accent, benchmarks in greys.
    for c in reversed(sheet.series):
        lw = 1.8 if c == sheet.strategy else 1.2
        ax_growth.plot(sheet.index.index, sheet.index[c], color=colours[c], linewidth=lw)
    style.despine(ax_growth)
    ax_growth.set_ylabel("Growth of 1 unit")
    ax_growth.tick_params(labelbottom=False)
    ends = [style.EndLabel(sheet.labels.get(c, c), float(sheet.index[c].iloc[-1]), colours[c])
            for c in sheet.series]
    style.label_line_ends(ax_growth, ends, min_gap=0.06, fontsize=9.0)

    # Drawdown from the running high: same colours, no labels (they would sit on top of each other at zero).
    for c in reversed(sheet.series):
        lw = 1.6 if c == sheet.strategy else 1.0
        ax_dd.plot(sheet.drawdown.index, sheet.drawdown[c], color=colours[c], linewidth=lw)
    ax_dd.fill_between(sheet.drawdown.index, sheet.drawdown[sheet.strategy], 0.0,
                       color=style.ACCENT, alpha=0.12, linewidth=0)
    style.despine(ax_dd)
    style.percent_axis(ax_dd)
    ax_dd.set_ylabel("Drawdown")
    s_dd = _f(sheet.metrics, "max_drawdown", sheet.strategy)
    ax_dd.annotate(_minus(f"{sheet.strategy} worst {s_dd * 100.0:.1f}%"),
                   xy=(sheet.drawdown.index[-1], float(sheet.drawdown[sheet.strategy].iloc[-1])),
                   xytext=(6.0, 0), textcoords="offset points", ha="left", va="center", fontsize=9.0,
                   color=style.ACCENT, annotation_clip=False)

    # Metrics (left) and calendar years (right) as borderless tables headed by the series ids.
    header = [""] + list(sheet.series)
    met_rows: list[list[str]] = []
    for m in METRIC_ORDER:
        met_rows.append([METRIC_LABELS[m]] + [_fmt(m, _f(sheet.metrics, m, c)) for c in sheet.series])
    b0 = sheet.benchmarks[0]
    diff = sheet.differences
    met_rows.append([""] * len(header))
    met_rows.append([f"{sheet.strategy} minus {b0}, % a month"]
                    + [_minus(f"{_f(diff, b0, 'mean_monthly_diff') * 100.0:+.2f}")] + [""] * (len(header) - 2))
    met_rows.append([f"Newey-West t, {int(_f(diff, b0, 'lags'))} lags"]
                    + [_minus(f"{_f(diff, b0, 't_newey_west'):.2f}")] + [""] * (len(header) - 2))
    cal_rows: list[list[str]] = []
    for year in sheet.calendar.index:
        n = int(_f(sheet.calendar, year, "months"))
        year_label: str = f"{int(str(year))}" + ("" if n == 12 else f" ({n} m)")
        cal_rows.append([year_label] + [_minus(f"{_f(sheet.calendar, year, c) * 100.0:+.1f}") for c in sheet.series])
    _table(ax_met, met_rows, header, colours, fontsize=8.0, row_height=1.0, label_width=0.44)
    _table(ax_cal, cal_rows, ["Year, %"] + list(sheet.series), colours, fontsize=8.0,
           row_height=min(1.0, 15.0 / max(len(cal_rows), 1)), label_width=0.3)

    style.source(fig, data_source, sheet.period, study, note)
    return fig


def _table(ax: Axes, rows: list[list[str]], header: list[str], colours: dict[str, str],
           fontsize: float, row_height: float, label_width: float = 0.3) -> None:
    ax.set_axis_off()
    style.despine(ax, keep=())
    n = len(header) - 1
    widths = [label_width] + [(1.0 - label_width) / n] * n
    table = ax.table(cellText=rows, colLabels=header, loc="upper left", cellLoc="right", colLoc="right",
                     edges="open", colWidths=widths)
    table.auto_set_font_size(False)
    table.set_fontsize(fontsize)
    table.scale(1.0, 1.05 * row_height)
    for (r, c), cell in table.get_celld().items():
        cell.set_text_props(color=style.TEXT, fontfamily=style.FONT_FAMILY)
        if c == 0:
            cell.set_text_props(ha="left", color=style.TEXT_MUTED)
        if r == 0:
            col_name = header[int(c)]
            cell.set_text_props(fontweight="bold", color=colours.get(col_name, style.TEXT))


def write(sheet: TearSheet, fig: Figure, out_dir: str | Path, stem: str) -> dict[str, Path]:
    """Write ``stem.svg``, ``stem.png`` (via ``style.save``), ``stem.json`` and three CSVs."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    svg, png = style.save(fig, out / stem)
    paths = {"svg": svg, "png": png, "json": out / f"{stem}.json",
             "metrics": out / f"{stem}_metrics.csv", "calendar": out / f"{stem}_calendar.csv",
             "differences": out / f"{stem}_differences.csv"}
    paths["json"].write_text(json.dumps(sheet.to_dict(), indent=2, sort_keys=True) + "\n")
    sheet.metrics.to_csv(paths["metrics"], float_format="%.12g")
    sheet.calendar.to_csv(paths["calendar"], float_format="%.12g")
    sheet.differences.to_csv(paths["differences"], float_format="%.12g")
    return paths
