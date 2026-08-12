"""VectorStore abstraction. Default implementation queries pgvector columns
directly on the jobs/candidate_profiles tables (see app/models). A dedicated
store like Qdrant can be swapped in later behind the same interface without
touching callers in app/services/matching_service.py or app/rag/retrieval.py.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.job import Job

settings = get_settings()


class VectorStore(ABC):
    @abstractmethod
    async def search_jobs(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        top_k: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[uuid.UUID, float]]:
        """Return (job_id, cosine_similarity) pairs, most similar first."""


class PgVectorStore(VectorStore):
    async def search_jobs(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        top_k: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[uuid.UUID, float]]:
        # cosine_distance is 0 (identical) .. 2 (opposite); similarity = 1 - distance
        distance = Job.embedding.cosine_distance(query_embedding)
        stmt = (
            select(Job.id, distance.label("distance"))
            .where(Job.embedding.is_not(None))
            .where(Job.is_duplicate.is_(False))
        )
        filters = filters or {}
        if filters.get("country"):
            stmt = stmt.where(Job.country == filters["country"])
        if filters.get("work_mode"):
            stmt = stmt.where(Job.work_mode.in_(filters["work_mode"]))
        if filters.get("employment_type"):
            stmt = stmt.where(Job.employment_type.in_(filters["employment_type"]))
        if filters.get("posted_after"):
            stmt = stmt.where(Job.posted_at >= filters["posted_after"])

        stmt = stmt.order_by(distance).limit(top_k)
        rows = (await db.execute(stmt)).all()
        return [(row.id, max(0.0, 1.0 - row.distance)) for row in rows]


def get_vector_store() -> VectorStore:
    if settings.vector_store == "pgvector":
        return PgVectorStore()
    raise ValueError(
        f"Unknown VECTOR_STORE: {settings.vector_store}. "
        "Implement a new VectorStore subclass to add one (e.g. Qdrant)."
    )
