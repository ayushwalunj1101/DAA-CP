"""Portfolio Builder screen (phase 4)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from pipeline.portfolio import PortfolioRequest, build_portfolio

from .deps import read_connection
from .routes_market import resolve_date

router = APIRouter(prefix="/api")


class PortfolioBody(BaseModel):
    capital: float = Field(1_000_000, ge=10_000, le=1_000_000_000)
    max_stocks: int = Field(8, ge=1, le=30)
    max_per_sector: int = Field(2, ge=1, le=30)
    risk_pct: float = Field(1.0, gt=0, le=10)
    fractional: bool = True
    date: str | None = None


@router.post("/portfolio")
def portfolio(body: PortfolioBody, con: sqlite3.Connection = Depends(read_connection)) -> dict:
    day, _ = resolve_date(con, body.date)
    req = PortfolioRequest(body.capital, body.max_stocks, body.max_per_sector, body.risk_pct, body.fractional)
    return build_portfolio(con, day, req)
