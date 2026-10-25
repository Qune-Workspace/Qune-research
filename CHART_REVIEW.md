# Chart review against the house standard (Tester, 2026-10-23)

Independent review of every published chart by a separate Tester agent session (Fable 5.1, isolated context, read-only, no network, no credentials) that did not write any of the chart code. Brief: the chart standard of 2026-10-23 and `qune_research.style.CHECKLIST`; 16 PNGs across Studies 001–004 and the desk view, every title number checked against the chart's manifest and the underlying results or numbers file. The reviewer's text is filed unedited below; the author's response follows it, dated.

## Reviewer's report (unedited)

Fable 5.1 (claude-fable-5-1). Repository reviewed at commit `73d7623494610f673a69b8a59030b1cd25e6a32a` (working tree clean; every `inputs_sha256` in all five manifests matches the committed file; all 16 PNGs are 1600 px wide, i.e. 2x, with an SVG beside each).

| Chart | Verdict | Failures and exact fix |
|---|---|---|
| research/004-xasset-trend-voltarget/charts/insample_drawdown_10assets.png | must-fix | (1) "the trough came in 2008" is true of B4 only; T1's deepest point is 2018-10-26 and is visible at the right edge, so the sentence misleads. Change the script's `finding` to "…from −7.8% to −6.8%; the matched book's trough came in 2008, the rule's in 2018" (add `int(dd["T1"].idxmin().year)` to the manifest). (3) Shade label "2008 crisis" sits on the lines at 0%. Fix: `ax.set_ylim(..., 0.012)` so the label has headroom, or anchor it at the band's bottom (`xy=(start, 0.0)`, `va="bottom"`). |
| research/004-xasset-trend-voltarget/charts/insample_growth_10assets.png | pass | Numbers and wording supported. |
| research/004-xasset-trend-voltarget/charts/oos_drawdown_10assets.png | must-fix | (1) "the trough came in 2022" is B4's; T1's −11.4% is 2020-03-19, the Covid spike, which the shaded 2022 band draws the eye away from. Same fix as in-sample: "…the matched book's trough came in 2022, the rule's in March 2020". (3) Shade label "2022" overlaps the lines at 0%; same headroom fix. |
| research/004-xasset-trend-voltarget/charts/oos_growth_10assets.png | should-fix | (4) Y-axis prints 1.4, 1.4, 1.3, 1.2, 1.2, 1.2, 1.1, 1.1: one-decimal formatter on 0.05 steps. Fix: `f"{v:,.2f}"` in the formatter, or `ax.yaxis.set_major_locator(MultipleLocator(0.1))`. Numbers supported. |
| research/003-bond-tsmom-ief/charts/insample_drawdown.png | pass | Numbers supported; shading (months in bills) supports the message. |
| research/003-bond-tsmom-ief/charts/insample_growth.png | pass | Numbers supported. |
| research/003-bond-tsmom-ief/charts/oos_drawdown.png | pass | "sitting in bills through 2023" supported (12 of 12 months BIL). |
| research/003-bond-tsmom-ief/charts/oos_growth.png | pass | Note (4): "(1.0% against −13.6%)" lacks the "+" that Studies 001/002 titles use for signed gaps; use `signed_pct`. Not a failure. |
| research/003-bond-tsmom-ief/charts/cash_check_by_year.png | pass | Gate ±0.30% and ex-ante 0.00 ± 0.20 are in PREREGISTRATION §5.3.3, so "written down beforehand" is supported. Unsorted bars explained in the source line. |
| research/001-slope-duration-switch/charts/validation_checks.png | pass | All seven title/subtitle numbers supported; "other four passed in both runs" true (A1, A2, B1, B2). |
| research/002-slope-duration-switch-r/charts/level_gap_by_year.png | should-fix | (3) The "mean −0.01%" label runs across the 2014 bar (+0.375%). Fix: place it below the line at the window's right end: `xytext=(-4, -5), va="top"` (2015's bar is only −0.06%, so the space is clear). Numbers supported. |
| research/002-slope-duration-switch-r/charts/tracking_error_vs_volatility.png | should-fix | (3) The "2013" label collides with the 2004 marker (points at 6.2%/1.51% and 6.5%/1.63%). Fix: for 2013 use `xytext=(-4, -10), ha="right"` (below-left), keeping the others as they are. Note (1): four-line title; dropping "set when volatility was 4.6%" (the point is already labelled) would bring it to three. Numbers supported (8 of 13 years above 1.5% recounted from the post-hoc table). |
| desk-view/charts/curve.png | pass | Note (4): the four "now" value labels (4.25 … 5.42) carry no % while the axis does; `f"{v:.2f}%"` would be consistent. |
| desk-view/charts/policy_vs_front_end.png | pass | +37 bp and +93 bp recomputed from numbers file (4.25−3.88, 4.81−3.88). |
| desk-view/charts/decomposition_10y.png | must-fix | (1) "+105 bp is real yield and only +2 bp breakeven" does not add to the stated 112 bp: the breakeven change is taken to 22 Oct 2026 (2.32) while nominal and real are to 21 Oct 2026. On the nominal's own date the raw file gives T10YIE 2.37 (21 Oct 2026) against 2.30 (23 Oct 2025), i.e. +7 bp, and 105 + 7 = 112. Fix: in `chart_decomposition` compute the breakeven change on `latest["DGS10"]["observed_on"]` (the numbers file's `decomposition_10y.breakeven_pct` already holds the 2.37), so the title reads "+105 bp is real yield and only +7 bp breakeven inflation"; the subtitle's "(breakeven to 22 Oct 2026 …)" clause then goes. The end label "breakeven 2.32%" can stay as the series' last print. |
| desk-view/charts/stock_bond_corr.png | must-fix | (1) "against 8% in 2016–2021": the correlation series starts 26 Jan 2017 (subtitle and source line say so), so `corr.loc["2016":"2021"]` contains no 2016 day. Fix: pass `before_label=f"in {corr.loc[:'2021'].index[0].year}–2021"` to `correlation_finding` (title becomes "in 2017–2021") and rename the manifest/numbers key accordingly, or extend the input so 2016 is actually covered. The 8% figure itself is correct for the days present. |

Summary
- Charts passed: 9 of 16
- Must-fix: 4 (004 in-sample drawdown, 004 OOS drawdown, desk-view decomposition, desk-view stock-bond correlation)
- Should-fix: 3 (004 OOS growth, 002 level gap, 002 tracking error)

Title numbers checked
- Study 004, `results/{insample,oos}/daily_index_10assets.csv` and `metrics_10assets_base.csv`, recomputed: max drawdowns T1/B4 −6.84/−7.77% and −11.39/−12.45%; B4 trough years 2008, 2022 (T1 troughs 2018, 2020); Sharpe 0.886/0.880 and 0.336/0.199; 2022 yearly returns −2.5%/−8.3%; end values 1.96/2.06/1.85 and 1.35/1.33/1.31. All matched the manifest and the chart; only the "trough" wording fails.
- Study 003, `monthly_base.csv`, `metrics_base.csv`, `summary.json`, `data_checks.json`, recomputed: monthly max drawdowns −8.60/−8.07% and −5.47/−22.24%; daily −10.4/−10.4% and −6.5/−23.9%; Sharpe 0.452/0.555 and 0.157/−0.259; switches 18, 10; 2022 yearly +1.03%/−13.56%; D2 mean +0.0366%, years outside ±0.2% = 2007–2009; end values 1.74/1.97/1.19 and 1.28/1.04/1.23. All matched.
- Study 001, both `validation.json`: A3 1.540%/1.145%, A4 +0.455%/+0.451%, limits 0.015 and ±0.004, 753 days, other checks pass. All matched.
- Study 002, `window1/window2/validation.json`, `posthoc_by_year.md`, Study 001 `validation.json`: means −0.0084%/+0.0999%, bands, Study 001 +0.451%; TE 2.02%/1.16%, ratios 0.21–0.37, window-2 ratio 0.29, IEF vol 4.6%, 8 of 13 years above 1.5%. All matched.
- Desk view, `numbers_2026-10-23.json` and raw FRED files: one-year changes 30/133/112/84 bp, yields 4.25/4.81/5.13/5.42, inversion flags, gaps +37/+93 bp, 112/+105/+2/+55 bp, 61%/8%/+0.41. All matched the manifest; the +2 bp and the "2016–2021" label match the numbers file but not the underlying data on consistent dates, as set out above.

## Author's response (Qune, 2026-10-23 07:4x)

Accepted in full: the four must-fix findings and the three should-fix findings are correct, and every one of the title numbers the reviewer recomputed matches the files the author used. Fixed in the commit that adds this file, with the PNGs inspected after re-rendering:

- **004 in-sample and out-of-sample drawdown (must-fix, item 1):** the trough sentence now names both books unless their trough years coincide: "the matched book's trough came in 2008, the rule's in October 2018" and "…in 2022, the rule's in March 2020"; the rule's trough date is in the manifest (`insample_T1_trough_date` 2018-10-26, `oos_T1_trough_date` 2020-03-19). The root README's alt text for the headline chart carries the corrected sentence. (Item 3) The y-axis top moved from 0.5% to 1.2% so the shade label sits above the 0% lines.
- **004 out-of-sample growth (should-fix, item 4):** the y-axis formatter prints two decimals (1.00, 1.05, …).
- **Desk view, 10-year decomposition (must-fix, item 1):** the breakeven change is now taken on the nominal's own date, from `decomposition_10y.breakeven_pct` (2.37% on 21 Oct 2026) against the same series a year earlier (2.30%), so the title reads "+105 bp is real yield and only +7 bp breakeven inflation" and 105 + 7 = 112; the subtitle's "breakeven to 22 Oct" clause is gone and the manifest records the date used. The view's own text, which says "2 bp" because it reads the breakeven row to 22 Oct as its table states, is unchanged and now carries a dated addendum pointing this out.
- **Desk view, stock-bond correlation (must-fix, item 1):** the "before" period is labelled from the series' first actual year, "2017–2021"; the manifest records the first day (26 Jan 2017). The share (8%) is unchanged. The numbers file's key keeps its name because the file is committed and quoted; the addendum in the view says what the period really is.

Open, for the next run (should-fix, Study 002): the "mean −0.01%" label across the 2014 bar in `level_gap_by_year.png` and the "2013" label on the 2004 marker in `tracking_error_vs_volatility.png`, with the reviewer's placements. Notes taken, not acted on today: the "+" on signed gaps in 003's out-of-sample growth title, the "%" on the curve chart's value labels, and the four-line title on 002's tracking-error chart.

*2026-10-23 08:1x, Qune:* the two Study 002 placements are done with the reviewer's offsets (commit e6ab986): the window-2 mean label sits below its line at the window's right end, the 2013 label below and to the left of its point; both PNGs re-rendered and inspected, the manifest's numbers and input hashes unchanged. The three notes stay as notes.

Nothing in `results/` was touched; no study was re-run; no verdict changed.


## Second review: the six tear-sheets (Tester, 2026-10-23 22:2x)

Separate Tester agent session (Fable 5.1, isolated, read-only, no network), brief `chart-review-tearsheets.md` adapted from the first; reviewed at commit `68b4181`. Report filed unedited below; the author's response follows it, dated.

### Reviewer's report (unedited)


Model: claude-fable-5-1 (Claude Fable 5.1). Reviewed qune-research at commit 68b4181 (tearsheets drawn at c901364, same files). Read-only; nothing re-run.
Recomputed from the monthly files with my own pandas: months, growth, annualised return, volatility, Sharpe (excess over B0, √12), max drawdown for all 24 series; all match the six JSONs to 1e-9 and every title number and verb is what the numbers say. The defect is in how rows are dated, not in the arithmetic.

| Sheet | Verdict | Failures (checklist no.) and exact fix |
|---|---|---|
| tearsheets/003_insample | must-fix | (1,4) Rows are indexed by `period_end`, the next period's execution date (first NYSE day of the following month), so every December holding period is booked to the next year: the year table shows "2003 (4 m)" and "2019 (1 m)" for a window the study calls 2003-08 to 2018-12 (5 periods in 2003, none in 2019); 2018 reads T1 -1.4 / B3 -0.6 where the holding-year figure is -0.7 / +1.7. Fix in `make_tearsheets.load_monthly`: index by the holding month, `pd.to_datetime(raw["execution_date"]).dt.to_period("M").dt.to_timestamp("M")`, and change the subtitle to "holding periods {sheet.period}" (then 2003-08 to 2018-12). Title numbers unchanged. (4, should) Title and tables use hyphen-minus "-8.6%" while the axes use "−8%": in `report.headline` and `report._fmt` replace "-" with "−" as `style.pct` does. (1, should) "lagged … 0.45 to 0.55" with Newey-West t 0.37 is fine; no wording change. |
| tearsheets/003_oos | must-fix | (1,4) Same dating defect: "2022" shows T1 +1.0 / B1 -13.6 / B3 -9.2, but the study README's calendar 2022 (periods executed in 2022) is +1.4 / -13.7 / -9.2, and "2019 (11 m)" / "2026 (10 m)" should be 12 and 9. Same fix. (4, should) hyphen-minus as above. (5, should) Source line wraps at the figure edge with no margin: last glyph at 1695 of 1700 px. Fix in `style.source`: drop `wrap=True` and write `"\n".join(_wrap(text, fig, SOURCE_SIZE, x))` so it wraps at 97% like the title. |
| tearsheets/004_insample | must-fix | (1,4) Same dating defect: "2004 (11 m)" and "2019 (1 m)" for 180 periods that are exactly 15 holding-years 2004–2018. Same fix. (1, should) "beat … 0.89 to 0.88" (gap 0.005, t 0.65) contradicts the study's own reading ("added nothing measurable"): in `report.headline` use "matched" when the Sharpe gap is below 0.05 and append "; Newey-West t {t:.2f}" so the reader can act on it. (4, should) hyphen-minus. |
| tearsheets/004_oos | must-fix | (1,4) Same dating defect ("2019 (11 m)", "2026 (10 m)"; holding-years are 12 and 9). Same fix. (4, should) hyphen-minus. (5, should) source line ends 53 px from the edge, acceptable; same `style.source` fix applies globally. |
| tearsheets/005_insample | must-fix | (1,4) Same dating defect ("2003 (4 m)", "2019 (1 m)"). Same fix. (1, should) "beat … 0.47 to 0.45" (t 0.51): same `headline` wording fix as 004_insample. (4, should) hyphen-minus. (5, should) source line ends 10 px from the edge. |
| tearsheets/005_episode | must-fix | (1,4) Same dating defect: "2022" shows T1 -9.4 / B2 +1.0 / B1 -13.6 where the study README states -7.6 / +1.4 / -13.7 for calendar 2022; a reader comparing sheet and note sees a contradiction. Same fix. (4, should) hyphen-minus. Titles, labels and end labels otherwise correct and readable. |

Checks that passed on all six: one accent + greys, no default cycle, no top/right spines, horizontal grid only, no legend, end labels do not overlap (nearest pair, 003_insample T1/B3, is clear), one font family (resolved to DejaVu Sans as fallback), left-aligned 13.5 pt title, source line present, SVG + 2x PNG committed, script reads committed results only, 120/120 self-check comparisons confirmed.

(a) Clipping: nothing is clipped on any sheet. Rendered source-line ink ends at 1692 / 1695 / 1603 / 1647 / 1690 / 1646 px of 1700 (003_insample, 003_oos, 004_insample, 004_oos, 005_insample, 005_episode); subtitles end at or below 90% and titles at or below 91% of width. matplotlib's `wrap=True` wraps at the figure edge, so 003_oos legitimately runs to 5 px from the edge; the `style.source` fix above gives it the same 3% margin as the title block.

(b) Labels: all three studies date rows by signal month (`month` / `signal_date`) and describe windows by holding month (READMEs: "2003-08 to 2018-12", "2019-01 to 2026-09", "2004-01 to 2018-12"). `period_end` is the next period's execution date, so "periods ending 2003-09 to 2019-01" is literally true of that column but names the wrong month for every row except 004_oos's last, which ends at the 2026-09-30 end bar (hence 004 "2026-09" against 003/005 "2026-10" for the same 93 holding periods, confirmed in 004 README §16). "Periods ending" is the right word for the column; the right label is "holding periods 2019-01 to 2026-09" for both, which the fix above produces.

Summary: passed 0 / must-fix 6 / should-fix 0 (the should-fix items ride on the must-fix sheets).
One root cause (row dating by `period_end`) accounts for every must-fix; the recompute confirms every title number, so after the index change the titles will not move.

### Author's response (Qune, 2026-10-23 22:5x)

Accepted in full. The reviewer's recompute of all 24 series matched the sheets to 1e-9, and the one root cause is real: the first version of `tools/make_tearsheets.py` indexed the rows by `period_end`, the next period's execution date, so every December holding period was booked to the following year and each window showed partial years at both ends. Confirmed before fixing by a three-way recompute of calendar 2022 from Study 003's out-of-sample file: by signal month T1 +1.7% / B1 −9.5%, by execution year +1.4% / −13.7%, by period-end year +1.0% / −13.6%; Study 005's note uses the execution year, Study 003's own charts the period-end year. Fixed in the commit that adds this section:

- **Row dating (must-fix on all six):** rows are indexed by the month of the execution date (`load_monthly`), the subtitle says "holding periods … each from one execution date to the next", and the year tables now show twelve months in every full year (003 in-sample: 2003 with 5 months to 2018; the 2019–2026 windows: 2019 to 2026 with 9). Titles and the metrics table did not move; the script's 120 checks against the committed metrics files still pass. The `tearsheets/README.md` records the convention and discloses that Study 003's charts group years by period end, which is why its calendar-2022 figures differ from the sheet's.
- **"beat" on a Sharpe gap of 0.005 (should-fix, 004 in-sample and 005 in-sample):** `report.headline` says "matched" when the absolute Sharpe gap is below 0.05 (`MATCHED_SHARPE_GAP`) and quotes the Newey-West t of the monthly gap in every title, so the 004 in-sample sheet reads "matched … 0.89 to 0.88 (Newey-West t 0.65)" and 003 out of sample "beat … (Newey-West t 1.31)".
- **Hyphen-minus (should-fix):** every number in the title, the tables and the drawdown label uses the typographic minus, as the axes do; labels such as "Newey-West" keep their hyphen.
- **Source line at the edge (should-fix):** `style.source` wraps at the title block's right margin instead of the figure edge, which also moves every other chart's source line inside the same margin when it is next re-rendered (none was re-rendered today; their PNGs are unchanged).

Tests: four added or extended in the library suite (the "matched" branch, the t in the headline, the typographic minus, the source wrap), 121 pass; ruff and mypy clean. Nothing in `results/` was touched; no study was re-run; no verdict changed.

### Note on SVG text (Qune, 2026-10-24; follows the house-font pin of 2026-10-23)

The charts are exported with `svg.fonttype = "none"`: the text in every SVG stays text, selectable and searchable, and the files are small. The cost is that a viewer without DejaVu Sans installed draws its own sans-serif at slightly different metrics, so an end-label or the wrapped source line can sit a few pixels from where matplotlib placed it; nothing overlaps in the PNG, which is laid out and rasterised with the pinned font and is the reference rendering of every chart. The alternative, `svg.fonttype = "path"`, would freeze the glyphs as outlines (identical look everywhere, no selectable text, files several times larger). Decided: keep text, since the PNG is the record and the SVG exists so that a reader can inspect and reuse the figure. Revisit if the 2026-10-26 cold read reports a misplaced label in an SVG. No chart re-rendered for this note.

*2026-10-24 09:20, Qune:* the "Author's response" heading above reads 07:4x; the commit that added it together with this file is `618c209`, committed 07:30:48 London, so the label is some ten minutes late and is left as written (the same label in `desk-view/DESK_VIEW.md`'s second addendum carries the same note). The 08:1x note sits between the commit it cites, `e6ab986` (08:16:58), and the commit that carries it, `b9ad02e` (08:21:56), and holds. The review's desk-view recomputation line was read again against `desk-view/data/numbers_2026-10-23.json` and both manifests: all matched. Nothing re-run.

## Third review: Study 006 charts (Tester, 2026-10-25 05:1x–05:2x GMT)

Brief: chart standard of 2026-10-23, the four §9.6 charts of Study 006 as committed in `b868f5d`. Reviewer: a separate Tester agent on Opus 5.5 (Fable's weekly allowance used up), isolated, read-only, about 3 minutes.

### Reviewer's report (unedited)

#### Chart review 006 (Tester, Opus, 2026-10-25). Read-only; input hashes match the manifest; 4 SVG + 4 PNG (1600 px wide = 2x) committed.

| Chart | Verdict | Failures and exact fix |
|---|---|---|
| charts/history_spread_and_holdings.png | should-fix | (1,2) Title runs 3 lines with "bond" alone on the last, carries two messages, and "never left the bond" reads as permanent although the curve inverted again after 2018. Change to "The curve inverted at 77 of 593 month ends, 54 of them before 1982; from September 2007 to December 2018 the rule held the bond" (or drop the second clause). (5) The bill shading (SHADE #F1F1F1) is too faint to see for the 1989, 2000–01 and 2006–07 bill months, which are half the message. In `shade_bills`, use `color=style.GREY_FAINT`. |
| charts/history_growth.png | must-fix | (1) "beat holding the bond" is stronger than the INCONCLUSIVE (FRAGILE) verdict (T2 and T3 fail C2). Retitle to "Over 1969–2018 the spread switch had the higher Sharpe, 0.46 against 0.34 for holding the bond and for the same-exposure mix; the result is fragile". This also removes the clumsy "0.34, and 0.34". In code, replace `verb` "beat" with "had the higher Sharpe" and add the fragile clause. (3) The "B1 32.7" and "B3 28.7" end labels touch: `style.label_line_ends` spaces labels in linear data fractions on a log axis. In style.py compute `frac` in axes coordinates, `ax.transLimits.transform(ax.transScale.transform((0, y)))[1]`; until then use `min_gap=0.2`. (4) The log axis labels only 1 and 10. Add `ax.yaxis.set_major_locator(FixedLocator([1, 2, 5, 10, 20, 50]))`. |
| charts/history_drawdown.png | must-fix | (1,2) The title credits the switch with the whole drop from −15.2% to −9.8% against B1, but part of that drop is lower average exposure. Against the pre-registered same-exposure mix the cut is −12.4% to −9.8% (21%, not 36%). B3 is also missing from the plot although PREREGISTRATION §9.6 asks for "T1 against B1 and B3, growth and drawdown". Retitle to "The switch's deepest monthly drawdown was −9.8%, against −12.4% for the same-exposure mix and −15.2% for holding the bond", and plot B3 as a `style.GREY` line with an end label. (1) "bottomed in March 1980" is the 1980-03-03 settlement mark of the February 1980 holding period (executed 1980-02-01). Say "February 1980", or drop the clause. (3) The B1 label is nudged by `−0.03` and sits at −6.3%, while B1 and T1 both end at −3.3%; it is also in GREY_DARK while the area is GREY_LIGHT. Remove the nudge and annotate the B1 area at its trough ("Hold the bond (B1), −15.2%"). |
| charts/history_differential_by_decade.png | must-fix | (1,2) "came from 1969–79" is not supported. 1969–79 is +1.9% a year (45% of the summed edge) and the 1980s +1.7% (39%); 1969–89 together carry 84%. The README itself says "sits in 1969–1989". Retitle to "The switch's edge over the same-exposure mix came from 1969–89, +1.9% and +1.7% a year; in the 2000s, the only later decade with bill months, it was −0.1%". Accent both the 1969–79 and 1980s bars (e.g. highlight every timing decade with a mean ≥ 0.5 × the maximum). (2) The 1990s and 2010–18 bars are an exposure gap, not timing, but they share the grey of the 1980s timing bar. Draw them in `style.GREY_FAINT` with `hatch="//"`, plus an in-plot note "no bill month: exposure gap only". |

Title and subtitle numbers checked (manifest = my own pandas on monthly_base.csv / metrics_base.csv unless noted):
- 593 month ends: 593 rows. 77 inverted: 77 with spread < 0 (no exact zeros; the 77 match the T1_holding = BIL rows one to one). 54 before 1982: 54 (same by signal month or by execution year).
- Last inverted execution 2007-08-01: yes. No bill month after it to the end (2019-01-02 period end).
- Sharpe (excess over B0, ddof 1, ×√12): T1 0.4633, B1 0.3384, B3 0.3382. These match metrics_base.csv and round to 0.46 / 0.34 / 0.34.
- Final growth: T1 44.414, B1 32.730, B3 28.657 (labels 44.4 / 32.7 / 28.7). Yes.
- Max monthly drawdown: T1 −9.757% (1987-10-01), B1 −15.152% (1980-03-03), B3 −12.361% (1980-03-03). Title −15.2% / −9.8% and note −12.4%: yes. Cut vs B1 35.6%; vs B3 21.1% (not shown).
- Decade means of T1 − B3 ×12: 1969–79 +1.944% (125 mo, 38 bill), 1980s +1.742% (120, 21), 1990s +0.368% (120, 0), 2000s −0.105% (120, 18), 2010–18 +0.484% (108, 0). Labels +1.9 / +1.7 / +0.4 / −0.1 / +0.5 and counts: yes. "Never held bills" in the 1990s and 2010–18: yes.
- "2 bp per side": summary.json cost_per_side 0.0002 (base). Period Aug 1969 to Dec 2018: first execution 1969-08-01, last period end 2019-01-02.

Every title number matches the manifest and the results files. The failures are wording and fairness: the numbers are right, two phrases ("beat", "came from 1969–79") and one comparison (drawdown vs B1 only) overstate the result.

Charts passed: 0
Must-fix: 3 (growth, drawdown, differential by decade)
Should-fix: 1 (spread and holdings)

### Author's response (Qune, 2026-10-25 05:2x GMT; British clocks went back at 02:00 BST today, so London time equals UTC from here on)

Accepted in full: no chart passed. Every title number the reviewer recomputed agrees with mine and with `charts/manifest.json` (nothing in the results moved); the faults were in what the words claimed. Fixed in `charts/make_charts.py`, all four charts re-rendered from the same committed files (input hashes unchanged), and checked by eye at 2x:

- **Growth (must-fix):** "beat" read as a stronger claim than the verdict. The title now says the switch "had the higher Sharpe, 0.46 against 0.34 for holding the bond and for the same-exposure mix; the verdict is inconclusive (fragile)". The end labels touched because the house helper spaces labels in linear units, which on a log axis lets close lines collide; a local `log_end_labels` applies the same rule in log space (the shared helper is unchanged, so no other chart moves). Log ticks fixed at 1, 2, 5, 10, 20, 50.
- **Drawdown (must-fix):** the title quoted a cut measured against holding the bond only (36%; against the same-exposure mix it is 21%). It now states all three depths, −9.8% / −12.4% / −15.2%, and the same-exposure mix is drawn as a grey line, as the pre-registration asks. "Bottomed in March 1980" named a period-end mark; the source line now names the holding period by its execution month (February 1980), the convention of the tear-sheets. The −0.03 nudge on the bond's label is gone (both T1 and B1 end at −3.3%).
- **Decade (must-fix):** "came from 1969–79" was not supported: that decade holds 45% of the summed edge and the 1980s 39%. The title now names every decade with bill months and a positive edge, "1969–89, +1.9% and +1.7% a year; in the 2000s, the only later decade with bill months, it was −0.1%"; both early bars carry the accent; the two exposure-only decades are pale, hatched and labelled "no bill month: exposure only" in the plot. Shares of the summed edge are in the manifest.
- **Spread (should-fix):** "never left the bond" read as permanent; the title now bounds the stretch by the window ("from September 2007 to December 2018 the rule held the bond"). The bill shading is one step darker (`GREY_FAINT`) on both shaded charts, so the 1989, 2000–01 and 2006–07 spells are visible.

Nothing in `results/` was touched; no study was re-run; no verdict changed. Not done: the reviewer did not see the re-rendered charts; the fixes are checked by the author only.

## Fourth review: Study 007 charts (Tester, 2026-10-25, between the 13:28 push and 13:32 GMT)

Brief: chart standard of 2026-10-23, the five §9.6 charts of Study 007 as committed in `9d2d317` (time labels `91367d8`). Reviewer: a separate Tester agent on Opus 5.5 (the owner's instruction of 2026-10-25: no Fable), isolated, read-only, 166 s by the harness; it recomputed every title number with its own code from the three committed inputs.

### Reviewer's report (unedited)

**Study 007 chart check: FAIL (1 must-fix)**

I looked at all five PNGs, read `make_charts.py` and `style.py`, and recomputed every title number with my own code from the three committed inputs, without importing `make_charts.py`. The input hashes in `manifest.json` match the committed files. All five charts use one font (DejaVu Sans), with the title at 13.5 pt and labels at 10 pt. Each has an SVG and a 2x PNG, and all ten files are committed. The period convention (rows dated by execution month, first holding period executed Jul 1974, last Dec 2018) is applied consistently. Running the windows by signal month instead would change the numbers, so the subtitle wording "by execution month" is correct and needed.

**1. history_carry_and_weight: PASS**
- note: carry is plotted at `execution_date`, not at the month-end signal date the subtitle names. That is a one-day shift and is not visible.
- note: the chart has two panels, but they make one point (how the rule positions itself), so it is acceptable.

**2. history_growth**
- should-fix: "had the higher Sharpe" reads close to "beat", and the title gives no measure of noise. The house `report.headline` rule quotes a test statistic so the reader can weigh the verb. The study's own test of T1's Sharpe against B3 gives p = 0.15. The title also runs to four lines. Fix, as the title string: "Over 1974–2018 the carry tilt's Sharpe was 0.49 against 0.38 for the bond and the same-exposure mix (p = 0.15), but it ended below the bond; verdict inconclusive (fragile)".
- note: minor tick marks show on the log y-axis. Fix: `ax.tick_params(axis="y", which="minor", length=0)`.

**3. history_drawdown: PASS**
- The footnote "bottomed with the February 1980 holding period" is correct: the trough is the period executed 1980-02-01 and ending 1980-03-03, signal month 1980-01. B3 also bottoms in that period.

**4. history_differential_by_decade**
- should-fix: "positive in every decade" reads as a consistent edge, yet no single decade is significant (t ranges from 0.37 in the 2000s to 1.90 in 2010–18). Fix: add to the title "; none alone significant (t 0.4 to 1.9)".
- should-fix: there are two baselines. The 0% `axhline` sits just above the bottom spine at −0.1%. Fix: set the y-axis floor to 0 when every bar is positive (`ax.set_ylim(0, …)`), or call `despine(ax, keep=())` and keep the `axhline`.
- note: the bar value labels are 9 pt; set them to `style.LABEL_SIZE` (10 pt).

**5. history_trials_by_window**
- **must-fix:** "adding trend raised it in 1974–81 and 1982–2008" overstates the result. The 1982–2008 gap is 0.05 percentage points a year (+0.62% for T2 against +0.58% for T1, t 1.32 against 1.18), which is noise. The README's attribution section concludes that trend adds nothing (+0.86% against +0.85% a year, both t 2.10). The script calls any positive difference "raised", with no noise threshold. Fix: replace the tail of the title with "adding trend changed little over the whole window (+0.86% against +0.85% a year, both t 2.10)". In the code, build that tail from `summary["cost_cases"]["base"]["attribution"]`, or apply a threshold the way `MATCHED_SHARPE_GAP` does.
- should-fix: "all five windows" counts every month twice, because the two sub-windows and the three rate eras are two different splits of the same 534 months. Fix: "in both registered sub-windows and all three rate eras".
- should-fix: the x-axis gives no visual cue that the two splits are separate. Fix: insert an empty slot or a faint vertical separator between group 2 and group 3, with small group captions "Registered sub-windows" and "Rate eras".
- should-fix: the chart carries two messages (carry against the mix, and the trend increment), and T3 is shown but never mentioned in the title. If the trend tail is replaced as above, T3 can stay as context.
- should-fix: the same double baseline as chart 4. The fix is the same.
- note: the T1, T2 and T3 labels are the only series key and are 9 pt; set them to 10 pt.

Title numbers: 22 values recomputed (carry 131 / 534 / 119 / 61; growth Sharpe 0.49296 / 0.38179 / 0.38139, end values 23.643 / 25.570 / 16.499, w 0.6056; drawdown −7.555% / −6.475% / −15.152%, trough period executed 1980-02; decade +0.289% / +1.498%, all five positive, 66 / 120 / 120 / 120 / 108 months; windows T1 positive in all five, highest t 1.9146, T2 > T1 in 1974–81 (2.13 vs 1.72) and 1982–2008 (0.62 vs 0.58, noise), T2 < T1 in 2009–18 (0.57 vs 0.92)): every one matches. "Every number in a title is arithmetically correct. The failures are in wording and layout, not in the data."

**Overall verdict: FAIL (1 must-fix)**, plus 8 should-fix items.

*(The reviewer's title-number table is given above as one paragraph with the same values; nothing in it was changed.)*

### Author's response (Qune, 2026-10-25 13:3x GMT)

All findings fixed in `charts/make_charts.py` and redrawn; checked by eye; no result file touched, nothing re-run, no verdict changed.
- **Window chart (must-fix):** the trend clause is now built from the whole-window attribution rows in `summary.json` ("over the whole window adding trend changed little (+0.86% against +0.85% a year, both t 2.10)"), with "changed little" below a 0.1-point-a-year gap fixed in the script (`TREND_LITTLE`, written to the manifest). "All five windows" is now "both registered sub-windows and all three rate eras"; a gap, a faint separator and the two group captions split the axis; one baseline; series keys at 10 pt.
- **Growth (should-fix):** title now "the carry tilt's Sharpe was 0.49 against 0.38 for the bond and the same-exposure mix (p = 0.15), but it ended below the bond; verdict inconclusive (fragile)", p from the study's own Ledoit–Wolf test against B3; minor ticks removed.
- **Decade (should-fix):** "; none alone significant (t 0.4 to 1.9)" added, the t-statistics computed with the study's own Newey–West function (6 lags) and written to the manifest; one baseline; bar labels at 10 pt.
- Notes on chart 1 (signal vs execution date, one day) accepted as they are.

Not done: the reviewer did not see the re-rendered charts; the fixes are checked by the author only.


## Fifth review: Study 008 charts (Tester, 2026-10-25, after the 22:20:04Z push of e4f3e41)

Brief: chart standard of 2026-10-23, the five §9.6 charts of Study 008 as committed in `e4f3e41`, with three questions from the author (the window chart's key, the decade title naming the one decade with |t| ≥ 2, the window title quoting a descriptive sub-window t). Reviewer: a separate Tester agent on Opus 5.5, isolated, read-only, 221 s by the harness; it recomputed every title number with its own code from the three committed inputs (its script in /tmp, not committed).

### Reviewer's report (unedited)

**Study 008 chart check: no must-fix, 4 charts with should-fix.** Read-only. The input hashes in the manifest match the committed files (sha256 e54e9c59…, da5ce721…, ae688e34…). I viewed all five PNGs (all 2x, 1600 px or 1720 px wide) and read `make_charts.py` and `style.py`. Every title and subtitle number was recomputed with my own code (`/tmp/tester008/recompute.py`), which uses its own Bartlett Newey–West at 6 lags and does not import the study or chart code. Each number matches both the manifest and the results files.

| Chart | Verdict | Failures and exact fix |
|---|---|---|
| charts/history_real_yield_and_weight.png | should-fix | **1/2:** the title lists two counts (weight, real yield) rather than one finding. Fix: change the title to "The value tilt held 0.9 or more of the bond only between May 1981 and May 1985, when the real yield peaked at 9.6%, and less than 0.3 in 186 of 534 months, 144 of them from 2000". Add `weight_ge_0_9_span`, `real_yield_max` and `weight_lt_0_3_from_2000` = 144 to the manifest. |
| charts/history_growth.png | pass | Note: the source line says "Ledoit–Wolf test vs B3", but the title puts p next to both benchmarks. That happens to hold, because p vs B1 is 0.6985, which also rounds to 0.70. Add `growth_ledoit_wolf_p_vs_B1` = 0.6985 to the manifest so the shared "(p = 0.70)" is backed by a recorded number. |
| charts/history_drawdown.png | should-fix | **1:** the title gives three numbers but not the comparison that matters: the tilt fell further than the mix it is tested against. "Deepest monthly drawdown" can also be read as the worst single month. Fix: change the title to "The tilt's deepest drawdown was −6.3%, deeper than the same-exposure mix's −3.8% but less than half the bond's −15.2% (month-end marks)". |
| charts/history_differential_by_decade.png | should-fix | **1:** "positive in 3 of 5 decades (−0.9% … to +2.6%)" puts a negative range after "positive", and "only … alone significant" is redundant and gives a descriptive t inferential weight (see b). The positive-to-negative split falls exactly at 2000. Fix: change the title to "The tilt's edge over the same-exposure mix was positive in the three decades to 1999 (+0.7% to +2.6% a year) and negative in the 2000s and 2010–18 (−0.5% and −0.9%); descriptive t −1.5 to 2.2". In code, replace the `count`/`qual` branch for mixed signs. |
| charts/history_trials_by_window.png | should-fix | **1:** the subtitle has no period. Fix: append ", Jul 1974 to Dec 2018 (T1b from Jul 1979)". **1:** the title quotes descriptive t's but not the decision t (see c). Fix: change the title to "The value tilt was ahead of the same-exposure mix before 2003 (+1.36% a year) and behind it over 2003–18 (−0.85%), as were T1a and T1b; over the whole period not supported (t 1.38)", with the t taken from `inference.T1.vs_B3.newey_west.t` into the manifest. **3:** the key sits under the "Rate eras" heading, so it reads as that group's key, and its last line runs past the plot's right edge. Fix: drop the key and label the three bars of the first cluster directly ("T1", "T1a", "T1b", 10 pt, above each bar). The subtitle already gives the full names. |

**(a)** Acceptable under checklist 3. The rule is "no legend when end labels work", and they do not work for clustered bars. The placement is the problem, not the key itself: it is inside the second group. The fix is in the table: direct labels on the first cluster, or move the key above both group captions.

**(b)** The title is numerically correct: the 1990s t is 2.161, or 2.152 with an n/(n−1) correction, the only |t| ≥ 2, and the 1980s t is 1.837. It is not clear, though. Naming a "significant" decade on a statistic the subtitle calls "no decision weight", one of five looks, puts the reader's eye on the smallest positive bar and on inference. The clear and fair message is the sign change at 2000, which also matches the failed 1986–2018 era row. Use the t range, not a significance label (fix above).

**(c)** It does not read as a claim that the tilt works, because it is paired with the reversal (t −1.81) and the split at 2003 is registered. Still, t 2.47 is the largest |t| on the figure, and it is the only inference in the title, while the decision statistic (t 1.38) and the verdict are absent. A reader sees a significant edge that later broke, which is a regime story the study did not test. My own split shows 1986-01 to 2002-12 at +0.69% a year, t 2.07 (204 periods), so the edge before 2003 is not only a 1974–85 effect. Should-fix: drop the sub-window t's and add the whole-period t 1.38 and "not supported" (fix above).

**Numbers checked (recomputed = manifest = results):**
- Real yield: 534 month ends. Real yield ≤ 0 at 76 (< 0 also 76). Weight ≥ 0.9 in 48 (May 1981 to May 1985). Weight < 0.3 in 186 (42 before 2000, 144 from 2000). w̄ 0.466176, sd 0.270051 (ddof 0). Real yield min −4.808%, max 9.606% (signal month 1984-06).
- Growth: Sharpe T1 0.414619, B1 0.381794, B3 0.381244 (excess over B0, ddof 1, ×√12; matches metrics_base and summary descriptive). Final values 17.604 / 25.570 / 13.995. B3 weight 0.466176. Ledoit–Wolf p vs B3 0.7004 (vs B1 0.6985). Whole-period NW t vs B3 1.381.
- Drawdown: T1 −6.290%, B3 −3.828%, B1 −15.152% (= metrics max_drawdown_monthly). Troughs: T1 in the period executed 1987-09, B3 and B1 in the period executed 1980-02.
- Decades (T1 − B3_T1, annualised mean / NW t / n): 1974–79 +0.875% / 1.286 / 66; 1980s +2.582% / 1.837 / 120; 1990s +0.721% / 2.161 / 120; 2000s −0.454% / −0.813 / 120; 2010–18 −0.910% / −1.511 / 108. The 1990s is the only |t| ≥ 2. The t range in the subtitle is −1.5 to 2.2. Era row 1986–2018: −0.0554% a year, t −0.184, 396 periods, fail.
- Windows: all 18 trial × window means, t's and n's, recomputed from monthly_base by execution month, equal summary.json and the manifest (e.g. T1 before 2003 +1.357% / t 2.467 / 342; 2003–18 −0.848% / −1.806 / 192). T1a and T1b have the same signs in both (+1.333 / −0.381 and +1.186 / −0.664). T1b n = 282 / 78 / 30 as in the footnote.

Layout checks pass on all five: one accent series with greys; no top or right spines and one baseline; faint horizontal grid; title 13.5 pt and labels 10 pt in one family, left-aligned; source line at the bottom left with source, period, Qune Research, Study 008 and the verdict; unsorted bars state why; SVG and 2x PNG committed.

Charts passed: 1 (growth)
Must-fix: 0
Should-fix: 4 charts (real yield, drawdown, decade, window; 6 items)

### Author's response (Qune, commit c2d4164, 22:26:23Z by git)

Before accepting, Qune recomputed the three numbers the reviewer proposed for titles from `monthly_base.csv` (weight ≥ 0.9 in 48 months, all between the periods executed 1981-05 and 1985-05; real-yield maximum 9.61% in the period executed 1984-07, inside that span; weight < 0.3 in 186 months, 144 of them from 2000). All six should-fix items answered in `charts/make_charts.py` and redrawn; every phrase is chosen by the script from computed numbers; no result file touched, nothing re-run, no verdict changed.
- **Real yield and weight:** title now one finding, "The value tilt held 0.9 or more of the bond only between May 1981 and May 1985, when the real yield peaked at 9.6%, and less than 0.3 in 186 of 534 months, 144 of them from 2000"; the peak clause is printed only if the peak falls inside the span; the count of month ends with a real yield at or below zero (76) moved to the source note; span, peak month and the 144 written to the manifest.
- **Drawdown:** "The tilt's deepest drawdown was −6.3%, deeper than the same-exposure mix's −3.8% but less than half the bond's −15.2% (month-end marks)"; both comparisons chosen by code.
- **Decade:** the title states the sign change, "positive in the three decades to 1999 (+0.7% to +2.6% a year) and negative in the 2000s and 2010–18 (−0.5% and −0.9%)", used only when the positive decades all precede the negative ones (otherwise the earlier count form); the Newey–West t range (−1.5 to 2.2) moved to the subtitle with "Descriptive, no decision weight". The reviewer's extra figure for 1986–2002 (+0.69% a year, t 2.07) is not a registered window and is not used.
- **Window:** sub-window t's dropped from the title and the whole-period Newey–West t against B3 added from `summary.json`: "…before 2003 (+1.36% a year) and behind it over 2003–18 (−0.85%), T1a and T1b alike; whole period not supported (t 1.38)"; period added to the subtitle. The key was **not** replaced by direct labels on the first group as the reviewer proposed: drawn that way in the first version, "T1", "T1a" and "T1b" overlap at 10 pt over bars about 19 pt wide. Following the reviewer's answer (a), the key moved instead from under the "Rate eras" heading to one row under the axis spanning both groups, with shorter names (the subtitle carries the rank types).
- **Growth (note):** the Ledoit–Wolf p against B1 (0.6985) is now in the manifest beside the one against B3.

Not done: the reviewer did not see the re-rendered charts; the fixes are checked by the author only.
