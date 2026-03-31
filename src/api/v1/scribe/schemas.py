import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator, ConfigDict
from typing import Any, Union, Optional

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


# --- Transcription ---
class SpeakerSegment(BaseModel):
    speaker: str
    text: str


class TranscribeResponse(BaseModel):
    segments: list[SpeakerSegment]
    full_text: str


class ChunkTranscribeResponse(BaseModel):
    text: str  # Raw transcript for this audio chunk, no speaker labels


# --- Doctor Answers ---
class DoctorSuggestion(BaseModel):
    id: str = None
    question: str
    options: list[str]
    category: str  # "observation" | "plan"

    def __init__(self, **data):
        if "id" not in data or data["id"] is None:
            data["id"] = str(uuid.uuid4())
        super().__init__(**data)


class DoctorSuggestionAnswer(BaseModel):
    suggestion_id: str
    selected_option: str | None = None
    custom_answer: str = ""


class DoctorAnswersRequest(BaseModel):
    answers: list[DoctorSuggestionAnswer]


# --- Session CRUD ---
class UpdateSessionRequest(BaseModel):
    title: str | None = None
    result: dict | None = None  # Partial NoteGenerationResult


# --- Polymorphic Types for Note Fields ---
class Medication(BaseModel):
    """Structured medication representation."""
    name: str
    dosage: str
    route: str


class ActionItem(BaseModel):
    """Structured action item representation."""
    text: str


class Finding(BaseModel):
    """Structured finding representation."""
    description: str


class NoteGenerationResult(BaseModel):
    """Clinical note generation result with polymorphic array fields."""
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None

    # Polymorphic arrays — can be string OR structured object
    medications: Optional[list[Union[str, Medication]]] = None
    action_items: Optional[list[Union[str, ActionItem]]] = None
    findings: Optional[list[Union[str, Finding]]] = None
    follow_up: Optional[str] = None

    # Doctor suggestions from clinical notes
    suggestions: Optional[list[DoctorSuggestion]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subjective": "Patient reports chest pain",
                "objective": "BP 120/80, HR 72",
                "assessment": "Stable angina",
                "plan": "Cardiology referral",
                "medications": [
                    "Aspirin 500mg oral",  # string format
                    {"name": "Lisinopril", "dosage": "10mg", "route": "oral"},  # object format
                ],
                "action_items": [
                    "Schedule follow-up in 2 weeks",
                    {"text": "Run blood tests"},
                ],
                "follow_up": "Cardiology consultation",
                "suggestions": [
                    {
                        "id": "sugg-1",
                        "question": "Did you observe any arrhythmias?",
                        "options": ["Regular", "Irregular", "Tachycardia", "Bradycardia"],
                        "category": "observation",
                    }
                ],
            }
        }
    )


# --- Updated Response ---
class ScribeSessionResponse(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    result: Any | None
    title: str | None = None
    doctor_answers: list[DoctorSuggestionAnswer] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
