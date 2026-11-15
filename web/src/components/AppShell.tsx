import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Moon, Search, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { api } from "@/lib/api";
import { day } from "@/lib/format";
import { useTheme } from "@/lib/theme";

import { CommandPalette } from "./CommandPalette";
import { NAV } from "./nav";
import { cn } from "./ui";

export function AppShell() {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { theme, toggle } = useTheme();
  const location = useLocation();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: 5 * 60_000 });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const synced = meta.data?.last_update;

  return (
    <div className="relative z-[1] flex min-h-full">
      {/* ---------- sidebar ---------- */}
      <aside className="sticky top-0 flex h-screen w-[248px] shrink-0 flex-col border-r border-line bg-raised/70 backdrop-blur-sm max-lg:hidden">
        <div className="px-6 pt-7 pb-6">
          <div className="flex items-baseline gap-2">
            <span className="font-display text-[26px] leading-none font-[520] tracking-[-0.03em] text-ink italic">Momentum</span>
            <span className="font-display text-[26px] leading-none font-[300] tracking-[-0.03em] text-accent">Desk</span>
          </div>
          <div className="eyebrow mt-2">NSE 500 · DAA course project</div>
        </div>
        <nav className="flex flex-col gap-0.5 px-3">
          {NAV.map((n) => {
            const active = n.path === "/" ? location.pathname === "/" : location.pathname.startsWith(n.path);
            return (
              <NavLink
                key={n.path}
                to={n.path}
                className={cn(
                  "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13.5px] transition",
                  active ? "bg-panel text-ink shadow-[0_0_0_1px_var(--line)]" : "text-ink-2 hover:bg-panel/60 hover:text-ink",
                )}
              >
                {active && (
                  <motion.span layoutId="nav-mark" className="absolute top-2 bottom-2 left-0 w-[3px] rounded-full bg-accent" />
                )}
                <span className={cn("num w-5 text-[11px]", active ? "text-accent" : "text-muted")}>{n.index}</span>
                <n.icon className="size-4 opacity-80" />
                {n.label}
              </NavLink>
            );
          })}
        </nav>
        <div className="mt-auto space-y-3 px-6 pb-6 text-[12px] text-muted">
          <div className="h-px bg-line" />
          <div>
            <div className="eyebrow mb-1">Data</div>
            <div className="text-ink-2">{meta.data ? `${day(meta.data.first_date)} – ${day(meta.data.last_date)}` : "…"}</div>
            <div>Universe {meta.data ? `${meta.data.universe_size} stocks · ${meta.data.universe_month}` : "…"}</div>
          </div>
          <div className="flex items-center gap-2">
            <span className={cn("size-1.5 rounded-full", synced ? "bg-bull" : "bg-accent")} />
            {synced ? `FYERS synced ${day(synced)}` : `Local history to ${day(meta.data?.local_end)}`}
          </div>
        </div>
      </aside>

      {/* ---------- main column ---------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="sticky top-0 z-20 flex h-14 items-center justify-between gap-4 border-b border-line bg-bg/75 px-8 backdrop-blur-md max-sm:px-4">
          <div className="flex items-center gap-3 text-[12.5px] text-muted">
            <span className="eyebrow">As of</span>
            <span className="num text-ink">{meta.data ? day(meta.data.last_date) : "…"}</span>
            {meta.data && meta.data.unreviewed_flags > 0 && (
              <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] text-accent">
                {meta.data.unreviewed_flags} price jumps to review
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPaletteOpen(true)}
              className="flex h-9 items-center gap-3 rounded-lg border border-line bg-raised px-3 text-[12.5px] text-muted transition hover:border-line-strong hover:text-ink"
            >
              <Search className="size-3.5" />
              <span className="max-sm:hidden">Search stocks</span>
              <kbd className="num rounded border border-line-strong px-1.5 text-[10.5px]">Ctrl K</kbd>
            </button>
            <button
              onClick={toggle}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              className="flex size-9 items-center justify-center rounded-lg border border-line bg-raised text-muted transition hover:text-accent"
            >
              {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
          </div>
        </div>
        <main className="mx-auto w-full max-w-[1480px] flex-1 px-8 pt-9 pb-16 max-sm:px-4">
          <motion.div key={location.pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: [0.2, 0.7, 0.2, 1] }}>
            <Outlet />
          </motion.div>
        </main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}
