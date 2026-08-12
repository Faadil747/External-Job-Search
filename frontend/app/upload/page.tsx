"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle2, FileText, Loader2, UploadCloud, X } from "lucide-react";

import { RouteGuard } from "@/components/route-guard";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ApiError, candidateApi } from "@/lib/api";
import { uploadResumeWithProgress } from "@/lib/upload-resume";
import { cn } from "@/lib/utils";
import type { ResumeUploadResponse } from "@/lib/types";

const ACCEPTED_EXTENSIONS = [".pdf", ".doc", ".docx", ".txt"];
const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10MB

const PROCESSING_STAGES = [
  "Extracting Text",
  "Analyzing Experience",
  "Extracting Skills",
  "Generating Candidate Profile",
];

type FlowState = "idle" | "uploading" | "processing" | "error";

function validateFile(file: File): string | null {
  const lower = file.name.toLowerCase();
  const hasValidExt = ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
  if (!hasValidExt) {
    return "Please upload a PDF, DOC, DOCX, or TXT file.";
  }
  if (file.size > MAX_SIZE_BYTES) {
    return "File is too large. Please keep it under 10MB.";
  }
  if (file.size === 0) {
    return "This file appears to be empty.";
  }
  return null;
}

export default function UploadPage() {
  return (
    <RouteGuard>
      <UploadFlow />
    </RouteGuard>
  );
}

function UploadFlow() {
  const router = useRouter();
  const [file, setFile] = React.useState<File | null>(null);
  const [validationError, setValidationError] = React.useState<string | null>(null);
  const [isDragging, setIsDragging] = React.useState(false);
  const [state, setState] = React.useState<FlowState>("idle");
  const [uploadPct, setUploadPct] = React.useState(0);
  const [stageIndex, setStageIndex] = React.useState(0);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const pollTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const stageIntervalRef = React.useRef<ReturnType<typeof setInterval> | null>(null);
  // Tracks whether we've already transitioned into the "processing" screen for
  // the in-flight upload. Using a ref (not the `state` variable) matters here:
  // handleUpload is a long-lived async closure, so `state` inside it stays
  // frozen at whatever it was when the function was invoked ("idle") and never
  // reflects the setState("processing") calls that happen along the way. A
  // check like `state !== "processing"` against that stale value was always
  // true, so the code re-entered the "start processing" branch a second time
  // on every upload -- calling startStageCycle() again, leaking the first
  // interval (its id was overwritten before ever being cleared), and visibly
  // snapping the stage list back to step 1.
  const enteredProcessingRef = React.useRef(false);

  React.useEffect(() => {
    return () => {
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
      if (stageIntervalRef.current) clearInterval(stageIntervalRef.current);
    };
  }, []);

  function pickFile(f: File | null) {
    if (!f) return;
    const err = validateFile(f);
    setValidationError(err);
    setFile(err ? null : f);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) pickFile(dropped);
  }

  function startStageCycle() {
    // Idempotent: always clear any interval already running before starting a
    // new one, so a duplicate call (e.g. a second onprogress event at 100%)
    // can never leak a timer or reset progress out from under an active cycle.
    stopStageCycle();
    setStageIndex(0);
    stageIntervalRef.current = setInterval(() => {
      setStageIndex((i) => (i + 1) % PROCESSING_STAGES.length);
    }, 2200);
  }

  function stopStageCycle() {
    if (stageIntervalRef.current) {
      clearInterval(stageIntervalRef.current);
      stageIntervalRef.current = null;
    }
  }

  async function pollStatus(resumeId: string, attemptsLeft: number) {
    if (attemptsLeft <= 0) {
      stopStageCycle();
      setState("error");
      setErrorMessage(
        "This is taking longer than expected. Your resume may still be processing — check back on the analysis page shortly, or try again."
      );
      return;
    }
    try {
      const status = await candidateApi.resumeStatus(resumeId);
      if (status.processing_status === "completed") {
        stopStageCycle();
        router.push("/resume-analysis");
        return;
      }
      if (status.processing_status === "failed") {
        stopStageCycle();
        setState("error");
        setErrorMessage(
          status.error_message ||
            "AI analysis is temporarily unavailable. Please try again in a few minutes."
        );
        return;
      }
      pollTimeoutRef.current = setTimeout(() => pollStatus(resumeId, attemptsLeft - 1), 3000);
    } catch (err) {
      stopStageCycle();
      setState("error");
      setErrorMessage(describeError(err));
    }
  }

  function enterProcessing() {
    if (enteredProcessingRef.current) return;
    enteredProcessingRef.current = true;
    setState("processing");
    startStageCycle();
  }

  async function handleUpload() {
    if (!file) return;
    enteredProcessingRef.current = false;
    setState("uploading");
    setUploadPct(0);
    setErrorMessage(null);

    try {
      const result: ResumeUploadResponse = await uploadResumeWithProgress(file, (pct) => {
        setUploadPct(pct);
        if (pct >= 100) {
          enterProcessing();
        }
      });

      if (result.processing_status === "completed") {
        stopStageCycle();
        router.push("/resume-analysis");
        return;
      }
      if (result.processing_status === "failed") {
        stopStageCycle();
        setState("error");
        setErrorMessage("AI analysis is temporarily unavailable. Please try again in a few minutes.");
        return;
      }

      // Still processing server-side — poll for completion.
      enterProcessing();
      pollTimeoutRef.current = setTimeout(() => pollStatus(result.id, 40), 3000);
    } catch (err) {
      stopStageCycle();
      setState("error");
      setErrorMessage(describeError(err));
    }
  }

  function reset() {
    stopStageCycle();
    if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    enteredProcessingRef.current = false;
    setFile(null);
    setValidationError(null);
    setState("idle");
    setUploadPct(0);
    setErrorMessage(null);
  }

  return (
    <div className="container max-w-2xl py-12">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Upload your resume</h1>
        <p className="mt-2 text-muted-foreground">
          We&apos;ll extract your experience, skills, and generate an AI match report.
        </p>
      </div>

      {state === "idle" && (
        <Card>
          <CardContent className="pt-6">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              className={cn(
                "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition-colors",
                isDragging ? "border-primary bg-primary-50" : "border-border hover:bg-muted/50"
              )}
            >
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary-100 text-primary">
                <UploadCloud className="h-6 w-6" />
              </div>
              <p className="font-medium text-foreground">
                Drag &amp; drop your resume here, or click to browse
              </p>
              <p className="mt-1 text-sm text-muted-foreground">PDF, DOC, DOCX, or TXT — up to 10MB</p>
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                className="hidden"
                onChange={(e) => pickFile(e.target.files?.[0] || null)}
              />
            </div>

            {validationError && (
              <p className="mt-4 flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" /> {validationError}
              </p>
            )}

            {file && !validationError && (
              <div className="mt-4 flex items-center justify-between rounded-xl border border-border bg-muted/40 px-4 py-3">
                <div className="flex items-center gap-3">
                  <FileText className="h-5 w-5 text-primary" />
                  <div>
                    <p className="text-sm font-medium text-foreground">{file.name}</p>
                    <p className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(0)} KB</p>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                  }}
                  className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted"
                  aria-label="Remove file"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            <Button className="mt-6 w-full" size="lg" disabled={!file} onClick={handleUpload}>
              Analyze My Resume
            </Button>
          </CardContent>
        </Card>
      )}

      {state === "uploading" && (
        <Card>
          <CardHeader>
            <CardTitle>Uploading your resume…</CardTitle>
            <CardDescription>{file?.name}</CardDescription>
          </CardHeader>
          <CardContent>
            <Progress value={uploadPct} />
            <p className="mt-2 text-right text-sm text-muted-foreground">{uploadPct}%</p>
          </CardContent>
        </Card>
      )}

      {state === "processing" && (
        <Card>
          <CardHeader>
            <CardTitle>Analyzing your resume</CardTitle>
            <CardDescription>
              Our AI is reading your resume like a recruiter would. This usually takes under a minute.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {PROCESSING_STAGES.map((stage, i) => {
                const isActive = i === stageIndex;
                const isDone = i < stageIndex;
                return (
                  <li
                    key={stage}
                    className={cn(
                      "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                      isActive && "bg-primary-50 text-primary font-medium",
                      !isActive && "text-muted-foreground"
                    )}
                  >
                    {isActive ? (
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
                    ) : isDone ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                    ) : (
                      <span className="h-4 w-4 shrink-0 rounded-full border border-border" />
                    )}
                    {stage}
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}

      {state === "error" && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <CardTitle className="text-destructive">Something went wrong</CardTitle>
            </div>
            <CardDescription>{errorMessage}</CardDescription>
          </CardHeader>
          <CardContent className="flex gap-3">
            <Button onClick={handleUpload} disabled={!file}>
              Retry
            </Button>
            <Button variant="outline" onClick={reset}>
              Choose a different file
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 503) {
      return "AI analysis is temporarily unavailable. Please try again in a few minutes.";
    }
    if (err.status === 413) {
      return "File is too large for the server to accept. Please upload a smaller file.";
    }
    if (err.status === 0) {
      return err.message;
    }
    return err.message || "Upload failed. Please try again.";
  }
  return "Something unexpected happened. Please try again.";
}
