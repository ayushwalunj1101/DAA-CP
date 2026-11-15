"""Phase 0: build, import, universe, FYERS updater and API skeleton."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import daa_core
from pipeline import db
from pipeline.config import UNIVERSE_SIZE
from pipeline.fyers_update import AuthError, latest_finished_day, update
from pipeline.universe import build_universe


# ---------------------------------------------------------------- C++ module
def test_core_module_loads():
    assert daa_core.version().count(".") == 2


# ---------------------------------------------------------------- universe (unit)
def test_universe_ranks_by_average_of_previous_days_only():
    days = pd.bdate_range("2024-01-01", "2024-04-30")
    tv = pd.DataFrame({"A": 10.0, "B": 5.0, "C": 1.0}, index=days)
    # On the first trading day of April, C trades a huge amount; that day must not count for April.
    first_april = days[days.month == 4][0]
    tv.loc[first_april, "C"] = 1e9
    uni = build_universe(tv, keep=3, lookback=20)
    april = uni[uni["month"] == "2024-04"].sort_values("rank")
    assert list(april["symbol"]) == ["A", "B", "C"]
    may_like = build_universe(tv.iloc[:-1], keep=3, lookback=20)  # sanity: still computable
    assert not may_like.empty


def test_universe_skips_months_without_full_lookback():
    days = pd.bdate_range("2024-01-01", "2024-02-29")
    tv = pd.DataFrame({"A": np.arange(len(days), dtype=float) + 1}, index=days)
    uni = build_universe(tv, keep=5, lookback=60)
    assert uni.empty  # fewer than 61 trading days, so no month has a full window


def test_universe_treats_missing_days_as_zero():
    days = pd.bdate_range("2024-01-01", "2024-03-31")
    tv = pd.DataFrame({"A": 10.0, "B": 9.0}, index=days)
    tv.loc[days[-30]:, "A"] = np.nan  # A stops trading: average must fall
    uni = build_universe(tv, keep=2, lookback=20)
    march = uni[uni["month"] == "2024-03"].sort_values("rank")
    assert list(march["symbol"])[0] == "B"


# ---------------------------------------------------------------- imported data (real)
@pytest.mark.realdata
def test_data_range(real_db):
    first, last = real_db.execute("SELECT MIN(date), MAX(date) FROM prices WHERE source='local'").fetchone()
    assert first == "2012-01-02"
    assert last == "2026-09-09"


@pytest.mark.realdata
def test_every_month_has_exactly_500_members(real_db):
    counts = real_db.execute(
        "SELECT MIN(c), MAX(c), COUNT(*) FROM (SELECT month, SUM(rank <= ?) c FROM universe GROUP BY month)",
        (UNIVERSE_SIZE,)).fetchone()
    assert counts[0] == counts[1] == UNIVERSE_SIZE
    assert counts[2] >= 170


@pytest.mark.realdata
def test_universe_ranks_are_unique_and_sorted_by_traded_value(real_db):
    df = pd.read_sql_query("SELECT month, rank, avg_traded_value FROM universe", real_db)
    assert not df.duplicated(["month", "rank"]).any()
    bad = df.sort_values(["month", "rank"]).groupby("month")["avg_traded_value"].apply(
        lambda s: (s.diff().dropna() > 0).sum()).sum()
    assert bad == 0


@pytest.mark.realdata
def test_universe_members_have_prices_and_most_have_sectors(real_db):
    month = real_db.execute("SELECT MAX(month) FROM universe").fetchone()[0]
    missing = real_db.execute(
        "SELECT COUNT(*) FROM universe u WHERE u.month = ? AND u.rank <= ? AND NOT EXISTS "
        "(SELECT 1 FROM prices p WHERE p.symbol = u.symbol)", (month, UNIVERSE_SIZE)).fetchone()[0]
    assert missing == 0
    mapped = real_db.execute(
        "SELECT AVG(s.sector != 'OTHER') FROM universe u JOIN stocks s USING(symbol) WHERE u.month = ? AND u.rank <= ?",
        (month, UNIVERSE_SIZE)).fetchone()[0]
    assert mapped >= 0.95


@pytest.mark.realdata
def test_price_rows_are_valid(real_db):
    bad = real_db.execute(
        "SELECT COUNT(*) FROM prices WHERE high < low OR close > high * 1.000001 OR close < low * 0.999999 "
        "OR volume <= 0 OR close <= 0").fetchone()[0]
    assert bad == 0


@pytest.mark.realdata
def test_nifty50_index_covers_local_history(real_db):
    first, last = real_db.execute("SELECT MIN(date), MAX(date) FROM indices WHERE name = 'NIFTY50'").fetchone()
    assert first == "2012-01-02" and last >= "2026-09-09"


# ---------------------------------------------------------------- FYERS updater (fake source)
class FakeSource:
    """Returns synthetic candles; one symbol jumps 50% overnight to trigger a flag."""

    def __init__(self, fail_auth: bool = False):
        self.calls: list[tuple[str, str, str]] = []
        self.fail_auth = fail_auth

    def daily_candles(self, fsym, start, end):
        if self.fail_auth:
            raise AuthError("token expired")
        self.calls.append((fsym, start, end))
        days = pd.bdate_range(start, end)
        base = 150.0 if "JUMP" in fsym else 100.0
        return [(d.date().isoformat(), base, base + 1, base - 1, base, 1000.0) for d in days]


def _tiny_db(tmp_path):
    path = tmp_path / "tiny.db"
    con = db.connect(path)
    db.init_schema(con)
    days = pd.bdate_range("2024-01-01", "2024-03-29")
    rows = []
    for sym in ("AAA", "JUMP"):
        rows += [(sym, d.date().isoformat(), 100, 101, 99, 100, 1000, 1e5, "local") for d in days]
    con.executemany("INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.executemany("INSERT INTO universe VALUES ('2024-03', ?, ?, 1e5)", [("AAA", 1), ("JUMP", 2)])
    con.execute("INSERT INTO holidays VALUES ('2024-04-02', 'test holiday')")
    con.commit()
    return con


def test_fyers_update_appends_days_flags_jumps_and_refreshes_universe(tmp_path):
    con = _tiny_db(tmp_path)
    src = FakeSource()
    rep = update(con, src, until=date(2024, 4, 30), log=lambda *_: None)
    assert rep.stocks_updated == 2
    assert con.execute("SELECT MAX(date) FROM prices WHERE source='fyers'").fetchone()[0] == "2024-04-30"
    flagged = con.execute("SELECT symbol, ROUND(change_pct) FROM update_flags").fetchall()
    assert flagged == [("JUMP", 50.0)]
    assert any(name == "NSE:NIFTY50-INDEX" for name, *_ in src.calls)
    assert con.execute("SELECT COUNT(*) FROM universe WHERE month = '2024-04'").fetchone()[0] == 2


def test_fyers_update_is_noop_when_up_to_date(tmp_path):
    con = _tiny_db(tmp_path)
    rep = update(con, FakeSource(), until=date(2024, 3, 29), log=lambda *_: None)
    assert rep.rows_added == 0


def test_fyers_update_dry_run_writes_nothing(tmp_path):
    con = _tiny_db(tmp_path)
    before = con.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    rep = update(con, FakeSource(), until=date(2024, 4, 30), dry_run=True, log=lambda *_: None)
    assert rep.rows_added > 0
    assert con.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == before


def test_fyers_update_stops_on_expired_token(tmp_path):
    con = _tiny_db(tmp_path)
    with pytest.raises(AuthError):
        update(con, FakeSource(fail_auth=True), until=date(2024, 4, 30), log=lambda *_: None)


def test_latest_finished_day_respects_market_close():
    from datetime import datetime

    from pipeline.fyers_update import IST
    assert latest_finished_day(datetime(2026, 11, 13, 10, 0, tzinfo=IST)) == date(2026, 11, 12)
    assert latest_finished_day(datetime(2026, 11, 13, 16, 0, tzinfo=IST)) == date(2026, 11, 13)


# ---------------------------------------------------------------- API skeleton
@pytest.mark.realdata
def test_api_health_and_meta(real_db):
    from api.main import app

    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    meta = client.get("/api/meta").json()
    assert meta["first_date"] == "2012-01-02"
    assert meta["universe_size"] == UNIVERSE_SIZE
