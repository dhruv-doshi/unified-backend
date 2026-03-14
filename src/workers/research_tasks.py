import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.workers.celery_app import celery_app
from src.core.config import settings
from src.core.logging import get_logger
from src.domain.research import service as research_service
from src.apps.research_digest_config import DAILY_FETCH_JOBS

logger = get_logger(__name__)


async def _run_all_fetches() -> int:
    # Create a fresh engine+session scoped to this event loop to avoid
    # "Future attached to a different loop" errors from reusing the shared pool.
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    total = 0
    try:
        for job in DAILY_FETCH_JOBS:
            try:
                async with Session() as db:
                    papers = await research_service.fetch_papers(
                        db, query=job["query"], categories=job["categories"]
                    )
                n = len(papers)
                total += n
                logger.info("fetch_job_done", query=job["query"], new_papers=n)
            except Exception as exc:
                logger.error("fetch_job_failed", query=job["query"], error=str(exc))
    finally:
        await engine.dispose()

    return total


@celery_app.task(name="fetch_daily_papers", bind=True, max_retries=2)
def fetch_daily_papers(self):
    logger.info("fetch_daily_papers_started")
    total_new = asyncio.run(_run_all_fetches())
    logger.info("fetch_daily_papers_completed", total_new=total_new)
    return total_new
