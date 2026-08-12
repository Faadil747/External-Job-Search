"use client";

import * as React from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp, ClipboardList, ExternalLink, Loader2 } from "lucide-react";

import { RouteGuard } from "@/components/route-guard";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError, applicationsApi, jobsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { Application, ApplicationStatus, JobDetail } from "@/lib/types";

const PIPELINE_COLUMNS: { status: ApplicationStatus; label: string }[] = [
  { status: "saved", label: "Saved" },
  { status: "apply_clicked", label: "Apply Clicked" },
  { status: "applied", label: "Applied" },
  { status: "screening", label: "Screening" },
  { status: "interview", label: "Interview" },
  { status: "offer", label: "Offer" },
];

const ALL_STATUSES: ApplicationStatus[] = [
  "saved",
  "apply_clicked",
  "applied",
  "screening",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
];

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  saved: "Saved",
  apply_clicked: "Apply Clicked",
  applied: "Applied",
  screening: "Screening",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

interface EnrichedApplication extends Application {
  job?: JobDetail;
}

export default function ApplicationsPage() {
  return (
    <RouteGuard>
      <ApplicationsContent />
    </RouteGuard>
  );
}

function ApplicationsContent() {
  const [apps, setApps] = React.useState<EnrichedApplication[]>([]);
  const [status, setStatus] = React.useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [closedOpen, setClosedOpen] = React.useState(false);
  const [updatingId, setUpdatingId] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    setStatus("loading");
    setErrorMessage(null);
    applicationsApi
      .list()
      .then(async (items) => {
        const enriched = await Promise.allSettled(
          items.map(async (a) => ({ ...a, job: await jobsApi.getById(a.job_id) }))
        );
        setApps(
          enriched.map((r, i) => (r.status === "fulfilled" ? r.value : items[i]))
        );
        setStatus("ready");
      })
      .catch((err) => {
        setErrorMessage(err instanceof ApiError ? err.message : "Failed to load your applications.");
        setStatus("error");
      });
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  async function handleStatusChange(app: EnrichedApplication, newStatus: ApplicationStatus) {
    setUpdatingId(app.id);
    const prevStatus = app.status;
    setApps((prev) => prev.map((a) => (a.id === app.id ? { ...a, status: newStatus } : a)));
    try {
      await applicationsApi.update(app.id, { status: newStatus });
    } catch {
      setApps((prev) => prev.map((a) => (a.id === app.id ? { ...a, status: prevStatus } : a)));
    } finally {
      setUpdatingId(null);
    }
  }

  if (status === "loading") {
    return (
      <div className="container max-w-7xl space-y-6 py-10">
        <Skeleton className="h-9 w-64" />
        <div className="grid gap-4 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-72 w-full rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="container max-w-2xl py-16">
        <ErrorState title="Couldn't load applications" description={errorMessage || undefined} onRetry={load} />
      </div>
    );
  }

  if (apps.length === 0) {
    return (
      <div className="container max-w-2xl py-16">
        <EmptyState
          icon={<ClipboardList className="h-5 w-5" />}
          title="No applications tracked yet"
          description="Save or apply to jobs and they'll show up here so you can track your progress."
          action={
            <Button asChild>
              <Link href="/jobs">Browse jobs</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const closedApps = apps.filter((a) => a.status === "rejected" || a.status === "withdrawn");

  return (
    <div className="container max-w-7xl space-y-8 py-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Applications Tracker</h1>
        <p className="mt-1 text-muted-foreground">Track where every job stands, from saved to offer.</p>
      </div>

      <div className="grid gap-4 overflow-x-auto lg:grid-cols-6">
        {PIPELINE_COLUMNS.map((col) => {
          const columnApps = apps.filter((a) => a.status === col.status);
          return (
            <div key={col.status} className="min-w-[240px]">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-foreground">{col.label}</h2>
                <Badge variant="secondary">{columnApps.length}</Badge>
              </div>
              <div className="space-y-3">
                {columnApps.length === 0 && (
                  <div className="rounded-xl border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                    No jobs here
                  </div>
                )}
                {columnApps.map((app) => (
                  <ApplicationCard
                    key={app.id}
                    app={app}
                    updating={updatingId === app.id}
                    onStatusChange={(s) => handleStatusChange(app, s)}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {closedApps.length > 0 && (
        <div>
          <button
            onClick={() => setClosedOpen((v) => !v)}
            className="flex items-center gap-1.5 text-sm font-semibold text-foreground"
          >
            Closed ({closedApps.length})
            {closedOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          {closedOpen && (
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {closedApps.map((app) => (
                <ApplicationCard
                  key={app.id}
                  app={app}
                  updating={updatingId === app.id}
                  onStatusChange={(s) => handleStatusChange(app, s)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ApplicationCard({
  app,
  updating,
  onStatusChange,
}: {
  app: EnrichedApplication;
  updating: boolean;
  onStatusChange: (status: ApplicationStatus) => void;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <Link href={`/jobs/${app.job_id}`} className="line-clamp-2 text-sm font-semibold text-foreground hover:text-primary">
            {app.job?.title || "Job details unavailable"}
          </Link>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">{app.job?.company_name || ""}</p>
        </div>
        {app.application_url && (
          <a
            href={app.application_url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 text-muted-foreground hover:text-primary"
            aria-label="Open application link"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>

      <p className="mt-2 text-xs text-muted-foreground">Added {formatDate(app.created_at)}</p>
      {app.notes && <p className="mt-1.5 line-clamp-2 text-xs text-foreground/80">{app.notes}</p>}

      <div className="mt-3 flex items-center gap-2">
        <Select value={app.status} onValueChange={(v) => onStatusChange(v as ApplicationStatus)} disabled={updating}>
          <SelectTrigger className="h-8 flex-1 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ALL_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {STATUS_LABELS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {updating && <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-muted-foreground" />}
      </div>
    </Card>
  );
}
