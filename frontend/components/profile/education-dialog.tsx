"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TagInput } from "@/components/tag-input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import type { Education, EducationInput } from "@/lib/types";

export function EducationDialog({
  open,
  onOpenChange,
  initial,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial?: Education | null;
  onSubmit: (data: EducationInput) => Promise<void>;
}) {
  const [degree, setDegree] = React.useState("");
  const [institution, setInstitution] = React.useState("");
  const [field, setField] = React.useState("");
  const [gradYear, setGradYear] = React.useState("");
  const [certifications, setCertifications] = React.useState<string[]>([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setDegree(initial?.degree || "");
      setInstitution(initial?.institution || "");
      setField(initial?.field || "");
      setGradYear(initial?.graduation_year != null ? String(initial.graduation_year) : "");
      setCertifications(initial?.certifications || []);
      setError(null);
    }
  }, [open, initial]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!degree.trim() || !institution.trim()) {
      setError("Degree and institution are required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        degree: degree.trim(),
        institution: institution.trim(),
        field: field || null,
        graduation_year: gradYear ? Number(gradYear) : null,
        certifications,
      });
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save education.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{initial ? "Edit education" : "Add education"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="edu-degree">Degree</Label>
            <Input id="edu-degree" value={degree} onChange={(e) => setDegree(e.target.value)} placeholder="e.g. B.Tech" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edu-institution">Institution</Label>
            <Input id="edu-institution" value={institution} onChange={(e) => setInstitution(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="edu-field">Field of study</Label>
              <Input id="edu-field" value={field} onChange={(e) => setField(e.target.value)} placeholder="e.g. Computer Science" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edu-year">Graduation year</Label>
              <Input id="edu-year" type="number" value={gradYear} onChange={(e) => setGradYear(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Certifications</Label>
            <TagInput value={certifications} onChange={setCertifications} placeholder="Add and press Enter" />
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
