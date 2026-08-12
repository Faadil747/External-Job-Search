import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SavedJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    job_id: uuid.UUID
    created_at: datetime


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    application_url: str
    apply_clicked_at: datetime | None
    applied_at: datetime | None
    notes: str | None
    created_at: datetime


class ApplicationStatusUpdate(BaseModel):
    status: str
    notes: str | None = None


class ApplyClickRequest(BaseModel):
    job_id: uuid.UUID
