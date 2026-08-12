import { cn } from "@/lib/utils";
import type { MatchCategory } from "@/lib/types";

function tierFromScore(score: number): "excellent" | "strong" | "good" | "low" {
  if (score >= 90) return "excellent";
  if (score >= 80) return "strong";
  if (score >= 70) return "good";
  return "low";
}

const STYLES: Record<string, string> = {
  excellent: "bg-emerald-50 text-emerald-700 border-emerald-200",
  strong: "bg-blue-50 text-blue-700 border-blue-200",
  good: "bg-amber-50 text-amber-700 border-amber-200",
  potential: "bg-amber-50 text-amber-700 border-amber-200",
  stretch: "bg-slate-100 text-slate-600 border-slate-200",
  low: "bg-slate-100 text-slate-600 border-slate-200",
};

export function MatchBadge({
  score,
  category,
  className,
}: {
  score?: number | null;
  category?: MatchCategory | null;
  className?: string;
}) {
  if (score == null) return null;
  const key = category || tierFromScore(score);
  const style = STYLES[key] || STYLES.low;

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold",
        style,
        className
      )}
      title="AI-generated match score"
    >
      {Math.round(score)}% Match
    </div>
  );
}
