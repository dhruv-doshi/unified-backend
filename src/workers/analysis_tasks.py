import uuid
import httpx
from sqlalchemy.orm import Session, sessionmaker
from src.workers.celery_app import celery_app
from src.core.config import settings
from src.core.llm import LLMClientSync
from src.core.logging import get_logger
from src.apps.shoot_right_config import ANALYSIS_MODEL_1, ANALYSIS_MODEL_2
from src.infrastructure.models.analysis import Analysis
from src.infrastructure.database import sync_engine

logger = get_logger(__name__)

_SessionLocal = sessionmaker(bind=sync_engine)


def _get_sync_session() -> Session:
    return _SessionLocal()


@celery_app.task(name="analyze_image_task", bind=True, max_retries=3)
def analyze_image_task(self, analysis_id: str):
    logger.info("task_started", analysis_id=analysis_id)

    db = _get_sync_session()
    try:
        analysis = db.query(Analysis).filter(Analysis.id == uuid.UUID(analysis_id)).first()
        if not analysis:
            logger.error("analysis_not_found", analysis_id=analysis_id)
            return

        analysis.status = "processing"
        db.commit()

        # Download image from storage
        image_url = analysis.original_url
        with httpx.Client(timeout=30) as client:
            response = client.get(image_url)
            response.raise_for_status()
            image_bytes = response.content

        # Call LLM (two-step pipeline)
        client = LLMClientSync()
        result = client.analyze_image(image_bytes, model1=ANALYSIS_MODEL_1, model2=ANALYSIS_MODEL_2)

        # Update analysis
        analysis.status = "completed"
        analysis.overall_score = result.get("overall_score")
        analysis.summary_headline = result.get("summary_headline")
        analysis.summary_text = result.get("summary_text")
        analysis.composition = result.get("composition")
        analysis.technical = result.get("technical")
        analysis.color_aesthetic = result.get("color_aesthetic")
        analysis.clicking_tips = result.get("clicking_tips")
        analysis.editing_tips = result.get("editing_tips")
        db.commit()

        logger.info("task_completed", analysis_id=analysis_id, score=result.get("overall_score"))

    except Exception as exc:
        logger.error("task_failed", analysis_id=analysis_id, error=str(exc))
        try:
            failed = db.query(Analysis).filter(Analysis.id == uuid.UUID(analysis_id)).first()
            if failed:
                failed.status = "failed"
                failed.error_message = str(exc)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
    finally:
        db.close()

