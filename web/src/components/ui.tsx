import * as SliderPrimitive from "@radix-ui/react-slider";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import { clsx } from "clsx";
import { AlertTriangle, Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { twMerge } from "tailwind-merge";

import { CLASS_META } from "@/lib/format";
import type { Cls } from "@/lib/types";

export function cn(...args: Parameters<typeof clsx>) {
  return twMerge(clsx(...args));
}

// ---------------------------------------------------------------- layout
export function PageHeader({ index, title, lede, actions }: { index: string; title: string; lede: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-7 flex flex-wrap items-end justify-between gap-6">
      <div className="max-w-3xl">
        <div className="eyebrow mb-2 flex items-center gap-3">
          <span className="text-accent">{index}</span>
          <span className="h-px w-10 bg-line-strong" />
        </div>
        <h1 className="font-display text-[42px] leading-[1.02] font-[420] tracking-[-0.02em] text-ink">{title}</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-ink-2">{lede}</p>
      </div>
      {actions && <div className="flex flex-wrap items-end gap-3">{actions}</div>}
    </header>
  );
}

export function Panel({
  title,
  eyebrow,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cn("panel relative overflow-hidden", className)}>
      {(title || eyebrow || actions) && (
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 pt-4 pb-3">
          <div>
            {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
            {title && <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={cn("p-5", bodyClassName)}>{children}</div>
    </section>
  );
}

/** A hero figure: the number is the point, the label explains it. */
export function Stat({
  label,
  value,
  note,
  tone = "ink",
  icon,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  tone?: "ink" | "bull" | "bear" | "accent";
  icon?: ReactNode;
}) {
  const color = { ink: "text-ink", bull: "text-bull", bear: "text-bear", accent: "text-accent" }[tone];
  return (
    <div className="panel px-5 py-4">
      <div className="eyebrow flex items-center gap-2">
        {icon}
        {label}
      </div>
      <div className={cn("mt-2 font-display text-[40px] leading-none font-[380] tracking-[-0.03em] tabular-nums", color)}>
        {value}
      </div>
      {note && <div className="mt-2 text-[12.5px] text-muted">{note}</div>}
    </div>
  );
}

// ---------------------------------------------------------------- semantic markers
export function ClassBadge({ cls, compact = false }: { cls: Cls | null | undefined; compact?: boolean }) {
  if (!cls) return <span className="text-muted">—</span>;
  const m = CLASS_META[cls];
  const tone =
    m.side === "bull"
      ? m.strength === 2
        ? "bg-bull text-white"
        : "bg-bull-soft text-bull ring-1 ring-inset ring-bull/40"
      : m.side === "bear"
        ? m.strength === 2
          ? "bg-bear text-white"
          : "bg-bear-soft text-bear ring-1 ring-inset ring-bear/40"
        : "bg-panel-2 text-ink-2 ring-1 ring-inset ring-line-strong";
  const glyph = m.side === "bull" ? "▲" : m.side === "bear" ? "▼" : "●";
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[11.5px] font-medium whitespace-nowrap", tone)}
      title={m.label}
    >
      <span aria-hidden className="text-[9px]">
        {glyph}
      </span>
      {compact ? m.short : m.label}
    </span>
  );
}

/** Signed change with direction glyph; colour is never the only cue. */
export function Delta({ value, suffix = "%", digits = 2, className }: { value: number | null | undefined; suffix?: string; digits?: number; className?: string }) {
  if (value === null || value === undefined || Number.isNaN(value)) return <span className="num text-muted">—</span>;
  const up = value > 0;
  const down = value < 0;
  return (
    <span className={cn("num inline-flex items-center gap-1", up ? "text-bull" : down ? "text-bear" : "text-muted", className)}>
      <span aria-hidden className="text-[9px]">
        {up ? "▲" : down ? "▼" : "■"}
      </span>
      {up ? "+" : down ? "−" : ""}
      {Math.abs(value).toFixed(digits)}
      {suffix}
    </span>
  );
}

export function RankChange({ value }: { value: number | null }) {
  if (value === null) return <span className="eyebrow !tracking-[0.08em] text-accent">new</span>;
  if (value === 0) return <span className="num text-muted">—</span>;
  return <Delta value={value} suffix="" digits={0} />;
}

// ---------------------------------------------------------------- controls
export function Button({
  children,
  variant = "primary",
  loading,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "outline"; loading?: boolean }) {
  const styles = {
    primary: "bg-accent text-accent-ink hover:brightness-110 shadow-[0_8px_24px_-12px_var(--accent)]",
    ghost: "text-ink-2 hover:bg-panel-2 hover:text-ink",
    outline: "border border-line-strong text-ink hover:border-accent hover:text-accent",
  }[variant];
  return (
    <button
      className={cn(
        "inline-flex h-9 items-center justify-center gap-2 rounded-lg px-4 text-[13px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50",
        styles,
        className,
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (v: T) => void;
  label?: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-line bg-raised p-[3px]">
      {options.map((o) => (
        <button
          key={String(o.value)}
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-md px-3 py-1.5 text-[12.5px] font-medium transition",
            o.value === value ? "bg-panel-2 text-ink shadow-[0_0_0_1px_var(--line-strong)]" : "text-muted hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="eyebrow">{label}</span>
      {children}
      {hint && <span className="text-[11.5px] text-muted">{hint}</span>}
    </label>
  );
}

export function TextInput({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "num h-9 rounded-lg border border-line bg-raised px-3 text-[13px] text-ink transition outline-none placeholder:text-muted hover:border-line-strong focus:border-accent",
        className,
      )}
      {...props}
    />
  );
}

export function Select({ className, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-9 rounded-lg border border-line bg-raised px-3 text-[13px] text-ink outline-none hover:border-line-strong focus:border-accent",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function Slider({
  value,
  min,
  max,
  step,
  onChange,
  label,
}: {
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  label: string;
}) {
  return (
    <SliderPrimitive.Root
      className="relative flex h-5 w-full touch-none items-center select-none"
      value={[value]}
      min={min}
      max={max}
      step={step}
      onValueChange={([v]) => onChange(v)}
      aria-label={label}
    >
      <SliderPrimitive.Track className="relative h-[3px] grow rounded-full bg-line-strong">
        <SliderPrimitive.Range className="absolute h-full rounded-full bg-accent" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb className="block size-4 rounded-full border-2 border-accent bg-panel shadow transition hover:scale-110" />
    </SliderPrimitive.Root>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2.5 text-[13px] text-ink-2">
      <SwitchPrimitive.Root
        checked={checked}
        onCheckedChange={onChange}
        className="relative h-5 w-9 rounded-full bg-line-strong transition data-[state=checked]:bg-accent"
      >
        <SwitchPrimitive.Thumb className="block size-4 translate-x-0.5 rounded-full bg-panel shadow transition data-[state=checked]:translate-x-[18px]" />
      </SwitchPrimitive.Root>
      {label}
    </label>
  );
}

// ---------------------------------------------------------------- states
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-panel-2", className)} />;
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="flex flex-col items-start gap-3 rounded-xl border border-bear/40 bg-bear-soft p-5 text-[13px]">
      <div className="flex items-center gap-2 font-semibold text-bear">
        <AlertTriangle className="size-4" /> Could not load this view
      </div>
      <div className="text-ink-2">{message}</div>
      <div className="text-muted">Is the API running? Start it with: python -m uvicorn api.main:app --port 8010</div>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-line-strong p-8 text-center text-[13px] text-muted">{children}</div>;
}

/** Thin horizontal bar for a 0-100 value inside tables. */
export function ScoreBar({ value, tone = "accent" }: { value: number; tone?: "accent" | "bull" | "bear" }) {
  const color = { accent: "bg-accent", bull: "bg-bull", bear: "bg-bear" }[tone];
  return (
    <div className="flex items-center gap-2.5">
      <span className="num w-10 text-right text-ink">{value.toFixed(1)}</span>
      <div className="h-[5px] w-20 overflow-hidden rounded-full bg-panel-2">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}
