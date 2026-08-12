// ---------------------------------------------------------------------------
// Types mirroring the FastAPI backend contract (base path /api/v1).
// Kept in one place so pages/components share a single source of truth.
// ---------------------------------------------------------------------------

// --- Auth ---------------------------------------------------------------

export interface UserPublic {
  id: string;
  email: string;
  is_email_verified: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// --- Resume / candidate profile ------------------------------------------

export type ProcessingStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed"
  | string;

export interface ResumeUploadResponse {
  id: string;
  original_filename: string;
  processing_status: ProcessingStatus;
  created_at: string;
}

export interface ResumeStatusResponse {
  id: string;
  processing_status: ProcessingStatus;
  error_message?: string | null;
}

export interface RecommendedRole {
  title: string;
  confidence: number; // 0-100
  tier: "excellent" | "strong" | "good" | "stretch" | "low" | string;
  reason: string;
  matching_skills: string[];
  missing_skills: string[];
}

export interface ResumeAnalysis {
  id: string;
  overall_score: number;
  score_breakdown: Record<string, number>;
  strengths: string[];
  improvement_suggestions: string[];
  recommended_roles: RecommendedRole[];
  created_at: string;
}

export interface Skill {
  id: string;
  name: string;
  category?: string | null;
  proficiency?: string | null;
  months_experience?: number | null;
  source?: string | null;
}

export type SkillInput = Omit<Skill, "id">;

export interface Experience {
  id: string;
  company: string;
  designation: string;
  start_date?: string | null;
  end_date?: string | null;
  is_current: boolean;
  duration_months?: number | null;
  responsibilities?: string[] | null;
  technologies?: string[] | null;
  domain?: string[] | null;
  achievements?: string[] | null;
}

export type ExperienceInput = Omit<Experience, "id" | "duration_months">;

export interface Education {
  id: string;
  degree: string;
  institution: string;
  field?: string | null;
  graduation_year?: number | null;
  certifications?: string[] | null;
}

export type EducationInput = Omit<Education, "id">;

export interface Project {
  id: string;
  name: string;
  description?: string | null;
  technologies?: string[] | null;
  domain?: string[] | null;
  complexity?: string | null;
}

export type ProjectInput = Omit<Project, "id">;

export interface Preferences {
  preferred_roles: string[];
  preferred_locations: string[];
  preferred_domains: string[];
  salary_min?: number | null;
  salary_max?: number | null;
  currency?: string | null;
  work_mode: string[];
  employment_type: string[];
  min_match_score?: number | null;
  willing_to_relocate: boolean;
  notice_period_days?: number | null;
}

export interface CandidateProfile {
  id: string;
  full_name?: string | null;
  phone?: string | null;
  linkedin_url?: string | null;
  portfolio_url?: string | null;
  github_url?: string | null;
  current_area?: string | null;
  current_city?: string | null;
  current_state?: string | null;
  current_country?: string | null;
  professional_summary?: string | null;
  career_level?: string | null;
  total_experience_months?: number | null;
  relevant_experience_months?: number | null;
  resume_score?: number | null;
  resume_score_breakdown?: Record<string, number> | null;
  ai_strengths?: string[] | null;
  ai_recommended_roles?: RecommendedRole[] | null;
  is_profile_complete: boolean;
  profile_completion_pct: number;
  skills: Skill[];
  experience: Experience[];
  education: Education[];
  projects: Project[];
  preferences: Preferences | null;
}

export type CandidateProfileUpdate = Partial<
  Pick<
    CandidateProfile,
    | "full_name"
    | "phone"
    | "linkedin_url"
    | "portfolio_url"
    | "github_url"
    | "current_area"
    | "current_city"
    | "current_state"
    | "current_country"
    | "professional_summary"
    | "career_level"
    | "total_experience_months"
    | "relevant_experience_months"
  >
>;

// --- Jobs -----------------------------------------------------------------

export type MatchCategory =
  | "excellent"
  | "strong"
  | "good"
  | "potential"
  | "stretch"
  | "low";

export interface JobCard {
  id: string;
  title: string;
  company_name: string;
  company_logo_url?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  work_mode?: string | null;
  employment_type?: string | null;
  experience_min?: number | null;
  experience_max?: number | null;
  salary_min?: number | null;
  salary_max?: number | null;
  currency?: string | null;
  posted_at?: string | null;
  top_skills: string[];
  match_score?: number | null;
  match_category?: MatchCategory | null;
  why_it_matches?: string | null;
  is_verified: boolean;
  is_saved: boolean;
}

export interface JobFeedResponse {
  items: JobCard[];
  next_cursor?: string | null;
  total_estimate?: number | null;
}

export interface JobSearchRequest {
  query?: string;
  city?: string;
  state?: string;
  country?: string;
  work_mode?: string[];
  employment_type?: string[];
  experience_min?: number;
  experience_max?: number;
  domain?: string[];
  skills?: string[];
  salary_min?: number;
  posted_within_days?: number;
  min_match_score?: number;
  sort_by: "best_match" | "newest" | "highest_salary" | "closest_location";
  cursor?: string;
  limit?: number;
}

export interface MatchBreakdown {
  skills?: number;
  experience?: number;
  role?: number;
  semantic?: number;
  location?: number;
  domain?: number;
  education?: number;
  work_mode?: number;
  recency?: number;
  trust?: number;
  [key: string]: number | undefined;
}

export interface TransferableSkill {
  skill: string;
  from: string;
}

export interface MatchReason {
  matched_skills?: string[] | null;
  missing_skills?: string[] | null;
  // Backend sends objects ({skill, from}), e.g. {"skill": "Next.js", "from": "react"}
  // — not plain strings — so a candidate's related-but-not-exact skill can be
  // explained ("Next.js" credited because they know "react").
  transferable_skills?: TransferableSkill[] | null;
  experience_reason?: string | null;
  location_reason?: string | null;
  role_reason?: string | null;
  domain_reason?: string | null;
  overall_reason?: string | null;
  concerns?: string[] | null;
}

export interface JobDetail {
  id: string;
  title: string;
  company_name: string;
  company_url?: string | null;
  description: string;
  responsibilities?: string[] | null;
  requirements_required?: string[] | null;
  requirements_preferred?: string[] | null;
  area?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  work_mode?: string | null;
  employment_type?: string | null;
  experience_min?: number | null;
  experience_max?: number | null;
  domain?: string[] | null;
  salary_min?: number | null;
  salary_max?: number | null;
  currency?: string | null;
  posted_at?: string | null;
  application_url?: string | null;
  source_url?: string | null;
  is_verified: boolean;
  trust_score?: number | null;
  match_score?: number | null;
  match_category?: MatchCategory | null;
  match_breakdown?: MatchBreakdown | null;
  match_reason?: MatchReason | null;
  other_sources?: string[] | null;
}

export type JobFeedbackAction = "not_relevant" | "interested" | "hidden_type";

// A live market-rate estimate -- NEVER the job's own posted salary, kept as
// a distinct shape so it can never be rendered as if it were what the
// employer actually offered. is_estimate is false only when the job already
// had a real posted salary and this endpoint just echoed it back.
export interface EstimatedSalary {
  job_title?: string | null;
  location?: string | null;
  min_salary?: number | null;
  max_salary?: number | null;
  median_salary?: number | null;
  currency?: string | null;
  period?: string | null;
  confidence?: string | null;
  publisher_name?: string | null;
  publisher_link?: string | null;
  sample_size?: number | null;
  is_estimate: boolean;
}

// --- Saved jobs & applications ---------------------------------------------

export interface SavedJob {
  id: string;
  job_id: string;
  created_at: string;
}

export type ApplicationStatus =
  | "apply_clicked"
  | "saved"
  | "applied"
  | "screening"
  | "interview"
  | "offer"
  | "rejected"
  | "withdrawn";

export interface Application {
  id: string;
  job_id: string;
  status: ApplicationStatus;
  application_url?: string | null;
  apply_clicked_at?: string | null;
  applied_at?: string | null;
  notes?: string | null;
  created_at: string;
}

// --- AI chat ----------------------------------------------------------------

export interface ChatRequest {
  message: string;
  job_id?: string;
}

export interface ChatResponse {
  reply: string;
}
