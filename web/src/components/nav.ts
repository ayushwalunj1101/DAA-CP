import { Activity, CandlestickChart, FlaskConical, Gauge, Network, Radar, Wallet } from "lucide-react";

export const NAV = [
  { index: "01", path: "/", label: "Market Overview", icon: Gauge },
  { index: "02", path: "/scanner", label: "Momentum Scanner", icon: Radar },
  { index: "03", path: "/stock", label: "Stock Analysis", icon: CandlestickChart },
  { index: "04", path: "/network", label: "Correlation Network", icon: Network },
  { index: "05", path: "/portfolio", label: "Portfolio Builder", icon: Wallet },
  { index: "06", path: "/backtest", label: "Backtest", icon: Activity },
  { index: "07", path: "/lab", label: "Algorithm Lab", icon: FlaskConical },
] as const;
