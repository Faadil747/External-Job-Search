import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    category: str
    proficiency: str | None = None
    months_experience: int | None = None
    source: str


class SkillIn(BaseModel):
    name: str
    category: str | None = None
    proficiency: str | None = None
    months_experience: int | None = None


class ExperienceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    company: str
    designation: str
    start_date: date | None
    end_date: date | None
    is_current: bool
    duration_months: int
    responsibilities: list[str] | None = None
    technologies: list[str] | None = None
    domain: list[str] | None = None
    achievements: list[str] | None = None


class ExperienceIn(BaseModel):
    company: str
    designation: str
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    responsibilities: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    domain: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)


class EducationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    degree: str | None
    institution: str | None
    field: str | None
    graduation_year: int | None
    certifications: list[str] | None = None


class EducationIn(BaseModel):
    degree: str | None = None
    institution: str | None = None
    field: str | None = None
    graduation_year: int | None = None
    certifications: list[str] = Field(default_factory=list)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    technologies: list[str] | None = None
    domain: list[str] | None = None
    complexity: str | None = None


class ProjectIn(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    domain: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    complexity: str | None = None


class PreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    preferred_roles: list[str] | None = None
    preferred_locations: list[str] | None = None
    preferred_domains: list[str] | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    work_mode: list[str] | None = None
    employment_type: list[str] | None = None
    min_match_score: int
    willing_to_relocate: bool
    notice_period_days: int | None = None


class PreferencesIn(BaseModel):
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    preferred_domains: list[str] = Field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    work_mode: list[str] = Field(default_factory=list)
    employment_type: list[str] = Field(default_factory=list)
    min_match_score: int = 50
    willing_to_relocate: bool = False
    notice_period_days: int | None = None


class CandidateProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str | None
    phone: str | None
    linkedin_url: str | None
    portfolio_url: str | None
    github_url: str | None
    current_area: str | None
    current_city: str | None
    current_state: str | None
    current_country: str | None
    professional_summary: str | None
    career_level: str | None
    total_experience_months: int
    relevant_experience_months: int
    resume_score: float | None
    resume_score_breakdown: dict | None
    ai_strengths: list[str] | None
    ai_recommended_roles: list[dict] | None
    is_profile_complete: bool
    profile_completion_pct: int
    created_at: datetime
    updated_at: datetime

    skills: list[SkillOut] = Field(default_factory=list)
    experience: list[ExperienceOut] = Field(default_factory=list)
    education: list[EducationOut] = Field(default_factory=list)
    projects: list[ProjectOut] = Field(default_factory=list)
    preferences: PreferencesOut | None = None


class CandidateProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    github_url: str | None = None
    current_area: str | None = None
    current_city: str | None = None
    current_state: str | None = None
    current_country: str | None = None
    professional_summary: str | None = None
    career_level: str | None = None

