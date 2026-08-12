"use client";

import * as React from "react";
import { Briefcase, GraduationCap, Info, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";

import { RouteGuard } from "@/components/route-guard";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { PersonalInfoForm } from "@/components/profile/personal-info-form";
import { PreferencesForm } from "@/components/profile/preferences-form";
import { SkillDialog } from "@/components/profile/skill-dialog";
import { ExperienceDialog } from "@/components/profile/experience-dialog";
import { EducationDialog } from "@/components/profile/education-dialog";
import { ProjectDialog } from "@/components/profile/project-dialog";
import { ApiError, candidateApi } from "@/lib/api";
import { formatDate, titleCase } from "@/lib/utils";
import type {
  CandidateProfile,
  Education,
  EducationInput,
  Experience,
  ExperienceInput,
  Project,
  ProjectInput,
  Skill,
  SkillInput,
} from "@/lib/types";

export default function ProfilePage() {
  return (
    <RouteGuard>
      <ProfileContent />
    </RouteGuard>
  );
}

function ProfileContent() {
  const [profile, setProfile] = React.useState<CandidateProfile | null>(null);
  const [status, setStatus] = React.useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    setStatus("loading");
    candidateApi
      .getProfile()
      .then((data) => {
        setProfile(data);
        setStatus("ready");
      })
      .catch((err) => {
        setErrorMessage(err instanceof ApiError ? err.message : "Failed to load your profile.");
        setStatus("error");
      });
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  if (status === "loading") {
    return (
      <div className="container max-w-4xl space-y-6 py-10">
        <Skeleton className="h-9 w-56" />
        <Skeleton className="h-32 w-full rounded-2xl" />
        <Skeleton className="h-96 w-full rounded-2xl" />
      </div>
    );
  }

  if (status === "error" || !profile) {
    return (
      <div className="container max-w-2xl py-16">
        <ErrorState title="Couldn't load your profile" description={errorMessage || undefined} onRetry={load} />
      </div>
    );
  }

  return (
    <div className="container max-w-4xl space-y-6 py-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">My Profile</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          AI extracted an initial version of your profile from your resume. Anything you edit here is yours —
          future resume re-uploads will never silently overwrite your manual edits.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-6 pt-6">
          <div className="flex-1 min-w-[200px]">
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="font-medium text-foreground">Profile completion</span>
              <span className="text-muted-foreground">{profile.profile_completion_pct}%</span>
            </div>
            <Progress value={profile.profile_completion_pct} />
          </div>
          {profile.resume_score != null && (
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              <span className="text-sm text-muted-foreground">AI resume score</span>
              <Badge>{Math.round(profile.resume_score)}/100</Badge>
            </div>
          )}
          {profile.career_level && (
            <Badge variant="outline">{titleCase(profile.career_level)}</Badge>
          )}
        </CardContent>
      </Card>

      <Tabs defaultValue="personal">
        <TabsList className="flex-wrap">
          <TabsTrigger value="personal">Personal</TabsTrigger>
          <TabsTrigger value="skills">Skills</TabsTrigger>
          <TabsTrigger value="experience">Experience</TabsTrigger>
          <TabsTrigger value="education">Education</TabsTrigger>
          <TabsTrigger value="projects">Projects</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
        </TabsList>

        <TabsContent value="personal">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Personal information</CardTitle>
              <CardDescription>Your contact details, links, and summary.</CardDescription>
            </CardHeader>
            <CardContent>
              <PersonalInfoForm
                profile={profile}
                onSave={async (data) => {
                  const updated = await candidateApi.updateProfile(data);
                  setProfile(updated);
                }}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="skills">
          <SkillsSection profile={profile} setProfile={setProfile} />
        </TabsContent>

        <TabsContent value="experience">
          <ExperienceSection profile={profile} setProfile={setProfile} />
        </TabsContent>

        <TabsContent value="education">
          <EducationSection profile={profile} setProfile={setProfile} />
        </TabsContent>

        <TabsContent value="projects">
          <ProjectsSection profile={profile} setProfile={setProfile} />
        </TabsContent>

        <TabsContent value="preferences">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Job preferences</CardTitle>
              <CardDescription>Used to prioritize and filter your recommended jobs.</CardDescription>
            </CardHeader>
            <CardContent>
              <PreferencesForm
                initial={profile.preferences}
                onSave={async (data) => {
                  const updated = await candidateApi.updatePreferences(data);
                  setProfile((p) => (p ? { ...p, preferences: updated } : p));
                }}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

type ProfileSetter = React.Dispatch<React.SetStateAction<CandidateProfile | null>>;

function SkillsSection({ profile, setProfile }: { profile: CandidateProfile; setProfile: ProfileSetter }) {
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Skill | null>(null);

  async function handleSubmit(data: SkillInput) {
    if (editing) {
      const updated = await candidateApi.updateSkill(editing.id, data);
      setProfile((p) => (p ? { ...p, skills: p.skills.map((s) => (s.id === updated.id ? updated : s)) } : p));
    } else {
      const created = await candidateApi.addSkill(data);
      setProfile((p) => (p ? { ...p, skills: [...p.skills, created] } : p));
    }
  }

  async function handleDelete(id: string) {
    await candidateApi.deleteSkill(id);
    setProfile((p) => (p ? { ...p, skills: p.skills.filter((s) => s.id !== id) } : p));
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-base">Skills</CardTitle>
          <CardDescription>AI-extracted and manually added skills.</CardDescription>
        </div>
        <Button
          size="sm"
          className="gap-1.5"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
        >
          <Plus className="h-4 w-4" /> Add skill
        </Button>
      </CardHeader>
      <CardContent>
        {profile.skills.length === 0 ? (
          <EmptyState title="No skills yet" description="Add skills manually or upload a resume to auto-extract them." />
        ) : (
          <div className="flex flex-wrap gap-2">
            {profile.skills.map((skill) => (
              <div
                key={skill.id}
                className="group flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-1.5 text-sm"
              >
                <span className="font-medium text-foreground">{skill.name}</span>
                {skill.proficiency && (
                  <span className="text-xs text-muted-foreground">{skill.proficiency}</span>
                )}
                {skill.source === "ai" && (
                  <Sparkles className="h-3 w-3 text-primary" aria-label="AI-extracted" />
                )}
                <button
                  onClick={() => {
                    setEditing(skill);
                    setDialogOpen(true);
                  }}
                  className="text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
                  aria-label={`Edit ${skill.name}`}
                >
                  <Pencil className="h-3 w-3" />
                </button>
                <button
                  onClick={() => handleDelete(skill.id)}
                  className="text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                  aria-label={`Delete ${skill.name}`}
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
      <SkillDialog open={dialogOpen} onOpenChange={setDialogOpen} initial={editing} onSubmit={handleSubmit} />
    </Card>
  );
}

function ExperienceSection({ profile, setProfile }: { profile: CandidateProfile; setProfile: ProfileSetter }) {
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Experience | null>(null);

  async function handleSubmit(data: ExperienceInput) {
    if (editing) {
      const updated = await candidateApi.updateExperience(editing.id, data);
      setProfile((p) => (p ? { ...p, experience: p.experience.map((e) => (e.id === updated.id ? updated : e)) } : p));
    } else {
      const created = await candidateApi.addExperience(data);
      setProfile((p) => (p ? { ...p, experience: [...p.experience, created] } : p));
    }
  }

  async function handleDelete(id: string) {
    await candidateApi.deleteExperience(id);
    setProfile((p) => (p ? { ...p, experience: p.experience.filter((e) => e.id !== id) } : p));
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-base">Experience</CardTitle>
          <CardDescription>Your work history.</CardDescription>
        </div>
        <Button
          size="sm"
          className="gap-1.5"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
        >
          <Plus className="h-4 w-4" /> Add experience
        </Button>
      </CardHeader>
      <CardContent>
        {profile.experience.length === 0 ? (
          <EmptyState icon={<Briefcase className="h-5 w-5" />} title="No experience added yet" />
        ) : (
          <div className="space-y-4">
            {profile.experience.map((exp) => (
              <div key={exp.id} className="rounded-xl border border-border p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-semibold text-foreground">{exp.designation}</h3>
                    <p className="text-sm text-muted-foreground">{exp.company}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {formatDate(exp.start_date)} — {exp.is_current ? "Present" : formatDate(exp.end_date) || "—"}
                    </p>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => {
                        setEditing(exp);
                        setDialogOpen(true);
                      }}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => handleDelete(exp.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                {exp.responsibilities && exp.responsibilities.length > 0 && (
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-foreground/90">
                    {exp.responsibilities.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                )}
                {exp.domain && exp.domain.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {exp.domain.map((d) => (
                      <span key={d} className="rounded-full bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary">
                        {d}
                      </span>
                    ))}
                  </div>
                )}
                {exp.technologies && exp.technologies.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {exp.technologies.map((t) => (
                      <span key={t} className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
      <ExperienceDialog open={dialogOpen} onOpenChange={setDialogOpen} initial={editing} onSubmit={handleSubmit} />
    </Card>
  );
}

function EducationSection({ profile, setProfile }: { profile: CandidateProfile; setProfile: ProfileSetter }) {
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Education | null>(null);

  async function handleSubmit(data: EducationInput) {
    if (editing) {
      const updated = await candidateApi.updateEducation(editing.id, data);
      setProfile((p) => (p ? { ...p, education: p.education.map((e) => (e.id === updated.id ? updated : e)) } : p));
    } else {
      const created = await candidateApi.addEducation(data);
      setProfile((p) => (p ? { ...p, education: [...p.education, created] } : p));
    }
  }

  async function handleDelete(id: string) {
    await candidateApi.deleteEducation(id);
    setProfile((p) => (p ? { ...p, education: p.education.filter((e) => e.id !== id) } : p));
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-base">Education</CardTitle>
          <CardDescription>Degrees and certifications.</CardDescription>
        </div>
        <Button
          size="sm"
          className="gap-1.5"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
        >
          <Plus className="h-4 w-4" /> Add education
        </Button>
      </CardHeader>
      <CardContent>
        {profile.education.length === 0 ? (
          <EmptyState icon={<GraduationCap className="h-5 w-5" />} title="No education added yet" />
        ) : (
          <div className="space-y-4">
            {profile.education.map((edu) => (
              <div key={edu.id} className="rounded-xl border border-border p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-semibold text-foreground">{edu.degree}</h3>
                    <p className="text-sm text-muted-foreground">
                      {edu.institution} {edu.field ? `· ${edu.field}` : ""}
                    </p>
                    {edu.graduation_year && (
                      <p className="mt-0.5 text-xs text-muted-foreground">Class of {edu.graduation_year}</p>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => {
                        setEditing(edu);
                        setDialogOpen(true);
                      }}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => handleDelete(edu.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                {edu.certifications && edu.certifications.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {edu.certifications.map((c) => (
                      <span key={c} className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        {c}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
      <EducationDialog open={dialogOpen} onOpenChange={setDialogOpen} initial={editing} onSubmit={handleSubmit} />
    </Card>
  );
}

function ProjectsSection({ profile, setProfile }: { profile: CandidateProfile; setProfile: ProfileSetter }) {
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Project | null>(null);

  async function handleSubmit(data: ProjectInput) {
    if (editing) {
      const updated = await candidateApi.updateProject(editing.id, data);
      setProfile((p) => (p ? { ...p, projects: p.projects.map((e) => (e.id === updated.id ? updated : e)) } : p));
    } else {
      const created = await candidateApi.addProject(data);
      setProfile((p) => (p ? { ...p, projects: [...p.projects, created] } : p));
    }
  }

  async function handleDelete(id: string) {
    await candidateApi.deleteProject(id);
    setProfile((p) => (p ? { ...p, projects: p.projects.filter((e) => e.id !== id) } : p));
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-base">Projects</CardTitle>
          <CardDescription>Notable projects that showcase your work.</CardDescription>
        </div>
        <Button
          size="sm"
          className="gap-1.5"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
        >
          <Plus className="h-4 w-4" /> Add project
        </Button>
      </CardHeader>
      <CardContent>
        {profile.projects.length === 0 ? (
          <EmptyState icon={<Info className="h-5 w-5" />} title="No projects added yet" />
        ) : (
          <div className="space-y-4">
            {profile.projects.map((proj) => (
              <div key={proj.id} className="rounded-xl border border-border p-4">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-semibold text-foreground">{proj.name}</h3>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => {
                        setEditing(proj);
                        setDialogOpen(true);
                      }}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => handleDelete(proj.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                {proj.description && <p className="mt-1 text-sm text-foreground/90">{proj.description}</p>}
                {proj.domain && proj.domain.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {proj.domain.map((d) => (
                      <span key={d} className="rounded-full bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary">
                        {d}
                      </span>
                    ))}
                  </div>
                )}
                {proj.technologies && proj.technologies.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {proj.technologies.map((t) => (
                      <span key={t} className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
      <ProjectDialog open={dialogOpen} onOpenChange={setDialogOpen} initial={editing} onSubmit={handleSubmit} />
    </Card>
  );
}
