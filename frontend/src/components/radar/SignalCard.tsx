"use client";

import { cn } from "@/lib/utils";
import ConfidenceBadge from "./ConfidenceBadge";
import { formatDistanceToNow } from "date-fns";

export interface SignalData {
  id: string;
  symbol: string;
  signal_type: string;
  confidence_score: number;
  description: string;
  explanation?: string;
  created_at: string;
}

interface Props {
  signal: SignalData;
  onClick: (signal: SignalData) => void;
  className?: string;
  isSelected?: boolean;
}

export default function SignalCard({
  signal,
  onClick,
  className,
  isSelected,
}: Props) {
  const timeStr = formatDistanceToNow(new Date(signal.created_at), {
    addSuffix: true,
  });

  const typeDisplay = signal.signal_type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

  return (
    <div
      className={cn(
        "border p-4 rounded-lg bg-[#1a1a1a] transition-all cursor-pointer group hover:-translate-y-1 hover:shadow-lg",
        isSelected
          ? "border-green-500/50 shadow-[0_0_15px_rgba(38,166,154,0.15)] bg-[#1e2321]"
          : "border-[#2a2a2a] hover:border-[#3a3a3a]",
        className,
      )}
      onClick={() => onClick(signal)}
    >
      <div className="flex justify-between items-start mb-3">
        <div className="flex flex-col">
          <span className="text-lg font-bold text-white tracking-tight">
            {signal.symbol}
          </span>
          <span className="text-[#888888] text-xs uppercase tracking-wider">
            {typeDisplay}
          </span>
        </div>
        <ConfidenceBadge score={signal.confidence_score} />
      </div>

      <p className="text-sm text-[#e8e8e8] line-clamp-2 mb-4 h-10 leading-relaxed">
        {signal.description}
      </p>

      <div className="flex justify-between items-center pt-3 border-t border-[#2a2a2a]">
        <span className="text-xs text-[#666666] tabular-nums">{timeStr}</span>
        <button className="text-xs font-medium text-green-400 group-hover:text-green-300 transition-colors uppercase tracking-wider flex items-center gap-1">
          View Details
          <svg
            className="w-3 h-3 group-hover:translate-x-1 transition-transform"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5l7 7-7 7"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
