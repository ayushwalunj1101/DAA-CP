import { keepPreviousData, useQuery, type UseQueryResult } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { DataTable } from "@/components/DataTable";
import {
  Button,
  ClassBadge,
  Delta,
  Empty,
  ErrorState,
  Field,
  PageHeader,
  Panel,
  RankChange,
  ScoreBar,
  Segmented,
  Select,
  Skeleton,
  Slider,
  TextInput,
} from "@/components/ui";
import { api } from "@/lib/api";
import { day, num, QUADRANT_LABEL, sectorLabel } from "@/lib/format";
import type { Scanner, ScannerRow } from "@/lib/types";

const WEIGHTS = [
  { key: "trend", label: "Trend strength", hint: "Mann–Kendall Z" },
  { key: "consistency", label: "Consistency", hint: "LIS ratio" },
  { key: "rs", label: "Relative strength", hint: "vs Nifty 50" },
  { key: "volume", label: "Volume", hint: "up vs down RVOL" },
  { key: "vwap", label: "VWAP position", hint: "in ATR units" },
];
const SECTORS = ["AUTO", "BANK", "CAPGOODS", "CEMENT", "CHEM", "CONSUMER", "ENERGY", "FIN", "FMCG", "INFRA", "IT", "MEDIA", "METAL", "OTHER", "PHARMA", "REALTY", "SERVICES", "TELECOM"];

export function ScannerPage() {
  const [date, setDate] = useState("");
  const [cls, setCls] = useState<"" | "ESTABLISHED" | "DEVELOPING">("");
  const [sector, setSector] = useState("");
  const [k, setK] = useState(20);
  const [weights, setWeights] = useState([1, 1, 1, 1, 1]);
  const [w, setW] = useState<string | undefined>(undefined);

  useEffect(() => {
    const t = setTimeout(() => setW(weights.every((x) => x === 1) ? undefined : weights.join(",")), 250);
    return () => clearTimeout(t);
  }, [weights]);

  const common = { date: date || undefined, sector: sector || undefined, k, w };
  const bull = useQuery({
    queryKey: ["scanner", "bullish", common, cls],
    queryFn: () => api.scanner({ ...common, side: "bullish", cls: cls ? `${cls}_BULLISH` : undefined }),
    placeholderData: keepPreviousData,
  });
  const bear = useQuery({
    queryKey: ["scanner", "bearish", common, cls],
    queryFn: () => api.scanner({ ...common, side: "bearish", cls: cls ? `${cls}_BEARISH` : undefined }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader
        index="02 · Momentum Scanner"
        title="Strongest momentum, ranked"
        lede={
          <>
            Each list is sorted twice with stable merge sort: first by relative strength, then by score, so ties keep a
            meaningful order. Change the weights and the day is re-scored and re-ranked from its stored percentiles.
            {bull.data && <span className="text-ink"> As of {day(bull.data.date)}.</span>}
          </>
        }
      />

      <div className="grid grid-cols-[300px_1fr] gap-5 max-xl:grid-cols-1">
        {/* ---------- filters ---------- */}
        <Panel eyebrow="Filters" title="Shape the lists" className="self-start xl:sticky xl:top-20">
          <div className="grid gap-5">
            <Field label="Class">
              <Segmented
                value={cls}
                onChange={setCls}
                label="Class filter"
                options={[
                  { value: "", label: "Both" },
                  { value: "ESTABLISHED", label: "Established" },
                  { value: "DEVELOPING", label: "Developing" },
                ]}
              />
            </Field>
            <Field label="Sector">
              <Select value={sector} onChange={(e) => setSector(e.target.value)}>
                <option value="">All sectors</option>
                {SECTORS.map((s) => (
                  <option key={s} value={s}>
                    {sectorLabel(s)}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Top K">
                <Select value={k} onChange={(e) => setK(Number(e.target.value))}>
                  {[10, 20, 50, 100].map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Date">
                <TextInput type="date" value={date} onChange={(e) => setDate(e.target.value)} />
              </Field>
            </div>
            <div className="h-px bg-line" />
            <div className="flex items-center justify-between">
              <span className="eyebrow">Score weights</span>
              <Button variant="ghost" className="h-7 px-2 text-[12px]" onClick={() => setWeights([1, 1, 1, 1, 1])}>
                <RotateCcw className="size-3.5" /> Equal
              </Button>
            </div>
            {WEIGHTS.map((item, i) => (
              <div key={item.key} className="grid gap-1.5">
                <div className="flex items-baseline justify-between text-[12.5px]">
                  <span className="text-ink-2">
                    {item.label} <span className="text-muted">· {item.hint}</span>
                  </span>
                  <span className="num text-ink">{weights[i].toFixed(1)}</span>
                </div>
                <Slider
                  label={`${item.label} weight`}
                  value={weights[i]}
                  min={0}
                  max={3}
                  step={0.5}
                  onChange={(v) => setWeights((ws) => ws.map((x, j) => (j === i ? v : x)))}
                />
              </div>
            ))}
          </div>
        </Panel>

        {/* ---------- lists ---------- */}
        <div className="grid grid-cols-1 gap-5 min-[2000px]:grid-cols-2">
          <ScannerList side="bullish" query={bull} />
          <ScannerList side="bearish" query={bear} />
        </div>
      </div>
    </>
  );
}

function ScannerList({ side, query }: { side: "bullish" | "bearish"; query: UseQueryResult<Scanner> }) {
  const navigate = useNavigate();
  const tone = side === "bullish" ? "bull" : "bear";
  const columns = useMemo<ColumnDef<ScannerRow, unknown>[]>(
    () => [
      { accessorKey: "rank", header: "Rank", cell: (c) => <span className="num text-ink-2">{c.getValue<number>()}</span>, meta: { align: "right" } },
      { accessorKey: "rank_change", header: "Δ", cell: (c) => <RankChange value={c.getValue<number | null>()} />, meta: { align: "right" }, enableSorting: false },
      {
        accessorKey: "symbol",
        header: "Stock",
        cell: (c) => (
          <div>
            <div className="num font-medium text-ink">{c.row.original.symbol}</div>
            <div className="text-[11.5px] text-muted">{sectorLabel(c.row.original.sector)}</div>
          </div>
        ),
      },
      { accessorKey: "cls", header: "Class", cell: (c) => <ClassBadge cls={c.row.original.cls} compact /> },
      { accessorKey: "score", header: "Score", cell: (c) => <ScoreBar value={c.getValue<number>()} tone={tone} /> },
      { accessorKey: "close", header: "Close", cell: (c) => <span className="num text-ink">{num(c.getValue<number>())}</span>, meta: { align: "right" } },
      { accessorKey: "change_pct", header: "1D", cell: (c) => <Delta value={c.getValue<number | null>()} />, meta: { align: "right" } },
      {
        accessorKey: "quadrant",
        header: "Price · volume",
        cell: (c) => {
          const q = c.row.original.quadrant;
          return <span className="text-[12px] text-ink-2">{q ? QUADRANT_LABEL[q] : "—"}</span>;
        },
        enableSorting: false,
      },
    ],
    [tone],
  );

  return (
    <Panel
      eyebrow={side === "bullish" ? "▲ Bullish" : "▼ Bearish"}
      title={side === "bullish" ? "Strongest upward momentum" : "Strongest downward momentum"}
      actions={query.data && <span className="num text-[12px] text-muted">{query.data.rows.length} shown</span>}
      bodyClassName="p-2"
    >
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
      {query.isLoading && (
        <div className="grid gap-2 p-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-9" />
          ))}
        </div>
      )}
      {query.data && query.data.rows.length === 0 && <Empty>No {side} stocks match these filters on this day.</Empty>}
      {query.data && query.data.rows.length > 0 && (
        <div className={query.isFetching ? "opacity-60 transition-opacity" : "transition-opacity"}>
          <DataTable data={query.data.rows} columns={columns} onRowClick={(r) => navigate(`/stock/${r.symbol}`)} />
        </div>
      )}
    </Panel>
  );
}
