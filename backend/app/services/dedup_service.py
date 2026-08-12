"""Duplicate detection — the hardest, highest-stakes part of ingestion.

Same underlying job posted to two channels (career page + LinkedIn, a raw
feed + an ATS mirror, etc.) must collapse to one canonical Job so a candidate
never sees the same role twice. But two DIFFERENT jobs at the same company
with a similar title must NOT be silently merged just because they look
alike on paper — that hides a real opportunity from the candidate, which is
worse than an occasional near-duplicate slipping through.

## Signals and weight-tuning rationale

Five 0..1 signals are combined into a weighted sum and compared against
`settings.duplicate_threshold` (0.85 by default):

    company   — exact match on Company.normalized_name             weight 0.28
    title     — rapidfuzz token_sort_ratio on normalized_title      weight 0.07
    location  — same city/work_mode logic, see _location_signal     weight 0.32
    semantic  — cosine sim of job_embedding_text() embeddings       weight 0.21
    skills    — Jaccard overlap of normalized skill-name sets       weight 0.12

These weights were reached empirically against this codebase's own seed
dataset (app/jobs_ingestion/adapters/seed_data.json), which was deliberately
authored with two calibration cases:

  * seed-001 / seed-002 — TRUE duplicates: same company, same city, same
    work_mode, but reworded titles ("Backend Developer (Python/Django)" vs
    "Python Developer - API Platform") because recruiters/job boards rewrite
    titles constantly. Measured token_sort_ratio on normalized titles is only
    ~0.46, and skills-Jaccard is only ~0.38 (Django/Celery/Docker vs
    FastAPI/DRF wording), so title and skills are surprisingly WEAK, noisy
    discriminators here despite being the two most "obvious" signals.

  * seed-004 / seed-005 — a TRICKY near-duplicate that should NOT merge:
    same company ("Bluepeak Systems" / "Bluepeak Systems Pvt Ltd" — identical
    after legal-suffix stripping), nearly identical title wording (~0.96
    token_sort_ratio after normalization), an IDENTICAL skill list
    (Jaccard = 1.0), and high description-embedding similarity (~0.83) —
    yet one is onsite Bangalore and the other is remote with no fixed city.
    Every signal except location says "merge these"; only location correctly
    says "don't."

Given that, title and skills are deliberately down-weighted (title in
particular — job titles are the least reliable identity signal in this
domain) while company-identity and location-consistency, the two signals
that are actually cheap to get exactly right, carry the most weight.
Semantic similarity sits in between: it's a strong corroborating signal but
on its own doesn't distinguish "same job, reworded" from "same company,
same tech stack, different role" (both land in the 0.75-0.90 range).

With these weights: seed-001/seed-002 score ~0.86 (>= 0.85 -> merged) while
seed-004/seed-005 score ~0.64 (well under 0.85 -> kept separate). See the
worked numbers in this module's test/inspection notes if you need to re-tune;
if false negatives (missed true duplicates) turn out to be a bigger problem
in production than false positives (wrongly merged jobs), the safest lever to
pull first is `settings.duplicate_threshold`, not these weights — merging
distinct jobs is the worse failure mode of the two.

On top of the weighted sum, two exact-match shortcuts short-circuit straight
to a duplicate call regardless of the weighted total: an identical
`content_hash` (byte-identical repost) or an identical canonicalized URL
(same posting re-ingested, e.g. with different UTM params).
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from rapidfuzz import fuzz
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding_provider import get_embedding_provider
from app.config import get_settings
from app.models.job import Company, Job, JobDuplicate, JobSkill, JobSource
from app.services.embedding_service import cosine_similarity, job_embedding_text
from app.services.job_normalizer import canonical_url, trust_rank_for_tier

logger = structlog.get_logger(__name__)

DEDUP_WEIGHTS: dict[str, float] = {
    "company": 0.28,
    "title": 0.07,
    "location": 0.32,
    "semantic": 0.21,
    "skills": 0.12,
}
assert abs(sum(DEDUP_WEIGHTS.values()) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Individual signals
# ---------------------------------------------------------------------------
async def _company_normalized_name(db: AsyncSession, job: Job) -> str | None:
    if job.company_id is None:
        return None
    company = await db.get(Company, job.company_id)
    return company.normalized_name if company else None


def _location_signal(a: Job, b: Job) -> float:
    a_remote = a.work_mode == "remote"
    b_remote = b.work_mode == "remote"
    if a_remote and b_remote:
        return 1.0
    if a_remote != b_remote:
        # One is tied to a physical place, the other isn't — can't be the
        # same posting regardless of how similar everything else looks.
        return 0.0
    a_city = (a.city or "").strip().lower()
    b_city = (b.city or "").strip().lower()
    if a_city and a_city == b_city:
        return 1.0 if a.work_mode == b.work_mode else 0.5
    return 0.0


async def _skill_names(db: AsyncSession, job_id: uuid.UUID) -> set[str]:
    stmt = select(JobSkill.normalized_name).where(JobSkill.job_id == job_id)
    return {row[0] for row in (await db.execute(stmt)).all()}


def _skills_jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


async def _semantic_signal(job_a: Job, job_b: Job) -> float:
    provider = get_embedding_provider()
    vec_a, vec_b = job_a.embedding, job_b.embedding
    if vec_a is None:
        vec_a = await asyncio.to_thread(provider.embed_one, job_embedding_text(job_a))
    if vec_b is None:
        vec_b = await asyncio.to_thread(provider.embed_one, job_embedding_text(job_b))
    return cosine_similarity(vec_a, vec_b)


async def compute_duplicate_signals(db: AsyncSession, job_a: Job, job_b: Job) -> dict[str, float]:
    """Returns each named signal (0..1) plus a `weighted_total`. Exposed
    standalone so it can be reused for the JobDuplicate.signals audit trail
    and inspected/tested independently of the linking side-effects."""
    company_a = await _company_normalized_name(db, job_a)
    company_b = await _company_normalized_name(db, job_b)
    company_sig = 1.0 if company_a and company_b and company_a == company_b else 0.0

    title_sig = fuzz.token_sort_ratio(job_a.normalized_title, job_b.normalized_title) / 100

    location_sig = _location_signal(job_a, job_b)

    semantic_sig = await _semantic_signal(job_a, job_b)

    skills_a = await _skill_names(db, job_a.id)
    skills_b = await _skill_names(db, job_b.id)
    skills_sig = _skills_jaccard(skills_a, skills_b)

    signals = {
        "company": round(company_sig, 4),
        "title": round(title_sig, 4),
        "location": round(location_sig, 4),
        "semantic": round(semantic_sig, 4),
        "skills": round(skills_sig, 4),
    }
    signals["weighted_total"] = round(sum(DEDUP_WEIGHTS[k] * v for k, v in signals.items()), 4)
    return signals


# ---------------------------------------------------------------------------
# Linking
# ---------------------------------------------------------------------------
async def find_and_link_duplicates(db: AsyncSession, job: Job) -> Job | None:
    """Checks `job` against a bounded set of existing candidates, links it as
    a duplicate (or promotes it to canonical over a lower-trust existing job)
    when the evidence clears the bar, and returns the surviving canonical Job
    — or None if `job` is judged genuinely new.

    Prefilter strategy: rather than compare `job` against every row in the
    table (O(n^2) across a full ingestion run), we only pull existing
    non-duplicate Jobs that share `job`'s normalized company name OR its
    exact content_hash. Both are cheap indexed/joinable lookups and cover the
    realistic cases (same employer posting to multiple channels; an
    identical repost). This is correctness-first for the current tiny seed
    dataset; at real scale you'd add a vector-similarity prefilter via
    get_vector_store().search_jobs() to also catch same-role-different-company
    reposts (e.g. a staffing agency repost) before falling back to full
    signal scoring on the shortlist.
    """
    settings = get_settings()
    company_norm = await _company_normalized_name(db, job)

    conditions = [Job.content_hash == job.content_hash]
    stmt = select(Job).where(Job.id != job.id, Job.is_duplicate.is_(False))
    if company_norm:
        stmt = stmt.join(Company, Job.company_id == Company.id, isouter=True).where(
            or_(*conditions, Company.normalized_name == company_norm)
        )
    else:
        stmt = stmt.where(or_(*conditions))

    candidates = (await db.execute(stmt)).scalars().all()
    if not candidates:
        return None

    job_canon_url = canonical_url(job.source_url)

    best_candidate: Job | None = None
    best_signals: dict[str, float] | None = None

    for candidate in candidates:
        # Exact-match shortcuts bypass the weighted formula entirely.
        exact_url = bool(job_canon_url) and job_canon_url == canonical_url(candidate.source_url)
        exact_hash = job.content_hash == candidate.content_hash
        if exact_url or exact_hash:
            signals = await compute_duplicate_signals(db, job, candidate)
            signals["weighted_total"] = 1.0
            signals["exact_url_match"] = exact_url
            signals["exact_content_hash_match"] = exact_hash
            best_candidate, best_signals = candidate, signals
            break  # an exact repost is decisive; no need to keep scoring

        signals = await compute_duplicate_signals(db, job, candidate)
        if signals["weighted_total"] >= settings.duplicate_threshold:
            if best_signals is None or signals["weighted_total"] > best_signals["weighted_total"]:
                best_candidate, best_signals = candidate, signals

    if best_candidate is None or best_signals is None:
        return None

    winner, loser = await _pick_canonical(db, job, best_candidate)

    if loser.id != job.id:
        # `job` (the newly-ingested row) won over a pre-existing canonical —
        # re-point anything that already treated `loser` as canonical so the
        # duplicate chain stays correct.
        await _reroute_canonical(db, old_canonical_id=loser.id, new_canonical_id=winner.id)

    loser.is_duplicate = True
    loser.canonical_job_id = winner.id

    db.add(
        JobDuplicate(
            canonical_job_id=winner.id,
            duplicate_job_id=loser.id,
            confidence=best_signals["weighted_total"],
            signals=best_signals,
        )
    )
    await db.flush()

    logger.info(
        "duplicate_linked",
        canonical_job_id=str(winner.id),
        duplicate_job_id=str(loser.id),
        confidence=best_signals["weighted_total"],
    )
    return winner


async def _pick_canonical(db: AsyncSession, job: Job, candidate: Job) -> tuple[Job, Job]:
    """Winner = higher JobSource.trust_tier, earliest posted_at as tie-break."""
    source_job = await db.get(JobSource, job.source_id)
    source_candidate = await db.get(JobSource, candidate.source_id)
    rank_job = trust_rank_for_tier(source_job.trust_tier if source_job else None)
    rank_candidate = trust_rank_for_tier(source_candidate.trust_tier if source_candidate else None)

    if rank_job > rank_candidate:
        return job, candidate
    if rank_candidate > rank_job:
        return candidate, job
    # Tie on trust tier — earliest posting wins (it's the "original").
    if job.posted_at < candidate.posted_at:
        return job, candidate
    return candidate, job


async def _reroute_canonical(db: AsyncSession, *, old_canonical_id: uuid.UUID, new_canonical_id: uuid.UUID) -> None:
    children_stmt = select(Job).where(Job.canonical_job_id == old_canonical_id)
    for child in (await db.execute(children_stmt)).scalars().all():
        child.canonical_job_id = new_canonical_id

    dup_rows_stmt = select(JobDuplicate).where(JobDuplicate.canonical_job_id == old_canonical_id)
    for dup_row in (await db.execute(dup_rows_stmt)).scalars().all():
        dup_row.canonical_job_id = new_canonical_id


# ---------------------------------------------------------------------------
# JobDetailOut.other_sources
# ---------------------------------------------------------------------------
async def get_other_sources(db: AsyncSession, canonical_job_id: uuid.UUID) -> list[str]:
    stmt = select(Job.source_id).where(
        or_(Job.id == canonical_job_id, Job.canonical_job_id == canonical_job_id)
    )
    source_ids = {row[0] for row in (await db.execute(stmt)).all()}
    if not source_ids:
        return []
    names_stmt = select(JobSource.name).where(JobSource.id.in_(source_ids))
    names = [row[0] for row in (await db.execute(names_stmt)).all()]
    return sorted(set(names))
