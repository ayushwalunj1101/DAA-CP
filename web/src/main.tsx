import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { ThemeProvider } from "@/lib/theme";
import { BacktestPage } from "@/pages/Backtest";
import { LabPage } from "@/pages/Lab";
import { NetworkPage } from "@/pages/Network";
import { OverviewPage } from "@/pages/Overview";
import { PortfolioPage } from "@/pages/Portfolio";
import { ScannerPage } from "@/pages/Scanner";
import { StockPage } from "@/pages/Stock";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1, refetchOnWindowFocus: false } },
});

const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <OverviewPage /> },
      { path: "/scanner", element: <ScannerPage /> },
      { path: "/stock", element: <Navigate to="/stock/RELIANCE" replace /> },
      { path: "/stock/:symbol", element: <StockPage /> },
      { path: "/network", element: <NetworkPage /> },
      { path: "/portfolio", element: <PortfolioPage /> },
      { path: "/backtest", element: <BacktestPage /> },
      { path: "/lab", element: <LabPage /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
