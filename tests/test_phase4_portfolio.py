"""Phase 4: tree DP, fractional and 0/1 knapsack, subset-sum backtracking, coin change, portfolio API."""
from __future__ import annotations

import itertools
import random

import pytest
from fastapi.testclient import TestClient

import daa_core as d
from pipeline.portfolio import PortfolioRequest, build_portfolio


# ---------------------------------------------------------------- tree DP
def random_forest(n, seed, edge_prob=0.9):
    r = random.Random(seed)
    edges = [(r.randrange(i), i) for i in range(1, n) if r.random() < edge_prob]
    weights = [r.choice([0, 0, r.uniform(1, 100)]) for _ in range(n)]
    return edges, weights


def mis_brute(n, edges, weights):
    best = 0.0
    for mask in range(1 << n):
        if all(not (mask >> u & 1 and mask >> v & 1) for u, v in edges):
            best = max(best, sum(weights[i] for i in range(n) if mask >> i & 1))
    return best


@pytest.mark.parametrize("seed", range(20))
def test_tree_independent_set_matches_brute_force(seed):
    n = random.Random(seed).randint(1, 14)
    edges, w = random_forest(n, seed)
    r = d.tree_max_independent_set(n, edges, w)
    assert r["weight"] == pytest.approx(mis_brute(n, edges, w))
    chosen = set(r["nodes"])
    assert all(not (u in chosen and v in chosen) for u, v in edges)
    assert sum(w[i] for i in chosen) == pytest.approx(r["weight"])


def test_tree_independent_set_rejects_cycles_and_handles_big_trees():
    with pytest.raises(ValueError, match="cycle"):
        d.tree_max_independent_set(3, [(0, 1), (1, 2), (2, 0)], [1, 1, 1])
    n = 100_000  # a long path: the iterative DFS must not overflow the stack
    r = d.tree_max_independent_set(n, [(i, i + 1) for i in range(n - 1)], [1.0] * n)
    assert r["weight"] == n // 2


# ---------------------------------------------------------------- knapsacks
def knapsack_brute(values, weights, cap):
    best = 0.0
    for k in range(len(values) + 1):
        for combo in itertools.combinations(range(len(values)), k):
            if sum(weights[i] for i in combo) <= cap:
                best = max(best, sum(values[i] for i in combo))
    return best


@pytest.mark.parametrize("seed", range(15))
def test_knapsack_01_matches_brute_force(seed):
    r = random.Random(seed)
    n = r.randint(0, 12)
    values = [r.uniform(1, 100) for _ in range(n)]
    weights = [r.randint(1, 30) for _ in range(n)]
    cap = r.randint(0, 100)
    ks = d.knapsack_01(values, weights, cap)
    assert ks["value"] == pytest.approx(knapsack_brute(values, weights, cap))
    assert sum(weights[i] for i in ks["items"]) == ks["used"] <= cap
    assert ks["cells"] == (n + 1) * (cap + 1)


@pytest.mark.parametrize("seed", range(15))
def test_fractional_knapsack_is_optimal_and_bounds_01(seed):
    r = random.Random(seed)
    n = r.randint(1, 12)
    values = [r.uniform(1, 100) for _ in range(n)]
    weights = [r.randint(1, 30) for _ in range(n)]
    cap = r.randint(1, 100)
    fk = d.fractional_knapsack(values, [float(w) for w in weights], cap)
    # Reference greedy (exchange argument): best value per unit first.
    left, ref = cap, 0.0
    for v, w in sorted(zip(values, weights), key=lambda t: -t[0] / t[1]):
        take = min(1.0, left / w)
        ref += take * v
        left -= take * w
        if left <= 0:
            break
    assert fk["value"] == pytest.approx(ref)
    assert fk["used"] <= cap + 1e-9
    assert fk["value"] >= d.knapsack_01(values, weights, cap)["value"] - 1e-9
    assert sum(1 for f in fk["fraction"] if 0 < f < 1) <= 1  # at most one item is split


# ---------------------------------------------------------------- subset sum
@pytest.mark.parametrize("seed", range(20))
def test_backtracking_matches_brute_force_and_explores_fewer_nodes(seed):
    r = random.Random(seed)
    n = r.randint(1, 14)
    cost = [float(r.randint(5, 40) * 1000) for _ in range(n)]
    score = [r.uniform(50, 100) for _ in range(n)]
    group = [r.randrange(4) for _ in range(n)]
    cap = float(r.randint(40, 200) * 1000)
    args = (cost, score, group, cap, 0.95, r.randint(1, 6), r.randint(1, 3))
    bt, bf = d.subset_sum_backtracking(*args), d.subset_sum_brute_force(*args)
    assert bt["reached_target"] == bf["reached_target"]
    assert bt["score"] == pytest.approx(bf["score"]) and bt["cost"] == pytest.approx(bf["cost"])
    assert bf["nodes"] == 2 ** (n + 1) - 1
    assert bt["nodes"] <= 2 * bf["nodes"]  # two passes at most when no subset reaches the target
    chosen = bt["items"]
    assert sum(cost[i] for i in chosen) <= cap and len(chosen) <= args[5]
    assert all(sum(1 for i in chosen if group[i] == g) <= args[6] for g in range(4))


def test_backtracking_prunes_heavily_when_a_target_exists():
    r = random.Random(1)
    n = 22
    cost = [float(r.randint(50, 150) * 1000) for _ in range(n)]
    args = (cost, [r.uniform(50, 100) for _ in range(n)], [r.randrange(8) for _ in range(n)], 1_000_000.0, 0.95, 10, 3)
    bt = d.subset_sum_backtracking(*args)
    brute = 2 ** (n + 1) - 1
    print(f"\n  n={n}: backtracking visited {bt['nodes']:,} of {brute:,} brute-force nodes "
          f"({100 * bt['nodes'] / brute:.0f}%)")
    assert bt["reached_target"]
    assert bt["nodes"] < brute / 2


# ---------------------------------------------------------------- coin change
@pytest.mark.parametrize("seed", range(10))
def test_coin_change_spends_the_most_possible(seed):
    r = random.Random(seed)
    prices = [r.randint(3, 60) for _ in range(r.randint(1, 5))]
    amount = r.randint(0, 400)
    reach = {0}
    for x in range(1, amount + 1):
        if any(x - p in reach for p in prices):
            reach.add(x)
    res = d.coin_change_max_spend(prices, amount)
    assert res["spent"] == max(reach)
    assert sum(c * p for c, p in zip(res["count"], prices)) == res["spent"]


# ---------------------------------------------------------------- real portfolio and API
@pytest.mark.realdata
@pytest.mark.parametrize("capital,risk", [(1_000_000, 1.0), (300_000, 2.0), (25_000_000, 0.5)])
def test_real_portfolio_invariants(real_db, capital, risk):
    day = real_db.execute("SELECT MAX(date) FROM daily_stats").fetchone()[0]
    req = PortfolioRequest(capital=capital, max_stocks=6, max_per_sector=2, risk_pct=risk)
    p = build_portfolio(real_db, day, req)
    assert set(p["diversified"]) <= set(p["candidates"]) and len(p["candidates"]) <= 30
    linked = {tuple(e) for e in p["candidate_links"]}
    assert not any((a, b) in linked or (b, a) in linked for a, b in itertools.combinations(p["diversified"], 2))
    m = {x["name"]: x for x in p["methods"]}
    assert m["fractional"]["total_score"] >= m["knapsack01"]["total_score"] - 1e-6
    assert m["knapsack01"]["total_score"] >= m["subset_sum"]["total_score"] - 1e-6
    for x in p["methods"]:
        assert x["capital_used"] <= capital + 1e-6
    ss = m["subset_sum"]
    assert len(ss["positions"]) <= 6
    sectors = [pos["sector"] for pos in ss["positions"]]
    assert all(sectors.count(s) <= 2 for s in sectors)
    assert ss["nodes_explored"] <= 2 * ss["brute_force_nodes"]


@pytest.mark.realdata
def test_portfolio_api(real_db):
    from api.main import app

    client = TestClient(app)
    body = client.post("/api/portfolio", json={"capital": 500000, "max_stocks": 5, "max_per_sector": 1,
                                               "risk_pct": 1.5, "fractional": False}).json()
    assert [m["name"] for m in body["methods"]] == ["fractional", "knapsack01", "subset_sum"]
    assert body["methods"][0]["what_if"] is True
    assert client.post("/api/portfolio", json={"capital": 10}).status_code == 422
