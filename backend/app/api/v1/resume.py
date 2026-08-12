"""Resume upload, status, and analysis endpoints.

The upload endpoint saves the file, extracts text (fast, synchronous), and
returns immediately with processing_status="extracting". The actual AI
pipeline (2-3 sequential LLM calls + embeddings, routinely 30-90+ seconds)
runs as a FastAPI background task on its own DB session, and the client polls
GET /candidate/resume/{id}/status until it reaches "completed"/"failed".

This used to run the whole pipeline inline within the upload request, which
held one HTTP connection open for the entire duration -- fragile against any
proxy/browser/dev-server interruption over a minute-long request, and exactly
the kind of failure mode that could make the upload page appear to "hang or
vanish" with no clear error. Returning fast and polling is both more robust
and a better UX fit for the staged "processing" screen the frontend already
shows.

In production this should still move to a real task queue (Celery is already
a project dependency) so an in-flight resume survives a server restart --
today a `--reload`/crash mid-processing leaves a resume stuck in "analyzing"
until the user retries.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_provider import LLMError
from app.core.exceptions import NotFoundError
from app.database import AsyncSessionLocal, get_db
from app.dependencies import get_current_candidate
from app.models.candidate import CandidateProfile
from app.models.resume import ResumeAnalysis, ResumeFile
from app.schemas.resume import ResumeAnalysisOut, ResumeStatusOut, ResumeUploadOut
from app.services.resume_extractor import extract_text, save_resume_file, validate_resume_file
from app.services.resume_parser import process_resume

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["resume"])


async def _process_resume_background(candidate_id: uuid.UUID, resume_file_id: uuid.UUID) -> None:
    """Runs after the upload response has already been sent -- the request's
    `db` session is closed by then, so this opens its own. There's no request
    left to return a response to, so failures are caught and logged here
    rather than raised; process_resume() has already persisted the failure
    state on ResumeFile (via LLMError) before this ever needs to intervene.
    """
    async with AsyncSessionLocal() as db:
        try:
            candidate = await db.get(CandidateProfile, candidate_id)
            resume_file = await db.get(ResumeFile, resume_file_id)
            if candidate is None or resume_file is None:
                logger.error(
                    "resume_background_missing_row",
                    candidate_id=str(candidate_id),
                    resume_file_id=str(resume_file_id),
                )
                return
            await process_resume(db, candidate, resume_file)
        except LLMError:
            pass  # already marked failed + logged inside process_resume
        except Exception:  # noqa: BLE001 - last line of defense: never leave the row silently stuck in "analyzing"
            logger.exception("resume_background_unexpected_error", resume_file_id=str(resume_file_id))
            try:
                resume_file = await db.get(ResumeFile, resume_file_id)
                if resume_file is not None:
                    resume_file.processing_status = "failed"
                    resume_file.error_message = "An unexpected error occurred while analyzing your resume."
                    await db.commit()
            except Exception:  # noqa: BLE001
                logger.exception("resume_background_failure_write_failed", resume_file_id=str(resume_file_id))


@router.post("/candidate/resume/upload", response_model=ResumeUploadOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> ResumeFile:
    file_bytes = await file.read()
    filename = file.filename or "resume"
    ext = validate_resume_file(filename, file_bytes)

    storage_path, file_type = save_resume_file(candidate.id, filename, file_bytes)

    resume_file = ResumeFile(
        candidate_id=candidate.id,
        original_filename=filename,
        storage_path=storage_path,
        file_type=file_type or ext,
        file_size_bytes=len(file_bytes),
        processing_status="pending",
    )
    db.add(resume_file)
    await db.flush()

    try:
        text = extract_text(file_bytes, file_type)
    except ValueError as exc:
        resume_file.processing_status = "failed"
        resume_file.error_message = str(exc)[:1000]
        await db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    resume_file.extracted_text = text
    resume_file.processing_status = "extracting"
    await db.commit()
    await db.refresh(resume_file)

    background_tasks.add_task(_process_resume_background, candidate.id, resume_file.id)

    return resume_file


@router.get("/candidate/resume/{resume_id}/status", response_model=ResumeStatusOut)
async def get_resume_status(
    resume_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> ResumeStatusOut:
    resume_file = await db.get(ResumeFile, resume_id)
    if resume_file is None or resume_file.candidate_id != candidate.id:
        raise NotFoundError("Resume not found")
    # Built explicitly rather than returned as the ORM row: ResumeStatusOut
    # has no `model_config = ConfigDict(from_attributes=True)`, so it can't
    # reliably validate directly from a SQLAlchemy instance.
    return ResumeStatusOut(
        id=resume_file.id,
        processing_status=resume_file.processing_status,
        error_message=resume_file.error_message,
    )


@router.get("/candidate/resume/analysis", response_model=ResumeAnalysisOut)
async def get_latest_resume_analysis(
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> ResumeAnalysis:
    result = await db.execute(
        select(ResumeAnalysis)
        .where(ResumeAnalysis.candidate_id == candidate.id)
        .order_by(ResumeAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise NotFoundError("No resume analysis found yet. Upload a resume first.")
    return analysis
