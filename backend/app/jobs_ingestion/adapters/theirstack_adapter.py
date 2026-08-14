"""Real adapter for the TheirStack Jobs API (https://theirstack.com), a
licensed job-postings data provider that aggregates real listings from
LinkedIn, Indeed, Naukri, company career pages (Workday, etc.) with rich,
pre-structured metadata -- notably `technology_slugs` (an actual detected
tech-stack list per posting, not something we have to guess at from free
text) and clean `remote`/`hybrid` flags. This is the highest-fidelity source
wired into this pipeline; confirmed live against real filter combinations
(technology + country + workplace_type + freshness all correctly narrowed
the result set — see the adapter's own module-level notes below for the
exact request/response shapes this was built against).

## Credit budget — read before changing query volume or scheduling

Unlike the RapidAPI-based adapters (a flat per-key request quota), TheirStack
bills **1 credit per job record returned**, and the credit pool is a
per-account MONTHLY allowance (confirmed live: a free/trial tier starts at
200 credits/month) — not a daily reset. That makes it fundamentally
unsuited to the same automatic-scheduler rotation as JSearch: the ingestion
scheduler (app/jobs_ingestion/ingestion_worker.py) re-runs EVERY enabled
source on the same interval, and at even 30 credits/cycle (3 queries x 10
jobs), a 6-hour cadence would exhaust a 200-credit/month budget in under two
days. Because of this, this adapter is deliberately NOT added to the default
JOB_SOURCES_ENABLED rotation -- it's meant to be run manually/occasionally
(`python -m app.jobs_ingestion.ingestion_worker` with THEIRSTACK temporarily
in JOB_SOURCES_ENABLED, or added to the rotation deliberately with a much
longer INGESTION_INTERVAL_MINUTES than JSearch would need) rather than on a
tight automatic schedule. THEIRSTACK_QUERIES x THEIRSTACK_LIMIT_PER_QUERY is
the exact credit cost of one ingestion pass -- do the multiplication before
changing either.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from app.config import get_settings
from app.jobs_ingestion.source_interface import JobSourceAdapter, NormalizedJob

logger = structlog.get_logger(__name__)
settings = get_settings()

SEARCH_URL = "https://api.theirstack.com/v1/jobs/search"

_EMPLOYMENT_STATUS_MAP = {
    "full_time": "full_time",
    "part_time": "part_time",
    "contract": "contract",
    "contractor": "contract",
    "internship": "internship",
    "temporary": "temporary",
}

# TheirStack's technology_slugs are hyphenated identifiers (e.g. "spring-boot",
# "amazon-web-services"), not display names. matching_service._normalize_skill
# only lowercases/strips -- it does NOT treat "spring-boot" and "spring boot"
# as equal -- so passing slugs through unconverted would silently break skill
# matching against candidate-entered skill names for anything with a hyphen.
# This covers the common cases most likely to appear on both sides (a
# candidate's resume and a job's detected stack); anything not listed here
# just gets hyphens turned into spaces, which is still a real improvement
# over the raw slug.
_SLUG_DISPLAY_OVERRIDES: dict[str, str] = {
    "amazon-web-services": "AWS",
    "google-cloud-platform": "GCP",
    "microsoft-azure": "Azure",
    "nodejs": "Node.js",
    "node-js": "Node.js",
    "next-js": "Next.js",
    "vue-js": "Vue.js",
    "react": "React",
    "reactjs": "React",
    "dot-net": ".NET",
    "dot-net-core": ".NET Core",
    "asp-net": "ASP.NET",
    "asp-net-core": "ASP.NET Core",
    "cplusplus": "C++",
    "c-sharp": "C#",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "rest-api": "REST API",
    "open-api": "REST API",
    "graphql": "GraphQL",
    "ci-cd": "CI/CD",
    "github-actions": "GitHub Actions",
    "spring-boot": "Spring Boot",
    "spring-framework": "Spring",
    "django": "Django",
    "fastapi": "FastAPI",
    "scikit-learn": "Scikit-learn",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "power-bi": "Power BI",
    "amazon-s3": "S3",
    "amazon-ec2": "EC2",
    "amazon-rds-for-mysql": "Amazon RDS",
    "aws-lambda": "AWS Lambda",
}

# Rough, explicitly-approximate mapping from TheirStack's seniority label to
# an experience-year range -- used only as a fallback when a posting has no
# other experience signal; a first-choice signal (an explicit "X years"
# phrase actually present in the description) is still extracted separately
# and takes priority in job_normalizer.py.
_SENIORITY_EXPERIENCE_RANGE: dict[str, tuple[int, int]] = {
    "entry_level": (0, 2),
    "junior": (0, 2),
    "mid_level": (2, 5),
    "senior": (5, 9),
    "lead": (8, 12),
    "principal": (10, 15),
    "director": (10, 18),
    "executive": (12, 20),
}


def _slug_to_display(slug: str) -> str:
    if slug in _SLUG_DISPLAY_OVERRIDES:
        return _SLUG_DISPLAY_OVERRIDES[slug]
    return slug.replace("-", " ").strip().title()


class TheirStackAdapter(JobSourceAdapter):
    name = "theirstack"

    def __init__(
        self,
        queries: list[str] | None = None,
        country: str | None = None,
        max_age_days: int | None = None,
        limit_per_query: int | None = None,
    ) -> None:
        self.queries = queries if queries is not None else settings.theirstack_queries_list
        self.country = country or settings.theirstack_country
        self.max_age_days = max_age_days or settings.theirstack_max_age_days
        self.limit_per_query = limit_per_query or settings.theirstack_limit_per_query

    def is_configured(self) -> bool:
        return bool(settings.theirstack_api_key)

    async def fetch_jobs(self, *, since: datetime | None = None, limit: int = 200) -> list[NormalizedJob]:
        if not self.is_configured():
            logger.warning("theirstack_not_configured", detail="THEIRSTACK_API_KEY missing, skipping")
            return []
        if not self.queries:
            logger.warning("theirstack_no_queries", detail="THEIRSTACK_QUERIES is empty, skipping")
            return []

        headers = {
            "Authorization": f"Bearer {settings.theirstack_api_key}",
            "Content-Type": "application/json",
        }

        jobs: list[NormalizedJob] = []
        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            for query in self.queries:
                if len(jobs) >= limit:
                    break
                per_query_limit = min(self.limit_per_query, limit - len(jobs))
                payload = {
                    "job_title_or": [query],
                    "job_country_code_or": [self.country],
                    "posted_at_max_age_days": self.max_age_days,
                    "limit": per_query_limit,
                }
                try:
                    resp = await client.post(SEARCH_URL, json=payload)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.error("theirstack_fetch_failed", query=query, error=str(exc))
                    continue

                results = (resp.json() or {}).get("data") or []
                for raw in results:
                    if len(jobs) >= limit:
                        break
                    try:
                        jobs.append(self._normalize(raw))
                    except Exception as exc:  # noqa: BLE001 - one bad record shouldn't kill the batch
                        logger.warning("theirstack_normalize_failed", error=str(exc), raw_id=raw.get("id"))

        return jobs[:limit]

    def _normalize(self, raw: dict) -> NormalizedJob:
        employment_statuses = raw.get("employment_statuses") or []
        employment_type = _EMPLOYMENT_STATUS_MAP.get(
            (employment_statuses[0] if employment_statuses else "").lower(), "full_time"
        )

        work_mode = "remote" if raw.get("remote") else ("hybrid" if raw.get("hybrid") else "onsite")

        # Prefer TheirStack's structured `locations` (geocoded, one row per
        # matched location) over the free-text `location`/`short_location`
        # strings when available -- real city/state fidelity, not parsed
        # guesswork.
        locations = raw.get("locations") or []
        loc = locations[0] if locations else {}
        city = loc.get("city") or (raw.get("short_location") or "").split(",")[0].strip() or None
        state = loc.get("state") or raw.get("state_code")
        country = loc.get("country_name") or raw.get("country")

        skills = [_slug_to_display(s) for s in (raw.get("technology_slugs") or [])]

        experience_range = _SENIORITY_EXPERIENCE_RANGE.get((raw.get("seniority") or "").lower())
        experience_min, experience_max = experience_range or (0, 0)

        company_object = raw.get("company_object") or {}
        company_url = company_object.get("url") or (
            f"https://{raw['company_domain']}" if raw.get("company_domain") else None
        )

        apply_url = raw.get("final_url") or raw.get("url") or ""

        return NormalizedJob(
            source=self.name,
            source_job_id=str(raw["id"]),
            title=(raw.get("job_title") or "").strip(),
            company=raw.get("company") or "Unknown",
            description=raw.get("description") or "",
            application_url=apply_url,
            source_url=raw.get("source_url") or apply_url,
            city=city,
            state=state,
            country=country,
            work_mode=work_mode,
            employment_type=employment_type,
            experience_min=experience_min,
            experience_max=experience_max,
            skills=skills,
            salary_min=int(raw["min_annual_salary_usd"]) if raw.get("min_annual_salary_usd") else None,
            salary_max=int(raw["max_annual_salary_usd"]) if raw.get("max_annual_salary_usd") else None,
            currency="USD" if raw.get("min_annual_salary_usd") or raw.get("max_annual_salary_usd") else None,
            posted_at=self._parse_date(raw.get("date_posted") or raw.get("discovered_at")),
            company_url=company_url,
            is_verified=False,
        )

    @staticmethod
    def _parse_date(raw: str | None) -> datetime:
        if not raw:
            return datetime.now(timezone.utc)
        try:
            if len(raw) == 10:  # date-only, e.g. "2026-08-13"
                return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
