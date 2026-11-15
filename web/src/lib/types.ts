// Shapes returned by the FastAPI server (see docs/api-contract.md).

export type Cls =
  | "ESTABLISHED_BULLISH"
  | "DEVELOPING_BULLISH"
  | "NEUTRAL"
  | "DEVELOPING_BEARISH"
  | "ESTABLISHED_BEARISH";
export type Quadrant = "ACCUMULATION" | "WEAK_RALLY" | "DISTRIBUTION" | "WEAK_SELLOFF" | null;

export interface Meta {
  first_date: string;
  last_date: string;
  universe_month: string;
  universe_size: number;
  local_end: string;
  last_update: string | null;
  unreviewed_flags: number;
}

export interface SymbolRow {
  symbol: string;
  sector: string;
}

export interface Bar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface IndicatorRow {
  date: string;
  ema20: number | null;
  ema50: number | null;
  ema200: number | null;
  vwap20: number | null;
  rsi14: number | null;
  atr14: number | null;
  rvol20: number | null;
  high20: number | null;
  low20: number | null;
  vol_spike: number | null;
}

export interface Classification {
  cls: Cls;
  bull_score: number;
  bear_score: number;
  bull_rank: number;
  bear_rank: number;
  scanned: number;
  quadrant: Quadrant;
  side: "bullish" | "bearish";
  inputs: { key: string; label: string; pct: number }[];
  checks: { label: string; passed: boolean; value: string }[];
}

export interface StockDetail {
  symbol: string;
  sector: string;
  as_of: string;
  bars: Bar[];
  indicators: IndicatorRow[];
  trend: Record<string, number | null>;
  classification: Classification | null;
}

export interface Overview {
  date: string;
  stocks_scanned: number;
  counts: Record<Cls, number>;
  sectors: { sector: string; counts: Record<Cls, number>; total: number }[];
  nifty: { date: string; close: number }[];
  rank_churn: { inversions: number | null; max_inversions: number | null; pct: number | null };
  cutoffs: Record<string, number | null>;
}

export interface ScannerRow {
  rank: number;
  symbol: string;
  sector: string;
  cls: Cls;
  score: number;
  rank_change: number | null;
  quadrant: Quadrant;
  close: number;
  change_pct: number | null;
}

export interface Scanner {
  date: string;
  side: "bullish" | "bearish";
  weights: number[];
  rows: ScannerRow[];
}

export interface NetworkNode {
  symbol: string;
  sector: string;
  bull_score: number | null;
  cls: Cls | null;
  cluster: number;
}

export interface Network {
  date: string;
  algo: "prim" | "kruskal";
  window: number;
  threshold: number;
  total_weight: number;
  millis: number;
  ops: number;
  threshold_edges: number;
  nodes: NetworkNode[];
  edges: { a: string; b: string; rho: number; distance: number }[];
  clusters: { id: number; symbols: string[] }[];
}

export interface Position {
  symbol: string;
  sector: string;
  shares: number;
  price: number;
  cost: number;
  score: number;
}

export interface PortfolioMethod {
  name: "fractional" | "knapsack01" | "subset_sum";
  positions: Position[];
  capital_used: number;
  cash_left: number;
  total_score: number;
  millis: number;
  leftover_spent: number;
  what_if?: boolean;
  dp_cells?: number;
  unit?: number;
  nodes_explored?: number;
  brute_force_nodes?: number;
  reached_target?: boolean;
}

export interface Portfolio {
  date: string;
  candidates: string[];
  diversified: string[];
  candidate_links: [string, string][];
  diversify_millis: number;
  methods: PortfolioMethod[];
}

export interface PortfolioBody {
  capital: number;
  max_stocks: number;
  max_per_sector: number;
  risk_pct: number;
  fractional: boolean;
}

export interface BacktestBody {
  start: string;
  end?: string | null;
  slots: number;
  hold_days: number;
  stop_atr: number;
  cost_pct: number;
  min_class: number;
}

export interface Trade {
  symbol: string;
  entry_date: string;
  exit_date: string;
  entry: number;
  exit: number;
  ret_pct: number;
  slot: number;
  reason: "stop" | "time" | "signal" | "end";
}

export interface Backtest {
  start: string;
  end: string;
  equity: { date: string; strategy: number; nifty: number }[];
  trades: Trade[];
  metrics: {
    total_return_pct: number;
    cagr_pct: number;
    nifty_return_pct: number;
    hit_rate: number | null;
    avg_trade_pct: number | null;
    max_drawdown_pct: number;
    nifty_max_drawdown_pct: number;
    trades_taken: number;
    signals: number;
    trades_per_slot: number;
    max_possible_trades_one_slot: number;
    hindsight_log_return: number;
    hindsight_pct: number | null;
    kendall_tau: number;
    exit_reasons: Record<string, number>;
    seconds: number;
  };
}

export interface LabAlgorithm {
  id: string;
  name: string;
  unit: string;
  group: string;
  complexity: string;
  curve: string;
  max_n: number;
  inputs: boolean;
  ops: string | null;
  used_for: string;
}

export interface LabResult {
  algorithm: string;
  name: string;
  complexity: string;
  input: string;
  points: { n: number; millis: number; ops: number; theory_millis: number }[];
  loglog_slope: number | null;
}
