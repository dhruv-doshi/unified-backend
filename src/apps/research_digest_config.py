DEFAULT_MODEL = "google/gemini-2.0-flash-001"
EMBEDDING_MODEL = "openai/text-embedding-ada-002"
EMBEDDING_DIM = 1536

AI_QUERY_SYSTEM_PROMPT = (
    "You are a research assistant. Use the provided paper abstracts to answer "
    "the user's question. Cite papers by their arXiv ID. Be concise and accurate."
)

# Topics fetched daily — covers major AI/ML research areas
DAILY_FETCH_JOBS = [
    {"query": "large language models", "categories": ["cs.CL", "cs.AI"]},
    {"query": "computer vision deep learning", "categories": ["cs.CV"]},
    {"query": "reinforcement learning", "categories": ["cs.LG", "cs.AI"]},
    {"query": "diffusion models generative", "categories": ["cs.CV", "cs.LG"]},
]
