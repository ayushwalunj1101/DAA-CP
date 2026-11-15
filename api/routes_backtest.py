"""Backtest screen (phase 5)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from pipeline.backtest import BacktestRequest, run_backtest

from .deps import read_connection

router = APIRouter(prefix="/api")


class BacktestBody(BaseModel):
    start: str = "2014-01-01"
    end: str | None = None
    slots: int = Field(5, ge=1, le=20)
    hold_days: int = Field(20, ge=1, le=120)
    stop_atr: float = Field(2.0, gt=0, le=10)
    cost_pct: float = Field(0.1, ge=0, le=2)
    capital: float = Field(1_000_000, ge=10_000)
    min_class: int = Field(1, ge=1, le=2)


@router.post("/backtest")
def backtest(body: BacktestBody, con: sqlite3.Connection = Depends(read_connection)) -> dict:
    try:
        return run_backtest(con, BacktestRequest(**body.model_dump()))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
