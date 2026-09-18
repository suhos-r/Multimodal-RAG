"""Celery app. Falls back to synchronous mode when broker missing (tests/demo)."""
import os

USE_CELERY = bool(os.getenv("REDIS_URL", "")) and os.getenv("CELERY_SYNC", "") != "1"

if USE_CELERY:
    try:
        from celery import Celery
        celery_app = Celery("rag", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        celery_app.conf.update(task_acks_late=True, task_track_started=True, task_default_queue="ingest")
    except ImportError:
        celery_app = None
else:
    celery_app = None


def delay_or_run(fn, *args, **kwargs):
    """If celery available, delay; else run inline (demo/test)."""
    task = getattr(fn, "delay", None)
    if celery_app is not None and task is not None:
        try:
            return task(*args, **kwargs)
        except Exception:
            pass
    return fn(*args, **kwargs)
