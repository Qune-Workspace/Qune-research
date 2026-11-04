"""The data-terms gate for prediction-market venues: no venue endpoint in the
tree, and no raw venue snapshot, unless the committed verdict allows it.

Written on 2026-11-01, the day the venue terms were finally read
(tools/pm_data_terms.md). The programme's rule since 2026-10-31 was "publish
only aggregates computed by us until each venue's terms are read". That rule
had no teeth: nothing stopped a script that calls a venue, or a committed
response file, from entering the tree while the terms were "not readable".
This check is the teeth.

What it checks, over every git-tracked file except the verdict file, this
script and BUILD_LOG.md (prose that records the verdict may name a host):

  A venue with verdict `neither`, or with no verdict line at all, may not be
      named by any of its API hostnames in any tracked file: no fetch code,
      no manifest, no data file.
  A venue with verdict `derived` may be fetched, but no tracked file may hold
      a raw response: the field names that only a raw venue response carries
      (`"clobTokenIds"`, `"outcomePrices"`, `"asset_id"` with `"bids"` for
      Polymarket) must not appear in a tracked data file (.json, .csv, .txt,
      .jsonl) under research/, desk-view/ or predictions/.
  A venue with verdict `raw` is not restricted by this script.

The verdict file carries one machine-readable line per venue, exactly
`verdict: <venue> = raw|derived|neither`, written by hand with the quoted
terms above it. This script never decides a verdict; it only holds the tree
to the one on record.

Exit 1 with one line per failure. `--selftest` runs the rule over in-memory
fixtures and reads nothing.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERDICT_FILE = Path("tools/pm_data_terms.md")
EXEMPT = {VERDICT_FILE.as_posix(), "tools/check_data_terms.py", "BUILD_LOG.md"}

# API hostnames per venue, from the venues' own documentation (read 2026-11-01).
HOSTS: dict[str, tuple[str, ...]] = {
    "polymarket": (
        "gamma-api.polymarket.com",
        "clob.polymarket.com",
        "data-api.polymarket.com",
        "ws-subscriptions-clob.polymarket.com",
        "ws-live-data.polymarket.com",
        "ws-live-v2.polymarket.com",
    ),
    "kalshi": (
        "api.elections.kalshi.com",
        "trading-api.kalshi.com",
        "demo-api.kalshi.co",
        "kalshi.com/trade-api",
    ),
    # Added 2026-11-04 (tools/pm_data_terms.md, "Price series for the Bitcoin
    # barrier markets"): Binance is the resolution source of those markets and
    # Coinbase the origin of the FRED series; neither's terms could be read,
    # so neither may be called. The FRED series is a fetch URL, not a host:
    # under `derived` it may be fetched, but its rows may not be committed.
    "binance": (
        "api.binance.com",
        "api1.binance.com",
        "api2.binance.com",
        "api3.binance.com",
        "api4.binance.com",
        "api-gcp.binance.com",
        "data-api.binance.vision",
        "stream.binance.com",
        "api.binance.us",
    ),
    "coinbase": (
        "api.exchange.coinbase.com",
        "api.coinbase.com",
        "api.pro.coinbase.com",
        "ws-feed.exchange.coinbase.com",
    ),
    "fred-cbbtcusd": ("fredgraph.csv?id=CBBTCUSD",),
}

# Field names that only a raw venue response carries. A derived aggregate
# (a count, a Brier score, a bucket table) never contains them.
RAW_MARKERS: dict[str, tuple[tuple[str, ...], ...]] = {
    "polymarket": (('"clobTokenIds"',), ('"outcomePrices"',), ('"asset_id"', '"bids"')),
    "kalshi": (('"yes_bid_dollars"',), ('"orderbook_fp"',), ('"event_ticker"', '"ticker"')),
    "binance": (),
    "coinbase": (),
    # The FRED download's own header, and the JSON observation form; a
    # realised-volatility figure or a barrier probability carries neither.
    "fred-cbbtcusd": (("CBBTCUSD", "observation_date"), ("CBBTCUSD", "DATE,"), ('"series_id"', '"CBBTCUSD"')),
}
DATA_SUFFIXES = {".json", ".csv", ".txt", ".jsonl"}
DATA_DIRS = ("research/", "desk-view/", "predictions/", "pm-view/")  # pm-view/ added 2026-11-04
VERDICTS = ("raw", "derived", "neither")
VERDICT_RE = re.compile(r"^verdict:\s*([a-z][a-z0-9-]*)\s*=\s*(raw|derived|neither)\s*$", re.M)


def parse_verdicts(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in VERDICT_RE.finditer(text)}


def check(files: list[tuple[str, str]], verdicts: dict[str, str]) -> list[str]:
    """files: (posix path, text). Returns failure lines; empty means pass."""
    failures: list[str] = []
    for venue, hosts in HOSTS.items():
        verdict = verdicts.get(venue)
        if verdict is None:
            failures.append(f"{VERDICT_FILE}: no verdict line for {venue} (verdict: {venue} = raw|derived|neither)")
        if verdict in (None, "neither"):
            for path, text in files:
                if path in EXEMPT:
                    continue
                for host in hosts:
                    if host in text:
                        failures.append(f"{path}: names {host} but the {venue} verdict is {verdict or 'missing'}")
                        break
        if verdict == "derived":
            for path, text in files:
                if path in EXEMPT or Path(path).suffix not in DATA_SUFFIXES or not path.startswith(DATA_DIRS):
                    continue
                for markers in RAW_MARKERS[venue]:
                    if all(m in text for m in markers):
                        failures.append(f"{path}: holds a raw {venue} response ({' + '.join(markers)}); verdict is derived")
                        break
    return failures


def tracked_files(root: Path) -> list[tuple[str, str]]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True).stdout
    files: list[tuple[str, str]] = []
    for raw in out.split(b"\0"):
        if not raw:
            continue
        path = raw.decode()
        p = root / path
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files.append((path, text))
    return files


def run(root: Path) -> int:
    verdict_path = root / VERDICT_FILE
    verdicts = parse_verdicts(verdict_path.read_text(encoding="utf-8")) if verdict_path.exists() else {}
    failures = check(tracked_files(root), verdicts)
    n = len(HOSTS)
    for line in failures:
        print(f"data terms: {line}")
    print(f"data terms: {'pass' if not failures else 'FAIL'} ({n} venues, verdicts {verdicts or 'none'})")
    return 1 if failures else 0


def selftest() -> int:
    ok = True
    v = {"polymarket": "derived", "kalshi": "neither", "binance": "neither", "coinbase": "neither",
         "fred-cbbtcusd": "derived"}
    # A clean tree under the recorded verdicts passes.
    clean = [
        ("README.md", "prose about Polymarket and Kalshi without hostnames"),
        ("research/013-x/results/calibration.csv", "bucket,n,mean_p,freq\n0.1,40,0.09,0.08\n"),
        ("research/013-x/src/fetch.py", 'BASE = "https://gamma-api.polymarket.com"'),
        ("BUILD_LOG.md", "the probe called api.elections.kalshi.com once"),
        ("tools/pm_data_terms.md", "verdict lines live here; api.elections.kalshi.com"),
    ]
    if check(clean, v):
        print("selftest: clean tree failed:", check(clean, v))
        ok = False
    # A fetch script naming a `neither` venue fails.
    bad_host = clean + [("research/013-x/src/fetch_k.py", 'BASE = "https://api.elections.kalshi.com/trade-api/v2"')]
    if not any("fetch_k.py" in f for f in check(bad_host, v)):
        print("selftest: kalshi hostname in a script did not fail")
        ok = False
    # A committed raw Polymarket response fails under `derived`.
    bad_raw = clean + [("research/013-x/data/markets.json", '[{"id": "1", "clobTokenIds": "[\\"1\\", \\"2\\"]"}]')]
    if not any("markets.json" in f for f in check(bad_raw, v)):
        print("selftest: raw Polymarket file did not fail under derived")
        ok = False
    # The same raw file passes under `raw`, and the hostname passes under `derived`.
    if check(bad_raw, {**v, "polymarket": "raw"}):
        print("selftest: raw verdict still failed")
        ok = False
    # A missing verdict line fails even with a clean tree.
    if not any("no verdict line for kalshi" in f for f in check(clean, {"polymarket": "derived"})):
        print("selftest: missing verdict did not fail")
        ok = False
    # 2026-11-04: a Binance or Coinbase endpoint anywhere in the tree fails (`neither` until read);
    # the FRED series may be fetched but its rows may not be committed, in pm-view/ too.
    bad_binance = clean + [("pm-view/btc.py", 'KLINES = "https://api.binance.com/api/v3/klines"')]
    if not any("btc.py" in f and "binance" in f for f in check(bad_binance, v)):
        print("selftest: binance hostname in a script did not fail")
        ok = False
    bad_coinbase = clean + [("pm-view/btc.py", 'CANDLES = "https://api.exchange.coinbase.com/products/BTC-USD/candles"')]
    if not any("btc.py" in f and "coinbase" in f for f in check(bad_coinbase, v)):
        print("selftest: coinbase hostname in a script did not fail")
        ok = False
    fred_fetch = clean + [("pm-view/btc.py", 'URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CBBTCUSD"')]
    if check(fred_fetch, v):
        print("selftest: fetching the FRED series under derived failed:", check(fred_fetch, v))
        ok = False
    bad_rows = clean + [("pm-view/data/cbbtcusd.csv", "observation_date,CBBTCUSD\n2026-11-03,77000.0\n")]
    if not any("cbbtcusd.csv" in f for f in check(bad_rows, v)):
        print("selftest: committed FRED rows under pm-view/ did not fail")
        ok = False
    derived_ok = clean + [("pm-view/data/btc_vol.json", '{"series": "CBBTCUSD via FRED", "realised_vol_30d": 0.52}')]
    if check(derived_ok, v):
        print("selftest: a derived statistic naming the series failed:", check(derived_ok, v))
        ok = False
    # The marker rule needs both halves of a pair: "asset_id" alone is not a book.
    half = clean + [("predictions/raw_note.txt", 'the field "asset_id" is the token id')]
    if check(half, v):
        print("selftest: a lone marker half failed")
        ok = False
    # Parsing: only the exact line form counts.
    parsed = parse_verdicts("verdict: polymarket = derived\nverdict: kalshi = neither\nverdict: manifold = maybe\n"
                            "verdict: fred-cbbtcusd = derived\n")
    if parsed != {"polymarket": "derived", "kalshi": "neither", "fred-cbbtcusd": "derived"}:
        print("selftest: verdict parsing", parsed)
        ok = False
    print("selftest: " + ("pass" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--selftest", action="store_true", help="check the rule on in-memory fixtures, read nothing")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    return run(args.root)


if __name__ == "__main__":
    sys.exit(main())
