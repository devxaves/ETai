"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { cn } from "@/lib/utils";
import AlertTicker from "./AlertTicker";

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function Header() {
  const [time, setTime] = useState<Date | null>(null);

  const { data: marketData, error } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/market/summary`,
    fetcher,
    { refreshInterval: 60000, keepPreviousData: true }
  );

  useEffect(() => {
    setTime(new Date());
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = (date: Date | null) => {
    if (!date) return "--:--:--";
    return date.toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    });
  };

  const isNiftyUp = marketData?.nifty50?.change > 0;

  return (
    <div className="flex flex-col bg-[#0a0a0a]">
      {/* Top Bar */}
      <div className="h-14 flex items-center justify-between px-6 border-b border-[#2a2a2a] bg-[#111111]">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 pulse-live"></div>
            <span className="text-sm font-medium text-white tracking-wide">MARKET OPEN</span>
          </div>

          <div className="h-6 w-px bg-[#2a2a2a]"></div>

          <div className="flex items-center gap-3">
            <span className="text-[#888888] text-sm hidden md:inline">NIFTY 50</span>
            {marketData ? (
              <div className="flex items-center gap-2 tabular-nums">
                <span className="text-white font-semibold">{marketData.nifty50.value.toLocaleString()}</span>
                <span
                  className={cn(
                    "text-sm font-medium",
                    isNiftyUp ? "text-green-400" : "text-red-400"
                  )}
                >
                  {isNiftyUp ? "▲ " : "▼ "}
                  {marketData.nifty50.change.toFixed(2)} ({marketData.nifty50.change_pct.toFixed(2)}%)
                </span>
              </div>
            ) : (
              <div className="w-32 h-4 skeleton"></div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4 text-sm font-medium text-[#888888] tabular-nums">
          <span className="hidden sm:inline">IST</span>
          <span className="text-white w-24 text-right">{formatTime(time)}</span>
        </div>
      </div>

      {/* Alert Ticker */}
      <AlertTicker />
    </div>
  );
}
