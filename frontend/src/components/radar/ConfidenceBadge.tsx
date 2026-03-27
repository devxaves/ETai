import { cn } from "@/lib/utils";

export default function ConfidenceBadge({ score, className }: { score: number; className?: string }) {
  let colorClass = "";
  if (score >= 70) {
    colorClass = "text-green-400 bg-green-400/10 border-green-400/20";
  } else if (score >= 40) {
    colorClass = "text-amber-400 bg-amber-400/10 border-amber-400/20";
  } else {
    colorClass = "text-red-400 bg-red-400/10 border-red-400/20";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-1 rounded text-xs font-bold border tabular-nums",
        colorClass,
        className
      )}
    >
      {score}% Confidence
    </span>
  );
}
