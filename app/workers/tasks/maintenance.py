from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.maintenance.prune_old_snapshots")
def prune_old_snapshots() -> dict[str, str]:
    return {"status": "not_implemented"}

