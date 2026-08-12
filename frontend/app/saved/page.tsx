"use client";

import * as React from "react";
import Link from "next/link";
import { Bookmark } from "lucide-react";

import { RouteGuard } from "@/components/route-guard";
import { Button } from "@/components/ui/button";
import { JobCard } from "@/components/job-card";
import { JobCardSkeleton } from "@/components/job-card-skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { ApiError, jobsApi, savedJobsApi } from "@/lib/api";
import type { JobCard as JobCardType, SavedJob } from "@/lib/types";

export default function SavedJobsPage() {
  return (
    <RouteGuard>
      <SavedJobsContent />
    </RouteGuard>
  );
}

function SavedJobsContent() {
  const [status, setStatus] = React.useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [jobs, setJobs] = React.useState<JobCardType[]>([]);
  const [failedCount, setFailedCount] = React.useState(0);

  const load = React.useCallback(() => {
    setStatus("loading");
    setErrorMessage(null);

    savedJobsApi
      .list()
      .then(async (saved: SavedJob[]) => {
        if (saved.length === 0) {
          setJobs([]);
          setStatus("ready");
          return;
        }

        const results = await Promise.allSettled(saved.map((s) => jobsApi.getById(s.job_id)));
        const resolved: JobCardType[] = [];
        let failures = 0;

        results.forEach((r, i) => {
          if (r.status === "fulfilled") {
            const detail = r.value;
            resolved.push({
              id: detail.id,
              title: detail.title,
              company_name: detail.company_name,
              company_logo_url: null,
              city: detail.city,
              state: detail.state,
              country: detail.country,
              work_mode: detail.work_mode,
              employment_type: detail.employment_type,
              experience_min: detail.experience_min,
              experience_max: detail.experience_max,
              salary_min: detail.salary_min,
              salary_max: detail.salary_max,
              currency: detail.currency,
              posted_at: detail.posted_at,
              top_skills: detail.match_reason?.matched_skills?.slice(0, 4) || [],
              match_score: detail.match_score,
              match_category: detail.match_category,
              why_it_matches: detail.match_reason?.overall_reason,
              is_verified: detail.is_verified,
              is_saved: true,
            });
          } else {
            failures++;
          }
        });

        setJobs(resolved);
        setFailedCount(failures);
        setStatus("ready");
      })
      .catch((err) => {
        setErrorMessage(err instanceof ApiError ? err.message : "Failed to load your saved jobs.");
        setStatus("error");
      });
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  async function handleUnsave(job: JobCardType) {
    setJobs((prev) => prev.filter((j) => j.id !== job.id));
    try {
      await jobsApi.unsave(job.id);
    } catch {
      // Re-add on failure so the user knows it didn't actually unsave.
      setJobs((prev) => [...prev, job]);
    }
  }

  return (
    <div className="container max-w-6xl space-y-6 py-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Saved Jobs</h1>
        <p className="mt-1 text-muted-foreground">Jobs you&apos;ve bookmarked for later.</p>
      </div>

      {status === "loading" && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <JobCardSkeleton key={i} />
          ))}
        </div>
      )}

      {status === "error" && (
        <ErrorState title="Couldn't load saved jobs" description={errorMessage || undefined} onRetry={load} />
      )}

      {status === "ready" && jobs.length === 0 && (
        <EmptyState
          icon={<Bookmark className="h-5 w-5" />}
          title="No saved jobs yet"
          description="Bookmark jobs you're interested in from the jobs page to find them here later."
          action={
            <Button asChild>
              <Link href="/jobs">Browse jobs</Link>
            </Button>
          }
        />
      )}

      {status === "ready" && jobs.length > 0 && (
        <>
          {failedCount > 0 && (
            <p className="text-sm text-muted-foreground">
              {failedCount} saved job{failedCount > 1 ? "s" : ""} could not be loaded and{" "}
              {failedCount > 1 ? "were" : "was"} skipped.
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} onToggleSave={handleUnsave} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
