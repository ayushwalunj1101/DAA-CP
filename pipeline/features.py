"""Per-stock features: loads bars from SQLite and runs the C++ feature engine and trend tests.

pandas is used here only to load and align data; every computation happens in daa_core.
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

import daa_core

TREND_WINDOWS = (20, 60)
TREND_FIELDS = ("mk_s", "mk_z", "lis_ratio", "lds_ratio", "up_days", "down_days", "sign_p_up", "sign_p_down")


def load_bars(con: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM prices WHERE symbol = ? ORDER BY date", con, params=(symbol,))


def load_index(con: sqlite3.Connection, name: str = "NIFTY50") -> pd.Series:
    df = pd.read_sql_query("SELECT date, close FROM indices WHERE name = ? ORDER BY date", con, params=(name,))
    return df.set_index("date")["close"]


def align_index(dates: pd.Series, index_close: pd.Series) -> np.ndarray:
    """Index close on each of the stock's dates (last known value if the index has no bar that day)."""
    union = index_close.index.union(pd.Index(dates)).sort_values()
    return index_close.reindex(union).ffill().reindex(dates).to_numpy(dtype=float)


def compute_frame(bars: pd.DataFrame, index_close: np.ndarray) -> pd.DataFrame:
    """Bars plus every feature and both trend windows, one row per trading day."""
    arrays = {c: bars[c].to_numpy(dtype=float) for c in ("open", "high", "low", "close", "volume")}
    feats = daa_core.compute_features(arrays["open"], arrays["high"], arrays["low"], arrays["close"],
                                      arrays["volume"], index_close)
    out = {"date": bars["date"].to_numpy()}
    out.update(feats)
    for w in TREND_WINDOWS:
        trend = daa_core.rolling_trend(arrays["close"], w)
        for field in TREND_FIELDS:
            out[f"{field}{w}"] = trend[field]
    return pd.DataFrame(out)


def stock_frame(con: sqlite3.Connection, symbol: str, index_close: pd.Series | None = None) -> pd.DataFrame:
    bars = load_bars(con, symbol)
    if bars.empty:
        raise KeyError(symbol)
    if index_close is None:
        index_close = load_index(con)
    return compute_frame(bars, align_index(bars["date"], index_close))
