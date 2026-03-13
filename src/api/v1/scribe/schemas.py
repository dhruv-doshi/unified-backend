import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator
from typing import Any

VALID_NOTE_TYPES = {"general", "meeting", "research", "clinical"}


class SummarizeRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text cannot be empty")
        return v


class GenerateNotesRequest(BaseModel):
    text: str
    note_type: str = "general"  # general | meeting | research | clinical

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text cannot be empty")
        return v

    @field_validator("note_type")
    @classmethod
    def note_type_valid(cls, v: str) -> str:
        if v not in VALID_NOTE_TYPES:
            raise ValueError(f"note_type must be one of {sorted(VALID_NOTE_TYPES)}")
        return v


class ScribeSessionResponse(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    result: Any | None
    created_at: datetime

    model_config = {"from_attributes": True}
