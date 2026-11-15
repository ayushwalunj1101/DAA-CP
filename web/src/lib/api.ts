import type {
  Backtest,
  BacktestBody,
  LabAlgorithm,
  LabResult,
  Meta,
  Network,
  Overview,
  Portfolio,
  PortfolioBody,
  Scanner,
  StockDetail,
  SymbolRow,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function query(params: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => request<Meta>("/meta"),
  symbols: (q = "") => request<{ symbols: SymbolRow[] }>(`/symbols${query({ q })}`),
  stock: (symbol: string, from?: string, to?: string) =>
    request<StockDetail>(`/stocks/${encodeURIComponent(symbol)}${query({ from, to })}`),
  overview: (date?: string) => request<Overview>(`/overview${query({ date })}`),
  scanner: (p: { date?: string; side: string; cls?: string; sector?: string; k: number; w?: string }) =>
    request<Scanner>(`/scanner${query(p)}`),
  network: (p: { date?: string; window: number; threshold: number; algo: string }) =>
    request<Network>(`/network${query(p)}`),
  portfolio: (body: PortfolioBody & { date?: string }) =>
    request<Portfolio>("/portfolio", { method: "POST", body: JSON.stringify(body) }),
  backtest: (body: BacktestBody) => request<Backtest>("/backtest", { method: "POST", body: JSON.stringify(body) }),
  labAlgorithms: () => request<{ algorithms: LabAlgorithm[] }>("/lab/algorithms"),
  labRun: (body: { algorithm: string; sizes: number[]; input: string }) =>
    request<LabResult>("/lab/run", { method: "POST", body: JSON.stringify(body) }),
};
