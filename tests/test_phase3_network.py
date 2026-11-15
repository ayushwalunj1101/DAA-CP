"""Phase 3: correlation matrix, distance, MST (Prim and Kruskal), BFS/DFS components, network API."""
from __future__ import annotations

import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

import daa_core as d
from pipeline.network import build_network, clusters


def random_closes(n, length, seed):
    r = np.random.default_rng(seed)
    market = r.normal(0, 0.01, length - 1)
    beta = r.uniform(0, 1.5, (n, 1))
    rets = beta * market + r.normal(0, 0.015, (n, length - 1))
    return 100 * np.exp(np.concatenate([np.zeros((n, 1)), np.cumsum(rets, axis=1)], axis=1))


def random_dist(n, seed):
    rho = d.correlation_matrix(random_closes(n, 61, seed))
    return d.correlation_distance(rho)


# ---------------------------------------------------------------- correlation and distance
@pytest.mark.parametrize("seed", range(3))
def test_correlation_matrix_matches_numpy(seed):
    closes = random_closes(40, 61, seed)
    np.testing.assert_allclose(d.correlation_matrix(closes), np.corrcoef(np.diff(np.log(closes), axis=1)),
                               atol=1e-12)


def test_distance_is_a_metric_on_samples():
    dist = random_dist(25, 1)
    assert np.allclose(np.diag(dist), 0) and np.allclose(dist, dist.T)
    n = len(dist)
    i, j, k = np.meshgrid(range(n), range(n), range(n), indexing="ij")
    assert (dist[i, k] <= dist[i, j] + dist[j, k] + 1e-12).all()  # triangle inequality
    assert np.isclose(d.correlation_distance(np.array([[1.0, -1.0], [-1.0, 1.0]]))[0, 1], 2.0)


def test_flat_series_has_zero_correlation():
    closes = random_closes(3, 30, 4)
    closes[1] = 50.0
    rho = d.correlation_matrix(closes)
    assert rho[1, 0] == rho[1, 2] == 0.0 and rho[1, 1] == 1.0


# ---------------------------------------------------------------- MST
def mst_reference(dist):
    """Plain Kruskal in Python: sorted() + naive union by relabelling."""
    n = len(dist)
    edges = sorted((dist[i, j], i, j) for i in range(n) for j in range(i + 1, n))
    comp, total, picked = list(range(n)), 0.0, 0
    for w, i, j in edges:
        if comp[i] != comp[j]:
            old, new = comp[j], comp[i]
            comp = [new if c == old else c for c in comp]
            total += w
            picked += 1
    return total, picked


def is_spanning_tree(edges, n):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    for u, v, _ in edges:
        ru, rv = find(u), find(v)
        if ru == rv:
            return False  # cycle
        parent[ru] = rv
    return len(edges) == n - 1


@pytest.mark.parametrize("n,seed", [(1, 0), (2, 1), (10, 2), (60, 3), (150, 4)])
def test_prim_and_kruskal_build_the_same_minimum_tree(n, seed):
    dist = random_dist(n, seed)
    prim, kruskal = d.prim_mst(dist), d.kruskal_mst(dist)
    ref_total, ref_edges = mst_reference(dist)
    assert prim["total"] == pytest.approx(ref_total) == pytest.approx(kruskal["total"])
    assert len(prim["edges"]) == len(kruskal["edges"]) == ref_edges == max(n - 1, 0)
    assert is_spanning_tree(prim["edges"], n) and is_spanning_tree(kruskal["edges"], n)


def test_mst_satisfies_cut_property():
    """Removing any tree edge splits the tree in two; that edge must be the lightest edge across the cut."""
    dist = random_dist(30, 9)
    n = len(dist)
    tree = d.prim_mst(dist)["edges"]
    for k, (u, v, w) in enumerate(tree):
        rest = [e for i, e in enumerate(tree) if i != k]
        side = {u}
        changed = True
        while changed:
            changed = False
            for a, b, _ in rest:
                if (a in side) != (b in side):
                    side |= {a, b}
                    changed = True
        other = [x for x in range(n) if x not in side]
        lightest = min(dist[a, b] for a in side for b in other)
        assert w == pytest.approx(lightest)


def test_prim_does_quadratic_work_and_kruskal_sorts_edges():
    small, big = random_dist(50, 5), random_dist(100, 6)
    ratio = d.prim_mst(big)["ops"] / d.prim_mst(small)["ops"]
    assert 3.8 < ratio < 4.2  # doubling V quadruples Prim's work on a dense graph
    assert d.kruskal_mst(big)["ops"] > 100 * 99 / 2  # at least one comparison per edge


# ---------------------------------------------------------------- components
@pytest.mark.parametrize("threshold", [0.0, 0.3, 0.5, 0.7, 0.95])
def test_bfs_and_dfs_find_the_same_components_as_union_find(threshold):
    rho = d.correlation_matrix(random_closes(80, 61, 12))
    comps = d.threshold_components(rho, threshold)
    assert comps["bfs"] == comps["dfs"]
    n = len(rho)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if rho[i, j] >= threshold:
                parent[find(i)] = find(j)
    roots = [find(i) for i in range(n)]
    for i in range(n):
        for j in range(n):
            assert (comps["bfs"][i] == comps["bfs"][j]) == (roots[i] == roots[j])
    assert comps["edges"] == int(np.triu(rho >= threshold, 1).sum())


def test_clusters_helper_orders_groups():
    groups, number = clusters([0, 1, 0, 2, 1, 1, 3])
    assert groups == [[1, 4, 5], [0, 2]]
    assert number == [2, 1, 2, 0, 1, 1, 0]


# ---------------------------------------------------------------- real network and API
@pytest.mark.realdata
def test_real_network(real_db):
    day = real_db.execute("SELECT MAX(date) FROM daily_stats").fetchone()[0]
    t0 = time.perf_counter()
    prim = build_network(real_db, day, algo="prim")
    elapsed = time.perf_counter() - t0
    kruskal = build_network(real_db, day, algo="kruskal")
    n = len(prim.symbols)
    print(f"\n  {n} stocks: network built in {elapsed:.2f}s; Prim {prim.millis:.1f} ms, Kruskal {kruskal.millis:.1f} ms")
    assert 400 < n <= 500
    assert len(prim.tree_edges) == n - 1
    assert prim.total_weight == pytest.approx(kruskal.total_weight)
    # MST property: the lightest edge at every node is in the tree, i.e. each stock is linked to the
    # stock it is most correlated with (when that partner is unique).
    neighbours = [set() for _ in range(n)]
    for u, v, _ in prim.tree_edges:
        neighbours[u].add(v)
        neighbours[v].add(u)
    dist = prim.distance.copy()
    np.fill_diagonal(dist, np.inf)
    for i in range(n):
        nearest = np.flatnonzero(dist[i] == dist[i].min())
        if len(nearest) == 1:
            assert nearest[0] in neighbours[i], prim.symbols[i]


@pytest.mark.realdata
def test_network_api(real_db):
    from api.main import app

    client = TestClient(app)
    p = client.get("/api/network").json()
    k = client.get("/api/network", params={"algo": "kruskal"}).json()
    assert p["total_weight"] == pytest.approx(k["total_weight"])
    assert len(p["edges"]) == len(p["nodes"]) - 1
    assert all(-1 <= e["rho"] <= 1 for e in p["edges"])
    loose = client.get("/api/network", params={"threshold": 0.5}).json()
    strict = client.get("/api/network", params={"threshold": 0.9}).json()
    assert loose["threshold_edges"] >= p["threshold_edges"] >= strict["threshold_edges"]
    assert client.get("/api/network", params={"algo": "dijkstra"}).status_code == 422
