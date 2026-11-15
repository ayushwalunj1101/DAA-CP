"""Daily update from the FYERS API: fills every trading day after the last stored date.

Run from the project root after logging in to FYERS for the day
(python -B "E:\\Algo Trading\\fyers_auth\\fyers_login.py" login):
    python -m pipeline.fyers_update            # update to the latest finished trading day
    python -m pipeline.fyers_update --limit 5  # quick check with 5 stocks
    python -m pipeline.fyers_update --dry-run  # fetch and report, write nothing

Which stocks: every stock ranked within the buffer (top 650) in the latest universe month.
Traded value for FYERS rows is close x volume (FYERS daily candles carry no turnover).
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

import pandas as pd

from . import db
from .config import (DB_PATH, FYERS_APP_ID_ENV, FYERS_INDEX_SYMBOLS, FYERS_MAX_REQ_PER_SEC, FYERS_TOKEN_FILE_ENV,
                     JUMP_FLAG_PCT, UNIVERSE_BUFFER)
from .universe import refresh_universe_from_db

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_CLOSE_IST = (15, 30)

Candle = tuple[str, float, float, float, float, float]  # (date, open, high, low, close, volume)


class AuthError(RuntimeError):
    """The FYERS token is missing or no longer valid."""


class CandleSource(Protocol):
    def daily_candles(self, fyers_symbol: str, start: str, end: str) -> list[Candle]: ...


def fyers_symbol(symbol: str) -> str:
    return f"NSE:{symbol}-EQ"


class RateLimiter:
    def __init__(self, per_second: float):
        self.interval = 1.0 / per_second
        self._next = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        if now < self._next:
            time.sleep(self._next - now)
        self._next = max(now, self._next) + self.interval


def _user_setting(name: str) -> str | None:
    """Read a setting from the process environment, falling back to the Windows user environment."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, name)[0]
    except (ImportError, OSError):
        return None


class FyersSource:
    """Daily candles from the FYERS history API, rate-limited."""

    AUTH_CODES = {-8, -15, -16, -17, -300}

    def __init__(self) -> None:
        from fyers_apiv3 import fyersModel

        app_id = _user_setting(FYERS_APP_ID_ENV)
        token_file = _user_setting(FYERS_TOKEN_FILE_ENV) or str(Path.home() / ".fyers" / "access_token.txt")
        if not app_id:
            raise AuthError(f"{FYERS_APP_ID_ENV} is not set. Run fyers_login.py setup first.")
        if not Path(token_file).exists():
            raise AuthError("No FYERS token file. Run fyers_login.py login first.")
        token = Path(token_file).read_text(encoding="utf-8").strip()
        log_dir = Path(os.environ.get("TEMP", ".")) / "fyers_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.client = fyersModel.FyersModel(client_id=app_id, token=token, is_async=False, log_path=str(log_dir))
        self.limiter = RateLimiter(FYERS_MAX_REQ_PER_SEC)

    def daily_candles(self, fyers_sym: str, start: str, end: str) -> list[Candle]:
        out: list[Candle] = []
        chunk_start = date.fromisoformat(start)
        last = date.fromisoformat(end)
        while chunk_start <= last:  # the API returns at most 366 days per daily request
            chunk_end = min(last, chunk_start + timedelta(days=365))
            self.limiter.wait()
            resp = self.client.history(data={
                "symbol": fyers_sym, "resolution": "D", "date_format": "1",
                "range_from": chunk_start.isoformat(), "range_to": chunk_end.isoformat(), "cont_flag": "1",
            })
            if resp.get("s") != "ok":
                code = resp.get("code")
                msg = str(resp.get("message", ""))
                if code in self.AUTH_CODES or "token" in msg.lower() or "auth" in msg.lower():
                    raise AuthError(f"FYERS refused the token ({code}: {msg}). Log in again for today.")
                if resp.get("s") == "no_data":
                    break
                raise RuntimeError(f"{fyers_sym}: {code} {msg}")
            for ts, o, h, lo, c, v in resp.get("candles", []):
                day = datetime.fromtimestamp(ts, IST).date().isoformat()
                out.append((day, float(o), float(h), float(lo), float(c), float(v)))
            chunk_start = chunk_end + timedelta(days=1)
        return out


@dataclass
class UpdateReport:
    start: str = ""
    end: str = ""
    stocks_requested: int = 0
    stocks_updated: int = 0
    rows_added: int = 0
    index_rows_added: int = 0
    flags: list[tuple[str, str, float]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    universe_rows: int = 0


def latest_finished_day(now: datetime | None = None) -> date:
    now = now or datetime.now(IST)
    today = now.date()
    if (now.hour, now.minute) >= MARKET_CLOSE_IST:
        return today
    return today - timedelta(days=1)


def trading_days(con: sqlite3.Connection, start: date, end: date) -> list[str]:
    holidays = {r[0] for r in con.execute("SELECT date FROM holidays")}
    days, d = [], start
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in holidays:
            days.append(d.isoformat())
        d += timedelta(days=1)
    return days


def symbols_to_update(con: sqlite3.Connection) -> list[str]:
    month = con.execute("SELECT MAX(month) FROM universe").fetchone()[0]
    rows = con.execute("SELECT symbol FROM universe WHERE month = ? AND rank <= ? ORDER BY rank",
                       (month, UNIVERSE_BUFFER)).fetchall()
    return [r[0] for r in rows]


def _last_close(con: sqlite3.Connection, symbol: str) -> tuple[str, float] | None:
    return con.execute("SELECT date, close FROM prices WHERE symbol = ? ORDER BY date DESC LIMIT 1",
                       (symbol,)).fetchone()


def update(con: sqlite3.Connection, source: CandleSource, until: date | None = None, limit: int | None = None,
           dry_run: bool = False, log=print) -> UpdateReport:
    rep = UpdateReport()
    last_stored = con.execute("SELECT MAX(date) FROM prices").fetchone()[0]
    start = date.fromisoformat(last_stored) + timedelta(days=1)
    end = until or latest_finished_day()
    rep.start, rep.end = start.isoformat(), end.isoformat()
    if not trading_days(con, start, end):
        log(f"Already up to date (last stored day {last_stored}).")
        return rep

    symbols = symbols_to_update(con)
    if limit:
        symbols = symbols[:limit]
    rep.stocks_requested = len(symbols)
    log(f"Fetching {len(symbols)} stocks and {len(FYERS_INDEX_SYMBOLS)} indices, {rep.start} to {rep.end} ...")

    for i, sym in enumerate(symbols, 1):
        prev = _last_close(con, sym)
        fetch_from = (date.fromisoformat(prev[0]) + timedelta(days=1)).isoformat() if prev else rep.start
        try:
            candles = source.daily_candles(fyers_symbol(sym), fetch_from, rep.end)
        except AuthError:
            raise
        except Exception as exc:  # one bad symbol must not stop the update
            rep.errors.append(f"{sym}: {exc}")
            continue
        candles = sorted(c for c in candles if c[0] >= fetch_from and c[4] > 0)
        if not candles:
            continue
        prev_close = prev[1] if prev else None
        rows = []
        for day, o, h, lo, c, v in candles:
            if prev_close:
                change = (c / prev_close - 1.0) * 100.0
                if abs(change) > JUMP_FLAG_PCT:
                    rep.flags.append((sym, day, round(change, 1)))
                    if not dry_run:
                        con.execute("INSERT OR REPLACE INTO update_flags(symbol, date, prev_close, close, change_pct)"
                                    " VALUES (?, ?, ?, ?, ?)", (sym, day, prev_close, c, change))
            rows.append((sym, day, o, h, lo, c, v, c * v))
            prev_close = c
        if not dry_run:
            con.executemany("INSERT OR REPLACE INTO prices(symbol, date, open, high, low, close, volume, traded_value,"
                            " source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'fyers')", rows)
        rep.rows_added += len(rows)
        rep.stocks_updated += 1
        if i % 50 == 0:
            log(f"  {i}/{len(symbols)} stocks done")

    for name, fsym in FYERS_INDEX_SYMBOLS.items():
        row = con.execute("SELECT MAX(date) FROM indices WHERE name = ?", (name,)).fetchone()
        fetch_from = (date.fromisoformat(row[0]) + timedelta(days=1)).isoformat() if row and row[0] else rep.start
        try:
            candles = [c for c in source.daily_candles(fsym, fetch_from, rep.end) if c[0] >= fetch_from]
        except AuthError:
            raise
        except Exception as exc:
            rep.errors.append(f"{name}: {exc}")
            continue
        if not dry_run:
            con.executemany("INSERT OR REPLACE INTO indices(name, date, close) VALUES (?, ?, ?)",
                            [(name, c[0], c[4]) for c in candles])
        rep.index_rows_added += len(candles)

    if not dry_run and rep.rows_added:
        from_month = last_stored[:7]
        rep.universe_rows = refresh_universe_from_db(con, from_month)
        new_last = con.execute("SELECT MAX(date) FROM prices").fetchone()[0]
        db.set_meta(con, "fyers_last_date", new_last)
        db.set_meta(con, "last_update", datetime.now(IST).isoformat(timespec="seconds"))
    return rep


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--until", help="last day to fetch (YYYY-MM-DD); default: latest finished trading day")
    ap.add_argument("--limit", type=int, help="only the first N stocks (for a quick check)")
    ap.add_argument("--dry-run", action="store_true", help="fetch and report, but write nothing")
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()
    t0 = time.time()
    try:
        source = FyersSource()
        with db.session(args.db) as con:
            rep = update(con, source, until=date.fromisoformat(args.until) if args.until else None,
                         limit=args.limit, dry_run=args.dry_run)
            if rep.rows_added and not args.dry_run:
                from .signals import build_since_last

                print("Classifying the new days ...")
                build_since_last(con)
    except AuthError as exc:
        raise SystemExit(f"{exc}\nLog in with: python -B \"E:\\Algo Trading\\fyers_auth\\fyers_login.py\" login")
    print(f"Done in {time.time() - t0:.0f}s: {rep.stocks_updated}/{rep.stocks_requested} stocks, "
          f"{rep.rows_added:,} price rows, {rep.index_rows_added} index rows, {rep.universe_rows:,} universe rows.")
    for sym, day, chg in rep.flags:
        print(f"  CHECK {sym} on {day}: {chg:+.1f}% overnight (possible split or bonus)")
    for err in rep.errors[:20]:
        print(f"  error: {err}")
    if len(rep.errors) > 20:
        print(f"  ... {len(rep.errors) - 20} more errors")


if __name__ == "__main__":
    main()
