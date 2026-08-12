import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

EMBED_DIM = get_settings().embedding_dim


class JobSource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "job_sources"

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    adapter_key: Mapped[str] = mapped_column(String(80), nullable=False)
    trust_tier: Mapped[str] = mapped_column(String(20), default="aggregator")  # employer|ats|platform|aggregator
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str] = mapped_column(String(20), default="never_run")
    jobs_fetched_total: Mapped[int] = mapped_column(Integer, default=0)
    jobs_accepted_total: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_total: Mapped[int] = mapped_column(Integer, default=0)
    failures_total: Mapped[int] = mapped_column(Integer, default=0)


class Company(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Job(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    canonical_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_sources.id"))
    # 512, not 255: some real sources (e.g. JSearch/RapidAPI) use long
    # base64-encoded opaque IDs (250-350+ chars observed live), which
    # overflowed a 255-char column and silently failed every insert until
    # this was widened.
    source_job_id: Mapped[str] = mapped_column(String(512), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True
    )
    company_name_raw: Mapped[str] = mapped_column(String(255), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    responsibilities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    requirements_required: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    requirements_preferred: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    work_mode: Mapped[str] = mapped_column(String(20), index=True, default="onsite")  # remote|hybrid|onsite
    employment_type: Mapped[str] = mapped_column(String(20), index=True, default="full_time")

    experience_min: Mapped[int] = mapped_column(Integer, default=0, index=True)
    experience_max: Mapped[int] = mapped_column(Integer, default=0, index=True)

    domain: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    education: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness_status: Mapped[str] = mapped_column(String(20), default="active")  # fresh|active|possibly_stale|expired

    application_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    company_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)

    trust_score: Mapped[float] = mapped_column(Float, default=0.5)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    risk_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    skills: Mapped[list["JobSkill"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobSkill(UUIDMixin, Base):
    __tablename__ = "job_skills"

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)

    job: Mapped["Job"] = relationship(back_populates="skills")


class JobDuplicate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "job_duplicates"

    canonical_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"))
    duplicate_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
