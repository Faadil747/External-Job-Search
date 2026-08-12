import {
  clearStoredTokens,
  getStoredAccessToken,
  getStoredRefreshToken,
  storeTokens,
} from "./auth-store";
import type {
  Application,
  ApplicationStatus,
  CandidateProfile,
  CandidateProfileUpdate,
  ChatRequest,
  ChatResponse,
  Education,
  EducationInput,
  EstimatedSalary,
  Experience,
  ExperienceInput,
  JobCard,
  JobDetail,
  JobFeedbackAction,
  JobFeedResponse,
  JobSearchRequest,
  Preferences,
  Project,
  ProjectInput,
  ResumeAnalysis,
  ResumeStatusResponse,
  ResumeUploadResponse,
  SavedJob,
  Skill,
  SkillInput,
  TokenPair,
  UserPublic,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
  /** Provide when the body is FormData (skips JSON.stringify + content-type). */
  isFormData?: boolean;
}

let refreshPromise: Promise<string | null> | null = null;

/** Exported so callers outside `request()` (e.g. the raw-XHR resume upload,
 * which needs upload progress events fetch() can't provide) can perform the
 * same silent refresh-and-retry on a 401 instead of forcing the user to log
 * in again for what's just an expired access token. */
export async function tryRefreshToken(): Promise<string | null> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) return null;

  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (res) => {
        if (!res.ok) return null;
        const data: TokenPair = await res.json();
        storeTokens(data.access_token, data.refresh_token);
        return data.access_token;
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

function extractErrorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    if (typeof b.detail === "string") return b.detail;
    if (Array.isArray(b.detail)) {
      const first = b.detail[0];
      if (first && typeof first === "object" && "msg" in first) {
        return String((first as Record<string, unknown>).msg);
      }
    }
    if (typeof b.message === "string") return b.message;
  }
  return fallback;
}

async function request<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, auth = false, signal, isFormData } = options;

  const headers: Record<string, string> = {};
  if (!isFormData) headers["Content-Type"] = "application/json";

  if (auth) {
    const token = getStoredAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const doFetch = () =>
    fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isFormData ? (body as FormData) : JSON.stringify(body),
      signal,
    });

  let res: Response;
  try {
    res = await doFetch();
  } catch (err) {
    throw new ApiError(
      "Unable to reach the server. Please check your connection and try again.",
      0,
      err
    );
  }

  // Attempt a single silent refresh-and-retry on 401 for authenticated calls.
  if (res.status === 401 && auth) {
    const newToken = await tryRefreshToken();
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      try {
        res = await fetch(`${API_BASE_URL}${path}`, {
          method,
          headers,
          body:
            body === undefined
              ? undefined
              : isFormData
              ? (body as FormData)
              : JSON.stringify(body),
          signal,
        });
      } catch (err) {
        throw new ApiError(
          "Unable to reach the server. Please check your connection and try again.",
          0,
          err
        );
      }
    } else {
      clearStoredTokens();
    }
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const contentType = res.headers.get("content-type") || "";
  const parsed = contentType.includes("application/json")
    ? await res.json().catch(() => null)
    : await res.text().catch(() => null);

  if (!res.ok) {
    throw new ApiError(
      extractErrorMessage(parsed, `Request failed (${res.status})`),
      res.status,
      parsed
    );
  }

  return parsed as T;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const authApi = {
  register: (body: { email: string; password: string; full_name?: string }) =>
    request<UserPublic>("/auth/register", { method: "POST", body }),

  login: (body: { email: string; password: string }) =>
    request<TokenPair>("/auth/login", { method: "POST", body }),

  refresh: (refresh_token: string) =>
    request<TokenPair>("/auth/refresh", { method: "POST", body: { refresh_token } }),

  me: () => request<UserPublic>("/auth/me", { auth: true }),
};

// ---------------------------------------------------------------------------
// Candidate profile / resume
// ---------------------------------------------------------------------------

export const candidateApi = {
  uploadResume: (file: File, signal?: AbortSignal) => {
    const form = new FormData();
    form.append("file", file);
    return request<ResumeUploadResponse>("/candidate/resume/upload", {
      method: "POST",
      body: form,
      auth: true,
      isFormData: true,
      signal,
    });
  },

  resumeStatus: (resumeId: string) =>
    request<ResumeStatusResponse>(`/candidate/resume/${resumeId}/status`, {
      auth: true,
    }),

  resumeAnalysis: () =>
    request<ResumeAnalysis>("/candidate/resume/analysis", { auth: true }),

  getProfile: () => request<CandidateProfile>("/candidate/profile", { auth: true }),

  updateProfile: (body: CandidateProfileUpdate) =>
    request<CandidateProfile>("/candidate/profile", {
      method: "PUT",
      body,
      auth: true,
    }),

  // Skills
  addSkill: (body: SkillInput) =>
    request<Skill>("/candidate/skills", { method: "POST", body, auth: true }),
  updateSkill: (id: string, body: Partial<SkillInput>) =>
    request<Skill>(`/candidate/skills/${id}`, { method: "PUT", body, auth: true }),
  deleteSkill: (id: string) =>
    request<void>(`/candidate/skills/${id}`, { method: "DELETE", auth: true }),

  // Experience
  addExperience: (body: ExperienceInput) =>
    request<Experience>("/candidate/experience", { method: "POST", body, auth: true }),
  updateExperience: (id: string, body: Partial<ExperienceInput>) =>
    request<Experience>(`/candidate/experience/${id}`, {
      method: "PUT",
      body,
      auth: true,
    }),
  deleteExperience: (id: string) =>
    request<void>(`/candidate/experience/${id}`, { method: "DELETE", auth: true }),

  // Education
  addEducation: (body: EducationInput) =>
    request<Education>("/candidate/education", { method: "POST", body, auth: true }),
  updateEducation: (id: string, body: Partial<EducationInput>) =>
    request<Education>(`/candidate/education/${id}`, {
      method: "PUT",
      body,
      auth: true,
    }),
  deleteEducation: (id: string) =>
    request<void>(`/candidate/education/${id}`, { method: "DELETE", auth: true }),

  // Projects
  addProject: (body: ProjectInput) =>
    request<Project>("/candidate/projects", { method: "POST", body, auth: true }),
  updateProject: (id: string, body: Partial<ProjectInput>) =>
    request<Project>(`/candidate/projects/${id}`, {
      method: "PUT",
      body,
      auth: true,
    }),
  deleteProject: (id: string) =>
    request<void>(`/candidate/projects/${id}`, { method: "DELETE", auth: true }),

  // Preferences
  getPreferences: () =>
    request<Preferences>("/candidate/preferences", { auth: true }),
  updatePreferences: (body: Preferences) =>
    request<Preferences>("/candidate/preferences", {
      method: "PUT",
      body,
      auth: true,
    }),
};

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------

export const jobsApi = {
  recommended: (params: { fresh_only?: boolean; cursor?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.fresh_only) qs.set("fresh_only", "true");
    if (params.cursor) qs.set("cursor", params.cursor);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<JobFeedResponse>(`/jobs/recommended${suffix}`, { auth: true });
  },

  search: (body: JobSearchRequest) =>
    request<JobFeedResponse>("/jobs/search", { method: "POST", body, auth: true }),

  searchNaturalLanguage: (query: string) =>
    request<JobFeedResponse>("/jobs/search/natural-language", {
      method: "POST",
      body: { query },
      auth: true,
    }),

  getById: (id: string) => request<JobDetail>(`/jobs/${id}`, { auth: true }),

  estimatedSalary: (id: string) =>
    request<EstimatedSalary>(`/jobs/${id}/estimated-salary`, { auth: true }),

  feedback: (id: string, action: JobFeedbackAction) =>
    request<void>(`/jobs/${id}/feedback`, { method: "POST", body: { action }, auth: true }),

  save: (id: string) => request<void>(`/jobs/${id}/save`, { method: "POST", auth: true }),
  unsave: (id: string) => request<void>(`/jobs/${id}/save`, { method: "DELETE", auth: true }),

  applyClick: (id: string) =>
    request<void>(`/jobs/${id}/apply-click`, { method: "POST", auth: true }),
};

// ---------------------------------------------------------------------------
// Saved jobs & applications
// ---------------------------------------------------------------------------

export const savedJobsApi = {
  list: () => request<SavedJob[]>("/saved-jobs", { auth: true }),
};

export const applicationsApi = {
  list: () => request<Application[]>("/applications", { auth: true }),
  update: (id: string, body: { status: ApplicationStatus; notes?: string }) =>
    request<Application>(`/applications/${id}`, { method: "PATCH", body, auth: true }),
};

// ---------------------------------------------------------------------------
// AI chat
// ---------------------------------------------------------------------------

export const aiApi = {
  chat: (body: ChatRequest) =>
    request<ChatResponse>("/ai/chat", { method: "POST", body, auth: true }),
};

export type { JobCard };
