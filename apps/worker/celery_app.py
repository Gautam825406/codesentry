"""Celery app (used only when CELERY_BROKER_URL / REDIS_URL is set)."""
from __future__ import annotations
import os
from settings import settings

try:
    from celery import Celery
    celery_app = Celery("codesentry", broker=settings.CELERY_BROKER_URL,
                        backend=settings.CELERY_BROKER_URL)
    celery_app.conf.update(task_serializer="json", result_serializer="json",
                           accept_content=["json"], timezone="UTC",
                           task_acks_late=True, worker_prefetch_multiplier=1)
except Exception as e:  # celery not installed: the thread fallback is used
    celery_app = None
    print(f"[celery] unavailable ({e}); using in-process queue fallback")
