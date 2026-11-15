"""Monthly stock universe: the most-traded stocks as of each month (no survivorship bias).

For a month whose first trading day is d, a stock's score is its average traded value
over the UNIVERSE_LOOKBACK trading days before d (a day with no trade counts as 0).
Stocks are ranked by that score; ranks 1..UNIVERSE_SIZE are the universe and ranks up
to UNIVERSE_BUFFER are kept as a watch list.
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from .config import UNIVERSE_BUFFER, UNIVERSE_LOOKBACK


def build_universe(traded_value: pd.DataFrame, keep: int = UNIVERSE_BUFFER,
                   lookback: int = UNIVERSE_LOOKBACK) -> pd.DataFrame:
    """traded_value: index = trading dates (sorted), columns = symbols, values = rupees (NaN = no trade).

    Returns rows (month, symbol, rank, avg_traded_value) for every month with a full lookback window.
    """
    tv = traded_value.sort_index().fillna(0.0)
    avg = tv.rolling(lookback, min_periods=lookback).mean().shift(1)
    dates = pd.DatetimeIndex(tv.index)
    first_days = pd.Series(dates, index=dates).groupby(dates.to_period("M")).min()
    rows = []
    for period, day in first_days.items():
        scores = avg.loc[day].dropna()
        scores = scores[scores > 0]
        if scores.empty:
            continue
        top = scores.nlargest(keep)
        month = str(period)
        rows.extend((month, sym, rank, float(val)) for rank, (sym, val) in enumerate(top.items(), start=1))
    return pd.DataFrame(rows, columns=["month", "symbol", "rank", "avg_traded_value"])


def refresh_universe_from_db(con: sqlite3.Connection, from_month: str) -> int:
    """Recompute universe months >= from_month using traded values stored in the database.

    Stocks stored in the database include every stock ever ranked within the buffer, so the
    top of each month's ranking is the same as a computation over all NSE stocks.
    """
    start = (pd.Period(from_month, "M").start_time - pd.Timedelta(days=150)).strftime("%Y-%m-%d")
    df = pd.read_sql_query("SELECT date, symbol, traded_value FROM prices WHERE date >= ?", con, params=(start,))
    if df.empty:
        return 0
    wide = df.pivot(index="date", columns="symbol", values="traded_value")
    wide.index = pd.to_datetime(wide.index)
    uni = build_universe(wide)
    uni = uni[uni["month"] >= from_month]
    con.execute("DELETE FROM universe WHERE month >= ?", (from_month,))
    con.executemany("INSERT INTO universe(month, symbol, rank, avg_traded_value) VALUES (?, ?, ?, ?)",
                    uni.itertuples(index=False, name=None))
    return len(uni)
