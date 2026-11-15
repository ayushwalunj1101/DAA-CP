import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { ArrowUpRight, Cpu } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { baseChrome, EChart } from "@/components/charts/EChart";
import { ClassBadge, cn, ErrorState, Field, PageHeader, Panel, Segmented, Select, Skeleton, Slider } from "@/components/ui";
import { api } from "@/lib/api";
import { CLASS_META, day, int, millis, num, sectorLabel } from "@/lib/format";
import { useChartColors } from "@/lib/theme";
import type { Network, NetworkNode } from "@/lib/types";

export function NetworkPage() {
  const [algo, setAlgo] = useState<"prim" | "kruskal">("prim");
  const [windowDays, setWindowDays] = useState(60);
  const [threshold, setThreshold] = useState(0.7);
  const [thresholdLive, setThresholdLive] = useState(0.7);
  const [sector, setSector] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setThreshold(thresholdLive), 300);
    return () => clearTimeout(t);
  }, [thresholdLive]);

  const q = useQuery({
    queryKey: ["network", algo, windowDays, threshold],
    queryFn: () => api.network({ algo, window: windowDays, threshold }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader
        index="04 · Correlation Network"
        title="A constellation of co-moving stocks"
        lede={
          <>
            Every stock is a star; the lines are the minimum spanning tree of the correlation distance d = √(2(1 − ρ)). Stocks
            linked here move most alike, so the portfolio builder never picks two neighbours.
            {q.data && <span className="text-ink"> Window ending {day(q.data.date)}.</span>}
          </>
        }
      />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      <div className="grid grid-cols-[1fr_340px] gap-5 max-xl:grid-cols-1">
        <Panel
          eyebrow="Minimum spanning tree"
          title={q.data ? `${q.data.nodes.length} stocks · ${q.data.edges.length} links` : "Building the tree…"}
          actions={<ClassKey />}
          bodyClassName="p-0"
        >
          <div className={cn("relative", q.isFetching && "opacity-60 transition-opacity")}>
            {q.data ? (
              <Constellation net={q.data} sector={sector} selected={selected} onSelect={setSelected} />
            ) : (
              <Skeleton className="m-5 h-[620px]" />
            )}
          </div>
        </Panel>

        <div className="grid content-start gap-5">
          <Panel eyebrow="Greedy MST" title="Algorithm">
            <div className="grid gap-4">
              <Segmented
                value={algo}
                onChange={setAlgo}
                label="MST algorithm"
                options={[
                  { value: "prim", label: "Prim · O(V²)" },
                  { value: "kruskal", label: "Kruskal · O(E log E)" },
                ]}
              />
              {q.data && (
                <div className="grid grid-cols-2 gap-3">
                  <Metric label="Run time" value={millis(q.data.millis)} icon />
                  <Metric label={algo === "prim" ? "Relaxations" : "Comparisons"} value={int(q.data.ops)} />
                  <Metric label="Total weight" value={num(q.data.total_weight, 3)} />
                  <Metric label="Edges considered" value={int((q.data.nodes.length * (q.data.nodes.length - 1)) / 2)} />
                </div>
              )}
              <p className="text-[12px] leading-relaxed text-muted">
                Both algorithms return a tree of the same total weight (cut property). On this dense graph Prim's O(V²)
                scan beats Kruskal's sort of every edge.
              </p>
            </div>
          </Panel>

          <Panel eyebrow="BFS components" title="Clusters">
            <div className="grid gap-4">
              <Field label={`Correlation threshold ρ ≥ ${thresholdLive.toFixed(2)}`}>
                <Slider label="Correlation threshold" value={thresholdLive} min={0.4} max={0.95} step={0.05} onChange={(v) => setThresholdLive(v)} />
              </Field>
              <Field label="Window">
                <Segmented
                  value={windowDays}
                  onChange={setWindowDays}
                  label="Return window"
                  options={[
                    { value: 20, label: "20 d" },
                    { value: 60, label: "60 d" },
                    { value: 120, label: "120 d" },
                  ]}
                />
              </Field>
              {q.data && <Clusters net={q.data} onPick={setSelected} />}
            </div>
          </Panel>

          <Panel eyebrow="Highlight" title="Sector">
            <Select value={sector} onChange={(e) => setSector(e.target.value)} className="w-full">
              <option value="">No highlight</option>
              {q.data &&
                [...new Set(q.data.nodes.map((n) => n.sector))].sort().map((s) => (
                  <option key={s} value={s}>
                    {sectorLabel(s)}
                  </option>
                ))}
            </Select>
          </Panel>

          {q.data && selected && <NodeCard net={q.data} symbol={selected} onPick={setSelected} />}
        </div>
      </div>
    </>
  );
}

function Metric({ label, value, icon }: { label: string; value: string; icon?: boolean }) {
  return (
    <div className="rounded-lg border border-line bg-raised px-3 py-2.5">
      <div className="eyebrow flex items-center gap-1.5">
        {icon && <Cpu className="size-3" />}
        {label}
      </div>
      <div className="num mt-1 text-[16px] text-ink">{value}</div>
    </div>
  );
}

function ClassKey() {
  return (
    <div className="flex flex-wrap gap-3 text-[11.5px] text-ink-2">
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-bull" /> ▲ bullish
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-neutral" /> ● neutral
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-bear" /> ▼ bearish
      </span>
      <span className="text-muted">size = bullish score</span>
    </div>
  );
}

function nodeColor(n: NetworkNode, c: ReturnType<typeof useChartColors>) {
  if (!n.cls) return c.neutral;
  const side = CLASS_META[n.cls].side;
  return side === "bull" ? c.bull : side === "bear" ? c.bear : c.neutral;
}

function Constellation({ net, sector, selected, onSelect }: { net: Network; sector: string; selected: string | null; onSelect: (s: string) => void }) {
  const c = useChartColors();
  const neighbours = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const e of net.edges) {
      if (!m.has(e.a)) m.set(e.a, new Set());
      if (!m.has(e.b)) m.set(e.b, new Set());
      m.get(e.a)!.add(e.b);
      m.get(e.b)!.add(e.a);
    }
    return m;
  }, [net.edges]);

  const option = useMemo<EChartsOption>(() => {
    const focus = selected ? new Set([selected, ...(neighbours.get(selected) ?? [])]) : null;
    const dim = (sym: string, s: string) => (focus ? !focus.has(sym) : sector ? s !== sector : false);
    const chrome = baseChrome(c);
    return {
      animationDurationUpdate: 400,
      tooltip: {
        ...chrome.tooltip,
        formatter: (p: unknown) => {
          const d = (p as { dataType: string; data: { name?: string; source?: string; target?: string; rho?: number; node?: NetworkNode } }).data;
          if ((p as { dataType: string }).dataType === "edge") return `${d.source} — ${d.target}<br/>ρ = ${num(d.rho ?? null, 3)}`;
          const n = d.node!;
          return `<b>${n.symbol}</b> · ${sectorLabel(n.sector)}<br/>${n.cls ? CLASS_META[n.cls].label : "Not classified"}<br/>bullish score ${num(n.bull_score, 1)}${n.cluster ? `<br/>cluster ${n.cluster}` : ""}`;
        },
      },
      series: [
        {
          type: "graph",
          layout: "force",
          roam: true,
          draggable: true,
          force: { repulsion: 18, gravity: 0.16, edgeLength: [3, 12], friction: 0.32 },
          zoom: 0.9,
          scaleLimit: { min: 0.4, max: 6 },
          label: { show: false },
          labelLayout: { hideOverlap: true },
          emphasis: { focus: "adjacency", label: { show: true, color: c.ink, fontFamily: '"IBM Plex Mono", monospace', fontSize: 11 }, lineStyle: { width: 2 } },
          data: net.nodes.map((n) => {
            const color = nodeColor(n, c);
            const faded = dim(n.symbol, n.sector);
            const isSel = n.symbol === selected;
            return {
              name: n.symbol,
              node: n,
              symbolSize: 4 + ((n.bull_score ?? 30) / 100) * 13,
              itemStyle: {
                color,
                opacity: faded ? 0.12 : 0.95,
                borderColor: isSel || (sector && n.sector === sector) ? c.accent : c.panel,
                borderWidth: isSel ? 3 : sector && n.sector === sector ? 1.5 : 1,
                shadowBlur: faded ? 0 : 8,
                shadowColor: color,
              },
              label: { show: isSel || (!!focus && focus.has(n.symbol)), color: c.ink, fontFamily: '"IBM Plex Mono", monospace', fontSize: 11 },
            };
          }),
          links: net.edges.map((e) => ({
            source: e.a,
            target: e.b,
            rho: e.rho,
            lineStyle: {
              color: c.axis,
              width: 0.6 + Math.max(0, e.rho) * 1.6,
              opacity: focus ? (focus.has(e.a) && focus.has(e.b) ? 0.9 : 0.06) : 0.55,
            },
          })),
        },
      ],
    };
  }, [net, c, sector, selected, neighbours]);

  const onEvents = useMemo(
    () => ({
      click: (p: unknown) => {
        const e = p as { dataType: string; name: string };
        if (e.dataType === "node") onSelect(e.name);
      },
    }),
    [onSelect],
  );
  return <EChart option={option} height={660} onEvents={onEvents} ariaLabel="Correlation network: minimum spanning tree of stocks" />;
}

function Clusters({ net, onPick }: { net: Network; onPick: (s: string) => void }) {
  const total = net.clusters.reduce((a, cl) => a + cl.symbols.length, 0);
  return (
    <div>
      <div className="mb-2 text-[12.5px] text-ink-2">
        <span className="num text-ink">{net.clusters.length}</span> clusters of 2+ stocks hold{" "}
        <span className="num text-ink">{total}</span> of {net.nodes.length}; the threshold graph has{" "}
        <span className="num text-ink">{int(net.threshold_edges)}</span> edges.
      </div>
      <div className="grid max-h-[260px] gap-2 overflow-y-auto pr-1">
        {net.clusters.slice(0, 12).map((cl) => (
          <div key={cl.id} className="rounded-lg border border-line bg-raised p-2.5">
            <div className="eyebrow mb-1.5">
              Cluster {cl.id} · {cl.symbols.length} stocks
            </div>
            <div className="flex flex-wrap gap-1">
              {cl.symbols.slice(0, 14).map((s) => (
                <button key={s} onClick={() => onPick(s)} className="num rounded bg-panel-2 px-1.5 py-0.5 text-[11px] text-ink-2 hover:text-accent">
                  {s}
                </button>
              ))}
              {cl.symbols.length > 14 && <span className="text-[11px] text-muted">+{cl.symbols.length - 14}</span>}
            </div>
          </div>
        ))}
        {net.clusters.length === 0 && <div className="text-[12.5px] text-muted">No pair is correlated this strongly.</div>}
      </div>
    </div>
  );
}

function NodeCard({ net, symbol, onPick }: { net: Network; symbol: string; onPick: (s: string) => void }) {
  const node = net.nodes.find((n) => n.symbol === symbol);
  const links = useCallback(
    () =>
      net.edges
        .filter((e) => e.a === symbol || e.b === symbol)
        .map((e) => ({ other: e.a === symbol ? e.b : e.a, rho: e.rho }))
        .sort((a, b) => b.rho - a.rho),
    [net.edges, symbol],
  )();
  if (!node) return null;
  return (
    <Panel
      eyebrow="Selected"
      title={symbol}
      actions={
        <Link to={`/stock/${symbol}`} className="inline-flex items-center gap-1 text-[12px] text-accent hover:underline">
          Open <ArrowUpRight className="size-3.5" />
        </Link>
      }
    >
      <div className="mb-3 flex items-center gap-3">
        <ClassBadge cls={node.cls} compact />
        <span className="text-[12.5px] text-muted">{sectorLabel(node.sector)}</span>
      </div>
      <div className="eyebrow mb-1.5">Neighbours in the tree</div>
      <div className="grid gap-1">
        {links.map((l) => (
          <button key={l.other} onClick={() => onPick(l.other)} className="flex justify-between rounded-md px-2 py-1 text-[13px] hover:bg-panel-2">
            <span className="num text-ink">{l.other}</span>
            <span className="num text-muted">ρ {num(l.rho, 3)}</span>
          </button>
        ))}
      </div>
    </Panel>
  );
}
