"use client";

import * as React from "react";
import { Loader2, MapPinOff, Search, Sparkles, SlidersHorizontal } from "lucide-react";

import { RouteGuard } from "@/components/route-guard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { JobCard } from "@/components/job-card";
import { JobCardSkeleton } from "@/components/job-card-skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { EMPTY_FILTERS, FilterSidebar, JobFilters, countActiveFilters } from "@/components/jobs/filter-sidebar";
import { ApiError, jobsApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { JobCard as JobCardType, JobSearchRequest } from "@/lib/types";

type Tab = "best" | "fresh" | "remote";
type SortBy = JobSearchRequest["sort_by"];

const SORT_OPTIONS: { label: string; value: SortBy }[] = [
  { label: "Best Match", value: "best_match" },
  { label: "Newest", value: "newest" },
  { label: "Highest Salary", value: "highest_salary" },
  { label: "Closest Location", value: "closest_location" },
];

export default function JobsPage() {
  return (
    <RouteGuard>
      <JobsContent />
    </RouteGuard>
  );
}

function JobsContent() {
  const [tab, setTab] = React.useState<Tab>("best");
  const [filters, setFilters] = React.useState<JobFilters>(EMPTY_FILTERS);
  const [sortBy, setSortBy] = React.useState<SortBy>("best_match");
  const [keyword, setKeyword] = React.useState("");
  const [aiQuery, setAiQuery] = React.useState("");
  const [aiMode, setAiMode] = React.useState(false);
  const [aiActiveQuery, setAiActiveQuery] = React.useState<string | null>(null);

  const [jobs, setJobs] = React.useState<JobCardType[]>([]);
  const [status, setStatus] = React.useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [nextCursor, setNextCursor] = React.useState<string | null | undefined>(undefined);
  const [loadingMore, setLoadingMore] = React.useState(false);
  const [mobileFiltersOpen, setMobileFiltersOpen] = React.useState(false);

  const requestIdRef = React.useRef(0);

  const buildFilteredRequest = React.useCallback(
    (cursor?: string): JobSearchRequest => {
      const workMode = [...(filters.work_mode || [])];
      if (tab === "remote" && !workMode.includes("remote")) workMode.push("remote");
      return {
        query: keyword || undefined,
        city: filters.city,
        state: filters.state,
        country: filters.country,
        work_mode: workMode.length ? workMode : undefined,
        employment_type: filters.employment_type?.length ? filters.employment_type : undefined,
        experience_min: filters.experience_min,
        experience_max: filters.experience_max,
        domain: filters.domain?.length ? filters.domain : undefined,
        skills: filters.skills?.length ? filters.skills : undefined,
        salary_min: filters.salary_min,
        posted_within_days: tab === "fresh" ? filters.posted_within_days ?? 7 : filters.posted_within_days,
        min_match_score: filters.min_match_score,
        sort_by: sortBy,
        cursor,
        limit: 20,
      };
    },
    [filters, sortBy, keyword, tab]
  );

  const fetchJobs = React.useCallback(
    async (cursor?: string) => {
      const myRequestId = ++requestIdRef.current;
      if (cursor) setLoadingMore(true);
      else {
        setStatus("loading");
        setErrorMessage(null);
      }

      try {
        const res = aiActiveQuery
          ? await jobsApi.searchNaturalLanguage(aiActiveQuery)
          : await jobsApi.search(buildFilteredRequest(cursor));

        if (requestIdRef.current !== myRequestId) return;

        setJobs((prev) => (cursor ? [...prev, ...res.items] : res.items));
        setNextCursor(res.next_cursor ?? null);
        setStatus("ready");
      } catch (err) {
        if (requestIdRef.current !== myRequestId) return;
        setErrorMessage(err instanceof ApiError ? err.message : "Failed to load jobs.");
        setStatus("error");
      } finally {
        if (requestIdRef.current === myRequestId) setLoadingMore(false);
      }
    },
    [aiActiveQuery, buildFilteredRequest]
  );

  React.useEffect(() => {
    // Debounce so rapid filter/keyword edits don't fire a request per keystroke.
    const timer = setTimeout(() => fetchJobs(), 350);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, filters, sortBy, keyword, aiActiveQuery]);

  function handleAiSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!aiQuery.trim()) {
      setAiActiveQuery(null);
      setAiMode(false);
      return;
    }
    setAiMode(true);
    setAiActiveQuery(aiQuery.trim());
  }

  function clearAiSearch() {
    setAiMode(false);
    setAiQuery("");
    setAiActiveQuery(null);
  }

  async function handleToggleSave(job: JobCardType) {
    setJobs((prev) => prev.map((j) => (j.id === job.id ? { ...j, is_saved: !j.is_saved } : j)));
    try {
      if (job.is_saved) await jobsApi.unsave(job.id);
      else await jobsApi.save(job.id);
    } catch {
      setJobs((prev) => prev.map((j) => (j.id === job.id ? { ...j, is_saved: job.is_saved } : j)));
    }
  }

  function resetFilters() {
    setFilters(EMPTY_FILTERS);
  }

  const activeFilterCount = countActiveFilters(filters);

  return (
    <div className="container max-w-7xl py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">Jobs for you</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Personalized matches from trusted job boards, ranked by our AI.
        </p>
      </div>

      {/* AI natural-language search */}
      <form onSubmit={handleAiSearch} className="mb-4">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Sparkles className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-primary" />
            <Input
              value={aiQuery}
              onChange={(e) => setAiQuery(e.target.value)}
              placeholder='Try "remote senior backend roles in fintech paying 20L+"'
              className="pl-10"
            />
          </div>
          <div className="flex gap-2">
            <Button type="submit" className="gap-2">
              <Sparkles className="h-4 w-4" /> Ask AI
            </Button>
            {aiMode && (
              <Button type="button" variant="outline" onClick={clearAiSearch}>
                Clear
              </Button>
            )}
          </div>
        </div>
      </form>

      {!aiMode && (
        <div className="relative mb-6">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="Search by title, company, or keyword"
            className="pl-10"
          />
        </div>
      )}

      {aiMode && aiActiveQuery && (
        <div className="mb-6 flex items-center gap-2 rounded-xl bg-primary-50 px-4 py-2.5 text-sm text-primary">
          <Sparkles className="h-4 w-4" />
          Showing AI results for &ldquo;{aiActiveQuery}&rdquo;
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <aside className="hidden lg:block">
          <div className={cn("sticky top-20 rounded-2xl border border-border bg-card p-5 shadow-soft", aiMode && "pointer-events-none opacity-50")}>
            <FilterSidebar filters={filters} onChange={setFilters} onClear={resetFilters} />
          </div>
        </aside>

        <div className="min-w-0">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
              <TabsList>
                <TabsTrigger value="best" disabled={aiMode}>
                  Best Matches
                </TabsTrigger>
                <TabsTrigger value="fresh" disabled={aiMode}>
                  Fresh Jobs
                </TabsTrigger>
                <TabsTrigger value="remote" disabled={aiMode}>
                  Remote
                </TabsTrigger>
              </TabsList>
            </Tabs>

            <div className="flex items-center gap-2">
              <Sheet open={mobileFiltersOpen} onOpenChange={setMobileFiltersOpen}>
                <SheetTrigger asChild>
                  <Button variant="outline" size="sm" className="gap-1.5 lg:hidden">
                    <SlidersHorizontal className="h-4 w-4" /> Filters
                    {activeFilterCount > 0 && <Badge className="ml-1 h-5 px-1.5">{activeFilterCount}</Badge>}
                  </Button>
                </SheetTrigger>
                <SheetContent side="left">
                  <SheetHeader>
                    <SheetTitle>Filters</SheetTitle>
                  </SheetHeader>
                  <div className="mt-4">
                    <FilterSidebar filters={filters} onChange={setFilters} onClear={resetFilters} />
                  </div>
                </SheetContent>
              </Sheet>

              <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortBy)} disabled={aiMode}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Sort by" />
                </SelectTrigger>
                <SelectContent>
                  {SORT_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {status === "loading" && (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <JobCardSkeleton key={i} />
              ))}
            </div>
          )}

          {status === "error" && (
            <ErrorState
              title="Couldn't load jobs"
              description={errorMessage || undefined}
              onRetry={() => fetchJobs()}
            />
          )}

          {status === "ready" && jobs.length === 0 && (
            <EmptyState
              icon={<MapPinOff className="h-5 w-5" />}
              title="No jobs match your filters"
              description="Try expanding your location, viewing jobs from the last 7 days, or removing the salary filter."
              action={
                <Button variant="outline" onClick={resetFilters}>
                  Clear filters
                </Button>
              }
            />
          )}

          {status === "ready" && jobs.length > 0 && (
            <>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {jobs.map((job) => (
                  <JobCard key={job.id} job={job} onToggleSave={handleToggleSave} />
                ))}
              </div>

              {nextCursor && (
                <div className="mt-8 flex justify-center">
                  <Button variant="outline" onClick={() => fetchJobs(nextCursor)} disabled={loadingMore} className="gap-2">
                    {loadingMore && <Loader2 className="h-4 w-4 animate-spin" />}
                    Load more
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
