"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Bookmark,
  Briefcase,
  ClipboardList,
  Sparkles,
  UploadCloud,
  UserCircle,
} from "lucide-react";

import { RouteGuard } from "@/components/route-guard";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { JobCard } from "@/components/job-card";
import { JobCardSkeleton } from "@/components/job-card-skeleton";
import { ApiError, applicationsApi, candidateApi, jobsApi, savedJobsApi } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import type { CandidateProfile, JobCard as JobCardType } from "@/lib/types";

export default function DashboardPage() {
  return (
    <RouteGuard>
      <DashboardContent />
    </RouteGuard>
  );
}

function DashboardContent() {
  const user = useAuthStore((s) => s.user);

  const [profile, setProfile] = React.useState<CandidateProfile | null>(null);
  const [profileStatus, setProfileStatus] = React.useState<"loading" | "ready" | "error" | "none">("loading");

  const [jobs, setJobs] = React.useState<JobCardType[]>([]);
  const [jobsStatus, setJobsStatus] = React.useState<"loading" | "ready" | "error">("loading");

  const [savedCount, setSavedCount] = React.useState<number | null>(null);
  const [inProgressCount, setInProgressCount] = React.useState<number | null>(null);

  React.useEffect(() => {
    candidateApi
      .getProfile()
      .then((data) => {
        setProfile(data);
        setProfileStatus("ready");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setProfileStatus("none");
        } else {
          setProfileStatus("error");
        }
      });

    jobsApi
      .recommended({ fresh_only: true })
      .then((res) => {
        setJobs(res.items.slice(0, 4));
        setJobsStatus("ready");
      })
      .catch(() => setJobsStatus("error"));

    savedJobsApi
      .list()
      .then((items) => setSavedCount(items.length))
      .catch(() => setSavedCount(null));

    applicationsApi
      .list()
      .then((items) =>
        setInProgressCount(
          items.filter((a) => !["rejected", "withdrawn"].includes(a.status)).length
        )
      )
      .catch(() => setInProgressCount(null));
  }, []);

  async function handleToggleSave(job: JobCardType) {
    setJobs((prev) => prev.map((j) => (j.id === job.id ? { ...j, is_saved: !j.is_saved } : j)));
    try {
      if (job.is_saved) {
        await jobsApi.unsave(job.id);
      } else {
        await jobsApi.save(job.id);
      }
    } catch {
      setJobs((prev) => prev.map((j) => (j.id === job.id ? { ...j, is_saved: job.is_saved } : j)));
    }
  }

  const topRole = profile?.ai_recommended_roles?.[0];

  return (
    <div className="container max-w-6xl space-y-8 py-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Welcome back{user?.email ? `, ${user.email.split("@")[0]}` : ""}
        </h1>
        <p className="mt-1 text-muted-foreground">Here&apos;s what&apos;s happening with your job search.</p>
      </div>

      {profileStatus === "none" && (
        <EmptyState
          icon={<UploadCloud className="h-6 w-6" />}
          title="Upload your resume to get started"
          description="We'll build your candidate profile and start matching you to jobs automatically."
          action={
            <Button asChild>
              <Link href="/upload">Upload Resume</Link>
            </Button>
          }
        />
      )}

      {profileStatus !== "none" && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            icon={<UserCircle className="h-5 w-5" />}
            label="Profile completion"
            value={profileStatus === "ready" && profile ? `${profile.profile_completion_pct}%` : undefined}
            loading={profileStatus === "loading"}
            href="/profile"
          >
            {profileStatus === "ready" && profile && (
              <Progress value={profile.profile_completion_pct} className="mt-2" />
            )}
          </StatCard>

          <StatCard
            icon={<Sparkles className="h-5 w-5" />}
            label="AI resume score"
            value={
              profileStatus === "ready" && profile?.resume_score != null
                ? `${Math.round(profile.resume_score)}/100`
                : profileStatus === "ready"
                ? "—"
                : undefined
            }
            loading={profileStatus === "loading"}
            href="/resume-analysis"
          />

          <StatCard
            icon={<Bookmark className="h-5 w-5" />}
            label="Saved jobs"
            value={savedCount != null ? String(savedCount) : undefined}
            loading={savedCount == null}
            href="/saved"
          />

          <StatCard
            icon={<ClipboardList className="h-5 w-5" />}
            label="Applications in progress"
            value={inProgressCount != null ? String(inProgressCount) : undefined}
            loading={inProgressCount == null}
            href="/applications"
          />
        </div>
      )}

      {profileStatus === "ready" && topRole && (
        <Card className="border-primary/20 bg-primary-50/50">
          <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Your top recommended role</p>
                <p className="text-lg font-semibold text-foreground">{topRole.title}</p>
              </div>
            </div>
            <Badge>{Math.round(topRole.confidence)}% confidence</Badge>
          </CardContent>
        </Card>
      )}

      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-foreground">Fresh Jobs For You</h2>
          <Button asChild variant="ghost" size="sm" className="gap-1">
            <Link href="/jobs">
              See all jobs <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>

        {jobsStatus === "loading" && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <JobCardSkeleton key={i} />
            ))}
          </div>
        )}

        {jobsStatus === "error" && (
          <EmptyState
            icon={<Briefcase className="h-5 w-5" />}
            title="Couldn't load recommended jobs"
            description="The jobs service may still be starting up. Try the full jobs page instead."
            action={
              <Button asChild variant="outline">
                <Link href="/jobs">Browse jobs</Link>
              </Button>
            }
          />
        )}

        {jobsStatus === "ready" && jobs.length === 0 && (
          <EmptyState
            icon={<Briefcase className="h-5 w-5" />}
            title="No fresh matches yet"
            description="Complete your profile and preferences to help our AI find better matches."
            action={
              <Button asChild variant="outline">
                <Link href="/profile">Complete profile</Link>
              </Button>
            }
          />
        )}

        {jobsStatus === "ready" && jobs.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} onToggleSave={handleToggleSave} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  loading,
  href,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  value?: string;
  loading?: boolean;
  href: string;
  children?: React.ReactNode;
}) {
  return (
    <Link href={href}>
      <Card className="h-full transition-shadow hover:shadow-soft-lg">
        <CardHeader className="flex-row items-center gap-3 space-y-0 pb-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary">
            {icon}
          </div>
          <CardDescription>{label}</CardDescription>
        </CardHeader>
        <CardContent>
          {loading || value === undefined ? (
            <Skeleton className="h-7 w-16" />
          ) : (
            <p className="text-2xl font-bold text-foreground">{value}</p>
          )}
          {children}
        </CardContent>
      </Card>
    </Link>
  );
}
