"use client";

import { useEffect, useState, useRef } from "react";
import { cn } from "@/lib/utils";

interface SignalMsg {
  signal_id: string;
  symbol: string;
  signal_type: string;
  confidence: number;
  description: string;
  timestamp: string;
}

export default function AlertTicker() {
  const [signals, setSignals] = useState<SignalMsg[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  const normalizeSignal = (raw: any): SignalMsg => ({
    signal_id: raw.id || raw.signal_id || `sig-${Date.now()}`,
    symbol: raw.symbol || "UNKNOWN",
    signal_type: raw.signal_type || "signal",
    confidence: Math.round(raw.confidence_score ?? raw.confidence ?? 0),
    description: raw.description || "Live update",
    timestamp: raw.created_at || raw.timestamp || new Date().toISOString(),
  });

  useEffect(() => {
    let reconnectTimeout: NodeJS.Timeout;
    let pollInterval: NodeJS.Timeout;

    const fetchRecentSignals = async () => {
      try {
        const apiBase =
          process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiBase}/api/signals?limit=8`);
        const data = await res.json();
        const recent = Array.isArray(data?.signals)
          ? data.signals.map(normalizeSignal)
          : [];
        if (recent.length > 0) {
          setSignals(recent);
        }
      } catch (err) {
        console.error("Failed to load recent signals", err);
      }
    };

    const connect = () => {
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

      try {
        ws.current = new WebSocket(`${wsUrl}/api/signals/live`);

        ws.current.onopen = () => {
          setIsConnected(true);
          console.log("WebSocket connected");
        };

        ws.current.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);

            if (payload?.type !== "signal" || !payload?.data) {
              return;
            }

            const raw = payload.data;
            const normalizedSignal: SignalMsg = normalizeSignal(raw);

            setSignals((prev) => {
              // Keep only last 20 signals to prevent memory issues
              const updated = [normalizedSignal, ...prev];
              return updated.slice(0, 20);
            });
          } catch (e) {
            console.error("Failed to parse signal message", e);
          }
        };

        ws.current.onclose = () => {
          setIsConnected(false);
          // Try to reconnect after 5 seconds
          reconnectTimeout = setTimeout(connect, 5000);
        };

        ws.current.onerror = (err) => {
          console.error("WebSocket error:", err);
          ws.current?.close();
        };
      } catch (err) {
        console.error("WebSocket instantiation error:", err);
      }
    };

    fetchRecentSignals();
    pollInterval = setInterval(fetchRecentSignals, 30000);
    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      clearInterval(pollInterval);
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  const getSignalColor = (confidence: number) => {
    if (confidence >= 70) return "text-green-400";
    if (confidence >= 40) return "text-amber-400";
    return "text-red-400";
  };

  return (
    <div className="h-10 bg-[#0a0a0a] border-b border-[#2a2a2a] flex items-center overflow-hidden relative">
      <div className="absolute left-0 top-0 bottom-0 w-24 bg-[#111111] z-10 flex items-center justify-center border-r border-[#2a2a2a] shadow-[4px_0_10px_rgba(0,0,0,0.5)]">
        <span className="text-xs font-bold tracking-widest text-[#888888] uppercase">
          Alerts
        </span>
        <div
          className={cn(
            "ml-2 w-2 h-2 rounded-full",
            isConnected ? "bg-green-500 pulse-live" : "bg-red-500",
          )}
          title={isConnected ? "WebSocket Connected" : "WebSocket Disconnected"}
        ></div>
      </div>

      {signals.length === 0 ? (
        <div className="pl-32 text-sm text-[#666666]">
          Waiting for real-time signals...
        </div>
      ) : (
        <div className="flex whitespace-nowrap animate-ticker pl-[100%]">
          {signals.map((signal, idx) => (
            <div
              key={`${signal.signal_id}-${idx}`}
              className="flex items-center mx-6"
            >
              <span className="font-bold text-white mr-2">{signal.symbol}</span>
              <span
                className={cn(
                  "text-xs px-1.5 py-0.5 rounded border border-[#2a2a2a] bg-[#1a1a1a] mr-2",
                  getSignalColor(signal.confidence),
                )}
              >
                {signal.confidence}%
              </span>
              <span className="text-sm text-[#aaaaaa] mr-2">
                {(signal.signal_type || "ALERT")
                  .replace(/_/g, " ")
                  .toUpperCase()}
              </span>
              <span className="text-sm text-[#e8e8e8] italic">
                — "{signal.description}"
              </span>
              <span className="mx-6 text-[#333333]">|</span>
            </div>
          ))}

          {/* Duplicate set for infinite scroll seamless looping */}
          {signals.map((signal, idx) => (
            <div
              key={`dup-${signal.signal_id}-${idx}`}
              className="flex items-center mx-6"
            >
              <span className="font-bold text-white mr-2">{signal.symbol}</span>
              <span
                className={cn(
                  "text-xs px-1.5 py-0.5 rounded border border-[#2a2a2a] bg-[#1a1a1a] mr-2",
                  getSignalColor(signal.confidence),
                )}
              >
                {signal.confidence}%
              </span>
              <span className="text-sm text-[#aaaaaa] mr-2">
                {(signal.signal_type || "ALERT")
                  .replace(/_/g, " ")
                  .toUpperCase()}
              </span>
              <span className="text-sm text-[#e8e8e8] italic">
                — "{signal.description}"
              </span>
              <span className="mx-6 text-[#333333]">|</span>
            </div>
          ))}
        </div>
      )}

      {/* Right fade gradient */}
      <div className="absolute right-0 top-0 bottom-0 w-16 bg-gradient-to-l from-[#0a0a0a] to-transparent z-10 pointer-events-none"></div>
    </div>
  );
}
