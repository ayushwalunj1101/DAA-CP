# API contract

The React app talks only to these endpoints. All responses are JSON; dates are `YYYY-MM-DD`.
`date` parameters default to the latest trading day in the database. Every endpoint is implemented. The exact response shapes used by the web app live in
`web/src/lib/types.ts`, which is kept in sync with the API; the sketches below are a summary.

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/api/health` | Server and C++ library are up | live |
| GET | `/api/meta` | Data range, universe month, last update | live |
| GET | `/api/symbols` | Sorted symbol list for Ctrl+K search | live |
| GET | `/api/stocks/{symbol}` | Bars, indicators, trend tests, class explanation | live |
| GET | `/api/overview` | Class counts, sector breakdown, Nifty 50, rank churn | live |
| GET | `/api/scanner` | Ranked bullish and bearish lists | live |
| GET | `/api/network` | MST nodes and edges, clusters | live |
| POST | `/api/portfolio` | Three allocations side by side | live |
| POST | `/api/backtest` | Equity curve, trades, metrics | live |
| GET | `/api/lab/algorithms` | Algorithms available for benchmarking | live |
| POST | `/api/lab/run` | Run a benchmark, return timings | live |

## Shapes

```ts
// GET /api/meta
{ first_date: string; last_date: string; universe_month: string; universe_size: number;
  local_end: string; last_update: string | null; unreviewed_flags: number }

// GET /api/symbols
{ symbols: { symbol: string; sector: string }[] }          // sorted by symbol

// GET /api/stocks/{symbol}?from=YYYY-MM-DD&to=YYYY-MM-DD
{ symbol: string; sector: string;
  bars: { date: string; open: number; high: number; low: number; close: number; volume: number }[];
  indicators: { date: string; ema20: number|null; ema50: number|null; ema200: number|null;
                vwap20: number|null; rsi14: number|null; atr14: number|null; rvol20: number|null;
                high20: number|null; low20: number|null }[];
  trend: { mk_z20: number; mk_z60: number; lis_ratio60: number; lds_ratio60: number;
           up_days60: number; sign_p60: number };
  classification: { cls: Class; bull_score: number; bear_score: number; quadrant: Quadrant;
                     checks: { label: string; passed: boolean; value: string }[] } }

type Class = "ESTABLISHED_BULLISH" | "DEVELOPING_BULLISH" | "NEUTRAL" | "DEVELOPING_BEARISH" | "ESTABLISHED_BEARISH";
type Quadrant = "ACCUMULATION" | "WEAK_RALLY" | "DISTRIBUTION" | "WEAK_SELLOFF";

// GET /api/overview?date=
{ date: string; stocks_scanned: number; counts: Record<Class, number>;
  sectors: { sector: string; counts: Record<Class, number> }[];
  nifty: { date: string; close: number }[];      // last 250 days
  rank_churn: { inversions: number; max_inversions: number; pct: number } }

// GET /api/scanner?date=&side=bullish|bearish&cls=&sector=&k=20&w=1,1,1,1,1
{ date: string; side: string; weights: number[];
  rows: { rank: number; symbol: string; sector: string; cls: Class; score: number;
          rank_change: number | null; quadrant: Quadrant; close: number; change_pct: number }[] }

// GET /api/network?date=&window=60&threshold=0.7&algo=prim|kruskal
{ date: string; algo: string; total_weight: number; millis: number;
  nodes: { symbol: string; sector: string; bull_score: number; cluster: number }[];
  edges: { a: string; b: string; rho: number; distance: number }[];
  clusters: { id: number; symbols: string[] }[] }

// POST /api/portfolio
// body: { capital: number; max_stocks: number; max_per_sector: number; risk_pct: number; fractional: boolean; date?: string }
{ date: string; candidates: string[]; diversified: string[];
  methods: { name: "fractional" | "knapsack01" | "subset_sum";
             positions: { symbol: string; sector: string; shares: number; price: number; cost: number; score: number }[];
             capital_used: number; cash_left: number; total_score: number; leftover_spent: number;
             millis: number; nodes_explored?: number }[] }

// POST /api/backtest
// body: { start: string; end: string; slots: number; hold_days: number; stop_atr: number; cost_pct: number }
{ equity: { date: string; strategy: number; nifty: number }[];
  trades: { symbol: string; entry_date: string; exit_date: string; entry: number; exit: number; ret_pct: number; slot: number }[];
  metrics: { total_return_pct: number; hit_rate: number; avg_trade_pct: number; max_drawdown_pct: number;
             trades_taken: number; max_possible_trades: number; hindsight_pct: number; kendall_tau: number } }

// POST /api/lab/run
// body: { algorithm: string; sizes: number[]; input: "random" | "sorted" | "nearly_sorted" }
{ algorithm: string; complexity: string;
  points: { n: number; millis: number; ops: number }[] }
```
