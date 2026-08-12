"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  Bookmark,
  Building2,
  Calendar,
  ExternalLink,
  Loader2,
  MapPin,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TrendingUp,
} from "lucide-react";

import { RouteGuard } from "@/components/route-guard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";
import { MatchBadge } from "@/components/match-badge";
import { MatchBreakdownBars } from "@/components/match-breakdown-bars";
import { cn, formatDate, formatExperienceRange, formatSalaryRange, logoColor, titleCase } from "@/lib/utils";
import { ApiError, jobsApi, savedJobsApi } from "@/lib/api";
import type { EstimatedSalary, JobDetail } from "@/lib/types";

export default function JobDetailPage() {
  return (
    <RouteGuard>
      <JobDetailContent />
    </RouteGuard>
  );
}

function JobDetailContent() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const jobId = params.id;

  const [job, setJob] = React.useState<JobDetail | null>(null);
  const [status, setStatus] = React.useState<"loading" | "ready" | "error" | "notfound">("loading");
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [isSaved, setIsSaved] = React.useState(false);
  const [applying, setApplying] = React.useState(false);
  const [feedbackSent, setFeedbackSent] = React.useState<string | null>(null);
  const [salaryEstimate, setSalaryEstimate] = React.useState<EstimatedSalary | null>(null);
  const [salaryEstimateStatus, setSalaryEstimateStatus] = React.useState<
    "idle" | "loading" | "unavailable"
  >("idle");

  const load = React.useCallback(() => {
    setStatus("loading");
    jobsApi
      .getById(jobId)
      .then((data) => {
        setJob(data);
        setStatus("ready");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setStatus("notfound");
          return;
        }
        setErrorMessage(err instanceof ApiError ? err.message : "Failed to load this job.");
        setStatus("error");
      });
  }, [jobId]);

  React.useEffect(() => {
    load();
  }, [load]);

  React.useEffect(() => {
    // JobDetail doesn't carry `is_saved` per the contract, so cross-reference
    // the saved-jobs list to reflect the correct initial bookmark state.
    let cancelled = false;
    savedJobsApi
      .list()
      .then((items) => {
        if (!cancelled) setIsSaved(items.some((s) => s.job_id === jobId));
      })
      .catch(() => {
        // Non-fatal — the button just starts unsaved.
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  async function handleToggleSave() {
    if (!job) return;
    setSaving(true);
    try {
      if (isSaved) {
        await jobsApi.unsave(job.id);
        setIsSaved(false);
      } else {
        await jobsApi.save(job.id);
        setIsSaved(true);
      }
    } catch {
      // Keep prior state on failure — no optimistic flip here since this is a single toggle.
    } finally {
      setSaving(false);
    }
  }

  async function handleApply() {
    if (!job) return;
    setApplying(true);
    try {
      await jobsApi.applyClick(job.id);
    } catch {
      // Even if the click-tracking call fails, still let the user get to the application.
    } finally {
      setApplying(false);
      if (job.application_url) {
        window.open(job.application_url, "_blank", "noopener,noreferrer");
      }
    }
  }

  async function handleEstimateSalary() {
    if (!job) return;
    setSalaryEstimateStatus("loading");
    try {
      const estimate = await jobsApi.estimatedSalary(job.id);
      setSalaryEstimate(estimate);
      setSalaryEstimateStatus("idle");
    } catch {
      setSalaryEstimateStatus("unavailable");
    }
  }

  async function sendFeedback(action: "not_relevant" | "interested" | "hidden_type") {
    if (!job) return;
    setFeedbackSent(action);
    try {
      await jobsApi.feedback(job.id, action);
    } catch {
      setFeedbackSent(null);
    }
  }

  if (status === "loading") {
    return (
      <div className="container max-w-4xl space-y-6 py-10">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-40 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (status === "notfound") {
    return (
      <div className="container max-w-2xl py-16">
        <ErrorState
          title="Job not found"
          description="This job may have been removed or the link is incorrect."
        />
        <div className="mt-4 flex justify-center">
          <Button asChild variant="outline">
            <Link href="/jobs">Back to jobs</Link>
          </Button>
        </div>
      </div>
    );
  }

  if (status === "error" || !job) {
    return (
      <div className="container max-w-2xl py-16">
        <ErrorState title="Couldn't load this job" description={errorMessage || undefined} onRetry={load} />
      </div>
    );
  }

  const location = [job.city, job.state, job.country].filter(Boolean).join(", ") || "Location flexible";

  return (
    <div className="container max-w-4xl space-y-6 py-8">
      <Button variant="ghost" size="sm" className="gap-1.5 -ml-2" onClick={() => router.back()}>
        <ArrowLeft className="h-4 w-4" /> Back
      </Button>

      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div
                className={cn(
                  "flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl text-lg font-semibold text-white",
                  logoColor(job.company_name)
                )}
              >
                {job.company_name?.slice(0, 2).toUpperCase() || "JM"}
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground">{job.title}</h1>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Building2 className="h-3.5 w-3.5" /> {job.company_name}
                  </span>
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5" /> {location}
                  </span>
                  {job.posted_at && (
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3.5 w-3.5" /> Posted {formatDate(job.posted_at)}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <button
              onClick={handleToggleSave}
              disabled={saving}
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:bg-muted disabled:opacity-50",
                isSaved && "border-primary/30 bg-primary-50 text-primary"
              )}
              aria-label={isSaved ? "Unsave job" : "Save job"}
            >
              <Bookmark className={cn("h-4 w-4", isSaved && "fill-current")} />
            </button>
          </div>

          <div className="mt-4 flex flex-wrap gap-1.5">
            {job.employment_type && <Badge variant="outline">{titleCase(job.employment_type)}</Badge>}
            {job.work_mode && <Badge variant="outline">{titleCase(job.work_mode)}</Badge>}
            <Badge variant="outline">{formatExperienceRange(job.experience_min, job.experience_max)}</Badge>
            {job.domain?.map((d) => (
              <Badge key={d} variant="outline">
                {d}
              </Badge>
            ))}
            {job.is_verified && (
              <Badge variant="success" className="gap-1">
                <ShieldCheck className="h-3 w-3" /> Verified
              </Badge>
            )}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <p className="text-lg font-semibold text-foreground">
              {formatSalaryRange(job.salary_min, job.salary_max, job.currency)}
            </p>
            {job.salary_min == null && job.salary_max == null && (
              <>
                {salaryEstimateStatus === "idle" && !salaryEstimate && (
                  <Button variant="outline" size="sm" className="gap-1.5" onClick={handleEstimateSalary}>
                    <TrendingUp className="h-3.5 w-3.5" /> View market estimate
                  </Button>
                )}
                {salaryEstimateStatus === "loading" && (
                  <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Fetching market estimate…
                  </span>
                )}
                {salaryEstimateStatus === "unavailable" && (
                  <span className="text-sm text-muted-foreground">
                    No market estimate available for this role.
                  </span>
                )}
              </>
            )}
          </div>
          {salaryEstimate && salaryEstimate.is_estimate && (
            <div className="mt-2 flex items-center gap-2 rounded-lg bg-warning/10 px-3 py-2 text-sm text-foreground">
              <TrendingUp className="h-4 w-4 shrink-0 text-warning" />
              <span>
                <span className="font-medium">Estimated</span> — not the posted salary:{" "}
                {formatSalaryRange(salaryEstimate.min_salary, salaryEstimate.max_salary, salaryEstimate.currency)}
                {salaryEstimate.publisher_name ? ` (market data via ${salaryEstimate.publisher_name})` : ""}
              </span>
            </div>
          )}

          <div className="mt-6 flex flex-wrap gap-3">
            <Button size="lg" className="gap-2" onClick={handleApply} disabled={applying || !job.application_url}>
              {applying ? <Loader2 className="h-4 w-4 animate-spin" /> : <ExternalLink className="h-4 w-4" />}
              Apply Now
            </Button>
            {!job.application_url && (
              <p className="flex items-center text-sm text-muted-foreground">
                No direct application link available for this listing.
              </p>
            )}
          </div>

          <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            <span>Was this job relevant to you?</span>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              disabled={!!feedbackSent}
              onClick={() => sendFeedback("interested")}
            >
              <ThumbsUp className="h-3.5 w-3.5" /> Interested
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              disabled={!!feedbackSent}
              onClick={() => sendFeedback("not_relevant")}
            >
              <ThumbsDown className="h-3.5 w-3.5" /> Not relevant
            </Button>
            {feedbackSent && <span className="text-xs text-success">Thanks for the feedback!</span>}
          </div>
        </CardContent>
      </Card>

      {job.match_score != null && (
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="h-4 w-4 text-primary" /> Why this matches you
            </CardTitle>
            <MatchBadge score={job.match_score} category={job.match_category} />
          </CardHeader>
          <CardContent className="space-y-5">
            {job.match_breakdown && <MatchBreakdownBars breakdown={job.match_breakdown} />}

            {job.match_reason && (
              <div className="grid gap-4 sm:grid-cols-2">
                {job.match_reason.matched_skills && job.match_reason.matched_skills.length > 0 && (
                  <div>
                    <p className="mb-1.5 text-sm font-medium text-foreground">Matched skills</p>
                    <div className="flex flex-wrap gap-1.5">
                      {job.match_reason.matched_skills.map((s) => (
                        <span key={s} className="rounded-full bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {job.match_reason.missing_skills && job.match_reason.missing_skills.length > 0 && (
                  <div>
                    <p className="mb-1.5 text-sm font-medium text-foreground">Missing skills</p>
                    <div className="flex flex-wrap gap-1.5">
                      {job.match_reason.missing_skills.map((s) => (
                        <span key={s} className="rounded-full bg-destructive/10 px-2.5 py-1 text-xs font-medium text-destructive">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {job.match_reason.transferable_skills && job.match_reason.transferable_skills.length > 0 && (
                  <div>
                    <p className="mb-1.5 text-sm font-medium text-foreground">Transferable skills</p>
                    <div className="flex flex-wrap gap-1.5">
                      {job.match_reason.transferable_skills.map((t) => (
                        <span
                          key={t.skill}
                          title={`Credited from your "${t.from}" experience`}
                          className="rounded-full bg-primary-100 px-2.5 py-1 text-xs font-medium text-primary"
                        >
                          {t.skill} <span className="text-primary/60">(from {t.from})</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {job.match_reason?.overall_reason && (
              <p className="rounded-xl bg-primary-50 p-3 text-sm text-foreground">
                {job.match_reason.overall_reason}
              </p>
            )}

            <div className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
              {job.match_reason?.experience_reason && <p>Experience: {job.match_reason.experience_reason}</p>}
              {job.match_reason?.location_reason && <p>Location: {job.match_reason.location_reason}</p>}
              {job.match_reason?.role_reason && <p>Role: {job.match_reason.role_reason}</p>}
              {job.match_reason?.domain_reason && <p>Domain: {job.match_reason.domain_reason}</p>}
            </div>

            {job.match_reason?.concerns && job.match_reason.concerns.length > 0 && (
              <div className="flex items-start gap-2 rounded-xl bg-warning/10 p-3 text-sm text-foreground">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                <ul className="list-inside list-disc space-y-1">
                  {job.match_reason.concerns.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Job description</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="whitespace-pre-line text-sm text-foreground/90">{job.description}</p>

          {job.responsibilities && job.responsibilities.length > 0 && (
            <div>
              <h3 className="mb-1.5 font-semibold text-foreground">Responsibilities</h3>
              <ul className="list-inside list-disc space-y-1 text-sm text-foreground/90">
                {job.responsibilities.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {job.requirements_required && job.requirements_required.length > 0 && (
            <div>
              <h3 className="mb-1.5 font-semibold text-foreground">Requirements</h3>
              <ul className="list-inside list-disc space-y-1 text-sm text-foreground/90">
                {job.requirements_required.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {job.requirements_preferred && job.requirements_preferred.length > 0 && (
            <div>
              <h3 className="mb-1.5 font-semibold text-foreground">Preferred</h3>
              <ul className="list-inside list-disc space-y-1 text-sm text-foreground/90">
                {job.requirements_preferred.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {(job.company_url || job.source_url || (job.other_sources && job.other_sources.length > 0)) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Source &amp; company</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {job.company_url && (
              <a
                href={job.company_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-primary hover:underline"
              >
                <ExternalLink className="h-3.5 w-3.5" /> Company website
              </a>
            )}
            {job.source_url && (
              <a
                href={job.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-primary hover:underline"
              >
                <ExternalLink className="h-3.5 w-3.5" /> Original job posting
              </a>
            )}
            {job.other_sources && job.other_sources.length > 0 && (
              <div>
                <p className="mb-1 text-muted-foreground">Also listed on:</p>
                <div className="flex flex-wrap gap-2">
                  {job.other_sources.map((src) => (
                    <a
                      key={src}
                      href={src}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground"
                    >
                      {src}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
