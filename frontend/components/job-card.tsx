"use client";

import * as React from "react";
import Link from "next/link";
import { Bookmark, MapPin, ShieldCheck, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MatchBadge } from "@/components/match-badge";
import { cn, formatExperienceRange, formatSalaryRange, logoColor, timeAgo, titleCase } from "@/lib/utils";
import type { JobCard as JobCardType } from "@/lib/types";

export function JobCard({
  job,
  onToggleSave,
  savePending,
}: {
  job: JobCardType;
  onToggleSave?: (job: JobCardType) => void;
  savePending?: boolean;
}) {
  const location = [job.city, job.state, job.country].filter(Boolean).join(", ") || "Location flexible";

  return (
    <div className="group flex h-full flex-col rounded-2xl border border-border bg-card p-5 shadow-soft transition-shadow hover:shadow-soft-lg">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white",
              logoColor(job.company_name)
            )}
          >
            {job.company_name?.slice(0, 2).toUpperCase() || "JM"}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-muted-foreground">{job.company_name}</p>
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <MapPin className="h-3 w-3 shrink-0" />
              <span className="truncate">{location}</span>
            </div>
          </div>
        </div>
        <button
          type="button"
          aria-label={job.is_saved ? "Unsave job" : "Save job"}
          disabled={savePending}
          onClick={(e) => {
            e.preventDefault();
            onToggleSave?.(job);
          }}
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted disabled:opacity-50",
            job.is_saved && "text-primary"
          )}
        >
          <Bookmark className={cn("h-4 w-4", job.is_saved && "fill-current")} />
        </button>
      </div>

      <Link href={`/jobs/${job.id}`} className="mt-3 block">
        <h3 className="text-base font-semibold leading-snug text-foreground group-hover:text-primary">
          {job.title}
        </h3>
      </Link>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {job.employment_type && <Badge variant="outline">{titleCase(job.employment_type)}</Badge>}
        {job.work_mode && <Badge variant="outline">{titleCase(job.work_mode)}</Badge>}
        <Badge variant="outline">{formatExperienceRange(job.experience_min, job.experience_max)}</Badge>
        {job.is_verified && (
          <Badge variant="success" className="gap-1">
            <ShieldCheck className="h-3 w-3" /> Verified
          </Badge>
        )}
      </div>

      {job.top_skills?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {job.top_skills.slice(0, 4).map((skill) => (
            <span
              key={skill}
              className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      <div className="mt-3 text-sm font-medium text-foreground">
        {formatSalaryRange(job.salary_min, job.salary_max, job.currency)}
      </div>

      {job.match_score != null && (
        <div className="mt-3 rounded-xl bg-primary-50 p-3">
          <div className="flex items-center justify-between gap-2">
            <MatchBadge score={job.match_score} category={job.match_category} />
            <span className="text-xs text-muted-foreground">{timeAgo(job.posted_at)}</span>
          </div>
          {job.why_it_matches && (
            <p className="mt-1.5 flex items-start gap-1 text-xs text-foreground/80">
              <Sparkles className="mt-0.5 h-3 w-3 shrink-0 text-primary" />
              <span className="clamp-2">{job.why_it_matches}</span>
            </p>
          )}
        </div>
      )}

      {job.match_score == null && (
        <div className="mt-3 text-xs text-muted-foreground">{timeAgo(job.posted_at)}</div>
      )}

      <div className="mt-4 flex gap-2 pt-1">
        <Button asChild variant="outline" size="sm" className="flex-1">
          <Link href={`/jobs/${job.id}`}>Details</Link>
        </Button>
        <Button asChild variant="secondary" size="sm" className="flex-1">
          <Link href={`/jobs/${job.id}`}>Apply Now</Link>
        </Button>
      </div>
    </div>
  );
}
