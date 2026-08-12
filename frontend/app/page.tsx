import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  Bookmark,
  MapPin,
  Sparkles,
  UploadCloud,
  Wand2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MatchBadge } from "@/components/match-badge";

export default function LandingPage() {
  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_20%_-10%,hsl(var(--primary-100)),transparent_45%),radial-gradient(circle_at_100%_10%,hsl(var(--primary-50)),transparent_40%)]" />
        <div className="container flex flex-col items-center gap-6 py-20 text-center sm:py-28">
          <Badge className="gap-1.5 px-3 py-1">
            <Sparkles className="h-3.5 w-3.5" /> AI-powered resume-to-job matching
          </Badge>
          <h1 className="max-w-3xl text-4xl font-bold tracking-tight text-foreground sm:text-6xl">
            Your Resume. Your{" "}
            <span className="text-primary">Best-Matched</span> Jobs.
          </h1>
          <p className="max-w-xl text-balance text-lg text-muted-foreground">
            Upload your resume once. Our AI reads it like a recruiter would, then
            continuously matches you against fresh roles sourced from trusted job
            boards — ranked, explained, and ready to apply to.
          </p>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row">
            <Button asChild size="lg" className="gap-2">
              <Link href="/upload">
                <UploadCloud className="h-4 w-4" /> Upload Resume
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="gap-2">
              <Link href="/jobs">
                Explore Jobs <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            No spam. No fake postings. Every job links back to its original, verifiable source.
          </p>
        </div>
      </section>

      {/* Marketing preview — static mock, not live data */}
      <section className="container pb-24">
        <div className="mb-6 flex items-center justify-center gap-2">
          <p className="text-center text-sm font-medium uppercase tracking-wide text-muted-foreground">
            Example preview
          </p>
          <Badge variant="secondary" className="text-[10px]">Illustrative — not live data</Badge>
        </div>

        <div className="mx-auto grid max-w-5xl gap-6 lg:grid-cols-[minmax(0,320px)_1fr]">
          {/* Mock candidate profile card */}
          <div className="rounded-2xl border border-border bg-card p-6 shadow-soft-lg">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-lg font-semibold text-primary-foreground">
                AS
              </div>
              <div>
                <p className="font-semibold text-foreground">Aisha Sharma</p>
                <p className="text-sm text-muted-foreground">Backend Engineer, 4 yrs</p>
              </div>
            </div>

            <div className="mt-6 flex flex-col items-center rounded-xl bg-primary-50 py-5">
              <span className="text-4xl font-bold text-primary">87</span>
              <span className="text-xs font-medium text-muted-foreground">
                AI Resume Score / 100
              </span>
            </div>

            <div className="mt-5 space-y-2 text-sm">
              <div className="flex items-center gap-2 text-foreground">
                <BadgeCheck className="h-4 w-4 text-success" /> Strong system-design depth
              </div>
              <div className="flex items-center gap-2 text-foreground">
                <BadgeCheck className="h-4 w-4 text-success" /> Clear quantified impact
              </div>
              <div className="flex items-center gap-2 text-foreground">
                <BadgeCheck className="h-4 w-4 text-success" /> Consistent career trajectory
              </div>
            </div>
          </div>

          {/* Mock job card */}
          <div className="flex flex-col justify-center rounded-2xl border border-border bg-card p-6 shadow-soft-lg">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-indigo-500 text-sm font-semibold text-white">
                  NX
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Nexora Systems</p>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3" /> Bengaluru, India · Hybrid
                  </div>
                </div>
              </div>
              <Bookmark className="h-4 w-4 text-primary" />
            </div>

            <h3 className="mt-3 text-lg font-semibold text-foreground">
              Senior Backend Engineer — Payments
            </h3>
            <p className="clamp-2 mt-1 text-sm text-muted-foreground">
              Own the core ledger service, design idempotent payment APIs, and mentor a
              team of four engineers shipping to millions of merchants.
            </p>

            <div className="mt-3 flex flex-wrap gap-1.5">
              <Badge variant="outline">Full Time</Badge>
              <Badge variant="outline">Mid-Senior</Badge>
              <Badge variant="outline">Hybrid</Badge>
            </div>

            <div className="mt-4 rounded-xl bg-primary-50 p-3">
              <div className="flex items-center justify-between">
                <MatchBadge score={92} category="excellent" />
                <span className="text-xs text-muted-foreground">2d ago</span>
              </div>
              <p className="mt-1.5 flex items-start gap-1 text-xs text-foreground/80">
                <Wand2 className="mt-0.5 h-3 w-3 shrink-0 text-primary" />
                Matches your Go + distributed-systems background and 4 years in fintech.
              </p>
            </div>

            <div className="mt-4 flex gap-2">
              <Button variant="outline" size="sm" className="flex-1" disabled>
                Details
              </Button>
              <Button variant="secondary" size="sm" className="flex-1" disabled>
                Apply Now
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-border bg-muted/40 py-20">
        <div className="container">
          <h2 className="text-center text-2xl font-bold text-foreground sm:text-3xl">
            How JobMatch AI works
          </h2>
          <div className="mt-12 grid gap-8 sm:grid-cols-3">
            {[
              {
                title: "1. Upload your resume",
                desc: "PDF, Word, or plain text — our AI extracts skills, experience, and career trajectory in seconds.",
              },
              {
                title: "2. Get an AI report card",
                desc: "A transparent score breakdown, your strengths, and ranked role recommendations with tier labels.",
              },
              {
                title: "3. Apply with confidence",
                desc: "See exactly why each job matches — skills, experience, location, domain — before you click apply.",
              },
            ].map((step) => (
              <div key={step.title} className="rounded-2xl border border-border bg-card p-6 shadow-soft">
                <h3 className="font-semibold text-foreground">{step.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="container flex flex-col items-center gap-4 py-20 text-center">
        <h2 className="text-2xl font-bold text-foreground sm:text-3xl">
          Ready to see your matches?
        </h2>
        <p className="max-w-md text-muted-foreground">
          It takes under two minutes to upload your resume and get your first AI match report.
        </p>
        <Button asChild size="lg" className="gap-2">
          <Link href="/upload">
            <UploadCloud className="h-4 w-4" /> Upload Resume
          </Link>
        </Button>
      </section>
    </div>
  );
}
