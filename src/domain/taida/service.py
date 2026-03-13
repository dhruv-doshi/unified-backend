import uuid
import json
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from src.core.config import settings
from src.core.logging import get_logger
from src.core.exceptions import NotFoundError, ForbiddenError
from src.infrastructure.models.taida import TaidaAnalysis

logger = get_logger(__name__)

DEFAULT_MODEL = "google/gemini-2.0-flash-001"

COMPETITOR_PROMPT = """\
You are a business intelligence analyst. Analyze the competitive landscape.

Product: {product}
Target Market: {target_market}
Sector: {sector}
Known Competitors: {competitors}

Return a JSON object with exactly this structure:
{{
  "competitors": [
    {{
      "name": "...",
      "strengths": ["...", "..."],
      "weaknesses": ["...", "..."],
      "market_position": "description of market position",
      "threat_level": "low|medium|high"
    }}
  ],
  "market_positioning": "recommended positioning for the product",
  "competitive_gaps": ["gap 1", "gap 2"],
  "opportunities": ["opportunity 1", "opportunity 2"]
}}"""

LEGAL_PROMPT = """\
You are a legal and regulatory compliance expert. Identify key legal and regulatory considerations.

Product: {product}
Target Market: {target_market}
Sector: {sector}

Return a JSON object with exactly this structure:
{{
  "regulations": [
    {{
      "name": "regulation name",
      "jurisdiction": "country/region",
      "description": "what it requires",
      "compliance_status": "required|recommended|optional"
    }}
  ],
  "risks": [
    {{
      "type": "risk category",
      "severity": "low|medium|high|critical",
      "description": "description of the risk",
      "mitigation": "how to mitigate"
    }}
  ],
  "risk_score": <integer 0-100>,
  "risk_summary": "one paragraph summary of overall risk profile"
}}"""


async def _call_llm(prompt: str) -> dict:
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)


async def run_analysis(
    db: AsyncSession,
    user_id: uuid.UUID,
    product: str,
    target_market: str,
    sector: str,
    competitors: list[str],
) -> TaidaAnalysis:
    request_data = {
        "product": product,
        "target_market": target_market,
        "sector": sector,
        "competitors": competitors,
    }

    analysis = TaidaAnalysis(
        user_id=user_id,
        request_json=request_data,
        status="processing",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    try:
        # Step 1: Competitor analysis
        competitor_result = await _call_llm(
            COMPETITOR_PROMPT.format(
                product=product,
                target_market=target_market,
                sector=sector,
                competitors=", ".join(competitors),
            )
        )

        # Step 2: Legal/regulatory analysis
        legal_result = await _call_llm(
            LEGAL_PROMPT.format(
                product=product,
                target_market=target_market,
                sector=sector,
            )
        )

        analysis.result_json = {
            "competitor_analysis": competitor_result,
            "legal_analysis": legal_result,
        }
        analysis.status = "completed"
    except Exception as e:
        logger.error("taida_analysis_failed", analysis_id=str(analysis.id), error=str(e))
        analysis.status = "failed"
        analysis.error_message = str(e)

    await db.commit()
    await db.refresh(analysis)
    return analysis


async def list_analyses(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 20
) -> list[TaidaAnalysis]:
    result = await db.execute(
        select(TaidaAnalysis)
        .where(TaidaAnalysis.user_id == user_id)
        .order_by(desc(TaidaAnalysis.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_analysis(
    db: AsyncSession, analysis_id: uuid.UUID, user_id: uuid.UUID
) -> TaidaAnalysis:
    result = await db.execute(
        select(TaidaAnalysis).where(TaidaAnalysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise NotFoundError("TaidaAnalysis")
    if analysis.user_id != user_id:
        raise ForbiddenError()
    return analysis
