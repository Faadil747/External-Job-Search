"""The scoring engine: turns (candidate, job) into a JobMatch (10 weighted
0-100 components -> a single 0-100 score -> a category) plus a deterministic,
template-based MatchReason.

Nothing in here calls an LLM — it needs to run over hundreds of jobs per
request, fast and deterministically, with GROQ_API_KEY unset. `build_match_reason`
is explicitly the deterministic stand-in for product spec section 53's LLM
validation pass; see its docstring for where an LLM refinement step over just
the top ~10-20 results could be layered on top later (optional/stretch).

Callers must ensure `candidate` and `job` have their relevant relationships
eagerly loaded (CandidateProfile.skills/experience/education/projects/
preferences; Job.skills) before calling anything here — see
ranking_service.load_candidate_with_relations().
"""

from __future__ import annotations

from datetime import datetime, timezone

from rapidfuzz import fuzz

from app.config import get_settings
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.match import JobMatch
from app.services.embedding_service import cosine_similarity

# ---------------------------------------------------------------------------
# Starter transferable-skills map. Not exhaustive — easy to extend. Skills
# inside the same set are considered partial substitutes for each other
# (exact match = full credit, transferable = 0.6 credit, neither = 0 credit).
# ---------------------------------------------------------------------------
TRANSFERABLE_SKILL_GROUPS: list[set[str]] = [
    {"django", "fastapi"},
    {"postgresql", "mysql"},
    {"aws", "azure", "gcp", "google cloud", "microsoft azure"},
    {"react", "next.js", "nextjs"},
    {"pytorch", "tensorflow"},
]
TRANSFERABLE_CREDIT = 0.6


def _normalize_skill(name: str) -> str:
    return name.strip().lower()


def _classify_skills(candidate: CandidateProfile, job: Job) -> dict:
    """Single source of truth for "what skills does this candidate have
    relative to this job", shared by both the numeric scorer and the
    human-readable reason builder so they never disagree with each other."""
    candidate_names = {_normalize_skill(s.name) for s in (candidate.skills or [])}

    if job.skills:
        required = [s.name for s in job.skills if s.is_required]
        preferred = [s.name for s in job.skills if not s.is_required]
    else:
        required = list(job.requirements_required or [])
        preferred = list(job.requirements_preferred or [])

    def classify(names: list[str]) -> tuple[list[str], list[str], list[dict]]:
        matched, missing, transferable = [], [], []
        for skill_name in names:
            norm = _normalize_skill(skill_name)
            if norm in candidate_names:
                matched.append(skill_name)
                continue
            source_skill = None
            for group in TRANSFERABLE_SKILL_GROUPS:
                if norm in group:
                    hits = candidate_names & group
                    if hits:
                        source_skill = sorted(hits)[0]
                        break
            if source_skill:
                transferable.append({"skill": skill_name, "from": source_skill})
            else:
                missing.append(skill_name)
        return matched, missing, transferable

    req_matched, req_missing, req_transfer = classify(required)
    pref_matched, pref_missing, pref_transfer = classify(preferred)

    return {
        "required": required,
        "preferred": preferred,
        "req_matched": req_matched,
        "req_missing": req_missing,
        "req_transfer": req_transfer,
        "pref_matched": pref_matched,
        "pref_missing": pref_missing,
        "pref_transfer": pref_transfer,
    }


def _score_skills(classification: dict) -> float:
    def component(total: list, matched: list, transfer: list) -> float:
        if not total:
            return 1.0  # nothing listed to fail against
        return (len(matched) * 1.0 + len(transfer) * TRANSFERABLE_CREDIT) / len(total)

    required_score = component(classification["required"], classification["req_matched"], classification["req_transfer"])
    if classification["preferred"]:
        preferred_score = component(classification["preferred"], classification["pref_matched"], classification["pref_transfer"])
    else:
        preferred_score = required_score
    return (required_score * 0.7 + preferred_score * 0.3) * 100


def _score_experience(candidate: CandidateProfile, job: Job) -> float:
    candidate_years = (candidate.total_experience_months or 0) / 12
    lo, hi = job.experience_min or 0, job.experience_max or 0
    if lo == 0 and hi == 0:
        return 70.0  # role doesn't specify a range — neutral, don't penalize
    if lo <= candidate_years <= hi:
        return 100.0
    if candidate_years < lo:
        gap = lo - candidate_years
        return max(15.0, 100 - gap * 30)  # taper, not a hard cliff
    gap = candidate_years - hi
    return max(30.0, 100 - gap * 15)  # overqualified is penalized more gently than underqualified


def _score_role(candidate: CandidateProfile, job: Job) -> float:
    candidate_titles: list[str] = []
    if candidate.experience:
        most_recent = candidate.experience[0]  # relationship is ordered desc(start_date)
        if most_recent.designation:
            candidate_titles.append(most_recent.designation)
    prefs = candidate.preferences
    if prefs and prefs.preferred_roles:
        candidate_titles.extend(prefs.preferred_roles)
    if not candidate_titles:
        return 0.0
    return max(fuzz.token_sort_ratio(job.normalized_title, t.lower()) for t in candidate_titles if t)


def _score_semantic(candidate: CandidateProfile, job: Job) -> float:
    return cosine_similarity(candidate.profile_embedding, job.embedding) * 100


def _norm_loc(value: str | None) -> str:
    return (value or "").strip().lower()


def _score_location(candidate: CandidateProfile, job: Job) -> float:
    if job.work_mode == "remote":
        return 100.0

    job_city, job_state, job_country = _norm_loc(job.city), _norm_loc(job.state), _norm_loc(job.country)
    cand_city, cand_state, cand_country = (
        _norm_loc(candidate.current_city),
        _norm_loc(candidate.current_state),
        _norm_loc(candidate.current_country),
    )
    prefs = candidate.preferences
    preferred_locations = {
        _norm_loc(loc) for loc in (prefs.preferred_locations or []) if loc
    } if prefs else set()

    if job_city and job_city in preferred_locations:
        score = 100.0
    elif job_city and job_city == cand_city:
        score = 90.0 if job.work_mode == "hybrid" else 100.0
    elif job_state and job_state == cand_state:
        score = 70.0
    elif job_country and job_country == cand_country:
        score = 40.0
    else:
        score = 10.0  # near-zero, genuinely unrelated locations

    if prefs and prefs.willing_to_relocate and score < 60.0:
        score = 60.0
    return score


def _score_domain(candidate: CandidateProfile, job: Job) -> float:
    job_domains = {d.strip().lower() for d in (job.domain or []) if d}
    if not job_domains:
        return 50.0  # role doesn't specify — neutral

    candidate_domains: set[str] = set()
    prefs = candidate.preferences
    if prefs and prefs.preferred_domains:
        candidate_domains |= {d.strip().lower() for d in prefs.preferred_domains if d}
    candidate_domains |= {
        s.category.strip().lower() for s in (candidate.skills or []) if s.category and s.category != "other"
    }
    for exp in candidate.experience or []:
        candidate_domains |= {d.strip().lower() for d in (exp.domain or []) if d}

    if not candidate_domains:
        return 30.0  # nothing to compare against

    overlap = job_domains & candidate_domains
    if not overlap:
        return 20.0
    return min(100.0, 60 + 40 * (len(overlap) / len(job_domains)))


def _score_education(candidate: CandidateProfile, job: Job) -> float:
    job_education = job.education or []
    if not job_education:
        return 100.0  # nothing required
    has_degree = bool(candidate.education) and any(e.degree for e in candidate.education)
    return 80.0 if has_degree else 40.0  # loose presence check, per spec — kept simple on purpose


def _score_work_mode(candidate: CandidateProfile, job: Job) -> float:
    prefs = candidate.preferences
    preferred_modes = [m.lower() for m in prefs.work_mode] if prefs and prefs.work_mode else None
    if not preferred_modes:
        return 60.0  # no stated preference — neutral
    return 100.0 if job.work_mode in preferred_modes else 30.0


def _score_recency(job: Job, now: datetime | None = None) -> float:
    settings = get_settings()
    now = now or datetime.now(timezone.utc)
    posted_at = job.posted_at
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    age_days = (now - posted_at).total_seconds() / 86400
    window = max(settings.fresh_job_window_days, 1)

    if age_days <= 0:
        return 100.0
    if age_days <= window:
        return 100 - 60 * (age_days / window)
    extra = min(age_days - window, 30)
    return max(10.0, 40 - 30 * (extra / 30))


def _score_trust(job: Job) -> float:
    return max(0.0, min(1.0, job.trust_score or 0.0)) * 100


def _category(total_score: float) -> str:
    if total_score >= 90:
        return "excellent"
    if total_score >= 80:
        return "strong"
    if total_score >= 70:
        return "good"
    if total_score >= 60:
        return "potential"
    if total_score >= 50:
        return "stretch"
    return "low"


async def score_job_for_candidate(db, candidate: CandidateProfile, job: Job) -> JobMatch:
    """Builds (does not commit) a JobMatch. `db` is accepted for interface
    symmetry with the rest of the services layer and future use (e.g. a DB
    query for market benchmarks); nothing here currently awaits it."""
    weights = get_settings().match_weights

    classification = _classify_skills(candidate, job)
    skills_score = _score_skills(classification)
    experience_score = _score_experience(candidate, job)
    role_score = _score_role(candidate, job)
    semantic_score = _score_semantic(candidate, job)
    location_score = _score_location(candidate, job)
    domain_score = _score_domain(candidate, job)
    education_score = _score_education(candidate, job)
    work_mode_score = _score_work_mode(candidate, job)
    recency_score = _score_recency(job)
    trust_score = _score_trust(job)

    total = (
        weights["skills"] * skills_score
        + weights["experience"] * experience_score
        + weights["role"] * role_score
        + weights["semantic"] * semantic_score
        + weights["location"] * location_score
        + weights["domain"] * domain_score
        + weights["education"] * education_score
        + weights["work_mode"] * work_mode_score
        + weights["recency"] * recency_score
        + weights["trust"] * trust_score
    )

    return JobMatch(
        candidate_id=candidate.id,
        job_id=job.id,
        score=round(total, 2),
        category=_category(total),
        skills_score=round(skills_score, 2),
        experience_score=round(experience_score, 2),
        role_score=round(role_score, 2),
        semantic_score=round(semantic_score, 2),
        location_score=round(location_score, 2),
        domain_score=round(domain_score, 2),
        education_score=round(education_score, 2),
        work_mode_score=round(work_mode_score, 2),
        recency_score=round(recency_score, 2),
        trust_score=round(trust_score, 2),
    )


def match_scores_dict(match: JobMatch) -> dict:
    """Flattens a persisted/pending JobMatch into the `scores` shape
    build_match_reason expects, so callers never have to hand-assemble it."""
    return {
        "skills": match.skills_score,
        "experience": match.experience_score,
        "role": match.role_score,
        "semantic": match.semantic_score,
        "location": match.location_score,
        "domain": match.domain_score,
        "education": match.education_score,
        "work_mode": match.work_mode_score,
        "recency": match.recency_score,
        "trust": match.trust_score,
        "total": match.score,
        "category": match.category,
    }


def _trunc(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_match_reason(candidate: CandidateProfile, job: Job, scores: dict) -> dict:
    """Deterministic, template-based match explanation — the stand-in for
    product spec section 53's LLM validation pass. This has to run over
    every scored job in a request (potentially hundreds), so it stays
    rule-based rather than calling an LLM. A future enhancement could run an
    LLM pass over just the top ~10-20 results to add nuance/polish to these
    strings (spec section 53) — that's optional/stretch scope; this
    deterministic version must (and does) work correctly on its own.

    `scores` should be the dict produced by match_scores_dict(): the 10
    component keys plus "total" and "category".
    """
    classification = _classify_skills(candidate, job)
    seen: set[str] = set()
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    transferable_skills: list[dict] = []
    for skill_name in classification["req_matched"] + classification["pref_matched"]:
        key = _normalize_skill(skill_name)
        if key not in seen:
            seen.add(key)
            matched_skills.append(skill_name)
    for entry in classification["req_transfer"] + classification["pref_transfer"]:
        key = _normalize_skill(entry["skill"])
        if key not in seen:
            seen.add(key)
            transferable_skills.append(entry)
    for skill_name in classification["req_missing"] + classification["pref_missing"]:
        key = _normalize_skill(skill_name)
        if key not in seen:
            seen.add(key)
            missing_skills.append(skill_name)

    total_considered = len(matched_skills) + len(missing_skills) + len(transferable_skills)

    exp_years = round((candidate.total_experience_months or 0) / 12, 1)
    exp_score = scores.get("experience", 0)
    exp_range = f"{job.experience_min}-{job.experience_max} years"
    if exp_score >= 90:
        experience_reason = f"Your {exp_years} years of experience fits well within the {exp_range} this role expects."
    elif exp_score >= 60:
        experience_reason = f"Your {exp_years} years of experience is reasonably close to the {exp_range} this role expects."
    else:
        experience_reason = f"Your {exp_years} years of experience is notably outside the {exp_range} this role expects."

    loc_score = scores.get("location", 0)
    place = job.city or job.country or "an unspecified location"
    if job.work_mode == "remote":
        location_reason = "This role is fully remote, so location isn't a barrier."
    elif loc_score >= 90:
        location_reason = f"This role is based in {place}, matching your location."
    elif loc_score >= 60:
        location_reason = f"This role is based in {place} — reasonably close to your location or stated preferences."
    else:
        location_reason = f"This role is based in {place}, which is a stretch from your current location."

    role_score = scores.get("role", 0)
    if role_score >= 75:
        role_reason = f"The title \"{job.title}\" closely matches your recent experience or preferences."
    elif role_score >= 45:
        role_reason = f"The title \"{job.title}\" partially aligns with your recent experience or preferences."
    else:
        role_reason = f"The title \"{job.title}\" differs notably from your recent experience or stated preferences."

    domain_score = scores.get("domain", 0)
    job_domains = ", ".join(job.domain) if job.domain else "an unspecified domain"
    if domain_score >= 70:
        domain_reason = f"This role's domain ({job_domains}) aligns with your background."
    elif domain_score >= 40:
        domain_reason = f"This role's domain ({job_domains}) partially overlaps with your background."
    else:
        domain_reason = f"This role's domain ({job_domains}) has limited overlap with your background."

    concerns: list[str] = []
    if exp_score < 50:
        concerns.append("Experience level does not closely match the role's expected range.")
    if loc_score < 40:
        concerns.append("Location or work mode may require relocation or doesn't match your preferences.")
    if total_considered and len(missing_skills) > (len(matched_skills) + len(transferable_skills)):
        concerns.append("Several required or preferred skills are missing from your profile.")
    if scores.get("trust", 100) < 40:
        concerns.append("This posting has a lower source-trust score than most listings.")

    total = scores.get("total")
    category = scores.get("category")
    skill_summary = f"{len(matched_skills)} of {total_considered} key skills matched" if total_considered else "no listed skill requirements to compare"
    if transferable_skills:
        skill_summary += f", {len(transferable_skills)} transferable"
    if total is not None and category is not None:
        overall_reason = f"Overall {category} match ({total:.0f}/100): {skill_summary}. {experience_reason}"
    else:
        overall_reason = f"{skill_summary}. {experience_reason}"

    return {
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "transferable_skills": transferable_skills,
        "experience_reason": _trunc(experience_reason, 500),
        "location_reason": _trunc(location_reason, 500),
        "role_reason": _trunc(role_reason, 500),
        "domain_reason": _trunc(domain_reason, 500),
        "overall_reason": _trunc(overall_reason, 1000),
        "concerns": concerns or None,
    }
