from app.analysis.metrics import recompute_tract_metrics
from app.db.session import SessionLocal
from app.logging import get_logger
from app.workers.celery_app import celery_app

LOGGER = get_logger(__name__)


@celery_app.task(name="app.workers.tasks.score.recompute_scores")
def recompute_scores() -> dict[str, object]:
    LOGGER.info("metric_recompute_task_started")
    try:
        with SessionLocal() as db:
            result = recompute_tract_metrics(db)
        LOGGER.info(
            "metric_recompute_task_completed",
            tracts_seen=result.tracts_seen,
            metrics_written=result.metrics_written,
            metrics_skipped=result.metrics_skipped,
        )
        return {
            "status": "succeeded",
            "tracts_seen": result.tracts_seen,
            "metrics_written": result.metrics_written,
            "metrics_skipped": result.metrics_skipped,
            "transit_available": result.transit_available,
            "metadata": result.metadata,
        }
    except Exception:
        LOGGER.exception("metric_recompute_task_failed")
        raise
