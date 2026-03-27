import { cn } from "@/lib/utils";

export default function LoadingSpinner({
  className,
  size = "md",
}: {
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const sizeClasses = {
    sm: "w-4 h-4",
    md: "w-8 h-8",
    lg: "w-12 h-12",
  };

  return (
    <div className={cn("flex justify-center items-center h-full w-full", className)}>
      <div
        className={cn(
          "animate-spin rounded-full border-b-2 border-green-500",
          sizeClasses[size]
        )}
      ></div>
    </div>
  );
}
