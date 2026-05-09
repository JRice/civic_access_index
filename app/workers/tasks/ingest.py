import asyncio

from app.ingestion.registry import get_source_registry
from app.ingestion.snapshots import write_local_snapshot
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.ingest.run_source_ingestion")
def run_source_ingestion(source_name: str) -> dict:
    registry = get_source_registry()
    if source_name not in registry:
        raise ValueError(f"Unknown source: {source_name}")

    async def _run() -> dict:
        adapter = registry[source_name]()
        records = await adapter.fetch()
        snapshot_uri = write_local_snapshot(source_name, records)
        result = await adapter.normalize(records)
        return {
            "source_name": source_name,
            "records_seen": result.records_seen,
            "records_created": result.records_created,
            "records_updated": result.records_updated,
            "records_rejected": result.records_rejected,
            "raw_snapshot_uri": result.raw_snapshot_uri or snapshot_uri,
            "metadata": result.metadata,
        }

    return asyncio.run(_run())

