"""Study 009 scoring (PREREGISTRATION.md §2-§3, step 4 of §6): the pooled
forward check of Studies 006, 007 and 008, scored once.

One function, ``score``, reads the three members' ``paper-log/shadow.csv``
(column ``d`` = T1 - B3 at base costs) and returns the single verdict of
trial P1.  It fetches nothing, computes no signal and changes nothing in the
members' folders.  ``python -m src.pool score --member-verdicts FILE`` writes
``results/score.json``; it refuses until every condition below holds, so on
any day before the members' first blocks are scored it only says why.

Rules, each tied to the pre-registration:

- **Members' verdicts are inputs (§2).**  A member is dropped when its *own*
  forward verdict for block 1 is "not testable".  That verdict and the
  member's block-1 scoring date come from the member's own ``score()`` (006
  ``forward.py``, 007 ``forward007.py``, 008 ``forward008.py``), not from this
  module, and are checked against the files (``check_members``): each scoring
  date must be the ``period_end`` of the member's shadow row 60; Study 006's
  whole row is recomputed from its ``T1_holding`` and ``d`` by its own rule;
  007 and 008 decide "not testable" from their decision records' targets,
  which ``shadow.csv`` lacks, so only one direction is checked there (a
  ``w_T1`` that never moved must come with "not testable").
- **Blocks (§3).**  A member's block 1 is its first 60 ``shadow.csv`` rows,
  the rows its own ``score()`` reads; they must be one continuous run in date
  order (each period starts where the last ended, as ``append_shadow``
  enforces).  A member with fewer rows is not scored, so nothing here runs
  early.
- **Pooled periods (§2).**  P_t is the mean of the remaining members' d for a
  holding period that sits inside every remaining member's block 1 with the
  same ``signal_date``, ``execution_date`` and ``period_end``.  Every other row
  of a remaining member's block is left out and listed with its reason; no
  value is ever filled.
- **Scoring date (§3).**  The scoring-date row must already be in
  ``trials.md`` (a log row whose step cell is exactly "Scoring date (P1)" and
  whose date cell starts with an ISO date), must fall strictly after every
  member's block-1 scoring date ("follows") and, in ``main``, not after today
  (UTC).  The row is read before any statistic is computed.
- **Verdict rows (§3).**  Newey-West t of mean(P), Bartlett kernel, 6 lags
  (the programme's C2).  Supported: mean > 0 and t >= 2.0; refuted: t <= -2.0;
  inconclusive otherwise, with the effect the block could have detected at its
  n from P's own dispersion (K x se x 12, K = 2.842 as §4); not testable when
  every member is dropped.  Every row carries "low-power check" (``row``).
  A pooled period that spans a missed month in all three members keeps its
  place in P, as §2 says; the count of periods longer than 45 days is
  reported beside the verdict.
- **Unregistered case.**  Remaining members with fewer than two common periods
  have no t; the pre-registration has no row for it, so the code refuses and
  the case needs a dated decision before anything is published.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

STUDY_DIR = Path(__file__).resolve().parents[1]
ROOT = STUDY_DIR.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qune_research.stats import newey_west_mean  # noqa: E402

MEMBERS = {
    "006": ROOT / "research/006-term-spread-switch-long-history/paper-log/shadow.csv",
    "007": ROOT / "research/007-bond-carry-tilt-long-history/paper-log/shadow.csv",
    "008": ROOT / "research/008-bond-value-tilt-long-history/paper-log/shadow.csv",
}
TRIALS_MD = STUDY_DIR / "trials.md"
RESULT_JSON = STUDY_DIR / "results" / "score.json"

KEY = ("signal_date", "execution_date", "period_end")
BLOCK_PERIODS = 60      # §3: each member's first 60-period block
LAGS = 6                # §3: Newey-West, Bartlett, 6 lags
T_BAR = 2.0             # §3
K = 2.842               # §4: t >= 2.0 at 80% power
PERIODS_PER_YEAR = 12

LABEL = "low-power check"
MEMBER_NOT_TESTABLE = "not testable"
MEMBER_VERDICTS = ("supported (forward)", "refuted (forward)", "inconclusive (forward)", MEMBER_NOT_TESTABLE)
VERDICT_SUPPORTED = "supported (pooled forward)"
VERDICT_REFUTED = "refuted (pooled forward)"
VERDICT_INCONCLUSIVE = "inconclusive (pooled forward)"
VERDICT_NOT_TESTABLE = "not testable"

# The step cell must read exactly "Scoring date (P1)" (code review, finding 4).
SCORING_ROW = re.compile(r"^\|\s*Scoring date \(P1\)\s*\|\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
LONG_PERIOD_DAYS = 45   # a holding period longer than this spans a missed month (reported, never dropped)


def read_shadows(paths: dict[str, Path] = MEMBERS) -> dict[str, pd.DataFrame]:
    """The members' ``shadow.csv`` files, every column as written (strings)."""
    missing = [m for m, p in paths.items() if not p.exists()]
    if missing:
        raise RuntimeError(f"no shadow.csv yet for {', '.join(missing)}: no forward record to score")
    return {m: pd.read_csv(p, dtype=str) for m, p in paths.items()}


def block(shadow: pd.DataFrame, member: str) -> pd.DataFrame:
    """Rows 1-60 of a member's shadow.csv, the rows its own score() reads."""
    for c in (*KEY, "d"):
        if c not in shadow.columns:
            raise ValueError(f"{member}: shadow.csv has no column {c}")
    if len(shadow) < BLOCK_PERIODS:
        raise RuntimeError(f"{member}: {len(shadow)} periods; block 1 ends after {BLOCK_PERIODS} (section 3)")
    rows = shadow.iloc[:BLOCK_PERIODS].copy()
    if rows.duplicated(list(KEY)).any() or rows["signal_date"].duplicated().any():
        raise ValueError(f"{member}: a signal date appears twice in block 1")
    for c in KEY:
        _iso(rows[c], f"{member}: {c}")
    if not (rows["signal_date"].is_monotonic_increasing
            and (rows["period_end"].iloc[:-1].to_numpy() == rows["execution_date"].iloc[1:].to_numpy()).all()):
        raise ValueError(f"{member}: block 1 is not one continuous run of periods in date order")
    rows["d"] = rows["d"].astype(float)
    if not np.isfinite(rows["d"].to_numpy()).all():
        raise ValueError(f"{member}: block 1 has an empty or non-finite d")
    return rows


def _iso(values, what: str) -> None:
    for v in values:
        try:
            ok = date.fromisoformat(str(v)).isoformat() == str(v)
        except ValueError:
            ok = False
        if not ok:
            raise ValueError(f"{what}: {v!r} is not an ISO date")


def own_006_verdict(rows: pd.DataFrame) -> str:
    """Study 006's block-1 row recomputed from its own shadow.csv by its own
    rule (006 ``forward.py`` ``forward_verdict``, §11.4): "not testable" when
    T1 held one asset in all 60 periods, else the Newey-West rows on d."""
    if "T1_holding" not in rows.columns:
        raise ValueError("006: shadow.csv has no column T1_holding")
    if rows["T1_holding"].nunique() == 1:
        return MEMBER_NOT_TESTABLE
    nw = newey_west_mean(rows["d"].astype(float).reset_index(drop=True), lags=LAGS)
    if nw["mean"] > 0 and nw["t"] >= T_BAR:
        return "supported (forward)"
    if nw["t"] <= -T_BAR:
        return "refuted (forward)"
    return "inconclusive (forward)"


def check_members(blocks: dict[str, pd.DataFrame], member_verdicts: dict[str, dict]) -> None:
    """The stated member verdicts against what the members' files can show
    (code review, findings 2, 5 and 7).  Each member's block-1 scoring date
    is the execution date of its 61st ok record, which is the period_end of
    its shadow row 60.  006's whole row is recomputed.  007 and 008 decide
    "not testable" from their records' targets, which shadow.csv lacks; one
    direction is checkable: a T1 weight that never moved in the block (w_T1
    constant) means every target was the same, so the member must say "not
    testable"."""
    for m, rows in blocks.items():
        if member_verdicts[m]["scoring_date"] != rows["period_end"].iloc[-1]:
            raise ValueError(f"{m}: stated scoring date {member_verdicts[m]['scoring_date']} is not the end of its "
                             f"block 1 in shadow.csv ({rows['period_end'].iloc[-1]})")
    own = own_006_verdict(blocks["006"])
    if member_verdicts["006"]["verdict"] != own:
        raise ValueError(f"006: stated verdict '{member_verdicts['006']['verdict']}' disagrees with its shadow.csv "
                         f"('{own}')")
    for m in ("007", "008"):
        rows = blocks[m]
        if "w_T1" not in rows.columns:
            raise ValueError(f"{m}: shadow.csv has no column w_T1")
        if rows["w_T1"].astype(float).nunique() == 1 and member_verdicts[m]["verdict"] != MEMBER_NOT_TESTABLE:
            raise ValueError(f"{m}: T1's weight never moved in block 1, but the stated verdict is "
                             f"'{member_verdicts[m]['verdict']}'")


def logged_scoring_date(trials_text: str) -> str | None:
    """The date in trials.md's "Scoring date (P1)" log row, if any (§3)."""
    found = SCORING_ROW.findall(trials_text)
    if len(found) > 1:
        raise ValueError("trials.md has more than one 'Scoring date (P1)' row")
    return found[0] if found else None


def pool(blocks: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, list[dict]]:
    """P on the periods common to every block (same three dates), and the
    left-out rows with their reasons."""
    keyed = {m: b.set_index(list(KEY)) for m, b in blocks.items()}
    common = None
    for b in keyed.values():
        common = b.index if common is None else common.intersection(b.index)
    common = common.sort_values() if common is not None else pd.MultiIndex.from_tuples([], names=KEY)
    left_out = []
    for m, b in blocks.items():
        for _, row in b.iterrows():
            k = tuple(row[c] for c in KEY)
            if k in common:
                continue
            reasons = []
            for other, ob in blocks.items():
                if other == m or k in keyed[other].index:
                    continue
                same_signal = ob[ob["signal_date"] == row["signal_date"]]
                if same_signal.empty:
                    reasons.append(f"{other}: no block-1 row with this signal date")
                else:
                    o = same_signal.iloc[0]
                    reasons.append(f"{other}: same signal date, execution {o['execution_date']}, "
                                   f"period end {o['period_end']}")
            left_out.append({"member": m, **{c: row[c] for c in KEY}, "reason": "; ".join(reasons)})
    frame = pd.DataFrame({m: keyed[m].loc[common, "d"].astype(float) for m in blocks}, index=common)
    frame["P"] = frame[list(blocks)].mean(axis=1) if blocks else pd.Series(dtype=float)
    return frame.reset_index(), left_out


def score(shadows: dict[str, pd.DataFrame], member_verdicts: dict[str, dict], trials_text: str) -> dict:
    """Trial P1, scored once (§3).  ``member_verdicts[m]`` = {"verdict": the
    member's own block-1 verdict, "scoring_date": its block-1 scoring date},
    both as the member's own score() returned them."""
    if set(shadows) != set(MEMBERS) or set(member_verdicts) != set(MEMBERS):
        raise ValueError(f"members are fixed: {', '.join(MEMBERS)} (section 2)")
    for m, v in member_verdicts.items():
        if not isinstance(v, dict):
            raise ValueError(f"{m}: member verdict must be {{'verdict': ..., 'scoring_date': ...}}")
        if v.get("verdict") not in MEMBER_VERDICTS:
            raise ValueError(f"{m}: unknown member verdict {v.get('verdict')!r}")
        _iso([v.get("scoring_date")], f"{m}: block-1 scoring date")
    blocks = {m: block(s, m) for m, s in shadows.items()}

    # §3: the scoring-date row is read before any statistic, and it must
    # follow (strictly) the last member's block-1 scoring date.
    when = logged_scoring_date(trials_text)
    last_member = max(v["scoring_date"] for v in member_verdicts.values())
    if when is None:
        raise RuntimeError("trials.md has no 'Scoring date (P1)' row: write it before any statistic (section 3)")
    _iso([when], "trials.md scoring date")
    if when <= last_member:
        raise RuntimeError(f"logged scoring date {when} does not follow the last member's block-1 scoring date "
                           f"{last_member} (section 3)")
    check_members(blocks, member_verdicts)

    dropped = sorted(m for m, v in member_verdicts.items() if v["verdict"] == MEMBER_NOT_TESTABLE)
    remaining = [m for m in MEMBERS if m not in dropped]
    out = {"trial": "P1", "label": LABEL, "scoring_date": when, "members": list(MEMBERS),
           "dropped": dropped, "remaining": remaining,
           "member_verdicts": {m: dict(v) for m, v in member_verdicts.items()}}
    if not remaining:
        return {**out, "verdict": VERDICT_NOT_TESTABLE, "row": f"{VERDICT_NOT_TESTABLE}, {LABEL}", "n": 0,
                "newey_west": None, "left_out": []}

    frame, left_out = pool({m: blocks[m] for m in remaining})
    n = len(frame)
    if n < 2:
        raise RuntimeError(f"{n} common period(s) among {', '.join(remaining)}: no row of section 3 covers this; "
                           "a dated decision is needed before anything is published")
    nw = newey_west_mean(frame["P"], lags=LAGS)
    if nw["mean"] > 0 and nw["t"] >= T_BAR:
        verdict = VERDICT_SUPPORTED
    elif nw["t"] <= -T_BAR:
        verdict = VERDICT_REFUTED
    else:
        verdict = VERDICT_INCONCLUSIVE
    span = (pd.to_datetime(frame["period_end"]) - pd.to_datetime(frame["execution_date"])).dt.days
    return {**out, "verdict": verdict, "row": f"{verdict}, {LABEL}", "n": n, "newey_west": nw,
            "mean_P_per_year": nw["mean"] * PERIODS_PER_YEAR,
            "detectable_per_year": K * nw["se"] * PERIODS_PER_YEAR,
            "periods": frame[list(KEY)].to_dict("records"),
            "periods_longer_than_45_days": int((span > LONG_PERIOD_DAYS).sum()),
            "left_out": left_out}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.pool", description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("score",))
    parser.add_argument("--member-verdicts", type=Path, required=True,
                        help="JSON {member: {verdict, scoring_date}} from the members' own score()")
    args = parser.parse_args(argv)
    today = datetime.now(UTC).date().isoformat()
    if RESULT_JSON.exists():
        print(f"refused: {RESULT_JSON.relative_to(STUDY_DIR)} exists; P1 is scored once (section 3)")
        return 1
    try:
        verdicts = json.loads(args.member_verdicts.read_text(encoding="utf-8"))
        trials_text = TRIALS_MD.read_text(encoding="utf-8")
        when = logged_scoring_date(trials_text)
        if when is not None and when > today:
            raise RuntimeError(f"the logged scoring date {when} is after today ({today}, UTC)")
        result = score(read_shadows(), verdicts, trials_text)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"refused: {exc}")
        return 1
    RESULT_JSON.parent.mkdir(exist_ok=True)
    RESULT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{result['verdict']} ({LABEL}); n = {result['n']}; written {RESULT_JSON.relative_to(STUDY_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
