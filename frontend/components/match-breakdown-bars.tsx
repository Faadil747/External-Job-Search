import { titleCase } from "@/lib/utils";
import type { MatchBreakdown } from "@/lib/types";

const DIMENSION_LABELS: Record<string, string> = {
  skills: "Skills",
  experience: "Experience",
  role: "Role Fit",
  semantic: "Semantic Fit",
  location: "Location",
  domain: "Domain",
  education: "Education",
  work_mode: "Work Mode",
  recency: "Recency",
  trust: "Source Trust",
};

export function MatchBreakdownBars({ breakdown }: { breakdown: MatchBreakdown }) {
  const entries = Object.entries(breakdown).filter(([, v]) => typeof v === "number");
  if (entries.length === 0) return null;

  return (
    <div className="space-y-3">
      {entries.map(([key, value]) => (
        <div key={key}>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="font-medium text-foreground">{DIMENSION_LABELS[key] || titleCase(key)}</span>
            <span className="text-muted-foreground">{Math.round(value as number)}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-700 ease-out"
              style={{ width: `${Math.max(0, Math.min(100, value as number))}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
