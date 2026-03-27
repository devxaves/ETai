"use client";

import { useState } from "react";
import useSWR from "swr";
import CandlestickChart from "@/components/charts/CandlestickChart";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function ChartsPage() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [searchInput, setSearchInput] = useState("RELIANCE");

  // Fetch chart and pattern data from API
  const { data, error, isLoading } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/patterns/${symbol}?days=90`,
    fetcher
  );

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) {
      setSymbol(searchInput.trim().toUpperCase());
    }
  };

  // Process data for charting
  let chartData = [];
  let volumeData = [];
  let patternMarkers = [];

  if (data?.chart_data) {
    chartData = data.chart_data.map((d: any) => ({
      time: d.date,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    
    volumeData = data.chart_data.map((d: any) => ({
      time: d.date,
      value: d.volume,
      color: d.close >= d.open ? "rgba(38, 166, 154, 0.5)" : "rgba(239, 83, 80, 0.5)",
    }));

    if (data.patterns) {
      patternMarkers = data.patterns.map((p: any) => {
        const isBullish = p.name.toLowerCase().includes("bullish") || p.name.toLowerCase().includes("morning");
        return {
          time: p.date,
          position: isBullish ? "belowBar" : "aboveBar",
          color: isBullish ? "#26a69a" : "#ef5350",
          shape: isBullish ? "arrowUp" : "arrowDown",
          text: p.name,
        };
      });
    }
  }

  return (
    <div className="h-full flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight uppercase">Chart Intelligence</h1>
          <p className="text-[#888888] text-sm mt-1">
            Over 60 candlestick patterns automatically detected and backtested against historical data.
          </p>
        </div>
        
        <form onSubmit={handleSearch} className="flex relative">
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="bg-[#111111] border border-[#2a2a2a] text-white px-4 py-2 rounded-l-md w-64 uppercase outline-none focus:border-green-500 transition-colors"
            placeholder="Search symbol (e.g. TCS)"
          />
          <button 
            type="submit"
            className="bg-green-600 hover:bg-green-500 px-4 py-2 rounded-r-md text-white font-bold transition-colors"
          >
            SCAN
          </button>
        </form>
      </div>

      <div className="flex-1 flex gap-6">
        {/* Main Chart Area */}
        <div className="w-2/3 h-full flex flex-col">
          <div className="bg-[#111111] border border-[#2a2a2a] p-4 rounded-lg flex-1">
            <h2 className="text-white font-bold mb-4">{symbol} — Daily Timeframe</h2>
            
            {isLoading ? (
              <LoadingSpinner />
            ) : error || !data || !data.chart_data ? (
              <div className="flex h-full items-center justify-center text-red-400">
                Failed to load chart data for {symbol}
              </div>
            ) : (
              <CandlestickChart 
                data={chartData} 
                volumeData={volumeData} 
                patterns={patternMarkers} 
                height={550}
              />
            )}
          </div>
        </div>

        {/* Right Info Panel */}
        <div className="w-1/3 flex flex-col gap-6 h-full p-2 overflow-y-auto">
          {data?.patterns && data.patterns.length > 0 ? (
            data.patterns.map((pattern: any, idx: number) => {
              const isBullish = pattern.name.toLowerCase().includes("bullish");
              return (
              <div key={idx} className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-5">
                <div className="flex justify-between items-start mb-3">
                  <span className="text-[#888888] text-xs uppercase tracking-widest">{pattern.date}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${isBullish ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                    {isBullish ? 'BULLISH' : 'BEARISH'}
                  </span>
                </div>
                
                <h3 className="text-xl font-bold text-white tracking-tight leading-tight mb-2">
                  {pattern.name}
                </h3>
                
                {pattern.score && (
                  <div className="flex justify-between items-center mb-4 p-3 bg-[#111111] border border-[#2a2a2a] rounded">
                    <div>
                      <p className="text-[#888888] text-xs uppercase tracking-wider mb-1">AI Confidence</p>
                      <p className="text-2xl font-bold text-white tabular-nums">{pattern.score}%</p>
                    </div>
                  </div>
                )}
                
                <p className="text-sm text-[#cccccc] leading-relaxed mb-4">
                  {pattern.explanation || "This pattern indicates a potential reversal in the current trend based on the latest 3 trading sessions."}
                </p>
              </div>
            )})
          ) : (
            <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-6 text-center text-[#888888]">
              No significant candlestick patterns detected in the recent timeframe.
            </div>
          )}

          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-6">
            <h4 className="text-white font-bold uppercase tracking-wide text-sm mb-4">Oscillators</h4>
            
            <div className="space-y-4">
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-[#888888] text-sm">RSI (14)</span>
                  <span className="text-white font-mono text-sm">54.2</span>
                </div>
                <div className="w-full bg-[#111111] rounded-full h-1.5">
                  <div className="bg-amber-400 h-1.5 rounded-full" style={{ width: "54.2%" }}></div>
                </div>
              </div>
              
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-[#888888] text-sm">MACD</span>
                  <span className="text-green-400 font-mono text-sm">+2.45</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
