"""SeedAdapter — a PLACEHOLDER job source for local development and testing
only. It reads hand-authored sample postings from seed_data.json (fictional
companies/URLs, clearly not real listings) so the ingestion → normalization →
dedup → embedding → matching pipeline can be exercised end-to-end without any
external API keys. It is registered with trust_tier="aggregator" and
is_verified defaults to the record's own flag — never claim these are real.

Replace/disable this adapter (via JOB_SOURCES_ENABLED) once a licensed source
such as Adzuna is configured.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.jobs_ingestion.source_interface import JobSourceAdapter, NormalizedJob

SEED_FILE = Path(__file__).parent / "seed_data.json"


class SeedAdapter(JobSourceAdapter):
    name = "seed"

    async def fetch_jobs(self, *, since: datetime | None = None, limit: int = 200) -> list[NormalizedJob]:
        raw_records = json.loads(SEED_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc)
        jobs: list[NormalizedJob] = []

        for raw in raw_records[:limit]:
            posted_at = now - timedelta(days=raw.get("posted_days_ago", 0))
            jobs.append(
                NormalizedJob(
                    source=self.name,
                    source_job_id=raw["source_job_id"],
                    title=raw["title"],
                    company=raw["company"],
                    description=raw["description"],
                    application_url=raw["application_url"],
                    source_url=raw["source_url"],
                    area=raw.get("area"),
                    city=raw.get("city"),
                    state=raw.get("state"),
                    country=raw.get("country"),
                    work_mode=raw.get("work_mode", "onsite"),
                    employment_type=raw.get("employment_type", "full_time"),
                    experience_min=raw.get("experience_min", 0),
                    experience_max=raw.get("experience_max", 0),
                    skills=raw.get("skills", []),
                    domain=raw.get("domain", []),
                    education=raw.get("education", []),
                    requirements_required=raw.get("requirements_required", []),
                    requirements_preferred=raw.get("requirements_preferred", []),
                    salary_min=raw.get("salary_min"),
                    salary_max=raw.get("salary_max"),
                    currency=raw.get("currency"),
                    posted_at=posted_at,
                    company_url=raw.get("company_url"),
                    is_verified=raw.get("is_verified", False),
                )
            )

        if since is not None:
            jobs = [j for j in jobs if j.posted_at and j.posted_at >= since]

        return jobs
