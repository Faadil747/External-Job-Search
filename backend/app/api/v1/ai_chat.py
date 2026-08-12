"""AI Career Copilot (product spec section 47). RAG-grounded over the
candidate's real profile and real retrieved jobs via app/services/chat_service.py
— never lets the model answer from unguided general knowledge about specific
jobs. LLMError (e.g. GROQ_API_KEY unset) propagates to the global handler in
app/main.py for a clean 503, same as every other AI-dependent endpoint.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_candidate
from app.models.candidate import CandidateProfile
from app.services.chat_service import answer_chat_message

router = APIRouter(tags=["ai"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    job_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    reply: str


@router.post("/ai/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    candidate: CandidateProfile = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    reply = await answer_chat_message(db, candidate, payload.message, payload.job_id)
    return ChatResponse(reply=reply)
