"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { cn } from "@/lib/utils";
import AlertTicker from "./AlertTicker";

const fetcher = (url: string) => fetch(url).then((res) => res.json());

interface MarketStatus {
  isOpen: boolean;
  status: string;
}

function getMarketStatus(): MarketStatus {
  const now = new Date();

  // Convert to IST (UTC+5:30)
  const istDate = new Date(
    now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }),
  );
  const hours = istDate.getHours();
  const minutes = istDate.getMinutes();
  const dayOfWeek = istDate.getDay(); // 0=Sunday, 1=Monday, ..., 5=Friday, 6=Saturday

  // Market hours: 9:15 AM to 3:30 PM IST
  const marketOpenTime = 9 * 60 + 15; // 9:15 AM in minutes
  const marketCloseTime = 15 * 60 + 30; // 3:30 PM in minutes
  const currentTime = hours * 60 + minutes;

  // Check if it's a trading day (Mon-Fri)
  const isTradingDay = dayOfWeek >= 1 && dayOfWeek <= 5;

  const isOpen =
    isTradingDay &&
    currentTime >= marketOpenTime &&
    currentTime < marketCloseTime;

  if (!isTradingDay) {
    return { isOpen: false, status: "MARKET CLOSED (Weekend)" };
  }

  if (currentTime < marketOpenTime) {
    return { isOpen: false, status: "MARKET CLOSED (Pre-market)" };
  }

  if (currentTime >= marketCloseTime) {
    return { isOpen: false, status: "MARKET CLOSED (After hours)" };
  }

  return { isOpen: true, status: "MARKET OPEN" };
}

export default function Header() {
  const [time, setTime] = useState<Date | null>(null);
  const [marketStatus, setMarketStatus] = useState<MarketStatus>({
    isOpen: false,
    status: "Loading...",
  });

  const { data: marketData, error } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/market/summary`,
    fetcher,
    { refreshInterval: 15000, keepPreviousData: true },
  );

  useEffect(() => {
    setTime(new Date());
    setMarketStatus(getMarketStatus());

    const timer = setInterval(() => {
      setTime(new Date());
      setMarketStatus(getMarketStatus());
    }, 1000);

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
            <div
              className={cn(
                "w-2 h-2 rounded-full pulse-live",
                marketStatus.isOpen ? "bg-green-500" : "bg-red-500",
              )}
            ></div>
            <span className="text-sm font-medium text-white tracking-wide">
              {marketStatus.status}
            </span>
          </div>

          <div className="h-6 w-px bg-[#2a2a2a]"></div>

          <div className="flex items-center gap-3">
            <span className="text-[#888888] text-sm hidden md:inline">
              NIFTY 50
            </span>
            {marketData ? (
              <div className="flex items-center gap-2 tabular-nums">
                <span className="text-white font-semibold">
                  {marketData.nifty50.value.toLocaleString()}
                </span>
                <span
                  className={cn(
                    "text-sm font-medium",
                    isNiftyUp ? "text-green-400" : "text-red-400",
                  )}
                >
                  {isNiftyUp ? "▲ " : "▼ "}
                  {marketData.nifty50.change.toFixed(2)} (
                  {marketData.nifty50.change_pct.toFixed(2)}%)
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
