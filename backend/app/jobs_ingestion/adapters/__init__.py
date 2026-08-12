from app.jobs_ingestion.adapters.adzuna_adapter import AdzunaAdapter
from app.jobs_ingestion.adapters.jsearch_adapter import JSearchAdapter
from app.jobs_ingestion.adapters.seed_adapter import SeedAdapter
from app.jobs_ingestion.source_interface import JobSourceAdapter

ADAPTER_REGISTRY: dict[str, type[JobSourceAdapter]] = {
    "seed": SeedAdapter,
    "adzuna": AdzunaAdapter,
    "jsearch": JSearchAdapter,
}

__all__ = ["ADAPTER_REGISTRY", "SeedAdapter", "AdzunaAdapter", "JSearchAdapter"]
