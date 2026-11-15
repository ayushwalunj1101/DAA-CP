import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

type Theme = "dark" | "light";

interface ThemeState {
  theme: Theme;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeState>({ theme: "dark", toggle: () => {} });

function initialTheme(): Theme {
  const attr = document.documentElement.dataset.theme;
  return attr === "light" ? "light" : "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  useEffect(() => {
    try {
      localStorage.setItem("theme", theme);
    } catch {
      /* private mode or blocked storage: the theme still applies for this visit */
    }
  }, [theme]);
  const toggle = useCallback(() => {
    const next: Theme = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    // Switch the attribute before re-rendering so charts read the new theme's colours.
    document.documentElement.dataset.theme = next;
    setTheme(next);
  }, []);
  const value = useMemo(() => ({ theme, toggle }), [theme, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);

export interface ChartColors {
  panel: string;
  ink: string;
  ink2: string;
  muted: string;
  grid: string;
  axis: string;
  line: string;
  accent: string;
  bull: string;
  bullDim: string;
  bear: string;
  bearDim: string;
  neutral: string;
  bench: string;
  series: [string, string, string, string];
}

function read(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Chart colours resolved from the CSS tokens of the active theme. */
export function useChartColors(): ChartColors {
  const { theme } = useTheme();
  return useMemo(
    () => ({
      panel: read("--panel"),
      ink: read("--ink"),
      ink2: read("--ink-2"),
      muted: read("--muted"),
      grid: read("--grid"),
      axis: read("--axis"),
      line: read("--line"),
      accent: read("--accent"),
      bull: read("--bull"),
      bullDim: read("--bull-dim"),
      bear: read("--bear"),
      bearDim: read("--bear-dim"),
      neutral: read("--neutral"),
      bench: read("--bench"),
      series: [read("--s1"), read("--s2"), read("--s3"), read("--s4")],
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [theme],
  );
}
