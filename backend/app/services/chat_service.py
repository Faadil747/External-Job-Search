"""Context assembly + orchestration for the AI Career Copilot (spec section 47).
Grounds every reply in the candidate's real profile and real retrieved jobs —
never lets the LLM free-associate about jobs that aren't in the database.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.llm_provider import get_llm_provider
from app.ai.prompts_chat import build_chat_system_prompt, build_user_prompt
from app.models.activity import AIConversation
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.schemas.job import JobSearchRequest
from app.services.matching_service import build_match_reason, match_scores_dict, score_job_for_candidate
from app.services.ranking_service import get_recommended_jobs, load_candidate_with_relations

HISTORY_TURNS = 6
CONTEXT_JOB_LIMIT = 5
DESCRIPTION_SNIPPET_CHARS = 400


def _format_candidate_context(candidate: CandidateProfile) -> str:
    lines: list[str] = []
    if candidate.full_name:
        lines.append(f"Name: {candidate.full_name}")
    if candidate.career_level:
        lines.append(f"Career level: {candidate.career_level}")
    years = round((candidate.total_experience_months or 0) / 12, 1)
    lines.append(f"Total experience: {years} years")
    location = ", ".join(p for p in [candidate.current_city, candidate.current_state, candidate.current_country] if p)
    if location:
        lines.append(f"Current location: {location}")
    if candidate.professional_summary:
        lines.append(f"Summary: {candidate.professional_summary}")
    if candidate.skills:
        lines.append(f"Skills: {', '.join(s.name for s in candidate.skills[:25])}")
    if candidate.experience:
        lines.append("Experience:")
        for exp in candidate.experience[:5]:
            span = f"{exp.duration_months} months" if exp.duration_months else "duration unknown"
            lines.append(f"  - {exp.designation} at {exp.company} ({span})")
    for edu in candidate.education[:3] if candidate.education else []:
        if edu.degree or edu.institution:
            lines.append(f"Education: {(edu.degree or '').strip()} {(edu.institution or '').strip()}".strip())
    prefs = candidate.preferences
    if prefs:
        if prefs.preferred_roles:
            lines.append(f"Preferred roles: {', '.join(prefs.preferred_roles)}")
        if prefs.preferred_locations:
            lines.append(f"Preferred locations: {', '.join(prefs.preferred_locations)}")
        if prefs.work_mode:
            lines.append(f"Preferred work mode: {', '.join(prefs.work_mode)}")
    if candidate.resume_score is not None:
        lines.append(f"AI resume score: {candidate.resume_score}/100")
    return "\n".join(lines) if lines else "No profile data available yet — candidate hasn't completed their profile."


async def _format_job_detail_context(db: AsyncSession, candidate: CandidateProfile, job_id: uuid.UUID) -> str:
    stmt = select(Job).where(Job.id == job_id).options(selectinload(Job.skills))
    job = (await db.execute(stmt)).scalar_one_or_none()
    if job is None:
        return "The candidate referenced a job_id that does not exist in our database."

    match = await score_job_for_candidate(db, candidate, job)
    reason = build_match_reason(candidate, job, match_scores_dict(match))
    description_snippet = (job.description or "")[:DESCRIPTION_SNIPPET_CHARS]

    location = ", ".join(p for p in [job.city, job.state, job.country] if p) or "Not specified"
    lines = [
        f"job_id={job.id}",
        f"Job: {job.title} at {job.company_name_raw}",
        f"Location: {location} ({job.work_mode})",
        f"Employment type: {job.employment_type}",
        f"Experience required: {job.experience_min}-{job.experience_max} years",
        f"Match score: {match.score}/100 ({match.category})",
        f"Matched skills: {', '.join(reason.get('matched_skills') or []) or 'none identified'}",
        f"Missing skills: {', '.join(reason.get('missing_skills') or []) or 'none identified'}",
        f"Description excerpt: {description_snippet}",
    ]
    if job.salary_min or job.salary_max:
        lines.append(f"Salary: {job.salary_min or '?'}-{job.salary_max or '?'} {job.currency or ''}")
    return "\n".join(lines)


async def _format_recommended_jobs_context(db: AsyncSession, candidate: CandidateProfile) -> str:
    cards = await get_recommended_jobs(db, candidate, JobSearchRequest(limit=CONTEXT_JOB_LIMIT, sort_by="best_match"))
    if not cards:
        return "No jobs are currently available in the database matching this candidate's profile."
    lines = []
    for card in cards[:CONTEXT_JOB_LIMIT]:
        lines.append(
            f"- job_id={card.id} | {card.title} at {card.company_name} ({card.city or card.work_mode}) — "
            f"{card.match_score}/100 match ({card.match_category}). "
            f"Top skills: {', '.join(card.top_skills) or 'n/a'}. "
            f"Why it matches: {card.why_it_matches or 'n/a'}."
        )
    return "\n".join(lines)


async def _format_history(db: AsyncSession, candidate_id: uuid.UUID) -> str:
    stmt = (
        select(AIConversation)
        .where(AIConversation.candidate_id == candidate_id)
        .order_by(AIConversation.created_at.desc())
        .limit(HISTORY_TURNS)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    rows.reverse()
    return "\n".join(f"{row.role}: {row.content}" for row in rows)


async def answer_chat_message(
    db: AsyncSession, candidate: CandidateProfile, message: str, job_id: uuid.UUID | None
) -> str:
    candidate = await load_candidate_with_relations(db, candidate)

    candidate_context = _format_candidate_context(candidate)
    jobs_context = (
        await _format_job_detail_context(db, candidate, job_id)
        if job_id is not None
        else await _format_recommended_jobs_context(db, candidate)
    )
    history_context = await _format_history(db, candidate.id)

    system_prompt = build_chat_system_prompt(candidate_context, jobs_context)
    user_prompt = build_user_prompt(message, history_context)

    provider = get_llm_provider()
    reply = await provider.complete_text(system_prompt, user_prompt)

    context_ids = [str(job_id)] if job_id else None
    db.add(AIConversation(candidate_id=candidate.id, role="user", content=message, context_job_ids=context_ids))
    db.add(AIConversation(candidate_id=candidate.id, role="assistant", content=reply, context_job_ids=context_ids))
    await db.commit()

    return reply
