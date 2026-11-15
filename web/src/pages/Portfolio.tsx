import { useMutation } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { ArrowRight, Check, GitBranch, Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { DataTable } from "@/components/DataTable";
import { Button, cn, Empty, ErrorState, Field, PageHeader, Panel, Skeleton, Slider, TextInput, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { day, int, millis, num, rupees, rupeesCompact, sectorLabel } from "@/lib/format";
import type { Portfolio, PortfolioBody, PortfolioMethod, Position } from "@/lib/types";

const METHOD_INFO: Record<PortfolioMethod["name"], { title: string; algo: string; unit: string; blurb: string }> = {
  fractional: {
    title: "Fractional shares",
    algo: "Fractional knapsack · greedy",
    unit: "Unit IV",
    blurb: "Best score per rupee first; the last position is cut to fit, so every rupee is used.",
  },
  knapsack01: {
    title: "Whole positions",
    algo: "0/1 knapsack · dynamic programming",
    unit: "Unit III",
    blurb: "Each position is bought in full or not at all; the DP table finds the best total score.",
  },
  subset_sum: {
    title: "Whole positions with limits",
    algo: "Subset sum · backtracking",
    unit: "Unit IV",
    blurb: "Spend at least 95% of capital with at most K stocks and s per sector; dead branches are pruned.",
  },
};

export function PortfolioPage() {
  const [form, setForm] = useState<PortfolioBody>({ capital: 1_000_000, max_stocks: 8, max_per_sector: 2, risk_pct: 1, fractional: true });
  const [active, setActive] = useState<PortfolioMethod["name"]>("knapsack01");
  const m = useMutation({ mutationFn: (body: PortfolioBody) => api.portfolio(body) });

  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    m.mutate(form);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const set = <K extends keyof PortfolioBody>(k: K, v: PortfolioBody[K]) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <>
      <PageHeader
        index="05 · Portfolio Builder"
        title="Diversify first, then fit the capital"
        lede={
          <>
            The top 30 bullish stocks go through a tree DP on the correlation MST, so no two picks are each other's closest
            neighbour. The survivors are sized by risk and allocated three ways, from the most relaxed to the most constrained.
          </>
        }
      />

      <div className="grid grid-cols-[300px_1fr] gap-5 max-xl:grid-cols-1">
        <Panel eyebrow="Inputs" title="Your constraints" className="self-start xl:sticky xl:top-20">
          <form
            className="grid gap-5"
            onSubmit={(e) => {
              e.preventDefault();
              m.mutate(form);
            }}
          >
            <Field label="Capital (₹)" hint={rupeesCompact(form.capital)}>
              <TextInput type="number" min={10000} step={10000} value={form.capital} onChange={(e) => set("capital", Number(e.target.value))} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Max stocks">
                <TextInput type="number" min={1} max={30} value={form.max_stocks} onChange={(e) => set("max_stocks", Number(e.target.value))} />
              </Field>
              <Field label="Per sector">
                <TextInput type="number" min={1} max={30} value={form.max_per_sector} onChange={(e) => set("max_per_sector", Number(e.target.value))} />
              </Field>
            </div>
            <Field label={`Risk per position: ${form.risk_pct.toFixed(1)}% of capital`} hint="A 2-ATR move against a position costs this much.">
              <Slider label="Risk per position" value={form.risk_pct} min={0.25} max={5} step={0.25} onChange={(v) => set("risk_pct", v)} />
            </Field>
            <Toggle checked={form.fractional} onChange={(v) => set("fractional", v)} label="My broker offers fractional shares" />
            <Button type="submit" loading={m.isPending}>
              <Sparkles className="size-4" /> Build portfolio
            </Button>
          </form>
        </Panel>

        <div className="grid content-start gap-5">
          {m.isError && <ErrorState error={m.error} onRetry={() => m.mutate(form)} />}
          {m.isPending && !m.data && <Skeleton className="h-[520px]" />}
          {m.data && <PortfolioResult p={m.data} active={active} onActive={setActive} capital={form.capital} stale={m.isPending} />}
        </div>
      </div>
    </>
  );
}

function PortfolioResult({ p, active, onActive, capital, stale }: { p: Portfolio; active: PortfolioMethod["name"]; onActive: (n: PortfolioMethod["name"]) => void; capital: number; stale: boolean }) {
  const byName = Object.fromEntries(p.methods.map((m) => [m.name, m])) as Record<PortfolioMethod["name"], PortfolioMethod>;
  const ordered = byName.fractional.total_score >= byName.knapsack01.total_score - 1e-6 && byName.knapsack01.total_score >= byName.subset_sum.total_score - 1e-6;
  const current = byName[active];

  return (
    <div className={cn("grid gap-5", stale && "opacity-60 transition-opacity")}>
      {/* ---------- pipeline ---------- */}
      <Panel eyebrow={`Signals of ${day(p.date)}`} title="From candidates to a diversified shortlist">
        <div className="flex flex-wrap items-center gap-4">
          <PipeStep value={p.candidates.length} label="bullish candidates" note="top 30 by rank" />
          <ArrowRight className="size-5 text-muted" />
          <div className="flex items-center gap-2 rounded-lg border border-accent/40 bg-accent-soft px-3 py-2 text-[12.5px] text-accent">
            <GitBranch className="size-4" /> tree DP on the MST · {millis(p.diversify_millis)}
          </div>
          <ArrowRight className="size-5 text-muted" />
          <PipeStep value={p.diversified.length} label="diversified stocks" note={`${p.candidate_links.length} MST links between candidates`} />
        </div>
        <div className="mt-4 flex flex-wrap gap-1.5">
          {p.candidates.map((s) => {
            const kept = p.diversified.includes(s);
            return (
              <Link
                key={s}
                to={`/stock/${s}`}
                className={cn(
                  "num rounded-md px-2 py-1 text-[11.5px] transition",
                  kept ? "bg-bull-soft text-bull ring-1 ring-bull/30" : "bg-panel-2 text-muted line-through decoration-1",
                )}
                title={kept ? "Kept" : "Dropped: directly linked to a higher-scoring candidate"}
              >
                {s}
              </Link>
            );
          })}
        </div>
      </Panel>

      {/* ---------- three methods ---------- */}
      <div className="grid grid-cols-3 gap-4 max-2xl:grid-cols-1">
        {p.methods.map((m) => (
          <MethodCard key={m.name} m={m} capital={capital} active={m.name === active} onClick={() => onActive(m.name)} />
        ))}
      </div>
      <div className={cn("flex items-center gap-2 rounded-lg px-4 py-2.5 text-[12.5px]", ordered ? "bg-bull-soft text-bull" : "bg-bear-soft text-bear")}>
        <Check className="size-4" />
        Total score: fractional <span className="num">{num(byName.fractional.total_score, 1)}</span> ≥ 0/1{" "}
        <span className="num">{num(byName.knapsack01.total_score, 1)}</span> ≥ with limits{" "}
        <span className="num">{num(byName.subset_sum.total_score, 1)}</span>
        <span className="text-ink-2">: each method solves the previous one's problem with one more restriction.</span>
      </div>

      {/* ---------- positions ---------- */}
      <div className="grid grid-cols-[1.6fr_1fr] gap-5 max-2xl:grid-cols-1">
        <Panel eyebrow={METHOD_INFO[active].algo} title={`Positions · ${METHOD_INFO[active].title}`} bodyClassName="p-2">
          {current.positions.length === 0 ? <Empty>No position fits these constraints.</Empty> : <Positions rows={current.positions} fractional={active === "fractional"} />}
        </Panel>
        <Panel eyebrow="Sector mix" title="Where the capital goes">
          <SectorMix rows={current.positions} />
        </Panel>
      </div>
    </div>
  );
}

function PipeStep({ value, label, note }: { value: number; label: string; note: string }) {
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className="font-display text-[38px] leading-none font-[380] tracking-[-0.03em] text-ink tabular-nums">{value}</span>
        <span className="text-[13px] text-ink-2">{label}</span>
      </div>
      <div className="text-[11.5px] text-muted">{note}</div>
    </div>
  );
}

function MethodCard({ m, capital, active, onClick }: { m: PortfolioMethod; capital: number; active: boolean; onClick: () => void }) {
  const info = METHOD_INFO[m.name];
  const used = Math.min(100, (100 * m.capital_used) / capital);
  return (
    <button
      onClick={onClick}
      className={cn(
        "panel relative flex flex-col items-stretch p-5 text-left transition",
        active ? "ring-2 ring-accent" : "hover:border-line-strong",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="eyebrow">{info.unit} · {info.algo}</div>
          <div className="mt-1 text-[15px] font-semibold text-ink">{info.title}</div>
        </div>
        {m.what_if && <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10.5px] text-accent">what-if</span>}
      </div>
      <div className="mt-4 flex items-baseline gap-2">
        <span className="font-display text-[44px] leading-none font-[380] tracking-[-0.03em] text-ink tabular-nums">{num(m.total_score, 1)}</span>
        <span className="text-[12.5px] text-muted">total score · {m.positions.length} stocks</span>
      </div>
      <div className="mt-4">
        <div className="mb-1 flex justify-between text-[12px]">
          <span className="text-muted">Capital used</span>
          <span className="num text-ink">
            {rupeesCompact(m.capital_used)} <span className="text-muted">({num(used, 1)}%)</span>
          </span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-panel-2">
          <div className="h-full rounded-full bg-accent" style={{ width: `${used}%` }} />
        </div>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-[12px]">
        <dt className="text-muted">Cash left</dt>
        <dd className="num text-right text-ink">{rupees(m.cash_left)}</dd>
        <dt className="text-muted">Coin change spent</dt>
        <dd className="num text-right text-ink">{m.name === "fractional" ? "—" : rupees(m.leftover_spent)}</dd>
        <dt className="text-muted">Compute time</dt>
        <dd className="num text-right text-ink">{millis(m.millis)}</dd>
        {m.dp_cells !== undefined && (
          <>
            <dt className="text-muted">DP table cells</dt>
            <dd className="num text-right text-ink">{int(m.dp_cells)}</dd>
          </>
        )}
        {m.nodes_explored !== undefined && (
          <>
            <dt className="text-muted">Nodes explored</dt>
            <dd className="num text-right text-ink">
              {int(m.nodes_explored)}
              <div className="text-[11px] text-muted">
                {num((100 * m.nodes_explored) / Math.max(1, m.brute_force_nodes ?? 1), 2)}% of brute force
              </div>
            </dd>
          </>
        )}
      </dl>
      <p className="mt-4 text-[12px] leading-relaxed text-ink-2">{info.blurb}</p>
    </button>
  );
}

function Positions({ rows, fractional }: { rows: Position[]; fractional: boolean }) {
  const columns = useMemo<ColumnDef<Position, unknown>[]>(
    () => [
      {
        accessorKey: "symbol",
        header: "Stock",
        cell: (c) => (
          <Link to={`/stock/${c.row.original.symbol}`} className="num font-medium text-ink hover:text-accent" onClick={(e) => e.stopPropagation()}>
            {c.row.original.symbol}
          </Link>
        ),
      },
      { accessorKey: "sector", header: "Sector", cell: (c) => <span className="text-ink-2">{sectorLabel(c.getValue<string>())}</span> },
      { accessorKey: "shares", header: "Shares", cell: (c) => <span className="num">{fractional ? num(c.getValue<number>(), 2) : int(c.getValue<number>())}</span>, meta: { align: "right" } },
      { accessorKey: "price", header: "Price", cell: (c) => <span className="num">{num(c.getValue<number>())}</span>, meta: { align: "right" } },
      { accessorKey: "cost", header: "Cost", cell: (c) => <span className="num text-ink">{rupees(c.getValue<number>())}</span>, meta: { align: "right" } },
      { accessorKey: "score", header: "Score", cell: (c) => <span className="num">{num(c.getValue<number>(), 1)}</span>, meta: { align: "right" } },
    ],
    [fractional],
  );
  return <DataTable data={rows} columns={columns} initialSort={[{ id: "cost", desc: true }]} />;
}

function SectorMix({ rows }: { rows: Position[] }) {
  const total = rows.reduce((a, r) => a + r.cost, 0);
  const bySector = new Map<string, number>();
  for (const r of rows) bySector.set(r.sector, (bySector.get(r.sector) ?? 0) + r.cost);
  const items = [...bySector.entries()].sort((a, b) => b[1] - a[1]);
  if (!items.length) return <Empty>No positions.</Empty>;
  return (
    <div className="grid gap-3">
      {items.map(([s, v]) => (
        <div key={s}>
          <div className="mb-1 flex justify-between text-[12.5px]">
            <span className="text-ink-2">{sectorLabel(s)}</span>
            <span className="num text-ink">
              {num((100 * v) / total, 1)}% <span className="text-muted">· {rupeesCompact(v)}</span>
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-panel-2">
            <div className="h-full rounded-full bg-[var(--s1)]" style={{ width: `${(100 * v) / total}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
