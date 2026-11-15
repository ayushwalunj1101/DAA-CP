# Algorithmic Stock Momentum Detection and Opportunity Ranking System

DAA course project. Detects, classifies and ranks momentum in the 500 most-traded NSE stocks,
builds diversified portfolios and backtests the signals. Every stage is a syllabus algorithm
written from scratch in C++.

```
E:\Algo Trading (local history) ─┐
FYERS API (daily updates) ───────┴─> pipeline/ (Python) ─> data/momentum.db (SQLite)
                                                                │
                                core/ (C++ algorithms, pybind11) ┤
                                                                ▼
                                            api/ (FastAPI) ─> web/ (React)
```

## Layout

| Folder | What it holds |
|---|---|
| `core/` | C++17 algorithm library (`include/daa`, `src`) and its Python bindings |
| `pipeline/` | Local data import, monthly universe, FYERS daily updater |
| `api/` | FastAPI server |
| `web/` | React + TypeScript web app |
| `tests/` | pytest suites, one file per phase |
| `docs/` | API contract and notes |
| `data/` | SQLite database (not in git; rebuilt by the pipeline) |

## Setup (once)

Requirements: Python 3.13, a 64-bit MinGW-w64 g++ (WinLibs UCRT), Node.js 20+.

```powershell
python -m pip install pybind11 pytest fastapi uvicorn pandas pyarrow fyers-apiv3 httpx
python core/build.py                 # builds daa_core.cp313-win_amd64.pyd in the project root (~20 s)
python -m pipeline.import_local      # ~1 minute: imports 2012 to Sep 2026 from E:\Algo Trading
python -m pipeline.signals           # ~70 s: classifies every trading day since 2013
cd web; npm install; npm run build; cd ..
```

## Run the app

```powershell
python -m uvicorn api.main:app --port 8010
```

Open **http://localhost:8010**. FastAPI serves both the API (`/api/...`, docs at `/docs`) and the
built React app. Port 8010 is used because 8000 is taken by another local project.

For UI development with hot reload, run the API with `--reload` and, in `web/`, `npm run dev`
(http://localhost:5173, which proxies `/api` to port 8010).

## Daily update (after 3:30 PM)

```powershell
python -B "E:\Algo Trading\fyers_auth\fyers_login.py" login   # FYERS needs a 2FA login each trading day
python -m pipeline.fyers_update                                 # fills every day since the last stored one,
                                                                # then classifies the new days
```

Overnight moves above 30% are listed for a manual check (usually a split or bonus that FYERS
does not adjust the same way as the local history).

## Tests

```powershell
python -m pytest              # 274 tests: every C++ algorithm against a brute-force or pandas reference,
                              # the imported data, the pipeline and every API endpoint
cd web; npm test              # 14 tests: formatting and UI components
```

The C++ library is tested through its Python bindings with pytest (instead of GoogleTest), so each
algorithm is compared with an independent reference implementation on thousands of random inputs.

## Build phases (all complete)

| Phase | Scope | Tests |
|---|---|---|
| 0 | Repository, C++ build, schema, local import, universe, FYERS updater, API skeleton | `tests/test_phase0_setup.py` |
| 1 | Binary search, topological sort, indicators, inversions, Mann-Kendall, LIS, sign test | `tests/test_phase1_features.py` |
| 2 | Percentile scores, classification, merge sort / quicksort ranking, rank churn | `tests/test_phase2_classify.py` |
| 3 | Correlation network: MST (Prim, Kruskal), clusters (BFS, DFS) | `tests/test_phase3_network.py` |
| 4 | Portfolio: tree DP, fractional and 0/1 knapsack, subset sum, coin change | `tests/test_phase4_portfolio.py` |
| 5 | Backtest: walk-forward, interval scheduling, DAG hindsight bound, metrics | `tests/test_phase5_backtest.py` |
| UI | React app: design system and seven screens | `web/src/**/*.test.ts(x)` |
| Final | Algorithm Lab: C++ benchmarks, measured vs theoretical growth | `tests/test_final_lab.py` |
