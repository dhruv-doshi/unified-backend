import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Any


class TaidaAnalyzeRequest(BaseModel):
    product: str
    target_market: str
    sector: str
    competitors: list[str]


class CompetitorInfo(BaseModel):
    name: str
    strengths: list[str]
    weaknesses: list[str]
    market_position: str
    threat_level: str  # low | medium | high


class CompetitorAnalysis(BaseModel):
    competitors: list[CompetitorInfo]
    market_positioning: str
    competitive_gaps: list[str]
    opportunities: list[str]


class RegulationInfo(BaseModel):
    name: str
    jurisdiction: str
    description: str
    compliance_status: str  # required | recommended | optional


class RiskInfo(BaseModel):
    type: str
    severity: str  # low | medium | high | critical
    description: str
    mitigation: str


class LegalAnalysis(BaseModel):
    regulations: list[RegulationInfo]
    risks: list[RiskInfo]
    risk_score: int  # 0-100
    risk_summary: str


class TaidaResult(BaseModel):
    competitor_analysis: CompetitorAnalysis
    legal_analysis: LegalAnalysis


class TaidaAnalysisResponse(BaseModel):
    id: uuid.UUID
    status: str
    request: dict
    result: TaidaResult | None
    created_at: datetime

    model_config = {"from_attributes": True}
