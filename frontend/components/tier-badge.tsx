import { cn } from "@/lib/utils";

const TIER_LABELS: Record<string, string> = {
  excellent: "Excellent Fit",
  strong: "Strong Fit",
  good: "Good Fit",
  stretch: "Stretch Opportunity",
  low: "Low Fit",
};

const TIER_STYLES: Record<string, string> = {
  excellent: "bg-emerald-50 text-emerald-700 border-emerald-200",
  strong: "bg-blue-50 text-blue-700 border-blue-200",
  good: "bg-amber-50 text-amber-700 border-amber-200",
  stretch: "bg-violet-50 text-violet-700 border-violet-200",
  low: "bg-slate-100 text-slate-600 border-slate-200",
};

export function TierBadge({ tier, className }: { tier: string; className?: string }) {
  const key = tier?.toLowerCase() || "low";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        TIER_STYLES[key] || TIER_STYLES.low,
        className
      )}
    >
      {TIER_LABELS[key] || tier}
    </span>
  );
}
