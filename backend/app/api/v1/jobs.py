"""Job search, natural-language search, and job detail endpoints.

/jobs/search and /jobs/search/natural-language require an authenticated
candidate (results are personalized — ranking_service scores every job
against the caller's profile). /jobs/{job_id} is intentionally the
exception: it accepts an OPTIONAL token so an anonymous visitor can still
view a job (e.g. from a shared link) and simply won't get match_score/
breakdown/reason back.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_candidate, oauth2_scheme
from app.models.activity import SearchHistory
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.user import User
from app.schemas.job import (
    EstimatedSalaryOut,
    JobDetailOut,
    JobFeedResponse,
    JobSearchRequest,
    MatchBreakdown,
    MatchReasonOut,
    NaturalLanguageSearchRequest,
)
from app.security import decode_token
from app.services.dedup_service import get_other_sources
from app.services.matching_service import build_match_reason, match_scores_dict, score_job_for_candidate
from app.services.nl_search_service import parse_natural_language_query
from app.services.ranking_service import (
    decode_cursor,
    encode_cursor,
    get_recommended_jobs,
    load_candidate_with_relations,
    upsert_match,
    upsert_reason,
)
from app.services.salary_service import SalaryEstimateUnavailable, get_estimated_salary

router = APIRouter(tags=["jobs"])


async def _optional_candidate(
    token: str | None = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> CandidateProfile | None:
    """Same decode logic as app.dependencies.get_current_candidate, but never
    raises — an invalid/missing token just means "anonymous viewer" here."""
    if not token:
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return None
    user = await db.get(User, uid)
    if user is None or not user.is_active:
        return None
    result = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    return result.scalar_one_or_none()


@router.post("/jobs/search", response_model=JobFeedResponse)
async def search_jobs(
    payload: JobSearchRequest,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> JobFeedResponse:
    offset = decode_cursor(payload.cursor)
    limit = max(1, payload.limit)

    all_cards = await get_recommended_jobs(db, candidate, payload)
    page = all_cards[offset : offset + limit]
    next_cursor = encode_cursor(offset + limit) if offset + limit < len(all_cards) else None

    return JobFeedResponse(items=page, next_cursor=next_cursor, total_estimate=len(all_cards))


@router.post("/jobs/search/natural-language", response_model=JobFeedResponse)
async def search_jobs_natural_language(
    payload: NaturalLanguageSearchRequest,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> JobFeedResponse:
    # LLMError propagates to app.main's global handler -> clean 503. We do NOT
    # catch it here: silently falling back to unfiltered results would be
    # more misleading than a clear "search AI unavailable" error.
    parsed = await parse_natural_language_query(payload.query)

    search_request = JobSearchRequest(
        query=" ".join(parsed.role) if parsed.role else None,
        city=parsed.location[0] if parsed.location else None,
        work_mode=parsed.work_mode or None,
        employment_type=parsed.employment_type or None,
        experience_min=parsed.experience_min,
        experience_max=parsed.experience_max,
        skills=parsed.skills or None,
        posted_within_days=parsed.posted_within_days,
        sort_by="best_match",
        limit=20,
    )

    all_cards = await get_recommended_jobs(db, candidate, search_request)
    page = all_cards[: search_request.limit]

    db.add(
        SearchHistory(
            candidate_id=candidate.id,
            raw_query=payload.query,
            parsed_filters=parsed.model_dump(),
            result_count=len(all_cards),
        )
    )
    await db.commit()

    next_cursor = encode_cursor(search_request.limit) if len(all_cards) > search_request.limit else None
    return JobFeedResponse(items=page, next_cursor=next_cursor, total_estimate=len(all_cards))


@router.get("/jobs/{job_id}", response_model=JobDetailOut)
async def get_job_detail(
    job_id: uuid.UUID,
    candidate: CandidateProfile | None = Depends(_optional_candidate),
    db: AsyncSession = Depends(get_db),
) -> JobDetailOut:
    job = await db.get(Job, job_id, options=[selectinload(Job.skills)])
    if job is not None and job.is_duplicate and job.canonical_job_id:
        job = await db.get(Job, job.canonical_job_id, options=[selectinload(Job.skills)])
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    other_sources = await get_other_sources(db, job.id)

    detail = JobDetailOut(
        id=job.id,
        title=job.title,
        company_name=job.company_name_raw,
        company_url=job.company_url,
        description=job.description,
        responsibilities=job.responsibilities,
        requirements_required=job.requirements_required,
        requirements_preferred=job.requirements_preferred,
        area=job.area,
        city=job.city,
        state=job.state,
        country=job.country,
        work_mode=job.work_mode,
        employment_type=job.employment_type,
        experience_min=job.experience_min,
        experience_max=job.experience_max,
        domain=job.domain,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        currency=job.currency,
        posted_at=job.posted_at,
        application_url=job.application_url,
        source_url=job.source_url,
        is_verified=job.is_verified,
        trust_score=job.trust_score,
        other_sources=other_sources,
    )

    if candidate is not None:
        loaded_candidate = await load_candidate_with_relations(db, candidate)
        match = await score_job_for_candidate(db, loaded_candidate, job)
        match = await upsert_match(db, match)
        scores = match_scores_dict(match)
        reason_dict = build_match_reason(loaded_candidate, job, scores)
        reason_row = await upsert_reason(db, match, reason_dict)
        await db.commit()

        detail.match_score = match.score
        detail.match_category = match.category
        detail.match_breakdown = MatchBreakdown(
            skills=match.skills_score,
            experience=match.experience_score,
            role=match.role_score,
            semantic=match.semantic_score,
            location=match.location_score,
            domain=match.domain_score,
            education=match.education_score,
            work_mode=match.work_mode_score,
            recency=match.recency_score,
            trust=match.trust_score,
        )
        detail.match_reason = MatchReasonOut.model_validate(reason_row)

    return detail


@router.get("/jobs/{job_id}/estimated-salary", response_model=EstimatedSalaryOut)
async def get_job_estimated_salary(
    job_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> EstimatedSalaryOut:
    """Live market-rate salary lookup (JSearch salary APIs) — called only when
    a candidate actually requests it, never during bulk ingestion, and never
    written back onto the Job row. If the job already has a real posted
    salary, that's returned as-is with is_estimate=False rather than spending
    an API call on a redundant estimate."""
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.salary_min is not None or job.salary_max is not None:
        return EstimatedSalaryOut(
            job_title=job.title,
            location=job.city,
            min_salary=job.salary_min,
            max_salary=job.salary_max,
            currency=job.currency,
            is_estimate=False,
        )

    location = job.city or job.state or job.country
    try:
        estimate = await get_estimated_salary(job.title, location, job.company_name_raw)
    except SalaryEstimateUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No salary estimate available for this role: {exc}",
        ) from exc

    return EstimatedSalaryOut(**estimate, is_estimate=True)
