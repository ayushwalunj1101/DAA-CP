"""One-time import of the local NSE history (E:\\Algo Trading) into SQLite.

Run from the project root:
    python -m pipeline.import_local

Steps:
  1. Read adjusted daily bars, keep the EQ series, drop rows flagged as bad data.
  2. Build the monthly universe from traded value (all stocks, so no survivorship bias).
  3. Store full price history for every stock that was ever ranked within the buffer.
  4. Store sectors, index closes, holidays and metadata.
Rows previously added by the FYERS updater are kept; local rows are replaced.
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime

import pandas as pd
import pyarrow.parquet as pq

from . import db
from .config import DB_PATH, LOCAL_FILES
from .universe import build_universe

PRICE_COLUMNS = ["date", "symbol", "isin", "series", "adj_open", "adj_high", "adj_low", "adj_close",
                 "adj_volume", "turnover", "quarantined"]


def load_prices() -> pd.DataFrame:
    table = pq.read_table(LOCAL_FILES["prices"], columns=PRICE_COLUMNS)
    df = table.to_pandas()
    total = len(df)
    df = df[(df["series"] == "EQ") & (~df["quarantined"])]
    df = df.dropna(subset=["adj_open", "adj_high", "adj_low", "adj_close", "adj_volume", "turnover"])
    df = df[(df["adj_close"] > 0) & (df["adj_high"] >= df["adj_low"])]
    print(f"  prices: {total:,} rows read, {len(df):,} kept (EQ series, not flagged, valid)")
    return df


def load_sectors() -> dict[str, str]:
    s = pd.read_parquet(LOCAL_FILES["sectors"])
    return {sym: sec for sym, sec in s["sector"].dropna().items()}


def load_indices() -> pd.DataFrame:
    wide = pd.read_parquet(LOCAL_FILES["indices"])
    wide.index = pd.to_datetime(wide.index)
    long = wide.stack().reset_index()
    long.columns = ["date", "name", "close"]
    long["date"] = long["date"].dt.strftime("%Y-%m-%d")
    return long[["name", "date", "close"]]


def load_holidays() -> pd.DataFrame:
    h = pd.read_csv(LOCAL_FILES["holidays"])
    h = h[h["kind"].str.lower() == "holiday"]
    return h[["date", "occasion"]]


def run(db_path=DB_PATH) -> dict:
    t0 = time.time()
    print("Reading local files ...")
    prices = load_prices()

    print("Building monthly universe ...")
    wide = prices.pivot(index="date", columns="symbol", values="turnover")
    universe = build_universe(wide)
    keep = set(universe["symbol"])
    months = universe["month"].nunique()
    print(f"  {months} months, {len(keep):,} distinct stocks ever ranked within the buffer")

    prices = prices[prices["symbol"].isin(keep)].copy()
    prices["date"] = prices["date"].dt.strftime("%Y-%m-%d")
    sectors = load_sectors()
    latest_isin = prices.sort_values("date").groupby("symbol")["isin"].last()
    stocks = pd.DataFrame({"symbol": sorted(keep)})
    stocks["isin"] = stocks["symbol"].map(latest_isin)
    stocks["sector"] = stocks["symbol"].map(sectors).fillna("OTHER")
    indices = load_indices()
    holidays = load_holidays()

    print("Writing SQLite ...")
    with db.session(db_path) as con:
        con.execute("DELETE FROM prices WHERE source = 'local'")
        for table in ("universe", "stocks", "indices", "holidays"):
            con.execute(f"DELETE FROM {table}")
        con.executemany("INSERT INTO stocks(symbol, isin, sector) VALUES (?, ?, ?)",
                        stocks.itertuples(index=False, name=None))
        rows = prices[["symbol", "date", "adj_open", "adj_high", "adj_low", "adj_close", "adj_volume", "turnover"]]
        con.executemany(
            "INSERT OR REPLACE INTO prices(symbol, date, open, high, low, close, volume, traded_value, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'local')",
            rows.itertuples(index=False, name=None),
        )
        con.executemany("INSERT INTO universe(month, symbol, rank, avg_traded_value) VALUES (?, ?, ?, ?)",
                        universe.itertuples(index=False, name=None))
        con.executemany("INSERT INTO indices(name, date, close) VALUES (?, ?, ?)",
                        indices.itertuples(index=False, name=None))
        con.executemany("INSERT INTO holidays(date, occasion) VALUES (?, ?)",
                        holidays.itertuples(index=False, name=None))
        db.set_meta(con, "local_start", prices["date"].min())
        db.set_meta(con, "local_end", prices["date"].max())
        db.set_meta(con, "imported_at", datetime.now().isoformat(timespec="seconds"))

    summary = {
        "price_rows": len(prices),
        "stocks": len(stocks),
        "sectors_mapped": int((stocks["sector"] != "OTHER").sum()),
        "universe_months": months,
        "index_rows": len(indices),
        "holidays": len(holidays),
        "first_date": prices["date"].min(),
        "last_date": prices["date"].max(),
        "seconds": round(time.time() - t0, 1),
    }
    for k, v in summary.items():
        print(f"  {k}: {v:,}" if isinstance(v, int) else f"  {k}: {v}")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DB_PATH), help="SQLite file to write (default: data/momentum.db)")
    args = ap.parse_args()
    run(args.db)
