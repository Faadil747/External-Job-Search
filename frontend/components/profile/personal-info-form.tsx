"use client";

import * as React from "react";
import { Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { CandidateProfile, CandidateProfileUpdate } from "@/lib/types";

export function PersonalInfoForm({
  profile,
  onSave,
}: {
  profile: CandidateProfile;
  onSave: (data: CandidateProfileUpdate) => Promise<void>;
}) {
  const [form, setForm] = React.useState<CandidateProfileUpdate>({
    full_name: profile.full_name || "",
    phone: profile.phone || "",
    linkedin_url: profile.linkedin_url || "",
    portfolio_url: profile.portfolio_url || "",
    github_url: profile.github_url || "",
    current_area: profile.current_area || "",
    current_city: profile.current_city || "",
    current_state: profile.current_state || "",
    current_country: profile.current_country || "",
    professional_summary: profile.professional_summary || "",
  });
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [saved, setSaved] = React.useState(false);

  function set<K extends keyof CandidateProfileUpdate>(key: K, value: CandidateProfileUpdate[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await onSave(form);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="full_name">Full name</Label>
          <Input id="full_name" value={form.full_name || ""} onChange={(e) => set("full_name", e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="phone">Phone</Label>
          <Input id="phone" value={form.phone || ""} onChange={(e) => set("phone", e.target.value)} />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="linkedin_url">LinkedIn URL</Label>
          <Input id="linkedin_url" value={form.linkedin_url || ""} onChange={(e) => set("linkedin_url", e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="github_url">GitHub URL</Label>
          <Input id="github_url" value={form.github_url || ""} onChange={(e) => set("github_url", e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="portfolio_url">Portfolio URL</Label>
          <Input id="portfolio_url" value={form.portfolio_url || ""} onChange={(e) => set("portfolio_url", e.target.value)} />
        </div>
      </div>

      <div>
        <Label className="mb-2 block text-sm text-muted-foreground">Current location</Label>
        <div className="grid gap-4 sm:grid-cols-4">
          <Input placeholder="Area" value={form.current_area || ""} onChange={(e) => set("current_area", e.target.value)} />
          <Input placeholder="City" value={form.current_city || ""} onChange={(e) => set("current_city", e.target.value)} />
          <Input placeholder="State" value={form.current_state || ""} onChange={(e) => set("current_state", e.target.value)} />
          <Input placeholder="Country" value={form.current_country || ""} onChange={(e) => set("current_country", e.target.value)} />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="summary">Professional summary</Label>
        <Textarea
          id="summary"
          rows={4}
          value={form.professional_summary || ""}
          onChange={(e) => set("professional_summary", e.target.value)}
          placeholder="A short summary of your professional background."
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving} className="gap-2">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save changes
        </Button>
        {saved && <span className="text-sm text-success">Saved</span>}
      </div>
    </form>
  );
}
