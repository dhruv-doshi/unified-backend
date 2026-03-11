# ── Models ────────────────────────────────────────────────────
ANALYSIS_MODEL_1 = "google/gemini-2.0-flash-001"   # vision → narrative text
ANALYSIS_MODEL_2 = "google/gemini-2.0-flash-001"   # vision + narrative → structured JSON
IMPROVEMENT_MODEL = "google/gemini-2.0-flash-001"  # text → improvement prescription

# ── Rate limits ───────────────────────────────────────────────
DAILY_ANALYSIS_LIMIT = 10   # uploads per user per day (IST midnight reset)
DAILY_IMPROVEMENT_LIMIT = 3  # improvement shots per user per day

# ── Prompts ───────────────────────────────────────────────────
MODEL_1_SYSTEM_PROMPT = """
You are an expert photography critic. Look at this image carefully and write a
detailed narrative analysis covering: composition, technical quality (sharpness,
exposure, noise), colour and aesthetic, mood, and notable strengths or weaknesses.
Be thorough. Return plain prose only — no JSON, no lists.
"""

MODEL_2_SYSTEM_PROMPT = """
You are an expert photography critic. You have already written a narrative
analysis of the image (provided below). Now convert that analysis into a
structured JSON object. Return ONLY valid JSON, no markdown, no code blocks,
exactly this shape:
{{
  "overall_score": <int 0-100>,
  "summary_headline": "<one sentence>",
  "summary_text": "<2-3 paragraph critique>",
  "composition":    {{"score": <int>, "strengths": [...], "weaknesses": [...], "details": "..."}},
  "technical":      {{"score": <int>, "sharpness": "excellent|good|fair|poor",
                     "exposure": "correct|slightly-over|overexposed|slightly-under|underexposed",
                     "noise": "minimal|low|moderate|high",
                     "strengths": [...], "weaknesses": [...], "details": "..."}},
  "color_aesthetic":{{"score": <int>, "dominant_colors": [{{"hex":"#RRGGBB","name":"...","percentage":<int>}}],
                     "color_harmony": "...", "mood": "...",
                     "strengths": [...], "weaknesses": [...], "details": "..."}},
  "clicking_tips": ["<tip>", ...],
  "editing_tips":  ["<tip>", ...]
}}

Narrative analysis:
{narrative}
"""

IMPROVEMENT_SYSTEM_PROMPT = """
You are an expert photography coach. Based on the analysis provided, give a
detailed, actionable improvement prescription. Describe exactly what changes
the photographer should make when taking the next shot. Be specific about camera
settings, composition adjustments, lighting considerations, and post-processing
suggestions. Write 3-5 paragraphs.
"""
