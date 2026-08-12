"use client";

import * as React from "react";
import { Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { TagInput } from "@/components/tag-input";
import type { Preferences } from "@/lib/types";

const WORK_MODES = ["remote", "hybrid", "onsite"];
const EMPLOYMENT_TYPES = ["full_time", "part_time", "contract", "internship"];

const DEFAULT_PREFERENCES: Preferences = {
  preferred_roles: [],
  preferred_locations: [],
  preferred_domains: [],
  salary_min: null,
  salary_max: null,
  currency: "INR",
  work_mode: [],
  employment_type: [],
  min_match_score: null,
  willing_to_relocate: false,
  notice_period_days: null,
};

export function PreferencesForm({
  initial,
  onSave,
}: {
  initial: Preferences | null;
  onSave: (data: Preferences) => Promise<void>;
}) {
  const [prefs, setPrefs] = React.useState<Preferences>(initial || DEFAULT_PREFERENCES);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [saved, setSaved] = React.useState(false);

  React.useEffect(() => {
    setPrefs(initial || DEFAULT_PREFERENCES);
  }, [initial]);

  function toggleListValue(list: string[], value: string): string[] {
    return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await onSave(prefs);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preferences.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-1.5">
        <Label>Preferred roles</Label>
        <TagInput
          value={prefs.preferred_roles}
          onChange={(v) => setPrefs((p) => ({ ...p, preferred_roles: v }))}
          placeholder="e.g. Backend Engineer"
        />
      </div>

      <div className="space-y-1.5">
        <Label>Preferred locations</Label>
        <TagInput
          value={prefs.preferred_locations}
          onChange={(v) => setPrefs((p) => ({ ...p, preferred_locations: v }))}
          placeholder="e.g. Bengaluru, Remote"
        />
      </div>

      <div className="space-y-1.5">
        <Label>Preferred domains</Label>
        <TagInput
          value={prefs.preferred_domains}
          onChange={(v) => setPrefs((p) => ({ ...p, preferred_domains: v }))}
          placeholder="e.g. Fintech, Healthtech"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="salary-min">Min salary</Label>
          <Input
            id="salary-min"
            type="number"
            value={prefs.salary_min ?? ""}
            onChange={(e) =>
              setPrefs((p) => ({ ...p, salary_min: e.target.value ? Number(e.target.value) : null }))
            }
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="salary-max">Max salary</Label>
          <Input
            id="salary-max"
            type="number"
            value={prefs.salary_max ?? ""}
            onChange={(e) =>
              setPrefs((p) => ({ ...p, salary_max: e.target.value ? Number(e.target.value) : null }))
            }
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="currency">Currency</Label>
          <Input
            id="currency"
            value={prefs.currency ?? ""}
            onChange={(e) => setPrefs((p) => ({ ...p, currency: e.target.value }))}
            placeholder="INR"
          />
        </div>
      </div>

      <div>
        <Label className="mb-2 block">Work mode</Label>
        <div className="flex flex-wrap gap-4">
          {WORK_MODES.map((mode) => (
            <label key={mode} className="flex items-center gap-2 text-sm capitalize">
              <Checkbox
                checked={prefs.work_mode.includes(mode)}
                onCheckedChange={() =>
                  setPrefs((p) => ({ ...p, work_mode: toggleListValue(p.work_mode, mode) }))
                }
              />
              {mode}
            </label>
          ))}
        </div>
      </div>

      <div>
        <Label className="mb-2 block">Employment type</Label>
        <div className="flex flex-wrap gap-4">
          {EMPLOYMENT_TYPES.map((type) => (
            <label key={type} className="flex items-center gap-2 text-sm capitalize">
              <Checkbox
                checked={prefs.employment_type.includes(type)}
                onCheckedChange={() =>
                  setPrefs((p) => ({ ...p, employment_type: toggleListValue(p.employment_type, type) }))
                }
              />
              {type.replace("_", " ")}
            </label>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="min-match">Minimum match score to show me</Label>
          <Input
            id="min-match"
            type="number"
            min={0}
            max={100}
            value={prefs.min_match_score ?? ""}
            onChange={(e) =>
              setPrefs((p) => ({ ...p, min_match_score: e.target.value ? Number(e.target.value) : null }))
            }
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="notice-period">Notice period (days)</Label>
          <Input
            id="notice-period"
            type="number"
            min={0}
            value={prefs.notice_period_days ?? ""}
            onChange={(e) =>
              setPrefs((p) => ({ ...p, notice_period_days: e.target.value ? Number(e.target.value) : null }))
            }
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Switch
          id="relocate"
          checked={prefs.willing_to_relocate}
          onCheckedChange={(checked) => setPrefs((p) => ({ ...p, willing_to_relocate: checked }))}
        />
        <Label htmlFor="relocate">Willing to relocate</Label>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving} className="gap-2">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save preferences
        </Button>
        {saved && <span className="text-sm text-success">Saved</span>}
      </div>
    </form>
  );
}
