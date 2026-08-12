"""EmbeddingProvider abstraction. Swap via EMBEDDING_PROVIDER env var.

Default is a local sentence-transformers model so embeddings work with zero API
keys. All vectors must be EMBEDDING_DIM-length floats — keep providers aligned
with app.config.Settings.embedding_dim or migrate the pgvector column.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache

from app.config import get_settings

settings = get_settings()


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class LocalEmbeddingProvider(EmbeddingProvider):
    """Runs sentence-transformers locally — no external API calls, no cost."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.local_embedding_model
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return vectors.tolist()


class GroqEmbeddingProvider(EmbeddingProvider):
    """Placeholder: Groq does not currently serve an embeddings endpoint. Kept
    for interface symmetry with LLMProvider; falls back to local embeddings."""

    def __init__(self) -> None:
        self._fallback = LocalEmbeddingProvider()

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._fallback.embed(texts)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_provider == "local":
        return LocalEmbeddingProvider()
    if settings.embedding_provider == "groq":
        return GroqEmbeddingProvider()
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider}")
