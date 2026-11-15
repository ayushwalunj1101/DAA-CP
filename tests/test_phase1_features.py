"""Phase 1: binary search, topological sort, sorting/inversions, trend tests, indicators, feature engine."""
from __future__ import annotations

import bisect
import itertools
import math
import random
import time
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import daa_core as d
from pipeline.features import TREND_WINDOWS, stock_frame

rng = np.random.default_rng(7)


def random_walk(n: int, seed: int = 0) -> np.ndarray:
    r = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(r.normal(0, 0.02, n)))


# ---------------------------------------------------------------- binary search
@pytest.mark.parametrize("trial", range(20))
def test_lower_upper_bound_match_bisect(trial):
    a = sorted(rng.integers(0, 30, rng.integers(0, 60)).astype(float).tolist())
    for x in np.arange(-2, 33, 0.5):
        assert d.lower_bound(a, x) == bisect.bisect_left(a, x)
        assert d.upper_bound(a, x) == bisect.bisect_right(a, x)


def test_date_range_and_last_at_or_before():
    dates = [x.date().isoformat() for x in pd.bdate_range("2024-01-01", "2024-12-31")]
    for start, end in [("2024-03-02", "2024-03-15"), ("2023-01-01", "2024-01-03"), ("2024-12-30", "2025-02-01"),
                       ("2024-05-01", "2024-04-01")]:
        first, last = d.date_range(dates, start, end)
        assert dates[first:last] == [x for x in dates if start <= x <= end]
    assert dates[d.last_at_or_before(dates, "2024-03-02")] == "2024-03-01"  # Saturday -> Friday
    assert d.last_at_or_before(dates, "2023-12-31") == -1


def test_prefix_range_matches_startswith():
    words = sorted({"".join(random.Random(i).choices("ABCR", k=random.Random(i).randint(1, 5))) for i in range(300)})
    for prefix in ["", "A", "AB", "R", "RC", "CCC", "Z", "ABCRA"]:
        first, last = d.prefix_range(words, prefix)
        assert words[first:last] == [w for w in words if w.startswith(prefix)]


# ---------------------------------------------------------------- topological sort
@pytest.mark.parametrize("seed", range(10))
def test_topological_sort_on_random_dags(seed):
    r = random.Random(seed)
    n = r.randint(1, 40)
    perm = list(range(n))
    r.shuffle(perm)
    edges = [(perm[i], perm[j]) for i in range(n) for j in range(i + 1, n) if r.random() < 0.15]
    order = d.topological_sort(n, edges)
    pos = {v: i for i, v in enumerate(order)}
    assert sorted(order) == list(range(n))
    assert all(pos[u] < pos[v] for u, v in edges)


@pytest.mark.parametrize("edges", [[(0, 1), (1, 2), (2, 0)], [(3, 3)], [(0, 1), (1, 3), (3, 2), (2, 1)]])
def test_topological_sort_detects_cycles(edges):
    with pytest.raises(ValueError, match="cycle"):
        d.topological_sort(4, edges)


def test_feature_order_respects_every_dependency():
    order = d.feature_order()
    pos = {name: i for i, name in enumerate(order)}
    inputs = set(d.feature_inputs())
    for dep, feat in d.feature_edges():
        assert feat in pos
        assert dep in inputs or pos[dep] < pos[feat], f"{dep} must be computed before {feat}"


# ---------------------------------------------------------------- sorting and inversions
@pytest.mark.parametrize("n", [0, 1, 2, 7, 100, 1001])
def test_merge_sort_and_quicksort_sort_correctly(n):
    a = rng.integers(0, 50, n).astype(float).tolist()
    assert d.merge_sort(a) == sorted(a)
    assert d.quicksort(a, "random") == sorted(a)
    assert d.quicksort(a, "last") == sorted(a)
    assert d.quicksort(sorted(a), "last") == sorted(a)  # worst case still correct


def test_argsort_merge_is_stable_and_argsort_quick_is_deterministic():
    keys = rng.integers(0, 5, 200).astype(float)
    order = d.argsort_merge(keys, descending=True)
    expected = sorted(range(len(keys)), key=lambda i: (-keys[i], i))  # stable: ties keep index order
    assert order == expected
    assert d.argsort_quick(keys, descending=True) == expected


@pytest.mark.parametrize("seed", range(10))
def test_count_inversions_matches_brute_force(seed):
    a = np.random.default_rng(seed).integers(0, 10, 300).astype(float)  # many ties
    brute = sum(1 for i in range(len(a)) for j in range(i + 1, len(a)) if a[j] < a[i])
    assert d.count_inversions(a) == brute == d.count_inversions_naive(a)


def test_ranking_distance_counts_pairs_in_different_order():
    before = list(range(30))
    after = before[:]
    random.Random(3).shuffle(after)
    brute = sum(1 for i, j in itertools.combinations(range(30), 2)
                if (before.index(i) - before.index(j)) * (after.index(i) - after.index(j)) < 0)
    assert d.ranking_distance(before, after) == brute
    assert d.ranking_distance(before, before) == 0
    assert d.ranking_distance(before, before[::-1]) == 30 * 29 // 2


# ---------------------------------------------------------------- trend tests
def mk_brute(x):
    n = len(x)
    s = sum(np.sign(x[j] - x[i]) for i in range(n) for j in range(i + 1, n))
    _, counts = np.unique(x, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in counts)) / 18
    z = 0.0 if s == 0 else (s - np.sign(s)) / math.sqrt(var)
    return s, var, z


@pytest.mark.parametrize("seed", range(10))
def test_mann_kendall_matches_brute_force_with_ties(seed):
    x = np.round(random_walk(60, seed), 0)  # rounding creates ties
    s, var, z = mk_brute(x)
    r = d.mann_kendall(x)
    assert r["s"] == s
    assert r["var"] == pytest.approx(var)
    assert r["z"] == pytest.approx(z)
    assert r["concordant"] + r["discordant"] + r["ties"] == 60 * 59 // 2


def lis_brute(x):
    best = 0
    for mask in range(1 << len(x)):
        sub = [x[i] for i in range(len(x)) if mask >> i & 1]
        if all(a < b for a, b in zip(sub, sub[1:])):
            best = max(best, len(sub))
    return best


@pytest.mark.parametrize("seed", range(15))
def test_lis_fast_dp_and_brute_force_agree(seed):
    x = np.random.default_rng(seed).integers(0, 6, 11).astype(float)
    assert d.lis_length(x) == d.lis_length_dp(x) == lis_brute(list(x))
    assert d.lds_length(x) == lis_brute(list(-x))


def test_binomial_table_and_sign_test():
    table = d.binomial_table(62)
    assert all(table[n][k] == math.comb(n, k) for n in range(63) for k in range(n + 1))
    for n, k in [(60, 41), (20, 15), (60, 30), (5, 0), (5, 6), (1, 1)]:
        exact = sum(Fraction(math.comb(n, i), 2 ** n) for i in range(max(k, 0), n + 1)) if k <= n else 0
        assert d.sign_test_p(k, n) == pytest.approx(float(exact), rel=1e-12)


def test_rolling_trend_equals_single_window_results():
    close = np.round(random_walk(300, 11), 1)
    for w in TREND_WINDOWS:
        r = d.rolling_trend(close, w)
        assert np.isnan(r["mk_z"][w - 1]) and not np.isnan(r["mk_z"][w])
        for t in (w, 150, 299):
            win = close[t - w + 1:t + 1]
            assert r["mk_s"][t] == d.mann_kendall(win)["s"]
            assert r["lis_ratio"][t] == d.lis_length(win) / w
            changes = np.diff(close[t - w:t + 1])
            up, down = int((changes > 0).sum()), int((changes < 0).sum())
            assert (r["up_days"][t], r["down_days"][t]) == (up, down)
            assert r["sign_p_up"][t] == pytest.approx(d.sign_test_p(up, up + down))


# ---------------------------------------------------------------- indicators vs pandas references
def ema_ref(x, n):
    out = np.full(len(x), np.nan)
    out[n - 1] = x[:n].mean()
    a = 2 / (n + 1)
    for i in range(n, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def wilder_ref(values, n, start):
    out = np.full(len(values), np.nan)
    out[start] = values[start - n + 1:start + 1].mean()
    for i in range(start + 1, len(values)):
        out[i] = (out[i - 1] * (n - 1) + values[i]) / n
    return out


def rsi_ref(c, n):
    diff = np.diff(c, prepend=np.nan)
    gain, loss = np.where(diff > 0, diff, 0.0), np.where(diff < 0, -diff, 0.0)
    g, lo = wilder_ref(gain, n, n), wilder_ref(loss, n, n)
    return 100 - 100 / (1 + g / lo)


@pytest.fixture(scope="module")
def reliance(real_db):
    df = pd.read_sql_query("SELECT * FROM prices WHERE symbol='RELIANCE' ORDER BY date", real_db)
    assert len(df) > 3000
    return df


@pytest.mark.realdata
def test_indicators_match_pandas_reference(reliance):
    h, lo, c, v = (reliance[k].to_numpy() for k in ("high", "low", "close", "volume"))
    np.testing.assert_allclose(d.ema(c, 50), ema_ref(c, 50), rtol=1e-10, equal_nan=True)
    np.testing.assert_allclose(d.rsi_wilder(c, 14), rsi_ref(c, 14), rtol=1e-9, equal_nan=True)
    prev = np.roll(c, 1)
    tr_ref = np.maximum(h - lo, np.maximum(abs(h - prev), abs(lo - prev)))
    tr_ref[0] = h[0] - lo[0]
    tr = d.true_range(h, lo, c)
    np.testing.assert_allclose(tr, tr_ref, rtol=1e-12)
    np.testing.assert_allclose(d.atr_wilder(tr, 14), wilder_ref(tr_ref, 14, 13), rtol=1e-10, equal_nan=True)
    vs = pd.Series(v)
    np.testing.assert_allclose(d.relative_volume(v, 20), (vs / vs.shift(1).rolling(20).mean()).to_numpy(),
                               rtol=1e-9, equal_nan=True)
    tp = pd.Series((h + lo + c) / 3)
    np.testing.assert_allclose(d.rolling_vwap(tp.to_numpy(), v, 20),
                               ((tp * vs).rolling(20).sum() / vs.rolling(20).sum()).to_numpy(), rtol=1e-8,
                               equal_nan=True)
    np.testing.assert_allclose(d.rolling_max_prev(h, 20), pd.Series(h).shift(1).rolling(20).max().to_numpy(),
                               equal_nan=True)
    np.testing.assert_allclose(d.rolling_min_prev(lo, 20), pd.Series(lo).shift(1).rolling(20).min().to_numpy(),
                               equal_nan=True)


def test_volume_spike_matches_median_mad_reference():
    v = np.random.default_rng(5).lognormal(10, 0.5, 400)
    v[[100, 250, 333]] *= 8
    flags = d.spike_flags(v, 60, 3.0)
    for t in range(60, 400):
        w = v[t - 60:t]
        med = np.median(w)
        mad = np.median(abs(w - med))
        assert flags[t] == float(v[t] > med + 3 * mad)
    assert flags[[100, 250, 333]].tolist() == [1.0, 1.0, 1.0]


# ---------------------------------------------------------------- feature engine on real data
@pytest.mark.realdata
def test_feature_frame_on_real_stock(real_db):
    f = stock_frame(real_db, "RELIANCE")
    assert len(f) > 3000 and f["date"].is_monotonic_increasing
    settled = f.iloc[260:]  # after the 200-day EMA and every window has warmed up
    for col in ["ema20", "ema50", "ema200", "rsi14", "atr14", "vwap20", "rvol20", "high20", "low20", "rs60",
                "vwap_dist", "updown_vol20", "rvol5_avg", "mk_z60", "lis_ratio60", "sign_p_up60"]:
        assert settled[col].notna().mean() > 0.99, col
    assert settled["rsi14"].between(0, 100).all()
    assert (settled["lis_ratio60"] <= 1).all() and (settled["lis_ratio60"] > 0).all()


@pytest.mark.realdata
def test_features_for_100_stocks_are_fast(real_db):
    syms = [r[0] for r in real_db.execute(
        "SELECT symbol FROM universe WHERE month = (SELECT MAX(month) FROM universe) ORDER BY rank LIMIT 100")]
    t0 = time.perf_counter()
    for s in syms:
        stock_frame(real_db, s)
    elapsed = time.perf_counter() - t0
    print(f"\n  features + trend tests for 100 stocks: {elapsed:.1f}s")
    assert elapsed < 60


# ---------------------------------------------------------------- API
@pytest.mark.realdata
def test_api_symbols_and_prefix_search(real_db):
    from api.main import app

    client = TestClient(app)
    all_syms = [s["symbol"] for s in client.get("/api/symbols").json()["symbols"]]
    assert len(all_syms) == 500 and all_syms == sorted(all_syms)
    rel = [s["symbol"] for s in client.get("/api/symbols", params={"q": "rel"}).json()["symbols"]]
    assert rel and all(s.startswith("REL") for s in rel)
    assert rel == [s for s in all_syms if s.startswith("REL")]


@pytest.mark.realdata
def test_api_stock_detail(real_db):
    from api.main import app

    client = TestClient(app)
    body = client.get("/api/stocks/RELIANCE").json()
    assert body["sector"] == "ENERGY"
    assert len(body["bars"]) == len(body["indicators"]) == 251
    assert body["bars"][-1]["date"] == body["as_of"]
    assert set(body["trend"]) >= {"mk_z60", "lis_ratio60", "sign_p_up60"}
    ranged = client.get("/api/stocks/RELIANCE", params={"from": "2020-03-01", "to": "2020-03-31"}).json()
    assert all("2020-03-01" <= b["date"] <= "2020-03-31" for b in ranged["bars"])
    assert client.get("/api/stocks/NOPE").status_code == 404
