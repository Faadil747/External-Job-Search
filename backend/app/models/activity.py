import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class SearchHistory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "search_history"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    raw_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_count: Mapped[int] = mapped_column(default=0)


class RecommendationHistory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "recommendation_history"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # viewed|saved|applied|not_relevant|hidden_type


class AIConversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_conversations"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user|assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context_job_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
