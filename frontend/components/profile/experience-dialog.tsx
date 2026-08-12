"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { TagInput } from "@/components/tag-input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import type { Experience, ExperienceInput } from "@/lib/types";

export function ExperienceDialog({
  open,
  onOpenChange,
  initial,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial?: Experience | null;
  onSubmit: (data: ExperienceInput) => Promise<void>;
}) {
  const [company, setCompany] = React.useState("");
  const [designation, setDesignation] = React.useState("");
  const [startDate, setStartDate] = React.useState("");
  const [endDate, setEndDate] = React.useState("");
  const [isCurrent, setIsCurrent] = React.useState(false);
  const [responsibilities, setResponsibilities] = React.useState<string[]>([]);
  const [technologies, setTechnologies] = React.useState<string[]>([]);
  const [domain, setDomain] = React.useState<string[]>([]);
  const [achievements, setAchievements] = React.useState<string[]>([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setCompany(initial?.company || "");
      setDesignation(initial?.designation || "");
      setStartDate(initial?.start_date?.slice(0, 10) || "");
      setEndDate(initial?.end_date?.slice(0, 10) || "");
      setIsCurrent(initial?.is_current || false);
      setResponsibilities(initial?.responsibilities || []);
      setTechnologies(initial?.technologies || []);
      setDomain(initial?.domain || []);
      setAchievements(initial?.achievements || []);
      setError(null);
    }
  }, [open, initial]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!company.trim() || !designation.trim()) {
      setError("Company and title are required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        company: company.trim(),
        designation: designation.trim(),
        start_date: startDate || null,
        end_date: isCurrent ? null : endDate || null,
        is_current: isCurrent,
        responsibilities,
        technologies,
        domain,
        achievements,
      });
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save experience.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{initial ? "Edit experience" : "Add experience"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="exp-company">Company</Label>
              <Input id="exp-company" value={company} onChange={(e) => setCompany(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="exp-title">Title</Label>
              <Input id="exp-title" value={designation} onChange={(e) => setDesignation(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="exp-start">Start date</Label>
              <Input id="exp-start" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="exp-end">End date</Label>
              <Input
                id="exp-end"
                type="date"
                value={endDate}
                disabled={isCurrent}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={isCurrent} onCheckedChange={setIsCurrent} id="exp-current" />
            <Label htmlFor="exp-current">I currently work here</Label>
          </div>
          <div className="space-y-1.5">
            <Label>Domain</Label>
            <TagInput value={domain} onChange={setDomain} placeholder="e.g. Fintech — press Enter" />
          </div>
          <div className="space-y-1.5">
            <Label>Responsibilities</Label>
            <TagInput
              value={responsibilities}
              onChange={setResponsibilities}
              placeholder="Add a responsibility and press Enter"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Technologies</Label>
            <TagInput value={technologies} onChange={setTechnologies} placeholder="Add and press Enter" />
          </div>
          <div className="space-y-1.5">
            <Label>Achievements</Label>
            <TagInput value={achievements} onChange={setAchievements} placeholder="Add and press Enter" />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="submit" disabled={saving} className="gap-2">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
