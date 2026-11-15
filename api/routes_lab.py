"""Algorithm Lab (final phase): run C++ benchmarks and compare measured growth with theory."""
from __future__ import annotations

import math

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import daa_core

router = APIRouter(prefix="/api/lab")

# curve: how the running time should grow with n (used to draw the theoretical line).
CATALOG = [
    {"id": "merge_sort", "name": "Merge sort", "unit": "II", "group": "Sorting", "complexity": "Θ(n log n)",
     "curve": "nlogn", "max_n": 1_000_000, "inputs": True, "ops": "comparisons",
     "used_for": "Ranking stocks by score (stable)"},
    {"id": "quicksort_random", "name": "Quicksort (random pivot)", "unit": "II", "group": "Sorting",
     "complexity": "O(n log n) expected", "curve": "nlogn", "max_n": 1_000_000, "inputs": True, "ops": "comparisons",
     "used_for": "Alternative ranking"},
    {"id": "quicksort_last", "name": "Quicksort (last-element pivot)", "unit": "II", "group": "Sorting",
     "complexity": "O(n²) on sorted input", "curve": "n2", "max_n": 20_000, "inputs": True, "ops": "comparisons",
     "used_for": "Shows why the pivot is randomized"},
    {"id": "count_inversions", "name": "Counting inversions (merge sort)", "unit": "II", "group": "Inversions",
     "complexity": "Θ(n log n)", "curve": "nlogn", "max_n": 1_000_000, "inputs": True, "ops": "comparisons",
     "used_for": "Mann–Kendall trend test, rank change"},
    {"id": "count_inversions_naive", "name": "Counting inversions (all pairs)", "unit": "II", "group": "Inversions",
     "complexity": "Θ(n²)", "curve": "n2", "max_n": 20_000, "inputs": True, "ops": "comparisons",
     "used_for": "Baseline"},
    {"id": "binary_search", "name": "Binary search (100,000 lookups)", "unit": "I", "group": "Searching",
     "complexity": "O(log n) per lookup", "curve": "logn", "max_n": 1_000_000, "inputs": False, "ops": "comparisons",
     "used_for": "Date ranges, Ctrl+K symbol search"},
    {"id": "lis_patience", "name": "LIS (patience, binary search)", "unit": "III", "group": "LIS",
     "complexity": "O(n log n)", "curve": "nlogn", "max_n": 1_000_000, "inputs": True, "ops": "comparisons",
     "used_for": "Trend consistency"},
    {"id": "lis_dp", "name": "LIS (O(n²) DP)", "unit": "III", "group": "LIS", "complexity": "Θ(n²)",
     "curve": "n2", "max_n": 20_000, "inputs": True, "ops": "comparisons", "used_for": "Baseline"},
    {"id": "mann_kendall", "name": "Mann–Kendall statistic", "unit": "II", "group": "Inversions",
     "complexity": "O(n log n)", "curve": "nlogn", "max_n": 1_000_000, "inputs": True, "ops": None,
     "used_for": "Trend strength"},
    {"id": "prim_mst", "name": "Prim (adjacency matrix)", "unit": "IV", "group": "MST", "complexity": "O(V²)",
     "curve": "n2", "max_n": 2_000, "inputs": False, "ops": "relaxations", "used_for": "Correlation network"},
    {"id": "kruskal_mst", "name": "Kruskal (merge sort + union-find)", "unit": "IV", "group": "MST",
     "complexity": "O(E log E), E = V²/2", "curve": "n2logn", "max_n": 2_000, "inputs": False,
     "ops": "comparisons", "used_for": "Correlation network"},
    {"id": "topological_sort", "name": "Topological sort (DFS)", "unit": "I", "group": "Graphs",
     "complexity": "O(V + E)", "curve": "n", "max_n": 1_000_000, "inputs": False, "ops": "V + E",
     "used_for": "Indicator computation order"},
    {"id": "bfs_components", "name": "BFS components", "unit": "I", "group": "Graphs", "complexity": "O(V + E)",
     "curve": "n", "max_n": 1_000_000, "inputs": False, "ops": None, "used_for": "Clusters of co-moving stocks"},
    {"id": "dfs_components", "name": "DFS components", "unit": "I", "group": "Graphs", "complexity": "O(V + E)",
     "curve": "n", "max_n": 1_000_000, "inputs": False, "ops": None, "used_for": "Cross-check of BFS"},
    {"id": "tree_independent_set", "name": "Tree independent set (DP)", "unit": "III", "group": "Dynamic programming",
     "complexity": "O(n)", "curve": "n", "max_n": 1_000_000, "inputs": False, "ops": None,
     "used_for": "Diversified stock selection"},
    {"id": "knapsack_01", "name": "0/1 knapsack (30 items, capacity n)", "unit": "III", "group": "Knapsack",
     "complexity": "O(n·W): pseudo-polynomial", "curve": "n", "max_n": 200_000, "inputs": False,
     "ops": "DP cells", "used_for": "Whole-share allocation"},
    {"id": "fractional_knapsack", "name": "Fractional knapsack (greedy)", "unit": "IV", "group": "Knapsack",
     "complexity": "O(n log n)", "curve": "nlogn", "max_n": 1_000_000, "inputs": False, "ops": None,
     "used_for": "Fractional-share allocation"},
    {"id": "subset_sum_backtracking", "name": "Subset sum (backtracking)", "unit": "IV", "group": "Subset sum",
     "complexity": "O(2ⁿ) worst case, pruned", "curve": "2n", "max_n": 28, "inputs": False,
     "ops": "nodes", "used_for": "Selection with limits"},
    {"id": "subset_sum_brute_force", "name": "Subset sum (enumerate all subsets)", "unit": "II", "group": "Subset sum",
     "complexity": "Θ(2ⁿ)", "curve": "2n", "max_n": 22, "inputs": False, "ops": "nodes",
     "used_for": "Baseline"},
    {"id": "coin_change", "name": "Coin change (5 prices, amount n)", "unit": "III", "group": "Dynamic programming",
     "complexity": "O(k·A)", "curve": "n", "max_n": 5_000_000, "inputs": False, "ops": None,
     "used_for": "Spending leftover cash"},
    {"id": "interval_scheduling", "name": "Interval scheduling (earliest finish)", "unit": "IV", "group": "Greedy",
     "complexity": "O(n log n)", "curve": "nlogn", "max_n": 1_000_000, "inputs": False, "ops": None,
     "used_for": "Backtest benchmark"},
    {"id": "hindsight_dag", "name": "Longest path in a DAG (50 stocks)", "unit": "III", "group": "Dynamic programming",
     "complexity": "O(D·H·S)", "curve": "n", "max_n": 5_000, "inputs": False, "ops": "edge checks",
     "used_for": "Hindsight bound"},
]
BY_ID = {a["id"]: a for a in CATALOG}

CURVES = {
    "n": lambda n: n,
    "logn": lambda n: math.log2(n + 1),
    "nlogn": lambda n: n * math.log2(n + 1),
    "n2": lambda n: n * n,
    "n2logn": lambda n: n * n * math.log2(n + 1),
    "2n": lambda n: 2.0 ** n,
}


class LabRun(BaseModel):
    algorithm: str
    sizes: list[int] = Field(..., min_length=1, max_length=12)
    input: str = Field("random", pattern="^(random|sorted|nearly_sorted)$")


@router.get("/algorithms")
def algorithms() -> dict:
    return {"algorithms": CATALOG}


@router.post("/run")
def run(body: LabRun) -> dict:
    algo = BY_ID.get(body.algorithm)
    if not algo:
        raise HTTPException(422, f"Unknown algorithm {body.algorithm}")
    sizes = sorted(set(body.sizes))
    if sizes[0] < 1 or sizes[-1] > algo["max_n"]:
        raise HTTPException(422, f"Sizes must be between 1 and {algo['max_n']:,} for {algo['name']}")
    points = []
    for n in sizes:
        repeats = 3 if n <= algo["max_n"] // 10 else 1
        millis, ops = daa_core.run_benchmark(algo["id"], n, body.input, 1, repeats)
        points.append({"n": n, "millis": round(millis, 4), "ops": int(ops)})
    curve = CURVES[algo["curve"]]
    last = points[-1]
    for p in points:  # theoretical curve scaled to pass through the largest measurement
        p["theory_millis"] = round(last["millis"] * curve(p["n"]) / curve(last["n"]), 4)
    usable = [p for p in points if p["millis"] > 0 and p["n"] > 1]
    slope = None
    if len(usable) >= 3:
        slope = float(np.polyfit(np.log([p["n"] for p in usable]), np.log([p["millis"] for p in usable]), 1)[0])
    return {"algorithm": algo["id"], "name": algo["name"], "complexity": algo["complexity"], "input": body.input,
            "points": points, "loglog_slope": None if slope is None else round(slope, 3)}
