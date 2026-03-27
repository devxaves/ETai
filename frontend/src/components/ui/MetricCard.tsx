import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon?: React.ReactNode;
  className?: string;
  isLoading?: boolean;
}

export default function MetricCard({
  title,
  value,
  change,
  icon,
  className,
  isLoading = false,
}: MetricCardProps) {
  if (isLoading) {
    return (
      <div className={cn("border border-[#2a2a2a] bg-[#1a1a1a] rounded-lg p-5 h-28 skeleton", className)} />
    );
  }

  const isPositive = change && change > 0;
  const isNegative = change && change < 0;

  return (
    <div className={cn("border border-[#2a2a2a] bg-[#1a1a1a] rounded-lg p-5 flex flex-col justify-between hover:border-[#3a3a3a] transition-colors", className)}>
      <div className="flex justify-between items-start text-[#888888]">
        <h3 className="text-sm font-medium">{title}</h3>
        {icon && <div className="text-[#666666]">{icon}</div>}
      </div>
      
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-2xl font-semibold tabular-nums text-[#e8e8e8]">
          {value}
        </span>
        
        {change !== undefined && (
          <span
            className={cn(
              "text-xs font-medium tabular-nums px-1.5 py-0.5 rounded",
              isPositive ? "text-green-400 bg-green-400/10" : 
              isNegative ? "text-red-400 bg-red-400/10" : 
              "text-[#888888] bg-[#2a2a2a]"
            )}
          >
            {isPositive ? "+" : ""}{change.toFixed(2)}%
          </span>
        )}
      </div>
    </div>
  );
}
