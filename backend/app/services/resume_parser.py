"""Orchestrates the resume -> candidate profile AI pipeline.

extract text (already done by resume_extractor before this is called) ->
LLM structured extraction -> clean/validate JSON -> LLM scoring -> LLM
recommended roles -> persist everything -> compute embeddings -> compute
profile completion.

Also exposes small reusable helpers (date parsing, overlap-merging duration
math, profile-completion scoring) that app/services/candidate_service.py
reuses so manual CRUD edits and resume-driven updates stay consistent.

Nothing in this module fabricates scores, skills, or roles: every AI-derived
value on CandidateProfile/ResumeAnalysis comes from an actual
get_llm_provider().complete_json() call on the actually-extracted resume
text. On LLMError, the ResumeFile is marked failed and the exception is
re-raised (never swallowed into a fake success).
"""

from __future__ import annotations

import asyncio
import re
from datetime import date
from typing import Any

import structlog
from rapidfuzz import fuzz, process
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding_provider import get_embedding_provider
from app.ai.llm_provider import LLMError, get_llm_provider
from app.ai.prompts_candidate import (
    CAREER_LEVELS,
    OTHER_CATEGORY_SLUG,
    SKILL_CATEGORY_SLUGS,
    SKILL_TAXONOMY,
    TIER_BANDS,
    extraction_schema_hint,
    extraction_system_prompt,
    extraction_user_prompt,
    roles_schema_hint,
    roles_system_prompt,
    roles_user_prompt,
    scoring_schema_hint,
    scoring_system_prompt,
    scoring_user_prompt,
)
from app.models.candidate import (
    CandidateEducation,
    CandidateExperience,
    CandidatePreference,
    CandidateProfile,
    CandidateProject,
    CandidateSkill,
)
from app.models.resume import ResumeAnalysis, ResumeFile

logger = structlog.get_logger(__name__)

MAX_LIST_LEN = 40


# ==========================================================================
# Date / duration helpers (also reused by candidate_service.py)
# ==========================================================================

_MONTH_NAMES = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_CURRENT_MARKERS = {"present", "current", "currently", "ongoing", "now", "till date", "to date", "n/a"}


def _is_current_marker(value: Any) -> bool:
    if not value or not isinstance(value, str):
        return False
    return value.strip().lower() in _CURRENT_MARKERS


def parse_flexible_date(value: Any, *, is_end: bool = False) -> date | None:
    """Best-effort parse of an LLM-provided date string into a date object.

    Never raises -- returns None on anything unparsable so callers can treat
    the range as open/unknown rather than crash the whole pipeline over one
    malformed date. `is_end` disambiguates year-only values (Jan vs Dec).
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or _is_current_marker(text):
        return None

    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, min(d, 28))
        except ValueError:
            return None

    m = re.match(r"^(\d{4})[-/](\d{1,2})$", text)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return date(y, mo, 1)
        return None

    m = re.match(r"^(\d{1,2})[-/](\d{4})$", text)
    if m:
        mo, y = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return date(y, mo, 1)
        return None

    m = re.match(r"^([A-Za-z]{3,9})\.?,?\s+(\d{4})$", text)
    if m:
        mon = _MONTH_NAMES.get(m.group(1).lower())
        if mon:
            return date(int(m.group(2)), mon, 1)

    m = re.match(r"^(\d{4})$", text)
    if m:
        y = int(m.group(1))
        return date(y, 12 if is_end else 1, 1)

    return None


def month_index(d: date) -> int:
    return d.year * 12 + d.month


def duration_months(start: date | None, end: date | None, is_current: bool = False) -> int:
    """Months covered by a single [start, end] range (inclusive), clamped >= 0."""
    if not start:
        return 0
    end_for_calc = date.today() if is_current else end
    if not end_for_calc:
        return 0
    return max(0, month_index(end_for_calc) - month_index(start) + 1)


def merge_month_ranges(ranges: list[tuple[date, date]]) -> int:
    """Merges overlapping/adjacent [start, end] month ranges (inclusive) and
    returns the total distinct months covered. Two concurrent jobs overlapping
    for 6 months are NOT double-counted -- this is the whole point of merging
    rather than naively summing each range's duration.
    """
    intervals: list[tuple[int, int]] = []
    for start, end in ranges:
        if start is None or end is None:
            continue
        s, e = month_index(start), month_index(end)
        if e < s:
            s, e = e, s
        intervals.append((s, e))
    if not intervals:
        return 0
    intervals.sort()
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e + 1:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))
    return sum(e - s + 1 for s, e in merged)


# ==========================================================================
# Skill category normalization
# ==========================================================================


def normalize_skill_category(raw: str | None) -> str:
    """Maps a free-text category label from the LLM (or a manual CRUD call)
    onto the fixed skill taxonomy slug set, falling back to 'other'.
    """
    if not raw:
        return OTHER_CATEGORY_SLUG
    raw = raw.strip()
    if not raw:
        return OTHER_CATEGORY_SLUG

    slug_guess = raw.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    if slug_guess in SKILL_CATEGORY_SLUGS.values():
        return slug_guess

    match = process.extractOne(raw, SKILL_TAXONOMY, scorer=fuzz.WRatio)
    if match and match[1] >= 70:
        return SKILL_CATEGORY_SLUGS[match[0]]
    return OTHER_CATEGORY_SLUG


def _normalize_career_level(raw: Any) -> str | None:
    text = _clean_str(raw, max_len=50)
    if not text:
        return None
    for level in CAREER_LEVELS:
        if level.lower() == text.lower():
            return level
    match = process.extractOne(text, CAREER_LEVELS, scorer=fuzz.WRatio)
    if match and match[1] >= 75:
        return match[0]
    return None


# ==========================================================================
# JSON cleaning helpers
# ==========================================================================


def _clean_str(value: Any, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_len:
        text = text[:max_len]
    return text


def _clean_str_list(values: Any, max_len: int = MAX_LIST_LEN) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        s = _clean_str(v)
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max_len:
            break
    return out


def _clean_months_experience(raw: Any) -> int | None:
    months: int | None = None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        months = int(raw)
    elif isinstance(raw, str) and raw.strip().isdigit():
        months = int(raw.strip())
    if months is not None and months < 0:
        months = None
    return months


def _clean_skills(raw_skills: Any) -> list[dict]:
    if not isinstance(raw_skills, list):
        return []
    by_key: dict[str, dict] = {}
    for item in raw_skills:
        if not isinstance(item, dict):
            continue
        name = _clean_str(item.get("name"), max_len=120)
        if not name:
            continue
        key = name.lower()
        category = normalize_skill_category(item.get("category"))
        proficiency = _clean_str(item.get("proficiency"), max_len=30)
        if proficiency and proficiency.lower() not in {"beginner", "intermediate", "advanced", "expert"}:
            proficiency = None
        months = _clean_months_experience(item.get("months_experience"))
        if key in by_key:
            existing = by_key[key]
            if months is not None:
                existing["months_experience"] = max(existing["months_experience"] or 0, months)
            continue
        by_key[key] = {
            "name": name,
            "normalized_name": key,
            "category": category,
            "proficiency": proficiency,
            "months_experience": months,
        }
    return list(by_key.values())


def _clean_experience(raw_list: Any) -> list[dict]:
    if not isinstance(raw_list, list):
        return []
    out = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        company = _clean_str(item.get("company"), max_len=255)
        designation = _clean_str(item.get("designation"), max_len=255)
        if not company and not designation:
            continue
        start_raw = item.get("start_date")
        end_raw = item.get("end_date")
        is_current = bool(item.get("is_current")) or _is_current_marker(end_raw)
        start_date = parse_flexible_date(start_raw, is_end=False)
        end_date = None if is_current else parse_flexible_date(end_raw, is_end=True)
        out.append({
            "company": company or "Unknown",
            "designation": designation or "Unknown",
            "start_date": start_date,
            "end_date": end_date,
            "is_current": is_current,
            "duration_months": duration_months(start_date, end_date, is_current),
            "responsibilities": _clean_str_list(item.get("responsibilities")),
            "technologies": _clean_str_list(item.get("technologies")),
            "domain": _clean_str_list(item.get("domain")),
            "achievements": _clean_str_list(item.get("achievements")),
        })
    return out


def _clean_education(raw_list: Any) -> list[dict]:
    if not isinstance(raw_list, list):
        return []
    out = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        degree = _clean_str(item.get("degree"), max_len=255)
        institution = _clean_str(item.get("institution"), max_len=255)
        field = _clean_str(item.get("field"), max_len=255)
        if not degree and not institution and not field:
            continue
        grad_year_raw = item.get("graduation_year")
        try:
            grad_year = int(grad_year_raw) if grad_year_raw is not None else None
        except (TypeError, ValueError):
            grad_year = None
        if grad_year is not None and not (1950 <= grad_year <= 2100):
            grad_year = None
        out.append({
            "degree": degree,
            "institution": institution,
            "field": field,
            "graduation_year": grad_year,
            "certifications": _clean_str_list(item.get("certifications")),
        })
    return out


def _clean_projects(raw_list: Any) -> list[dict]:
    if not isinstance(raw_list, list):
        return []
    out = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        name = _clean_str(item.get("name"), max_len=255)
        if not name:
            continue
        complexity = _clean_str(item.get("complexity"), max_len=30)
        if complexity and complexity.lower() not in {"low", "medium", "high"}:
            complexity = None
        out.append({
            "name": name,
            "description": _clean_str(item.get("description"), max_len=4000),
            "technologies": _clean_str_list(item.get("technologies")),
            "domain": _clean_str_list(item.get("domain")),
            "responsibilities": _clean_str_list(item.get("responsibilities")),
            "complexity": complexity,
        })
    return out


def _clean_extracted_profile(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raw = {}
    return {
        "full_name": _clean_str(raw.get("full_name"), max_len=255),
        "linkedin_url": _clean_str(raw.get("linkedin_url"), max_len=512),
        "portfolio_url": _clean_str(raw.get("portfolio_url"), max_len=512),
        "github_url": _clean_str(raw.get("github_url"), max_len=512),
        "professional_summary": _clean_str(raw.get("professional_summary"), max_len=4000),
        "career_level": _normalize_career_level(raw.get("career_level")),
        "skills": _clean_skills(raw.get("skills")),
        "experience": _clean_experience(raw.get("experience")),
        "education": _clean_education(raw.get("education")),
        "projects": _clean_projects(raw.get("projects")),
    }


SCORE_BREAKDOWN_KEYS = [
    "skills_strength", "experience_strength", "career_clarity", "technical_depth",
    "achievements", "resume_structure", "job_readiness", "ats_compatibility",
]


def _clamp_score(value: Any, default: int = 0) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, n))


def _clean_score_data(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raw = {}
    breakdown_raw = raw.get("score_breakdown") if isinstance(raw.get("score_breakdown"), dict) else {}
    breakdown = {k: _clamp_score(breakdown_raw.get(k)) for k in SCORE_BREAKDOWN_KEYS}
    overall_raw = raw.get("overall_score")
    if overall_raw is not None:
        overall_score = _clamp_score(overall_raw)
    else:
        overall_score = round(sum(breakdown.values()) / len(breakdown))
    return {
        "overall_score": overall_score,
        "score_breakdown": breakdown,
        "strengths": _clean_str_list(raw.get("strengths"), max_len=10),
        "improvement_suggestions": _clean_str_list(raw.get("improvement_suggestions"), max_len=10),
    }


def _tier_for_confidence(confidence: int) -> str:
    for low, high, tier in TIER_BANDS:
        if low <= confidence <= high:
            return tier
    return "low"


def _clean_roles_data(raw: dict, known_skill_names: list[str]) -> list[dict]:
    if not isinstance(raw, dict):
        raw = {}
    roles_raw = raw.get("recommended_roles")
    if not isinstance(roles_raw, list):
        return []
    known_lower = {s.lower(): s for s in known_skill_names}
    out = []
    for item in roles_raw:
        if not isinstance(item, dict):
            continue
        title = _clean_str(item.get("title"), max_len=150)
        if not title:
            continue
        confidence = _clamp_score(item.get("confidence"))
        reason = _clean_str(item.get("reason"), max_len=500) or ""
        matching_raw = _clean_str_list(item.get("matching_skills"), max_len=20)
        # Ground matching_skills against the candidate's actual extracted
        # skills -- a safety net on top of the prompt instructions so a
        # hallucinated skill can never leak into the response.
        matching = [known_lower[m.lower()] for m in matching_raw if m.lower() in known_lower]
        missing = _clean_str_list(item.get("missing_skills"), max_len=20)
        out.append({
            "title": title,
            "confidence": confidence,
            "tier": _tier_for_confidence(confidence),
            "reason": reason,
            "matching_skills": matching,
            "missing_skills": missing,
        })
    out.sort(key=lambda r: r["confidence"], reverse=True)
    return out[:8]


# ==========================================================================
# Embedding text builders
# ==========================================================================


def _build_profile_embedding_text(candidate: CandidateProfile, profile_data: dict) -> str:
    parts: list[str] = []
    if candidate.professional_summary:
        parts.append(candidate.professional_summary)
    skill_names = [s["name"] for s in profile_data["skills"]]
    if skill_names:
        parts.append("Skills: " + ", ".join(skill_names))
    for e in profile_data["experience"]:
        bits = [e["designation"], e["company"], *e["technologies"], *e["responsibilities"]]
        line = " ".join(b for b in bits if b)
        if line:
            parts.append(line)
    return "\n".join(p for p in parts if p)


def _build_skill_embedding_text(skills: list[dict]) -> str:
    return ", ".join(s["name"] for s in skills)


# ==========================================================================
# Shared recompute helpers (also used by candidate_service.py)
# ==========================================================================


async def recompute_experience_totals(db: AsyncSession, candidate: CandidateProfile) -> None:
    """Recomputes total/relevant experience months from every
    CandidateExperience row currently persisted for this candidate, merging
    overlapping employment ranges so concurrent jobs are never double-counted.

    Caller is responsible for commit(). Mutates `candidate` in place.

    Phase 1 has no target-role context to distinguish "relevant" experience
    from "total" experience (that requires knowing which job the candidate is
    being matched against), so relevant_experience_months mirrors
    total_experience_months for now. This should be revisited once
    job-matching (Phase 2) can score domain/role relevance per experience
    entry.
    """
    result = await db.execute(
        select(CandidateExperience).where(CandidateExperience.candidate_id == candidate.id)
    )
    rows = result.scalars().all()
    ranges: list[tuple[date, date]] = []
    for row in rows:
        if not row.start_date:
            continue
        end = date.today() if row.is_current else row.end_date
        if not end:
            continue
        ranges.append((row.start_date, end))
    total = merge_month_ranges(ranges)
    candidate.total_experience_months = total
    candidate.relevant_experience_months = total


async def recompute_profile_completion(db: AsyncSession, candidate: CandidateProfile) -> None:
    """Recomputes profile_completion_pct / is_profile_complete from current
    DB state. Caller is responsible for commit(). Safe to call after any
    profile / skill / experience / education / preferences / resume mutation.

    Weighting (sums to 100, chosen as a reasonable default -- not from an
    exact spec table):
      resume uploaded & processed .......... 15
      full_name set ......................... 5
      professional_summary set ............. 10
      >=1 skill ............................. 15
      >=1 experience entry .................. 15
      >=1 education entry ................... 10
      full current location (city/state/country) 10
      at least one profile link (linkedin/github/portfolio) 5
      preferences: salary range set ........ 7.5
      preferences: work_mode set ........... 7.5
    is_profile_complete is True once the score reaches 80.
    """
    skills_count = (
        await db.execute(
            select(func.count()).select_from(CandidateSkill).where(CandidateSkill.candidate_id == candidate.id)
        )
    ).scalar_one()
    experience_count = (
        await db.execute(
            select(func.count()).select_from(CandidateExperience).where(
                CandidateExperience.candidate_id == candidate.id
            )
        )
    ).scalar_one()
    education_count = (
        await db.execute(
            select(func.count()).select_from(CandidateEducation).where(
                CandidateEducation.candidate_id == candidate.id
            )
        )
    ).scalar_one()
    resume_count = (
        await db.execute(
            select(func.count()).select_from(ResumeFile).where(
                ResumeFile.candidate_id == candidate.id,
                ResumeFile.processing_status == "completed",
            )
        )
    ).scalar_one()
    prefs = (
        await db.execute(select(CandidatePreference).where(CandidatePreference.candidate_id == candidate.id))
    ).scalar_one_or_none()

    checklist: list[tuple[bool, float]] = [
        (resume_count > 0, 15),
        (bool(candidate.full_name), 5),
        (bool(candidate.professional_summary), 10),
        (skills_count > 0, 15),
        (experience_count > 0, 15),
        (education_count > 0, 10),
        (bool(candidate.current_city and candidate.current_state and candidate.current_country), 10),
        (bool(candidate.linkedin_url or candidate.github_url or candidate.portfolio_url), 5),
        (bool(prefs and prefs.salary_min and prefs.salary_max), 7.5),
        (bool(prefs and prefs.work_mode), 7.5),
    ]
    pct = sum(weight for done, weight in checklist if done)
    candidate.profile_completion_pct = int(round(pct))
    candidate.is_profile_complete = pct >= 80


# ==========================================================================
# Main pipeline
# ==========================================================================


async def process_resume(db: AsyncSession, candidate: CandidateProfile, resume_file: ResumeFile) -> ResumeAnalysis:
    """Runs extraction -> scoring -> role recommendation -> persistence for a
    resume whose text has already been extracted into resume_file.extracted_text.

    Raises LLMError (never caught here beyond marking the failure) if any of
    the three LLM calls fail after their internal retries -- callers must let
    it propagate so the API layer's global handler returns a 503. Nothing is
    ever silently faked on failure.
    """
    llm = get_llm_provider()
    text = resume_file.extracted_text or ""

    resume_file.processing_status = "analyzing"
    await db.commit()

    try:
        extracted_raw = await llm.complete_json(
            extraction_system_prompt(), extraction_user_prompt(text), extraction_schema_hint()
        )
        profile_data = _clean_extracted_profile(extracted_raw)
        logger.info("resume_extraction_complete", resume_file_id=str(resume_file.id),
                    skills=len(profile_data["skills"]), experience=len(profile_data["experience"]))

        score_raw = await llm.complete_json(
            scoring_system_prompt(), scoring_user_prompt(text, profile_data), scoring_schema_hint()
        )
        score_data = _clean_score_data(score_raw)

        roles_raw = await llm.complete_json(
            roles_system_prompt(), roles_user_prompt(text, profile_data), roles_schema_hint()
        )
        known_skill_names = [s["name"] for s in profile_data["skills"]]
        roles_data = _clean_roles_data(roles_raw, known_skill_names)
    except LLMError as exc:
        resume_file.processing_status = "failed"
        resume_file.error_message = str(exc)[:1000]
        await db.commit()
        logger.error("resume_processing_failed", resume_file_id=str(resume_file.id), error=str(exc))
        raise

    # --- scalar profile fields ---
    # Manual edits take priority over AI extraction: identity/link fields are
    # only filled in when currently empty. professional_summary/career_level
    # and every AI-derived field below have no independent "manual truth" of
    # their own on re-upload -- they ARE the resume-driven output -- so they
    # are refreshed every time a resume is (re-)processed.
    if not candidate.full_name and profile_data["full_name"]:
        candidate.full_name = profile_data["full_name"]
    if not candidate.linkedin_url and profile_data["linkedin_url"]:
        candidate.linkedin_url = profile_data["linkedin_url"]
    if not candidate.portfolio_url and profile_data["portfolio_url"]:
        candidate.portfolio_url = profile_data["portfolio_url"]
    if not candidate.github_url and profile_data["github_url"]:
        candidate.github_url = profile_data["github_url"]

    if profile_data["professional_summary"]:
        candidate.professional_summary = profile_data["professional_summary"]
    if profile_data["career_level"]:
        candidate.career_level = profile_data["career_level"]

    candidate.resume_score = float(score_data["overall_score"])
    candidate.resume_score_breakdown = score_data["score_breakdown"]
    candidate.ai_strengths = score_data["strengths"]
    candidate.ai_recommended_roles = roles_data

    # --- replace child rows (skills/experience/education/projects) ---
    await db.execute(delete(CandidateSkill).where(CandidateSkill.candidate_id == candidate.id))
    await db.execute(delete(CandidateExperience).where(CandidateExperience.candidate_id == candidate.id))
    await db.execute(delete(CandidateEducation).where(CandidateEducation.candidate_id == candidate.id))
    await db.execute(delete(CandidateProject).where(CandidateProject.candidate_id == candidate.id))
    await db.flush()

    for s in profile_data["skills"]:
        db.add(CandidateSkill(
            candidate_id=candidate.id,
            name=s["name"],
            normalized_name=s["normalized_name"],
            category=s["category"],
            proficiency=s["proficiency"],
            months_experience=s["months_experience"],
            source="resume",
        ))

    for e in profile_data["experience"]:
        db.add(CandidateExperience(
            candidate_id=candidate.id,
            company=e["company"],
            designation=e["designation"],
            start_date=e["start_date"],
            end_date=e["end_date"],
            is_current=e["is_current"],
            duration_months=e["duration_months"],
            responsibilities=e["responsibilities"] or None,
            technologies=e["technologies"] or None,
            domain=e["domain"] or None,
            achievements=e["achievements"] or None,
        ))

    for ed in profile_data["education"]:
        db.add(CandidateEducation(
            candidate_id=candidate.id,
            degree=ed["degree"],
            institution=ed["institution"],
            field=ed["field"],
            graduation_year=ed["graduation_year"],
            certifications=ed["certifications"] or None,
        ))

    for p in profile_data["projects"]:
        db.add(CandidateProject(
            candidate_id=candidate.id,
            name=p["name"],
            description=p["description"],
            technologies=p["technologies"] or None,
            domain=p["domain"] or None,
            responsibilities=p["responsibilities"] or None,
            complexity=p["complexity"],
        ))

    await db.flush()
    await recompute_experience_totals(db, candidate)

    # --- embeddings (run the blocking local model off the event loop) ---
    embedder = get_embedding_provider()
    profile_text = _build_profile_embedding_text(candidate, profile_data)
    skill_text = _build_skill_embedding_text(profile_data["skills"])
    if profile_text.strip():
        candidate.profile_embedding = await asyncio.to_thread(embedder.embed_one, profile_text)
    if skill_text.strip():
        candidate.skill_embedding = await asyncio.to_thread(embedder.embed_one, skill_text)

    # --- resume file + analysis ---
    resume_file.processing_status = "completed"
    resume_file.error_message = None

    analysis = ResumeAnalysis(
        resume_file_id=resume_file.id,
        candidate_id=candidate.id,
        overall_score=score_data["overall_score"],
        score_breakdown=score_data["score_breakdown"],
        raw_llm_output={"extraction": extracted_raw, "scoring": score_raw, "roles": roles_raw},
        strengths=score_data["strengths"],
        improvement_suggestions=score_data["improvement_suggestions"],
        recommended_roles=roles_data,
    )
    db.add(analysis)
    await db.flush()

    await recompute_profile_completion(db, candidate)

    await db.commit()
    await db.refresh(analysis)
    logger.info("resume_processing_complete", resume_file_id=str(resume_file.id), score=score_data["overall_score"])
    return analysis
