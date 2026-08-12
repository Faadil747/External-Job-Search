"""Real adapter for the Adzuna Jobs API (https://developer.adzuna.com/).
Requires ADZUNA_APP_ID and ADZUNA_APP_KEY — until those are set this adapter
is skipped by the ingestion worker (see jobs_ingestion/ingestion_worker.py).
Adzuna is a legitimate licensed job aggregator with a documented public API,
so this satisfies the "no unauthorized scraping" constraint in the spec.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from app.config import get_settings
from app.jobs_ingestion.source_interface import JobSourceAdapter, NormalizedJob

logger = structlog.get_logger(__name__)
settings = get_settings()

BASE_URL = "https://api.adzuna.com/v1/api/jobs"


class AdzunaAdapter(JobSourceAdapter):
    name = "adzuna"

    def __init__(self, country: str = "in", results_per_page: int = 50) -> None:
        self.country = country
        self.results_per_page = results_per_page

    def is_configured(self) -> bool:
        return bool(settings.adzuna_app_id and settings.adzuna_app_key)

    async def fetch_jobs(self, *, since: datetime | None = None, limit: int = 200) -> list[NormalizedJob]:
        if not self.is_configured():
            logger.warning("adzuna_not_configured", detail="ADZUNA_APP_ID/ADZUNA_APP_KEY missing, skipping")
            return []

        jobs: list[NormalizedJob] = []
        page = 1
        async with httpx.AsyncClient(timeout=30) as client:
            while len(jobs) < limit:
                url = f"{BASE_URL}/{self.country}/search/{page}"
                params = {
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "results_per_page": self.results_per_page,
                    "content-type": "application/json",
                    "sort_by": "date",
                }
                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.error("adzuna_fetch_failed", page=page, error=str(exc))
                    break

                payload = resp.json()
                results = payload.get("results", [])
                if not results:
                    break

                for raw in results:
                    try:
                        jobs.append(self._normalize(raw))
                    except Exception as exc:  # noqa: BLE001 - one bad record shouldn't kill the batch
                        logger.warning("adzuna_normalize_failed", error=str(exc), raw_id=raw.get("id"))

                if len(results) < self.results_per_page:
                    break
                page += 1

        return jobs[:limit]

    def _normalize(self, raw: dict) -> NormalizedJob:
        location = raw.get("location", {})
        area_list = location.get("area", [])
        category = raw.get("category", {})
        salary_min = raw.get("salary_min")
        salary_max = raw.get("salary_max")

        return NormalizedJob(
            source=self.name,
            source_job_id=str(raw["id"]),
            title=raw.get("title", "").strip(),
            company=(raw.get("company") or {}).get("display_name", "Unknown"),
            description=raw.get("description", ""),
            application_url=raw.get("redirect_url", ""),
            source_url=raw.get("redirect_url", ""),
            city=area_list[-1] if area_list else None,
            state=area_list[-2] if len(area_list) > 1 else None,
            country=self.country.upper(),
            work_mode="onsite",
            employment_type="full_time" if raw.get("contract_time") == "full_time" else "part_time",
            domain=[category.get("label")] if category.get("label") else [],
            salary_min=int(salary_min) if salary_min else None,
            salary_max=int(salary_max) if salary_max else None,
            currency="INR" if self.country == "in" else "USD",
            posted_at=self._parse_date(raw.get("created")),
            is_verified=False,
        )

    @staticmethod
    def _parse_date(raw: str | None) -> datetime:
        if not raw:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
