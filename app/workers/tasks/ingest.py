import asyncio

from httpx import HTTPError

from app.db.models.ingestion_run import IngestionRun
from app.db.session import SessionLocal
from app.ingestion.lifecycle import (
    create_ingestion_run,
    ensure_data_source,
    mark_ingestion_run_failed,
    mark_ingestion_run_succeeded,
)
from app.ingestion.registry import get_source_registry
from app.ingestion.snapshots import write_local_snapshot
from app.logging import get_logger
from app.workers.celery_app import celery_app

LOGGER = get_logger(__name__)


@celery_app.task(name="app.workers.tasks.ingest.run_source_ingestion")
def run_source_ingestion(source_name: str) -> dict:
    registry = get_source_registry()
    if source_name not in registry:
        raise ValueError(f"Unknown source: {source_name}")

    async def _run() -> dict:
        adapter = registry[source_name]()
        with SessionLocal() as db:
            data_source = ensure_data_source(db, adapter)
            run = create_ingestion_run(db, data_source_id=data_source.id)
            run_id = run.id
        if hasattr(adapter, "run_id"):
            adapter.run_id = run_id

        LOGGER.info("source_ingestion_started", source_name=source_name, run_id=run_id)
        snapshot_uri = None
        try:
            records = await adapter.fetch()
            snapshot_uri = write_local_snapshot(source_name, records)
            result = await adapter.normalize(records)
            with SessionLocal() as db:
                run = db.get(IngestionRun, run_id)
                if run is None:
                    raise RuntimeError(f"Ingestion run disappeared: {run_id}")
                mark_ingestion_run_succeeded(
                    db,
                    run,
                    records_seen=result.records_seen,
                    records_created=result.records_created,
                    records_updated=result.records_updated,
                    records_rejected=result.records_rejected,
                    raw_snapshot_uri=result.raw_snapshot_uri or snapshot_uri,
                    metadata_json=result.metadata,
                )
            LOGGER.info(
                "source_ingestion_completed",
                source_name=source_name,
                run_id=run_id,
                records_seen=result.records_seen,
                records_rejected=result.records_rejected,
            )
            return {
                "source_name": source_name,
                "run_id": run_id,
                "records_seen": result.records_seen,
                "records_created": result.records_created,
                "records_updated": result.records_updated,
                "records_rejected": result.records_rejected,
                "raw_snapshot_uri": result.raw_snapshot_uri or snapshot_uri,
                "metadata": result.metadata,
            }
        except HTTPError as exc:
            error_summary = f"Upstream Census request failed: {exc}"
            with SessionLocal() as db:
                failed_run = db.get(IngestionRun, run_id)
                if failed_run is not None:
                    mark_ingestion_run_failed(db, failed_run, error_summary)
            LOGGER.exception("source_ingestion_failed", source_name=source_name, run_id=run_id)
            raise RuntimeError(error_summary) from exc
        except Exception as exc:
            error_summary = str(exc)[:1000]
            with SessionLocal() as db:
                failed_run = db.get(IngestionRun, run_id)
                if failed_run is not None:
                    mark_ingestion_run_failed(db, failed_run, error_summary)
            LOGGER.exception("source_ingestion_failed", source_name=source_name, run_id=run_id)
            raise

    return asyncio.run(_run())
