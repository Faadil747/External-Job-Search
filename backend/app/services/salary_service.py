"""On-demand salary estimation via the JSearch salary endpoints (RapidAPI).

Deliberately NOT called during bulk ingestion and NEVER written into
`Job.salary_min`/`salary_max` — those columns are reserved for a job's own
*posted* salary. Writing a market estimate into the same field would make an
estimate indistinguishable from what the employer actually offered, which is
exactly the "never fabricate salary" rule the product spec calls out (section
84). Instead this is a live, on-demand lookup — called only when a candidate
actually asks for it (GET /jobs/{id}/estimated-salary), so API quota usage
stays proportional to real user interest rather than proportional to the
number of jobs ever ingested.

Tries `company-job-salary` first (more specific — factors in the actual
employer) when a company name is available, falling back to the more general
`estimated-salary` endpoint otherwise or if the company-specific lookup
returns nothing.
"""

from __future__ import annotations

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_HEADERS_HOST = "jsearch.p.rapidapi.com"
COMPANY_SALARY_URL = "https://jsearch.p.rapidapi.com/company-job-salary"
ESTIMATED_SALARY_URL = "https://jsearch.p.rapidapi.com/estimated-salary"


class SalaryEstimateUnavailable(Exception):
    """Raised when no estimate could be produced (not configured, no data,
    or the upstream API failed) — callers should degrade to "not available"
    rather than crash."""


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-rapidapi-host": _HEADERS_HOST,
        "x-rapidapi-key": settings.jsearch_rapidapi_key,
    }


def _parse_estimate(entry: dict) -> dict:
    return {
        "job_title": entry.get("job_title"),
        "location": entry.get("location"),
        "min_salary": entry.get("min_salary"),
        "max_salary": entry.get("max_salary"),
        "median_salary": entry.get("median_salary"),
        "currency": entry.get("salary_currency"),
        "period": entry.get("salary_period"),
        "confidence": entry.get("confidence"),
        "publisher_name": entry.get("publisher_name"),
        "publisher_link": entry.get("publisher_link"),
        "sample_size": entry.get("salary_count"),
    }


async def get_estimated_salary(
    job_title: str, location: str | None, company: str | None = None
) -> dict:
    """Returns a market salary estimate dict (see _parse_estimate for shape).
    Raises SalaryEstimateUnavailable if none could be obtained."""
    if not settings.jsearch_rapidapi_key:
        raise SalaryEstimateUnavailable("JSEARCH_RAPIDAPI_KEY is not configured")

    async with httpx.AsyncClient(timeout=20, headers=_headers()) as client:
        if company:
            try:
                resp = await client.get(
                    COMPANY_SALARY_URL,
                    params={
                        "company": company,
                        "job_title": job_title,
                        "location_type": "ANY",
                        "years_of_experience": "ALL",
                    },
                )
                resp.raise_for_status()
                entries = (resp.json() or {}).get("data") or []
                if entries:
                    return _parse_estimate(entries[0])
            except httpx.HTTPError as exc:
                logger.warning("company_job_salary_failed", company=company, error=str(exc))

        try:
            resp = await client.get(
                ESTIMATED_SALARY_URL,
                params={
                    "job_title": job_title,
                    "location": location or "",
                    "location_type": "ANY",
                    "years_of_experience": "ALL",
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("estimated_salary_failed", job_title=job_title, error=str(exc))
            raise SalaryEstimateUnavailable(str(exc)) from exc

        entries = (resp.json() or {}).get("data") or []
        if not entries:
            raise SalaryEstimateUnavailable("No salary data available for this role/location")
        return _parse_estimate(entries[0])
