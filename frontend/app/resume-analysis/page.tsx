"use client";

import * as React from "react";
import Link from "next/link";
import { CheckCircle2, FileWarning, Lightbulb, Sparkles, UploadCloud } from "lucide-react";

import { RouteGuard } from "@/components/route-guard";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { ScoreRing } from "@/components/score-ring";
import { ScoreBar } from "@/components/score-bar";
import { TierBadge } from "@/components/tier-badge";
import { ApiError, candidateApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { ResumeAnalysis } from "@/lib/types";

export default function ResumeAnalysisPage() {
  return (
    <RouteGuard>
      <ResumeAnalysisContent />
    </RouteGuard>
  );
}

function ResumeAnalysisContent() {
  const [analysis, setAnalysis] = React.useState<ResumeAnalysis | null>(null);
  const [status, setStatus] = React.useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    setStatus("loading");
    candidateApi
      .resumeAnalysis()
      .then((data) => {
        setAnalysis(data);
        setStatus("ready");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setStatus("empty");
          return;
        }
        setErrorMessage(err instanceof ApiError ? err.message : "Failed to load your resume analysis.");
        setStatus("error");
      });
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  if (status === "loading") {
    return (
      <div className="container max-w-4xl space-y-6 py-10">
        <Skeleton className="h-9 w-72" />
        <div className="grid gap-6 md:grid-cols-[240px_1fr]">
          <Skeleton className="h-56 w-full rounded-2xl" />
          <Skeleton className="h-56 w-full rounded-2xl" />
        </div>
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (status === "empty") {
    return (
      <div className="container max-w-2xl py-16">
        <EmptyState
          icon={<UploadCloud className="h-6 w-6" />}
          title="No resume analysis yet"
          description="Upload your resume to get an AI-generated match report with a score breakdown, strengths, and recommended roles."
          action={
            <Button asChild>
              <Link href="/upload">Upload Resume</Link>
            </Button>
          }
        />
      </div>
    );
  }

  if (status === "error" || !analysis) {
    return (
      <div className="container max-w-2xl py-16">
        <ErrorState
          title="Couldn't load your resume analysis"
          description={errorMessage || undefined}
          onRetry={load}
        />
      </div>
    );
  }

  const breakdownEntries = Object.entries(analysis.score_breakdown || {});

  return (
    <div className="container max-w-4xl space-y-8 py-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Your AI Resume Report</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Generated {formatDate(analysis.created_at)} · AI-generated assessment, not a certification
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/upload">Re-upload Resume</Link>
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-[240px_1fr]">
        <Card className="flex flex-col items-center justify-center py-8">
          <ScoreRing score={analysis.overall_score} label="/ 100" />
          <p className="mt-4 text-center text-sm font-medium text-foreground">Overall AI Score</p>
          <p className="mt-1 max-w-[180px] text-center text-xs text-muted-foreground">
            An AI-generated assessment of resume strength, not an official certification.
          </p>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Score Breakdown</CardTitle>
            <CardDescription>How the AI weighted different dimensions of your resume.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {breakdownEntries.length === 0 ? (
              <p className="text-sm text-muted-foreground">No breakdown data available.</p>
            ) : (
              breakdownEntries.map(([key, value]) => <ScoreBar key={key} label={key} value={value} />)
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CheckCircle2 className="h-4 w-4 text-success" /> Strengths
            </CardTitle>
          </CardHeader>
          <CardContent>
            {analysis.strengths?.length ? (
              <ul className="space-y-2.5">
                {analysis.strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                    {s}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No strengths identified yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Lightbulb className="h-4 w-4 text-warning" /> Suggestions to Improve
            </CardTitle>
          </CardHeader>
          <CardContent>
            {analysis.improvement_suggestions?.length ? (
              <ul className="space-y-2.5">
                {analysis.improvement_suggestions.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                    <FileWarning className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                    {s}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No suggestions right now — nice work.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-4 w-4 text-primary" /> Recommended Roles
          </CardTitle>
          <CardDescription>Ranked by how closely your background matches each role.</CardDescription>
        </CardHeader>
        <CardContent>
          {analysis.recommended_roles?.length ? (
            <div className="space-y-4">
              {analysis.recommended_roles.map((role, i) => (
                <div key={`${role.title}-${i}`} className="rounded-xl border border-border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground">
                        {i + 1}
                      </span>
                      <h3 className="font-semibold text-foreground">{role.title}</h3>
                    </div>
                    <div className="flex items-center gap-2">
                      <TierBadge tier={role.tier} />
                      <Badge variant="outline">{Math.round(role.confidence)}% confidence</Badge>
                    </div>
                  </div>
                  {role.reason && <p className="mt-2 text-sm text-muted-foreground">{role.reason}</p>}
                  <div className="mt-3 flex flex-wrap gap-4 text-xs">
                    {role.matching_skills?.length > 0 && (
                      <div>
                        <p className="mb-1 font-medium text-success">Matching skills</p>
                        <div className="flex flex-wrap gap-1">
                          {role.matching_skills.map((s) => (
                            <span key={s} className="rounded-full bg-success/10 px-2 py-0.5 text-success">
                              {s}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {role.missing_skills?.length > 0 && (
                      <div>
                        <p className="mb-1 font-medium text-destructive">Skills to build</p>
                        <div className="flex flex-wrap gap-1">
                          {role.missing_skills.map((s) => (
                            <span key={s} className="rounded-full bg-destructive/10 px-2 py-0.5 text-destructive">
                              {s}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No role recommendations yet.</p>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-center gap-3 pb-6">
        <Button asChild size="lg">
          <Link href="/jobs">See My Matched Jobs</Link>
        </Button>
        <Button asChild size="lg" variant="outline">
          <Link href="/profile">Review My Profile</Link>
        </Button>
      </div>
    </div>
  );
}
