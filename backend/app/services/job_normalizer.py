"""Turns a source-agnostic NormalizedJob (see app/jobs_ingestion/source_interface.py)
into persisted Job + Company + JobSkill rows.

Nothing here talks to a specific job board — that's the adapters' job. This
module only knows how to clean/normalize fields and write them to the DB in a
shape the dedup engine and matching engine can rely on.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs_ingestion.source_interface import NormalizedJob
from app.models.job import Company, Job, JobSkill, JobSource
from app.services.skill_extraction import extract_experience_range_from_text, extract_skills_from_text

# ---------------------------------------------------------------------------
# Trust tiers
# ---------------------------------------------------------------------------
# JobSource.trust_tier is a free string (see app/models/job.py comment:
# employer|ats|platform|aggregator). We define the ordering explicitly here so
# both "which job survives a dedup merge" (dedup_service) and "how much do we
# trust this posting's content" (Job.trust_score) can reference one canonical
# mapping. Unknown/unrecognized tiers are treated as the lowest priority.
TRUST_TIER_RANK: dict[str, int] = {"employer": 4, "ats": 3, "platform": 2, "aggregator": 1}
TRUST_TIER_SCORE: dict[str, float] = {"employer": 0.95, "ats": 0.80, "platform": 0.65, "aggregator": 0.50}
DEFAULT_TRUST_RANK = 0
DEFAULT_TRUST_SCORE = 0.40


def trust_score_for_tier(trust_tier: str | None) -> float:
    return TRUST_TIER_SCORE.get((trust_tier or "").lower(), DEFAULT_TRUST_SCORE)


def trust_rank_for_tier(trust_tier: str | None) -> int:
    return TRUST_TIER_RANK.get((trust_tier or "").lower(), DEFAULT_TRUST_RANK)


# ---------------------------------------------------------------------------
# Title normalization
# ---------------------------------------------------------------------------
_SENIORITY_WORDS = [
    "senior", "sr", "junior", "jr", "lead", "principal", "staff",
    "entry level", "entry-level",
]


def normalize_title(title: str) -> str:
    """Lowercase, strip seniority/location noise (typically parenthetical,
    e.g. "(Remote India)", "(Python/Django)"), collapse whitespace.

    This is intentionally lossy — it exists for grouping/search/dedup, not for
    display. The original `title` is always kept verbatim on the Job row.
    """
    t = title.lower()
    t = re.sub(r"\([^)]*\)", " ", t)  # drop parenthetical noise entirely
    t = re.sub(r"[^a-z0-9\s/+#-]", " ", t)  # drop stray punctuation
    for kw in _SENIORITY_WORDS:
        t = re.sub(rf"\b{re.escape(kw)}\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ---------------------------------------------------------------------------
# Company normalization
# ---------------------------------------------------------------------------
# Longest-first so multi-word suffixes ("private limited") are stripped before
# a shorter suffix ("limited") could partially match and leave a dangling
# "private".
_LEGAL_SUFFIXES = sorted(
    [
        "pvt ltd", "private limited", "pvt limited", "llc", "ltd", "limited",
        "corporation", "corp", "llp", "gmbh", "inc", "co",
    ],
    key=len,
    reverse=True,
)


def normalize_company_name(name: str) -> str:
    n = name.lower()
    n = re.sub(r"[.,]", "", n)  # "Inc." -> "inc" before suffix stripping
    n = re.sub(r"[^a-z0-9\s&-]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()

    changed = True
    while changed:
        changed = False
        for suf in _LEGAL_SUFFIXES:
            new_n = re.sub(rf"\b{re.escape(suf)}\b\s*$", "", n).strip()
            if new_n != n:
                n = new_n
                changed = True
    return re.sub(r"\s+", " ", n).strip()


# ---------------------------------------------------------------------------
# URL canonicalization (dedup matching only — never overwrites the stored,
# clickable application_url/source_url on the Job row)
# ---------------------------------------------------------------------------
def canonical_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------
def compute_freshness_status(posted_at: datetime, now: datetime | None = None) -> str:
    """Standalone so it can be recomputed at READ time too — a job's age (and
    therefore freshness bucket) keeps changing after it's inserted, but we
    still persist a snapshot on Job.freshness_status for cheap filtering."""
    from app.config import get_settings

    settings = get_settings()
    now = now or datetime.now(timezone.utc)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    age_days = (now - posted_at).total_seconds() / 86400
    if age_days <= settings.fresh_job_window_days:
        return "fresh"
    if age_days <= 14:
        return "active"
    if age_days <= 30:
        return "possibly_stale"
    return "expired"


# ---------------------------------------------------------------------------
# Content hash — cheap exact-repost check
# ---------------------------------------------------------------------------
def compute_content_hash(normalized_title: str, normalized_company: str, city: str | None, description: str) -> str:
    basis = f"{normalized_title}|{normalized_company}|{(city or '').strip().lower()}|{description[:500]}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Company get-or-create
# ---------------------------------------------------------------------------
async def get_or_create_company(db: AsyncSession, raw_name: str) -> Company:
    normalized = normalize_company_name(raw_name)
    stmt = select(Company).where(Company.normalized_name == normalized)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing
    company = Company(name=raw_name.strip(), normalized_name=normalized)
    db.add(company)
    await db.flush()
    return company


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def normalize_and_persist(db: AsyncSession, source: JobSource, normalized_job: NormalizedJob) -> Job:
    """Creates (and flushes, but does NOT commit) the Job row plus its
    JobSkill rows. The caller (ingestion_worker) owns the transaction boundary
    so a Job, its dedup link, and its JobDuplicate audit row can all commit or
    roll back together as one unit per source record.
    """
    now = datetime.now(timezone.utc)
    posted_at = normalized_job.posted_at or now
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)

    company = await get_or_create_company(db, normalized_job.company)
    normalized_title = normalize_title(normalized_job.title)
    content_hash = compute_content_hash(
        normalized_title, company.normalized_name, normalized_job.city, normalized_job.description
    )

    # Fallback extraction: only kicks in when the adapter itself supplied
    # nothing structured (Adzuna/seed data already has real fields and is
    # left untouched). See skill_extraction.py — this only ever reports a
    # skill/range literally present in the posting's own text, never a guess.
    full_text = "\n".join(
        p for p in (normalized_job.title, normalized_job.description, *normalized_job.requirements_required) if p
    )
    effective_skills = list(normalized_job.skills)
    if not effective_skills and not normalized_job.requirements_required:
        effective_skills = extract_skills_from_text(full_text)

    experience_min, experience_max = normalized_job.experience_min, normalized_job.experience_max
    if experience_min == 0 and experience_max == 0:
        extracted_range = extract_experience_range_from_text(full_text)
        if extracted_range:
            experience_min, experience_max = extracted_range

    job = Job(
        source_id=source.id,
        source_job_id=normalized_job.source_job_id,
        title=normalized_job.title,
        normalized_title=normalized_title,
        company_id=company.id,
        company_name_raw=normalized_job.company,
        description=normalized_job.description,
        responsibilities=normalized_job.responsibilities or None,
        requirements_required=normalized_job.requirements_required or None,
        requirements_preferred=normalized_job.requirements_preferred or None,
        area=normalized_job.area,
        city=normalized_job.city,
        state=normalized_job.state,
        country=normalized_job.country,
        work_mode=normalized_job.work_mode,
        employment_type=normalized_job.employment_type,
        experience_min=experience_min,
        experience_max=experience_max,
        domain=normalized_job.domain or None,
        education=normalized_job.education or None,
        salary_min=normalized_job.salary_min,
        salary_max=normalized_job.salary_max,
        currency=normalized_job.currency,
        posted_at=posted_at,
        last_seen_at=now,
        freshness_status=compute_freshness_status(posted_at, now),
        application_url=normalized_job.application_url,
        company_url=normalized_job.company_url,
        source_url=normalized_job.source_url,
        content_hash=content_hash,
        trust_score=trust_score_for_tier(source.trust_tier),
        is_verified=normalized_job.is_verified,
    )

    required_norm = {s.strip().lower() for s in (normalized_job.requirements_required or [])}
    skill_rows: list[JobSkill] = []
    seen_skills: set[str] = set()
    for skill_name in effective_skills:
        norm = skill_name.strip().lower()
        if not norm or norm in seen_skills:
            continue
        seen_skills.add(norm)
        skill_rows.append(
            JobSkill(
                name=skill_name.strip(),
                normalized_name=norm,
                is_required=(norm in required_norm) if required_norm else True,
            )
        )
    # Assign (not append-after-add) so the relationship is populated
    # in-memory immediately — with expire_on_commit=False (see
    # app/database.py) this lets job_embedding_text() read job.skills
    # synchronously right after this call without an extra DB round trip.
    job.skills = skill_rows

    db.add(job)
    await db.flush()
    return job
