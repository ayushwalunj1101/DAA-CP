"""Market Overview and Momentum Scanner (phase 2)."""
from __future__ import annotations

import sqlite3
from collections import Counter

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

import daa_core
from pipeline.signals import DEFAULT_WEIGHTS, PCT_FIELDS

from .deps import read_connection
from .util import clean

router = APIRouter(prefix="/api")

CLASS_NAMES = {2: "ESTABLISHED_BULLISH", 1: "DEVELOPING_BULLISH", 0: "NEUTRAL", -1: "DEVELOPING_BEARISH",
               -2: "ESTABLISHED_BEARISH"}
CLASS_CODES = {v: k for k, v in CLASS_NAMES.items()}
QUADRANT_NAMES = {0: "ACCUMULATION", 1: "WEAK_RALLY", 2: "DISTRIBUTION", 3: "WEAK_SELLOFF", -1: None}


def signal_dates(con: sqlite3.Connection) -> list[str]:
    return [r[0] for r in con.execute("SELECT date FROM daily_stats ORDER BY date")]


def resolve_date(con: sqlite3.Connection, date: str | None) -> tuple[str, str | None]:
    """The latest signal day on or before `date` (binary search), and the signal day before it."""
    dates = signal_dates(con)
    if not dates:
        raise HTTPException(503, "No signals yet; run python -m pipeline.signals")
    i = daa_core.last_at_or_before(dates, date or dates[-1])
    if i < 0:
        raise HTTPException(404, f"No signals on or before {date}")
    return dates[i], dates[i - 1] if i > 0 else None


def parse_weights(w: str | None) -> list[float]:
    if not w:
        return DEFAULT_WEIGHTS
    try:
        weights = [float(x) for x in w.split(",")]
    except ValueError:
        raise HTTPException(422, "w must be five comma-separated numbers") from None
    if len(weights) != 5 or any(x < 0 for x in weights) or sum(weights) <= 0:
        raise HTTPException(422, "w must be five non-negative numbers with a positive sum")
    return weights


def day_view(con: sqlite3.Connection, date: str, weights: list[float]) -> pd.DataFrame:
    """Every scored stock on `date` with class, scores and ranks for the given weights."""
    df = pd.read_sql_query(
        "SELECT g.*, s.sector FROM signals g JOIN stocks s USING(symbol) WHERE g.date = ? ORDER BY g.symbol",
        con, params=(date,))
    if weights != DEFAULT_WEIGHTS and not df.empty:
        r = daa_core.rescore_day({p: df[p].to_numpy() for p in PCT_FIELDS}, df["flags"].tolist(),
                                 df["quadrant"].tolist(), weights)
        df["cls"] = r["cls"]
        df["bull_score"] = r["bull_score"]
        df["bear_score"] = r["bear_score"]
        for side in ("bull", "bear"):
            rank = np.full(len(df), -1)
            order = r[f"{side}_order"]
            rank[order] = np.arange(1, len(order) + 1)
            df[f"{side}_rank"] = rank
    return df


@router.get("/overview")
def overview(date: str | None = None, con: sqlite3.Connection = Depends(read_connection)) -> dict:
    day, _ = resolve_date(con, date)
    stats = con.execute("SELECT * FROM daily_stats WHERE date = ?", (day,)).fetchone()
    cols = [c[1] for c in con.execute("PRAGMA table_info(daily_stats)")]
    st = dict(zip(cols, stats))
    counts = {CLASS_NAMES[k]: st[c] for k, c in
              {2: "est_bull", 1: "dev_bull", 0: "neutral", -1: "dev_bear", -2: "est_bear"}.items()}
    # Sector breakdown: a hash map keyed by (sector, class).
    tally = Counter(con.execute("SELECT s.sector, g.cls FROM signals g JOIN stocks s USING(symbol) WHERE g.date = ?",
                                (day,)).fetchall())
    sectors = sorted({sec for sec, _ in tally})
    sector_rows = [{"sector": sec, "counts": {CLASS_NAMES[k]: tally.get((sec, k), 0) for k in CLASS_NAMES},
                    "total": sum(tally.get((sec, k), 0) for k in CLASS_NAMES)} for sec in sectors]
    sector_rows.sort(key=lambda r: -r["total"])
    nifty = con.execute("SELECT date, close FROM indices WHERE name = 'NIFTY50' AND date <= ? ORDER BY date DESC "
                        "LIMIT 250", (day,)).fetchall()[::-1]
    inv, pairs = st["churn_inversions"], st["churn_pairs"]
    return {
        "date": day,
        "stocks_scanned": st["scanned"],
        "counts": counts,
        "sectors": sector_rows,
        "nifty": [{"date": d, "close": c} for d, c in nifty],
        "rank_churn": {"inversions": inv, "max_inversions": pairs,
                       "pct": round(100 * inv / pairs, 2) if inv is not None and pairs else None},
        "cutoffs": {k: clean(st[k]) for k in ("bull_cut_est", "bull_cut_dev", "bear_cut_est", "bear_cut_dev")},
    }


@router.get("/scanner")
def scanner(date: str | None = None, side: str = Query("bullish", pattern="^(bullish|bearish)$"),
            cls: str | None = None, sector: str | None = None, k: int = Query(20, ge=1, le=500),
            w: str | None = None, con: sqlite3.Connection = Depends(read_connection)) -> dict:
    day, prev = resolve_date(con, date)
    weights = parse_weights(w)
    today = day_view(con, day, weights)
    s = "bull" if side == "bullish" else "bear"
    wanted = {2, 1} if side == "bullish" else {-2, -1}
    if cls:
        code = CLASS_CODES.get(cls.upper())
        if code is None:
            raise HTTPException(422, f"Unknown class {cls}")
        wanted = {code}
    rows = today[today["cls"].isin(wanted)]
    if sector:
        rows = rows[rows["sector"] == sector.upper()]
    rows = rows.sort_values(f"{s}_rank").head(k)
    prev_rank: dict[str, int] = {}
    if prev:
        yesterday = day_view(con, prev, weights)
        prev_rank = dict(zip(yesterday["symbol"], yesterday[f"{s}_rank"]))
    out = []
    for r in rows.itertuples():
        rank = int(getattr(r, f"{s}_rank"))
        before = prev_rank.get(r.symbol)
        out.append({
            "rank": rank, "symbol": r.symbol, "sector": r.sector, "cls": CLASS_NAMES[int(r.cls)],
            "score": round(float(getattr(r, f"{s}_score")), 2),
            "rank_change": None if before is None else int(before) - rank,
            "quadrant": QUADRANT_NAMES[int(r.quadrant)], "close": float(r.close),
            "change_pct": clean(r.change_pct),
        })
    return {"date": day, "side": side, "weights": weights, "rows": out}
