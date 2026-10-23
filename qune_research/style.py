"""House chart style for every report script in this repository.

The standard (set by the owner on 2026-10-23) in one place, so that every study,
the desk view and the paper log draw charts that look the same and read the
same way:

1. The title states the finding, not the variable names.  A subtitle carries
   the units and the period.
2. One message per chart: the series that matters in the accent colour, the
   rest in greys.  Never the matplotlib default colour cycle, never rainbows,
   3D, shadows or gradients.
3. No clutter: top and right spines off, faint horizontal gridlines only, no
   chart border, lines labelled at their ends instead of a legend, bars sorted
   by value.
4. One sans-serif family; title 13-14 pt, labels 10 pt; left-aligned title;
   consistent number formats (%, bp, $) with thousands separators.
5. A source line bottom left: data source, sample period, "Qune Research" and
   the study id.  Regime shading only when it supports the message.
6. Export as SVG plus a 2x PNG.

``check(fig)`` tests a figure against the mechanical part of this list and
returns the failures as text; ``save`` refuses a figure that fails it, so a
script cannot publish a chart that breaks the standard by accident.  The
judgement calls (does the title state the finding? is there one message?) stay
with the Tester review.

Nothing here reads data or computes a number.
"""

from __future__ import annotations

import textwrap
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from cycler import cycler  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.colors import to_hex  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator, PercentFormatter  # noqa: E402

# ----------------------------------------------------------------------------
# Palette.  One accent, one counter-accent for a second emphasis only when the
# message needs it, four greys for context series, and the text and grid tones.
# ----------------------------------------------------------------------------

ACCENT = "#0B5394"        # the series the chart is about
ACCENT_2 = "#B4533A"      # a second emphasis (a loss, a benchmark that wins), used sparingly
GREY_DARK = "#4A4A4A"     # the main comparison series
GREY = "#8A8A8A"
GREY_LIGHT = "#BDBDBD"
GREY_FAINT = "#DCDCDC"
TEXT = "#1F1F1F"
TEXT_MUTED = "#6B6B6B"
GRID = "#E8E8E8"
SHADE = "#F1F1F1"         # regime or recession shading
CONTEXT = (GREY_DARK, GREY, GREY_LIGHT, GREY_FAINT)

# Matplotlib's default cycle, which must never appear in a published chart.
_DEFAULT_CYCLE = {
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
}

FONT_FAMILY = ["Helvetica Neue", "Helvetica", "Arial", "Liberation Sans", "DejaVu Sans"]
TITLE_SIZE = 13.5
SUBTITLE_SIZE = 10.0
LABEL_SIZE = 10.0
TICK_SIZE = 9.0
SOURCE_SIZE = 8.0
BASE_DPI = 100            # the PNG is written at twice this

_SOURCE_TAG = "qune-source-line"
_TITLE_TAG = "qune-title"
_SUBTITLE_TAG = "qune-subtitle"


def rc_params() -> dict:
    """The rcParams of the house style, as a dict so that scripts can inspect them."""
    return {
        "font.family": "sans-serif",
        "font.sans-serif": FONT_FAMILY,
        "font.size": LABEL_SIZE,
        "text.color": TEXT,
        "axes.titlesize": TITLE_SIZE,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.labelsize": LABEL_SIZE,
        "axes.labelcolor": TEXT_MUTED,
        "axes.edgecolor": GREY_LIGHT,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "axes.prop_cycle": cycler(color=[ACCENT, *CONTEXT]),
        "axes.facecolor": "white",
        "figure.facecolor": "white",
        "figure.edgecolor": "white",
        "figure.frameon": False,
        "figure.dpi": BASE_DPI,
        "savefig.dpi": 2 * BASE_DPI,
        "savefig.facecolor": "white",
        "savefig.edgecolor": "white",
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "grid.linestyle": "-",
        "xtick.labelsize": TICK_SIZE,
        "ytick.labelsize": TICK_SIZE,
        "xtick.color": TEXT_MUTED,
        "ytick.color": TEXT_MUTED,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 3.0,
        "ytick.major.size": 0.0,
        "lines.linewidth": 1.6,
        "lines.solid_capstyle": "round",
        "legend.frameon": False,
        "legend.fontsize": LABEL_SIZE,
        "axes.formatter.use_mathtext": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }


def apply() -> None:
    """Install the house style into matplotlib for the rest of the process."""
    plt.rcParams.update(rc_params())


def figure(width: float = 8.0, height: float = 4.5, nrows: int = 1, ncols: int = 1,
           **kwargs) -> tuple[Figure, Axes | list]:
    """A figure in the house style with room for the title block and the source line."""
    apply()
    fig, ax = plt.subplots(nrows, ncols, figsize=(width, height), **kwargs)
    fig.subplots_adjust(left=0.09, right=0.78, top=0.80, bottom=0.17)
    return fig, ax


# ----------------------------------------------------------------------------
# Text blocks.
# ----------------------------------------------------------------------------

def _wrap(text: str, fig: Figure, fontsize: float, x: float, right: float = 0.97,
          em: float = 0.56) -> list[str]:
    """Wrap to the figure width; ``em`` is the average character width in ems (bold is wider)."""
    width_pt = (right - x) * fig.get_size_inches()[0] * 72.0
    chars = max(20, int(width_pt / (em * fontsize)))
    return textwrap.wrap(text, width=chars) or [""]


def title(fig: Figure, finding: str, subtitle: str | None = None, x: float = 0.02) -> float:
    """Left-aligned title that states the finding, with the units and period below it.

    Wraps both to the figure width, places the subtitle under the last title
    line, moves the axes' top edge below the block, and returns that edge
    (figure fraction).
    """
    height_pt = fig.get_size_inches()[1] * 72.0
    title_lines = _wrap(finding, fig, TITLE_SIZE, x, em=0.66)
    y = 0.965
    fig.text(x, y, "\n".join(title_lines), ha="left", va="top", fontsize=TITLE_SIZE, fontweight="bold",
             color=TEXT, gid=_TITLE_TAG, linespacing=1.15)
    y -= len(title_lines) * TITLE_SIZE * 1.15 / height_pt + 6.0 / height_pt
    if subtitle:
        sub_lines = _wrap(subtitle, fig, SUBTITLE_SIZE, x)
        fig.text(x, y, "\n".join(sub_lines), ha="left", va="top", fontsize=SUBTITLE_SIZE,
                 color=TEXT_MUTED, gid=_SUBTITLE_TAG, linespacing=1.2)
        y -= len(sub_lines) * SUBTITLE_SIZE * 1.2 / height_pt
    top = y - 16.0 / height_pt
    fig.subplots_adjust(top=top)
    return top


def source(fig: Figure, data_source: str, period: str, study: str, note: str | None = None,
           x: float = 0.02) -> None:
    """The source line, bottom left: data source, sample period, Qune Research, study id."""
    text = f"Source: {data_source}. Sample {period}. Qune Research, {study}."
    if note:
        text += f" {note}"
    fig.text(x, 0.02, text, ha="left", va="bottom", fontsize=SOURCE_SIZE, color=TEXT_MUTED,
             gid=_SOURCE_TAG, wrap=True)


def despine(ax: Axes, keep: Iterable[str] = ("left", "bottom")) -> None:
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(side in keep)


# ----------------------------------------------------------------------------
# Direct labels instead of legends.
# ----------------------------------------------------------------------------

@dataclass
class EndLabel:
    text: str
    y: float
    color: str


def label_line_ends(ax: Axes, labels: Sequence[EndLabel], x: float | None = None,
                    min_gap: float = 0.045, pad_points: float = 6.0, fontsize: float = LABEL_SIZE) -> list[float]:
    """Write each label just right of the axes at its line's final y, nudged apart.

    Labels are placed at their own y, then pushed apart in axes fractions so no
    two are closer than ``min_gap``.  Returns the y positions used (data units).
    """
    if not labels:
        return []
    y0, y1 = ax.get_ylim()
    span = (y1 - y0) or 1.0
    order = sorted(range(len(labels)), key=lambda i: labels[i].y)
    frac = [(labels[i].y - y0) / span for i in order]
    for k in range(1, len(frac)):
        if frac[k] - frac[k - 1] < min_gap:
            frac[k] = frac[k - 1] + min_gap
    overshoot = frac[-1] - 1.0 + 0.01
    if overshoot > 0:
        frac = [f - overshoot for f in frac]
    placed: list[float] = [0.0] * len(labels)
    xpos = ax.get_xlim()[1] if x is None else x
    for k, i in enumerate(order):
        y = y0 + frac[k] * span
        placed[i] = y
        ax.annotate(labels[i].text, xy=(xpos, y), xytext=(pad_points, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=fontsize, color=labels[i].color,
                    annotation_clip=False)
    return placed


def shade(ax: Axes, start, end, label: str | None = None, color: str = SHADE) -> None:
    """A regime or recession band; use only when it supports the message."""
    ax.axvspan(start, end, color=color, lw=0, zorder=0)
    if label:
        ax.annotate(label, xy=(start, 1.0), xycoords=("data", "axes fraction"), xytext=(2, -2),
                    textcoords="offset points", ha="left", va="top", fontsize=TICK_SIZE, color=TEXT_MUTED)


# ----------------------------------------------------------------------------
# Number formats.
# ----------------------------------------------------------------------------

def percent_axis(ax: Axes, axis: str = "y", decimals: int = 0, xmax: float = 1.0) -> None:
    fmt = PercentFormatter(xmax=xmax, decimals=decimals)
    which = ax.yaxis if axis == "y" else ax.xaxis
    which.set_major_formatter(fmt)
    which.set_major_locator(MaxNLocator(nbins=7, steps=[1, 2, 2.5, 5, 10]))


def thousands_axis(ax: Axes, axis: str = "y", prefix: str = "", decimals: int = 0) -> None:
    fmt = FuncFormatter(lambda v, _p: f"{prefix}{v:,.{decimals}f}")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def bp_axis(ax: Axes, axis: str = "y") -> None:
    fmt = FuncFormatter(lambda v, _p: f"{v:,.0f} bp")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def pct(x: float, decimals: int = 1) -> str:
    """0.0412 -> '4.1%'; negatives carry the typographic minus the tick labels use."""
    return f"{100.0 * x:.{decimals}f}%".replace("-", "−")


# ----------------------------------------------------------------------------
# Sorted bars.
# ----------------------------------------------------------------------------

def sorted_bars(ax: Axes, values: Mapping[str, float], highlight: Iterable[str] = (),
                horizontal: bool = True, ascending: bool = True) -> list[str]:
    """Bars sorted by value, the highlighted ones in the accent colour, the rest grey."""
    items = sorted(values.items(), key=lambda kv: kv[1], reverse=not ascending)
    names = [k for k, _ in items]
    vals = [v for _, v in items]
    hi = set(highlight)
    colors = [ACCENT if n in hi else GREY_LIGHT for n in names]
    if horizontal:
        ax.barh(names, vals, color=colors, height=0.7)
        ax.grid(False, axis="y")
        ax.grid(True, axis="x", color=GRID, linewidth=0.6)
        despine(ax, keep=("left",))
        ax.tick_params(axis="y", length=0)
    else:
        ax.bar(names, vals, color=colors, width=0.7)
        despine(ax, keep=("bottom",))
    return names


# ----------------------------------------------------------------------------
# The mechanical check and the export.
# ----------------------------------------------------------------------------

def check(fig: Figure) -> list[str]:
    """Failures against the mechanical part of the standard; empty means pass."""
    failures: list[str] = []
    gids = {t.get_gid() for t in fig.texts}
    if _TITLE_TAG not in gids:
        failures.append("no title block (use style.title: the title must state the finding)")
    if _SOURCE_TAG not in gids:
        failures.append("no source line (use style.source: data source, period, Qune Research, study id)")
    for i, ax in enumerate(fig.axes):
        if ax.spines["top"].get_visible() or ax.spines["right"].get_visible():
            failures.append(f"axes {i}: top or right spine visible")
        if ax.get_legend() is not None:
            failures.append(f"axes {i}: legend present; label the lines at their ends")
        if ax.get_title():
            failures.append(f"axes {i}: axes title set; the finding belongs in the figure title block")
        for line in ax.get_lines():
            if to_hex(line.get_color()).lower() in _DEFAULT_CYCLE:
                failures.append(f"axes {i}: a line uses matplotlib's default colour {to_hex(line.get_color())}")
                break
        for patch in ax.patches:
            fc = patch.get_facecolor()
            if isinstance(fc, tuple) and len(fc) == 4 and float(fc[3]) > 0 and to_hex(fc).lower() in _DEFAULT_CYCLE:
                failures.append(f"axes {i}: a bar or band uses matplotlib's default colour {to_hex(fc)}")
                break
        for gl in ax.get_xgridlines():
            if gl.get_visible() and gl.get_linewidth() > 0 and not _is_barh(ax):
                failures.append(f"axes {i}: vertical gridlines on a line chart")
                break
    if fig.get_frameon() and fig.patch.get_edgecolor() not in (
            (1.0, 1.0, 1.0, 1.0), (1.0, 1.0, 1.0, 0.0)) and fig.patch.get_linewidth() > 0:
        failures.append("figure border drawn")
    return failures


def _is_barh(ax: Axes) -> bool:
    return any(isinstance(p, Rectangle) and p.get_height() < p.get_width() for p in ax.patches)


def save(fig: Figure, stem: str | Path, strict: bool = True) -> tuple[Path, Path]:
    """Write ``stem.svg`` and ``stem.png`` (2x).  Refuses a figure that fails ``check``."""
    failures = check(fig)
    if failures and strict:
        raise ValueError("chart fails the house style: " + "; ".join(failures))
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    svg = stem.with_suffix(".svg")
    png = stem.with_suffix(".png")
    fig.savefig(svg, format="svg", metadata={"Date": None})
    fig.savefig(png, format="png", dpi=2 * BASE_DPI, metadata={"Software": None})
    return svg, png


CHECKLIST = """Chart review checklist (Tester). Return each failure with the exact fix.
1. Title states the finding in words a reader can act on; subtitle has units and period.
2. One message; one accent series, the rest grey; no default cycle, rainbow, 3D, shadow, gradient.
3. No top/right spines, faint horizontal grid only, no border, no legend when end labels work, bars sorted.
4. One sans-serif family, title 13-14 pt, labels 10 pt, left-aligned title, %/bp/$ consistent, thousands separators.
5. Source line bottom left: data source, sample period, Qune Research, study id. Shading only if it supports the message.
6. Built with qune_research.style; SVG and 2x PNG both committed; the script reads committed results only.
"""
