import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Check, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { PriceChart } from "@/components/charts/PriceChart";
import { ClassBadge, cn, Delta, Empty, ErrorState, PageHeader, Panel, Segmented, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { CLASS_META, day, int, num, QUADRANT_LABEL, sectorLabel } from "@/lib/format";
import type { StockDetail } from "@/lib/types";

const RANGES = [
  { value: "3M", days: 92 },
  { value: "6M", days: 183 },
  { value: "1Y", days: 365 },
  { value: "3Y", days: 1096 },
  { value: "All", days: 0 },
] as const;
type Range = (typeof RANGES)[number]["value"];

function rangeStart(end: string, r: Range): string | undefined {
  const spec = RANGES.find((x) => x.value === r)!;
  if (!spec.days) return "2012-01-01";
  const d = new Date(`${end}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - spec.days);
  return d.toISOString().slice(0, 10);
}

export function StockPage() {
  const { symbol = "RELIANCE" } = useParams();
  const [range, setRange] = useState<Range>("1Y");
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: 5 * 60_000 });
  const end = meta.data?.last_date;
  const from = end ? rangeStart(end, range) : undefined;
  const q = useQuery({
    queryKey: ["stock", symbol, from],
    queryFn: () => api.stock(symbol, from),
    enabled: !!end,
    placeholderData: keepPreviousData,
  });

  const d = q.data;
  const last = d?.bars[d.bars.length - 1];
  const prev = d && d.bars.length > 1 ? d.bars[d.bars.length - 2] : undefined;
  const change = last && prev ? (last.close / prev.close - 1) * 100 : null;

  return (
    <>
      <PageHeader
        index="03 · Stock Analysis"
        title={symbol.toUpperCase()}
        lede={
          d ? (
            <span className="inline-flex flex-wrap items-center gap-x-4 gap-y-2">
              <span>{sectorLabel(d.sector)}</span>
              <ClassBadge cls={d.classification?.cls} />
              <span className="num text-[22px] text-ink">₹{num(last?.close)}</span>
              <Delta value={change} className="text-[15px]" />
              <span className="text-muted">close on {day(d.as_of)}</span>
            </span>
          ) : (
            "Loading…"
          )
        }
        actions={
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-1.5 text-[12px] text-muted md:inline-flex">
              <Search className="size-3.5" /> Ctrl K to switch stock
            </span>
            <Segmented value={range} onChange={setRange} label="Date range" options={RANGES.map((r) => ({ value: r.value, label: r.value }))} />
          </div>
        }
      />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {!d && !q.isError && <Skeleton className="h-[460px]" />}
      {d && (
        <div className={cn("grid gap-5", q.isFetching && "opacity-70 transition-opacity")}>
          <Panel eyebrow="Price, moving averages and volume" title="Daily chart" bodyClassName="p-3 pt-4">
            <PriceChart bars={d.bars} indicators={d.indicators} />
            <p className="px-2 pt-2 text-[12px] text-muted">
              Volume bars in the accent colour are spikes: volume above the 60-day median + 3 × MAD (median found by merge sort).
            </p>
          </Panel>
          <StockFacts d={d} />
        </div>
      )}
    </>
  );
}

function StockFacts({ d }: { d: StockDetail }) {
  const c = d.classification;
  const t = d.trend;
  const latest = d.indicators[d.indicators.length - 1];
  const side = c?.side ?? "bullish";
  const tone = side === "bullish" ? "bull" : "bear";
  const fill = tone === "bull" ? "bg-bull" : "bg-bear";
  const text = tone === "bull" ? "text-bull" : "text-bear";

  const trendRows = useMemo(
    () => [
      { label: "Mann–Kendall Z, 60 days", value: num(t.mk_z60), note: "|Z| ≥ 1.96 is significant" },
      { label: "Mann–Kendall Z, 20 days", value: num(t.mk_z20), note: "via inversion counting" },
      { label: "LIS ratio, 60 days", value: num(t.lis_ratio60, 3), note: "longest rising run ÷ 60" },
      { label: "LDS ratio, 60 days", value: num(t.lds_ratio60, 3), note: "longest falling run ÷ 60" },
      { label: "Up / down days, 60", value: `${int(t.up_days60)} / ${int(t.down_days60)}`, note: `sign test p ↑ ${num(t.sign_p_up60, 4)} · ↓ ${num(t.sign_p_down60, 4)}` },
      { label: "RSI 14 · ATR 14 · RVOL 20", value: `${num(latest?.rsi14, 1)} · ${num(latest?.atr14)} · ${num(latest?.rvol20)}`, note: "Wilder smoothing, prefix sums" },
    ],
    [t, latest],
  );

  return (
    <div className="grid grid-cols-[1.15fr_1fr_1fr] gap-5 max-2xl:grid-cols-2 max-lg:grid-cols-1">
      <Panel eyebrow="Why this class" title={c ? CLASS_META[c.cls].label : "Not classified on this day"}>
        {!c && <Empty>This stock was not in the day's universe of 500, so it has no class.</Empty>}
        {c && (
          <>
            <ul className="grid gap-2">
              {c.checks.map((ch, i) => (
                <li
                  key={ch.label}
                  className={cn(
                    "flex items-start gap-3 rounded-lg px-3 py-2",
                    ch.passed ? "bg-panel-2" : "",
                    i === 4 && "mt-2 border-t border-line pt-3",
                  )}
                >
                  <span
                    className={cn(
                      "mt-0.5 flex size-4.5 shrink-0 items-center justify-center rounded-full",
                      ch.passed ? `${fill} text-white` : "border border-line-strong text-muted",
                    )}
                    aria-label={ch.passed ? "passed" : "not met"}
                  >
                    {ch.passed ? <Check className="size-3" strokeWidth={3} /> : <X className="size-3" />}
                  </span>
                  <div className="min-w-0">
                    <div className={cn("text-[13px]", ch.passed ? "text-ink" : "text-ink-2")}>{ch.label}</div>
                    <div className="num text-[11.5px] text-muted">{ch.value}</div>
                  </div>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-[12px] text-muted">
              Rules 1–4 make a stock Established; rule 5 or 6 plus rule 7 make it Developing. Rank{" "}
              <span className="num text-ink">{side === "bullish" ? c.bull_rank : c.bear_rank}</span> of{" "}
              <span className="num text-ink">{c.scanned}</span> · quadrant {c.quadrant ? QUADRANT_LABEL[c.quadrant] : "—"}.
            </p>
          </>
        )}
      </Panel>

      <Panel eyebrow={`${side === "bullish" ? "Bullish" : "Bearish"} score`} title="What drives the score">
        {c ? (
          <>
            <div className="mb-5 flex items-end gap-3">
              <span className={`font-display text-[52px] leading-none font-[360] tracking-[-0.03em] ${text} tabular-nums`}>
                {num(side === "bullish" ? c.bull_score : c.bear_score, 1)}
              </span>
              <span className="pb-1.5 text-[12.5px] text-muted">average of five percentile ranks across today's universe</span>
            </div>
            <div className="grid gap-3.5">
              {c.inputs.map((inp) => (
                <div key={inp.key}>
                  <div className="mb-1 flex justify-between text-[12.5px]">
                    <span className="text-ink-2">{inp.label}</span>
                    <span className="num text-ink">{num(inp.pct, 1)}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-panel-2">
                    <div className={`h-full rounded-full ${fill}`} style={{ width: `${inp.pct}%`, opacity: 0.35 + inp.pct / 160 }} />
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <Empty>No score for this day.</Empty>
        )}
      </Panel>

      <Panel eyebrow="Trend tests and indicators" title="The numbers behind it" className="max-2xl:col-span-2 max-lg:col-span-1">
        <dl className="grid gap-0">
          {trendRows.map((r) => (
            <div key={r.label} className="grid grid-cols-[1fr_auto] gap-x-4 border-b border-line/70 py-2.5 last:border-b-0">
              <dt className="text-[13px] text-ink-2">{r.label}</dt>
              <dd className="num text-right text-[14px] text-ink">{r.value}</dd>
              <dd className="col-span-2 text-[11.5px] text-muted">{r.note}</dd>
            </div>
          ))}
        </dl>
      </Panel>
    </div>
  );
}
