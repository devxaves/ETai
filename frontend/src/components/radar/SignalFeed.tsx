"use client";

import { useState } from "react";
import useSWR from "swr";
import SignalCard, { SignalData } from "./SignalCard";
import LoadingSpinner from "../ui/LoadingSpinner";
import ErrorBoundary from "../ui/ErrorBoundary";
import ReactMarkdown from "react-markdown";

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function SignalFeed() {
  const [selectedSignal, setSelectedSignal] = useState<SignalData | null>(null);
  const [filter, setFilter] = useState<"all" | "high" | "medium">("all");

  const { data, error, isLoading } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/signals?limit=50`,
    fetcher,
    { refreshInterval: 60000 } // Poll every minute for updates
  );

  if (error) return <ErrorBoundary fallback={<div className="p-4 text-red-500 border border-red-500/20 bg-red-500/5 rounded">Failed to load signals. Is the backend running?</div>} />;
  if (isLoading) return <LoadingSpinner className="h-64" />;

  const signals: SignalData[] = data?.signals || [];
  
  // Apply filters
  const filteredSignals = signals.filter(s => {
    if (filter === "high") return s.confidence >= 70;
    if (filter === "medium") return s.confidence >= 40;
    return true; // all
  });

  return (
    <div className="flex flex-col md:flex-row gap-6 h-[calc(100vh-140px)]">
      {/* Left side: Feed list */}
      <div className="w-full md:w-5/12 lg:w-1/3 flex flex-col h-full bg-[#111111] border border-[#2a2a2a] rounded-lg overflow-hidden">
        <div className="p-4 border-b border-[#2a2a2a] bg-[#1a1a1a] flex justify-between items-center">
          <h2 className="font-semibold text-white">Live Feed</h2>
          
          <select 
            className="bg-[#0a0a0a] border border-[#2a2a2a] text-xs text-[#e8e8e8] rounded px-2 py-1 outline-none focus:border-[#3a3a3a]"
            value={filter}
            onChange={(e) => setFilter(e.target.value as any)}
          >
            <option value="all">All Signals</option>
            <option value="high">High Confidence (&gt;70%)</option>
            <option value="medium">Actionable (&gt;40%)</option>
          </select>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {filteredSignals.length === 0 ? (
            <div className="text-center text-[#888888] mt-10 text-sm">No signals match the current filter.</div>
          ) : (
            filteredSignals.map((signal) => (
              <SignalCard 
                key={signal.id} 
                signal={signal} 
                onClick={setSelectedSignal}
                isSelected={selectedSignal?.id === signal.id}
              />
            ))
          )}
        </div>
      </div>

      {/* Right side: Detail Panel */}
      <div className="w-full md:w-7/12 lg:w-2/3 h-full border border-[#2a2a2a] bg-[#111111] rounded-lg overflow-hidden flex flex-col">
        {!selectedSignal ? (
          <div className="flex-1 flex flex-col items-center justify-center text-[#666666]">
            <svg className="w-16 h-16 mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <p className="text-lg font-medium text-[#888888]">Select a signal to view details</p>
            <p className="text-sm mt-2 max-w-sm text-center">
              The AI Engine provides a comprehensive breakdown of why this signal fired 
              and its historical precedent.
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto animate-fade-in relative scroll-smooth">
            <div className="p-6 md:p-8">
              <div className="flex items-center gap-3 mb-6">
                <span className="text-3xl font-black text-white tracking-tighter">{selectedSignal.symbol}</span>
                <span className="px-3 py-1 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-sm font-semibold tracking-wider uppercase text-[#aaaaaa]">
                  {selectedSignal.signal_type.replace('_', ' ')}
                </span>
              </div>
              
              <div className="text-xl text-[#e8e8e8] font-medium leading-snug mb-8 pl-4 border-l-4 border-green-500">
                {selectedSignal.description}
              </div>
              
              <div className="bg-[#0a0a0a] rounded-lg p-6 border border-[#2a2a2a] shadow-inner mb-8">
                <div className="flex items-center justify-between mb-4 border-b border-[#2a2a2a] pb-4">
                  <h3 className="font-semibold text-white tracking-wide uppercase text-sm">AI Analysis</h3>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#888888]">Engine:</span>
                    <span className="text-xs font-mono bg-[#1a1a1a] border border-[#2a2a2a] px-2 py-0.5 rounded text-blue-400">Claude-3.5-Sonnet</span>
                  </div>
                </div>
                
                <div className="prose prose-invert prose-green max-w-none prose-p:leading-relaxed prose-headings:font-semibold prose-a:text-green-400">
                  <ReactMarkdown>
                    {selectedSignal.explanation_markdown || "*No detailed markdown available for this signal.*"}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
