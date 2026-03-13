from celery import Celery
from celery.schedules import crontab
from src.core.config import settings

celery_app = Celery(
    "unified-backend",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["src.workers.analysis_tasks", "src.workers.research_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "fetch-daily-papers": {
            "task": "fetch_daily_papers",
            "schedule": crontab(hour=6, minute=0),  # 6 AM UTC every day
        },
    },
)
