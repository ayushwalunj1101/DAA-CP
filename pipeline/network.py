"""Correlation network of the universe on a given day (phase 3).

Closes for the last `window` returns are loaded with pandas; the correlation matrix, distances,
minimum spanning tree (Prim or Kruskal) and threshold-graph components (BFS) are computed in C++.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import numpy as np
import pandas as pd

import daa_core

from .config import UNIVERSE_SIZE


@dataclass
class Network:
    date: str
    window: int
    threshold: float
    algo: str
    symbols: list[str]
    sectors: list[str]
    bull_scores: list[float | None]
    classes: list[int | None]
    rho: np.ndarray
    distance: np.ndarray
    tree_edges: list[tuple[int, int, float]]  # (u, v, distance)
    total_weight: float
    millis: float
    ops: int
    components: list[int]  # BFS label of every node in the threshold graph
    threshold_edges: int


def window_closes(con: sqlite3.Connection, date: str, window: int) -> tuple[list[str], np.ndarray]:
    """Universe members with a close on each of the last window + 1 trading days up to `date`."""
    days = [r[0] for r in con.execute(
        "SELECT DISTINCT date FROM prices WHERE date <= ? ORDER BY date DESC LIMIT ?", (date, window + 1))][::-1]
    if len(days) < window + 1:
        raise ValueError(f"not enough history before {date} for a {window}-day window")
    members = [r[0] for r in con.execute("SELECT symbol FROM universe WHERE month = ? AND rank <= ?",
                                         (date[:7], UNIVERSE_SIZE))]
    if not members:
        month = con.execute("SELECT MAX(month) FROM universe WHERE month <= ?", (date[:7],)).fetchone()[0]
        members = [r[0] for r in con.execute("SELECT symbol FROM universe WHERE month = ? AND rank <= ?",
                                             (month, UNIVERSE_SIZE))]
    marks = ",".join("?" * len(members))
    df = pd.read_sql_query(f"SELECT symbol, date, close FROM prices WHERE date BETWEEN ? AND ? AND symbol IN ({marks})",
                           con, params=(days[0], days[-1], *members))
    wide = df.pivot(index="date", columns="symbol", values="close").reindex(days)
    wide = wide.dropna(axis=1)  # stocks that missed a day in the window are left out
    wide = wide[sorted(wide.columns)]
    return list(wide.columns), wide.to_numpy(dtype=float).T.copy()


def build_network(con: sqlite3.Connection, date: str, window: int = 60, threshold: float = 0.7,
                  algo: str = "prim") -> Network:
    if algo not in ("prim", "kruskal"):
        raise ValueError("algo must be 'prim' or 'kruskal'")
    symbols, closes = window_closes(con, date, window)
    rho = daa_core.correlation_matrix(closes)
    dist = daa_core.correlation_distance(rho)
    tree = daa_core.prim_mst(dist) if algo == "prim" else daa_core.kruskal_mst(dist)
    comps = daa_core.threshold_components(rho, threshold)
    sector = dict(con.execute("SELECT symbol, sector FROM stocks").fetchall())
    rows = con.execute("SELECT symbol, bull_score, cls FROM signals WHERE date = ?", (date,)).fetchall()
    score = {s: b for s, b, _ in rows}
    cls = {s: c for s, _, c in rows}
    return Network(
        date=date, window=window, threshold=threshold, algo=algo, symbols=symbols,
        sectors=[sector.get(s, "OTHER") for s in symbols], bull_scores=[score.get(s) for s in symbols],
        classes=[cls.get(s) for s in symbols],
        rho=rho, distance=dist, tree_edges=[tuple(e) for e in tree["edges"]], total_weight=tree["total"],
        millis=tree["millis"], ops=tree["ops"], components=list(comps["bfs"]), threshold_edges=comps["edges"],
    )


def clusters(components: list[int]) -> tuple[list[list[int]], list[int]]:
    """Groups of 2+ nodes, largest first, and each node's cluster number (1-based; 0 = on its own)."""
    groups: dict[int, list[int]] = {}
    for node, label in enumerate(components):
        groups.setdefault(label, []).append(node)
    multi = sorted((g for g in groups.values() if len(g) > 1), key=lambda g: (-len(g), g[0]))
    number = [0] * len(components)
    for k, g in enumerate(multi, 1):
        for node in g:
            number[node] = k
    return multi, number
