from pydantic import BaseModel
from typing import Any
import uuid
from datetime import datetime


class UploadResponse(BaseModel):
    analysisId: uuid.UUID
    status: str
    message: str


class ImprovementShotResponse(BaseModel):
    url: str | None
    explanation: str
    generatedAt: datetime


class AnalysisResponse(BaseModel):
    id: uuid.UUID
    imageUrl: str | None
    thumbnailUrl: str | None
    filename: str
    uploadedAt: datetime
    status: str
    overallScore: int | None = None
    summaryHeadline: str | None = None
    summaryText: str | None = None
    metadata: dict[str, Any] | None = None
    histogram: dict[str, Any] | None = None
    composition: dict[str, Any] | None = None
    technical: dict[str, Any] | None = None
    colorAesthetic: dict[str, Any] | None = None
    clickingTips: list[str] | None = None
    editingTips: list[str] | None = None
    improvementShot: ImprovementShotResponse | None = None
