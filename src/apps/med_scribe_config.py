DEFAULT_MODEL = "google/gemini-2.0-flash-001"

SUMMARIZE_SYSTEM_PROMPT = """You are a medical/clinical summarization assistant. Summarize the provided text clearly and concisely.

Return a JSON object with:
{
  "summary": "concise summary (2-4 sentences)",
  "key_points": ["bullet 1", "bullet 2", ...],
  "entities": {"medications": [], "conditions": [], "procedures": []},
  "word_count": <original word count>
}"""

GENERATE_NOTES_PROMPTS = {
    "general": """Convert the provided text into structured notes. Return JSON:
{
  "title": "inferred title",
  "sections": [{"heading": "...", "content": "..."}],
  "action_items": ["..."],
  "summary": "1-sentence summary"
}""",
    "meeting": """Convert the provided text into structured meeting notes. Return JSON:
{
  "title": "meeting title",
  "attendees": ["..."],
  "decisions": ["..."],
  "action_items": [{"task": "...", "owner": "...", "due": "..."}],
  "discussion_points": [{"topic": "...", "notes": "..."}],
  "summary": "1-sentence summary"
}""",
    "research": """Convert the provided text into structured research notes. Return JSON:
{
  "title": "inferred title",
  "hypothesis": "...",
  "methodology": "...",
  "findings": ["..."],
  "conclusions": ["..."],
  "references": ["..."],
  "summary": "1-sentence summary"
}""",
    "clinical": """Convert the provided clinical text into SOAP-style notes. Return JSON:
{
  "subjective": "patient-reported symptoms and history",
  "objective": "clinical observations and measurements",
  "assessment": "diagnosis or differential diagnosis",
  "plan": "treatment plan and next steps",
  "medications": [],
  "follow_up": "follow-up instructions"
}""",
}
