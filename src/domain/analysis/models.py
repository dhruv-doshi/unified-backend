from pydantic import BaseModel
from typing import Any
import uuid
from datetime import datetime


class LLMAnalysisResult(BaseModel):
    overall_score: int
    summary_headline: str
    summary_text: str
    composition: dict[str, Any]
    technical: dict[str, Any]
    color_aesthetic: dict[str, Any]
    clicking_tips: list[str]
    editing_tips: list[str]
