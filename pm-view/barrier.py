"""The touch-market method of the prediction-market view, run end to end on the
FRED series CBBTCUSD (Coinbase Bitcoin, daily): fetch the series, keep it
git-ignored and hashed, estimate realised volatility, and print the first-passage
probability of each barrier for the Eastern-time month the market names
(pm_lib.touch_probability, pm_lib.realised_vol).  Nothing here writes a call;
the desk reads these figures beside the market's mid and applies the call rule
of README.md by hand, in the view.

PRE-SPECIFIED 2026-11-04 12:2x UTC, before the series was read for the first
time (the window and the rules below were committed before any figure existed,
so they cannot have been chosen to make or avoid a call; the rule of
research/POST_MORTEMS.md "thresholds before data", tools/check_question_gate.py):

* Spot: the last observation of the series, Coinbase's BTC-USD daily price as of
  17:00 Pacific on its date (FRED's note).  Its date and its lag to the run are
  printed; a lag over four days is flagged `stale`.  The level itself is printed
  only with --show-level (tools/pm_data_terms.md condition 2: at most one dated
  level per view).
* Volatility: close-to-close log returns of consecutive observations, sample
  standard deviation, annualised by sqrt(365) (pm_lib.realised_vol).  PRIMARY
  window: the last 30 observations, the length of the month the market spans;
  SENSITIVITY: the last 90.  Both are printed; the primary is the method's
  figure and the sensitivity is reported beside it, never swapped in.
* Horizon: from the spot's 17:00 Pacific timestamp to the end of the market's
  window, 00:00 Eastern on the first day of the following month (the markets'
  rules: "from 00:00 AM ET on the first day to 11:59 PM ET on the last"), in
  calendar days, fractional.
* Already touched: a daily close inside the month at or beyond a barrier means
  the barrier was touched, so the probability is 1.0 with the reason printed.
  A close short of the barrier does not rule out an intraday touch; the figure
  is then the formula's, which is a LOWER reading of the touch chance for two
  reasons the basis sentence must carry: daily closes understate the intraday
  range Binance's one-minute extremes see, and the series is Coinbase's price,
  not Binance's (tools/pm_data_terms.md condition 3).
* Drift: zero by construction (pm_lib.touch_probability).  Any drift the desk
  believes in is a reason for the basis sentence, not a parameter here.
* Departure: with --mid <barrier>:<market mid>, the departure of the primary
  figure from the market's mid is printed against the 0.10 threshold of the
  call rule.  A figure above the threshold is NOT a call; the view decides,
  with a basis sentence that names the market's number and the reading's
  limits.

Data terms (tools/pm_data_terms.md, verdict fred-cbbtcusd = derived): the raw
download stays under data/raw/fred/<UTC time>/ (git-ignored); data/fred_manifest.json
records the fetch time, URL, byte count, SHA-256, row count and the first and
last observation dates, never a value.  Citation printed with every figure:
"Coinbase, Coinbase Bitcoin [CBBTCUSD], retrieved from FRED, Federal Reserve
Bank of St. Louis".

Usage (from this folder):
    python barrier.py --month 2026-11 --barrier 80000:up --barrier 75000:down [--mid 80000:0.765]
    python barrier.py ... --dry-run                   # fetch, compute, write nothing
    python barrier.py ... --from-file <csv>           # a kept download instead of a fetch
    python barrier.py ... --show-level                # print the spot level (one per view)
Exit 0 when the figures were computed, 1 when the fetch failed or the series is
too short (the line says so).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pm_lib import realised_vol, touch_probability

HERE = Path(__file__).resolve().parent
SERIES = "CBBTCUSD"
FRED_URL = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={SERIES}"
UA = "qune-research/0.1 (public research; prediction-market view barrier method; pm-view/barrier.py)"
CITATION = "Coinbase, Coinbase Bitcoin [CBBTCUSD], retrieved from FRED, Federal Reserve Bank of St. Louis"
PRIMARY_WINDOW = 30      # observations: the month the market spans
SENSITIVITY_WINDOW = 90  # observations: reported beside the primary, never used in its place
STALE_DAYS = 4
CALL_THRESHOLD = 0.10    # README.md rule 2
EASTERN = ZoneInfo("America/New_York")
PACIFIC = ZoneInfo("America/Los_Angeles")
SPOT_HOUR_PACIFIC = 17   # FRED: "All data is as of 5 PM PST"

Fetcher = Callable[[str], bytes]


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def parse_fred_csv(text: str) -> list[tuple[date, float]]:
    """FRED's two-column download (a header line, then `<date>,<value>`); a missing
    value is `.` and is skipped; the rows keep the file's order."""
    out: list[tuple[date, float]] = []
    lines = text.strip().splitlines()
    if not lines or "," not in lines[0]:
        raise ValueError("not a FRED csv download")
    for ln in lines[1:]:
        d, _, v = ln.strip().partition(",")
        if not v or v == ".":
            continue
        out.append((date.fromisoformat(d), float(v)))
    return out


def month_window_utc(year: int, month: int) -> tuple[datetime, datetime]:
    """[00:00 Eastern on the 1st, 00:00 Eastern on the 1st of the next month), in UTC."""
    start = datetime(year, month, 1, tzinfo=EASTERN)
    nxt = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=EASTERN)
    return start.astimezone(UTC), nxt.astimezone(UTC)


def spot_time_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, SPOT_HOUR_PACIFIC, tzinfo=PACIFIC).astimezone(UTC)


def already_touched(obs: list[tuple[date, float]], barrier: float, side: str,
                    start: datetime, end: datetime) -> date | None:
    """The first observation date inside [start, end) whose close is at or beyond the
    barrier (`up`: close >= barrier; `down`: close <= barrier), else None."""
    for d, v in obs:
        t = spot_time_utc(d)
        if not (start <= t < end):
            continue
        if (side == "up" and v >= barrier) or (side == "down" and v <= barrier):
            return d
    return None


def assess(obs: list[tuple[date, float]], barriers: list[tuple[float, str]], year: int, month: int,
           now: datetime, primary: int = PRIMARY_WINDOW, sensitivity: int = SENSITIVITY_WINDOW) -> dict[str, Any]:
    """The method's figures for one month's barriers.  `obs` is the parsed series in
    date order; the spot is its last row.  Refuses a series shorter than the
    primary window plus one, or a spot after the month's end."""
    if len(obs) < primary + 1:
        raise ValueError(f"series has {len(obs)} observations; the primary window needs {primary + 1}")
    for side in (s for _, s in barriers):
        if side not in ("up", "down"):
            raise ValueError(f"barrier side must be up or down, not {side!r}")
    start, end = month_window_utc(year, month)
    spot_date, spot = obs[-1]
    spot_at = spot_time_utc(spot_date)
    if spot_at >= end:
        raise ValueError("the spot observation is after the month's end; nothing to assess")
    horizon_days = (end - spot_at).total_seconds() / 86400.0
    lag_days = (now - spot_at).total_seconds() / 86400.0
    closes = [v for _, v in obs]
    sigma_primary = realised_vol(closes[-(primary + 1):])
    sigma_sens = realised_vol(closes[-(sensitivity + 1):]) if len(closes) >= sensitivity + 1 else None
    rows: list[dict[str, Any]] = []
    for level, side in barriers:
        touched = already_touched(obs, level, side, start, end)
        row: dict[str, Any] = {"barrier": level, "side": side, "touched_on": touched.isoformat() if touched else None}
        if touched:
            row["p_primary"] = 1.0
            row["p_sensitivity"] = 1.0 if sigma_sens is not None else None
        else:
            row["p_primary"] = touch_probability(spot, level, sigma_primary, horizon_days)
            row["p_sensitivity"] = (touch_probability(spot, level, sigma_sens, horizon_days)
                                    if sigma_sens is not None else None)
        row["log_distance"] = math.log(level / spot)
        rows.append(row)
    return {
        "series": SERIES, "month": f"{year:04d}-{month:02d}", "window_start_utc": start.isoformat(),
        "window_end_utc": end.isoformat(), "spot_date": spot_date.isoformat(), "spot_level": spot,
        "spot_at_utc": spot_at.isoformat(), "lag_days": lag_days, "stale": lag_days > STALE_DAYS,
        "horizon_days": horizon_days, "observations": len(obs),
        "sigma_primary": sigma_primary, "primary_window": primary,
        "sigma_sensitivity": sigma_sens, "sensitivity_window": sensitivity,
        "barriers": rows,
    }


def fetch_series(fetcher: Fetcher, raw_dir: Path, manifest: Path, now: datetime,
                 dry_run: bool) -> tuple[list[tuple[date, float]], dict[str, Any]]:
    """Read the download, keep the bytes git-ignored under raw_dir/<time>/ and append
    one manifest entry without any value of the series.  Returns (rows, entry)."""
    body = fetcher(FRED_URL)
    rows = parse_fred_csv(body.decode("utf-8"))
    if not rows:
        raise ValueError("the download holds no observation")
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {
        "fetched_utc": stamp, "series": SERIES, "url": FRED_URL, "bytes": len(body), "sha256": sha256(body),
        "rows": len(rows), "first_obs": rows[0][0].isoformat(), "last_obs": rows[-1][0].isoformat(),
        "citation": CITATION, "kept": "raw download git-ignored; no value committed (verdict derived)",
    }
    if not dry_run:
        folder = raw_dir / stamp.replace(":", "")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{SERIES}.csv").write_bytes(body)
        entries: list[dict[str, Any]] = []
        if manifest.exists():
            entries = json.loads(manifest.read_text(encoding="utf-8"))
        entries.append(entry)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rows, entry


def lines(a: dict[str, Any], mids: dict[float, float], show_level: bool) -> list[str]:
    """The printed report.  The spot level appears only when asked for."""
    level = f"{a['spot_level']:,.2f}" if show_level else "withheld (--show-level prints it; one dated level per view)"
    sens = "n/a" if a["sigma_sensitivity"] is None else f"{a['sigma_sensitivity']:.4f}"
    out = [
        f"{a['series']} month {a['month']}: window {a['window_start_utc']} to {a['window_end_utc']} "
        f"(Eastern-time month, the markets' rule)",
        f"  spot: {a['spot_date']} close as of 17:00 Pacific = {a['spot_at_utc']}, level {level}; "
        f"lag {a['lag_days']:.2f} d{' STALE' if a['stale'] else ''}; horizon {a['horizon_days']:.2f} d; "
        f"{a['observations']} observations",
        f"  realised vol (close-to-close, annualised by sqrt(365)): primary {a['primary_window']} obs = "
        f"{a['sigma_primary']:.4f}; sensitivity {a['sensitivity_window']} obs = {sens}",
    ]
    for r in a["barriers"]:
        touched = f" TOUCHED on {r['touched_on']} (a daily close at or beyond the level)" if r["touched_on"] else ""
        ps = "n/a" if r["p_sensitivity"] is None else f"{r['p_sensitivity']:.3f}"
        s = f"  barrier {r['barrier']:,.0f} {r['side']}: P(touch) primary {r['p_primary']:.3f}, sensitivity {ps}{touched}"
        if r["barrier"] in mids:
            m = mids[r["barrier"]]
            dep = r["p_primary"] - m
            verdict = "at or over the 0.10 threshold: a call needs a basis sentence" if abs(dep) >= CALL_THRESHOLD \
                else "under the 0.10 threshold: nothing to add"
            s += f"; market mid {m:.3f}, departure {dep:+.3f} ({verdict})"
        out.append(s)
    out.append("  basis: daily Coinbase closes understate an intraday Binance one-minute touch, and the two venues' "
               "prices differ by a basis of their own; zero drift; the figure is a lower reading of the touch chance")
    out.append(f"  source: {CITATION}")
    return out


def parse_barrier(s: str) -> tuple[float, str]:
    level, _, side = s.partition(":")
    return float(level), side


def parse_mid(s: str) -> tuple[float, float]:
    level, _, m = s.partition(":")
    return float(level), float(m)


def run(month: str, barriers: list[tuple[float, str]], mids: dict[float, float], fetcher: Fetcher | None,
        from_file: Path | None, raw_dir: Path, manifest: Path, dry_run: bool, show_level: bool,
        now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> int:
    at = now()
    try:
        if from_file is not None:
            rows = parse_fred_csv(from_file.read_text(encoding="utf-8"))
            print(f"{SERIES}: read from {from_file.name} ({len(rows)} observations; nothing fetched or written)")
        else:
            assert fetcher is not None
            rows, entry = fetch_series(fetcher, raw_dir, manifest, at, dry_run)
            print(f"{SERIES}: fetched {entry['bytes']:,} bytes, sha256 {entry['sha256'][:12]}, {entry['rows']} "
                  f"observations {entry['first_obs']}..{entry['last_obs']}"
                  f"{' (dry run: nothing written)' if dry_run else ''}")
        y, m = (int(x) for x in month.split("-"))
        a = assess(rows, barriers, y, m, at)
    except (urllib.error.URLError, OSError, ValueError, UnicodeDecodeError) as e:
        print(f"{SERIES}: FAILED {e}")
        return 1
    for ln in lines(a, mids, show_level):
        print(ln)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", required=True, help="YYYY-MM, the Eastern-time month the market names")
    ap.add_argument("--barrier", action="append", required=True, help="<level>:<up|down>, repeatable")
    ap.add_argument("--mid", action="append", default=[], help="<level>:<market mid>, repeatable")
    ap.add_argument("--from-file", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show-level", action="store_true")
    ap.add_argument("--raw-dir", type=Path, default=None)
    ap.add_argument("--manifest", type=Path, default=None)
    a = ap.parse_args(argv)
    raw_dir = a.raw_dir if a.raw_dir is not None else HERE / "data" / "raw" / "fred"
    manifest = a.manifest if a.manifest is not None else HERE / "data" / "fred_manifest.json"
    barriers = [parse_barrier(b) for b in a.barrier]
    mids = dict(parse_mid(m) for m in a.mid)
    return run(a.month, barriers, mids, None if a.from_file else http_get, a.from_file, raw_dir, manifest,
               a.dry_run, a.show_level)


if __name__ == "__main__":
    sys.exit(main())
