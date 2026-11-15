import * as echarts from "echarts";
import { useEffect, useRef } from "react";

import { cn } from "@/components/ui";

type Handlers = Record<string, (params: unknown) => void>;

/** Thin React wrapper around an ECharts instance: resizes with its box, replaces options on change. */
export function EChart({
  option,
  height = 320,
  onEvents,
  className,
  ariaLabel,
}: {
  option: echarts.EChartsOption;
  height?: number | string;
  onEvents?: Handlers;
  className?: string;
  ariaLabel: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!box.current) return;
    const instance = echarts.init(box.current, undefined, { renderer: "canvas" });
    chart.current = instance;
    const ro = new ResizeObserver(() => instance.resize());
    ro.observe(box.current);
    return () => {
      ro.disconnect();
      instance.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, { notMerge: true, lazyUpdate: true });
  }, [option]);

  useEffect(() => {
    const instance = chart.current;
    if (!instance || !onEvents) return;
    for (const [name, fn] of Object.entries(onEvents)) instance.on(name, fn);
    return () => {
      if (instance.isDisposed()) return;
      for (const [name, fn] of Object.entries(onEvents)) instance.off(name, fn);
    };
  }, [onEvents]);

  return <div ref={box} role="img" aria-label={ariaLabel} className={cn("w-full", className)} style={{ height }} />;
}

/** Shared axis / tooltip styling so every ECharts chart matches the theme. */
export function baseChrome(c: { ink2: string; muted: string; grid: string; axis: string; panel: string; line: string }) {
  const mono = '"IBM Plex Mono", ui-monospace, monospace';
  return {
    textStyle: { fontFamily: '"Schibsted Grotesk Variable", system-ui, sans-serif', color: c.ink2 },
    axisLabel: { color: c.muted, fontFamily: mono, fontSize: 10.5 },
    axisLine: { lineStyle: { color: c.axis } },
    splitLine: { lineStyle: { color: c.grid } },
    tooltip: {
      backgroundColor: c.panel,
      borderColor: c.line,
      borderWidth: 1,
      textStyle: { color: c.ink2, fontFamily: mono, fontSize: 12 },
      extraCssText: "border-radius:10px;box-shadow:0 12px 30px -12px rgba(0,0,0,.5);",
    },
  };
}
