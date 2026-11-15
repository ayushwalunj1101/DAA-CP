"""FastAPI application.

Run from the project root:
    python -m uvicorn api.main:app --reload --port 8010
Interactive docs: http://localhost:8010/docs
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import daa_core
from pipeline.config import UNIVERSE_SIZE

from . import routes_backtest, routes_lab, routes_market, routes_network, routes_portfolio, routes_stocks
from .deps import read_connection

app = FastAPI(title="Momentum System API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(routes_stocks.router)
app.include_router(routes_market.router)
app.include_router(routes_network.router)
app.include_router(routes_portfolio.router)
app.include_router(routes_backtest.router)
app.include_router(routes_lab.router)


@app.get("/api/health")
def health(con: sqlite3.Connection = Depends(read_connection)) -> dict:
    con.execute("SELECT 1").fetchone()
    return {"status": "ok", "core_version": daa_core.version()}


@app.get("/api/meta")
def meta(con: sqlite3.Connection = Depends(read_connection)) -> dict:
    # Two queries: SQLite answers a lone MIN() or MAX() straight from the date index.
    first = con.execute("SELECT MIN(date) FROM prices").fetchone()[0]
    last = con.execute("SELECT MAX(date) FROM prices").fetchone()[0]
    month = con.execute("SELECT MAX(month) FROM universe").fetchone()[0]
    members = con.execute("SELECT COUNT(*) FROM universe WHERE month = ? AND rank <= ?",
                          (month, UNIVERSE_SIZE)).fetchone()[0]
    meta_rows = dict(con.execute("SELECT key, value FROM meta").fetchall())
    flags = con.execute("SELECT COUNT(*) FROM update_flags WHERE reviewed = 0").fetchone()[0]
    return {
        "first_date": first,
        "last_date": last,
        "universe_month": month,
        "universe_size": members,
        "local_end": meta_rows.get("local_end"),
        "last_update": meta_rows.get("last_update"),
        "unreviewed_flags": flags,
    }


# ---------------------------------------------------------------- built web app (npm run build)
# When web/dist exists, the API also serves the React app, so one command runs everything:
#     python -m uvicorn api.main:app --port 8010   ->   http://localhost:8010
WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"

if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web_app(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = (WEB_DIST / path).resolve()
        if path and file.is_file() and WEB_DIST in file.parents:
            return FileResponse(file)
        return FileResponse(WEB_DIST / "index.html")  # client-side routes (/scanner, /stock/X, ...)
