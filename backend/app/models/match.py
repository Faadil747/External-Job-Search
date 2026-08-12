import uuid

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class JobMatch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "job_matches"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)

    score: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # excellent|strong|good|potential|stretch|low

    skills_score: Mapped[float] = mapped_column(Float, default=0)
    experience_score: Mapped[float] = mapped_column(Float, default=0)
    role_score: Mapped[float] = mapped_column(Float, default=0)
    semantic_score: Mapped[float] = mapped_column(Float, default=0)
    location_score: Mapped[float] = mapped_column(Float, default=0)
    domain_score: Mapped[float] = mapped_column(Float, default=0)
    education_score: Mapped[float] = mapped_column(Float, default=0)
    work_mode_score: Mapped[float] = mapped_column(Float, default=0)
    recency_score: Mapped[float] = mapped_column(Float, default=0)
    trust_score: Mapped[float] = mapped_column(Float, default=0)

    reason: Mapped["MatchReason"] = relationship(
        back_populates="match", uselist=False, cascade="all, delete-orphan"
    )


class MatchReason(UUIDMixin, Base):
    __tablename__ = "match_reasons"

    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_matches.id", ondelete="CASCADE"), unique=True
    )
    matched_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    missing_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    transferable_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    experience_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    role_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    domain_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    overall_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    concerns: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    llm_validated: Mapped[bool] = mapped_column(Boolean, default=False)

    match: Mapped["JobMatch"] = relationship(back_populates="reason")
