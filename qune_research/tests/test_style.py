"""Tests for the house chart style: the mechanical part of the standard is enforced."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib import pyplot as plt

from qune_research import style


def _finished_figure():
    fig, ax = style.figure()
    x = np.arange(10)
    ax.plot(x, x * 0.01, color=style.ACCENT)
    ax.plot(x, x * 0.005, color=style.GREY)
    style.percent_axis(ax)
    style.label_line_ends(ax, [style.EndLabel("rule", 0.09, style.ACCENT),
                               style.EndLabel("benchmark", 0.045, style.GREY)])
    style.title(fig, "The rule doubled the benchmark", "Cumulative return, %, 2004-2018")
    style.source(fig, "vendor daily bars", "2004-01 to 2018-12", "Study 000")
    return fig, ax


def test_rc_params_never_use_the_default_cycle():
    style.apply()
    cycle = [c["color"].lower() for c in plt.rcParams["axes.prop_cycle"]]
    assert cycle[0] == style.ACCENT.lower()
    assert not set(cycle) & style._DEFAULT_CYCLE
    assert plt.rcParams["axes.spines.top"] is False
    assert plt.rcParams["axes.spines.right"] is False
    assert plt.rcParams["axes.grid.axis"] == "y"
    assert plt.rcParams["axes.titlelocation"] == "left"
    assert 13.0 <= plt.rcParams["axes.titlesize"] <= 14.0
    assert plt.rcParams["axes.labelsize"] == 10.0
    assert plt.rcParams["savefig.dpi"] == 2 * style.BASE_DPI


def test_finished_figure_passes_the_check():
    fig, _ = _finished_figure()
    assert style.check(fig) == []
    plt.close(fig)


def test_missing_title_and_source_are_reported():
    fig, ax = style.figure()
    ax.plot([0, 1], [0, 1], color=style.ACCENT)
    failures = style.check(fig)
    assert any("title" in f for f in failures)
    assert any("source" in f for f in failures)
    plt.close(fig)


def test_default_colour_legend_and_spines_are_reported():
    fig, ax = style.figure()
    ax.plot([0, 1], [0, 1], color="tab:blue", label="x")
    ax.legend()
    ax.spines["top"].set_visible(True)
    style.title(fig, "t", "s")
    style.source(fig, "a", "b", "c")
    failures = style.check(fig)
    assert any("default colour" in f for f in failures)
    assert any("legend" in f for f in failures)
    assert any("spine" in f for f in failures)
    plt.close(fig)


def test_save_writes_svg_and_2x_png_and_refuses_a_failing_figure(tmp_path):
    fig, _ = _finished_figure()
    svg, png = style.save(fig, tmp_path / "chart")
    assert svg.exists() and png.exists()
    assert svg.read_text()[:200].lstrip().startswith("<?xml")
    from matplotlib.image import imread
    img = imread(png)
    w_in, h_in = fig.get_size_inches()
    assert img.shape[1] == pytest.approx(w_in * 2 * style.BASE_DPI, abs=2)
    assert img.shape[0] == pytest.approx(h_in * 2 * style.BASE_DPI, abs=2)
    plt.close(fig)
    bad, ax = style.figure()
    ax.plot([0, 1], [0, 1], color=style.ACCENT)
    with pytest.raises(ValueError, match="house style"):
        style.save(bad, tmp_path / "bad")
    assert not (tmp_path / "bad.svg").exists()
    plt.close(bad)


def test_end_labels_are_pushed_apart():
    fig, ax = style.figure()
    ax.set_ylim(0, 1)
    ys = style.label_line_ends(ax, [style.EndLabel("a", 0.50, style.ACCENT),
                                    style.EndLabel("b", 0.51, style.GREY),
                                    style.EndLabel("c", 0.52, style.GREY_LIGHT)], min_gap=0.05)
    ordered = sorted(ys)
    assert all(b - a >= 0.05 - 1e-9 for a, b in zip(ordered, ordered[1:], strict=False))
    assert ys[0] < ys[1] < ys[2]
    assert max(ys) <= 1.0
    plt.close(fig)


def test_svg_output_is_byte_identical_run_to_run(tmp_path):
    style.apply()
    outputs = []
    for run in ("a", "b"):
        fig, _ = _finished_figure()
        svg, _png = style.save(fig, tmp_path / run / "chart")
        outputs.append(svg.read_bytes())
        plt.close(fig)
    assert outputs[0] == outputs[1]


def test_end_labels_on_a_log_axis_are_spaced_as_drawn():
    # Linear spacing put 520 at about 550 here: 0.014 apart on the drawn axis, so the labels touched.
    fig, ax = style.figure()
    ax.set_yscale("log")
    ax.set_ylim(1, 1000)
    ys = style.label_line_ends(ax, [style.EndLabel("a", 500.0, style.ACCENT),
                                    style.EndLabel("b", 520.0, style.GREY),
                                    style.EndLabel("c", 3.0, style.GREY_LIGHT)], min_gap=0.05)
    drawn = [ax.transAxes.inverted().transform(ax.transData.transform((0.5, y)))[1] for y in ys]
    assert ys[0] == pytest.approx(500.0) and ys[2] == pytest.approx(3.0)
    assert drawn[1] - drawn[0] == pytest.approx(0.05)
    assert max(drawn) <= 1.0
    plt.close(fig)


def test_sorted_bars_sort_and_highlight():
    fig, ax = style.figure()
    names = style.sorted_bars(ax, {"c": 3.0, "a": 1.0, "b": 2.0}, highlight=["b"])
    assert names == ["a", "b", "c"]
    colours = [p.get_facecolor() for p in ax.patches]
    from matplotlib.colors import to_hex
    assert to_hex(colours[1]).lower() == style.ACCENT.lower()
    assert to_hex(colours[0]).lower() == style.GREY_LIGHT.lower()
    style.title(fig, "t", "s")
    style.source(fig, "a", "b", "c")
    assert style.check(fig) == []
    plt.close(fig)


def test_percent_format_helper():
    assert style.pct(0.0412) == "4.1%"
    assert style.pct(-0.11091, 0) == "−11%"


def test_title_block_wraps_and_lowers_the_axes_top():
    fig, ax = style.figure()
    long = "A finding long enough to need two lines when it is set at thirteen and a half points across eight inches"
    top = style.title(fig, long, "Units, period")
    assert top < 0.80
    text = next(t for t in fig.texts if t.get_gid() == "qune-title")
    assert "\n" in text.get_text()
    plt.close(fig)


def test_house_font_is_installed_and_resolves_without_fallback(caplog):
    """The family is pinned to a font matplotlib ships, so no machine falls back."""
    from matplotlib import font_manager as fm

    assert len(style.FONT_FAMILY) == 1
    path = fm.findfont(fm.FontProperties(family=style.FONT_FAMILY), fallback_to_default=False)
    assert fm.FontProperties(fname=path).get_name() == style.FONT_FAMILY[0]
    style.apply()
    with caplog.at_level("WARNING", logger="matplotlib.font_manager"):
        fig, _ = _finished_figure()
        fig.canvas.draw()
        plt.close(fig)
    assert not [r for r in caplog.records if "findfont" in r.getMessage()]
