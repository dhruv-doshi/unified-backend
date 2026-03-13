import asyncio
from src.workers.celery_app import celery_app
from src.core.logging import get_logger
from src.infrastructure.database import AsyncSessionLocal
from src.domain.research import service as research_service

logger = get_logger(__name__)

# Topics fetched daily — covers major AI/ML research areas
DAILY_FETCH_JOBS = [
    {"query": "large language models", "categories": ["cs.CL", "cs.AI"]},
    {"query": "computer vision deep learning", "categories": ["cs.CV"]},
    {"query": "reinforcement learning", "categories": ["cs.LG", "cs.AI"]},
    {"query": "diffusion models generative", "categories": ["cs.CV", "cs.LG"]},
]


async def _run_fetch(query: str, categories: list[str]) -> int:
    async with AsyncSessionLocal() as db:
        papers = await research_service.fetch_papers(db, query=query, categories=categories)
        return len(papers)


@celery_app.task(name="fetch_daily_papers", bind=True, max_retries=2)
def fetch_daily_papers(self):
    logger.info("fetch_daily_papers_started")
    total_new = 0
    for job in DAILY_FETCH_JOBS:
        try:
            n = asyncio.run(_run_fetch(job["query"], job["categories"]))
            total_new += n
            logger.info("fetch_job_done", query=job["query"], new_papers=n)
        except Exception as exc:
            logger.error("fetch_job_failed", query=job["query"], error=str(exc))
    logger.info("fetch_daily_papers_completed", total_new=total_new)
    return total_new
