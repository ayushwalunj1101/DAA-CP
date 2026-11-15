import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { baseChrome, EChart } from "@/components/charts/EChart";
import { TimeSeries } from "@/components/charts/TimeSeries";
import { ErrorState, PageHeader, Panel, Skeleton, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { CLASS_META, CLASS_ORDER, day, int, num, pct, sectorLabel } from "@/lib/format";
import { useChartColors } from "@/lib/theme";
import type { Overview } from "@/lib/types";

export function OverviewPage() {
  const [date, setDate] = useState<string>("");
  const q = useQuery({ queryKey: ["overview", date], queryFn: () => api.overview(date || undefined) });

  return (
    <>
      <PageHeader
        index="01 · Market Overview"
        title="The market, read through momentum"
        lede={
          q.data ? (
            <>
              {int(q.data.stocks_scanned)} of the 500 most-traded NSE stocks scored and classified at the close of{" "}
              <span className="text-ink">{day(q.data.date)}</span>. Each stock is ranked on five percentile inputs; the class
              rules decide whether its momentum is established, developing or absent.
            </>
          ) : (
            "Loading the latest classification…"
          )
        }
        actions={
          <label className="flex flex-col gap-1.5">
            <span className="eyebrow">Analysis date</span>
            <TextInput type="date" value={date} max={q.data?.date} onChange={(e) => setDate(e.target.value)} />
          </label>
        }
      />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.isLoading && <OverviewSkeleton />}
      {q.data && <OverviewBody o={q.data} />}
    </>
  );
}

function OverviewSkeleton() {
  return (
    <div className="grid gap-5">
      <div className="grid grid-cols-5 gap-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
      <Skeleton className="h-80" />
    </div>
  );
}

function OverviewBody({ o }: { o: Overview }) {
  const c = useChartColors();
  const bullish = o.counts.ESTABLISHED_BULLISH + o.counts.DEVELOPING_BULLISH;
  const bearish = o.counts.ESTABLISHED_BEARISH + o.counts.DEVELOPING_BEARISH;
  const nifty = useMemo(() => [{ name: "Nifty 50", data: o.nifty.map((p) => ({ date: p.date, value: p.close })), color: c.series[0], area: true }], [o.nifty, c]);
  const niftyChange = o.nifty.length > 1 ? (o.nifty[o.nifty.length - 1].close / o.nifty[0].close - 1) * 100 : null;

  return (
    <div className="grid gap-5">
      {/* ---------- class distribution ---------- */}
      <div className="grid grid-cols-5 gap-4 max-xl:grid-cols-3 max-md:grid-cols-2">
        {CLASS_ORDER.map((cls, i) => {
          const m = CLASS_META[cls];
          const tone = m.side === "bull" ? "text-bull" : m.side === "bear" ? "text-bear" : "text-ink";
          const share = (100 * o.counts[cls]) / Math.max(1, o.stocks_scanned);
          return (
            <motion.div
              key={cls}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.04 * i, duration: 0.4 }}
              className="panel group relative px-5 py-4"
            >
              <div className="eyebrow flex items-center gap-2">
                <span aria-hidden className={tone}>
                  {m.side === "bull" ? "▲" : m.side === "bear" ? "▼" : "●"}
                </span>
                {m.label}
              </div>
              <div className={`mt-2 font-display text-[46px] leading-none font-[360] tracking-[-0.03em] tabular-nums ${tone}`}>
                {o.counts[cls]}
              </div>
              <div className="mt-3 h-[3px] overflow-hidden rounded-full bg-panel-2">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${share}%`,
                    background: m.side === "bull" ? "var(--bull)" : m.side === "bear" ? "var(--bear)" : "var(--muted)",
                    opacity: m.strength === 1 ? 0.55 : 1,
                  }}
                />
              </div>
              <div className="mt-1.5 text-[12px] text-muted">{num(share, 1)}% of scanned</div>
            </motion.div>
          );
        })}
      </div>

      <div className="grid grid-cols-[1.35fr_1fr] gap-5 max-xl:grid-cols-1">
        {/* ---------- Nifty ---------- */}
        <Panel
          eyebrow="Benchmark"
          title="Nifty 50, last 250 sessions"
          actions={
            <span className="num text-[13px]">
              <span className="text-muted">1Y </span>
              <span className={niftyChange && niftyChange >= 0 ? "text-bull" : "text-bear"}>{pct(niftyChange)}</span>
            </span>
          }
        >
          <TimeSeries series={nifty} height={290} ariaLabel="Nifty 50 closing level over the last 250 sessions" format={(v) => num(v, 0)} />
        </Panel>

        {/* ---------- breadth + churn ---------- */}
        <div className="grid gap-5">
          <Panel eyebrow="Breadth" title="Bullish versus bearish">
            <BreadthBar bullish={bullish} bearish={bearish} neutral={o.counts.NEUTRAL} />
            <p className="mt-4 text-[13px] leading-relaxed text-ink-2">
              {bullish > bearish ? "Bullish" : "Bearish"} classes outnumber the other side{" "}
              <span className="num text-ink">
                {Math.max(bullish, bearish)} to {Math.min(bullish, bearish)}
              </span>
              . Cut-offs today: top-10% bullish score <span className="num text-ink">{num(o.cutoffs.bull_cut_est, 1)}</span>,
              top-25% <span className="num text-ink">{num(o.cutoffs.bull_cut_dev, 1)}</span>.
            </p>
          </Panel>
          <Panel eyebrow="Counting inversions" title="How much the ranking moved since yesterday">
            <div className="flex items-end gap-4">
              <div className="font-display text-[46px] leading-none font-[360] tracking-[-0.03em] text-accent tabular-nums">
                {o.rank_churn.pct === null ? "—" : `${num(o.rank_churn.pct, 1)}%`}
              </div>
              <div className="pb-1 text-[12.5px] text-muted">of stock pairs swapped order</div>
            </div>
            <p className="mt-3 text-[13px] leading-relaxed text-ink-2">
              <span className="num text-ink">{int(o.rank_churn.inversions)}</span> inversions out of{" "}
              <span className="num text-ink">{int(o.rank_churn.max_inversions)}</span> possible pairs (Kendall tau distance,
              merge-sort counting in O(n log n)). A low figure means today's input to the sort is nearly sorted.
            </p>
          </Panel>
        </div>
      </div>

      {/* ---------- sectors ---------- */}
      <Panel
        eyebrow="Sector breakdown · hash map counts"
        title="Where the momentum sits"
        actions={<Legend c={c} />}
      >
        <SectorChart o={o} />
        <p className="mt-2 text-[12px] text-muted">
          Bearish counts extend left, bullish counts right; hover a bar for neutral and total counts. Open the{" "}
          <Link to="/scanner" className="text-accent hover:underline">
            scanner
          </Link>{" "}
          to see the stocks.
        </p>
      </Panel>
    </div>
  );
}

function BreadthBar({ bullish, bearish, neutral }: { bullish: number; bearish: number; neutral: number }) {
  const total = Math.max(1, bullish + bearish + neutral);
  const seg = (v: number) => `${(100 * v) / total}%`;
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-panel-2">
        <div className="h-full bg-bull" style={{ width: seg(bullish) }} />
        <div className="h-full bg-neutral" style={{ width: seg(neutral), marginLeft: 2, marginRight: 2 }} />
        <div className="h-full bg-bear" style={{ width: seg(bearish) }} />
      </div>
      <div className="mt-2 flex justify-between text-[12px]">
        <span className="text-bull">▲ {bullish} bullish</span>
        <span className="text-muted">● {neutral} neutral</span>
        <span className="text-bear">▼ {bearish} bearish</span>
      </div>
    </div>
  );
}

function Legend({ c }: { c: ReturnType<typeof useChartColors> }) {
  const items = [
    { label: "Est. bearish", color: c.bear },
    { label: "Dev. bearish", color: c.bearDim },
    { label: "Dev. bullish", color: c.bullDim },
    { label: "Est. bullish", color: c.bull },
  ];
  return (
    <div className="flex flex-wrap gap-3 text-[11.5px] text-ink-2">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm" style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

function SectorChart({ o }: { o: Overview }) {
  const c = useChartColors();
  const option = useMemo<EChartsOption>(() => {
    const rows = [...o.sectors]
      .filter((s) => s.total > 0)
      .map((s) => ({
        ...s,
        net: (s.counts.ESTABLISHED_BULLISH + s.counts.DEVELOPING_BULLISH - s.counts.ESTABLISHED_BEARISH - s.counts.DEVELOPING_BEARISH) / s.total,
      }))
      .sort((a, b) => a.net - b.net);
    const chrome = baseChrome(c);
    const bar = (name: string, key: keyof Overview["counts"], color: string, sign: 1 | -1) => ({
      name,
      type: "bar" as const,
      stack: "total",
      barWidth: 14,
      data: rows.map((r) => sign * r.counts[key]),
      itemStyle: { color, borderRadius: sign > 0 ? [0, 4, 4, 0] : [4, 0, 0, 4], borderColor: c.panel, borderWidth: 1 },
      emphasis: { focus: "series" as const },
    });
    return {
      animationDuration: 600,
      grid: { left: 110, right: 24, top: 8, bottom: 28 },
      textStyle: chrome.textStyle,
      tooltip: {
        ...chrome.tooltip,
        trigger: "axis",
        axisPointer: { type: "shadow", shadowStyle: { color: "rgba(127,133,147,0.08)" } },
        formatter: (params: unknown) => {
          const p = params as { dataIndex: number }[];
          const r = rows[p[0].dataIndex];
          return `<b>${sectorLabel(r.sector)}</b> · ${r.total} stocks<br/>▲ est ${r.counts.ESTABLISHED_BULLISH} · dev ${r.counts.DEVELOPING_BULLISH}<br/>● neutral ${r.counts.NEUTRAL}<br/>▼ dev ${r.counts.DEVELOPING_BEARISH} · est ${r.counts.ESTABLISHED_BEARISH}`;
        },
      },
      xAxis: {
        type: "value",
        axisLabel: { ...chrome.axisLabel, formatter: (v: number) => String(Math.abs(v)) },
        splitLine: chrome.splitLine,
        axisLine: { show: false },
      },
      yAxis: {
        type: "category",
        data: rows.map((r) => sectorLabel(r.sector)),
        axisLabel: { color: c.ink2, fontSize: 12 },
        axisLine: chrome.axisLine,
        axisTick: { show: false },
      },
      series: [
        bar("Est. bearish", "ESTABLISHED_BEARISH", c.bear, -1),
        bar("Dev. bearish", "DEVELOPING_BEARISH", c.bearDim, -1),
        bar("Dev. bullish", "DEVELOPING_BULLISH", c.bullDim, 1),
        bar("Est. bullish", "ESTABLISHED_BULLISH", c.bull, 1),
      ],
    };
  }, [o.sectors, c]);
  return <EChart option={option} height={Math.max(260, o.sectors.length * 26 + 40)} ariaLabel="Bullish and bearish stock counts by sector" />;
}
