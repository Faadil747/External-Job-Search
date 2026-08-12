"""Orchestration layer (product spec sections 44/52): turns a JobSearchRequest
into a scored, sorted, diversified list of JobCardOut, and persists the
JobMatch/MatchReason rows behind them. Both /jobs/search and /jobs/recommended
call get_recommended_jobs() so filter/scoring/pagination logic lives in
exactly one place.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.embedding_provider import get_embedding_provider
from app.config import get_settings
from app.models.application import SavedJob
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.match import JobMatch, MatchReason
from app.rag.vector_store import get_vector_store
from app.schemas.job import JobCardOut, JobSearchRequest
from app.services.embedding_service import candidate_embedding_text
from app.services.job_normalizer import compute_freshness_status
from app.services.matching_service import build_match_reason, match_scores_dict, score_job_for_candidate

_FRESHNESS_RANK = {"fresh": 3, "active": 2, "possibly_stale": 1, "expired": 0}
_WIDEN_WINDOWS_DAYS = (14, 30)  # tried only if settings.fresh_job_window_days yields zero results
_SEMANTIC_PREFILTER_THRESHOLD = 200  # pool sizes above this get an ANN prefilter before full scoring
_DIVERSITY_WINDOW = 20
# Matches CandidatePreference.min_match_score's own column default (see
# app/models/candidate.py) -- used as the effective floor when a candidate
# has never explicitly saved a preferences row at all (None, not merely
# "unset"), so an incomplete/never-touched preferences record can never mean
# "show every job regardless of fit."
_DEFAULT_MIN_MATCH_SCORE = 50
_DIVERSITY_MAX_CONSECUTIVE = 3


# ---------------------------------------------------------------------------
# Cursor pagination
# ---------------------------------------------------------------------------
# Scheme: cursor is base64(str(offset)) into the already-scored, already-
# sorted result pool for this request's filters. Simple and stateless; the
# tradeoff is that the pool is recomputed (cheap for this dataset size) on
# every page request rather than persisted server-side between pages.
def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(base64.urlsafe_b64decode(cursor.encode()).decode()))
    except Exception:  # noqa: BLE001 - a malformed cursor just restarts from the top
        return 0


# ---------------------------------------------------------------------------
# get_current_candidate (app/dependencies.py) returns a CandidateProfile
# without any relationships eagerly loaded. matching_service/embedding_service
# touch skills/experience/education/projects/preferences synchronously, which
# would raise MissingGreenlet under AsyncSession unless loaded up front.
# ---------------------------------------------------------------------------
async def load_candidate_with_relations(db: AsyncSession, candidate: CandidateProfile) -> CandidateProfile:
    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.id == candidate.id)
        .options(
            selectinload(CandidateProfile.skills),
            selectinload(CandidateProfile.experience),
            selectinload(CandidateProfile.education),
            selectinload(CandidateProfile.projects),
            selectinload(CandidateProfile.preferences),
        )
    )
    return (await db.execute(stmt)).scalar_one()


async def _ensure_candidate_embedding(db: AsyncSession, candidate: CandidateProfile) -> None:
    if candidate.profile_embedding is not None:
        return
    text = candidate_embedding_text(candidate)
    if not text.strip():
        return
    provider = get_embedding_provider()
    vector = await asyncio.to_thread(provider.embed_one, text)
    candidate.profile_embedding = vector
    await db.flush()


# ---------------------------------------------------------------------------
# Hard filters + freshness-first pool selection
# ---------------------------------------------------------------------------
def _apply_hard_filters(stmt, filters: JobSearchRequest):
    if filters.city:
        stmt = stmt.where(Job.city.ilike(filters.city))
    if filters.state:
        stmt = stmt.where(Job.state.ilike(filters.state))
    if filters.country:
        stmt = stmt.where(Job.country.ilike(filters.country))
    if filters.work_mode:
        stmt = stmt.where(Job.work_mode.in_(filters.work_mode))
    if filters.employment_type:
        stmt = stmt.where(Job.employment_type.in_(filters.employment_type))
    if filters.experience_min is not None:
        stmt = stmt.where(Job.experience_max >= filters.experience_min)
    if filters.experience_max is not None:
        stmt = stmt.where(Job.experience_min <= filters.experience_max)
    if filters.salary_min is not None:
        from sqlalchemy import or_

        stmt = stmt.where(or_(Job.salary_max.is_(None), Job.salary_max >= filters.salary_min))
    return stmt


async def _fetch_pool(db: AsyncSession, filters: JobSearchRequest, now: datetime) -> list[Job]:
    base_stmt = select(Job).options(selectinload(Job.skills)).where(Job.is_duplicate.is_(False))
    base_stmt = _apply_hard_filters(base_stmt, filters)

    if filters.posted_within_days is not None:
        cutoff = now - timedelta(days=filters.posted_within_days)
        stmt = base_stmt.where(Job.posted_at >= cutoff)
        return list((await db.execute(stmt)).scalars().all())

    # Freshness-first (product requirement): the default feed is the top
    # matches posted within settings.fresh_job_window_days (3 days) — this is
    # a strict default, not a soft preference. We only widen the window if
    # that pool is genuinely EMPTY, so a real (large) job source keeps a true
    # "last 3 days" feed; the small dev/seed dataset falling short of some
    # arbitrary minimum count is not, by itself, a reason to dilute it with
    # older jobs. "Explore older" is an explicit, separate action
    # (posted_within_days set directly) per spec section 20, not an implicit
    # fallback.
    settings = get_settings()
    for window_days in (settings.fresh_job_window_days, *_WIDEN_WINDOWS_DAYS):
        cutoff = now - timedelta(days=window_days)
        stmt = base_stmt.where(Job.posted_at >= cutoff)
        pool = list((await db.execute(stmt)).scalars().all())
        if pool:
            return pool
    # Still nothing at all — drop the time constraint entirely rather than
    # return a completely empty feed.
    return list((await db.execute(base_stmt)).scalars().all())


async def _semantic_prefilter(
    db: AsyncSession, candidate: CandidateProfile, pool: list[Job]
) -> list[Job]:
    """Hybrid retrieval (spec sections 26-28): when the hard-filtered pool is
    large, use the vector store's pgvector ANN search to cut it down to the
    most semantically relevant jobs BEFORE running the full deterministic
    scorer over every one of them. Below the threshold, scoring the whole
    pool directly is both cheap and more precise (exact cosine, not
    approximate), so this is skipped -- this is why it never fires against
    the current small seed dataset, but it's what keeps recommendations fast
    once a real job source brings the table to real-world size.
    """
    if len(pool) <= _SEMANTIC_PREFILTER_THRESHOLD or candidate.profile_embedding is None:
        return pool
    store = get_vector_store()
    ranked = await store.search_jobs(db, candidate.profile_embedding, top_k=_SEMANTIC_PREFILTER_THRESHOLD)
    keep_ids = {job_id for job_id, _similarity in ranked}
    narrowed = [job for job in pool if job.id in keep_ids]
    # Guard against an empty/degenerate vector search result silently
    # emptying the feed -- fall back to the unfiltered pool rather than risk
    # that.
    return narrowed or pool


def _post_filter(pool: list[Job], filters: JobSearchRequest) -> list[Job]:
    """Domain/skills/free-text query filters aren't part of the "hard SQL
    filter" set called out by the spec (location/work_mode/employment_type/
    posted_within_days/experience range) — applying them in Python here
    avoids fragile JSONB containment SQL for a dataset this size."""
    if filters.domain:
        wanted = {d.lower() for d in filters.domain}
        pool = [j for j in pool if j.domain and wanted & {d.lower() for d in j.domain}]
    if filters.skills:
        wanted = {s.lower() for s in filters.skills}
        pool = [j for j in pool if {sk.normalized_name for sk in j.skills} & wanted]
    if filters.query:
        q = filters.query.lower()
        pool = [j for j in pool if q in j.title.lower() or q in (j.description or "").lower()]
    return pool


# ---------------------------------------------------------------------------
# Diversity control: cap consecutive same-company jobs within the top N
# ---------------------------------------------------------------------------
def _apply_diversity_cap(
    ranked: list[tuple[Job, JobMatch]], window: int = _DIVERSITY_WINDOW, max_consecutive: int = _DIVERSITY_MAX_CONSECUTIVE
) -> list[tuple[Job, JobMatch]]:
    remaining = list(ranked)
    result: list[tuple[Job, JobMatch]] = []
    streak_company = None
    streak_count = 0

    while remaining:
        take_index = 0
        if len(result) < window and streak_count >= max_consecutive:
            for i, (job, _match) in enumerate(remaining):
                if job.company_id != streak_company:
                    take_index = i
                    break
            # if nothing else exists (all remaining are the same company),
            # take_index stays 0 and we just accept the streak continuing.
        job, match = remaining.pop(take_index)
        if job.company_id == streak_company:
            streak_count += 1
        else:
            streak_company = job.company_id
            streak_count = 1
        result.append((job, match))
    return result


# ---------------------------------------------------------------------------
# Upserts (also reused by the /jobs/{id} detail endpoint)
# ---------------------------------------------------------------------------
_MATCH_COMPONENT_FIELDS = [
    "score", "category", "skills_score", "experience_score", "role_score", "semantic_score",
    "location_score", "domain_score", "education_score", "work_mode_score", "recency_score", "trust_score",
]


async def upsert_match(db: AsyncSession, new_match: JobMatch) -> JobMatch:
    """Recompute-on-every-request is intentionally simple for this phase.
    TODO(perf): cache by (candidate.updated_at, job.updated_at) and skip
    rescoring when neither changed since the last stored JobMatch."""
    stmt = select(JobMatch).where(
        JobMatch.candidate_id == new_match.candidate_id, JobMatch.job_id == new_match.job_id
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        for field in _MATCH_COMPONENT_FIELDS:
            setattr(existing, field, getattr(new_match, field))
        await db.flush()
        return existing
    db.add(new_match)
    await db.flush()
    return new_match


async def upsert_reason(db: AsyncSession, match: JobMatch, reason: dict) -> MatchReason:
    stmt = select(MatchReason).where(MatchReason.match_id == match.id)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        for key, value in reason.items():
            setattr(existing, key, value)
        await db.flush()
        return existing
    row = MatchReason(match_id=match.id, **reason)
    db.add(row)
    await db.flush()
    return row


async def _fetch_saved_job_ids(db: AsyncSession, candidate_id) -> set:
    rows = await db.execute(select(SavedJob.job_id).where(SavedJob.candidate_id == candidate_id))
    return {row[0] for row in rows.all()}


def _to_job_card(job: Job, match: JobMatch, reason: dict, saved_job_ids: set) -> JobCardOut:
    top_skills = [s.name for s in job.skills[:5]] if job.skills else []
    return JobCardOut(
        id=job.id,
        title=job.title,
        company_name=job.company_name_raw,
        company_logo_url=None,
        city=job.city,
        state=job.state,
        country=job.country,
        work_mode=job.work_mode,
        employment_type=job.employment_type,
        experience_min=job.experience_min,
        experience_max=job.experience_max,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        currency=job.currency,
        posted_at=job.posted_at,
        top_skills=top_skills,
        match_score=match.score,
        match_category=match.category,
        why_it_matches=reason.get("overall_reason"),
        is_verified=job.is_verified,
        is_saved=job.id in saved_job_ids,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _sort_key_for(sort_by: str, now: datetime):
    """Returns a (key_fn, reverse) pair for the requested sort_by. All keys
    return tuples so ties break deterministically instead of depending on
    Python's stable-sort input order."""

    def freshness(job: Job) -> int:
        return _FRESHNESS_RANK.get(compute_freshness_status(job.posted_at, now), 0)

    if sort_by == "newest":
        return (lambda pair: (pair[0].posted_at, pair[1].score), True)
    if sort_by == "highest_salary":
        # Jobs without salary data sort last, not above real high salaries.
        return (
            lambda pair: (
                pair[0].salary_max is not None or pair[0].salary_min is not None,
                pair[0].salary_max or pair[0].salary_min or 0,
                pair[1].score,
            ),
            True,
        )
    if sort_by == "closest_location":
        return (lambda pair: (pair[1].location_score, pair[1].score), True)
    # "best_match" (default/unknown values fall back here too)
    return (lambda pair: (pair[1].score, freshness(pair[0]), pair[0].trust_score), True)


async def get_recommended_jobs(db: AsyncSession, candidate: CandidateProfile, filters: JobSearchRequest) -> list[JobCardOut]:
    """Full pipeline: hard-filter -> freshness-first pool -> score -> STRICT
    min-score filter -> sort -> diversify -> persist JobMatch/MatchReason ->
    return cards.

    min_match_score (from filters, or the candidate's saved preference,
    default 50) is a HARD filter: a job that doesn't clear it is not shown,
    full stop. This used to fall back to "show everything" when nothing
    cleared the bar, which defeated the entire point of a *personalized*
    feed — a candidate's recommendations must only ever contain roles
    genuinely tied to their own profile, never padded with unrelated jobs
    just to avoid an empty screen. An empty result here is a real, honest
    answer ("nothing suitable posted in this window yet") and the frontend's
    empty state already guides the candidate toward next steps (widen
    location, look further back, etc.) rather than silently substituting
    irrelevant jobs for suitable ones.
    """
    now = datetime.now(timezone.utc)

    candidate = await load_candidate_with_relations(db, candidate)
    await _ensure_candidate_embedding(db, candidate)

    pool = await _fetch_pool(db, filters, now)
    pool = _post_filter(pool, filters)
    pool = await _semantic_prefilter(db, candidate, pool)
    if not pool:
        return []

    scored: list[tuple[Job, JobMatch]] = []
    for job in pool:
        match = await score_job_for_candidate(db, candidate, job)
        scored.append((job, match))

    threshold = filters.min_match_score
    if threshold is None:
        threshold = candidate.preferences.min_match_score if candidate.preferences else _DEFAULT_MIN_MATCH_SCORE
    if threshold:
        scored = [pair for pair in scored if pair[1].score >= threshold]
    if not scored:
        return []

    key_fn, reverse = _sort_key_for(filters.sort_by, now)
    scored.sort(key=key_fn, reverse=reverse)
    scored = _apply_diversity_cap(scored)

    saved_job_ids = await _fetch_saved_job_ids(db, candidate.id)

    cards: list[JobCardOut] = []
    for job, match in scored:
        match = await upsert_match(db, match)
        reason = build_match_reason(candidate, job, match_scores_dict(match))
        await upsert_reason(db, match, reason)
        cards.append(_to_job_card(job, match, reason, saved_job_ids))

    await db.commit()
    return cards
