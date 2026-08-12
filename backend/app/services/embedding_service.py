"""Builds the text blobs that get embedded for jobs and candidates, plus a
small shared cosine-similarity helper used by both dedup_service and
matching_service so the two don't drift on how similarity is computed.

Callers are responsible for making sure any relationships these functions
touch (Job.skills, CandidateProfile.experience/skills/projects/education/
preferences) are already loaded (e.g. via selectinload) before calling —
these functions are synchronous and must never trigger a lazy DB load inside
an async SQLAlchemy session.
"""

from __future__ import annotations

from app.models.candidate import CandidateProfile
from app.models.job import Job


def _joined(items: list[str] | None) -> str:
    return ", ".join(i for i in items if i) if items else ""


def job_embedding_text(job: Job) -> str:
    """NEVER embed title alone — title-only embeddings collapse too many
    unrelated roles together. Concatenate everything that describes what the
    job actually is."""
    skill_names = [s.name for s in (job.skills or [])]
    parts = [
        job.title,
        job.company_name_raw,
        job.description,
        _joined(job.responsibilities),
        _joined(job.requirements_required),
        _joined(job.requirements_preferred),
        _joined(skill_names),
        _joined(job.domain),
        " ".join(p for p in [job.city, job.state, job.country] if p),
        job.work_mode,
    ]
    return "\n".join(p for p in parts if p)


def candidate_embedding_text(candidate: CandidateProfile) -> str:
    """Standalone helper in case matching/ranking needs to (re)compute a
    candidate embedding defensively when candidate.profile_embedding is
    missing (e.g. profile created before an embedding pass ever ran). May
    overlap with logic the resume-parsing pipeline runs inline — that's fine,
    this just needs to work standalone."""
    parts: list[str] = [candidate.professional_summary or ""]

    for exp in candidate.experience or []:
        parts.append(exp.designation or "")
        parts.append(_joined(exp.technologies))
        parts.append(_joined(exp.responsibilities))
        parts.append(_joined(exp.domain))

    parts.append(_joined([s.name for s in (candidate.skills or [])]))

    for proj in candidate.projects or []:
        parts.append(proj.name or "")
        parts.append(_joined(proj.technologies))
        parts.append(_joined(proj.domain))

    for edu in candidate.education or []:
        if edu.field:
            parts.append(edu.field)

    prefs = candidate.preferences
    if prefs is not None:
        parts.append(_joined(prefs.preferred_roles))
        parts.append(_joined(prefs.preferred_domains))

    return "\n".join(p for p in parts if p)


def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float:
    """Manual dot-product cosine so we don't need numpy for a 384-dim vector.
    Returns 0.0 (not an error) when either side is missing — callers should
    treat that as "no signal", never crash."""
    if a is None or b is None or not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    similarity = dot / (norm_a * norm_b)
    return max(0.0, min(1.0, similarity))
