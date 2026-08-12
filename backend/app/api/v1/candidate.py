"""Candidate profile, skills, experience, education, projects, and
preferences CRUD endpoints. All routes require an authenticated candidate.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_candidate
from app.models.candidate import CandidateProfile
from app.schemas.candidate import (
    CandidateProfileOut,
    CandidateProfileUpdate,
    EducationIn,
    EducationOut,
    ExperienceIn,
    ExperienceOut,
    PreferencesIn,
    PreferencesOut,
    ProjectIn,
    ProjectOut,
    SkillIn,
    SkillOut,
)
from app.services import candidate_service

router = APIRouter(tags=["candidate"])


# ==========================================================================
# Profile
# ==========================================================================


@router.get("/candidate/profile", response_model=CandidateProfileOut)
async def get_profile(
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    return await candidate_service.get_full_profile(db, candidate.id)


@router.put("/candidate/profile", response_model=CandidateProfileOut)
async def update_profile(
    payload: CandidateProfileUpdate,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    return await candidate_service.update_profile(db, candidate, payload)


# ==========================================================================
# Skills
# ==========================================================================


@router.post("/candidate/skills", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def create_skill(
    payload: SkillIn,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    return await candidate_service.create_skill(db, candidate, payload)


@router.put("/candidate/skills/{skill_id}", response_model=SkillOut)
async def update_skill(
    skill_id: uuid.UUID,
    payload: SkillIn,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    return await candidate_service.update_skill(db, candidate, skill_id, payload)


@router.delete("/candidate/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_skill(
    skill_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> None:
    await candidate_service.delete_skill(db, candidate, skill_id)


# ==========================================================================
# Experience
# ==========================================================================


@router.post("/candidate/experience", response_model=ExperienceOut, status_code=status.HTTP_201_CREATED)
async def create_experience(
    payload: ExperienceIn,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    return await candidate_service.create_experience(db, candidate, payload)


@router.put("/candidate/experience/{experience_id}", response_model=ExperienceOut)
async def update_experience(
    experience_id: uuid.UUID,
    payload: ExperienceIn,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    return await candidate_service.update_experience(db, candidate, experience_id, payload)


@router.delete("/candidate/experience/{experience_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_experience(
    experience_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> None:
    await candidate_service.delete_experience(db, candidate, experience_id)


# ==========================================================================
# Education
# ==========================================================================


@router.post("/candidate/education", response_model=EducationOut, status_code=status.HTTP_201_CREATED)
async def create_education(
    payload: EducationIn,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    return await candidate_service.create_education(db, candidate, payload)


@router.put("/candidate/education/{education_id}", response_model=EducationOut)
async def update_education(
    education_id: uuid.UUID,
    payload: EducationIn,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    return await candidate_service.update_education(db, candidate, education_id, payload)


@router.delete("/candidate/education/{education_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_education(
    education_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> None:
    await candidate_service.delete_education(db, candidate, education_id)


# ==========================================================================
# Projects
# ==========================================================================


@router.post("/candidate/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectIn,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    return await candidate_service.create_project(db, candidate, payload)


@router.put("/candidate/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectIn,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    return await candidate_service.update_project(db, candidate, project_id, payload)


@router.delete("/candidate/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_project(
    project_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> None:
    await candidate_service.delete_project(db, candidate, project_id)


# ==========================================================================
# Preferences
# ==========================================================================


@router.get("/candidate/preferences", response_model=PreferencesOut)
async def get_preferences(
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    return await candidate_service.get_or_create_preferences(db, candidate)


@router.put("/candidate/preferences", response_model=PreferencesOut)
async def update_preferences(
    payload: PreferencesIn,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    return await candidate_service.upsert_preferences(db, candidate, payload)
