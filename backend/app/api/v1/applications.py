import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateResourceError, NotFoundError
from app.database import get_db
from app.dependencies import get_current_candidate
from app.models.application import Application, SavedJob
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.schemas.application import (
    ApplicationOut,
    ApplicationStatusUpdate,
    ApplyClickRequest,
    SavedJobOut,
)

router = APIRouter(tags=["applications"])

VALID_STATUSES = {
    "apply_clicked",
    "saved",
    "applied",
    "screening",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
}


@router.post("/jobs/{job_id}/save", response_model=SavedJobOut, status_code=status.HTTP_201_CREATED)
async def save_job(
    job_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> SavedJob:
    job = await db.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")

    existing = await db.execute(
        select(SavedJob).where(SavedJob.candidate_id == candidate.id, SavedJob.job_id == job_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise DuplicateResourceError("Job already saved")

    saved = SavedJob(candidate_id=candidate.id, job_id=job_id)
    db.add(saved)
    await db.commit()
    await db.refresh(saved)
    return saved


@router.delete("/jobs/{job_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_job(
    job_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(SavedJob).where(SavedJob.candidate_id == candidate.id, SavedJob.job_id == job_id)
    )
    saved = result.scalar_one_or_none()
    if saved is None:
        raise NotFoundError("Saved job not found")
    await db.delete(saved)
    await db.commit()


@router.get("/saved-jobs", response_model=list[SavedJobOut])
async def list_saved_jobs(
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> list[SavedJob]:
    result = await db.execute(
        select(SavedJob).where(SavedJob.candidate_id == candidate.id).order_by(SavedJob.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/jobs/{job_id}/apply-click", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def apply_click(
    job_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> Application:
    """Records that the candidate opened the authentic application URL. This
    does NOT mark the job as applied — per spec section 107, only an explicit
    status update does that."""
    job = await db.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")

    result = await db.execute(
        select(Application).where(Application.candidate_id == candidate.id, Application.job_id == job_id)
    )
    application = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if application is None:
        application = Application(
            candidate_id=candidate.id,
            job_id=job_id,
            application_url=job.application_url,
            status="apply_clicked",
            apply_clicked_at=now,
        )
        db.add(application)
    else:
        application.apply_clicked_at = now

    await db.commit()
    await db.refresh(application)
    return application


@router.get("/applications", response_model=list[ApplicationOut])
async def list_applications(
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> list[Application]:
    result = await db.execute(
        select(Application).where(Application.candidate_id == candidate.id).order_by(Application.updated_at.desc())
    )
    return list(result.scalars().all())


@router.patch("/applications/{application_id}", response_model=ApplicationOut)
async def update_application_status(
    application_id: uuid.UUID,
    payload: ApplicationStatusUpdate,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> Application:
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid status: {payload.status}")

    application = await db.get(Application, application_id)
    if application is None or application.candidate_id != candidate.id:
        raise NotFoundError("Application not found")

    application.status = payload.status
    if payload.notes is not None:
        application.notes = payload.notes
    if payload.status == "applied" and application.applied_at is None:
        application.applied_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(application)
    return application
