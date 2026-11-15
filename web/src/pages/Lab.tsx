import { useMutation, useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { FlaskConical, Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { baseChrome, EChart } from "@/components/charts/EChart";
import { Button, cn, Empty, ErrorState, PageHeader, Panel, Segmented, Skeleton, Slider } from "@/components/ui";
import { api } from "@/lib/api";
import { geometricSizes, int, millis, num } from "@/lib/format";
import { useChartColors } from "@/lib/theme";
import type { LabAlgorithm, LabResult } from "@/lib/types";

const EXPECTED_SLOPE: Record<string, string> = { n: "1", logn: "≈ 0", nlogn: "≈ 1.1", n2: "2", n2logn: "≈ 2.1", "2n": "exponential" };
const PRESETS: { label: string; ids: string[]; input: "random" | "sorted" | "nearly_sorted" }[] = [
  { label: "Sorting on nearly sorted input", ids: ["merge_sort", "quicksort_random", "quicksort_last"], input: "nearly_sorted" },
  { label: "Inversions: merge sort vs all pairs", ids: ["count_inversions", "count_inversions_naive"], input: "random" },
  { label: "LIS: patience vs DP", ids: ["lis_patience", "lis_dp"], input: "random" },
  { label: "MST: Prim vs Kruskal", ids: ["prim_mst", "kruskal_mst"], input: "random" },
  { label: "Subset sum: backtracking vs brute force", ids: ["subset_sum_backtracking", "subset_sum_brute_force"], input: "random" },
];

export function LabPage() {
  const catalog = useQuery({ queryKey: ["lab-algorithms"], queryFn: api.labAlgorithms, staleTime: Infinity });
  const [picked, setPicked] = useState<string[]>(PRESETS[0].ids);
  const [input, setInput] = useState<"random" | "sorted" | "nearly_sorted">("nearly_sorted");
  const [scale, setScale] = useState(1); // fraction of the largest safe size, as a power slider
  const [results, setResults] = useState<LabResult[]>([]);

  const algos = catalog.data?.algorithms ?? [];
  const byId = useMemo(() => Object.fromEntries(algos.map((a) => [a.id, a])), [algos]);
  const chosen = picked.map((id) => byId[id]).filter(Boolean) as LabAlgorithm[];
  const maxN = chosen.length ? Math.min(...chosen.map((a) => a.max_n)) : 0;
  const exponential = chosen.some((a) => a.curve === "2n");
  const hi = exponential ? Math.max(6, Math.round(maxN * (0.55 + 0.45 * scale))) : Math.max(10, Math.round(maxN * Math.pow(10, -2 * (1 - scale))));
  const sizes = exponential ? Array.from({ length: Math.min(8, hi - 5) }, (_, i) => hi - Math.min(8, hi - 5) + 1 + i) : geometricSizes(Math.max(10, Math.round(hi / 40)), hi, 7);

  const run = useMutation({
    mutationFn: async () => {
      const out: LabResult[] = [];
      for (const a of chosen) out.push(await api.labRun({ algorithm: a.id, sizes, input: a.inputs ? input : "random" }));
      return out;
    },
    onSuccess: setResults,
  });

  const started = useRef(false);
  useEffect(() => {
    if (!algos.length || started.current) return;
    started.current = true;
    run.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [algos.length]);

  const toggle = (id: string) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length >= 3 ? [...p.slice(1), id] : [...p, id]));

  const groups = useMemo(() => {
    const g = new Map<string, LabAlgorithm[]>();
    for (const a of algos) g.set(a.group, [...(g.get(a.group) ?? []), a]);
    return [...g.entries()];
  }, [algos]);

  return (
    <>
      <PageHeader
        index="07 · Algorithm Lab"
        title="Theory, measured"
        lede="Every algorithm in the app runs here on generated inputs, timed in C++ with std::chrono and instrumented to count its basic operations. On log-log axes a power law is a straight line whose slope is the exponent."
      />
      {catalog.isError && <ErrorState error={catalog.error} onRetry={() => catalog.refetch()} />}
      <div className="grid grid-cols-[320px_1fr] gap-5 max-xl:grid-cols-1">
        <Panel eyebrow="Pick up to three" title="Algorithms" bodyClassName="p-3" className="self-start">
          {catalog.isLoading && <Skeleton className="h-96" />}
          <div className="grid gap-4">
            {groups.map(([group, list]) => (
              <div key={group}>
                <div className="eyebrow mb-1.5 px-2">{group}</div>
                <div className="grid gap-0.5">
                  {list.map((a) => {
                    const on = picked.includes(a.id);
                    const slot = picked.indexOf(a.id);
                    return (
                      <button
                        key={a.id}
                        onClick={() => toggle(a.id)}
                        className={cn(
                          "flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-[13px] transition",
                          on ? "bg-panel-2 text-ink" : "text-ink-2 hover:bg-panel-2/60",
                        )}
                      >
                        <span
                          className="flex size-4 shrink-0 items-center justify-center rounded border text-[9px] font-bold text-white"
                          style={on ? { background: `var(--s${slot + 1})`, borderColor: "transparent" } : { borderColor: "var(--line-strong)" }}
                        >
                          {on ? slot + 1 : ""}
                        </span>
                        <span className="min-w-0 flex-1 truncate">{a.name}</span>
                        <span className="shrink-0 text-[10.5px] text-muted" title={`Syllabus unit ${a.unit}`}>Unit {a.unit}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <div className="grid content-start gap-5">
          <Panel eyebrow="Experiment" title="Set up a run">
            <div className="grid gap-4">
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((p) => (
                  <button
                    key={p.label}
                    onClick={() => {
                      setPicked(p.ids);
                      setInput(p.input);
                    }}
                    className="rounded-full border border-line px-3 py-1 text-[12px] text-ink-2 transition hover:border-accent hover:text-accent"
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap items-end gap-6">
                <div className="grid gap-1.5">
                  <span className="eyebrow">Input</span>
                  <Segmented
                    value={input}
                    onChange={setInput}
                    label="Input order"
                    options={[
                      { value: "random", label: "Random" },
                      { value: "sorted", label: "Sorted" },
                      { value: "nearly_sorted", label: "Nearly sorted" },
                    ]}
                  />
                </div>
                <div className="grid min-w-64 flex-1 gap-1.5">
                  <span className="eyebrow">
                    Largest n: <span className="num text-ink">{int(hi)}</span> · sizes {sizes.map((s) => int(s)).join(", ")}
                  </span>
                  <Slider label="Problem size" value={scale} min={0} max={1} step={0.05} onChange={setScale} />
                </div>
                <Button onClick={() => run.mutate()} loading={run.isPending} disabled={!chosen.length}>
                  <Play className="size-4" /> Run
                </Button>
              </div>
            </div>
          </Panel>

          {run.isError && <ErrorState error={run.error} onRetry={() => run.mutate()} />}
          {results.length === 0 && run.isPending && <Skeleton className="h-[420px]" />}
          {results.length > 0 && <Results results={results} byId={byId} stale={run.isPending} />}
          {results.length === 0 && !run.isPending && (
            <Empty>
              <FlaskConical className="mx-auto mb-2 size-5" /> Choose algorithms and press Run.
            </Empty>
          )}
        </div>
      </div>
    </>
  );
}

function Results({ results, byId, stale }: { results: LabResult[]; byId: Record<string, LabAlgorithm>; stale: boolean }) {
  const c = useChartColors();
  const [metric, setMetric] = useState<"time" | "ops">("time");
  const hasOps = results.every((r) => r.points.some((p) => p.ops > 0));
  const useOps = metric === "ops" && hasOps;

  const option = useMemo<EChartsOption>(() => {
    const chrome = baseChrome(c);
    const exp = results.some((r) => byId[r.algorithm]?.curve === "2n");
    return {
      animationDuration: 500,
      grid: { left: 64, right: 48, top: 16, bottom: 48 },
      textStyle: chrome.textStyle,
      tooltip: {
        ...chrome.tooltip,
        trigger: "axis",
        valueFormatter: (v: unknown) => (useOps ? int(v as number) : millis(v as number)),
      },
      xAxis: {
        type: exp ? "value" : "log",
        name: "n",
        nameLocation: "middle",
        nameGap: 28,
        nameTextStyle: { color: c.muted },
        axisLabel: { ...chrome.axisLabel, formatter: (v: number) => int(v) },
        axisLine: chrome.axisLine,
        splitLine: chrome.splitLine,
        min: exp ? "dataMin" : undefined,
      },
      yAxis: {
        type: "log",
        axisLabel: { ...chrome.axisLabel, formatter: (v: number) => (useOps ? int(v) : num(v, v < 1 ? 3 : 0)) },
        axisLine: chrome.axisLine,
        splitLine: chrome.splitLine,
      },
      series: results.flatMap((r, i) => {
        const color = c.series[i];
        const measured = {
          name: `${r.name}`,
          type: "line" as const,
          data: r.points.map((p) => [p.n, Math.max(useOps ? p.ops : p.millis, 1e-4)]),
          lineStyle: { color, width: 2 },
          itemStyle: { color, borderColor: c.panel, borderWidth: 2 },
          symbol: "circle",
          symbolSize: 8,
          endLabel: { show: results.length <= 4, formatter: () => `${i + 1}`, color: c.ink2, fontFamily: '"IBM Plex Mono", monospace' },
        };
        if (useOps) return [measured];
        return [
          measured,
          {
            name: `${r.name} · theory`,
            type: "line" as const,
            data: r.points.map((p) => [p.n, Math.max(p.theory_millis, 1e-4)]),
            lineStyle: { color, width: 1.5, type: "dashed" as const, opacity: 0.7 },
            symbol: "none",
            tooltip: { show: false },
          },
        ];
      }),
    } as EChartsOption;
  }, [results, byId, c, useOps]);

  return (
    <div className={cn("grid gap-5", stale && "opacity-60 transition-opacity")}>
      <Panel
        eyebrow={`Log-log · ${useOps ? "operations" : "time in ms"} against n · solid = measured, dashed = theory`}
        title="Growth with input size"
        actions={hasOps && <Segmented value={metric} onChange={setMetric} label="Metric" options={[{ value: "time", label: "Time" }, { value: "ops", label: "Operations" }]} />}
      >
        <EChart option={option} height={400} ariaLabel="Running time against input size on log-log axes" />
      </Panel>
      <div className={cn("grid gap-4", results.length === 1 ? "grid-cols-1" : results.length === 2 ? "grid-cols-2" : "grid-cols-3", "max-xl:grid-cols-1")}>
        {results.map((r, i) => {
          const a = byId[r.algorithm];
          const last = r.points[r.points.length - 1];
          return (
            <div key={r.algorithm} className="panel p-5">
              <div className="flex items-center gap-2">
                <span className="flex size-5 items-center justify-center rounded text-[11px] font-bold text-white" style={{ background: c.series[i] }}>
                  {i + 1}
                </span>
                <span className="eyebrow">Unit {a?.unit} · {a?.group}</span>
              </div>
              <div className="mt-2 text-[15px] font-semibold text-ink">{r.name}</div>
              <div className="num mt-1 text-[13px] text-accent">{r.complexity}</div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div>
                  <div className="eyebrow">Measured slope</div>
                  <div className="num mt-1 text-[22px] text-ink">{r.loglog_slope === null ? "—" : num(r.loglog_slope, 2)}</div>
                  <div className="text-[11.5px] text-muted">expected {EXPECTED_SLOPE[a?.curve ?? "n"]}</div>
                </div>
                <div>
                  <div className="eyebrow">Largest run</div>
                  <div className="num mt-1 text-[22px] text-ink">{millis(last.millis)}</div>
                  <div className="text-[11.5px] text-muted">
                    n = {int(last.n)}
                    {last.ops > 0 && ` · ${int(last.ops)} ${a?.ops ?? "ops"}`}
                  </div>
                </div>
              </div>
              <p className="mt-4 border-t border-line pt-3 text-[12px] text-ink-2">
                Used in the app for: <span className="text-ink">{a?.used_for}</span>
              </p>
            </div>
          );
        })}
      </div>
      <Panel eyebrow="Raw measurements" title="Points" bodyClassName="p-2">
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="border-b border-line">
                <th className="eyebrow px-3 py-2 text-left font-normal">n</th>
                {results.map((r, i) => (
                  <th key={r.algorithm} className="eyebrow px-3 py-2 text-right font-normal">
                    <span style={{ color: c.series[i] }}>■</span> {r.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results[0].points.map((p, row) => (
                <tr key={p.n} className="border-b border-line/60 last:border-0">
                  <td className="num px-3 py-1.5 text-ink-2">{int(p.n)}</td>
                  {results.map((r) => {
                    const q = r.points[row];
                    return (
                      <td key={r.algorithm} className="num px-3 py-1.5 text-right text-ink">
                        {q ? millis(q.millis) : "—"}
                        {q && q.ops > 0 && <span className="text-muted"> · {int(q.ops)}</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
