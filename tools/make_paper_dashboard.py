"""Paper dashboard for Studies 003 to 008, 010 and 011 from their committed paper-log folders.

Descriptive only.  This script reads each study's ``paper-log/`` exactly as
committed (decision records, shadow lines, execution records, runner and
stop-check lines; Studies 010 and 011: monthly position files and the last
fetch-log line), compounds the shadow lines into one equity path per
series with ``qune_research.paperlog`` and writes ``dashboard/README.md``,
one chart per study that has at least one shadow line (SVG + 2x PNG, house
style) and ``dashboard/manifest.json`` with the SHA-256 of every input and
output and the generation time.  It fetches nothing, runs no strategy code,
writes nothing into any study folder and carries no decision weight.  A
record that is not on disk is reported as absent, never estimated; the page
is regenerated after each forward record and never by hand.

Run from the repository root:  .venv/bin/python tools/make_paper_dashboard.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qune_research import paperlog  # noqa: E402

OUT = ROOT / "dashboard"

# One entry per published study with a forward record.  Series ids, labels,
# book sizes and columns are the ones each study's PREREGISTRATION.md §11 and
# its forward code define; nothing here changes how a record is written.
SPECS = [
    paperlog.LogSpec(
        study="Study 003", folder="research/003-bond-tsmom-ief", kind="paper sleeve",
        label="not supported; paper record of a not-supported rule; orders only once Independent Risk clears the sleeve",
        first_signal_date="2026-10-30",
        strategy="T1", benchmarks=("B3", "B1", "B0"), shadow_file="summary.csv",
        return_columns={"T1": "rule_return", "B3": "B3", "B1": "B1", "B0": "B0"},
        labels={"T1": "Trend rule T1", "B3": "Same-exposure mix B3", "B1": "Hold IEF B1", "B0": "Bills B0"},
        data_source="Alpaca daily IEF and BIL bars (adjustment='all') read by paper/summarise.py",
        chart_note="Rule at official closes, net of 2 bp per side; the sleeve's own fills are in summary.csv",
    ),
    paperlog.LogSpec(
        study="Study 004", folder="research/004-xasset-trend-voltarget", kind="shadow record",
        label="not supported; no paper order", first_signal_date="2026-10-30",
        strategy="T1", benchmarks=("B4", "B3"),
        book_columns={"T1": "T1_book", "B4": "B4_book", "B3": "B3_book"}, book_usd=10_000.0,
        labels={"T1": "Trend T1", "B4": "Vol-scaled long-only B4", "B3": "Equal weight B3"},
        data_source="Alpaca daily bars (adjustment='all') read by the study's forward code; ten ETFs and BIL",
    ),
    paperlog.LogSpec(
        study="Study 005", folder="research/005-duration-trend-regime", kind="shadow record",
        label="refuted in-sample; no paper order", first_signal_date="2026-10-30",
        strategy="T1", benchmarks=("B2", "B1"),
        return_columns={"T1": "T1", "B2": "B2", "B1": "B1"},
        labels={"T1": "Conditional exit T1", "B2": "Trend exit B2", "B1": "Hold IEF B1"},
        data_source="Alpaca daily IEF, BIL and SPY bars (adjustment='all') read by the study's forward code",
    ),
    paperlog.LogSpec(
        study="Study 006", folder="research/006-term-spread-switch-long-history", kind="shadow record",
        label="inconclusive (fragile) on 1969–2018; forward record, scored once after 60 periods; no paper order",
        first_signal_date="2026-10-30",
        strategy="T1", benchmarks=("B3", "B1"),
        return_columns={"T1": "T1", "B3": "B3", "B1": "B1"},
        labels={"T1": "Term-spread switch T1", "B3": "Same-exposure mix B3", "B1": "Hold IEF B1"},
        data_source="FRED DGS10, DTB3 and DGS7 (signals) and Alpaca daily IEF and BIL bars (adjustment='all') "
                    "read by the study's forward code",
    ),
    paperlog.LogSpec(
        study="Study 007", folder="research/007-bond-carry-tilt-long-history", kind="shadow record",
        label="inconclusive (fragile) on 1974–2018; forward record, scored once after 60 periods; no paper order",
        first_signal_date="2026-10-30",
        strategy="T1", benchmarks=("B3_T1", "B1"),
        return_columns={"T1": "T1", "B3_T1": "B3_T1", "B1": "B1"},
        labels={"T1": "Carry tilt T1", "B3_T1": "Same-exposure mix B3", "B1": "Hold IEF B1"},
        data_source="FRED DGS10, DTB3 and DGS7 (carry) and Alpaca daily IEF and BIL bars (adjustment='all') "
                    "read by the study's forward code",
    ),
    paperlog.LogSpec(
        study="Study 008", folder="research/008-bond-value-tilt-long-history", kind="shadow record",
        label="not supported on 1974–2018; forward record, scored once after 60 periods; no paper order",
        first_signal_date="2026-10-30",
        strategy="T1", benchmarks=("B3_T1", "B1"),
        return_columns={"T1": "T1", "B3_T1": "B3_T1", "B1": "B1"},
        labels={"T1": "Value tilt T1", "B3_T1": "Same-exposure mix B3", "B1": "Hold IEF B1"},
        data_source="FRED DGS10, DTB3 and DGS7, FRED CPIAUCNS and CPILFENS (real yield) and Alpaca daily IEF "
                    "and BIL bars (adjustment='all') read by the study's forward code",
    ),
    # Studies 010 and 011 (added 2026-10-26): shadow-only monthly records from the Kenneth French Data
    # Library; no return is drawn here because each study scores its record once, after 60 holding months.
    # Study 009 has no record of its own (it scores the shadow records of 006 to 008).
    paperlog.LogSpec(
        study="Study 010", folder="research/010-factor-momentum-french-us", kind="monthly position record",
        label="not supported on 1927–2026; shadow-only, every month scored once after 60 holding months; no paper order",
        first_signal_date="2026-09", records_file="positions.csv", record_format="{factor} {h:+d}",
        release_log="releases/fetch_log.csv",
        scored_note="once, by `python -m src.forward010 score --release YYYYMM`, after 60 holding months (2026-09 to 2031-08), from the "
                    "first archived release that contains 2031-08; a low-power check (detects a Sharpe of d of about 1.27 "
                    "at 80% power); `interim` gives months recorded, months with a return, cumulative T and B3 and the mean of d, without a t-statistic or verdict",
        chart_note="No equity line: positions are +1 (long) or −1 (short) per factor; the factor returns of each month "
                   "come from a later library release and are scored only at the end.",
    ),
    paperlog.LogSpec(
        study="Study 011", folder="research/011-industry-momentum-french-us", kind="monthly cohort record",
        label="not supported on 806 months outside [MG99]'s 1963–1995 sample; shadow-only, scored once after 60 "
              "holding months; no paper order",
        first_signal_date="2026-09", records_file="cohorts.csv", record_format="long {winners} / short {losers}",
        release_log="releases/fetch_log.csv",
        scored_note="once, by `python -m src.forward011 score --release YYYYMM`, after 60 holding months (2026-09 to 2031-08), from the "
                    "first archived release that contains 2031-08; a low-power check (detects a Sharpe of d of about 1.27 "
                    "at 80% power); `interim` gives counts and the mean and sum of d without a t-statistic or verdict",
        chart_note="No equity line: each month starts a six-month cohort (winners long, losers short, French Data "
                   "Library industry names); its returns are scored only at the end.",
    ),
]


def main() -> int:
    generated = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = paperlog.build(ROOT, SPECS, OUT, generated)
    for entry in manifest["studies"]:
        print(f"{entry['study']}: {entry['records']} record(s), {entry['shadow_lines']} shadow line(s), "
              f"{entry['executions']} execution record(s); next record due {entry['next_record_due']}")
    print(f"written: {OUT.relative_to(ROOT)}/README.md, manifest.json"
          + (", " + ", ".join(sorted(manifest["outputs_sha256"])) if manifest["outputs_sha256"] else " (no chart: no shadow line yet)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
