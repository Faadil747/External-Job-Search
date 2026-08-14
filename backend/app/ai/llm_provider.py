"""LLMProvider abstraction. Swap providers via LLM_PROVIDER env var — no other
code should import Groq/RunPod SDKs directly."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

settings = get_settings()


class LLMError(Exception):
    """Raised when the LLM provider fails after retries. Callers must catch this
    and degrade gracefully (see app/core/exceptions.py) rather than crash."""


class LLMProvider(ABC):
    @abstractmethod
    async def complete_json(
        self, system_prompt: str, user_prompt: str, schema_hint: str = ""
    ) -> dict[str, Any]:
        """Return a validated JSON object. Implementations must ask the model for
        JSON-only output and raise LLMError on unparsable/empty responses."""

    @abstractmethod
    async def complete_text(self, system_prompt: str, user_prompt: str) -> str:
        ...


def _extract_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"No JSON object found in LLM response: {raw[:200]!r}")
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"Malformed JSON from LLM: {exc}") from exc


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise LLMError(
                    "GROQ_API_KEY is not configured. Set it in backend/.env to enable AI features."
                )
            from groq import AsyncGroq

            self._client = AsyncGroq(api_key=self.api_key)
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    async def complete_json(
        self, system_prompt: str, user_prompt: str, schema_hint: str = ""
    ) -> dict[str, Any]:
        client = self._get_client()
        full_system = system_prompt + (
            f"\n\nRespond ONLY with a single JSON object matching this shape:\n{schema_hint}"
            if schema_hint
            else "\n\nRespond ONLY with a single valid JSON object. No prose, no markdown fences."
        )
        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": full_system},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # noqa: BLE001 - external SDK errors vary
            raise LLMError(f"Groq request failed: {exc}") from exc
        content = resp.choices[0].message.content or ""
        return _extract_json(content)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    async def complete_text(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Groq request failed: {exc}") from exc
        return resp.choices[0].message.content or ""


class RunPodLlamaProvider(LLMProvider):
    """A self-hosted model served by Ollama (https://ollama.com) on a RunPod
    GPU pod, reached through RunPod's HTTP proxy (the /proxy.runpod.net URL —
    Ollama's default port 11434 is the giveaway). Confirmed live against this
    exact deployment: `GET /` -> "Ollama is running", `GET /api/tags` lists
    the pulled models.

    Uses Ollama's native /api/chat endpoint (not an OpenAI-compat shim) with
    `format: "json"` for structured output -- Ollama enforces valid JSON
    syntax at the sampling level for that flag, which is more reliable than
    prompt-only JSON instructions. `keep_alive` is set generously so the
    model stays resident in GPU memory across the 2-3 sequential calls a
    single resume-processing pipeline run makes; the very first call after
    the pod has been idle still pays a real model-load cost (~4s observed
    live for qwen2.5:14b) before generation even starts, which is why the
    timeout here is generous.

    No API key is required by this specific deployment (Ollama has no
    built-in auth; RunPod's proxy URL itself is the access control) --
    RUNPOD_API_KEY is accepted and forwarded as a Bearer token if set, in
    case a future deployment sits behind an authenticating proxy, but is
    optional.
    """

    def __init__(self, api_key: str | None = None, endpoint: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.runpod_api_key
        self.endpoint = (endpoint or settings.runpod_endpoint).rstrip("/")
        self.model = model or settings.runpod_model
        if not self.endpoint:
            raise LLMError("RUNPOD_ENDPOINT is not configured. Set it in backend/.env to enable AI features.")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    async def complete_json(
        self, system_prompt: str, user_prompt: str, schema_hint: str = ""
    ) -> dict[str, Any]:
        full_system = system_prompt + (
            f"\n\nRespond ONLY with a single JSON object matching this shape:\n{schema_hint}"
            if schema_hint
            else "\n\nRespond ONLY with a single valid JSON object. No prose, no markdown fences."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": full_system},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": 0.2},
        }
        try:
            import httpx

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{self.endpoint}/api/chat", json=payload, headers=self._headers())
                resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - httpx/network errors vary
            raise LLMError(f"RunPod/Ollama request failed: {exc}") from exc
        content = (resp.json().get("message") or {}).get("content") or ""
        return _extract_json(content)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    async def complete_text(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": 0.3},
        }
        try:
            import httpx

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{self.endpoint}/api/chat", json=payload, headers=self._headers())
                resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"RunPod/Ollama request failed: {exc}") from exc
        return (resp.json().get("message") or {}).get("content") or ""


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "groq":
        return GroqProvider()
    if settings.llm_provider == "runpod":
        return RunPodLlamaProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")
