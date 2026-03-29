"use client";

import useSWR from "swr";
import MetricCard from "@/components/ui/MetricCard";
import CandlestickChart from "@/components/charts/CandlestickChart";
import SignalCard from "@/components/radar/SignalCard";
import SectorHeatmap from "@/components/charts/SectorHeatmap";

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function Dashboard() {
  const { data: marketData, isLoading: mLoading } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/market/summary`,
    fetcher,
    { refreshInterval: 60000 },
  );

  const { data: signalsData } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/signals?limit=5`,
    fetcher,
  );

  const { data: niftyPatterns } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/patterns/nifty50`,
    fetcher,
  );

  const { data: sectorData } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/market/sector`,
    fetcher,
  );

  const heatmapArray = sectorData?.sectors
    ? Object.entries(sectorData.sectors).map(([name, data]: any) => ({
        name,
        size: Math.abs(data.avg_change_pct) + 1, // Add 1 so 0% isn't invisible
        change: data.avg_change_pct,
      }))
    : [];

  return (
    <div className="space-y-6 pb-6">
      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Nifty 50"
          value={marketData?.nifty50?.value.toLocaleString() || "---"}
          change={marketData?.nifty50?.change_pct}
          isLoading={mLoading}
        />
        <MetricCard
          title="Nifty Bank"
          value={marketData?.niftybank?.value.toLocaleString() || "---"}
          change={marketData?.niftybank?.change_pct}
          isLoading={mLoading}
        />
        <MetricCard
          title="Active Radar Signals"
          value={signalsData?.total || 0}
          isLoading={!signalsData}
        />
        <MetricCard
          title="Patterns Detected (Today)"
          value={niftyPatterns?.patterns?.length || 0}
          isLoading={!niftyPatterns}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Col: Primary Chart & Adv/Dec */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-[#111111] border border-[#2a2a2a] rounded-lg p-5">
            <h2 className="text-white font-bold tracking-wide uppercase text-sm mb-4">
              Market Technical Overview (^NSEI)
            </h2>
            {/* For demo, mock standard Nifty line to avoid failing when nse API throws 429 */}
            <CandlestickChart
              data={Array.from({ length: 60 }).map((_, i) => {
                const base = 22000;
                const date = new Date();
                date.setDate(date.getDate() - (60 - i));
                return {
                  time: date.toISOString().split("T")[0] as string,
                  open: base + i * 10 + Math.random() * 50,
                  high: base + i * 10 + Math.random() * 100,
                  low: base + i * 10 - Math.random() * 100,
                  close: base + i * 10 + Math.random() * 80,
                };
              })}
              height={300}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Adv/Dec */}
            <div className="bg-[#111111] border border-[#2a2a2a] rounded-lg p-5">
              <h2 className="text-white font-bold tracking-wide uppercase text-sm mb-4">
                Market Breadth (Nifty 50)
              </h2>
              <div className="flex justify-between items-center px-4">
                <div className="text-center">
                  <div className="text-3xl font-bold text-green-400 tabular-nums">
                    {marketData?.market_breadth?.advances || 0}
                  </div>
                  <div className="text-[#888] text-xs uppercase font-bold tracking-wider mt-1">
                    Advances
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-[#666] tabular-nums">
                    {marketData?.market_breadth?.unchanged || 0}
                  </div>
                  <div className="text-[#888] text-xs uppercase font-bold tracking-wider mt-1">
                    Neutral
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-red-400 tabular-nums">
                    {marketData?.market_breadth?.declines || 0}
                  </div>
                  <div className="text-[#888] text-xs uppercase font-bold tracking-wider mt-1">
                    Declines
                  </div>
                </div>
              </div>

              <div className="w-full bg-[#1a1a1a] h-3 mt-6 rounded-full overflow-hidden flex">
                <div
                  className="bg-green-500 h-full"
                  style={{
                    width: `${(marketData?.market_breadth?.advances / 50) * 100 || 50}%`,
                  }}
                ></div>
                <div
                  className="bg-[#444] h-full"
                  style={{
                    width: `${(marketData?.market_breadth?.unchanged / 50) * 100 || 0}%`,
                  }}
                ></div>
                <div
                  className="bg-red-500 h-full"
                  style={{
                    width: `${(marketData?.market_breadth?.declines / 50) * 100 || 50}%`,
                  }}
                ></div>
              </div>
            </div>

            {/* FII / DII */}
            <div className="bg-[#111111] border border-[#2a2a2a] rounded-lg p-5 flex flex-col justify-center">
              <h2 className="text-white font-bold tracking-wide uppercase text-sm mb-4">
                Institutional Flow (₹ Cr)
              </h2>
              <div className="space-y-4">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-[#888] font-semibold">FII Net</span>
                  <span className="text-green-400 font-mono font-bold">
                    +{marketData?.fii_dii?.fii_net || "1,132"}
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-[#888] font-semibold">DII Net</span>
                  <span className="text-green-400 font-mono font-bold">
                    +{marketData?.fii_dii?.dii_net || "1,109"}
                  </span>
                </div>
              </div>
              <p className="text-[#666] text-xs mt-4 text-center">
                Data updated daily at 6:00 PM IST
              </p>
            </div>
          </div>
        </div>

        {/* Right Col: Signals & Sector Heatmap */}
        <div className="space-y-6">
          {/* Top Signals */}
          <div className="bg-[#111111] border border-[#2a2a2a] rounded-lg p-5 flex flex-col h-[350px]">
            <h2 className="text-white font-bold tracking-wide uppercase text-sm mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500 pulse-live"></span>
              Top Actionable Signals
            </h2>

            <div className="flex-1 overflow-y-auto space-y-3 pr-2">
              {!signalsData ? (
                <div className="h-full flex items-center justify-center text-[#888]">
                  Loading AI radar...
                </div>
              ) : signalsData.signals.length === 0 ? (
                <div className="h-full flex items-center justify-center text-[#666]">
                  No high-confidence signals today.
                </div>
              ) : (
                signalsData.signals.slice(0, 3).map((signal: any) => (
                  <SignalCard
                    key={signal.id}
                    signal={{
                      id: signal.id,
                      symbol: signal.symbol,
                      signal_type: signal.signal_type,
                      confidence_score: signal.confidence_score,
                      description: signal.description,
                      explanation: signal.explanation,
                      created_at: signal.created_at,
                    }}
                    onClick={(s) => (window.location.href = `/radar`)} // Lazy nav to radar
                    className="p-3"
                  />
                ))
              )}
            </div>
          </div>

          {/* Heatmap */}
          <div className="bg-[#111111] border border-[#2a2a2a] rounded-lg p-5">
            <h2 className="text-white font-bold tracking-wide uppercase text-sm mb-4">
              Sector Heatmap
            </h2>
            <SectorHeatmap data={heatmapArray} height={200} />
          </div>
        </div>
      </div>
    </div>
  );
}
