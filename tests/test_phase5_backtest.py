"""Phase 5: trade exits, interval scheduling, hindsight longest path, online slot policy, backtest API."""
from __future__ import annotations

import itertools
import math
import random

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import daa_core as d
from pipeline.backtest import BacktestRequest, run_backtest, run_online


# ---------------------------------------------------------------- exits
def bars(opens, highs, lows, closes):
    return [np.array(x, float) for x in (opens, highs, lows, closes)]


def test_exit_rules_in_priority_order():
    o, h, lo, c = bars([100, 101, 102, 103, 104, 105], [101, 102, 103, 104, 105, 106], [99, 100, 101, 102, 103, 104],
                       [100, 101, 102, 103, 104, 105])
    bull = [1] * 6
    # time exit: held 3 bars -> exit at bar 2's close
    x = d.simulate_exits(o, h, lo, c, bull, [0], [1.0], 3, 2.0)
    assert (x["exit_index"], x["exit_price"], x["reason"]) == ([2], [102.0], [1])
    # signal exit: not bullish at bar 1's close -> exit at bar 2's open
    x = d.simulate_exits(o, h, lo, c, [1, 0, 1, 1, 1, 1], [0], [1.0], 10, 2.0)
    assert (x["exit_index"], x["exit_price"], x["reason"]) == ([2], [102.0], [2])
    # end of data
    x = d.simulate_exits(o, h, lo, c, bull, [3], [1.0], 10, 2.0)
    assert (x["exit_index"], x["reason"]) == ([5], [3])


def test_stop_exit_at_stop_or_gap_open():
    o, h, lo, c = bars([100, 99, 90], [101, 100, 91], [99, 97, 85], [100, 98, 88])
    x = d.simulate_exits(o, h, lo, c, [1, 1, 1], [0], [1.5], 10, 2.0)  # stop = 97
    assert (x["exit_index"], x["exit_price"], x["reason"]) == ([1], [97.0], [0])
    x = d.simulate_exits(o, h, lo, c, [1, 1, 1], [0], [4.0], 10, 2.0)  # stop = 92, bar 2 gaps to 90
    assert (x["exit_index"], x["exit_price"], x["reason"]) == ([2], [90.0], [0])


# ---------------------------------------------------------------- interval scheduling
@pytest.mark.parametrize("seed", range(15))
def test_interval_scheduling_is_maximum(seed):
    r = random.Random(seed)
    n = r.randint(0, 11)
    start = [r.randint(0, 30) for _ in range(n)]
    end = [s + r.randint(0, 8) for s in start]
    chosen = d.interval_scheduling(start, end)
    picked = sorted(chosen, key=lambda i: start[i])
    assert all(start[b] > end[a] for a, b in zip(picked, picked[1:]))
    best = 0
    for k in range(n, 0, -1):
        if any(all(start[b] > end[a] for a, b in zip(sorted(c, key=lambda i: start[i]),
                                                     sorted(c, key=lambda i: start[i])[1:]))
               for c in itertools.combinations(range(n), k)):
            best = k
            break
    assert len(chosen) == best


# ---------------------------------------------------------------- hindsight longest path
def hindsight_ref(closes, max_hold, cost):
    days, stocks = closes.shape
    best = [0.0] * days
    for j in range(1, days):
        best[j] = best[j - 1]
        for i in range(max(0, j - max_hold), j):
            for s in range(stocks):
                a, b = closes[i, s], closes[j, s]
                if a > 0 and b > 0:
                    best[j] = max(best[j], best[i] + math.log(b / a) - 2 * cost)
    return best[-1]


@pytest.mark.parametrize("seed", range(6))
def test_hindsight_path_matches_reference_dp(seed):
    r = np.random.default_rng(seed)
    closes = 100 * np.exp(np.cumsum(r.normal(0, 0.03, (40, 5)), axis=0))
    closes[r.random(closes.shape) < 0.1] = np.nan  # some stocks not tradable on some days
    res = d.hindsight_longest_path(closes, 7, 0.001)
    assert res["total_log_return"] == pytest.approx(hindsight_ref(closes, 7, 0.001))
    total = 0.0
    for b, s, k in zip(res["buy_day"], res["sell_day"], res["stock"]):
        assert 0 < s - b <= 7
        total += math.log(closes[s, k] / closes[b, k]) - 0.002
    assert total == pytest.approx(res["total_log_return"])
    assert all(s1 <= b2 for s1, b2 in zip(res["sell_day"], res["buy_day"][1:]))  # trades never overlap


# ---------------------------------------------------------------- online policy
def test_online_policy_respects_slots_and_priority():
    trades = pd.DataFrame({
        "symbol": ["A", "B", "C", "A", "D", "E"],
        "entry_date": ["2024-01-02", "2024-01-02", "2024-01-02", "2024-01-03", "2024-01-05", "2024-01-09"],
        "exit_date": ["2024-01-04", "2024-01-08", "2024-01-03", "2024-01-06", "2024-01-06", "2024-01-10"],
        "rank": [1, 2, 3, 1, 1, 1], "ret_pct": [1.0] * 6,
    })
    chosen = run_online(trades, slots=2)
    assert list(chosen["symbol"]) == ["A", "B", "D", "E"]  # C: no slot; second A: still held
    # A takes slot 0, B slot 1; D (Jan 5) reuses slot 0 after A exits on Jan 4; E (Jan 9) finds both free
    # and takes the lowest-numbered one.
    assert chosen["slot"].tolist() == [0, 1, 0, 0]


# ---------------------------------------------------------------- real backtest and API
@pytest.fixture(scope="module")
def short_run(real_db):
    return run_backtest(real_db, BacktestRequest(start="2019-01-01", end="2021-12-31", slots=4))


@pytest.mark.realdata
def test_backtest_has_no_look_ahead_and_respects_slots(short_run):
    trades = pd.DataFrame(short_run["trades"])
    assert (trades["entry_date"] <= trades["exit_date"]).all()
    for _, g in trades.groupby("slot"):
        g = g.sort_values("entry_date")
        assert (g["entry_date"].iloc[1:].to_numpy() > g["exit_date"].iloc[:-1].to_numpy()).all()
    m = short_run["metrics"]
    assert m["trades_taken"] == len(trades) <= m["signals"]
    assert trades.groupby("slot").size().max() <= m["max_possible_trades_one_slot"]


@pytest.mark.realdata
def test_backtest_equity_and_metrics(short_run):
    eq = short_run["equity"]
    assert eq[0]["date"] >= "2019-01-01" and eq[-1]["date"] <= "2021-12-31"
    assert eq[0]["nifty"] == pytest.approx(1_000_000)
    m = short_run["metrics"]
    assert m["total_return_pct"] == pytest.approx((eq[-1]["strategy"] / 1_000_000 - 1) * 100, abs=0.01)
    assert -100 < m["max_drawdown_pct"] <= 0 and 0 <= m["hit_rate"] <= 100
    assert m["hindsight_log_return"] > 0 and -1 <= m["kendall_tau"] <= 1
    assert sum(m["exit_reasons"].values()) == m["trades_taken"]


@pytest.mark.realdata
def test_backtest_api(real_db):
    from api.main import app

    client = TestClient(app)
    res = client.post("/api/backtest", json={"start": "2020-01-01", "end": "2020-12-31", "min_class": 2})
    assert res.status_code == 200 and res.json()["metrics"]["trades_taken"] >= 0
    assert client.post("/api/backtest", json={"start": "2026-09-01", "end": "2026-09-09"}).status_code == 422
    assert client.post("/api/backtest", json={"slots": 0}).status_code == 422
