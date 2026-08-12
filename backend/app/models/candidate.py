import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

EMBED_DIM = get_settings().embedding_dim


class CandidateProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "candidate_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )

    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    current_area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_country: Mapped[str | None] = mapped_column(String(120), nullable=True)

    professional_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    career_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_experience_months: Mapped[int] = mapped_column(Integer, default=0)
    relevant_experience_months: Mapped[int] = mapped_column(Integer, default=0)

    resume_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    resume_score_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_strengths: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    ai_recommended_roles: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    profile_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    skill_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)

    is_profile_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    profile_completion_pct: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="candidate_profile")  # noqa: F821
    skills: Mapped[list["CandidateSkill"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    experience: Mapped[list["CandidateExperience"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", order_by="desc(CandidateExperience.start_date)"
    )
    education: Mapped[list["CandidateEducation"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    projects: Mapped[list["CandidateProject"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    preferences: Mapped["CandidatePreference | None"] = relationship(
        back_populates="candidate", uselist=False, cascade="all, delete-orphan"
    )


class CandidateSkill(UUIDMixin, Base):
    __tablename__ = "candidate_skills"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="other")
    proficiency: Mapped[str | None] = mapped_column(String(30), nullable=True)
    months_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="resume")  # resume | manual

    candidate: Mapped["CandidateProfile"] = relationship(back_populates="skills")


class CandidateExperience(UUIDMixin, Base):
    __tablename__ = "candidate_experience"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    designation: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_months: Mapped[int] = mapped_column(Integer, default=0)
    responsibilities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    technologies: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    domain: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    achievements: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    candidate: Mapped["CandidateProfile"] = relationship(back_populates="experience")


class CandidateEducation(UUIDMixin, Base):
    __tablename__ = "candidate_education"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    degree: Mapped[str | None] = mapped_column(String(255), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    graduation_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    certifications: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    candidate: Mapped["CandidateProfile"] = relationship(back_populates="education")


class CandidateProject(UUIDMixin, Base):
    __tablename__ = "candidate_projects"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    domain: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    responsibilities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    complexity: Mapped[str | None] = mapped_column(String(30), nullable=True)

    candidate: Mapped["CandidateProfile"] = relationship(back_populates="projects")


class CandidatePreference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "candidate_preferences"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), unique=True
    )
    preferred_roles: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    preferred_locations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    preferred_domains: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    work_mode: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # remote/hybrid/onsite
    employment_type: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    min_match_score: Mapped[int] = mapped_column(Integer, default=50)
    willing_to_relocate: Mapped[bool] = mapped_column(Boolean, default=False)
    notice_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    candidate: Mapped["CandidateProfile"] = relationship(back_populates="preferences")
