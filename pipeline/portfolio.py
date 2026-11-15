"""Portfolio builder (phase 4): diversify on the MST, size by risk, allocate three ways, spend leftover cash.

1. Candidates: the top 30 stocks in a bullish class, by bullish rank.
2. Diversify: maximum-weight independent set on the correlation MST (tree DP), weight = bullish score.
3. Size: a full position is risk x capital / (2 x ATR) shares, so a 2-ATR move costs `risk` of capital.
4. Allocate: fractional knapsack (greedy), 0/1 knapsack (DP) and subset sum with limits (backtracking).
5. Whole-share methods spend their leftover cash with coin change.
"""
from __future__ import annotations

import math
import sqlite3
import time
from dataclasses import dataclass

import daa_core

from .network import build_network

CANDIDATES = 30
TARGET_FRAC = 0.95


def capacity_unit(capital: float) -> int:
    """Rupees per DP capacity unit: a power of ten keeping the 0/1 table at most ~20,000 columns wide."""
    return max(1, 10 ** math.ceil(math.log10(max(capital, 1) / 20_000)))


@dataclass
class PortfolioRequest:
    capital: float = 1_000_000
    max_stocks: int = 8
    max_per_sector: int = 2
    risk_pct: float = 1.0
    fractional: bool = True


def _candidates(con: sqlite3.Connection, date: str) -> list[dict]:
    rows = con.execute(
        "SELECT g.symbol, s.sector, g.bull_score, g.close, g.atr14, g.bull_rank, g.cls FROM signals g "
        "JOIN stocks s USING(symbol) WHERE g.date = ? AND g.cls > 0 AND g.atr14 > 0 ORDER BY g.bull_rank LIMIT ?",
        (date, CANDIDATES)).fetchall()
    keys = ["symbol", "sector", "score", "price", "atr", "rank", "cls"]
    return [dict(zip(keys, r)) for r in rows]


def _diversify(con: sqlite3.Connection, date: str, cands: list[dict]) -> tuple[list[dict], dict]:
    net = build_network(con, date)
    index = {s: i for i, s in enumerate(net.symbols)}
    n = len(net.symbols)
    weight = [0.0] * n
    extra = []  # candidates missing from the network (gaps in their price history) are isolated nodes
    for c in cands:
        if c["symbol"] in index:
            weight[index[c["symbol"]]] = c["score"]
        else:
            extra.append(c)
    for c in extra:
        index[c["symbol"]] = len(weight)
        weight.append(c["score"])
    edges = [(u, v) for u, v, _ in net.tree_edges]
    t0 = time.perf_counter()
    mis = daa_core.tree_max_independent_set(len(weight), edges, weight)
    millis = (time.perf_counter() - t0) * 1000
    chosen = set(mis["nodes"])
    picked = [c for c in cands if index[c["symbol"]] in chosen]
    adjacency = sorted((net.symbols[u], net.symbols[v]) for u, v in edges
                       if weight[u] > 0 and weight[v] > 0)  # MST links between two candidates
    return picked, {"millis": millis, "candidate_links": adjacency, "tree_nodes": len(weight)}


def _position(c: dict, shares: float, score_share: float = 1.0) -> dict:
    return {"symbol": c["symbol"], "sector": c["sector"], "shares": shares, "price": c["price"],
            "cost": shares * c["price"], "score": c["score"] * score_share}


def _spend_leftover(positions: list[dict], leftover: float) -> float:
    """Coin change: buy extra whole shares of the chosen stocks with the cash left over."""
    if not positions or leftover <= 0:
        return 0.0
    unit = 1 if leftover <= 5_000_000 else 10
    prices = [max(1, math.ceil(p["price"] / unit)) for p in positions]
    r = daa_core.coin_change_max_spend(prices, int(leftover // unit))
    spent = 0.0
    for p, extra in zip(positions, r["count"]):
        if extra:
            p["shares"] += extra
            p["cost"] = p["shares"] * p["price"]
            spent += extra * p["price"]
    return spent


def _summary(name: str, positions: list[dict], capital: float, millis: float, **extra) -> dict:
    used = sum(p["cost"] for p in positions)
    return {"name": name, "positions": positions, "capital_used": round(used, 2),
            "cash_left": round(capital - used, 2), "total_score": round(sum(p["score"] for p in positions), 2),
            "millis": round(millis, 3), **extra}


def build_portfolio(con: sqlite3.Connection, date: str, req: PortfolioRequest) -> dict:
    cands = _candidates(con, date)
    picked, div = _diversify(con, date, cands) if cands else ([], {"millis": 0, "candidate_links": []})
    risk = req.capital * req.risk_pct / 100
    for c in picked:
        c["whole_shares"] = math.floor(risk / (2 * c["atr"]))
    # All three methods share the same items (one full position per stock) and the same rounded-up
    # costs, so fractional >= 0/1 >= subset-with-limits in total score is guaranteed.
    whole = [c for c in picked if c["whole_shares"] > 0]
    unit = capacity_unit(req.capital)
    units = [math.ceil(c["whole_shares"] * c["price"] / unit) for c in whole]
    cap_units = int(req.capital // unit)
    scores = [c["score"] for c in whole]
    methods = []

    # Fractional knapsack: positions may be cut (fractional shares), greedy by score per rupee.
    t0 = time.perf_counter()
    frac = daa_core.fractional_knapsack(scores, [c["whole_shares"] * c["price"] for c in whole], req.capital)
    fpos = [_position(c, c["whole_shares"] * f, f) for c, f in zip(whole, frac["fraction"]) if f > 0]
    methods.append(_summary("fractional", fpos, req.capital, (time.perf_counter() - t0) * 1000,
                            what_if=not req.fractional, leftover_spent=0.0))

    # 0/1 knapsack: whole positions, best total score within the capital.
    t0 = time.perf_counter()
    ks = daa_core.knapsack_01(scores, units, cap_units)
    kpos = [_position(whole[i], whole[i]["whole_shares"]) for i in ks["items"]]
    millis = (time.perf_counter() - t0) * 1000
    spent = _spend_leftover(kpos, req.capital - sum(p["cost"] for p in kpos))
    methods.append(_summary("knapsack01", kpos, req.capital, millis, leftover_spent=round(spent, 2),
                            dp_cells=ks["cells"], unit=unit))

    # Subset sum with limits: spend at least 95% of capital, at most K stocks and s per sector.
    t0 = time.perf_counter()
    sectors = {s: i for i, s in enumerate(sorted({c["sector"] for c in whole}))}
    ss = daa_core.subset_sum_backtracking([float(u * unit) for u in units], scores,
                                          [sectors[c["sector"]] for c in whole], float(cap_units * unit),
                                          TARGET_FRAC, req.max_stocks, req.max_per_sector)
    spos = [_position(whole[i], whole[i]["whole_shares"]) for i in ss["items"]]
    millis = (time.perf_counter() - t0) * 1000
    spent = _spend_leftover(spos, req.capital - sum(p["cost"] for p in spos))
    methods.append(_summary("subset_sum", spos, req.capital, millis, leftover_spent=round(spent, 2),
                            nodes_explored=ss["nodes"], brute_force_nodes=2 ** (len(whole) + 1) - 1,
                            reached_target=ss["reached_target"]))
    for m in methods:
        for p in m["positions"]:
            p["shares"] = round(p["shares"], 4)
            p["cost"] = round(p["cost"], 2)
            p["score"] = round(p["score"], 2)
    return {
        "date": date,
        "candidates": [c["symbol"] for c in cands],
        "diversified": [c["symbol"] for c in picked],
        "candidate_links": [list(e) for e in div["candidate_links"]],
        "diversify_millis": round(div["millis"], 3),
        "methods": methods,
    }
