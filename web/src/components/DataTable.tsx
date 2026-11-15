import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

import { cn } from "./ui";

/** Sortable (optionally paginated) table with tabular figures and sticky header. */
export function DataTable<T>({
  data,
  columns,
  pageSize,
  onRowClick,
  initialSort,
  dense = false,
}: {
  data: T[];
  columns: ColumnDef<T, unknown>[];
  pageSize?: number;
  onRowClick?: (row: T) => void;
  initialSort?: SortingState;
  dense?: boolean;
}) {
  const [sorting, setSorting] = useState<SortingState>(initialSort ?? []);
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    ...(pageSize ? { getPaginationRowModel: getPaginationRowModel(), initialState: { pagination: { pageSize } } } : {}),
  });

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-line">
                {hg.headers.map((h) => {
                  const sorted = h.column.getIsSorted();
                  const align = (h.column.columnDef.meta as { align?: string } | undefined)?.align;
                  return (
                    <th
                      key={h.id}
                      className={cn(
                        "eyebrow sticky top-0 bg-panel px-3 py-2.5 font-normal whitespace-nowrap",
                        align === "right" ? "text-right" : "text-left",
                        h.column.getCanSort() && "cursor-pointer select-none hover:text-ink",
                      )}
                      onClick={h.column.getToggleSortingHandler()}
                    >
                      <span className="inline-flex items-center gap-1">
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {sorted === "asc" && <ArrowUp className="size-3" />}
                        {sorted === "desc" && <ArrowDown className="size-3" />}
                      </span>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                className={cn(
                  "border-b border-line/70 transition-colors last:border-b-0",
                  onRowClick && "cursor-pointer hover:bg-panel-2",
                )}
              >
                {row.getVisibleCells().map((cell) => {
                  const align = (cell.column.columnDef.meta as { align?: string } | undefined)?.align;
                  return (
                    <td key={cell.id} className={cn("px-3 whitespace-nowrap", dense ? "py-1.5" : "py-2.5", align === "right" && "text-right")}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pageSize && table.getPageCount() > 1 && (
        <div className="mt-3 flex items-center justify-end gap-3 text-[12px] text-muted">
          <span className="num">
            {table.getState().pagination.pageIndex + 1} / {table.getPageCount()}
          </span>
          <button
            aria-label="Previous page"
            className="rounded-md border border-line p-1 hover:text-ink disabled:opacity-40"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            <ChevronLeft className="size-4" />
          </button>
          <button
            aria-label="Next page"
            className="rounded-md border border-line p-1 hover:text-ink disabled:opacity-40"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      )}
    </div>
  );
}
