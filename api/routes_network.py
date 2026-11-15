"""Correlation Network screen (phase 3)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from pipeline.network import build_network, clusters

from .deps import read_connection
from .routes_market import CLASS_NAMES, resolve_date
from .util import clean

router = APIRouter(prefix="/api")


@router.get("/network")
def network(date: str | None = None, window: int = Query(60, ge=20, le=250),
            threshold: float = Query(0.7, ge=0.0, le=1.0), algo: str = Query("prim", pattern="^(prim|kruskal)$"),
            con: sqlite3.Connection = Depends(read_connection)) -> dict:
    day, _ = resolve_date(con, date)
    try:
        net = build_network(con, day, window, threshold, algo)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    groups, number = clusters(net.components)
    s = net.symbols
    return {
        "date": day, "algo": algo, "window": window, "threshold": threshold,
        "total_weight": round(net.total_weight, 6), "millis": round(net.millis, 3), "ops": net.ops,
        "threshold_edges": net.threshold_edges,
        "nodes": [{"symbol": sym, "sector": net.sectors[i], "bull_score": clean(net.bull_scores[i]),
                   "cls": None if net.classes[i] is None else CLASS_NAMES[net.classes[i]],
                   "cluster": number[i]} for i, sym in enumerate(s)],
        "edges": [{"a": s[u], "b": s[v], "rho": round(float(net.rho[u, v]), 4), "distance": round(w, 4)}
                  for u, v, w in net.tree_edges],
        "clusters": [{"id": k, "symbols": [s[i] for i in g]} for k, g in enumerate(groups, 1)],
    }
