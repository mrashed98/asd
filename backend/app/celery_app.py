"""Celery application configuration."""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

# Create Celery app
celery_app = Celery(
    "arabseed_downloader",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.episode_checker", "app.tasks.download_monitor"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    "check-new-episodes": {
        "task": "app.tasks.episode_checker.check_new_episodes",
        "schedule": crontab(minute=0, hour=f"*/{settings.check_interval_hours}"),
    },
    "sync-downloads": {
        "task": "app.tasks.download_monitor.sync_downloads",
        "schedule": crontab(minute=f"*/{settings.download_sync_interval_minutes}"),
    },
}

