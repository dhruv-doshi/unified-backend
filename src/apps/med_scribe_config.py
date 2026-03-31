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
}

IMPORTANT for medications and action_items:
- For medications, return each as EITHER:
  1. A simple string: "Drug Name dose route" (e.g., "Lisinopril 10mg oral")
  2. OR a structured object: {"name": "...", "dosage": "...", "route": "..."}
  Prefer structured objects when all three fields are clearly identifiable.

- For action_items, return each as EITHER:
  1. A simple string: "action description"
  2. OR a structured object: {"text": "action description"}
  Prefer simple strings unless extra structure is needed.

The frontend will handle both formats seamlessly.""",
}

DIARIZATION_PROMPT = """You are a medical transcription assistant. Given a raw transcript, identify distinct speakers
and label them as "Doctor", "Patient", or "Other [n]" based on conversational context and patterns.

Return ONLY valid JSON with no additional text:
{
  "segments": [
    {"speaker": "Doctor", "text": "..."},
    {"speaker": "Patient", "text": "..."}
  ]
}"""

SUGGESTIONS_PROMPT = """You are a clinical observation assistant. Based on the clinical conversation provided, generate 3-5 follow-up observation questions
that a doctor would typically need to answer during a physical exam, but were NOT explicitly mentioned in the conversation.

For each question:
1. Create a natural clinical question
2. Provide 4 realistic MCQ answer options (mutually exclusive and appropriate for the scenario)
3. Assign a category: "observation" (for exam findings) or "plan" (for treatment decisions)

Return ONLY valid JSON with no additional text:
{
  "suggestions": [
    {
      "id": "<uuid>",
      "question": "Did you hear any abnormal lung sounds on auscultation?",
      "options": ["Clear bilateral breath sounds", "Crackles suggesting fluid buildup", "Wheezing suggesting bronchospasm", "Other abnormality"],
      "category": "observation"
    }
  ]
}

Guidelines:
- Suggestions should surface clinically-relevant findings not redundant with the SOAP note
- Keep options realistic and mutually exclusive
- Include 3-5 suggestions total, prioritizing high-value observations
- For treatment decisions, options should reflect evidence-based choices"""
