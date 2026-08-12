import asyncio
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.llm_provider import LLMError
from app.api.v1.router import api_router
from app.config import get_settings
from app.jobs_ingestion.ingestion_worker import scheduler_loop

# Real-world job postings/resumes routinely contain emoji and other non-ASCII
# characters. Windows' console defaults to a legacy codepage (cp1252) that
# can't encode most of them, which crashes any log line touching that text
# with UnicodeEncodeError -- this took down an entire ingestion cycle over a
# single 🚀 in a job description. Force UTF-8 on stdout/stderr regardless of
# platform so logging can never be the thing that fails.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

settings = get_settings()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task: asyncio.Task | None = None
    if settings.ingestion_scheduler_enabled:
        # Keep a reference so the task isn't garbage-collected mid-flight --
        # a classic asyncio footgun for fire-and-forget background loops.
        task = asyncio.create_task(scheduler_loop())
    yield
    if task is not None:
        task.cancel()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI resume-to-job discovery and matching platform.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMError)
async def llm_error_handler(request, exc: LLMError) -> JSONResponse:
    logger.error("llm_error", path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=503,
        content={"detail": "AI analysis is temporarily unavailable. Your saved profile and jobs remain accessible."},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


app.include_router(api_router, prefix=settings.api_v1_prefix)
