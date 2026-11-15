"""Paths and settings shared by the pipeline, the API and the tests."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("MOMENTUM_DB", DATA_DIR / "momentum.db"))

# Local history built earlier in E:\Algo Trading (read-only for this project).
LOCAL_ROOT = Path(os.environ.get("ALGO_TRADING_ROOT", r"E:\Algo Trading"))
LOCAL_FILES = {
    "prices": LOCAL_ROOT / "data" / "processed" / "daily_adjusted.parquet",
    "indices": LOCAL_ROOT / "etf_lab" / "data" / "index_daily.parquet",
    "sectors": LOCAL_ROOT / "combo_lab" / "cache" / "exp73_sector_map.parquet",
    "holidays": LOCAL_ROOT / "swing_lab" / "nse_holidays.csv",
}

# Stock universe: each month, the top UNIVERSE_SIZE stocks by average traded value
# over the previous UNIVERSE_LOOKBACK trading days. Ranks up to UNIVERSE_BUFFER are
# stored too, so the daily updater also tracks stocks just outside the universe.
UNIVERSE_SIZE = 500
UNIVERSE_BUFFER = 650
UNIVERSE_LOOKBACK = 60

# Daily update sanity check: an overnight move bigger than this is flagged.
JUMP_FLAG_PCT = 30.0

# FYERS settings come from the user's environment (set by fyers_auth/fyers_login.py).
FYERS_APP_ID_ENV = "FYERS_APP_ID"
FYERS_TOKEN_FILE_ENV = "FYERS_TOKEN_FILE"
FYERS_MAX_REQ_PER_SEC = 3.0  # FYERS allows 10/s and 200/min; stay well below both.

# Indices kept current through FYERS (local name -> FYERS symbol).
FYERS_INDEX_SYMBOLS = {
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "NIFTY500": "NSE:NIFTY500-INDEX",
    "VIX": "NSE:INDIAVIX-INDEX",
}
