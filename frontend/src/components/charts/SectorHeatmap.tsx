"use client";

import { Treemap, ResponsiveContainer, Tooltip } from "recharts";
import { cn } from "@/lib/utils";

interface SectorData {
  name: string;
  size: number;
  change: number;
  [key: string]: any;
}

const COLORS = {
  strongUp: "#1e4620",
  up: "#26a69a",
  flat: "#2a2a2a",
  down: "#ef5350",
  strongDown: "#7f1d1d",
};

const CustomizedContent = (props: any) => {
  const { root, depth, x, y, width, height, index, payload, colors, rank, name, change } = props;

  // Determine color based on performance
  let color = COLORS.flat;
  if (change > 2) color = COLORS.strongUp;
  else if (change > 0) color = COLORS.up;
  else if (change < -2) color = COLORS.strongDown;
  else if (change < 0) color = COLORS.down;

  if (width < 30 || height < 30) return null; // Too small to render text

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{
          fill: depth < 2 ? color : "none",
          stroke: "#0a0a0a",
          strokeWidth: 2,
          strokeOpacity: 1,
        }}
        className="transition-colors hover:opacity-80 cursor-pointer"
      />
      {depth === 1 ? (
        <text
          x={x + width / 2}
          y={y + height / 2}
          textAnchor="middle"
          fill="#fff"
          fontSize={12}
          fontWeight="bold"
          dominantBaseline="middle"
          className="pointer-events-none"
        >
          {name}
        </text>
      ) : null}
      {depth === 1 && height > 40 && (
        <text
          x={x + width / 2}
          y={y + height / 2 + 16}
          textAnchor="middle"
          fill="#f0f0f0"
          fontSize={10}
          dominantBaseline="middle"
          className="pointer-events-none tabular-nums font-mono"
        >
          {change > 0 ? "+" : ""}
          {change.toFixed(2)}%
        </text>
      )}
    </g>
  );
};

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] p-3 rounded shadow-lg text-sm">
        <p className="font-bold text-white mb-1">{data.name}</p>
        <p className="text-[#888888] mb-1">Weight: {data.size}%</p>
        <p
          className={cn(
            "font-mono font-bold",
            data.change > 0 ? "text-green-400" : data.change < 0 ? "text-red-400" : "text-[#888888]"
          )}
        >
          Change: {data.change > 0 ? "+" : ""}
          {data.change.toFixed(2)}%
        </p>
      </div>
    );
  }
  return null;
};

interface Props {
  data: SectorData[];
  height?: number;
}

export default function SectorHeatmap({ data, height = 300 }: Props) {
  if (!data || data.length === 0) {
    return <div className="h-[300px] w-full skeleton rounded"></div>;
  }

  return (
    <div className="w-full relative bg-[#111111] border border-[#2a2a2a] rounded" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <Treemap
          data={data}
          dataKey="size"
          aspectRatio={4 / 3}
          stroke="#fff"
          content={<CustomizedContent />}
        >
          <Tooltip content={<CustomTooltip />} />
        </Treemap>
      </ResponsiveContainer>
    </div>
  );
}
