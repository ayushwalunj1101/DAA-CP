import type { Cls, Quadrant } from "./types";

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** ₹12,34,567 (Indian digit grouping). */
export function rupees(v: number | null | undefined, decimals = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `₹${(decimals ? inr2 : inr).format(v)}`;
}

/** Compact Indian units: ₹12.3 L, ₹4.56 Cr. */
export function rupeesCompact(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
  if (a >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`;
  return rupees(v);
}

export function num(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function int(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Math.round(v).toLocaleString("en-IN");
}

/** +1.23% / −4.50%, with a real minus sign. */
export function pct(v: number | null | undefined, digits = 2, signed = true): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = Math.abs(v).toFixed(digits);
  if (!signed) return `${v < 0 ? "−" : ""}${s}%`;
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${s}%`;
}

export function millis(v: number): string {
  if (v < 1) return `${(v * 1000).toFixed(0)} µs`;
  if (v < 1000) return `${v.toFixed(v < 10 ? 2 : 1)} ms`;
  return `${(v / 1000).toFixed(2)} s`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-09-09" -> "9 Sep 2026" (parsed from the string, so no time-zone shift). */
export function day(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

export const CLASS_META: Record<Cls, { label: string; short: string; side: "bull" | "bear" | "neutral"; strength: 0 | 1 | 2 }> = {
  ESTABLISHED_BULLISH: { label: "Established Bullish", short: "Est. bull", side: "bull", strength: 2 },
  DEVELOPING_BULLISH: { label: "Developing Bullish", short: "Dev. bull", side: "bull", strength: 1 },
  NEUTRAL: { label: "Neutral", short: "Neutral", side: "neutral", strength: 0 },
  DEVELOPING_BEARISH: { label: "Developing Bearish", short: "Dev. bear", side: "bear", strength: 1 },
  ESTABLISHED_BEARISH: { label: "Established Bearish", short: "Est. bear", side: "bear", strength: 2 },
};

export const CLASS_ORDER: Cls[] = [
  "ESTABLISHED_BULLISH",
  "DEVELOPING_BULLISH",
  "NEUTRAL",
  "DEVELOPING_BEARISH",
  "ESTABLISHED_BEARISH",
];

export const QUADRANT_LABEL: Record<NonNullable<Quadrant>, string> = {
  ACCUMULATION: "Accumulation",
  WEAK_RALLY: "Weak rally",
  DISTRIBUTION: "Distribution",
  WEAK_SELLOFF: "Weak selloff",
};

export function sectorLabel(s: string): string {
  const map: Record<string, string> = {
    CAPGOODS: "Capital goods",
    FIN: "Financials",
    FMCG: "FMCG",
    IT: "IT",
    CHEM: "Chemicals",
    OTHER: "Other",
  };
  return map[s] ?? s.charAt(0) + s.slice(1).toLowerCase();
}

/** Geometric series of sizes from lo to hi (inclusive), rounded to friendly values. */
export function geometricSizes(lo: number, hi: number, count: number): number[] {
  if (count <= 1 || hi <= lo) return [hi];
  const out = new Set<number>();
  for (let i = 0; i < count; i++) {
    const v = lo * Math.pow(hi / lo, i / (count - 1));
    const mag = Math.pow(10, Math.max(0, Math.floor(Math.log10(v)) - 1));
    out.add(Math.max(1, Math.round(v / mag) * mag));
  }
  return [...out].sort((a, b) => a - b);
}
