import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResumeUploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    original_filename: str
    processing_status: str
    created_at: datetime


class ResumeStatusOut(BaseModel):
    id: uuid.UUID
    processing_status: str
    error_message: str | None = None


class RecommendedRole(BaseModel):
    title: str
    confidence: int
    tier: str  # excellent | strong | good | stretch | low
    reason: str
    matching_skills: list[str] = []
    missing_skills: list[str] = []


class ResumeAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    overall_score: int
    score_breakdown: dict
    strengths: list[str]
    improvement_suggestions: list[str]
    recommended_roles: list[RecommendedRole]
    created_at: datetime


class JobFitOut(BaseModel):
    job_id: uuid.UUID
    resume_match_pct: int
    strong_skills: list[str]
    partial_skills: list[str]
    missing_skills: list[str]
    summary: str
