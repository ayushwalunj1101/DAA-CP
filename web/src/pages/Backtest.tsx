import { useMutation } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import type { EChartsOption } from "echarts";
import { Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { baseChrome, EChart } from "@/components/charts/EChart";
import { TimeSeries } from "@/components/charts/TimeSeries";
import { DataTable } from "@/components/DataTable";
import { Button, cn, Delta, ErrorState, Field, PageHeader, Panel, Segmented, Skeleton, Stat, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { day, int, num, pct, rupeesCompact } from "@/lib/format";
import { useChartColors } from "@/lib/theme";
import type { Backtest, BacktestBody, Trade } from "@/lib/types";

export function BacktestPage() {
  const [form, setForm] = useState<BacktestBody>({ start: "2014-01-01", end: null, slots: 5, hold_days: 60, stop_atr: 2, cost_pct: 0.1, min_class: 2 });
  const m = useMutation({ mutationFn: (b: BacktestBody) => api.backtest(b) });
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    m.mutate(form);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const set = <K extends keyof BacktestBody>(k: K, v: BacktestBody[K]) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <>
      <PageHeader
        index="06 · Backtest"
        title="Would the signals have worked?"
        lede="Walk-forward: every decision uses only data up to that day's close, and trades enter at the next open. The universe is rebuilt each month from that month's most-traded stocks, so delisted names are included."
      />
      <div className="grid grid-cols-[300px_1fr] gap-5 max-xl:grid-cols-1">
        <Panel eyebrow="Rules" title="Test settings" className="self-start xl:sticky xl:top-20">
          <form
            className="grid gap-5"
            onSubmit={(e) => {
              e.preventDefault();
              m.mutate(form);
            }}
          >
            <Field label="Signals">
              <Segmented
                value={form.min_class}
                onChange={(v) => set("min_class", v)}
                label="Signal classes"
                options={[
                  { value: 2, label: "Established" },
                  { value: 1, label: "All bullish" },
                ]}
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="From">
                <TextInput type="date" value={form.start} onChange={(e) => set("start", e.target.value)} />
              </Field>
              <Field label="To">
                <TextInput type="date" value={form.end ?? ""} onChange={(e) => set("end", e.target.value || null)} />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Slots">
                <TextInput type="number" min={1} max={20} value={form.slots} onChange={(e) => set("slots", Number(e.target.value))} />
              </Field>
              <Field label="Hold days">
                <TextInput type="number" min={1} max={120} value={form.hold_days} onChange={(e) => set("hold_days", Number(e.target.value))} />
              </Field>
              <Field label="Stop (× ATR)">
                <TextInput type="number" min={0.5} max={10} step={0.5} value={form.stop_atr} onChange={(e) => set("stop_atr", Number(e.target.value))} />
              </Field>
              <Field label="Cost / side %">
                <TextInput type="number" min={0} max={2} step={0.05} value={form.cost_pct} onChange={(e) => set("cost_pct", Number(e.target.value))} />
              </Field>
            </div>
            <Button type="submit" loading={m.isPending}>
              <Play className="size-4" /> Run backtest
            </Button>
            <p className="text-[11.5px] leading-relaxed text-muted">
              The first run over 12 years takes about 15 s while every signal's trade is simulated; changing only the slots is
              fast after that.
            </p>
          </form>
        </Panel>
        <div className="grid content-start gap-5">
          {m.isError && <ErrorState error={m.error} onRetry={() => m.mutate(form)} />}
          {m.isPending && !m.data && <Skeleton className="h-[640px]" />}
          {m.data && <BacktestResult b={m.data} slots={form.slots} stale={m.isPending} />}
        </div>
      </div>
    </>
  );
}

function BacktestResult({ b, slots, stale }: { b: Backtest; slots: number; stale: boolean }) {
  const c = useChartColors();
  const x = b.metrics;
  const series = useMemo(
    () => [
      { name: "Nifty 50 buy-and-hold", data: b.equity.map((e) => ({ date: e.date, value: e.nifty })), color: c.bench, width: 2 as const },
      { name: "Strategy", data: b.equity.map((e) => ({ date: e.date, value: e.strategy })), color: c.series[0], width: 2 as const },
    ],
    [b.equity, c],
  );
  const beat = x.total_return_pct > x.nifty_return_pct;

  return (
    <div className={cn("grid gap-5", stale && "opacity-60 transition-opacity")}>
      <div className="grid grid-cols-4 gap-4 max-2xl:grid-cols-2">
        <Stat label="Total return" value={pct(x.total_return_pct, 0)} tone={beat ? "bull" : "bear"} note={<>Nifty 50: {pct(x.nifty_return_pct, 0)}</>} />
        <Stat label="CAGR" value={pct(x.cagr_pct, 1)} note={`${day(b.start)} – ${day(b.end)}`} />
        <Stat label="Max drawdown" value={pct(x.max_drawdown_pct, 1)} tone="bear" note={<>Nifty 50: {pct(x.nifty_max_drawdown_pct, 1)}</>} />
        <Stat label="Hit rate" value={`${num(x.hit_rate, 1)}%`} note={<>avg trade <Delta value={x.avg_trade_pct} /></>} />
      </div>

      <Panel
        eyebrow="Equity, ₹10 L start"
        title="Strategy against Nifty 50"
        actions={
          <div className="flex gap-4 text-[12px] text-ink-2">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded" style={{ background: c.series[0] }} /> Strategy
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded" style={{ background: c.bench }} /> Nifty 50
            </span>
          </div>
        }
      >
        <TimeSeries series={series} height={340} ariaLabel="Strategy equity curve compared with Nifty 50" format={(v) => rupeesCompact(v)} />
      </Panel>

      <div className="grid grid-cols-3 gap-4 max-2xl:grid-cols-1">
        <Panel eyebrow="Interval scheduling · greedy" title="Slot capacity">
          <div className="font-display text-[40px] leading-none font-[380] tracking-[-0.03em] tabular-nums">
            {num(x.trades_per_slot, 0)} <span className="text-[18px] text-muted">/ {int(x.max_possible_trades_one_slot)}</span>
          </div>
          <p className="mt-3 text-[12.5px] leading-relaxed text-ink-2">
            Trades each slot took, against the most non-overlapping trades one slot could have taken with full knowledge
            (earliest-finish-time greedy over all {int(x.signals)} signals).
          </p>
        </Panel>
        <Panel eyebrow="Longest path in a DAG" title="Hindsight bound">
          <div className="font-display text-[40px] leading-none font-[380] tracking-[-0.03em] tabular-nums">
            {x.hindsight_pct === null ? "—" : `${num(x.hindsight_pct, 3)}%`}
          </div>
          <p className="mt-3 text-[12.5px] leading-relaxed text-ink-2">
            Share of the best possible single-slot log return ({num(x.hindsight_log_return, 1)}), found by DP over trading days
            in time order. A perfect-hindsight ceiling, not a target.
          </p>
        </Panel>
        <Panel eyebrow="Counting inversions" title="Ranking quality">
          <div className="font-display text-[40px] leading-none font-[380] tracking-[-0.03em] tabular-nums">τ {num(x.kendall_tau, 3)}</div>
          <p className="mt-3 text-[12.5px] leading-relaxed text-ink-2">
            Kendall tau between each day's bullish ranking and the ranking by actual 20-day returns (1 = perfect order, 0 = no
            relation).
          </p>
        </Panel>
      </div>

      <Panel eyebrow="One row per slot" title="Trade timeline" actions={<ExitReasons reasons={x.exit_reasons} />}>
        <Timeline trades={b.trades} slots={slots} />
      </Panel>

      <Panel eyebrow={`${int(x.trades_taken)} trades`} title="Trade list" bodyClassName="p-2">
        <Trades rows={b.trades} />
      </Panel>
    </div>
  );
}

function ExitReasons({ reasons }: { reasons: Record<string, number> }) {
  const labels: Record<string, string> = { signal: "signal ended", stop: "stop hit", time: "time", end: "end of data" };
  return (
    <div className="flex flex-wrap gap-3 text-[12px] text-muted">
      {Object.entries(reasons).map(([k, v]) => (
        <span key={k}>
          {labels[k] ?? k} <span className="num text-ink">{int(v)}</span>
        </span>
      ))}
    </div>
  );
}

function Timeline({ trades, slots }: { trades: Trade[]; slots: number }) {
  const c = useChartColors();
  const option = useMemo<EChartsOption>(() => {
    const chrome = baseChrome(c);
    const data = trades.map((t) => ({
      value: [t.slot, Date.parse(t.entry_date), Date.parse(t.exit_date) + 86_400_000, t.ret_pct],
      trade: t,
      itemStyle: { color: t.ret_pct >= 0 ? c.bull : c.bear },
    }));
    return {
      animation: false,
      grid: { left: 64, right: 16, top: 8, bottom: 52 },
      tooltip: {
        ...chrome.tooltip,
        formatter: (p: unknown) => {
          const t = (p as { data: { trade: Trade } }).data.trade;
          return `<b>${t.symbol}</b> · slot ${t.slot + 1}<br/>${t.entry_date} → ${t.exit_date}<br/>${t.ret_pct >= 0 ? "▲" : "▼"} ${pct(t.ret_pct)} · exit: ${t.reason}`;
        },
      },
      dataZoom: [
        { type: "inside", xAxisIndex: 0 },
        { type: "slider", xAxisIndex: 0, height: 18, bottom: 8, borderColor: c.line, textStyle: { color: c.muted } },
      ],
      xAxis: { type: "time", axisLabel: chrome.axisLabel, axisLine: chrome.axisLine, splitLine: { show: false } },
      yAxis: {
        type: "category",
        data: Array.from({ length: slots }, (_, i) => `Slot ${i + 1}`),
        axisLabel: { color: c.ink2, fontSize: 11.5 },
        axisLine: chrome.axisLine,
        axisTick: { show: false },
      },
      series: [
        {
          type: "custom",
          renderItem: (_params: unknown, api: unknown) => {
            const a = api as { value: (i: number) => number; coord: (v: [number, number]) => [number, number]; size: (v: [number, number]) => [number, number] };
            const start = a.coord([a.value(1), a.value(0)]);
            const end = a.coord([a.value(2), a.value(0)]);
            const h = a.size([0, 1])[1] * 0.56;
            return {
              type: "rect",
              shape: { x: start[0], y: start[1] - h / 2, width: Math.max(1.5, end[0] - start[0] - 1), height: h, r: 2 },
              style: { fill: a.value(3) >= 0 ? c.bull : c.bear },
            };
          },
          encode: { x: [1, 2], y: 0 },
          data,
        },
      ],
    } as EChartsOption;
  }, [trades, slots, c]);
  return <EChart option={option} height={Math.max(180, slots * 34 + 70)} ariaLabel="Timeline of trades in each capital slot" />;
}

function Trades({ rows }: { rows: Trade[] }) {
  const columns = useMemo<ColumnDef<Trade, unknown>[]>(
    () => [
      { accessorKey: "entry_date", header: "Entry", cell: (c) => <span className="num text-ink-2">{c.getValue<string>()}</span> },
      { accessorKey: "exit_date", header: "Exit", cell: (c) => <span className="num text-ink-2">{c.getValue<string>()}</span> },
      {
        accessorKey: "symbol",
        header: "Stock",
        cell: (c) => (
          <Link to={`/stock/${c.getValue<string>()}`} className="num font-medium text-ink hover:text-accent">
            {c.getValue<string>()}
          </Link>
        ),
      },
      { accessorKey: "slot", header: "Slot", cell: (c) => <span className="num">{c.getValue<number>() + 1}</span>, meta: { align: "right" } },
      { accessorKey: "entry", header: "Entry ₹", cell: (c) => <span className="num">{num(c.getValue<number>())}</span>, meta: { align: "right" } },
      { accessorKey: "exit", header: "Exit ₹", cell: (c) => <span className="num">{num(c.getValue<number>())}</span>, meta: { align: "right" } },
      { accessorKey: "ret_pct", header: "Return", cell: (c) => <Delta value={c.getValue<number>()} />, meta: { align: "right" } },
      { accessorKey: "reason", header: "Exit reason", cell: (c) => <span className="text-ink-2">{c.getValue<string>()}</span> },
    ],
    [],
  );
  return <DataTable data={rows} columns={columns} pageSize={15} initialSort={[{ id: "entry_date", desc: true }]} dense />;
}
