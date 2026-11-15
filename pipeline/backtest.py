"""Walk-forward backtest of the bullish signals (phase 5).

A signal is a stock entering a bullish class at a day's close (it was not bullish the day before).
Its trade enters at the next open and exits by stop (2 ATR), time (hold days) or signal (no longer
bullish), whichever comes first. Every decision uses only data up to that day.

Online policy: capital is split into equal slots; each day's new signals are taken in rank order
while slots are free. Offline benchmarks: interval scheduling (most non-overlapping trades one slot
could take) and the hindsight-best single-slot path (longest path in a DAG of trading days).
"""
from __future__ import annotations

import bisect
import math
import sqlite3
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

import daa_core

REASONS = {0: "stop", 1: "time", 2: "signal", 3: "end"}
_cache: dict = {}


@dataclass
class BacktestRequest:
    start: str = "2014-01-01"
    end: str | None = None
    slots: int = 5
    hold_days: int = 20
    stop_atr: float = 2.0
    cost_pct: float = 0.1  # per side
    capital: float = 1_000_000
    min_class: int = 1  # 1 = developing or established bullish signals, 2 = established only


def _trading_days(con: sqlite3.Connection, start: str, end: str) -> list[str]:
    return [r[0] for r in con.execute("SELECT date FROM daily_stats WHERE date BETWEEN ? AND ? ORDER BY date",
                                      (start, end))]


def _signals(con: sqlite3.Connection, start: str, end: str) -> pd.DataFrame:
    return pd.read_sql_query("SELECT date, symbol, cls, bull_rank, atr14, close FROM signals WHERE date BETWEEN ? AND ?",
                             con, params=(start, end))


def potential_trades(con: sqlite3.Connection, req: BacktestRequest, days: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every signal's trade under the exit rules (independent of slots), and the signals frame."""
    key = (req.start, days[-1], req.hold_days, req.stop_atr, req.cost_pct, req.min_class)
    if key in _cache:
        return _cache[key]
    lookback = con.execute("SELECT MAX(date) FROM daily_stats WHERE date < ?", (days[0],)).fetchone()[0] or days[0]
    sig = _signals(con, lookback, days[-1])
    bullish = sig[sig["cls"] > 0]
    bull_keys = set(zip(bullish["date"], bullish["symbol"]))  # hash set of (day, stock) that were bullish
    entry_class = sig[sig["cls"] >= req.min_class]
    entry_keys = set(zip(entry_class["date"], entry_class["symbol"]))
    prev_day = dict(zip(days[1:], days[:-1]))
    prev_day[days[0]] = lookback
    ev = entry_class[entry_class["date"].isin(set(days))]
    is_new = [(prev_day[d], s) not in entry_keys for d, s in zip(ev["date"], ev["symbol"])]
    events = ev[is_new].sort_values(["date", "bull_rank"]).reset_index(drop=True)

    symbols = sorted(events["symbol"].unique())
    marks = ",".join("?" * len(symbols))
    bars = pd.read_sql_query(
        f"SELECT symbol, date, open, high, low, close FROM prices WHERE date > ? AND date <= ? AND symbol IN ({marks})"
        " ORDER BY symbol, date", con, params=(days[0], days[-1], *symbols))
    rows = []
    for sym, g in bars.groupby("symbol", sort=False):
        e = events[events["symbol"] == sym]
        dates = g["date"].tolist()
        entries, atrs, keep = [], [], []
        for k, (d, atr) in enumerate(zip(e["date"], e["atr14"])):
            i = bisect.bisect_right(dates, d)  # first bar after the signal day (binary search)
            if i < len(dates) and atr and not math.isnan(atr):
                entries.append(i)
                atrs.append(float(atr))
                keep.append(k)
        if not entries:
            continue
        bull_flags = [1 if (d, sym) in bull_keys else 0 for d in dates]
        x = daa_core.simulate_exits(g["open"].to_numpy(), g["high"].to_numpy(), g["low"].to_numpy(),
                                    g["close"].to_numpy(), bull_flags, entries, atrs, req.hold_days, req.stop_atr)
        opens = g["open"].to_numpy()
        for k, i, xi, xp, why in zip(keep, entries, x["exit_index"], x["exit_price"], x["reason"]):
            ev_row = e.iloc[k]
            entry = float(opens[i])
            ret = (xp / entry - 1) - 2 * req.cost_pct / 100
            rows.append((sym, ev_row["date"], dates[i], dates[xi], entry, float(xp), ret * 100, REASONS[why],
                         int(ev_row["bull_rank"])))
    trades = pd.DataFrame(rows, columns=["symbol", "signal_date", "entry_date", "exit_date", "entry", "exit", "ret_pct",
                                         "reason", "rank"])
    trades = trades.sort_values(["entry_date", "rank"], kind="stable").reset_index(drop=True)
    _cache.clear()
    _cache[key] = (trades, sig)
    return trades, sig


def run_online(trades: pd.DataFrame, slots: int) -> pd.DataFrame:
    """Take signals in (entry day, rank) order whenever a slot is free and the stock is not already held."""
    slot_busy_until = [""] * slots  # exit date of the trade in each slot ("" = free)
    held: dict[str, str] = {}
    taken = []
    for t in trades.itertuples():
        if held.get(t.symbol, "") >= t.entry_date:
            continue
        free = [k for k in range(slots) if slot_busy_until[k] < t.entry_date]
        if not free:
            continue
        k = free[0]
        slot_busy_until[k] = t.exit_date
        held[t.symbol] = t.exit_date
        taken.append((t.Index, k))
    chosen = trades.loc[[i for i, _ in taken]].copy()
    chosen["slot"] = [k for _, k in taken]
    return chosen


def equity_curve(chosen: pd.DataFrame, sig: pd.DataFrame, days: list[str], req: BacktestRequest) -> np.ndarray:
    """Daily mark-to-market equity: each slot compounds its own trades; idle slots hold cash."""
    closes = dict(zip(zip(sig["date"], sig["symbol"]), sig["close"]))
    slot_cash = [req.capital / req.slots] * req.slots
    by_slot: dict[int, list] = {k: [] for k in range(req.slots)}
    for t in chosen.itertuples():
        by_slot[t.slot].append(t)
    pointer = [0] * req.slots
    last_mark: dict[str, float] = {}
    out = np.empty(len(days))
    for di, day in enumerate(days):
        total = 0.0
        for k in range(req.slots):
            trades = by_slot[k]
            while pointer[k] < len(trades) and trades[pointer[k]].exit_date < day:
                t = trades[pointer[k]]
                slot_cash[k] *= 1 + t.ret_pct / 100
                pointer[k] += 1
            value = slot_cash[k]
            if pointer[k] < len(trades):
                t = trades[pointer[k]]
                if t.entry_date <= day <= t.exit_date:
                    if day == t.exit_date:
                        mark = t.exit
                    else:
                        mark = closes.get((day, t.symbol), last_mark.get(t.symbol, t.entry))
                    last_mark[t.symbol] = mark
                    value = slot_cash[k] * (mark / t.entry) * (1 - req.cost_pct / 100)
            total += value
        out[di] = total
    return out


def ranking_quality(sig: pd.DataFrame, days: list[str], horizon: int = 20, every: int = 5) -> float:
    """Average Kendall tau between each day's bullish ranking and the ranking by realised forward return."""
    close = sig.pivot(index="date", columns="symbol", values="close").reindex(days)
    rank = sig.pivot(index="date", columns="symbol", values="bull_rank").reindex(days)
    taus = []
    for i in range(0, len(days) - horizon, every):
        fwd = close.iloc[i + horizon] / close.iloc[i] - 1
        r = rank.iloc[i]
        ok = fwd.notna() & r.notna()
        if ok.sum() < 30:
            continue
        ordered = fwd[ok].to_numpy()[np.argsort(r[ok].to_numpy(), kind="stable")]
        n = len(ordered)
        s = daa_core.mann_kendall(ordered)["s"]  # inversion counting
        taus.append(-s / (n * (n - 1) / 2))  # good ranking: returns fall as rank number rises
    return float(np.mean(taus)) if taus else float("nan")


def max_drawdown(curve: np.ndarray) -> float:
    peak = np.maximum.accumulate(curve)
    return float(((curve / peak) - 1).min() * 100)


def run_backtest(con: sqlite3.Connection, req: BacktestRequest) -> dict:
    t0 = time.perf_counter()
    end = req.end or con.execute("SELECT MAX(date) FROM daily_stats").fetchone()[0]
    days = _trading_days(con, req.start, end)
    if len(days) < 60:
        raise ValueError("the test period needs at least 60 trading days")
    trades, sig = potential_trades(con, BacktestRequest(**{**req.__dict__, "end": end}), days)
    chosen = run_online(trades, req.slots)
    curve = equity_curve(chosen, sig, days, req)

    nifty = pd.read_sql_query("SELECT date, close FROM indices WHERE name = 'NIFTY50' AND date BETWEEN ? AND ?", con,
                              params=(days[0], days[-1])).set_index("date")["close"].reindex(days).ffill().bfill()
    nifty_curve = req.capital * nifty.to_numpy() / nifty.iloc[0]

    day_index = {d: i for i, d in enumerate(days)}
    starts = [day_index[d] for d in trades["entry_date"]]
    ends = [day_index.get(d, len(days) - 1) for d in trades["exit_date"]]
    offline = daa_core.interval_scheduling(starts, ends)

    closes = sig.pivot(index="date", columns="symbol", values="close").reindex(days).to_numpy(dtype=float)
    hind = daa_core.hindsight_longest_path(closes, 60, req.cost_pct / 100)
    strat_log = math.log(curve[-1] / req.capital) if curve[-1] > 0 else float("-inf")

    years = len(days) / 248
    rets = chosen["ret_pct"].to_numpy()
    metrics = {
        "total_return_pct": round((curve[-1] / req.capital - 1) * 100, 2),
        "cagr_pct": round(((curve[-1] / req.capital) ** (1 / years) - 1) * 100, 2),
        "nifty_return_pct": round((nifty_curve[-1] / req.capital - 1) * 100, 2),
        "hit_rate": round(float((rets > 0).mean() * 100), 2) if len(rets) else None,
        "avg_trade_pct": round(float(rets.mean()), 3) if len(rets) else None,
        "max_drawdown_pct": round(max_drawdown(curve), 2),
        "nifty_max_drawdown_pct": round(max_drawdown(nifty_curve), 2),
        "trades_taken": int(len(chosen)),
        "signals": int(len(trades)),
        "trades_per_slot": round(len(chosen) / req.slots, 1),
        "max_possible_trades_one_slot": len(offline),
        "hindsight_log_return": round(hind["total_log_return"], 3),
        "hindsight_pct": round(100 * strat_log / hind["total_log_return"], 4) if hind["total_log_return"] > 0 else None,
        "kendall_tau": round(ranking_quality(sig, days), 4),
        "exit_reasons": {k: int(v) for k, v in chosen["reason"].value_counts().items()},
        "seconds": round(time.perf_counter() - t0, 2),
    }
    step = max(1, len(days) // 1500)  # keep the curve light for the browser
    equity = [{"date": days[i], "strategy": round(float(curve[i]), 2), "nifty": round(float(nifty_curve[i]), 2)}
              for i in range(0, len(days), step)]
    if equity[-1]["date"] != days[-1]:
        equity.append({"date": days[-1], "strategy": round(float(curve[-1]), 2),
                       "nifty": round(float(nifty_curve[-1]), 2)})
    trade_rows = [{"symbol": t.symbol, "entry_date": t.entry_date, "exit_date": t.exit_date, "entry": round(t.entry, 2),
                   "exit": round(t.exit, 2), "ret_pct": round(t.ret_pct, 2), "slot": int(t.slot), "reason": t.reason}
                  for t in chosen.itertuples()]
    return {"start": days[0], "end": days[-1], "equity": equity, "trades": trade_rows, "metrics": metrics}
