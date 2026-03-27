"""
tasks/celery_app.py — Celery application setup with Redis broker.
"""

import os
from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "et_intelligence",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.tasks.scheduled"],
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
    result_expires=3600,  # Results expire after 1 hour
    broker_connection_retry_on_startup=True,
)

# Celery Beat schedule — all times in UTC (IST = UTC+5:30)
celery_app.conf.beat_schedule = {
    # 6:00 PM IST = 12:30 UTC
    "daily-data-refresh": {
        "task": "backend.tasks.scheduled.daily_data_refresh",
        "schedule": crontab(hour=12, minute=30, day_of_week="1-5"),
    },
    # 6:30 PM IST = 13:00 UTC
    "scan-opportunity-radar": {
        "task": "backend.tasks.scheduled.scan_opportunity_radar",
        "schedule": crontab(hour=13, minute=0, day_of_week="1-5"),
    },
    # 7:00 PM IST = 13:30 UTC
    "scan-chart-patterns": {
        "task": "backend.tasks.scheduled.scan_chart_patterns_nifty50",
        "schedule": crontab(hour=13, minute=30, day_of_week="1-5"),
    },
    # 7:30 PM IST = 14:00 UTC
    "update-embeddings": {
        "task": "backend.tasks.scheduled.update_embeddings",
        "schedule": crontab(hour=14, minute=0, day_of_week="1-5"),
    },
}
