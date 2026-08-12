"""Orchestrates one ingestion pass: for each enabled source, fetch ->
normalize -> dedup -> embed -> update JobSource stats.

Runnable standalone once Postgres is up:

    python -m app.jobs_ingestion.ingestion_worker
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding_provider import get_embedding_provider
from app.config import get_settings
from app.jobs_ingestion.adapters import ADAPTER_REGISTRY
from app.jobs_ingestion.source_interface import NormalizedJob
from app.models.job import Job, JobSource
from app.services.dedup_service import find_and_link_duplicates
from app.services.embedding_service import job_embedding_text
from app.services.job_normalizer import normalize_and_persist

logger = structlog.get_logger(__name__)

# Sources whose postings come straight from the employer's own system get the
# highest default trust tier; general aggregators (seed, adzuna) start lowest
# and can be manually promoted later (e.g. once a source is verified).
_DEFAULT_TRUST_TIER_BY_ADAPTER: dict[str, str] = {
    "seed": "aggregator",
    "adzuna": "aggregator",
    "jsearch": "aggregator",
}


async def _get_or_create_source(db: AsyncSession, adapter_key: str) -> JobSource:
    stmt = select(JobSource).where(JobSource.adapter_key == adapter_key)
    source = (await db.execute(stmt)).scalar_one_or_none()
    if source is not None:
        return source
    source = JobSource(
        name=adapter_key,
        adapter_key=adapter_key,
        trust_tier=_DEFAULT_TRUST_TIER_BY_ADAPTER.get(adapter_key, "aggregator"),
    )
    db.add(source)
    await db.flush()
    return source


async def _ingest_source(db: AsyncSession, adapter_key: str) -> dict:
    source = await _get_or_create_source(db, adapter_key)

    adapter_cls = ADAPTER_REGISTRY.get(adapter_key)
    if adapter_cls is None:
        logger.warning("unknown_adapter", adapter_key=adapter_key)
        return {"fetched": 0, "accepted": 0, "duplicates": 0, "failures": 0, "status": "unknown_adapter"}

    adapter = adapter_cls()

    try:
        normalized_jobs: list[NormalizedJob] = await adapter.fetch_jobs(since=source.last_synced_at, limit=200)
    except Exception as exc:  # noqa: BLE001 - one source failing must not kill the whole run
        logger.error("adapter_fetch_failed", source=adapter_key, error=str(exc))
        source.failures_total += 1
        source.last_sync_status = "failed"
        source.last_synced_at = datetime.now(timezone.utc)
        await db.commit()
        return {"fetched": 0, "accepted": 0, "duplicates": 0, "failures": 1, "status": "failed"}

    fetched = len(normalized_jobs)
    accepted = 0
    duplicates = 0
    failures = 0
    accepted_jobs: list[Job] = []

    for nj in normalized_jobs:
        try:
            job = await normalize_and_persist(db, source, nj)
            canonical = await find_and_link_duplicates(db, job)
            if canonical is not None and canonical.id != job.id:
                duplicates += 1
            else:
                # Either genuinely new, or `job` itself won a trust-tier
                # promotion over a pre-existing lower-trust duplicate.
                accepted_jobs.append(job)
                accepted += 1
            await db.commit()
        except Exception as exc:  # noqa: BLE001 - a single bad record must not abort the batch
            await db.rollback()
            failures += 1
            logger.warning(
                "job_normalize_failed",
                source=adapter_key,
                source_job_id=getattr(nj, "source_job_id", None),
                error=str(exc),
            )

    to_embed = [j for j in accepted_jobs if j.embedding is None]
    if to_embed:
        try:
            provider = get_embedding_provider()
            texts = [job_embedding_text(j) for j in to_embed]
            vectors = await asyncio.to_thread(provider.embed, texts)
            for j, vec in zip(to_embed, vectors):
                j.embedding = vec
            await db.commit()
        except Exception as exc:  # noqa: BLE001 - embeddings are an enhancement, not required for correctness
            await db.rollback()
            failures += len(to_embed)
            logger.error("embedding_batch_failed", source=adapter_key, error=str(exc))

    source.jobs_fetched_total += fetched
    source.jobs_accepted_total += accepted
    source.duplicates_total += duplicates
    source.failures_total += failures
    source.last_synced_at = datetime.now(timezone.utc)
    if fetched == 0:
        source.last_sync_status = "warning"
    elif failures >= fetched:
        source.last_sync_status = "failed"
    elif failures > 0:
        source.last_sync_status = "warning"
    else:
        source.last_sync_status = "healthy"
    await db.commit()

    return {
        "fetched": fetched,
        "accepted": accepted,
        "duplicates": duplicates,
        "failures": failures,
        "status": source.last_sync_status,
    }


async def run_ingestion(db: AsyncSession) -> dict:
    settings = get_settings()
    summary: dict[str, dict] = {}
    for adapter_key in settings.job_sources_enabled_list:
        summary[adapter_key] = await _ingest_source(db, adapter_key)
    return summary


async def scheduler_loop() -> None:
    """Runs run_ingestion() on a fixed interval for as long as the app
    process is alive (settings.ingestion_interval_minutes, default 30) --
    section 61 of the product spec calls for periodic ingestion every 15-60
    minutes, and this is the in-process stand-in for that until a real task
    queue (Celery) takes over. This is what makes "add a job source's API
    keys and it just works" true: once JOB_SOURCES_ENABLED/ADZUNA_* are set
    and the backend restarts, real listings start flowing in automatically
    on this schedule with no manual `python -m app.jobs_ingestion.ingestion_worker`
    step required. A failed cycle is logged and never kills the loop.
    """
    from app.database import AsyncSessionLocal

    settings = get_settings()
    interval = max(1, settings.ingestion_interval_minutes) * 60
    logger.info(
        "ingestion_scheduler_started",
        interval_minutes=settings.ingestion_interval_minutes,
        sources=settings.job_sources_enabled_list,
    )
    while True:
        try:
            async with AsyncSessionLocal() as db:
                summary = await run_ingestion(db)
            logger.info("ingestion_cycle_complete", summary=summary)
        except Exception as exc:  # noqa: BLE001 - the scheduler must survive any single bad cycle
            logger.error("ingestion_cycle_failed", error=str(exc))
        await asyncio.sleep(interval)


if __name__ == "__main__":
    import sys

    from app.database import AsyncSessionLocal

    # Same rationale as app/main.py: real job text routinely contains emoji /
    # non-ASCII characters that a Windows console's default codepage can't
    # print, which would otherwise crash this standalone run.
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

    async def _main() -> None:
        async with AsyncSessionLocal() as db:
            result = await run_ingestion(db)
            print(result)

    asyncio.run(_main())
