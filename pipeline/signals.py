"""Daily classification and ranking of the universe (phase 2), stored for the app and the backtest.

Run from the project root:
    python -m pipeline.signals                 # rebuild every day from 2013-01-01
    python -m pipeline.signals --since-last    # only days after the last stored day (daily use)

For each trading day the C++ classifier converts every input to a percentile rank across the
day's universe (merge sort), combines them into bullish and bearish scores, applies the class
rules and ranks the stocks. Rank change between consecutive days is the number of inversions
between the two rankings.
"""
from __future__ import annotations

import argparse
import sqlite3
import time
from collections import defaultdict

import numpy as np
import pandas as pd

import daa_core

from . import db
from .config import DB_PATH, UNIVERSE_SIZE
from .features import load_index, stock_frame

SIGNAL_START = "2013-01-01"
DEFAULT_WEIGHTS = [1.0, 1.0, 1.0, 1.0, 1.0]
INPUTS = ["close", "ema50", "ema200", "high20", "low20", "mk_z20", "mk_z60", "lis_ratio60", "lds_ratio60",
          "sign_p_up60", "sign_p_down60", "rs60", "updown_vol20", "vwap_dist", "ret5", "rvol5_avg"]
EXTRA = ["ret1", "atr14"]
PCT_FIELDS = ["p_trend", "p_cons_bull", "p_cons_bear", "p_rs", "p_volume", "p_vwap"]
CLASS_COLUMNS = {2: "est_bull", 1: "dev_bull", 0: "neutral", -1: "dev_bear", -2: "est_bear"}


def member_months(con: sqlite3.Connection, start: str, end: str) -> dict[str, set[str]]:
    rows = con.execute("SELECT symbol, month FROM universe WHERE rank <= ? AND month BETWEEN ? AND ?",
                       (UNIVERSE_SIZE, start[:7], end[:7])).fetchall()
    out: dict[str, set[str]] = defaultdict(set)
    for sym, month in rows:
        out[sym].add(month)
    return out


def collect_inputs(con: sqlite3.Connection, start: str, end: str, log=print) -> pd.DataFrame:
    """One row per (day, stock) for stocks in that month's universe, with every classifier input."""
    members = member_months(con, start, end)
    index_close = load_index(con)
    parts = []
    t0 = time.time()
    for i, (sym, months) in enumerate(sorted(members.items()), 1):
        f = stock_frame(con, sym, index_close)
        f = f[(f["date"] >= start) & (f["date"] <= end)]
        f = f[f["date"].str[:7].isin(months)]
        if not f.empty:
            part = f[["date", *INPUTS, *EXTRA]].copy()
            part.insert(1, "symbol", sym)
            parts.append(part)
        if i % 250 == 0:
            log(f"  features: {i}/{len(members)} stocks ({time.time() - t0:.0f}s)")
    if not parts:
        return pd.DataFrame(columns=["date", "symbol", *INPUTS, *EXTRA])
    return pd.concat(parts, ignore_index=True).sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)


def classify_days(data: pd.DataFrame, prev_ranking: list[str] | None = None, weights=DEFAULT_WEIGHTS):
    """Classify every day in `data`. Returns (signal rows, daily stats rows)."""
    signal_rows, stat_rows = [], []
    for day, g in data.groupby("date", sort=True):
        inputs = {c: g[c].to_numpy(dtype=float) for c in INPUTS}
        r = daa_core.classify_day(inputs, weights)
        syms = g["symbol"].to_numpy()
        bull_rank = np.full(len(g), -1)
        bear_rank = np.full(len(g), -1)
        bull_rank[r["bull_order"]] = np.arange(1, len(r["bull_order"]) + 1)
        bear_rank[r["bear_order"]] = np.arange(1, len(r["bear_order"]) + 1)
        ranking = [syms[i] for i in r["bull_order"]]

        inversions = pairs = None
        if prev_ranking:
            common = set(prev_ranking) & set(ranking)
            ids = {s: k for k, s in enumerate(sorted(common))}
            before = [ids[s] for s in prev_ranking if s in common]
            after = [ids[s] for s in ranking if s in common]
            inversions = daa_core.ranking_distance(before, after)
            pairs = len(common) * (len(common) - 1) // 2
        prev_ranking = ranking

        cls = np.asarray(r["cls"])
        scored = ~np.isnan(r["bull_score"])
        counts = {v: int(((cls == k) & scored).sum()) for k, v in CLASS_COLUMNS.items()}
        stat_rows.append((day, int(scored.sum()), counts["est_bull"], counts["dev_bull"], counts["neutral"],
                          counts["dev_bear"], counts["est_bear"], r["bull_cut_est"], r["bull_cut_dev"],
                          r["bear_cut_est"], r["bear_cut_dev"], inversions, pairs))
        ret1, atr = g["ret1"].to_numpy(), g["atr14"].to_numpy()
        close = g["close"].to_numpy()
        for i in np.flatnonzero(scored):
            signal_rows.append((
                day, syms[i], int(cls[i]), int(r["quadrant"][i]), int(r["flags"][i]),
                float(r["bull_score"][i]), float(r["bear_score"][i]), int(bull_rank[i]), int(bear_rank[i]),
                *(float(r[p][i]) for p in PCT_FIELDS),
                float(close[i]), None if np.isnan(ret1[i]) else float(ret1[i]),
                None if np.isnan(atr[i]) else float(atr[i]),
            ))
    return signal_rows, stat_rows


def previous_ranking(con: sqlite3.Connection, before: str) -> list[str] | None:
    row = con.execute("SELECT MAX(date) FROM signals WHERE date < ?", (before,)).fetchone()
    if not row or not row[0]:
        return None
    return [r[0] for r in con.execute("SELECT symbol FROM signals WHERE date = ? ORDER BY bull_rank", (row[0],))]


def build(con: sqlite3.Connection, start: str = SIGNAL_START, end: str | None = None, log=print) -> dict:
    t0 = time.time()
    end = end or con.execute("SELECT MAX(date) FROM prices").fetchone()[0]
    if start > end:
        log("Signals already up to date.")
        return {"days": 0, "rows": 0}
    log(f"Computing features for universe members, {start} to {end} ...")
    data = collect_inputs(con, start, end, log)
    log(f"Classifying {data['date'].nunique()} days ({len(data):,} stock-days) ...")
    sig, stats = classify_days(data, previous_ranking(con, start))
    con.execute("DELETE FROM signals WHERE date BETWEEN ? AND ?", (start, end))
    con.execute("DELETE FROM daily_stats WHERE date BETWEEN ? AND ?", (start, end))
    con.executemany(f"INSERT INTO signals VALUES ({','.join('?' * 18)})", sig)
    con.executemany(f"INSERT INTO daily_stats VALUES ({','.join('?' * 13)})", stats)
    summary = {"days": len(stats), "rows": len(sig), "seconds": round(time.time() - t0, 1)}
    log(f"  stored {summary['rows']:,} signals for {summary['days']} days in {summary['seconds']}s")
    return summary


def build_since_last(con: sqlite3.Connection, log=print) -> dict:
    last = con.execute("SELECT MAX(date) FROM signals").fetchone()[0]
    if not last:
        return build(con, log=log)
    nxt = con.execute("SELECT MIN(date) FROM prices WHERE date > ?", (last,)).fetchone()[0]
    if not nxt:
        log("Signals already up to date.")
        return {"days": 0, "rows": 0}
    return build(con, start=nxt, log=log)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since-last", action="store_true", help="only classify days after the last stored day")
    ap.add_argument("--start", default=SIGNAL_START)
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()
    with db.session(args.db) as con:
        build_since_last(con) if args.since_last else build(con, start=args.start)
