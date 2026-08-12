"""The default personalized feed (product spec sections 43/98) plus
lightweight feedback capture. Both endpoints require an authenticated
candidate — recommendations are inherently personalized.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.dependencies import get_current_candidate
from app.models.activity import RecommendationHistory
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.schemas.job import JobFeedResponse, JobSearchRequest
from app.services.ranking_service import decode_cursor, encode_cursor, get_recommended_jobs, load_candidate_with_relations

router = APIRouter(tags=["recommendations"])


class JobFeedbackRequest(BaseModel):
    action: Literal["not_relevant", "interested", "hidden_type"]


@router.get("/jobs/recommended", response_model=JobFeedResponse)
async def get_recommended(
    fresh_only: bool = Query(False, description="Restrict to jobs posted within the fresh window only."),
    explore_older: bool = Query(False, description="Widen beyond the usual freshness window to surface older jobs too."),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> JobFeedResponse:
    # get_current_candidate doesn't eager-load relationships; touching
    # candidate.preferences synchronously here (before get_recommended_jobs
    # gets a chance to do its own eager load) would raise MissingGreenlet.
    candidate = await load_candidate_with_relations(db, candidate)
    prefs = candidate.preferences

    posted_within_days = None
    if fresh_only:
        posted_within_days = get_settings().fresh_job_window_days
    elif explore_older:
        posted_within_days = 90  # deliberately wider than ranking_service's own auto-widening (up to 30)

    search_request = JobSearchRequest(
        work_mode=prefs.work_mode if prefs and prefs.work_mode else None,
        employment_type=prefs.employment_type if prefs and prefs.employment_type else None,
        posted_within_days=posted_within_days,
        min_match_score=prefs.min_match_score if prefs else None,
        sort_by="best_match",
        limit=limit,
    )

    offset = decode_cursor(cursor)
    all_cards = await get_recommended_jobs(db, candidate, search_request)
    page = all_cards[offset : offset + limit]
    next_cursor = encode_cursor(offset + limit) if offset + limit < len(all_cards) else None

    return JobFeedResponse(items=page, next_cursor=next_cursor, total_estimate=len(all_cards))


@router.post("/jobs/{job_id}/feedback", status_code=204, response_model=None)
async def submit_job_feedback(
    job_id: uuid.UUID,
    payload: JobFeedbackRequest,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> None:
    job = await db.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")

    db.add(RecommendationHistory(candidate_id=candidate.id, job_id=job_id, action=payload.action))
    await db.commit()
