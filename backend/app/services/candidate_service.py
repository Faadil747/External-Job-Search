"""Business logic for candidate profile / skills / experience / education /
projects / preferences CRUD.

Reuses the experience-overlap and profile-completion helpers from
resume_parser.py so the numbers stay consistent regardless of whether they
were last touched by a resume upload or a manual edit here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.candidate import (
    CandidateEducation,
    CandidateExperience,
    CandidatePreference,
    CandidateProfile,
    CandidateProject,
    CandidateSkill,
)
from app.schemas.candidate import (
    CandidateProfileUpdate,
    EducationIn,
    ExperienceIn,
    PreferencesIn,
    ProjectIn,
    SkillIn,
)
from app.services.resume_parser import (
    duration_months,
    normalize_skill_category,
    recompute_experience_totals,
    recompute_profile_completion,
)


async def get_full_profile(db: AsyncSession, candidate_id: uuid.UUID) -> CandidateProfile:
    result = await db.execute(
        select(CandidateProfile)
        .options(
            selectinload(CandidateProfile.skills),
            selectinload(CandidateProfile.experience),
            selectinload(CandidateProfile.education),
            selectinload(CandidateProfile.projects),
            selectinload(CandidateProfile.preferences),
        )
        .where(CandidateProfile.id == candidate_id)
    )
    return result.scalar_one()


async def update_profile(
    db: AsyncSession, candidate: CandidateProfile, payload: CandidateProfileUpdate
) -> CandidateProfile:
    # Candidate's manual edits always take priority: only fields the client
    # actually sent, and that aren't null, get applied.
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in data.items():
        setattr(candidate, field, value)
    await recompute_profile_completion(db, candidate)
    await db.commit()
    return await get_full_profile(db, candidate.id)


# ==========================================================================
# Skills
# ==========================================================================


async def _get_owned_skill(db: AsyncSession, candidate_id: uuid.UUID, skill_id: uuid.UUID) -> CandidateSkill:
    skill = await db.get(CandidateSkill, skill_id)
    if skill is None or skill.candidate_id != candidate_id:
        raise NotFoundError("Skill not found")
    return skill


async def create_skill(db: AsyncSession, candidate: CandidateProfile, payload: SkillIn) -> CandidateSkill:
    name = payload.name.strip()
    skill = CandidateSkill(
        candidate_id=candidate.id,
        name=name,
        normalized_name=name.lower(),
        category=normalize_skill_category(payload.category),
        proficiency=payload.proficiency,
        months_experience=payload.months_experience,
        source="manual",
    )
    db.add(skill)
    await db.flush()
    await recompute_profile_completion(db, candidate)
    await db.commit()
    await db.refresh(skill)
    return skill


async def update_skill(
    db: AsyncSession, candidate: CandidateProfile, skill_id: uuid.UUID, payload: SkillIn
) -> CandidateSkill:
    skill = await _get_owned_skill(db, candidate.id, skill_id)
    name = payload.name.strip()
    skill.name = name
    skill.normalized_name = name.lower()
    skill.category = normalize_skill_category(payload.category)
    skill.proficiency = payload.proficiency
    skill.months_experience = payload.months_experience
    skill.source = "manual"
    await db.commit()
    await db.refresh(skill)
    return skill


async def delete_skill(db: AsyncSession, candidate: CandidateProfile, skill_id: uuid.UUID) -> None:
    skill = await _get_owned_skill(db, candidate.id, skill_id)
    await db.delete(skill)
    await db.flush()
    await recompute_profile_completion(db, candidate)
    await db.commit()


# ==========================================================================
# Experience
# ==========================================================================


async def _get_owned_experience(
    db: AsyncSession, candidate_id: uuid.UUID, experience_id: uuid.UUID
) -> CandidateExperience:
    exp = await db.get(CandidateExperience, experience_id)
    if exp is None or exp.candidate_id != candidate_id:
        raise NotFoundError("Experience entry not found")
    return exp


async def create_experience(
    db: AsyncSession, candidate: CandidateProfile, payload: ExperienceIn
) -> CandidateExperience:
    exp = CandidateExperience(
        candidate_id=candidate.id,
        company=payload.company,
        designation=payload.designation,
        start_date=payload.start_date,
        end_date=None if payload.is_current else payload.end_date,
        is_current=payload.is_current,
        duration_months=duration_months(payload.start_date, payload.end_date, payload.is_current),
        responsibilities=payload.responsibilities or None,
        technologies=payload.technologies or None,
        domain=payload.domain or None,
        achievements=payload.achievements or None,
    )
    db.add(exp)
    await db.flush()
    await recompute_experience_totals(db, candidate)
    await recompute_profile_completion(db, candidate)
    await db.commit()
    await db.refresh(exp)
    return exp


async def update_experience(
    db: AsyncSession, candidate: CandidateProfile, experience_id: uuid.UUID, payload: ExperienceIn
) -> CandidateExperience:
    exp = await _get_owned_experience(db, candidate.id, experience_id)
    exp.company = payload.company
    exp.designation = payload.designation
    exp.start_date = payload.start_date
    exp.end_date = None if payload.is_current else payload.end_date
    exp.is_current = payload.is_current
    exp.duration_months = duration_months(payload.start_date, payload.end_date, payload.is_current)
    exp.responsibilities = payload.responsibilities or None
    exp.technologies = payload.technologies or None
    exp.domain = payload.domain or None
    exp.achievements = payload.achievements or None
    await db.flush()
    await recompute_experience_totals(db, candidate)
    await recompute_profile_completion(db, candidate)
    await db.commit()
    await db.refresh(exp)
    return exp


async def delete_experience(db: AsyncSession, candidate: CandidateProfile, experience_id: uuid.UUID) -> None:
    exp = await _get_owned_experience(db, candidate.id, experience_id)
    await db.delete(exp)
    await db.flush()
    await recompute_experience_totals(db, candidate)
    await recompute_profile_completion(db, candidate)
    await db.commit()


# ==========================================================================
# Education
# ==========================================================================


async def _get_owned_education(
    db: AsyncSession, candidate_id: uuid.UUID, education_id: uuid.UUID
) -> CandidateEducation:
    edu = await db.get(CandidateEducation, education_id)
    if edu is None or edu.candidate_id != candidate_id:
        raise NotFoundError("Education entry not found")
    return edu


async def create_education(db: AsyncSession, candidate: CandidateProfile, payload: EducationIn) -> CandidateEducation:
    edu = CandidateEducation(
        candidate_id=candidate.id,
        degree=payload.degree,
        institution=payload.institution,
        field=payload.field,
        graduation_year=payload.graduation_year,
        certifications=payload.certifications or None,
    )
    db.add(edu)
    await db.flush()
    await recompute_profile_completion(db, candidate)
    await db.commit()
    await db.refresh(edu)
    return edu


async def update_education(
    db: AsyncSession, candidate: CandidateProfile, education_id: uuid.UUID, payload: EducationIn
) -> CandidateEducation:
    edu = await _get_owned_education(db, candidate.id, education_id)
    edu.degree = payload.degree
    edu.institution = payload.institution
    edu.field = payload.field
    edu.graduation_year = payload.graduation_year
    edu.certifications = payload.certifications or None
    await db.commit()
    await db.refresh(edu)
    return edu


async def delete_education(db: AsyncSession, candidate: CandidateProfile, education_id: uuid.UUID) -> None:
    edu = await _get_owned_education(db, candidate.id, education_id)
    await db.delete(edu)
    await db.flush()
    await recompute_profile_completion(db, candidate)
    await db.commit()


# ==========================================================================
# Projects
# ==========================================================================


async def _get_owned_project(db: AsyncSession, candidate_id: uuid.UUID, project_id: uuid.UUID) -> CandidateProject:
    project = await db.get(CandidateProject, project_id)
    if project is None or project.candidate_id != candidate_id:
        raise NotFoundError("Project not found")
    return project


async def create_project(db: AsyncSession, candidate: CandidateProfile, payload: ProjectIn) -> CandidateProject:
    project = CandidateProject(
        candidate_id=candidate.id,
        name=payload.name,
        description=payload.description,
        technologies=payload.technologies or None,
        domain=payload.domain or None,
        responsibilities=payload.responsibilities or None,
        complexity=payload.complexity,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def update_project(
    db: AsyncSession, candidate: CandidateProfile, project_id: uuid.UUID, payload: ProjectIn
) -> CandidateProject:
    project = await _get_owned_project(db, candidate.id, project_id)
    project.name = payload.name
    project.description = payload.description
    project.technologies = payload.technologies or None
    project.domain = payload.domain or None
    project.responsibilities = payload.responsibilities or None
    project.complexity = payload.complexity
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, candidate: CandidateProfile, project_id: uuid.UUID) -> None:
    project = await _get_owned_project(db, candidate.id, project_id)
    await db.delete(project)
    await db.commit()


# ==========================================================================
# Preferences
# ==========================================================================


async def get_or_create_preferences(db: AsyncSession, candidate: CandidateProfile) -> CandidatePreference:
    result = await db.execute(select(CandidatePreference).where(CandidatePreference.candidate_id == candidate.id))
    prefs = result.scalar_one_or_none()
    if prefs is None:
        prefs = CandidatePreference(candidate_id=candidate.id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)
    return prefs


async def upsert_preferences(
    db: AsyncSession, candidate: CandidateProfile, payload: PreferencesIn
) -> CandidatePreference:
    result = await db.execute(select(CandidatePreference).where(CandidatePreference.candidate_id == candidate.id))
    prefs = result.scalar_one_or_none()
    if prefs is None:
        prefs = CandidatePreference(candidate_id=candidate.id)
        db.add(prefs)

    prefs.preferred_roles = payload.preferred_roles or None
    prefs.preferred_locations = payload.preferred_locations or None
    prefs.preferred_domains = payload.preferred_domains or None
    prefs.salary_min = payload.salary_min
    prefs.salary_max = payload.salary_max
    prefs.currency = payload.currency
    prefs.work_mode = payload.work_mode or None
    prefs.employment_type = payload.employment_type or None
    prefs.min_match_score = payload.min_match_score
    prefs.willing_to_relocate = payload.willing_to_relocate
    prefs.notice_period_days = payload.notice_period_days

    await db.flush()
    await recompute_profile_completion(db, candidate)
    await db.commit()
    await db.refresh(prefs)
    return prefs
