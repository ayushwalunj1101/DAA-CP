import {
  CandlestickSeries,
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

import { num } from "@/lib/format";
import { useChartColors } from "@/lib/theme";
import type { Bar, IndicatorRow } from "@/lib/types";

interface Legend {
  date: string;
  o: number;
  h: number;
  l: number;
  c: number;
  ema20: number | null;
  ema50: number | null;
  ema200: number | null;
  vwap20: number | null;
}

/** Candles with EMA 20/50/200, 20-day VWAP (dashed) and the 20-day breakout level, over a volume pane. */
export function PriceChart({ bars, indicators, height = 440 }: { bars: Bar[]; indicators: IndicatorRow[]; height?: number }) {
  const box = useRef<HTMLDivElement>(null);
  const c = useChartColors();
  const [legend, setLegend] = useState<Legend | null>(null);

  useEffect(() => {
    if (!box.current || bars.length === 0) return;
    const chart: IChartApi = createChart(box.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: c.muted,
        fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
        fontSize: 11,
        panes: { separatorColor: c.line, separatorHoverColor: c.axis },
      },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: c.axis },
      timeScale: { borderColor: c.axis, rightOffset: 4 },
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: c.bull,
      downColor: c.bear,
      wickUpColor: c.bull,
      wickDownColor: c.bear,
      borderVisible: false,
      priceLineVisible: false,
    });
    candles.setData(bars.map((b) => ({ time: b.date as Time, open: b.open, high: b.high, low: b.low, close: b.close })));

    const line = (key: keyof IndicatorRow, color: string, style: LineStyle, width: 1 | 2 = 2) => {
      const s = chart.addSeries(LineSeries, {
        color,
        lineWidth: width,
        lineStyle: style,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      s.setData(
        indicators.filter((r) => r[key] !== null).map((r) => ({ time: r.date as Time, value: r[key] as number })),
      );
    };
    line("ema20", c.series[0], LineStyle.Solid);
    line("ema50", c.series[1], LineStyle.Solid);
    line("ema200", c.series[2], LineStyle.Solid);
    line("vwap20", c.series[3], LineStyle.Dashed);
    line("high20", c.bench, LineStyle.Dotted, 1);

    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false },
      1,
    );
    const spikes = new Set(indicators.filter((r) => r.vol_spike === 1).map((r) => r.date));
    volume.setData(
      bars.map((b) => ({
        time: b.date as Time,
        value: b.volume,
        color: spikes.has(b.date) ? c.accent : b.close >= b.open ? c.bullDim : c.bearDim,
      })),
    );
    const panes = chart.panes();
    if (panes[1]) panes[1].setHeight(Math.round(height * 0.22));

    const byDate = new Map(indicators.map((r) => [r.date, r]));
    const barByDate = new Map(bars.map((b) => [b.date, b]));
    const show = (d: string) => {
      const b = barByDate.get(d);
      const r = byDate.get(d);
      if (b) setLegend({ date: d, o: b.open, h: b.high, l: b.low, c: b.close, ema20: r?.ema20 ?? null, ema50: r?.ema50 ?? null, ema200: r?.ema200 ?? null, vwap20: r?.vwap20 ?? null });
    };
    show(bars[bars.length - 1].date);
    chart.subscribeCrosshairMove((p) => show(p.time ? String(p.time) : bars[bars.length - 1].date));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [bars, indicators, c, height]);

  const items: { label: string; value: number | null; color: string; dashed?: boolean }[] = legend
    ? [
        { label: "EMA 20", value: legend.ema20, color: c.series[0] },
        { label: "EMA 50", value: legend.ema50, color: c.series[1] },
        { label: "EMA 200", value: legend.ema200, color: c.series[2] },
        { label: "VWAP 20", value: legend.vwap20, color: c.series[3], dashed: true },
      ]
    : [];

  return (
    <div className="relative">
      {legend && (
        <div className="pointer-events-none absolute top-1 left-1 z-10 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md bg-panel/85 px-2 py-1 text-[11.5px] backdrop-blur-sm">
          <span className="num text-ink-2">{legend.date}</span>
          <span className="num text-muted">
            O <span className="text-ink">{num(legend.o)}</span> H <span className="text-ink">{num(legend.h)}</span> L{" "}
            <span className="text-ink">{num(legend.l)}</span> C <span className="text-ink">{num(legend.c)}</span>
          </span>
          {items.map((i) => (
            <span key={i.label} className="inline-flex items-center gap-1.5 text-muted">
              <span
                className="inline-block h-0 w-4 border-t-2"
                style={{ borderColor: i.color, borderStyle: i.dashed ? "dashed" : "solid" }}
              />
              {i.label} <span className="num text-ink">{num(i.value)}</span>
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5 text-muted">
            <span className="inline-block h-0 w-4 border-t border-dotted" style={{ borderColor: c.bench }} />
            20-day high
          </span>
        </div>
      )}
      <div ref={box} style={{ height }} role="img" aria-label="Candlestick price chart with moving averages and volume" />
    </div>
  );
}
