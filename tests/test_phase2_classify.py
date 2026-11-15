"""Phase 2: percentile ranks, scores, classification rules, ranking, rank churn, Overview and Scanner APIs."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import daa_core as d
from pipeline.signals import INPUTS, PCT_FIELDS

rng = np.random.default_rng(42)


# ---------------------------------------------------------------- reference implementation (pandas/numpy)
def pct_ref(x):
    s = pd.Series(x)
    m = s.notna().sum()
    if m == 1:
        return np.where(s.notna(), 50.0, np.nan)
    return ((s.rank(method="average") - 1) / (m - 1) * 100).to_numpy()


def cutoff_ref(x, p):
    v = np.sort(np.asarray(x)[~np.isnan(x)])
    k = max(math.ceil(p / 100 * len(v)) - 1, 0)
    return v[min(k, len(v) - 1)]


def classify_ref(inp, w=(1, 1, 1, 1, 1)):
    n = len(inp["close"])
    p = {"trend": pct_ref(inp["mk_z60"]), "cb": pct_ref(inp["lis_ratio60"]), "cr": pct_ref(inp["lds_ratio60"]),
         "rs": pct_ref(inp["rs60"]), "vol": pct_ref(inp["updown_vol20"]), "vw": pct_ref(inp["vwap_dist"])}
    w = np.asarray(w, float)
    bull = (w[0] * p["trend"] + w[1] * p["cb"] + w[2] * p["rs"] + w[3] * p["vol"] + w[4] * p["vw"]) / w.sum()
    bear = (w[0] * (100 - p["trend"]) + w[1] * p["cr"] + w[2] * (100 - p["rs"]) + w[3] * (100 - p["vol"])
            + w[4] * (100 - p["vw"])) / w.sum()
    cuts = [cutoff_ref(bull, 90), cutoff_ref(bull, 75), cutoff_ref(bear, 90), cutoff_ref(bear, 75)]
    cls = np.zeros(n, int)
    with np.errstate(invalid="ignore"):
        up, heavy = inp["ret5"] >= 0, inp["rvol5_avg"] > 1
        known = ~np.isnan(inp["ret5"]) & ~np.isnan(inp["rvol5_avg"])
        quad = np.where(known, np.where(up, np.where(heavy, 0, 1), np.where(heavy, 2, 3)), -1)
        c, e50, e200 = inp["close"], inp["ema50"], inp["ema200"]
        est_b = (inp["mk_z60"] >= 1.96) & (c > e50) & (e50 > e200) & (inp["sign_p_up60"] < 0.05)
        dev_b = (inp["mk_z20"] >= 1.96) | ((c > inp["high20"]) & (quad == 0))
        est_r = (inp["mk_z60"] <= -1.96) & (c < e50) & (e50 < e200) & (inp["sign_p_down60"] < 0.05)
        dev_r = (inp["mk_z20"] <= -1.96) | ((c < inp["low20"]) & (quad == 2))
    for i in range(n):
        if np.isnan(bull[i]):
            continue
        b = 2 if est_b[i] and bull[i] >= cuts[0] else 1 if dev_b[i] and bull[i] >= cuts[1] else 0
        r = -2 if est_r[i] and bear[i] >= cuts[2] else -1 if dev_r[i] and bear[i] >= cuts[3] else 0
        cls[i] = 0 if (b and r) else (b or r)
    valid = [i for i in range(n) if not np.isnan(bull[i])]
    bull_order = sorted(valid, key=lambda i: (-bull[i], -p["rs"][i], i))
    bear_order = sorted(valid, key=lambda i: (-bear[i], p["rs"][i], i))
    return {"cls": cls, "bull": bull, "bear": bear, "quad": quad, "cuts": cuts, "bull_order": bull_order,
            "bear_order": bear_order}


def random_day(n=300, nan_frac=0.05, seed=0):
    r = np.random.default_rng(seed)
    close = r.uniform(50, 500, n)
    inp = {
        "close": close, "ema50": close * r.uniform(0.85, 1.15, n), "ema200": close * r.uniform(0.8, 1.2, n),
        "high20": close * r.uniform(0.9, 1.1, n), "low20": close * r.uniform(0.85, 1.05, n),
        "mk_z20": r.normal(0, 2, n), "mk_z60": np.round(r.normal(0, 2.5, n), 1),  # rounding creates ties
        "lis_ratio60": np.round(r.uniform(0.05, 0.6, n), 2), "lds_ratio60": np.round(r.uniform(0.05, 0.6, n), 2),
        "sign_p_up60": r.uniform(0, 0.3, n), "sign_p_down60": r.uniform(0, 0.3, n), "rs60": r.normal(0, 0.1, n),
        "updown_vol20": r.lognormal(0, 0.4, n), "vwap_dist": r.normal(0, 1.5, n), "ret5": r.normal(0, 4, n),
        "rvol5_avg": r.lognormal(0, 0.3, n),
    }
    for k in ("mk_z60", "rs60", "vwap_dist", "ret5"):
        inp[k][r.random(n) < nan_frac] = np.nan
    return inp


# ---------------------------------------------------------------- unit tests
@pytest.mark.parametrize("seed", range(5))
def test_percentile_ranks_match_pandas_average_rank(seed):
    x = np.round(np.random.default_rng(seed).normal(0, 1, 200), 1)
    x[::17] = np.nan
    np.testing.assert_allclose(d.percentile_ranks(x), pct_ref(x), equal_nan=True)


def test_percentile_ranks_edge_cases():
    assert np.isnan(d.percentile_ranks(np.array([np.nan, np.nan]))).all()
    assert d.percentile_ranks(np.array([7.0]))[0] == 50.0
    np.testing.assert_allclose(d.percentile_ranks(np.array([3.0, 3.0, 3.0])), [50, 50, 50])


@pytest.mark.parametrize("p", [0, 25, 75, 90, 100])
def test_percentile_cutoff_is_nearest_rank(p):
    x = rng.normal(0, 1, 101)
    assert d.percentile_cutoff(x, p) == cutoff_ref(x, p)


@pytest.mark.parametrize("seed", range(8))
def test_classify_day_matches_reference_implementation(seed):
    inp = random_day(seed=seed)
    r = d.classify_day(inp)
    ref = classify_ref(inp)
    np.testing.assert_allclose(r["bull_score"], ref["bull"], equal_nan=True)
    np.testing.assert_allclose(r["bear_score"], ref["bear"], equal_nan=True)
    assert list(r["cls"]) == list(ref["cls"])
    assert list(r["quadrant"]) == list(ref["quad"])
    assert [r["bull_cut_est"], r["bull_cut_dev"], r["bear_cut_est"], r["bear_cut_dev"]] == pytest.approx(ref["cuts"])
    assert r["bull_order"] == ref["bull_order"]
    assert r["bear_order"] == ref["bear_order"]


def test_custom_weights_and_rescore_match_reference():
    inp = random_day(seed=99)
    w = [3, 0, 1, 0.5, 2]
    ref = classify_ref(inp, w)
    full = d.classify_day(inp, w)
    assert list(full["cls"]) == list(ref["cls"])
    base = d.classify_day(inp)
    re = d.rescore_day({p: base[p] for p in PCT_FIELDS}, base["flags"], base["quadrant"], w)
    assert list(re["cls"]) == list(full["cls"]) and re["bull_order"] == full["bull_order"]
    same = d.rescore_day({p: base[p] for p in PCT_FIELDS}, base["flags"], base["quadrant"], [1] * 5)
    assert list(same["cls"]) == list(base["cls"])


def test_conflicting_signals_are_neutral():
    inp = random_day(n=50, nan_frac=0, seed=5)
    # Stock 0: satisfies both developing-bull and developing-bear rules with top scores on both sides.
    for k, v in {"mk_z20": 5.0, "mk_z60": 0.0, "rs60": 0.0}.items():
        inp[k][0] = v
    r = d.classify_day(inp, thresholds={"dev_pct": 0})  # every score passes the developing cut-off
    assert r["flags"][0] & 2  # developing-bull rule
    inp2 = {k: v.copy() for k, v in inp.items()}
    inp2["low20"][0] = inp2["close"][0] * 2  # also a breakdown ...
    inp2["ret5"][0], inp2["rvol5_avg"][0] = -1.0, 2.0  # ... with distribution
    r2 = d.classify_day(inp2, thresholds={"dev_pct": 0})
    assert r2["flags"][0] & 2 and r2["flags"][0] & 8
    assert r2["cls"][0] == 0


def test_quicksort_ranking_equals_merge_sort_ranking():
    scores = rng.integers(0, 50, 500).astype(float)
    assert d.argsort_quick(scores, descending=True) == d.argsort_merge(scores, descending=True)


# ---------------------------------------------------------------- stored signals (real data)
@pytest.mark.realdata
def test_daily_counts_add_up(real_db):
    bad = real_db.execute("SELECT COUNT(*) FROM daily_stats WHERE est_bull + dev_bull + neutral + dev_bear + est_bear"
                          " != scanned").fetchone()[0]
    assert bad == 0
    first, last, days = real_db.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM daily_stats").fetchone()
    assert first.startswith("2013-01") and days > 3300


@pytest.mark.realdata
def test_ranks_are_permutations_and_classes_respect_cutoffs(real_db):
    for day in ("2013-06-03", "2020-03-23", "2024-01-15", "2026-09-09"):
        df = pd.read_sql_query("SELECT * FROM signals WHERE date = ?", real_db, params=(day,))
        cuts = real_db.execute("SELECT bull_cut_est, bull_cut_dev, bear_cut_est, bear_cut_dev FROM daily_stats "
                               "WHERE date = ?", (day,)).fetchone()
        n = len(df)
        assert sorted(df["bull_rank"]) == list(range(1, n + 1)) == sorted(df["bear_rank"])
        assert (df["bull_score"].rank(ascending=False, method="min") <= df["bull_rank"]).all()
        est = df[df["cls"] == 2]
        assert ((est["flags"] & 1) > 0).all() and (est["bull_score"] >= cuts[0]).all()
        dev = df[df["cls"] == -1]
        assert ((dev["flags"] & 8) > 0).all() and (dev["bear_score"] >= cuts[3]).all()


@pytest.mark.realdata
def test_stored_churn_equals_brute_force_inversions(real_db):
    days = [r[0] for r in real_db.execute("SELECT date FROM daily_stats WHERE date BETWEEN '2024-03-01' AND "
                                          "'2024-03-08' ORDER BY date")]
    a, b = days[2], days[3]
    rank_a = [r[0] for r in real_db.execute("SELECT symbol FROM signals WHERE date = ? ORDER BY bull_rank", (a,))]
    rank_b = [r[0] for r in real_db.execute("SELECT symbol FROM signals WHERE date = ? ORDER BY bull_rank", (b,))]
    common = set(rank_a) & set(rank_b)
    pos_a = {s: i for i, s in enumerate(x for x in rank_a if x in common)}
    seq = [pos_a[s] for s in rank_b if s in common]
    brute = d.count_inversions_naive(np.array(seq, float))
    assert real_db.execute("SELECT churn_inversions FROM daily_stats WHERE date = ?", (b,)).fetchone()[0] == brute


# ---------------------------------------------------------------- API
@pytest.fixture(scope="module")
def client(real_db):
    from api.main import app

    return TestClient(app)


@pytest.mark.realdata
def test_overview_api(client):
    o = client.get("/api/overview").json()
    assert sum(o["counts"].values()) == o["stocks_scanned"]
    assert sum(s["total"] for s in o["sectors"]) == o["stocks_scanned"]
    assert 0 < len(o["nifty"]) <= 250 and o["nifty"][-1]["date"] <= o["date"]
    assert o["rank_churn"]["pct"] is not None
    weekend = client.get("/api/overview", params={"date": "2020-03-22"}).json()
    assert weekend["date"] == "2020-03-20"


@pytest.mark.realdata
def test_scanner_api(client):
    bull = client.get("/api/scanner", params={"k": 15}).json()
    rows = bull["rows"]
    assert 0 < len(rows) <= 15
    assert all(r["cls"] in ("ESTABLISHED_BULLISH", "DEVELOPING_BULLISH") for r in rows)
    assert [r["rank"] for r in rows] == sorted(r["rank"] for r in rows)
    bear = client.get("/api/scanner", params={"side": "bearish", "cls": "ESTABLISHED_BEARISH", "k": 500}).json()
    assert all(r["cls"] == "ESTABLISHED_BEARISH" for r in bear["rows"])
    sector = client.get("/api/scanner", params={"sector": "IT", "k": 500}).json()
    assert all(r["sector"] == "IT" for r in sector["rows"])
    trend_only = client.get("/api/scanner", params={"w": "1,0,0,0,0", "k": 500}).json()
    assert trend_only["weights"] == [1, 0, 0, 0, 0]
    assert client.get("/api/scanner", params={"w": "1,2"}).status_code == 422


@pytest.mark.realdata
def test_stock_classification_explains_the_class(client):
    body = client.get("/api/stocks/RELIANCE").json()
    c = body["classification"]
    assert c is not None and len(c["checks"]) == 7
    if c["cls"].startswith("ESTABLISHED"):
        assert all(ch["passed"] for ch in c["checks"][:4])
    scanned_top = client.get("/api/scanner", params={"k": 1}).json()["rows"][0]
    top = client.get(f"/api/stocks/{scanned_top['symbol']}").json()["classification"]
    assert top["cls"] == scanned_top["cls"] and top["bull_rank"] == scanned_top["rank"]
