"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CandlestickData,
  Time,
  CandlestickSeries,
  HistogramSeries,
  createSeriesMarkers,
} from "lightweight-charts";

interface PatternMarker {
  time: Time;
  position: "aboveBar" | "belowBar";
  color: string;
  shape: "arrowDown" | "arrowUp" | "circle";
  text: string;
}

interface Props {
  data: CandlestickData[];
  volumeData?: { time: Time; value: number; color: string }[];
  patterns?: PatternMarker[];
  height?: number;
}

export default function CandlestickChart({
  data,
  volumeData,
  patterns,
  height = 400,
}: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [chartReady, setChartReady] = useState(false);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Guard: Don't render if no data or data is invalid
    if (!data || data.length === 0) {
      console.warn("CandlestickChart: No data provided");
      return;
    }

    try {
      const chart = createChart(chartContainerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: "#0a0a0a" },
          textColor: "#888888",
        },
        grid: {
          vertLines: { color: "#2a2a2a" },
          horzLines: { color: "#2a2a2a" },
        },
        width: chartContainerRef.current.clientWidth,
        height: height,
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
          borderColor: "#2a2a2a",
        },
        rightPriceScale: {
          borderColor: "#2a2a2a",
        },
        crosshair: {
          mode: 0,
          vertLine: { width: 1, color: "#444", style: 3 },
          horzLine: { width: 1, color: "#444", style: 3 },
        },
      });

      const mainSeries = chart.addSeries(CandlestickSeries, {
        upColor: "#26a69a",
        downColor: "#ef5350",
        borderVisible: false,
        wickUpColor: "#26a69a",
        wickDownColor: "#ef5350",
      });

      if (mainSeries && data.length > 0) {
        mainSeries.setData(data);
      }

      if (patterns && patterns.length > 0 && mainSeries) {
        createSeriesMarkers(mainSeries, patterns as any);
      }

      if (volumeData && volumeData.length > 0) {
        const volumeSeries = chart.addSeries(HistogramSeries, {
          color: "#26a69a",
          priceFormat: { type: "volume" },
          priceScaleId: "",
        });
        volumeSeries.priceScale().applyOptions({
          scaleMargins: { top: 0.8, bottom: 0 },
        });
        volumeSeries.setData(volumeData);
      }

      chart.timeScale().fitContent();
      setChartReady(true);

      const handleResize = () => {
        chart.applyOptions({
          width: chartContainerRef.current?.clientWidth || 0,
        });
      };

      window.addEventListener("resize", handleResize);

      return () => {
        window.removeEventListener("resize", handleResize);
        chart.remove();
      };
    } catch (error) {
      console.error("CandlestickChart error:", error);
      setChartReady(true);
    }
  }, [data, volumeData, patterns, height]);

  return (
    <div className="w-full relative border border-[#2a2a2a] rounded overflow-hidden">
      {!chartReady && (
        <div className="absolute inset-0 bg-[#111111] animate-pulse flex items-center justify-center text-[#888888]">
          Initializing Chart...
        </div>
      )}
      <div ref={chartContainerRef} className="w-full" />
    </div>
  );
}
