"""Real adapter for the JSearch API on RapidAPI
(https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) — a licensed aggregator
that republishes postings from LinkedIn, Indeed, Glassdoor, ZipRecruiter, and
many company/ATS career pages, each with a real `job_apply_link` back to the
original posting. This is a legitimate, documented public API (satisfies the
"no unauthorized scraping" constraint) and is inert (returns an empty list
with a warning log) until JSEARCH_RAPIDAPI_KEY is set.

## Field-availability notes (checked against live responses, not assumed)

`search-v2` reliably returns: title, employer/company, full description,
location (city/state/country), a remote flag, employment type, the apply
link, and a posting timestamp. It does NOT reliably return structured
required-skills/required-experience/salary fields — most real-world postings
aggregated from third-party publishers simply don't carry that structured
metadata, this isn't a bug in the integration. Rather than heuristically
guessing "required skills" out of free-text descriptions (which risks
mischaracterizing a posting — see spec section 84, never fabricate job
details), those fields are left empty when absent and the matching engine's
semantic-similarity score (built from the *full* description text) carries
proportionally more weight for these jobs. `_score_skills()` in
matching_service.py already treats an empty required-skills list as "nothing
to fail against" (full credit) rather than a penalty, so this degrades
gracefully rather than unfairly.

`job_highlights.Qualifications`, when the publisher provides it, is used
verbatim as `requirements_required` — real, publisher-authored text, not an
inference.

## Rate limits — read before changing ingestion frequency

RapidAPI enforces a per-plan request quota (observed live during development:
`X-RateLimit-Requests-Limit: 200` per reset period on the plan tied to the
key in use). Each `fetch_jobs()` call issues one HTTP request per configured
query (JSEARCH_QUERIES), not one per job. Keep JSEARCH_QUERIES short and/or
raise INGESTION_INTERVAL_MINUTES if JSearch is in JOB_SOURCES_ENABLED, or the
automatic scheduler (app/jobs_ingestion/ingestion_worker.py) will exhaust the
quota within a few days. This adapter does not implement its own retry-on-429
specifically to avoid compounding that risk — a failed cycle is logged and
simply tried again on the next scheduled run.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from app.config import get_settings
from app.jobs_ingestion.source_interface import JobSourceAdapter, NormalizedJob

logger = structlog.get_logger(__name__)
settings = get_settings()

SEARCH_URL = "https://jsearch.p.rapidapi.com/search-v2"

_EMPLOYMENT_TYPE_MAP = {
    "FULLTIME": "full_time",
    "PARTTIME": "part_time",
    "CONTRACTOR": "contract",
    "INTERN": "internship",
    "TEMPORARY": "temporary",
}


class JSearchAdapter(JobSourceAdapter):
    name = "jsearch"

    def __init__(self, queries: list[str] | None = None, country: str | None = None, num_pages: int | None = None) -> None:
        self.queries = queries if queries is not None else settings.jsearch_queries_list
        self.country = country or settings.jsearch_country
        self.num_pages = num_pages or settings.jsearch_num_pages

    def is_configured(self) -> bool:
        return bool(settings.jsearch_rapidapi_key)

    async def fetch_jobs(self, *, since: datetime | None = None, limit: int = 200) -> list[NormalizedJob]:
        if not self.is_configured():
            logger.warning("jsearch_not_configured", detail="JSEARCH_RAPIDAPI_KEY missing, skipping")
            return []
        if not self.queries:
            logger.warning("jsearch_no_queries", detail="JSEARCH_QUERIES is empty, skipping")
            return []

        headers = {
            "Content-Type": "application/json",
            "x-rapidapi-host": "jsearch.p.rapidapi.com",
            "x-rapidapi-key": settings.jsearch_rapidapi_key,
        }

        jobs: list[NormalizedJob] = []
        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            for query in self.queries:
                if len(jobs) >= limit:
                    break
                params = {
                    "query": query,
                    "num_pages": str(self.num_pages),
                    "country": self.country,
                    "date_posted": "all",
                }
                try:
                    resp = await client.get(SEARCH_URL, params=params)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.error("jsearch_fetch_failed", query=query, error=str(exc))
                    continue

                payload = resp.json()
                results = (payload.get("data") or {}).get("jobs") or []
                for raw in results:
                    if len(jobs) >= limit:
                        break
                    try:
                        jobs.append(self._normalize(raw))
                    except Exception as exc:  # noqa: BLE001 - one bad record shouldn't kill the batch
                        logger.warning("jsearch_normalize_failed", error=str(exc), raw_id=raw.get("job_id"))

        return jobs[:limit]

    def _normalize(self, raw: dict) -> NormalizedJob:
        employment_types = raw.get("job_employment_types") or []
        employment_type = _EMPLOYMENT_TYPE_MAP.get(
            (employment_types[0] if employment_types else "").upper(), "full_time"
        )

        highlights = raw.get("job_highlights") or {}
        qualifications = [q for q in (highlights.get("Qualifications") or []) if isinstance(q, str)]
        responsibilities = [r for r in (highlights.get("Responsibilities") or []) if isinstance(r, str)]

        salary_min = raw.get("job_min_salary")
        salary_max = raw.get("job_max_salary")

        apply_link = raw.get("job_apply_link") or ""

        return NormalizedJob(
            source=self.name,
            source_job_id=str(raw["job_id"]),
            title=(raw.get("job_title") or "").strip(),
            company=raw.get("employer_name") or "Unknown",
            description=raw.get("job_description") or "",
            application_url=apply_link,
            source_url=apply_link,
            city=raw.get("job_city") or None,
            state=raw.get("job_state") or None,
            country=raw.get("job_country") or None,
            work_mode="remote" if raw.get("job_is_remote") else "onsite",
            employment_type=employment_type,
            requirements_required=qualifications,
            responsibilities=responsibilities,
            salary_min=int(salary_min) if salary_min else None,
            salary_max=int(salary_max) if salary_max else None,
            currency=raw.get("job_salary_currency") or (None if not salary_min else "USD"),
            posted_at=self._parse_date(raw.get("job_posted_at_datetime_utc")),
            company_url=raw.get("employer_website") or None,
            # job_apply_is_direct means the link goes straight to the employer's
            # own application system rather than a third-party republisher —
            # a real, data-driven trust signal rather than an arbitrary default.
            is_verified=bool(raw.get("job_apply_is_direct")),
        )

    @staticmethod
    def _parse_date(raw: str | None) -> datetime:
        if not raw:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
