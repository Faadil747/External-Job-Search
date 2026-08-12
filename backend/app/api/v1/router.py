from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.candidate import router as candidate_router
from app.api.v1.resume import router as resume_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.applications import router as applications_router
from app.api.v1.ai_chat import router as ai_chat_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(candidate_router)
api_router.include_router(resume_router)
# recommendations_router (GET /jobs/recommended) must be registered before
# jobs_router (GET /jobs/{job_id}) -- FastAPI/Starlette match routes in
# registration order, so the parameterized route would otherwise greedily
# swallow "recommended" as a job_id and fail UUID parsing.
api_router.include_router(recommendations_router)
api_router.include_router(jobs_router)
api_router.include_router(applications_router)
api_router.include_router(ai_chat_router)
