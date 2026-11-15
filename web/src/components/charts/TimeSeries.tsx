import { AreaSeries, ColorType, createChart, LineSeries, type Time } from "lightweight-charts";
import { useEffect, useRef } from "react";

import { useChartColors } from "@/lib/theme";

export interface SeriesSpec {
  name: string;
  data: { date: string; value: number }[];
  color: string;
  area?: boolean;
  width?: 1 | 2 | 3;
}

/** Line/area time series on one shared axis (never a second y-axis). */
export function TimeSeries({ series, height = 300, ariaLabel, format }: { series: SeriesSpec[]; height?: number; ariaLabel: string; format?: (v: number) => string }) {
  const box = useRef<HTMLDivElement>(null);
  const c = useChartColors();

  useEffect(() => {
    if (!box.current) return;
    const chart = createChart(box.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: c.muted,
        fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
        fontSize: 11,
      },
      grid: { vertLines: { visible: false }, horzLines: { color: c.grid } },
      rightPriceScale: { borderColor: c.axis },
      timeScale: { borderColor: c.axis },
      localization: format ? { priceFormatter: format } : undefined,
      handleScroll: { mouseWheel: false },
    });
    for (const s of series) {
      const data = s.data.map((p) => ({ time: p.date as Time, value: p.value }));
      if (s.area) {
        const a = chart.addSeries(AreaSeries, {
          lineColor: s.color,
          topColor: `${s.color}55`,
          bottomColor: `${s.color}00`,
          lineWidth: s.width ?? 2,
          priceLineVisible: false,
        });
        a.setData(data);
      } else {
        const l = chart.addSeries(LineSeries, { color: s.color, lineWidth: s.width ?? 2, priceLineVisible: false });
        l.setData(data);
      }
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [series, c, format]);

  return <div ref={box} style={{ height }} role="img" aria-label={ariaLabel} />;
}
