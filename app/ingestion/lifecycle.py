from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models.ingestion_run import IngestionRun


def create_ingestion_run(db: Session, data_source_id: str | None = None) -> IngestionRun:
    run = IngestionRun(
        data_source_id=data_source_id,
        status="running",
        started_at=datetime.now(UTC),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def mark_ingestion_run_succeeded(
    db: Session,
    run: IngestionRun,
    *,
    records_seen: int,
    records_created: int,
    records_updated: int,
    records_rejected: int,
    raw_snapshot_uri: str | None,
    metadata_json: dict | None = None,
) -> IngestionRun:
    run.status = "succeeded" if records_rejected == 0 else "partial"
    run.completed_at = datetime.now(UTC)
    run.records_seen = records_seen
    run.records_created = records_created
    run.records_updated = records_updated
    run.records_rejected = records_rejected
    run.raw_snapshot_uri = raw_snapshot_uri
    run.metadata_json = metadata_json
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def mark_ingestion_run_failed(db: Session, run: IngestionRun, error_summary: str) -> IngestionRun:
    run.status = "failed"
    run.completed_at = datetime.now(UTC)
    run.error_summary = error_summary
    db.add(run)
    db.commit()
    db.refresh(run)
    return run

