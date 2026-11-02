"""Power first for Study 013 (calibration and the favourite-longshot bias on
Polymarket), from counts of resolved markets only. No outcome is read.

Written 2026-11-02 from 00:2xZ by the research loop before the question is
fixed (RESEARCH_AGENDA, status on 2026-11-01: "how many independent resolved
markets the venues' public history holds, and so the power of a calibration
test, ... is computed and committed before the question is fixed").

What it fetches: the Gamma API's closed-market keyset listing
(/markets/keyset, cursor pagination), one scheduled-end-date day at a time,
100 rows a page (the API's page cap, observed 2026-11-02 00:21Z on a request
for 500; the offset form refuses deeper pages with 422), public, no key, no
wallet, read-only, inside the documented rate limits (300 requests per 10 s
on /markets). Each response body is hashed in memory and discarded; what is
kept, git-ignored under tools/data/raw/pm013-power-<date>/, is one JSON line
per market with a whitelist of fields: identifiers, dates, resolution status
and mechanism, order-book flag, negative-risk flag, volume, liquidity, tag
labels and the parent event ids. The outcome fields (`outcomePrices`,
`outcomes`, `resolvedBy`), the question text, the description and the slug
are never written and never printed, so the author of the question note sees
no outcome and no wording. A reviewer recounts from the kept lines
(`--from`) or re-fetches by id. Records are streamed to disk and only the
counters stay in memory: the first version held every record in memory and
was killed by the host's out-of-memory killer at about 7.6 GB of pages read
(2026-11-02 00:50Z, nothing written; this version replaced it).

What it counts, by calendar month of `closedTime` (the venue's resolution
time, not the scheduled `endDate`): markets, markets with UMA status
`resolved`, with an order book, distinct parent events, negative-risk markets,
markets carrying a Sports tag, markets with volume of at least 10,000 USDC,
and the resolution mechanism (UMA markets against the venue's automatically
resolved up/down price markets). The fetch windows are scheduled end dates,
so a month's count is a lower bound on the markets that resolved in it: a
market that resolved early under a later scheduled date is not fetched
(stated in the output).

What it computes: the minimum detectable departure of a logistic
recalibration slope b from 1 (one-sided, b > 1 means prices compressed
towards 0.50, the favourite-longshot direction) over a forward window of
4, 8 and 12 weeks at the last three complete months' rate, with the
independent count taken as (a) markets and (b) distinct parent events, the
conservative row. SE(b) under the null of calibration is
1 / sqrt(n * E[x^2 p(1-p)]) with x = logit(p), E over an assumed price
distribution at the test horizon (three assumptions, stated; the data step
measures the distribution before any outcome is read, as Study 005 measured
sigma_d). MDE = K * SE with K = 2.842 (t >= 2.0 at 80% power, the programme's
convention) and K = 2.486 (one-sided 5% at 80% power). The published effect
the ratio is stated against is the Princeton senior thesis "The Price is
(Almost) Right" (Walker, 2026-04-09; 188,509 resolved binary markets 2022-11
to 2025-12): fitted overall logistic recalibration slope b = 1.112, reported
from its abstract; the full text answered HTTP 401 on 2026-11-02 and was not
read. The bucket form (outcome share less mean price in the longshot bucket)
is reported beside it against the published probability errors of
arXiv:2609.12878 (Cardozo and Rivero-Wildemauwe, read in full, HTML,
2026-11-02): +0.24 / -0.23 / +0.20 percentage points for longshots under its
three aggregations.

Why a sample of days: one scheduled day holds about 25,000 closed markets
(2026-08-01: 25,916 over 260 pages; 2026-08-02: 24,830; observed 2026-11-02
00:52-00:54Z), most of them the venue's automatically resolved short-dated
up/down price markets, so a full count of three months is about two hours of
paging; the committed run takes one scheduled day in every five from
2026-08-01 to 2026-10-31 (19 days of 92; five is coprime with seven, so the
sample cycles through the weekdays) and scales the mean per sampled day to a
month.

Run from the repository root (fetches; about 20 minutes):
    .venv/bin/python tools/power_pm013.py --fetch --first 2026-08-01 --last 2026-10-31 --every 5 > tools/power_pm013.txt
Recompute from the kept lines without fetching:
    .venv/bin/python tools/power_pm013.py --from tools/data/raw/pm013-power-2026-11-02 > tools/power_pm013.txt

Correction (2026-11-02 01:2xZ, before any figure was copied into the
question note): the first output (written 01:09:37Z) divided the sampled
total by the 38 distinct `endDate` day labels instead of the 19 fetched
windows. A window [day 00:00Z, day+1 00:00Z] also returns the markets
scheduled exactly at the next midnight, which carry the next day's label, so
every window produced two labels and every monthly rate was understated by
half (the MDEs overstated by sqrt(2)). The rate now divides by the number of
fetched windows read from the page manifest; the day table keeps the labels
and says so. The 01:09Z figures were never used.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator
from pathlib import Path

GAMMA_KEYSET = "https://gamma-api.polymarket.com/markets/keyset"
UA = "qune-research/0.1 (public research; counts only; tools/power_pm013.py)"
PAGE = 100  # observed page cap
KEEP = (
    "id",
    "closedTime",
    "endDate",
    "startDate",
    "createdAt",
    "umaResolutionStatus",
    "resolutionMechanism",
    "enableOrderBook",
    "negRisk",
    "volumeNum",
    "liquidityNum",
    "restricted",
    "version",
    "active",
    "archived",
    "closed",
)
K_PROGRAMME = 2.842  # NW t >= 2.0 at 80% power (tools/power_mined.py)
K_ONESIDED = 2.486  # z(0.95) + z(0.80)
PUBLISHED_SLOPE_MINUS_ONE = 0.112  # thesis abstract: b = 1.112 (not read in full)
PUBLISHED_BUCKET_PP = 0.24  # arXiv:2609.12878 Table 6, equal child-market longshot probability error, pp
VOLUME_FLOOR = 10_000.0
MONTHS_PER_4W = 4 / (365.25 / 12 / 7)


def strip(m: dict) -> dict:
    out = {k: m.get(k) for k in KEEP}
    out["eventIds"] = sorted(str(e.get("id")) for e in (m.get("events") or []) if e.get("id") is not None)
    out["tagLabels"] = sorted(str(t.get("label")) for t in (m.get("tags") or []) if t.get("label"))
    return out


def fetch_page(day: dt.date, cursor: str | None) -> tuple[list[dict], str | None, str, int]:
    """One page of the keyset listing. Returns rows, next cursor, body hash, bytes."""
    q = {
        "closed": "true",
        "end_date_min": f"{day.isoformat()}T00:00:00Z",
        "end_date_max": f"{(day + dt.timedelta(days=1)).isoformat()}T00:00:00Z",
        "limit": str(PAGE),
        "include_tag": "true",
    }
    if cursor:
        q["after_cursor"] = cursor
    url = GAMMA_KEYSET + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    delay = 1.0
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            page = json.loads(body)
            rows = page.get("markets") or []
            nxt = page.get("next_cursor") or None
            return rows, nxt, hashlib.sha256(body).hexdigest(), len(body)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 5:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("unreachable")


def fetch_stream(first: dt.date, last: dt.date, out_dir: Path, every: int) -> Iterator[dict]:
    """Yield stripped records while streaming them to records.jsonl and the
    page manifest to manifest.jsonl; duplicates across day windows are
    removed by id (a bounded set of ids, not the records). `every` > 1
    fetches one scheduled day in every `every` (a systematic sample of
    scheduled end dates; 5 cycles through the weekdays)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    pages = 0
    with (
        open(out_dir / "records.jsonl", "w", encoding="utf-8") as rec,
        open(out_dir / "manifest.jsonl", "w", encoding="utf-8") as man,
    ):
        day = first
        while day <= last:
            if (day - first).days % every:
                day += dt.timedelta(days=1)
                continue
            cursor: str | None = None
            page_no = 0
            day_rows = 0
            while True:
                rows, nxt, digest, nbytes = fetch_page(day, cursor)
                pages += 1
                man.write(
                    json.dumps(
                        {
                            "end_date_day": day.isoformat(),
                            "page": page_no,
                            "rows": len(rows),
                            "bytes": nbytes,
                            "sha256": digest,
                            "fetched_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        }
                    )
                    + "\n"
                )
                for m in rows:
                    mid = str(m.get("id"))
                    if mid in seen:
                        continue
                    seen.add(mid)
                    r = strip(m)
                    rec.write(json.dumps(r) + "\n")
                    day_rows += 1
                    yield r
                if len(rows) < PAGE or not nxt:
                    break
                cursor = nxt
                page_no += 1
                time.sleep(0.05)
            print(f"  {day}: {page_no + 1} pages, {day_rows} new markets", file=sys.stderr, flush=True)
            day += dt.timedelta(days=1)
            time.sleep(0.05)
    print(f"{pages} pages, {len(seen)} distinct markets", file=sys.stderr, flush=True)


def read_stream(src: Path) -> Iterator[dict]:
    with open(src / "records.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def month_of(ts: str | None) -> str | None:
    if not ts or len(ts) < 7:
        return None
    return ts[:7]


def is_sports(r: dict) -> bool:
    return any(lab.lower() == "sports" for lab in r.get("tagLabels", []))


def new_month() -> dict:
    return {
        "markets": 0,
        "uma_resolved": 0,
        "orderbook": 0,
        "negrisk": 0,
        "sports": 0,
        "nonsports": 0,
        "vol10k": 0,
        "clean": 0,
        "clean_nonsports": 0,
        "events": set(),
        "events_nonsports": set(),
        "events_clean": set(),
        "events_clean_nonsports": set(),
        "mechanism": collections.Counter(),
    }


def count_table(records: Iterable[dict]) -> tuple[dict[str, dict], dict[str, dict], int]:
    """Counts keyed by month of closedTime (first table) and by scheduled
    endDate day (second table, the fetch window)."""
    by_month: dict[str, dict] = collections.defaultdict(new_month)
    by_day: dict[str, dict] = collections.defaultdict(new_month)
    n = 0
    for r in records:
        n += 1
        mo = month_of(r.get("closedTime")) or "no closedTime"
        day = (r.get("endDate") or "no endDate")[:10]
        uma = r.get("umaResolutionStatus") == "resolved"
        ob = bool(r.get("enableOrderBook"))
        vol = float(r.get("volumeNum") or 0.0)
        sp = is_sports(r)
        evs = r.get("eventIds") or [f"market:{r['id']}"]
        clean = uma and ob and vol >= VOLUME_FLOOR
        for t in (by_month[mo], by_day[day]):
            t["markets"] += 1
            t["uma_resolved"] += uma
            t["orderbook"] += ob
            t["negrisk"] += bool(r.get("negRisk"))
            t["sports"] += sp
            t["nonsports"] += not sp
            t["vol10k"] += vol >= VOLUME_FLOOR
            t["mechanism"][str(r.get("resolutionMechanism"))] += 1
            t["events"].update(evs)
            if not sp:
                t["events_nonsports"].update(evs)
            if clean:
                t["clean"] += 1
                t["events_clean"].update(evs)
                if not sp:
                    t["clean_nonsports"] += 1
                    t["events_clean_nonsports"].update(evs)
    return by_month, by_day, n


def logit(p: float) -> float:
    return math.log(p / (1 - p))


def info_per_market(dist: str) -> float:
    """E[x^2 p(1-p)] under an assumed price distribution on (0.02, 0.98)."""
    lo, hi, n = 0.02, 0.98, 20000
    xs = [lo + (hi - lo) * (i + 0.5) / n for i in range(n)]
    if dist == "uniform":
        w = [1.0] * n
    elif dist == "u-shaped (Beta 0.5,0.5)":
        w = [1 / math.sqrt(p * (1 - p)) for p in xs]
    elif dist == "tails-heavy (half in 0.02-0.10 or 0.90-0.98)":
        w = [(0.5 / 0.16) if (p < 0.10 or p >= 0.90) else (0.5 / 0.80) for p in xs]
    else:
        raise ValueError(dist)
    s = sum(w)
    return sum(wi * logit(p) ** 2 * p * (1 - p) for wi, p in zip(w, xs, strict=True)) / s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--from", dest="src", default=None)
    ap.add_argument("--first", default="2026-08-01")
    ap.add_argument("--last", default=None)
    ap.add_argument("--every", type=int, default=1, help="fetch one scheduled day in every N (systematic sample)")
    args = ap.parse_args()
    today = dt.datetime.now(dt.UTC).date()
    last = dt.date.fromisoformat(args.last) if args.last else today
    first = dt.date.fromisoformat(args.first)

    t0 = time.time()
    if args.fetch:
        out_dir = Path("tools/data/raw") / f"pm013-power-{today.isoformat()}"
        by_month, by_day, n = count_table(fetch_stream(first, last, out_dir, args.every))
        src_line = (
            f"fetched one scheduled end date in every {args.every} from {first} to {last} in {time.time() - t0:.0f} s; "
            f"{n:,} distinct closed markets kept (whitelisted fields, one JSON line each) under {out_dir}"
        )
    elif args.src:
        by_month, by_day, n = count_table(read_stream(Path(args.src)))
        src_line = f"recomputed from {args.src}: {n:,} distinct closed markets"
    else:
        ap.error("--fetch or --from needed")

    print("Power first for Study 013: Polymarket resolved-market counts (tools/power_pm013.py)")
    print(src_line)
    print("no outcome read: outcomePrices/outcomes/resolvedBy, question text, description and slug never written or printed")
    print("fetch windows: scheduled endDate days (a systematic sample of days), closed=true, keyset pages of 100; a window [day, day+1) also returns the markets scheduled exactly at the next midnight, which the day table lists under the next day's label")
    print("a day's count is a lower bound on the markets scheduled for it that have resolved; early resolutions under a later scheduled date are not fetched")
    print()
    hdr = (
        f"{'scheduled day':17} {'markets':>9} {'UMA res.':>9} {'book':>8} {'negRisk':>8} {'Sports':>8} {'nonSp':>8} {'vol>=10k':>8} "
        f"{'clean':>8} {'cleanNS':>8} | {'events':>8} {'ev nonSp':>8} {'ev clean':>8} {'ev clNS':>8}"
    )
    print(hdr)

    def row(label: str, t: dict) -> str:
        return (
            f"{label:17} {t['markets']:9,} {t['uma_resolved']:9,} {t['orderbook']:8,} {t['negrisk']:8,} {t['sports']:8,} {t['nonsports']:8,} {t['vol10k']:8,} "
            f"{t['clean']:8,} {t['clean_nonsports']:8,} | {len(t['events']):8,} {len(t['events_nonsports']):8,} {len(t['events_clean']):8,} {len(t['events_clean_nonsports']):8,}"
        )

    for day in sorted(by_day):
        print(row(day, by_day[day]))
    print("clean = UMA resolved and order book and volume >= 10,000 USDC; NS = Sports tag absent; ev = distinct parent events among that day's markets")
    print()
    print("the same markets by month of closedTime (the sample's resolution months, not a monthly total):")
    print(hdr.replace("scheduled day    ", "closedTime month "))
    for mo in sorted(by_month):
        print(row(mo, by_month[mo]))
    print()
    print("resolution mechanism by scheduled day (venue field `resolutionMechanism`):")
    for day in sorted(by_day):
        mech = ", ".join(f"{k} {v:,}" for k, v in by_day[day]["mechanism"].most_common())
        print(f"  {day:17} {mech}")
    print()

    cur = today.strftime("%Y-%m")
    days = sorted(d for d in by_day if d != "no endDate" and d[:7] < cur)
    man_path = (out_dir if args.fetch else Path(args.src)) / "manifest.jsonl"
    with open(man_path, encoding="utf-8") as mf:
        windows = sorted({json.loads(line)["end_date_day"] for line in mf if line.strip()})
    windows = [w for w in windows if w[:7] < cur]
    if len(windows) < 4:
        print("fewer than four fetched windows in complete months; no rate computed")
        return 0
    dpm = 365.25 / 12
    k = len(windows)
    rates = {
        "markets (all)": sum(by_day[d]["markets"] for d in days) / k * dpm,
        "UMA-resolved markets": sum(by_day[d]["uma_resolved"] for d in days) / k * dpm,
        "distinct events (all)": sum(len(by_day[d]["events"]) for d in days) / k * dpm,
        "clean markets": sum(by_day[d]["clean"] for d in days) / k * dpm,
        "distinct events, clean": sum(len(by_day[d]["events_clean"]) for d in days) / k * dpm,
        "distinct events, clean, non-Sports": sum(len(by_day[d]["events_clean_nonsports"]) for d in days) / k * dpm,
    }
    print(
        f"monthly rate = total over the {k} fetched windows {windows[0]}..{windows[-1]} (which produced the {len(days)} day labels above: a window's midnight-exact markets carry the next day's label) / {k} x {dpm:.2f} days a month (a lower bound; events spanning several scheduled days are counted on each): "
        + "; ".join(f"{k_} {v:,.0f}" for k_, v in rates.items())
    )
    print()

    dists = ["uniform", "u-shaped (Beta 0.5,0.5)", "tails-heavy (half in 0.02-0.10 or 0.90-0.98)"]
    infos = {d: info_per_market(d) for d in dists}
    print("Slope test: logistic recalibration y ~ a + b*logit(p) at one fixed horizon; H1: b > 1 (compression towards 0.50)")
    print(f"published effect: b - 1 = {PUBLISHED_SLOPE_MINUS_ONE} (thesis abstract, 2026-04-09; full text HTTP 401 on 2026-11-02, not read)")
    print("SE(b) = 1/sqrt(n * E[x^2 p(1-p)]) under calibration; E under an assumed price distribution at the horizon (measured at the data step before any outcome is read):")
    for d in dists:
        print(f"  {d:48} E = {infos[d]:.4f}")
    print(f"MDE = K * SE, K = {K_PROGRAMME} (t >= 2.0 at 80% power) and {K_ONESIDED} (one-sided 5%, 80% power); ratio = MDE / {PUBLISHED_SLOPE_MINUS_ONE}")
    print()
    print(f"{'window':>8} {'unit (rate per 4 weeks)':36} {'n':>9} | {'E assumption':48} {'MDE K=2.842':>12} {'ratio':>6} {'MDE K=2.486':>12} {'ratio':>6}")
    for weeks in (4, 8, 12):
        for label, rate in rates.items():
            n_w = rate * MONTHS_PER_4W * weeks / 4
            for d in dists:
                if d != "uniform" and label not in ("distinct events, clean", "distinct events, clean, non-Sports"):
                    continue
                se = 1 / math.sqrt(max(n_w, 1) * infos[d])
                m1, m2 = K_PROGRAMME * se, K_ONESIDED * se
                print(
                    f"{weeks:>6} w {label:36} {n_w:9,.0f} | {d:48} {m1:12.4f} {m1 / PUBLISHED_SLOPE_MINUS_ONE:6.2f} {m2:12.4f} {m2 / PUBLISHED_SLOPE_MINUS_ONE:6.2f}"
                )
    print()
    print("Bucket test (not the decision test): outcome share less mean price among markets priced 0.02-0.10 at the horizon, in percentage points")
    print(f"published effect: {PUBLISHED_BUCKET_PP} pp (arXiv:2609.12878 Table 6, equal child-market; -0.23 pooled; +0.20 equal parent-event; signs differ by aggregation)")
    ev_clean = rates["distinct events, clean"]
    for share in (0.10, 0.25, 0.50):
        for weeks in (4, 12):
            n_b = ev_clean * MONTHS_PER_4W * weeks / 4 * share
            pbar = 0.05
            se = math.sqrt(pbar * (1 - pbar) / max(n_b, 1)) * 100
            m1 = K_PROGRAMME * se
            print(f"  longshot share {share:.2f}, {weeks:2} w, clean events: n = {n_b:9,.0f}; MDE = {m1:6.2f} pp; ratio to 0.24 pp = {m1 / PUBLISHED_BUCKET_PP:7.1f}")
    print("  interior bins: arXiv:2609.12878 Figure 1 reports -5.86 pp at the 35-40 cent bin and +7.28 pp at the 60-65 cent bin (equal child-market weights)")
    for share in (0.02, 0.05, 0.10):
        for weeks in (4, 12):
            n_b = ev_clean * MONTHS_PER_4W * weeks / 4 * share
            pbar = 0.375
            se = math.sqrt(pbar * (1 - pbar) / max(n_b, 1)) * 100
            m1 = K_PROGRAMME * se
            print(f"  bin share {share:.2f}, {weeks:2} w, clean events: n = {n_b:9,.0f}; MDE = {m1:6.2f} pp; ratio to 5.86 pp = {m1 / 5.86:5.2f}")
    print("  the return-unit form (per dollar) has a per-market sd of sqrt((1-p)/p), about 4.4 at p = 0.05, and is not computed: it cannot be the decision test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
