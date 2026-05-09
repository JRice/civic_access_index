from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.index.reindex_search")
def reindex_search() -> dict[str, str]:
    return {"status": "not_implemented"}

