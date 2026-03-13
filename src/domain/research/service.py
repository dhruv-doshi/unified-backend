import json
import httpx
import arxiv
from datetime import timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, desc

from src.core.config import settings
from src.core.logging import get_logger
from src.core.exceptions import NotFoundError
from src.infrastructure.models.paper import Paper

logger = get_logger(__name__)

DEFAULT_MODEL = "google/gemini-2.0-flash-001"
EMBEDDING_MODEL = "openai/text-embedding-ada-002"
EMBEDDING_DIM = 1536


async def _embed_text(text_content: str) -> list[float] | None:
    """Call OpenRouter embedding endpoint."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.OPENROUTER_BASE_URL}/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"model": EMBEDDING_MODEL, "input": text_content},
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]
    except Exception as e:
        logger.warning("embedding_failed", error=str(e))
        return None


async def fetch_papers(
    db: AsyncSession,
    query: str,
    max_results: int | None = None,
    categories: list[str] | None = None,
) -> list[Paper]:
    """Fetch papers from arXiv and upsert into DB with embeddings."""
    limit = max_results or settings.ARXIV_MAX_RESULTS

    search_query = query
    if categories:
        cat_filter = " OR ".join(f"cat:{c}" for c in categories)
        search_query = f"({query}) AND ({cat_filter})"

    client = arxiv.Client()
    search = arxiv.Search(
        query=search_query,
        max_results=limit,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )

    stored: list[Paper] = []
    for result in client.results(search):
        arxiv_id = result.entry_id.split("/abs/")[-1]

        # Check if already exists
        existing = await db.execute(select(Paper).where(Paper.arxiv_id == arxiv_id))
        paper = existing.scalar_one_or_none()

        if paper is None:
            # Embed the abstract for semantic search
            embedding = await _embed_text(result.summary)

            # Compute tsvector for full-text search
            fts_text = f"{result.title} {result.summary}"

            paper = Paper(
                arxiv_id=arxiv_id,
                title=result.title,
                abstract=result.summary,
                authors=[str(a) for a in result.authors],
                url=result.entry_id,
                categories=[str(c) for c in result.categories] if result.categories else [],
                published_at=result.published.replace(tzinfo=timezone.utc) if result.published else None,
                embedding=embedding,
            )
            db.add(paper)
            await db.flush()

            # Update search vector via SQL
            await db.execute(
                text(
                    "UPDATE papers SET search_vector = to_tsvector('english', :txt) WHERE id = :id"
                ),
                {"txt": fts_text, "id": str(paper.id)},
            )
            stored.append(paper)

    await db.commit()
    return stored


async def list_papers(
    db: AsyncSession,
    offset: int = 0,
    limit: int = 20,
    category: str | None = None,
) -> list[Paper]:
    q = select(Paper).order_by(desc(Paper.published_at)).offset(offset).limit(limit)
    if category:
        # JSON @> operator: check if categories array contains the given string
        # Cast parameter explicitly to jsonb to avoid asyncpg type inference issues
        q = q.where(text(f"categories::jsonb @> '[{json.dumps(category)}]'::jsonb"))
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_paper(db: AsyncSession, paper_id: str) -> Paper:
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise NotFoundError("Paper")
    return paper


async def search_papers(db: AsyncSession, query: str, limit: int = 20) -> list[Paper]:
    """Full-text search + optional semantic fallback."""
    # Try full-text search first
    fts_result = await db.execute(
        text(
            """
            SELECT * FROM papers
            WHERE search_vector @@ plainto_tsquery('english', :query)
            ORDER BY ts_rank(search_vector, plainto_tsquery('english', :query)) DESC
            LIMIT :limit
            """
        ),
        {"query": query, "limit": limit},
    )
    rows = fts_result.fetchall()

    # If few FTS results, supplement with semantic search
    if len(rows) < 5:
        embedding = await _embed_text(query)
        if embedding:
            sem_result = await db.execute(
                text(
                    """
                    SELECT * FROM papers
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:emb AS vector)
                    LIMIT :limit
                    """
                ),
                {"emb": str(embedding), "limit": limit},
            )
            sem_rows = sem_result.fetchall()
            # Merge, dedup by id
            seen = {r.id for r in rows}
            rows = list(rows) + [r for r in sem_rows if r.id not in seen]

    if not rows:
        return []

    ids = [r.id for r in rows]
    orm_result = await db.execute(select(Paper).where(Paper.id.in_(ids)))
    papers_map = {str(p.id): p for p in orm_result.scalars().all()}
    return [papers_map[str(r.id)] for r in rows if str(r.id) in papers_map]


async def ai_query(db: AsyncSession, query: str, limit: int = 5) -> tuple[str, list[Paper]]:
    """Find semantically relevant papers then generate an answer with LLM."""
    embedding = await _embed_text(query)

    if embedding:
        sem_result = await db.execute(
            text(
                """
                SELECT id FROM papers
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:emb AS vector)
                LIMIT :limit
                """
            ),
            {"emb": str(embedding), "limit": limit},
        )
        paper_ids = [row.id for row in sem_result.fetchall()]
    else:
        paper_ids = []

    # Fallback to FTS if no embeddings available
    if not paper_ids:
        papers = await search_papers(db, query, limit)
    else:
        orm_result = await db.execute(select(Paper).where(Paper.id.in_(paper_ids)))
        papers = list(orm_result.scalars().all())

    if not papers:
        return "No relevant papers found in the database for this query.", []

    context = "\n\n".join(
        f"**{p.title}** ({p.arxiv_id})\n{p.abstract[:500]}" for p in papers
    )

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a research assistant. Use the provided paper abstracts to answer "
                    "the user's question. Cite papers by their arXiv ID. Be concise and accurate."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {query}\n\nRelevant papers:\n{context}",
            },
        ],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"]

    return answer, papers
