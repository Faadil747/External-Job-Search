"use client";

import * as React from "react";
import { RotateCcw } from "lucide-react";

import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { TagInput } from "@/components/tag-input";
import type { JobSearchRequest } from "@/lib/types";

export type JobFilters = Omit<JobSearchRequest, "sort_by" | "cursor" | "limit" | "query">;

export const EMPTY_FILTERS: JobFilters = {
  city: undefined,
  state: undefined,
  country: undefined,
  work_mode: [],
  employment_type: [],
  experience_min: undefined,
  experience_max: undefined,
  domain: [],
  skills: [],
  salary_min: undefined,
  posted_within_days: undefined,
  min_match_score: undefined,
};

const WORK_MODES = ["remote", "hybrid", "onsite"];
const EMPLOYMENT_TYPES = ["full_time", "part_time", "contract", "internship"];
const POSTED_WINDOWS = [
  { label: "Any time", value: undefined },
  { label: "Last 24 hours", value: 1 },
  { label: "Last 7 days", value: 7 },
  { label: "Last 30 days", value: 30 },
];

export function FilterSidebar({
  filters,
  onChange,
  onClear,
}: {
  filters: JobFilters;
  onChange: (next: JobFilters) => void;
  onClear: () => void;
}) {
  function toggle(field: "work_mode" | "employment_type", value: string) {
    const current = filters[field] || [];
    const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
    onChange({ ...filters, [field]: next });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Filters</h2>
        <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-xs" onClick={onClear}>
          <RotateCcw className="h-3 w-3" /> Reset
        </Button>
      </div>

      <div>
        <Label className="mb-2 block text-xs font-semibold uppercase text-muted-foreground">Job type</Label>
        <div className="space-y-2">
          {EMPLOYMENT_TYPES.map((type) => (
            <label key={type} className="flex items-center gap-2 text-sm capitalize">
              <Checkbox
                checked={(filters.employment_type || []).includes(type)}
                onCheckedChange={() => toggle("employment_type", type)}
              />
              {type.replace("_", " ")}
            </label>
          ))}
        </div>
      </div>

      <div>
        <Label className="mb-2 block text-xs font-semibold uppercase text-muted-foreground">Work type</Label>
        <div className="space-y-2">
          {WORK_MODES.map((mode) => (
            <label key={mode} className="flex items-center gap-2 text-sm capitalize">
              <Checkbox
                checked={(filters.work_mode || []).includes(mode)}
                onCheckedChange={() => toggle("work_mode", mode)}
              />
              {mode}
            </label>
          ))}
        </div>
      </div>

      <div>
        <Label className="mb-2 block text-xs font-semibold uppercase text-muted-foreground">Experience (years)</Label>
        <div className="flex items-center gap-2">
          <Input
            type="number"
            min={0}
            placeholder="Min"
            value={filters.experience_min ?? ""}
            onChange={(e) =>
              onChange({ ...filters, experience_min: e.target.value ? Number(e.target.value) : undefined })
            }
          />
          <span className="text-muted-foreground">–</span>
          <Input
            type="number"
            min={0}
            placeholder="Max"
            value={filters.experience_max ?? ""}
            onChange={(e) =>
              onChange({ ...filters, experience_max: e.target.value ? Number(e.target.value) : undefined })
            }
          />
        </div>
      </div>

      <div>
        <Label className="mb-2 block text-xs font-semibold uppercase text-muted-foreground">Minimum salary</Label>
        <Input
          type="number"
          min={0}
          placeholder="e.g. 800000"
          value={filters.salary_min ?? ""}
          onChange={(e) => onChange({ ...filters, salary_min: e.target.value ? Number(e.target.value) : undefined })}
        />
      </div>

      <div>
        <Label className="mb-2 block text-xs font-semibold uppercase text-muted-foreground">Posted within</Label>
        <div className="space-y-2">
          {POSTED_WINDOWS.map((w) => (
            <label key={w.label} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="posted_within"
                className="h-3.5 w-3.5 accent-primary"
                checked={filters.posted_within_days === w.value}
                onChange={() => onChange({ ...filters, posted_within_days: w.value })}
              />
              {w.label}
            </label>
          ))}
        </div>
      </div>

      <div>
        <Label className="mb-2 block text-xs font-semibold uppercase text-muted-foreground">Location</Label>
        <div className="space-y-2">
          <Input
            placeholder="City"
            value={filters.city ?? ""}
            onChange={(e) => onChange({ ...filters, city: e.target.value || undefined })}
          />
          <Input
            placeholder="State"
            value={filters.state ?? ""}
            onChange={(e) => onChange({ ...filters, state: e.target.value || undefined })}
          />
          <Input
            placeholder="Country"
            value={filters.country ?? ""}
            onChange={(e) => onChange({ ...filters, country: e.target.value || undefined })}
          />
        </div>
      </div>

      <div>
        <Label className="mb-2 block text-xs font-semibold uppercase text-muted-foreground">Domain</Label>
        <TagInput
          value={filters.domain || []}
          onChange={(v) => onChange({ ...filters, domain: v })}
          placeholder="e.g. Fintech"
        />
      </div>

      <div>
        <Label className="mb-2 block text-xs font-semibold uppercase text-muted-foreground">Skills</Label>
        <TagInput
          value={filters.skills || []}
          onChange={(v) => onChange({ ...filters, skills: v })}
          placeholder="e.g. React"
        />
      </div>

      <div>
        <Label className="mb-2 block text-xs font-semibold uppercase text-muted-foreground">
          Minimum match score
        </Label>
        <Input
          type="number"
          min={0}
          max={100}
          placeholder="e.g. 70"
          value={filters.min_match_score ?? ""}
          onChange={(e) =>
            onChange({ ...filters, min_match_score: e.target.value ? Number(e.target.value) : undefined })
          }
        />
      </div>
    </div>
  );
}

export function countActiveFilters(filters: JobFilters): number {
  let count = 0;
  if (filters.city) count++;
  if (filters.state) count++;
  if (filters.country) count++;
  if (filters.work_mode?.length) count += filters.work_mode.length;
  if (filters.employment_type?.length) count += filters.employment_type.length;
  if (filters.experience_min != null) count++;
  if (filters.experience_max != null) count++;
  if (filters.domain?.length) count += filters.domain.length;
  if (filters.skills?.length) count += filters.skills.length;
  if (filters.salary_min != null) count++;
  if (filters.posted_within_days != null) count++;
  if (filters.min_match_score != null) count++;
  return count;
}
