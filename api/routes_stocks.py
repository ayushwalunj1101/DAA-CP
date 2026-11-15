"""Symbols (Ctrl+K search) and single-stock analysis."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

import daa_core
from pipeline.config import UNIVERSE_SIZE
from pipeline.features import stock_frame

from .deps import read_connection
from .util import clean, records

router = APIRouter(prefix="/api")

INDICATOR_COLUMNS = ["ema20", "ema50", "ema200", "vwap20", "rsi14", "atr14", "rvol20", "high20", "low20", "vol_spike"]
TREND_COLUMNS = ["mk_z20", "mk_z60", "lis_ratio60", "lds_ratio60", "up_days60", "down_days60", "sign_p_up60",
                 "sign_p_down60"]


def universe_symbols(con: sqlite3.Connection) -> list[tuple[str, str]]:
    month = con.execute("SELECT MAX(month) FROM universe").fetchone()[0]
    return con.execute(
        "SELECT u.symbol, s.sector FROM universe u JOIN stocks s USING(symbol) "
        "WHERE u.month = ? AND u.rank <= ? ORDER BY u.symbol", (month, UNIVERSE_SIZE)).fetchall()


@router.get("/symbols")
def symbols(q: str = "", con: sqlite3.Connection = Depends(read_connection)) -> dict:
    rows = universe_symbols(con)
    names = [r[0] for r in rows]
    first, last = daa_core.prefix_range(names, q.strip().upper())  # binary search on the sorted list
    return {"symbols": [{"symbol": s, "sector": sec} for s, sec in rows[first:last]]}


@router.get("/stocks/{symbol}")
def stock(symbol: str, start: str | None = Query(None, alias="from"), end: str | None = Query(None, alias="to"),
          con: sqlite3.Connection = Depends(read_connection)) -> dict:
    symbol = symbol.upper()
    row = con.execute("SELECT sector FROM stocks WHERE symbol = ?", (symbol,)).fetchone()
    if not row:
        raise HTTPException(404, f"Unknown symbol {symbol}")
    frame = stock_frame(con, symbol)
    dates = frame["date"].tolist()
    end = end or dates[-1]
    start = start or dates[max(0, daa_core.last_at_or_before(dates, end) - 250)]
    first, last = daa_core.date_range(dates, start, end)  # binary search for both ends
    if first >= last:
        raise HTTPException(404, f"No bars for {symbol} between {start} and {end}")
    part = frame.iloc[first:last]
    latest = part.iloc[-1]
    return {
        "symbol": symbol,
        "sector": row[0],
        "bars": records({c: part[c] for c in ("date", "open", "high", "low", "close", "volume")}),
        "indicators": records({c: part[c] for c in ["date", *INDICATOR_COLUMNS]}),
        "trend": {c: clean(latest[c]) for c in TREND_COLUMNS},
        "classification": classification(con, symbol, latest),
        "as_of": latest["date"],
    }


def _fmt(v, digits=2) -> str:
    return "n/a" if v is None or v != v else f"{v:.{digits}f}"


def classification(con: sqlite3.Connection, symbol: str, f) -> dict | None:
    """Class, scores and the rule checks behind them, for the stock's latest bar in the requested range."""
    from .routes_market import CLASS_NAMES, QUADRANT_NAMES

    sig = con.execute("SELECT cls, bull_score, bear_score, quadrant, bull_rank, bear_rank, p_trend, p_cons_bull, "
                      "p_cons_bear, p_rs, p_volume, p_vwap FROM signals WHERE date = ? AND symbol = ?",
                      (f["date"], symbol)).fetchone()
    if not sig:
        return None
    cls, bull, bear, quad, bull_rank, bear_rank, p_tr, p_cb, p_cr, p_rs, p_vol, p_vw = sig
    cuts = con.execute("SELECT bull_cut_est, bull_cut_dev, bear_cut_est, bear_cut_dev, scanned FROM daily_stats "
                       "WHERE date = ?", (f["date"],)).fetchone()
    bullish_side = cls > 0 or (cls == 0 and bull >= bear)
    c, e50, e200 = f["close"], f["ema50"], f["ema200"]
    if bullish_side:
        up, dn = f["up_days60"], f["down_days60"]
        checks = [
            ("60-day trend Z ≥ 1.96", f["mk_z60"] >= 1.96, _fmt(f["mk_z60"])),
            ("Close > EMA 50 > EMA 200", c > e50 > e200, f"{_fmt(c, 1)} / {_fmt(e50, 1)} / {_fmt(e200, 1)}"),
            ("Sign test significant (60 days)", f["sign_p_up60"] < 0.05,
             f"up {int(up)} of {int(up + dn)}, p = {_fmt(f['sign_p_up60'], 3)}"),
            ("Score in top 10%", bull >= cuts[0], f"{bull:.1f} (cut-off {cuts[0]:.1f})"),
            ("20-day trend Z ≥ 1.96", f["mk_z20"] >= 1.96, _fmt(f["mk_z20"])),
            ("20-day breakout with accumulation", c > f["high20"] and quad == 0,
             f"close {_fmt(c, 1)} vs high {_fmt(f['high20'], 1)}"),
            ("Score in top 25%", bull >= cuts[1], f"{bull:.1f} (cut-off {cuts[1]:.1f})"),
        ]
    else:
        up, dn = f["up_days60"], f["down_days60"]
        checks = [
            ("60-day trend Z ≤ −1.96", f["mk_z60"] <= -1.96, _fmt(f["mk_z60"])),
            ("Close < EMA 50 < EMA 200", c < e50 < e200, f"{_fmt(c, 1)} / {_fmt(e50, 1)} / {_fmt(e200, 1)}"),
            ("Sign test significant (60 days)", f["sign_p_down60"] < 0.05,
             f"down {int(dn)} of {int(up + dn)}, p = {_fmt(f['sign_p_down60'], 3)}"),
            ("Score in top 10%", bear >= cuts[2], f"{bear:.1f} (cut-off {cuts[2]:.1f})"),
            ("20-day trend Z ≤ −1.96", f["mk_z20"] <= -1.96, _fmt(f["mk_z20"])),
            ("20-day breakdown with distribution", c < f["low20"] and quad == 2,
             f"close {_fmt(c, 1)} vs low {_fmt(f['low20'], 1)}"),
            ("Score in top 25%", bear >= cuts[3], f"{bear:.1f} (cut-off {cuts[3]:.1f})"),
        ]
    return {
        "cls": CLASS_NAMES[cls], "bull_score": round(bull, 2), "bear_score": round(bear, 2),
        "bull_rank": bull_rank, "bear_rank": bear_rank, "scanned": cuts[4],
        "quadrant": QUADRANT_NAMES[quad], "side": "bullish" if bullish_side else "bearish",
        # Percentile (0-100) of each score input, oriented for the side shown.
        "inputs": [
            {"key": "trend", "label": "Trend strength (Mann–Kendall)", "pct": round(p_tr if bullish_side else 100 - p_tr, 1)},
            {"key": "consistency", "label": "Trend consistency (LIS)", "pct": round(p_cb if bullish_side else p_cr, 1)},
            {"key": "rs", "label": "Relative strength vs Nifty", "pct": round(p_rs if bullish_side else 100 - p_rs, 1)},
            {"key": "volume", "label": "Volume confirmation", "pct": round(p_vol if bullish_side else 100 - p_vol, 1)},
            {"key": "vwap", "label": "Position vs VWAP", "pct": round(p_vw if bullish_side else 100 - p_vw, 1)},
        ],
        "checks": [{"label": lbl, "passed": bool(ok), "value": val} for lbl, ok, val in checks],
    }
