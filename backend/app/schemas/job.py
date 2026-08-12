import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EstimatedSalaryOut(BaseModel):
    """A live market-rate estimate (JSearch salary APIs), NEVER the job's own
    posted salary — kept as an explicitly separate response shape so a
    frontend can never accidentally render this as if it were what the
    employer actually offered."""

    job_title: str | None = None
    location: str | None = None
    min_salary: float | None = None
    max_salary: float | None = None
    median_salary: float | None = None
    currency: str | None = None
    period: str | None = None
    confidence: str | None = None
    publisher_name: str | None = None
    publisher_link: str | None = None
    sample_size: int | None = None
    is_estimate: bool = True


class MatchReasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    matched_skills: list[str] | None = None
    missing_skills: list[str] | None = None
    transferable_skills: list[dict] | None = None
    experience_reason: str | None = None
    location_reason: str | None = None
    role_reason: str | None = None
    domain_reason: str | None = None
    overall_reason: str | None = None
    concerns: list[str] | None = None


class MatchBreakdown(BaseModel):
    skills: float
    experience: float
    role: float
    semantic: float
    location: float
    domain: float
    education: float
    work_mode: float
    recency: float
    trust: float


class JobCardOut(BaseModel):
    """Slim payload for feed/search list views."""

    id: uuid.UUID
    title: str
    company_name: str
    company_logo_url: str | None = None
    city: str | None
    state: str | None
    country: str | None
    work_mode: str
    employment_type: str
    experience_min: int
    experience_max: int
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    posted_at: datetime
    top_skills: list[str] = []
    match_score: float | None = None
    match_category: str | None = None
    why_it_matches: str | None = None
    is_verified: bool
    is_saved: bool = False


class JobDetailOut(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str
    company_url: str | None
    description: str
    responsibilities: list[str] | None = None
    requirements_required: list[str] | None = None
    requirements_preferred: list[str] | None = None
    area: str | None
    city: str | None
    state: str | None
    country: str | None
    work_mode: str
    employment_type: str
    experience_min: int
    experience_max: int
    domain: list[str] | None = None
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    posted_at: datetime
    application_url: str
    source_url: str
    is_verified: bool
    trust_score: float
    match_score: float | None = None
    match_category: str | None = None
    match_breakdown: MatchBreakdown | None = None
    match_reason: MatchReasonOut | None = None
    other_sources: list[str] = []


class JobFeedResponse(BaseModel):
    items: list[JobCardOut]
    next_cursor: str | None = None
    total_estimate: int | None = None


class JobSearchRequest(BaseModel):
    query: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    work_mode: list[str] | None = None
    employment_type: list[str] | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    domain: list[str] | None = None
    skills: list[str] | None = None
    salary_min: int | None = None
    posted_within_days: int | None = None
    min_match_score: int | None = None
    sort_by: str = "best_match"  # best_match | newest | highest_salary | closest_location
    cursor: str | None = None
    limit: int = 20


class NaturalLanguageSearchRequest(BaseModel):
    query: str


class ParsedSearchFilters(BaseModel):
    role: list[str] = []
    location: list[str] = []
    experience_min: int | None = None
    experience_max: int | None = None
    posted_within_days: int | None = None
    work_mode: list[str] = []
    employment_type: list[str] = []
    skills: list[str] = []
