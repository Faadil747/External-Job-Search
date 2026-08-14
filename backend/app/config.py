from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MatchWeights(BaseSettings):
    skills: float = 0.25
    experience: float = 0.20
    role: float = 0.15
    semantic: float = 0.15
    location: float = 0.10
    domain: float = 0.05
    education: float = 0.03
    work_mode: float = 0.03
    recency: float = 0.02
    trust: float = 0.02


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "JobMatch AI"
    app_env: str = "development"
    secret_key: str = "insecure-dev-key-change-me"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000"

    database_url: str = "postgresql+asyncpg://jobmatch:jobmatch@localhost:5432/jobmatch"
    database_url_sync: str = "postgresql+psycopg2://jobmatch:jobmatch@localhost:5432/jobmatch"

    redis_url: str = "redis://localhost:6379/0"

    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    runpod_api_key: str = ""
    runpod_endpoint: str = ""
    runpod_model: str = "qwen2.5:14b"

    embedding_provider: str = "local"
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    vector_store: str = "pgvector"
    qdrant_url: str = ""

    job_sources_enabled: str = "seed"
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    jsearch_rapidapi_key: str = ""
    jsearch_queries: str = "software developer jobs,backend developer jobs"
    jsearch_country: str = "in"
    jsearch_num_pages: int = 1
    theirstack_api_key: str = ""
    theirstack_queries: str = "Backend Developer,Python Developer,Software Engineer"
    theirstack_country: str = "IN"
    theirstack_max_age_days: int = 3
    theirstack_limit_per_query: int = 10

    resume_storage_dir: str = "./storage/resumes"
    max_resume_size_mb: int = 10

    weight_skills: float = 0.25
    weight_experience: float = 0.20
    weight_role: float = 0.15
    weight_semantic: float = 0.15
    weight_location: float = 0.10
    weight_domain: float = 0.05
    weight_education: float = 0.03
    weight_work_mode: float = 0.03
    weight_recency: float = 0.02
    weight_trust: float = 0.02

    duplicate_threshold: float = 0.85
    fresh_job_window_days: int = 3

    ingestion_scheduler_enabled: bool = True
    ingestion_interval_minutes: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def job_sources_enabled_list(self) -> list[str]:
        return [s.strip() for s in self.job_sources_enabled.split(",") if s.strip()]

    @property
    def jsearch_queries_list(self) -> list[str]:
        return [q.strip() for q in self.jsearch_queries.split(",") if q.strip()]

    @property
    def theirstack_queries_list(self) -> list[str]:
        return [q.strip() for q in self.theirstack_queries.split(",") if q.strip()]

    @property
    def match_weights(self) -> dict[str, float]:
        return {
            "skills": self.weight_skills,
            "experience": self.weight_experience,
            "role": self.weight_role,
            "semantic": self.weight_semantic,
            "location": self.weight_location,
            "domain": self.weight_domain,
            "education": self.weight_education,
            "work_mode": self.weight_work_mode,
            "recency": self.weight_recency,
            "trust": self.weight_trust,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
