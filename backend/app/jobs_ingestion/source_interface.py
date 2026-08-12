"""JobSourceInterface — every job source (API, feed, career page, ATS) plugs in
here. Adding a source means writing one adapter under jobs_ingestion/adapters/
and registering it in ADAPTER_REGISTRY; nothing else in the ingestion pipeline
changes. Adapters return NormalizedJob objects — the unified schema from
section 19 of the product spec — so downstream dedup/embedding/ranking code
never has to know which source a job came from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NormalizedJob:
    source: str
    source_job_id: str
    title: str
    company: str
    description: str
    application_url: str
    source_url: str

    area: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    work_mode: str = "onsite"  # remote | hybrid | onsite
    employment_type: str = "full_time"  # full_time | part_time | internship | contract | temporary

    experience_min: int = 0
    experience_max: int = 0

    skills: list[str] = field(default_factory=list)
    domain: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    requirements_required: list[str] = field(default_factory=list)
    requirements_preferred: list[str] = field(default_factory=list)

    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None

    posted_at: datetime | None = None
    company_url: str | None = None
    is_verified: bool = False


class JobSourceAdapter(ABC):
    """One adapter per external source. `name` must match a JobSource.adapter_key
    row so ingestion stats (section 76) attribute correctly."""

    name: str

    @abstractmethod
    async def fetch_jobs(self, *, since: datetime | None = None, limit: int = 200) -> list[NormalizedJob]:
        """Fetch and normalize jobs. Must not raise on a single bad record —
        skip it and let the ingestion worker log the failure count instead."""
