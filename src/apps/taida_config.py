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
