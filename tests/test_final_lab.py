"""Final phase: Algorithm Lab benchmarks match their theoretical growth."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import daa_core as d
from api.main import app
from api.routes_lab import CATALOG

client = TestClient(app)


def run(algo, sizes, inp="random"):
    res = client.post("/api/lab/run", json={"algorithm": algo, "sizes": sizes, "input": inp})
    assert res.status_code == 200, res.text
    return res.json()


def test_catalog_matches_cpp_benchmarks():
    assert {a["id"] for a in CATALOG} <= set(d.benchmark_names())
    assert client.get("/api/lab/algorithms").json()["algorithms"] == CATALOG


@pytest.mark.parametrize("algo,sizes,inp,lo,hi", [
    # Wall-clock slopes are noisy (caches, timer resolution): n log n algorithms land near 1.1,
    # quadratic ones near 2 but sometimes above it as the data outgrows the cache.
    ("merge_sort", [20_000, 80_000, 320_000], "random", 0.9, 1.35),
    ("count_inversions_naive", [2_000, 4_000, 8_000], "random", 1.7, 2.6),
    ("lis_dp", [2_000, 4_000, 8_000], "random", 1.7, 2.6),
    ("quicksort_last", [2_000, 4_000, 8_000], "sorted", 1.7, 2.6),
    ("prim_mst", [250, 500, 1_000], "random", 1.6, 2.6),
])
def test_measured_slope_matches_theory(algo, sizes, inp, lo, hi):
    out = run(algo, sizes, inp)
    assert lo <= out["loglog_slope"] <= hi, out


def test_operation_counts_grow_as_predicted():
    naive = run("count_inversions_naive", [1_000, 2_000])["points"]
    assert [p["ops"] for p in naive] == [1_000 * 999 // 2, 2_000 * 1_999 // 2]
    lis = run("lis_dp", [1_000, 2_000])["points"]
    assert [p["ops"] for p in lis] == [1_000 * 999 // 2, 2_000 * 1_999 // 2]
    brute = run("subset_sum_brute_force", [10, 14])["points"]
    assert [p["ops"] for p in brute] == [2 ** 11 - 1, 2 ** 15 - 1]
    ks = run("knapsack_01", [1_000, 4_000])["points"]
    assert [p["ops"] for p in ks] == [31 * 1_001, 31 * 4_001]


def test_random_pivot_avoids_the_sorted_input_worst_case():
    sizes = [4_000, 8_000]
    fixed = run("quicksort_last", sizes, "sorted")["points"][-1]["ops"]
    rand = run("quicksort_random", sizes, "sorted")["points"][-1]["ops"]
    assert fixed == 8_000 * 7_999 // 2  # every partition peels off one element
    assert rand < fixed / 50


def test_backtracking_visits_fewer_nodes_than_brute_force():
    bt = run("subset_sum_backtracking", [18])["points"][0]["ops"]
    bf = run("subset_sum_brute_force", [18])["points"][0]["ops"]
    assert bt < bf


def test_lab_validation():
    assert client.post("/api/lab/run", json={"algorithm": "nope", "sizes": [10]}).status_code == 422
    assert client.post("/api/lab/run", json={"algorithm": "lis_dp", "sizes": [10**7]}).status_code == 422
    assert client.post("/api/lab/run", json={"algorithm": "merge_sort", "sizes": [10], "input": "x"}).status_code == 422
