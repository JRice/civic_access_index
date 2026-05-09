from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.normalize.normalize_pending_records")
def normalize_pending_records() -> dict[str, str]:
    return {"status": "not_implemented"}

