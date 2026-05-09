from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.score.recompute_scores")
def recompute_scores() -> dict[str, str]:
    return {"status": "not_implemented"}

