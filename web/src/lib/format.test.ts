import { describe, expect, it } from "vitest";

import { CLASS_META, CLASS_ORDER, day, geometricSizes, int, millis, pct, rupees, rupeesCompact } from "./format";

describe("number formatting", () => {
  it("groups rupees the Indian way", () => {
    expect(rupees(1234567)).toBe("₹12,34,567");
    expect(rupees(null)).toBe("—");
    expect(int(112101)).toBe("1,12,101");
  });

  it("uses lakh and crore for compact amounts", () => {
    expect(rupeesCompact(1_000_000)).toBe("₹10.00 L");
    expect(rupeesCompact(25_000_000)).toBe("₹2.50 Cr");
    expect(rupeesCompact(9_500)).toBe("₹9,500");
  });

  it("signs percentages with a real minus sign", () => {
    expect(pct(1.234)).toBe("+1.23%");
    expect(pct(-4.5)).toBe("−4.50%");
    expect(pct(0)).toBe("0.00%");
    expect(pct(undefined)).toBe("—");
  });

  it("formats durations from microseconds to seconds", () => {
    expect(millis(0.042)).toBe("42 µs");
    expect(millis(3.154)).toBe("3.15 ms");
    expect(millis(218.9)).toBe("218.9 ms");
    expect(millis(13080)).toBe("13.08 s");
  });

  it("formats ISO dates without a time-zone shift", () => {
    expect(day("2026-09-09")).toBe("9 Sep 2026");
    expect(day("2012-01-02T00:00:00")).toBe("2 Jan 2012");
    expect(day(null)).toBe("—");
  });
});

describe("classes", () => {
  it("orders the five classes from strongest bullish to strongest bearish", () => {
    expect(CLASS_ORDER.map((c) => CLASS_META[c].side)).toEqual(["bull", "bull", "neutral", "bear", "bear"]);
    expect(CLASS_ORDER.map((c) => CLASS_META[c].strength)).toEqual([2, 1, 0, 1, 2]);
  });
});

describe("geometricSizes", () => {
  it("spans the range in increasing, de-duplicated steps", () => {
    const s = geometricSizes(500, 20_000, 7);
    expect(s[0]).toBe(500);
    expect(s[s.length - 1]).toBe(20_000);
    expect([...s].sort((a, b) => a - b)).toEqual(s);
    expect(new Set(s).size).toBe(s.length);
  });

  it("returns the single top size when the range is empty", () => {
    expect(geometricSizes(100, 100, 5)).toEqual([100]);
  });
});
