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
