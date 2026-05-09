from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "civic_access_index",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks.ingest",
        "app.workers.tasks.normalize",
        "app.workers.tasks.score",
        "app.workers.tasks.index",
        "app.workers.tasks.maintenance",
    ],
)

celery_app.conf.task_routes = {
    "app.workers.tasks.ingest.*": {"queue": "ingestion"},
    "app.workers.tasks.score.*": {"queue": "analysis"},
    "app.workers.tasks.index.*": {"queue": "search"},
}

