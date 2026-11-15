import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import { CornerDownLeft, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/lib/api";
import { sectorLabel } from "@/lib/format";

import { NAV } from "./nav";

/** Ctrl+K: jump to any stock (prefix search done by binary search on the server) or any screen. */
export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 90);
    return () => clearTimeout(t);
  }, [q]);

  const { data, isFetching } = useQuery({
    queryKey: ["symbols", debounced],
    queryFn: () => api.symbols(debounced),
    enabled: open && debounced.length > 0,
    staleTime: 60_000,
  });

  const go = (path: string) => {
    onOpenChange(false);
    setQ("");
    navigate(path);
  };

  const screens = NAV.filter((n) => n.label.toLowerCase().includes(q.toLowerCase()));

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px]" />
        <Dialog.Content
          aria-describedby={undefined}
          className="panel fixed top-[14vh] left-1/2 z-50 w-[min(620px,92vw)] -translate-x-1/2 overflow-hidden !rounded-2xl"
        >
          <Dialog.Title className="sr-only">Search stocks and screens</Dialog.Title>
          <Command shouldFilter={false} loop>
            <div className="flex items-center gap-3 border-b border-line px-4">
              <Search className="size-4 text-muted" />
              <Command.Input
                autoFocus
                value={q}
                onValueChange={setQ}
                placeholder="Type a symbol (REL…) or a screen"
                className="num h-13 w-full bg-transparent text-[15px] text-ink outline-none placeholder:text-muted"
              />
              {isFetching && <span className="eyebrow">searching</span>}
            </div>
            <Command.List className="max-h-[52vh] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-6 text-center text-[13px] text-muted">
                {debounced ? `No stock in the universe starts with “${debounced.toUpperCase()}”.` : "Start typing a symbol."}
              </Command.Empty>
              {data && data.symbols.length > 0 && (
                <Command.Group heading="Stocks" className="[&_[cmdk-group-heading]]:eyebrow [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2">
                  {data.symbols.slice(0, 40).map((s) => (
                    <Command.Item
                      key={s.symbol}
                      value={`stock-${s.symbol}`}
                      onSelect={() => go(`/stock/${s.symbol}`)}
                      className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-[13.5px] data-[selected=true]:bg-accent-soft"
                    >
                      <span className="num font-medium text-ink">{s.symbol}</span>
                      <span className="text-[12px] text-muted">{sectorLabel(s.sector)}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}
              {screens.length > 0 && (
                <Command.Group heading="Screens" className="[&_[cmdk-group-heading]]:eyebrow [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2">
                  {screens.map((n) => (
                    <Command.Item
                      key={n.path}
                      value={`screen-${n.path}`}
                      onSelect={() => go(n.path)}
                      className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] text-ink-2 data-[selected=true]:bg-accent-soft data-[selected=true]:text-ink"
                    >
                      <span className="num w-6 text-muted">{n.index}</span>
                      <n.icon className="size-4" />
                      {n.label}
                    </Command.Item>
                  ))}
                </Command.Group>
              )}
            </Command.List>
            <div className="flex items-center justify-between border-t border-line px-4 py-2 text-[11.5px] text-muted">
              <span>Prefix search runs a binary search over the sorted symbol list.</span>
              <span className="inline-flex items-center gap-1">
                <CornerDownLeft className="size-3" /> open
              </span>
            </div>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
