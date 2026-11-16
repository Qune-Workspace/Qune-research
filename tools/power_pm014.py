"""Power first for Study 014 (the longshot spread premium at the horizon on
Polymarket), from counts only. No spread, bid, ask, mid or outcome is read.

Written 2026-11-16 from 18:3xZ by the research loop before the question is
fixed (the question gate of 2026-10-31: power computed and committed before
the question note, tools/check_question_gate.py).

What it tests the power of: the decision statistic of Study 014, the
difference in the mean of ln(relative quoted spread) between two price bins
of the snapshot-of-record row at the horizon,

    Delta = mean(ln s | longshot bin, 0.01 <= mid < 0.10)
          - mean(ln s | central bin, 0.40 <= mid <= 0.60),

with s = (bestAsk - bestBid) / mid of the first listed outcome token (a
spread below the market's tick is floored at the tick), one-sided H1:
Delta > 0 (longshots quoted relatively wider), clustered by parent event.

The published effect the ratio is stated against: arXiv:2604.24366v2
(Dubach, "The Anatomy of a Decentralized Prediction Market", v2 of
2026-05-14; read from the arXiv HTML on 2026-11-16 18:2xZ), stylized fact
SF1 on a pre-registered 600-market panel over 2026-02-28 to 2026-03-27:
median quoted spread about 400 bps of mid in the central [0.4, 0.6] range,
1,300 to 1,800 bps for markets trading below 0.10. In log units the smaller
end of that premium is ln(1300 / 400) = 1.179; the ratio is scale-free, so
full and half spreads give the same figure.

Why counts suffice: ln s is bounded on each bin, because the sample's
spread cap is 0.10 (Study 013 §6.3, the same rows), the smallest tick the
venue uses is 0.001 (`orderPriceMinTickSize`; most markets 0.01, the wider
bound is kept) and the mid lies inside the bin. Longshot bin: s in
[0.001 / 0.10, 0.10 / 0.01] = [0.01, 10], ln range 6.908, so by Popoviciu's
inequality sd <= 3.454. Central bin: s in [0.001 / 0.60, 0.10 / 0.40] =
[0.00167, 0.25], ln range 5.011, sd <= 2.505. SE(Delta) <= sqrt(3.454^2 / n1
+ 2.505^2 / n2) with n1, n2 the independent counts in the two bins. MDE =
K * SE with K = 2.842 (t >= 2.0 at 80% power, the programme's convention)
and K = 2.486 (one-sided 5% at 80% power). These are upper bounds on the
MDE: the realised spread distribution is narrower than its range, so the
realised power, computed with the result, is higher. The bound is the
honest figure here because the spread is the quantity under test and its
spread cannot be measured before the question is fixed without reading it.

Where the counts come from: the clean counts per 4 and 8 weeks are read
from tools/power_pm013.txt (markets and distinct parent events, UMA
resolved, order book, volume >= 10,000 USDC; the systematic one-in-five day
sample of 2026-08-01 to 2026-10-31 scaled to the window), because Study 014
reads the same rows as Study 013. The bin shares at the horizon are not
known without reading prices, so a grid is printed and the decision row is
the conservative one named in QUESTION.md. `--snapshot <records.jsonl>`
cross-checks the rate against the newest kept snapshot: open binary
order-book markets whose scheduled `endDate` lies inside the window and
whose `volumeNum` is already at the floor, with their distinct events; the
fields read are listed in the output and no price field is among them.

Run from the repository root:
    .venv/bin/python tools/power_pm014.py --snapshot research/013-polymarket-calibration-forward/data/raw/snapshots/2026-11-16/records.jsonl > tools/power_pm014.txt
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from pathlib import Path

K_PROGRAMME = 2.842  # NW t >= 2.0 at 80% power (tools/power_mined.py)
K_ONESIDED = 2.486  # z(0.95) + z(0.80)

SPREAD_CAP = 0.10  # Study 013 §6.3
TICK_MIN = 0.001  # the smallest orderPriceMinTickSize seen on the venue (most markets 0.01)
LONGSHOT = (0.01, 0.10)  # mid in [0.01, 0.10)
CENTRAL = (0.40, 0.60)  # mid in [0.40, 0.60]
PUBLISHED_LOG_PREMIUM = math.log(1300 / 400)  # arXiv:2604.24366v2 SF1, smaller end

WINDOW_LO = dt.datetime(2026, 11, 17, tzinfo=dt.UTC)  # the first UTC day after this note (counts only)
WINDOW_HI = dt.datetime(2026, 12, 30, tzinfo=dt.UTC)  # Study 013's window end (exclusive)
VOLUME_FLOOR = 10_000.0

SNAPSHOT_FIELDS_READ = ("enableOrderBook", "outcomes", "endDate", "volumeNum", "eventIds")
PRICE_FIELDS_NEVER_READ = ("bestBid", "bestAsk", "spread", "lastTradePrice", "outcomePrices", "umaResolutionStatus")

ROW_RE = re.compile(r"^\s*(4|8) w (clean markets|distinct events, clean)\s+([\d,]+)\s*\|")


def log_sd_bound(mid_lo: float, mid_hi: float, tick: float = TICK_MIN, cap: float = SPREAD_CAP) -> float:
    """Popoviciu's bound on the sd of ln(spread / mid) when the spread lies in
    [tick, cap] and the mid in [mid_lo, mid_hi]: half the range of the log."""
    s_lo = tick / mid_hi
    s_hi = cap / mid_lo
    return (math.log(s_hi) - math.log(s_lo)) / 2.0


def mde(n_longshot: float, n_central: float, k: float) -> float:
    """Minimum detectable Delta (log units) at power 80% for the given K,
    from the two bins' counts and the per-bin sd bounds."""
    if n_longshot <= 0 or n_central <= 0:
        raise ValueError("both bins need a positive count")
    sd1 = log_sd_bound(*LONGSHOT)
    sd2 = log_sd_bound(*CENTRAL)
    return k * math.sqrt(sd1 * sd1 / n_longshot + sd2 * sd2 / n_central)


def clean_counts(power_013_text: str) -> dict[tuple[int, str], int]:
    """The clean counts per window from tools/power_pm013.txt: keys
    (weeks, 'markets' | 'events'). Refuses a file without all four rows."""
    out: dict[tuple[int, str], int] = {}
    for line in power_013_text.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        weeks = int(m.group(1))
        unit = "markets" if m.group(2) == "clean markets" else "events"
        out.setdefault((weeks, unit), int(m.group(3).replace(",", "")))
    missing = [k for k in [(4, "markets"), (4, "events"), (8, "markets"), (8, "events")] if k not in out]
    if missing:
        raise ValueError(f"tools/power_pm013.txt lacks the rows {missing}")
    return out


def parse_end(stamp: str) -> dt.datetime:
    """A venue stamp with a zone, to UTC; ISO 8601 only, `Z` spelled out."""
    parsed = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"zoneless stamp {stamp!r}")
    return parsed.astimezone(dt.UTC)


def snapshot_counts(path: Path) -> dict[str, int]:
    """Open binary order-book markets of one kept snapshot whose scheduled end
    lies in the window and whose volume is already at the floor, with their
    distinct parent events. Reads SNAPSHOT_FIELDS_READ only."""
    rows = book = binary = windowed = at_floor = unreadable_end = 0
    events: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            rows += 1
            if not row.get("enableOrderBook"):
                continue
            book += 1
            try:
                outcomes = json.loads(row.get("outcomes") or "[]")
            except json.JSONDecodeError:
                outcomes = []
            if len(outcomes) != 2:
                continue
            binary += 1
            end = row.get("endDate")
            try:
                end_at = parse_end(end) if end else None  # a datetime, parsed with its zone, never ordered as text
            except ValueError:
                end_at = None
            if end_at is None:
                unreadable_end += 1
                continue
            if not (WINDOW_LO <= end_at < WINDOW_HI):
                continue
            windowed += 1
            if float(row.get("volumeNum") or 0.0) < VOLUME_FLOOR:
                continue
            at_floor += 1
            events.add(",".join(str(e) for e in (row.get("eventIds") or [])) or f"market:{row.get('id')}")
    return {
        "rows": rows,
        "order_book": book,
        "binary": binary,
        "end_unreadable_or_missing": unreadable_end,
        "end_in_window": windowed,
        "at_volume_floor": at_floor,
        "events_at_floor": len(events),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--power-013", default="tools/power_pm013.txt")
    ap.add_argument("--snapshot", default=None, help="a kept records.jsonl to cross-check the rate (counts only)")
    args = ap.parse_args()

    counts = clean_counts(Path(args.power_013).read_text(encoding="utf-8"))
    print("Power first for Study 014: the longshot spread premium at the horizon (tools/power_pm014.py)")
    print(
        f"counts from {args.power_013} (Study 013's clean rows: UMA resolved, order book, volume >= 10,000 USDC; "
        "one scheduled day in five, 2026-08-01 to 2026-10-31, scaled to the window); no spread, bid, ask, mid or outcome read"
    )
    print(
        f"published effect: arXiv:2604.24366v2 SF1, median quoted spread ~400 bps of mid central [0.4, 0.6] vs 1,300-1,800 bps below 0.10 "
        f"(600-market pre-registered panel, 2026-02-28 to 2026-03-27); smaller end in log units ln(1300/400) = {PUBLISHED_LOG_PREMIUM:.3f}"
    )
    sd1, sd2 = log_sd_bound(*LONGSHOT), log_sd_bound(*CENTRAL)
    print(
        f"sd bounds (Popoviciu; spread in [{TICK_MIN}, {SPREAD_CAP}], mid inside the bin): longshot {sd1:.3f}, central {sd2:.3f}; "
        f"MDE = K * sqrt(sd1^2/n1 + sd2^2/n2), K = {K_PROGRAMME} (programme) and {K_ONESIDED} (one-sided 5%); upper bounds on the MDE"
    )
    print()
    print(f"{'window':>8} {'unit':8} {'clean n':>9} {'longshot share':>14} {'central share':>13} {'n1':>8} {'n2':>8} | {'MDE K=2.842':>11} {'ratio':>6} {'MDE K=2.486':>11} {'ratio':>6}")
    for weeks in (4, 8):
        for unit in ("markets", "events"):
            n = counts[(weeks, unit)]
            for share_l in (0.10, 0.25, 0.50):
                for share_c in (0.02, 0.05, 0.10):
                    n1, n2 = n * share_l, n * share_c
                    m1, m2 = mde(n1, n2, K_PROGRAMME), mde(n1, n2, K_ONESIDED)
                    print(
                        f"{weeks:>6} w {unit:8} {n:9,} {share_l:14.2f} {share_c:13.2f} {n1:8,.0f} {n2:8,.0f} | "
                        f"{m1:11.3f} {m1 / PUBLISHED_LOG_PREMIUM:6.2f} {m2:11.3f} {m2 / PUBLISHED_LOG_PREMIUM:6.2f}"
                    )
    print("decision row: 8 w, events (the conservative unit), longshot share 0.10, central share 0.02 (the thinnest bins on the grid)")
    print()

    if args.snapshot:
        snap = Path(args.snapshot)
        c = snapshot_counts(snap)
        print(f"cross-check on the kept snapshot {snap} (fields read: {', '.join(SNAPSHOT_FIELDS_READ)}; never read: {', '.join(PRICE_FIELDS_NEVER_READ)}):")
        print(
            f"  rows {c['rows']:,}; order book {c['order_book']:,}; binary {c['binary']:,}; scheduled end unreadable or missing {c['end_unreadable_or_missing']:,}; "
            f"end in [{WINDOW_LO.date()}, {WINDOW_HI.date()}) {c['end_in_window']:,}; of those already at the volume floor {c['at_volume_floor']:,} markets in {c['events_at_floor']:,} events"
        )
        print(
            "  a lower bound on the window's clean count: markets listed after this snapshot, and markets that reach the floor later, are not in it; "
            "a market that resolves before its scheduled end is counted under its scheduled day here and under its closedTime in the study"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
