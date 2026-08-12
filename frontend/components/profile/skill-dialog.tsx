"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import type { Skill, SkillInput } from "@/lib/types";

const PROFICIENCY_OPTIONS = ["beginner", "intermediate", "advanced", "expert"];

export function SkillDialog({
  open,
  onOpenChange,
  initial,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial?: Skill | null;
  onSubmit: (data: SkillInput) => Promise<void>;
}) {
  const [name, setName] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [proficiency, setProficiency] = React.useState("intermediate");
  const [months, setMonths] = React.useState<string>("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setName(initial?.name || "");
      setCategory(initial?.category || "");
      setProficiency(initial?.proficiency || "intermediate");
      setMonths(initial?.months_experience != null ? String(initial.months_experience) : "");
      setError(null);
    }
  }, [open, initial]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Skill name is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        name: name.trim(),
        category: category.trim() || null,
        proficiency,
        months_experience: months ? Number(months) : null,
        source: initial?.source || "manual",
      });
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save skill.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{initial ? "Edit skill" : "Add a skill"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="skill-name">Skill name</Label>
            <Input id="skill-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Python" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="skill-category">Category</Label>
              <Input
                id="skill-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="e.g. Programming"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="skill-months">Months experience</Label>
              <Input
                id="skill-months"
                type="number"
                min={0}
                value={months}
                onChange={(e) => setMonths(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="skill-proficiency">Proficiency</Label>
            <select
              id="skill-proficiency"
              value={proficiency}
              onChange={(e) => setProficiency(e.target.value)}
              className="flex h-10 w-full rounded-xl border border-input bg-card px-3.5 py-2 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring"
            >
              {PROFICIENCY_OPTIONS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
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
