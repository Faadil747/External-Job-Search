"""Natural-language job search: free text -> ParsedSearchFilters via the LLM.

If the LLM is unavailable (no GROQ_API_KEY, network failure, unparsable
output after retries), `get_llm_provider().complete_json` raises LLMError.
We deliberately let that propagate — app/main.py's global handler turns
LLMError into a 503 — rather than silently returning empty/fabricated
filters, since a search silently returning "everything" or "nothing" because
the parser failed would be a worse user experience than a clear "try again"
error.
"""

from __future__ import annotations

from pydantic import ValidationError

from app.ai.llm_provider import LLMError, get_llm_provider
from app.ai.prompts_job import parse_schema_hint, parse_system_prompt, parse_user_prompt
from app.schemas.job import ParsedSearchFilters

_LIST_FIELDS = {"role", "location", "work_mode", "employment_type", "skills"}


def _coerce(raw: dict) -> dict:
    """LLM JSON output is never fully trusted to match the schema exactly —
    coerce common shape issues (string instead of list, unknown keys) before
    handing off to Pydantic validation."""
    allowed = ParsedSearchFilters.model_fields.keys()
    cleaned: dict = {}
    for key in allowed:
        if key not in raw or raw[key] is None:
            continue
        value = raw[key]
        if key in _LIST_FIELDS:
            if isinstance(value, str):
                value = [value]
            if isinstance(value, list):
                cleaned[key] = [str(v) for v in value if v]
        else:
            cleaned[key] = value
    return cleaned


async def parse_natural_language_query(query: str) -> ParsedSearchFilters:
    provider = get_llm_provider()
    raw = await provider.complete_json(
        parse_system_prompt(), parse_user_prompt(query), schema_hint=parse_schema_hint()
    )
    cleaned = _coerce(raw if isinstance(raw, dict) else {})
    try:
        return ParsedSearchFilters(**cleaned)
    except ValidationError as exc:
        raise LLMError(f"LLM returned an unparsable filter shape: {exc}") from exc
